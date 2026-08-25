from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from law_rag_core.domain.catalog import SourceKind

    # 한국 표준시(UTC+9)를 나타내는 시간대 상수.
SEOUL_TIME_ZONE = timezone(timedelta(hours=9), name="Asia/Seoul")


def _korea_today() -> date:
    return datetime.now(SEOUL_TIME_ZONE).date()


class ProjectStage(StrEnum):
    # 사업·시설 계획을 수립하는 단계.
    PLANNING = "planning"
    # 인허가를 신청하거나 심사받는 단계.
    PERMITTING = "permitting"
    # 공사·시공을 수행하는 단계.
    CONSTRUCTION = "construction"
    # 완공 후 시설을 운영하는 단계.
    OPERATION = "operation"
    # 기존 사업·시설의 변경을 검토하는 단계.
    CHANGE = "change"


class AnswerMode(StrEnum):
    # 검색 근거를 바탕으로 AI가 서술형 답변을 생성함.
    AI = "ai"
    # AI 생성 없이 검색 결과만 반환함.
    SEARCH_ONLY = "search_only"


class AiFailureCategory(StrEnum):
    # AI 기능이 설정상 비활성화됨.
    DISABLED = "disabled"
    # 사용량 한도에 도달함.
    QUOTA = "quota"
    # API 인증 또는 권한 확인에 실패함.
    AUTHORIZATION = "authorization"
    # 요청한 모델을 사용할 수 없음.
    MODEL_UNAVAILABLE = "model_unavailable"
    # 모델 출력이 형식 또는 검증 조건을 충족하지 못함.
    INVALID_OUTPUT = "invalid_output"
    # 그 밖의 실행 중 오류가 발생함.
    RUNTIME = "runtime"


class AiFallbackReason(StrEnum):
    """Public, non-sensitive reason why a Terra request returned search-only results."""

    # AI 기능이 비활성화되어 검색 전용으로 처리함.
    AI_DISABLED = "ai_disabled"
    # AI 사용량 한도를 모두 소진함.
    QUOTA_EXHAUSTED = "quota_exhausted"
    # 청구 또는 사용량 관련 오류가 발생함.
    BILLING_OR_QUOTA_ERROR = "billing_or_quota_error"
    # 검색 임베딩 생성 또는 조회에 실패함.
    EMBEDDING_ERROR = "embedding_error"
    # 답변 텍스트 생성에 실패함.
    GENERATION_ERROR = "generation_error"
    # 생성된 답변이 인용 근거 조건을 충족하지 못함.
    GROUNDING_FAILED = "grounding_failed"
    # 답변을 만들 수 있는 검색 근거가 없음.
    NO_EVIDENCE = "no_evidence"


class AiRuntimeState(BaseModel):
    """Terra 이외 생성 모델로 자동 전환하지 않는 런타임 계약."""

    # 응답 또는 런타임에서 실제로 선택된 처리 방식.
    mode: AnswerMode
    # 요청에 사용할 생성 모델 식별자.
    requested_model: Literal["gpt-5.6-terra"] = "gpt-5.6-terra"
    # AI 처리에 실패했을 때의 내부 원인 분류.
    failure_category: AiFailureCategory | None = None

    def model_post_init(self, __context: object) -> None:
        if self.mode is AnswerMode.AI and self.failure_category is not None:
            raise ValueError("AI 모드에는 실패 분류를 지정할 수 없습니다")
        if self.mode is AnswerMode.SEARCH_ONLY and self.failure_category is None:
            raise ValueError("검색 전용 모드에는 실패 분류가 필요합니다")


class ConversationTurnContext(BaseModel):
    # 사용자가 입력한 법률 질의 또는 이전 대화의 질문.
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    # 질의에 대해 반환된 답변.
    answer: Annotated[str, Field(min_length=1, max_length=12000)]


