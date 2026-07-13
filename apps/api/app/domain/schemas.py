from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.catalog import SourceKind


class ProjectStage(StrEnum):
    PLANNING = "planning"
    PERMITTING = "permitting"
    CONSTRUCTION = "construction"
    OPERATION = "operation"
    CHANGE = "change"


class QuestionRequest(BaseModel):
    question: Annotated[str, Field(min_length=2, max_length=2000)]
    as_of_date: date = Field(default_factory=date.today)
    project_stage: ProjectStage = ProjectStage.PLANNING
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


class QuestionResponse(BaseModel):
    request_id: str
    mode: Literal["ai", "search_only"]
    summary: str
    scope: str
    sections: list[AnswerSection]
    checklist: list[ChecklistItem]
    citations: list[Citation]
    limitations: list[str]
    corpus_as_of: datetime | None = None


class CorpusItemStatus(BaseModel):
    title: str
    source_kind: SourceKind
    state: Literal["ready", "missing", "failed"]
    latest_effective_date: date | None = None


class CorpusStatus(BaseModel):
    last_successful_sync: datetime | None
    ai_available: bool
    source: Literal["국가법령정보 공동활용 Open API"] = "국가법령정보 공동활용 Open API"
    items: list[CorpusItemStatus]
    warnings: list[str]


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
