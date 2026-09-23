"""LLM-based free-text continuation extractor for clarification turns."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from openai import AsyncOpenAI

from app.adapters.nvidia_nim_clarification import build_continuation_extraction_messages
from app.application.clarification_workflow import ClarificationTurnJudgment
from app.domain.clarification import RequiredFact
from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.provider_observability import (
    classify_provider_failure,
    emit_provider_attempt,
    provider_attempt_scope,
)
from app.runtime_observability import ErrorLogMode


class LlmClarificationContinuationExtractor:
    """Extract answered facts from a free-text continuation via guided JSON."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        error_log_mode: ErrorLogMode = "redacted",
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("NVIDIA API key is required")
        if base_url != "https://integrate.api.nvidia.com/v1":
            raise ValueError("unsupported NVIDIA hosted NIM base URL")
        self.client = (client_factory or (
            lambda: AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=0,
            )
        ))()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.error_log_mode = error_log_mode

    async def extract_continuation(
        self,
        *,
        original_question: str,
        unresolved_facts: tuple[RequiredFact, ...],
        user_text: str,
    ) -> ClarificationTurnJudgment:
        with provider_attempt_scope():
            deadline = time.monotonic() + self.timeout_seconds
            attempt_started = time.monotonic()
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=build_continuation_extraction_messages(
                        original_question=original_question,
                        unresolved_facts=unresolved_facts,
                        user_text=user_text,
                    ),
                    max_tokens=700,
                    temperature=0.0,
                    stream=False,
                    extra_body={
                        "guided_json": ClarificationTurnJudgment.model_json_schema(),
                        "chat_template_kwargs": {"enable_thinking": False},
                    },
                )
                result = ClarificationTurnJudgment.model_validate_json(_content(response))
            except asyncio.CancelledError as exc:
                finished_at = time.monotonic()
                emit_provider_attempt(
                    operation="clarification",
                    model=self.model,
                    timeout_ms=max(round(self.timeout_seconds * 1000), 1),
                    attempt=1,
                    max_attempts=1,
                    outcome="failed",
                    failure_kind="cancelled",
                    upstream_status=None,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                    error=exc,
                    mode=self.error_log_mode,
                )
                raise
            except Exception as exc:  # noqa: BLE001 - classified without provider data
                finished_at = time.monotonic()
                failure_kind, upstream_status = classify_provider_failure(exc)
                emit_provider_attempt(
                    operation="clarification",
                    model=self.model,
                    timeout_ms=max(round(self.timeout_seconds * 1000), 1),
                    attempt=1,
                    max_attempts=1,
                    outcome="failed",
                    failure_kind=failure_kind,
                    upstream_status=upstream_status,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                    error=exc,
                    mode=self.error_log_mode,
                )
                if failure_kind in {"provider_http", "timeout", "connection"}:
                    raise ProviderAttemptsExhausted(
                        failure_kind=failure_kind,
                        upstream_status=upstream_status,
                    ) from None
                raise
            else:
                finished_at = time.monotonic()
                emit_provider_attempt(
                    operation="clarification",
                    model=self.model,
                    timeout_ms=max(round(self.timeout_seconds * 1000), 1),
                    attempt=1,
                    max_attempts=1,
                    outcome="succeeded",
                    failure_kind=None,
                    upstream_status=None,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                    mode=self.error_log_mode,
                )
                return result

    async def aclose(self) -> None:
        await self.client.close()


def _content(response: object) -> str:
    choices = getattr(response, "choices", ())
    content = getattr(getattr(choices[0], "message", None), "content", None) if choices else None
    if not content:
        raise ValueError("NVIDIA NIM returned no continuation extraction result")
    return content