class QuestionRequest(BaseModel):
    # 클라이언트가 중복 요청을 구분하기 위해 부여한 ID.
    client_request_id: UUID = Field(default_factory=uuid4)
    # 사용자가 입력한 법률 질의 또는 이전 대화의 질문.
    question: Annotated[str, Field(min_length=2, max_length=2000)]
    # 법령의 효력을 판단하는 기준일.
    as_of_date: date = Field(default_factory=_korea_today)
    # 질의 대상 프로젝트의 진행 단계.
    project_stage: ProjectStage = ProjectStage.PLANNING
    # 클라이언트가 요청한 답변 방식.
    answer_mode: Literal["terra", "search_only"] = "terra"
    # 질의와 관련된 업종.
    business_type: Annotated[str | None, Field(max_length=120)] = None
    # 질의와 관련된 시설 유형.
    facility_type: Annotated[str | None, Field(max_length=120)] = None
    # 연결된 대화를 식별하는 ID.
    conversation_id: UUID | None = None
    # 현재 답변에 참고할 이전 질문·답변 목록.
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
    # 검색할 키워드 또는 자연어 질의.
    query: Annotated[str, Field(min_length=1, max_length=500)]
    # 법령의 효력을 판단하는 기준일.
    as_of_date: date = Field(default_factory=_korea_today)
    # 검색 범위를 제한할 법률 자료 종류.
    source_kinds: list[SourceKind] = Field(default_factory=list)
    # 반환할 최대 검색 결과 수.
    limit: Annotated[int, Field(ge=1, le=30)] = 10


class Citation(BaseModel):
    # 해당 엔터티의 고유 식별자.
    id: str
    # 조문 또는 판례 조항 레코드의 ID.
    provision_id: UUID
    # 원문 법령·판례 문서의 제목.
    document_title: str
    # 문서 버전을 표시하는 값.
    version_label: str
    # 문서 안의 조문 위치를 나타내는 경로.
    path: str
    # 답변 근거로 제시할 원문 발췌문.
    quote: str
    # 원문을 확인할 수 있는 출처 URL.
    source_url: str
    # 법률 자료의 종류.
    source_kind: SourceKind
    # 법령 유형을 구분하는 코드.
    law_type_code: str | None = None


class SearchHit(BaseModel):
    # 조문 또는 판례 조항 레코드의 ID.
    provision_id: UUID
    # 원문 문서의 ID.
    document_id: UUID
    # 원문 법령·판례 문서의 제목.
    document_title: str
    # 법률 자료의 종류.
    source_kind: SourceKind
    # 문서 버전을 표시하는 값.
    version_label: str
    # 이 문서 버전의 효력 시작일.
    effective_from: date | None
    # 이 문서 버전의 효력 종료일.
    effective_to: date | None
    # 문서 안의 조문 위치를 나타내는 경로.
    path: str
    # 조문 제목 또는 소제목.
    heading: str | None = None
    # 검색에 일치한 원문 내용.
    content: str
    # 원문을 확인할 수 있는 출처 URL.
    source_url: str
    # 질의와의 관련도 점수.
    score: float = 0
    # 법령 유형을 구분하는 코드.
    law_type_code: str | None = None


class AnswerSection(BaseModel):
    # 법률 근거로 뒷받침되는 핵심 주장.
    claim: str
    # 주장의 적용 범위와 해석을 풀어 쓴 설명.
    explanation: str
    # 이 항목의 근거가 되는 Citation.id 목록.
    citation_ids: list[str]


class ChecklistItem(BaseModel):
    # 사용자에게 표시할 점검 항목 설명.
    label: str
    # 점검 항목의 의무·적용 상태.
    status: Literal["required", "conditional", "check", "not_applicable"]
    # 이 항목의 근거가 되는 Citation.id 목록.
    citation_ids: list[str]


class ChecklistExportFormat(StrEnum):
    # Markdown 문서 형식.
    MARKDOWN = "md"
    # 쉼표로 구분한 표 형식.
    CSV = "csv"
    # PDF 문서 형식.
    PDF = "pdf"


class ChecklistDocument(BaseModel):
    # 문서·대화·자료를 표시하는 제목.
    title: str
    # 법령의 효력을 판단하는 기준일.
    as_of_date: date
    # 질의 대상 프로젝트의 진행 단계.
    project_stage: ProjectStage
    # 현재 응답 또는 문서에 포함된 항목 목록.
    items: list[ChecklistItem]
    # 답변 또는 항목의 근거가 되는 인용 목록.
    citations: list[Citation]


