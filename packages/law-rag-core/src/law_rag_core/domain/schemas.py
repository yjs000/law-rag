from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from law_rag_core.domain.catalog import SourceKind

SEOUL_TIME_ZONE = timezone(timedelta(hours=9), name="Asia/Seoul")


def _korea_today() -> date:
    return datetime.now(SEOUL_TIME_ZONE).date()


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


class ConversationTurnContext(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    answer: Annotated[str, Field(min_length=1, max_length=12000)]


class QuestionRequest(BaseModel):
    client_request_id: UUID = Field(default_factory=uuid4)
    question: Annotated[str, Field(min_length=2, max_length=2000)]
    as_of_date: date = Field(default_factory=_korea_today)
    project_stage: ProjectStage = ProjectStage.PLANNING
    answer_mode: Literal["terra", "search_only"] = "terra"
    business_type: Annotated[str | None, Field(max_length=120)] = None
    facility_type: Annotated[str | None, Field(max_length=120)] = None
    conversation_id: UUID | None = None
    conversation_context: Annotated[list[ConversationTurnContext], Field(max_length=20)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_context_size(self) -> Self:
        # Conservative server-side guard for direct API clients. The model adapter
        # must still enforce its real tokenizer budget before generation.
        context_characters = len(self.question) + sum(
            len(turn.question) + len(turn.answer) for turn in self.conversation_context
        )
        if context_characters > 24_576:
            raise ValueError("conversation context exceeds the input budget")
        return self


class SearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=500)]
    as_of_date: date = Field(default_factory=_korea_today)
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
    conversation_id: UUID | None = None
    # 0025 M5 item 2, 2026-08-08 - MOCK/미확정: D-10 gold의 answerability 네 값과 이름을
    # 맞췄지만 app/domain/answer_actions.py의 파생 규칙 자체는 아직 D-10로 검증하지 않았다.
    # 하위 호환을 위해 optional로 추가했다 - 기존 클라이언트는 무시해도 된다.
    action: (
        Literal[
            "fully_answerable",
            "partially_answerable",
            "clarification_required",
            "unanswerable",
        ]
        | None
    ) = None
    # 0028 M4.5, 2026-08-08: 검색 전 라우팅 결과. app/domain/routing.py의 QuestionRoute와
    # 값을 맞췄지만(그 모듈은 app 계층이라 여기서 직접 import할 수 없어 리터럴을 복제했다),
    # `action`(D-10 answerability 4값)과는 다른 축이다 - route는 "검색을 실행해도 되는가",
    # action은 "생성된 답이 얼마나 완전한가"를 나타낸다. clarification_required라는 이름이
    # 우연히 겹치지만 서로 다른 필드다. legal_search 외 세 route는 검색·생성 없이 결정적
    # 응답으로 끝나므로 이때 action은 항상 None이다. 하위 호환을 위해 optional.
    route: (
        Literal[
            "legal_search",
            "clarification_required",
            "realtime_required",
            "external_document_required",
        ]
        | None
    ) = None


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
    conversation_id: UUID | None = None
    turn_index: int | None = None


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    turn_count: int
    last_turn_id: UUID


class ConversationPage(BaseModel):
    items: list[ConversationSummary]
    next_cursor: str | None = None
    has_more: bool = False


class ConversationTurnPage(BaseModel):
    items: list[QuestionHistoryEntry]
    next_cursor: str | None = None
    has_more: bool = False


class CorpusItemStatus(BaseModel):
    title: str
    source_kind: SourceKind
    state: Literal["ready", "missing", "failed"]
    latest_effective_date: date | None = None


class CorpusSearchStatus(BaseModel):
    ready: bool
    reason: str | None = None


class CorpusTemporalState(BaseModel):
    """Searchable corpus bounds and today's content identity."""

    ready: bool
    reason: str | None = None
    supported_as_of_from: date | None = None
    supported_as_of_through: date
    corpus_snapshot_id: str | None = None
    eligible_provision_count: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def ready_state_has_complete_bounds(self) -> Self:
        if not self.ready:
            if self.reason is None:
                raise ValueError("unready corpus temporal state requires a reason")
            return self
        if self.reason is not None:
            raise ValueError("ready corpus temporal state cannot have an unavailable reason")
        if self.supported_as_of_from is None or self.corpus_snapshot_id is None:
            raise ValueError("ready corpus temporal state requires bounds and snapshot identity")
        if self.supported_as_of_from > self.supported_as_of_through:
            raise ValueError("corpus temporal bounds are reversed")
        if self.eligible_provision_count == 0:
            raise ValueError("ready corpus temporal state requires an eligible population")
        return self


class CorpusStatus(BaseModel):
    last_successful_sync: datetime | None
    corpus_snapshot_id: str | None
    supported_as_of_from: date | None
    supported_as_of_through: date
    corpus_search_ready: bool
    corpus_search_unavailable_reason: str | None = None
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
