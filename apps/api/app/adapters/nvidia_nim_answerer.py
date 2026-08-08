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
            extra_body={
                "guided_json": DraftAnswer.model_json_schema(),
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ValueError("NVIDIA NIM returned no structured answer")
        return DraftAnswer.model_validate_json(content)
