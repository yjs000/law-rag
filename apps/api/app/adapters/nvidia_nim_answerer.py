from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.adapters.openai_answerer import (
    CoreDraft,
    DraftAnswer,
    build_blocked_route_messages,
    build_core_messages,
    build_messages,
)
from app.domain.routing import QuestionRoute
from app.domain.schemas import QuestionRequest, SearchHit

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
    ) -> None:
        if not api_key:
            raise ValueError("NVIDIA API key is required")
        if base_url != "https://integrate.api.nvidia.com/v1":
            raise ValueError("unsupported NVIDIA hosted NIM base URL")
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.message_builder = message_builder

    async def answer(self, request: QuestionRequest, hits: list[SearchHit]) -> DraftAnswer:
        return await self._generate(self.message_builder(request, hits), DraftAnswer)

    async def answer_core(self, request: QuestionRequest, hits: list[SearchHit]) -> CoreDraft:
        return await self._generate(build_core_messages(request, hits), CoreDraft)

    async def answer_blocked_route(
        self, request: QuestionRequest, route: QuestionRoute, reason: str | None
    ) -> DraftAnswer:
        """0046: 사전 라우팅이 legal_search 밖으로 걸러낸 질문(embedding·검색 없음)에
        근거 없이 LLM을 호출한다 - `answer()`와 같은 재시도·타임아웃 정책을 그대로
        쓰되 프롬프트만 `build_blocked_route_messages`로 다르다."""
        return await self._generate(
            build_blocked_route_messages(request, route, reason), DraftAnswer
        )

    async def aclose(self) -> None:
        """Release the process-owned NVIDIA HTTP client."""

        await self.client.close()

    async def _generate(
        self, messages: list[dict[str, str]], schema: type[StructuredAnswer]
    ) -> StructuredAnswer:
        deadline = time.monotonic() + self.timeout_seconds
        last_error: Exception
        for attempt in range(self.max_attempts):
            remaining = deadline - time.monotonic()
            if attempt > 0 and remaining < _MIN_RETRY_SECONDS:
                break
            try:
                attempt_timeout = max(remaining, _MIN_RETRY_SECONDS)
                async with asyncio.timeout(max(remaining, 0)):
                    return await self._attempt(messages, schema, attempt_timeout=attempt_timeout)
            except Exception as exc:  # noqa: BLE001 - reclassified by status_code below
                last_error = exc
                if getattr(exc, "status_code", None) in _NON_RETRYABLE_STATUS_CODES:
                    raise
        raise last_error

    async def _attempt(
        self,
        messages: list[dict[str, str]],
        schema: type[StructuredAnswer],
        *,
        attempt_timeout: float,
    ) -> StructuredAnswer:
        response = await self.client.chat.completions.create(
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
