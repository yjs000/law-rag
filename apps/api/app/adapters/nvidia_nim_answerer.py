from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.adapters.openai_answerer import (
    ClarificationCoreDraft,
    ClarificationDraftAnswer,
    CoreDraft,
    DraftAnswer,
    build_blocked_route_messages,
    build_core_messages,
    build_messages,
    build_messages_v2,
)
from app.application.v2.grounding import ClarificationGrounding
from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.domain.routing import QuestionRoute
from app.domain.schemas import QuestionRequest, SearchHit
from app.provider_observability import (
    ProviderOperation,
    classify_provider_failure,
    emit_provider_attempt,
)

# Below this many remaining seconds, a retry can't realistically get a response
# back before the caller's own deadline (Vercel's function hard cap) hits, so
# it isn't worth starting.
_MIN_RETRY_SECONDS = 3.0
_NON_RETRYABLE_STATUS_CODES = {402, 429}

MessageBuilder = Callable[[QuestionRequest, list[SearchHit]], list[dict[str, str]]]
StructuredAnswer = TypeVar("StructuredAnswer", bound=BaseModel)


class NvidiaNimAnswerer:
    """NVIDIA hosted NIM adapter with a schema-validated legal answer boundary."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        max_attempts: int = 3,
        message_builder: MessageBuilder = build_messages,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("NVIDIA API key is required")
        if base_url != "https://integrate.api.nvidia.com/v1":
            raise ValueError("unsupported NVIDIA hosted NIM base URL")
        self.client: Any | None = None
        self._client_factory = client_factory or (
            lambda: AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=0,
            )
        )
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.message_builder = message_builder

    async def answer(
        self,
        request: QuestionRequest,
        hits: list[SearchHit],
        *,
        clarification: ClarificationGrounding | None = None,
    ) -> DraftAnswer:
        messages = (
            build_messages_v2(request, hits, clarification=clarification)
            if clarification is not None
            else self.message_builder(request, hits)
        )
        schema = ClarificationDraftAnswer if clarification is not None else DraftAnswer
        operation: ProviderOperation = (
            "clarification" if clarification is not None else "answer_detail"
        )
        return await self._generate(messages, schema, operation=operation)

    async def answer_core(
        self,
        request: QuestionRequest,
        hits: list[SearchHit],
        *,
        clarification: ClarificationGrounding | None = None,
    ) -> CoreDraft:
        schema = ClarificationCoreDraft if clarification is not None else CoreDraft
        messages = build_core_messages(request, hits, clarification=clarification)
        operation: ProviderOperation = (
            "clarification" if clarification is not None else "answer_core"
        )
        return await self._generate(messages, schema, operation=operation)

    async def answer_blocked_route(
        self, request: QuestionRequest, route: QuestionRoute, reason: str | None
    ) -> DraftAnswer:
        """0046: 사전 라우팅이 legal_search 밖으로 걸러낸 질문(embedding·검색 없음)에
        근거 없이 LLM을 호출한다 - `answer()`와 같은 재시도·타임아웃 정책을 그대로
        쓰되 프롬프트만 `build_blocked_route_messages`로 다르다."""
        return await self._generate(
            build_blocked_route_messages(request, route, reason),
            DraftAnswer,
            operation="answer_detail",
        )

    async def aclose(self) -> None:
        """Release the process-owned NVIDIA HTTP client."""

        if self.client is not None and hasattr(self.client, "close"):
            await self.client.close()

    async def _generate(
        self,
        messages: list[dict[str, str]],
        schema: type[StructuredAnswer],
        *,
        operation: ProviderOperation,
    ) -> StructuredAnswer:
        deadline = time.monotonic() + self.timeout_seconds
        attempt = 1
        task, attempt_started = await self._start_attempt(
            messages,
            schema,
            deadline=deadline,
            attempt_index=0,
        )
        if task is None or attempt_started is None:
            raise RuntimeError("initial provider attempt did not start")

        while True:
            try:
                result = await task
            except asyncio.CancelledError:
                finished_at = time.monotonic()
                emit_provider_attempt(
                    operation=operation,
                    attempt=attempt,
                    max_attempts=self.max_attempts,
                    outcome="failed",
                    failure_kind="cancelled",
                    upstream_status=None,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                )
                raise
            except Exception as exc:  # noqa: BLE001 - reclassified by status_code below
                finished_at = time.monotonic()
                failure_kind, upstream_status = classify_provider_failure(exc)
                remaining_after = deadline - finished_at
                retry_candidate = (
                    attempt < self.max_attempts
                    and getattr(exc, "status_code", None) not in _NON_RETRYABLE_STATUS_CODES
                    and remaining_after >= _MIN_RETRY_SECONDS
                )
                next_task: asyncio.Task[StructuredAnswer | None] | None = None
                next_attempt_started: float | None = None
                if retry_candidate:
                    # A synchronous sink can consume the remaining budget. Start the
                    # successor before announcing it so the event stays truthful.
                    next_task, next_attempt_started = await self._start_attempt(
                        messages,
                        schema,
                        deadline=deadline,
                        attempt_index=attempt,
                    )
                retry_scheduled = next_task is not None
                emit_provider_attempt(
                    operation=operation,
                    attempt=attempt,
                    max_attempts=self.max_attempts,
                    outcome="failed",
                    failure_kind=failure_kind,
                    upstream_status=upstream_status,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int(remaining_after * 1000), 0),
                    retry_scheduled=retry_scheduled,
                )
                if next_task is not None:
                    assert next_attempt_started is not None
                    task = next_task
                    attempt_started = next_attempt_started
                    attempt += 1
                    continue
                if failure_kind in {"provider_http", "timeout", "connection"}:
                    raise ProviderAttemptsExhausted(
                        failure_kind=failure_kind,
                        upstream_status=upstream_status,
                    ) from None
                raise
            else:
                finished_at = time.monotonic()
                emit_provider_attempt(
                    operation=operation,
                    attempt=attempt,
                    max_attempts=self.max_attempts,
                    outcome="succeeded",
                    failure_kind=None,
                    upstream_status=None,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                )
                return result

    async def _start_attempt(
        self,
        messages: list[dict[str, str]],
        schema: type[StructuredAnswer],
        *,
        deadline: float,
        attempt_index: int,
    ) -> tuple[asyncio.Task[StructuredAnswer | None] | None, float | None]:
        started = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(
            self._attempt_before_deadline(
                messages,
                schema,
                deadline=deadline,
                attempt_index=attempt_index,
                started=started,
            )
        )
        try:
            attempt_started = await started
        except BaseException:
            task.cancel()
            raise
        if attempt_started is None:
            assert await task is None
            return None, None
        return task, attempt_started

    async def _attempt_before_deadline(
        self,
        messages: list[dict[str, str]],
        schema: type[StructuredAnswer],
        *,
        deadline: float,
        attempt_index: int,
        started: asyncio.Future[float | None],
    ) -> StructuredAnswer | None:
        attempt_started = time.monotonic()
        remaining = deadline - attempt_started
        if attempt_index > 0 and remaining < _MIN_RETRY_SECONDS:
            started.set_result(None)
            return None

        started.set_result(attempt_started)
        attempt_timeout = max(remaining, _MIN_RETRY_SECONDS)
        timeout_at = asyncio.get_running_loop().time() + max(remaining, 0)
        async with asyncio.timeout_at(timeout_at):
            return await self._attempt(
                messages,
                schema,
                attempt_timeout=attempt_timeout,
            )

    async def _attempt(
        self,
        messages: list[dict[str, str]],
        schema: type[StructuredAnswer],
        *,
        attempt_timeout: float,
    ) -> StructuredAnswer:
        async with self._client_scope() as client:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=self.max_output_tokens,
                # TODO(2026-08-08, 0025 M5): 0.3은 잠정값이다. 원래 1.0이었는데 근거가 없었다
                # (git blame: 45edf43에서 설명 없이 하드코딩). 법률 답변처럼 재현성이 중요한
                # 출력에 맞춰 낮췄지만, D-10/E-10 실제 실행으로 검증 전까지는 확정이 아니다.
                # 검증 제안: D-10 10문항을 동결 문맥으로 온도 {0.0, 0.3, 0.7} 각각 3회씩 반복
                # 호출해 (1) 같은 온도 내 claim·citation·checklist status 변동률(재현성),
                # (2) gold answerability와의 일치율(품질)을 같이 본다. 재현성이 크게 나쁘지
                # 않은 선에서 가장 낮은 온도를 고르고, 0.3이 0.0보다 유의미하게 나은 품질을
                # 못 보이면 0.0으로 낮춘다. E1(pilot 50문항) 전에 확정한다.
                temperature=0.3,
                top_p=0.95,
                stream=False,
                timeout=attempt_timeout,
                extra_body={
                    "guided_json": schema.model_json_schema(),
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ValueError("NVIDIA NIM returned no structured answer")
        return schema.model_validate_json(content)

    @asynccontextmanager
    async def _client_scope(self) -> AsyncIterator[Any]:
        if self.client is not None:
            yield self.client
            return
        client = self._client_factory()
        try:
            yield client
        finally:
            await client.close()
