from __future__ import annotations

from openai import AsyncOpenAI

from app.adapters.openai_answerer import DraftAnswer, build_messages
from app.domain.schemas import QuestionRequest, SearchHit


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

    async def answer(self, request: QuestionRequest, hits: list[SearchHit]) -> DraftAnswer:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=build_messages(request, hits),  # type: ignore[arg-type]
            max_tokens=self.max_output_tokens,
            temperature=1.0,
            top_p=0.95,
            stream=False,
            extra_body={
                "guided_json": DraftAnswer.model_json_schema(),
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ValueError("NVIDIA NIM returned no structured answer")
        return DraftAnswer.model_validate_json(content)