class QuestionResponse(BaseModel):
    # 서버가 발급한 요청 처리 ID.
    request_id: str
    # 응답 또는 런타임에서 실제로 선택된 처리 방식.
    mode: AnswerMode
    # 답변 전체를 짧게 요약한 내용.
    summary: str
    # 답변이 다루는 사실관계와 적용 범위.
    scope: str
    # 근거와 함께 제시하는 세부 답변 단락 목록.
    sections: list[AnswerSection]
    # 사용자가 후속으로 확인할 체크리스트.
    checklist: list[ChecklistItem]
    # 답변 또는 항목의 근거가 되는 인용 목록.
    citations: list[Citation]
    # 검색 범위 또는 근거 부족 등 답변의 한계.
    limitations: list[str]
    # 검색에 사용한 코퍼스의 기준 시각.
    corpus_as_of: datetime | None = None
    # 검색 결과 존재 여부.
    result_status: Literal["results", "no_results"] = "results"
    # 검색 결과가 없을 때의 사유.
    no_results_reason: Literal["requested_path_not_found", "no_matching_evidence"] | None = None
    # 클라이언트가 요청한 응답 방식.
    requested_answer_mode: Literal["terra", "search_only"] = "search_only"
    # AI 요청이 검색 전용으로 처리된 공개용 사유.
    fallback_reason: AiFallbackReason | None = None
    # 연결된 대화를 식별하는 ID.
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
    # 우연히 겹치지만 서로 다른 필드다. legal_search 외 route는 검색 없이 안내 또는
    # 안전한 unanswerable 응답으로 끝난다. 하위 호환을 위해 optional.
    route: (
        Literal[
            "legal_search",
            "clarification_required",
            "realtime_required",
            "external_document_required",
            "routing_unavailable",
        ]
        | None
    ) = None


class MockUser(BaseModel):
    # 해당 엔터티의 고유 식별자.
    id: UUID
    # 로그인 및 식별에 사용하는 이메일 주소.
    email: str
    # 화면에 표시할 사용자 이름.
    display_name: str
    # 인증에 사용한 제공자.
    auth_provider: Literal["google"] = "google"
    # 해당 레코드가 생성된 시각.
    created_at: datetime


class QuestionHistoryEntry(BaseModel):
    # 해당 엔터티의 고유 식별자.
    id: UUID
    # 이력을 소유한 사용자 ID.
    user_id: UUID
    # 사용자가 제출한 원래 질의.
    request: QuestionRequest
    # 질의 처리 결과.
    response: QuestionResponse
    # 해당 레코드가 생성된 시각.
    created_at: datetime
    # 개인정보 보존 정책에 따라 이력이 만료되는 시각.
    expires_at: datetime
    # 연결된 대화를 식별하는 ID.
    conversation_id: UUID | None = None
    # 대화 안에서 이 차례의 순서.
    turn_index: int | None = None


class ConversationSummary(BaseModel):
    # 해당 엔터티의 고유 식별자.
    id: UUID
    # 문서·대화·자료를 표시하는 제목.
    title: str
    # 해당 레코드가 생성된 시각.
    created_at: datetime
    # 마지막으로 갱신된 시각.
    updated_at: datetime
    # 대화에 저장된 질문·답변 차례 수.
    turn_count: int
    # 가장 최근 대화 이력의 ID.
    last_turn_id: UUID


class ConversationPage(BaseModel):
    # 현재 응답 또는 문서에 포함된 항목 목록.
    items: list[ConversationSummary]
    # 다음 페이지를 요청할 때 사용할 커서.
    next_cursor: str | None = None
    # 뒤에 더 가져올 페이지가 있는지.
    has_more: bool = False


class ConversationTurnPage(BaseModel):
    # 현재 응답 또는 문서에 포함된 항목 목록.
    items: list[QuestionHistoryEntry]
    # 다음 페이지를 요청할 때 사용할 커서.
    next_cursor: str | None = None
    # 뒤에 더 가져올 페이지가 있는지.
    has_more: bool = False


