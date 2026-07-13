from pydantic import BaseModel, Field

from app.domain.schemas import AnswerSection, ChecklistItem, QuestionRequest, SearchHit


class DraftAnswer(BaseModel):
    summary: str
    scope: str
    sections: list[AnswerSection]
    checklist: list[ChecklistItem]
    limitations: list[str] = Field(default_factory=list)


class OpenAIAnswerer:
    def __init__(self, *, api_key: str, model: str) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def answer(self, request: QuestionRequest, hits: list[SearchHit]) -> DraftAnswer:
        evidence = "\n\n".join(
            f"[C{index}] {hit.document_title} {hit.path} ({hit.version_label})\n{hit.content}"
            for index, hit in enumerate(hits, 1)
        )
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "당신은 분산에너지 법령 조사 보조자다. 제공된 근거만 사용한다. "
                        "모든 실질 주장에는 존재하는 C번호를 붙인다. "
                        "근거가 부족하면 한계로 명시한다."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"질문: {request.question}\n기준일: {request.as_of_date}\n"
                        f"사업단계: {request.project_stage.value}\n\n근거:\n{evidence}"
                    ),
                },
            ],
            text_format=DraftAnswer,
        )
        if response.output_parsed is None:
            raise ValueError("구조화 답변이 없습니다")
        return response.output_parsed


def validate_draft(draft: DraftAnswer, hit_count: int) -> bool:
    valid = {f"C{index}" for index in range(1, hit_count + 1)}
    claims = [*draft.sections, *draft.checklist]
    return bool(claims) and all(
        item.citation_ids and set(item.citation_ids) <= valid for item in claims
    )
