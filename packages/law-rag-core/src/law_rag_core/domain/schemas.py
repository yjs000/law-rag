from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from law_rag_core.domain.catalog import SourceKind


class ProjectStage(StrEnum):
    PLANNING = "planning"
    PERMITTING = "permitting"
    CONSTRUCTION = "construction"
    OPERATION = "operation"
    CHANGE = "change"


class AnswerMode(StrEnum):
    AI = "ai"
    SEARCH_ONLY = "search_only"


class AiFailureCategory(StrEnum):
    DISABLED = "disabled"
    QUOTA = "quota"
    AUTHORIZATION = "authorization"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_OUTPUT = "invalid_output"
    RUNTIME = "runtime"


class AiFallbackReason(StrEnum):
    """Public, non-sensitive reason why a Terra request returned search-only results."""

    AI_DISABLED = "ai_disabled"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BILLING_OR_QUOTA_ERROR = "billing_or_quota_error"
    EMBEDDING_ERROR = "embedding_error"
    GENERATION_ERROR = "generation_error"
    GROUNDING_FAILED = "grounding_failed"
    NO_EVIDENCE = "no_evidence"


class AiRuntimeState(BaseModel):
    """Terra 이외 생성 모델로 자동 전환하지 않는 런타임 계약."""

    mode: AnswerMode
    requested_model: Literal["gpt-5.6-terra"] = "gpt-5.6-terra"
    failure_category: AiFailureCategory | None = None

    def model_post_init(self, __context: object) -> None:
        if self.mode is AnswerMode.AI and self.failure_category is not None:
            raise ValueError("AI 모드에는 실패 분류를 지정할 수 없습니다")
        if self.mode is AnswerMode.SEARCH_ONLY and self.failure_category is None:
            raise ValueError("검색 전용 모드에는 실패 분류가 필요합니다")


class QuestionRequest(BaseModel):
    question: Annotated[str, Field(min_length=2, max_length=2000)]
    as_of_date: date = Field(default_factory=date.today)
    project_stage: ProjectStage = ProjectStage.PLANNING
    answer_mode: Literal["terra", "search_only"] = "terra"
    business_type: Annotated[str | None, Field(max_length=120)] = None
    facility_type: Annotated[str | None, Field(max_length=120)] = None


class SearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=500)]
    as_of_date: date = Field(default_factory=date.today)
    source_kinds: list[SourceKind] = Field(default_factory=list)
    limit: Annotated[int, Field(ge=1, le=30)] = 10


class Citation(BaseModel):
    id: str
    provision_id: UUID
    document_title: str
    version_label: str
    path: str
    quote: str
    source_url: str


class SearchHit(BaseModel):
    provision_id: UUID
    document_id: UUID
    document_title: str
    source_kind: SourceKind
    version_label: str
    effective_from: date | None
    effective_to: date | None
    path: str
    heading: str | None = None
    content: str
    source_url: str
    score: float = 0


class AnswerSection(BaseModel):
    claim: str
    explanation: str
    citation_ids: list[str]


class ChecklistItem(BaseModel):
    label: str
    status: Literal["required", "conditional", "check", "not_applicable"]
    citation_ids: list[str]


class ChecklistExportFormat(StrEnum):
    MARKDOWN = "md"
    CSV = "csv"
    PDF = "pdf"


class ChecklistDocument(BaseModel):
    title: str
    as_of_date: date
    project_stage: ProjectStage
    items: list[ChecklistItem]
    citations: list[Citation]


class QuestionResponse(BaseModel):
    request_id: str
    mode: AnswerMode
    summary: str
    scope: str
    sections: list[AnswerSection]
    checklist: list[ChecklistItem]
    citations: list[Citation]
    limitations: list[str]
    corpus_as_of: datetime | None = None
    result_status: Literal["results", "no_results"] = "results"
    no_results_reason: Literal["requested_path_not_found", "no_matching_evidence"] | None = None
    requested_answer_mode: Literal["terra", "search_only"] = "search_only"
    fallback_reason: AiFallbackReason | None = None


class MockUser(BaseModel):
    id: UUID
    email: str
    display_name: str
    auth_provider: Literal["google"] = "google"
    created_at: datetime


class QuestionHistoryEntry(BaseModel):
    id: UUID
    user_id: UUID
    request: QuestionRequest
    response: QuestionResponse
    created_at: datetime
    expires_at: datetime


class CorpusItemStatus(BaseModel):
    title: str
    source_kind: SourceKind
    state: Literal["ready", "missing", "failed"]
    latest_effective_date: date | None = None


class CorpusStatus(BaseModel):
    last_successful_sync: datetime | None
    ai_available: bool
    ai_unavailable_reason: Literal["ai_disabled", "quota_exhausted"] | None = None
    source: Literal["국가법령정보 공동활용 Open API"] = "국가법령정보 공동활용 Open API"
    items: list[CorpusItemStatus]
    warnings: list[str]


class IngestionResult(BaseModel):
    title: str
    state: Literal["ready", "unchanged", "failed", "unsupported"]
    wire_format: Literal["JSON", "XML"] | None = None
    fallback_reason: str | None = None
    detail: str | None = None
    source_id: str | None = None
    mst: str | None = None


class ProvisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hit: SearchHit
    parent_path: str | None = None
    child_paths: list[str] = Field(default_factory=list)


class ChangeItem(BaseModel):
    path: str
    change_type: Literal["added", "removed", "modified"]
    before: str | None = None
    after: str | None = None


class DocumentChangesResponse(BaseModel):
    document_id: UUID
    from_date: date
    to_date: date
    changes: list[ChangeItem]
    supported: bool = True
    message: str | None = None