class CorpusItemStatus(BaseModel):
    # 문서·대화·자료를 표시하는 제목.
    title: str
    # 법률 자료의 종류.
    source_kind: SourceKind
    # 자료 또는 수집 작업의 현재 상태.
    state: Literal["ready", "missing", "failed"]
    # 확보한 버전 중 가장 최신 효력 발생일.
    latest_effective_date: date | None = None


class CorpusSearchStatus(BaseModel):
    # 현재 기능 또는 코퍼스를 사용할 준비가 되었는지.
    ready: bool
    # 현재 상태 또는 처리 결과의 사유.
    reason: str | None = None


class CorpusTemporalState(BaseModel):
    """Searchable corpus bounds and today's content identity."""

    # 현재 기능 또는 코퍼스를 사용할 준비가 되었는지.
    ready: bool
    # 현재 상태 또는 처리 결과의 사유.
    reason: str | None = None
    # 지원하는 기준일 범위의 시작일.
    supported_as_of_from: date | None = None
    # 지원하는 기준일 범위의 마지막 날.
    supported_as_of_through: date
    # 현재 코퍼스 스냅샷 식별자.
    corpus_snapshot_id: str | None = None
    # 기준일 범위에서 검색 가능한 조문 수.
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
    # 마지막으로 코퍼스 동기화에 성공한 시각.
    last_successful_sync: datetime | None
    # 현재 코퍼스 스냅샷 식별자.
    corpus_snapshot_id: str | None
    # 지원하는 기준일 범위의 시작일.
    supported_as_of_from: date | None
    # 지원하는 기준일 범위의 마지막 날.
    supported_as_of_through: date
    # 법률 코퍼스를 검색할 수 있는지.
    corpus_search_ready: bool
    # 검색이 불가능할 때의 사유.
    corpus_search_unavailable_reason: str | None = None
    # AI 답변 생성 기능을 사용할 수 있는지.
    ai_available: bool
    # AI를 사용할 수 없을 때의 공개용 사유.
    ai_unavailable_reason: Literal["ai_disabled", "quota_exhausted"] | None = None
    # 코퍼스의 법률 원문 제공 출처.
    source: Literal["국가법령정보 공동활용 Open API"] = "국가법령정보 공동활용 Open API"
    # 현재 응답 또는 문서에 포함된 항목 목록.
    items: list[CorpusItemStatus]
    # 상태 확인 중 발견한 비치명적 경고 목록.
    warnings: list[str]


class IngestionResult(BaseModel):
    # 문서·대화·자료를 표시하는 제목.
    title: str
    # 자료 또는 수집 작업의 현재 상태.
    state: Literal["ready", "unchanged", "failed", "unsupported"]
    # 실제로 사용한 외부 API 응답 형식.
    wire_format: Literal["JSON", "XML"] | None = None
    # AI 요청이 검색 전용으로 처리된 공개용 사유.
    fallback_reason: str | None = None
    # 수집 결과에 덧붙이는 세부 설명 또는 오류 요약.
    detail: str | None = None
    # 출처 시스템에서 부여한 문서 식별자.
    source_id: str | None = None
    # 국가법령정보 공동활용 API의 법령 마스터 식별자.
    mst: str | None = None


class ProvisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # 요청한 조문 검색 결과.
    hit: SearchHit
    # 상위 조문으로 이어지는 경로.
    parent_path: str | None = None
    # 하위 조문으로 이어지는 경로 목록.
    child_paths: list[str] = Field(default_factory=list)


class ChangeItem(BaseModel):
    # 문서 안의 조문 위치를 나타내는 경로.
    path: str
    # 변경 종류: 추가, 삭제, 수정.
    change_type: Literal["added", "removed", "modified"]
    # 변경 전 원문.
    before: str | None = None
    # 변경 후 원문.
    after: str | None = None


class DocumentChangesResponse(BaseModel):
    # 원문 문서의 ID.
    document_id: UUID
    # 비교 범위의 시작 기준일.
    from_date: date
    # 비교 범위의 끝 기준일.
    to_date: date
    # 발견된 조문 변경 사항 목록.
    changes: list[ChangeItem]
    # 해당 문서가 변경 비교를 지원하는지.
    supported: bool = True
    # 비교를 지원하지 않거나 결과가 제한적일 때의 설명.
    message: str | None = None
