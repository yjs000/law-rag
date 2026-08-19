from typing import Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    route: Literal[
        "legal_search",
        "clarification_required",
        "realtime_required",
        "external_document_required",
    ]
    reason: str = Field(description="이 라우팅으로 판단한 근거를 한두 문장으로 설명")


class GenerationResult(BaseModel):
    answer: str = Field(description="근거 조문에 기반한 답변 초안")
    citation_ids: list[str] = Field(description="답변에서 실제로 인용한 근거 ID 목록")
    action: Literal[
        "fully_answerable", "partially_answerable", "clarification_required", "unanswerable"
    ]
