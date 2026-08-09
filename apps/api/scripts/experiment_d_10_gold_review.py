"""Build and validate a user-reviewed full-corpus Gold candidate for D-10."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

from law_rag_core.persistence import PARSER_SCHEMA_VERSION
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.settings import get_settings
from scripts.evaluate_experiment_d_gold import PostgresExperimentDBackend
from scripts.experiment_d_10_frozen_contract import load_frozen_contract
from scripts.experiment_d_gold_contract import canonical_provision_id_set_sha256
from scripts.experiment_d_manual_review import _validate_snapshot
from scripts.experiment_d_manual_review_contract import (
    DEFAULT_APPROVAL_MANIFEST,
    DEFAULT_SOURCE_BANK,
    load_manual_pilot_artifacts,
)
from scripts.experiment_d_pilot_contract import canonical_json_sha256

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "experiments" / "d_gold_10" / "experiment-d-10-gold-contract.json"
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Answerability = Literal[
    "fully_answerable",
    "partially_answerable",
    "clarification_required",
    "unanswerable",
]
ExpectedAction = Literal[
    "answer",
    "partial_answer_with_limits",
    "ask_clarifying_question",
    "insufficient_evidence",
]
FacetStatus = Literal["supported", "unsupported", "needs_clarification"]


class D10GoldReviewError(ValueError):
    """Raised when a D-10 Gold draft is incomplete or not reproducible."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactBinding(StrictModel):
    path: NonBlankStr
    file_sha256: Sha256


class CorpusBinding(StrictModel):
    as_of_date: Literal["2026-08-05"]
    corpus_snapshot_id: Literal[
        "corpus-sha256:605b1f53b4fbe3edff19000796e56d906415e7648e7e6ae6119a46f5fc8d9578"
    ]
    corpus_population_fingerprint_sha256: Literal[
        "b0bef0c04b2f85d5197a1dbf1e29166a7cea0e1e0fa8becc5be6c6b1cf54da6e"
    ]
    eligible_provision_count: Literal[3066]
    parser_contract_version: NonBlankStr


class D10GoldWorkflowContract(StrictModel):
    schema_version: Literal[1]
    experiment: Literal["D-10-GOLD-V1"]
    artifact_class: Literal["d10_full_corpus_gold_workflow_contract"]
    status: Literal["annotation_workflow_locked"]
    question_input_binding: ArtifactBinding
    frozen_calibration_binding: ArtifactBinding
    corpus_binding: CorpusBinding
    expected_case_count: Literal[10]
    expected_total_judgment_count: Literal[30660]
    relevance_scale: dict[Literal["0", "1", "2"], NonBlankStr]
    forbidden_annotation_input_fields: list[NonBlankStr]
    prohibited_claims_before_seal: list[NonBlankStr]
    output_root: NonBlankStr
    workflow_contract_payload_sha256: Sha256

    @model_validator(mode="after")
    def scale_and_counts_are_consistent(self) -> D10GoldWorkflowContract:
        if set(self.relevance_scale) != {"0", "1", "2"}:
            raise ValueError("relevance scale must define exactly 0, 1, and 2")
        expected = self.expected_case_count * self.corpus_binding.eligible_provision_count
        if self.expected_total_judgment_count != expected:
            raise ValueError("total judgment count does not match case and corpus counts")
        if len(set(self.forbidden_annotation_input_fields)) != len(
            self.forbidden_annotation_input_fields
        ):
            raise ValueError("forbidden annotation fields must be unique")
        return self


class ProposedFacet(StrictModel):
    facet_id: NonBlankStr
    claim: NonBlankStr
    status: FacetStatus
    status_reason: NonBlankStr


class ProposedPositiveJudgment(StrictModel):
    provision_id: NonBlankStr
    relevance: Literal[1, 2]
    facet_ids: list[NonBlankStr] = Field(min_length=1)
    evidence_scope: Literal["leaf", "subtree", "article"]
    rationale: NonBlankStr


class ProposedReferenceResponse(StrictModel):
    action: ExpectedAction
    text: NonBlankStr
    cited_provision_ids: list[NonBlankStr]


class ProposedCase(StrictModel):
    case_id: NonBlankStr
    answerability: Answerability
    expected_action: ExpectedAction
    missing_user_facts: list[NonBlankStr]
    insufficient_reason: str | None
    facets: list[ProposedFacet] = Field(min_length=1)
    positive_judgments: list[ProposedPositiveJudgment]
    reference_response: ProposedReferenceResponse
    annotation_notes: NonBlankStr

    @model_validator(mode="after")
    def proposal_is_consistent(self) -> ProposedCase:
        facet_ids = [facet.facet_id for facet in self.facets]
        if len(set(facet_ids)) != len(facet_ids):
            raise ValueError("proposal facet IDs must be unique")
        positives = [item.provision_id for item in self.positive_judgments]
        if len(set(positives)) != len(positives):
            raise ValueError("proposal positive provision IDs must be unique")
        facet_id_set = set(facet_ids)
        if any(not set(item.facet_ids) <= facet_id_set for item in self.positive_judgments):
            raise ValueError("positive judgment references an unknown facet")
        if not set(self.reference_response.cited_provision_ids) <= set(positives):
            raise ValueError("reference response cites a non-positive provision")
        if self.reference_response.action != self.expected_action:
            raise ValueError("reference response action mismatch")
        if self.answerability == "fully_answerable" and self.expected_action != "answer":
            raise ValueError("fully answerable proposal must answer")
        if (
            self.answerability == "partially_answerable"
            and self.expected_action != "partial_answer_with_limits"
        ):
            raise ValueError("partial proposal action mismatch")
        if self.answerability == "clarification_required" and (
            self.expected_action != "ask_clarifying_question" or not self.missing_user_facts
        ):
            raise ValueError("clarification proposal is incomplete")
        if self.answerability == "unanswerable" and (
            self.expected_action != "insufficient_evidence"
            or self.positive_judgments
            or self.reference_response.cited_provision_ids
        ):
            raise ValueError("unanswerable proposal cannot contain positive evidence")
        return self


class AnnotationProposal(StrictModel):
    schema_version: Literal[1]
    experiment: Literal["D-10-GOLD-V1"]
    artifact_class: Literal["assistant_annotation_proposal_not_gold"]
    status: Literal["pending_user_review"]
    annotator_id: NonBlankStr
    annotation_method: Literal["canonical_full_corpus_proposal_without_retrieval_labels"]
    independence_limitation: NonBlankStr
    cases: list[ProposedCase] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def case_ids_are_unique(self) -> AnnotationProposal:
        if len({case.case_id for case in self.cases}) != 10:
            raise ValueError("annotation proposal must contain 10 distinct cases")
        return self


class UserReviewCase(StrictModel):
    case_id: NonBlankStr
    decision: Literal["pending", "approved", "needs_revision"]
    positive_qrels_confirmed: bool
    bulk_negative_confirmed: bool
    facets_and_reference_confirmed: bool
    comment: str


class UserAdjudication(StrictModel):
    schema_version: Literal[1]
    experiment: Literal["D-10-GOLD-V1"]
    artifact_class: Literal["user_adjudication_input"]
    status: Literal["pending_user_review", "confirmed"]
    annotator_id: NonBlankStr
    reviewer_id: NonBlankStr
    reviewed_at: datetime | None
    annotation_draft_sha256: Sha256
    judgments_jsonl_sha256: Sha256
    cases: list[UserReviewCase] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def review_is_well_formed(self) -> UserAdjudication:
        if len({case.case_id for case in self.cases}) != 10:
            raise ValueError("user adjudication must contain 10 distinct cases")
        if self.status == "confirmed":
            if self.reviewed_at is None or self.reviewed_at.tzinfo is None:
                raise ValueError("confirmed review timestamp must include a timezone")
            if self.annotator_id == self.reviewer_id:
                raise ValueError("reviewer must differ from draft annotator")
        return self


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    except OSError as error:
        raise D10GoldReviewError(f"could not read artifact: {path}") from error


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise D10GoldReviewError(f"could not read {label}: {path}") from error
    if not isinstance(value, dict):
        raise D10GoldReviewError(f"{label} root must be an object")
    return value


def _resolve_repository_path(path_text: str) -> Path:
    candidate = (REPOSITORY_ROOT / path_text).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT.resolve()):
        raise D10GoldReviewError("artifact path escapes repository root")
    return candidate


def load_workflow_contract(
    path: Path = DEFAULT_CONTRACT,
) -> D10GoldWorkflowContract:
    try:
        contract = D10GoldWorkflowContract.model_validate(
            _read_json(path, label="D-10 Gold workflow contract")
        )
    except ValidationError as error:
        raise D10GoldReviewError("D-10 Gold workflow contract is invalid") from error
    payload = contract.model_dump(mode="json", exclude={"workflow_contract_payload_sha256"})
    if canonical_json_sha256(payload) != contract.workflow_contract_payload_sha256:
        raise D10GoldReviewError("workflow contract payload SHA-256 mismatch")
    return contract


def preflight_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, object]:
    contract = load_workflow_contract(path)
    question_path = _resolve_repository_path(contract.question_input_binding.path)
    frozen_path = _resolve_repository_path(contract.frozen_calibration_binding.path)
    if _sha256_file(question_path) != contract.question_input_binding.file_sha256:
        raise D10GoldReviewError("question input file SHA-256 mismatch")
    if _sha256_file(frozen_path) != contract.frozen_calibration_binding.file_sha256:
        raise D10GoldReviewError("frozen calibration file SHA-256 mismatch")
    artifacts = load_manual_pilot_artifacts(
        question_path, DEFAULT_SOURCE_BANK, DEFAULT_APPROVAL_MANIFEST
    )
    frozen = load_frozen_contract(frozen_path)
    if len(artifacts.questions) != contract.expected_case_count:
        raise D10GoldReviewError("question count mismatch")
    if [question.id for question in artifacts.questions] != [case.case_id for case in frozen.cases]:
        raise D10GoldReviewError("question order differs from frozen D-10")
    corpus = contract.corpus_binding
    if (
        frozen.run_binding.as_of_date != corpus.as_of_date
        or frozen.run_binding.corpus_snapshot_id != corpus.corpus_snapshot_id
        or frozen.run_binding.eligible_provision_count != corpus.eligible_provision_count
    ):
        raise D10GoldReviewError("workflow corpus binding differs from frozen D-10")
    if corpus.parser_contract_version != PARSER_SCHEMA_VERSION:
        raise D10GoldReviewError("parser contract version mismatch")
    return {
        "status": "valid",
        "experiment": contract.experiment,
        "question_count": contract.expected_case_count,
        "eligible_provision_count": corpus.eligible_provision_count,
        "expected_total_judgment_count": contract.expected_total_judgment_count,
        "corpus_snapshot_id": corpus.corpus_snapshot_id,
        "external_calls": 0,
        "next_status": "pending_user_review",
    }


def _jsonl_bytes(records: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(_canonical_bytes(record) + b"\n" for record in records)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _atomic_publish_directory(temporary: Path, final: Path) -> None:
    if final.exists():
        raise D10GoldReviewError(f"refusing to overwrite existing artifact: {final}")
    temporary.replace(final)


async def export_corpus(contract_path: Path = DEFAULT_CONTRACT) -> dict[str, object]:
    contract = load_workflow_contract(contract_path)
    preflight_contract(contract_path)
    settings = get_settings()
    if not settings.database_url:
        raise D10GoldReviewError("DATABASE_URL is required for read-only corpus export")
    backend = PostgresExperimentDBackend(settings.database_url)
    try:
        snapshot = await backend.snapshot()
    finally:
        await backend.close()
    population = _validate_snapshot(
        "d10_gold_export",
        snapshot,
        date.fromisoformat(contract.corpus_binding.as_of_date),
    )
    corpus = contract.corpus_binding
    if (
        population.snapshot_id != corpus.corpus_snapshot_id
        or population.fingerprint_sha256 != corpus.corpus_population_fingerprint_sha256
        or population.count != corpus.eligible_provision_count
    ):
        raise D10GoldReviewError("current DB corpus differs from frozen D-10 corpus")

    records: list[dict[str, object]] = []
    for provision in population.provisions:
        record = {
            "provision_id": provision.provision_id,
            "version_id": provision.version_id,
            "document_id": provision.document_id,
            "document_title": provision.document_title,
            "source_kind": provision.source_kind,
            "mst": provision.mst,
            "effective_from": provision.effective_from.isoformat(),
            "effective_to": _iso(provision.effective_to),
            "source_url": provision.source_url,
            "path": provision.path,
            "parent_path": provision.parent_path,
            "heading": provision.heading,
            "content": provision.content,
            "content_sha256": provision.content_sha256,
            "ordinal": provision.ordinal,
        }
        forbidden = set(contract.forbidden_annotation_input_fields).intersection(record)
        if forbidden:
            raise D10GoldReviewError(
                f"corpus export contains forbidden annotation fields: {sorted(forbidden)}"
            )
        records.append(record)
    encoded = _jsonl_bytes(records)
    questions = load_manual_pilot_artifacts().questions
    question_payload = [
        {
            "case_id": item.id,
            "question": item.question,
            "question_sha256": item.question_sha256,
            "question_scope_sha256": item.question_scope_sha256,
            "intent": item.intent,
            "technology": item.technology,
            "question_style": item.question_style,
            "scenario_family_id": item.scenario_family_id,
        }
        for item in questions
    ]
    now = datetime.now(UTC)
    draft_id = f"d10-gold-{now.strftime('%Y%m%dt%H%M%S%fZ').lower()}"
    output_root = _resolve_repository_path(contract.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / f".{draft_id}.tmp-{uuid.uuid4().hex}"
    final = output_root / draft_id
    temporary.mkdir(parents=False)
    try:
        (temporary / "corpus.jsonl").write_bytes(encoded)
        (temporary / "questions.json").write_text(
            json.dumps(question_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 1,
            "experiment": contract.experiment,
            "artifact_class": "blind_canonical_corpus_export",
            "status": "ready_for_annotation_proposal",
            "draft_id": draft_id,
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "workflow_contract_payload_sha256": contract.workflow_contract_payload_sha256,
            "corpus_snapshot_id": population.snapshot_id,
            "corpus_population_fingerprint_sha256": population.fingerprint_sha256,
            "eligible_provision_count": population.count,
            "candidate_set_sha256": canonical_provision_id_set_sha256(
                [record["provision_id"] for record in records]
            ),
            "corpus_jsonl_sha256": _sha256_bytes(encoded),
            "question_count": len(question_payload),
            "questions_file_sha256": _sha256_file(temporary / "questions.json"),
            "forbidden_annotation_input_fields": contract.forbidden_annotation_input_fields,
            "retrieval_scores_or_ranks_included": False,
            "database_access": "repeatable_read_read_only",
            "external_model_calls": 0,
        }
        (temporary / "export-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _atomic_publish_directory(temporary, final)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "status": "corpus_exported",
        "draft_id": draft_id,
        "directory": str(final),
        "eligible_provision_count": population.count,
        "corpus_snapshot_id": population.snapshot_id,
        "retrieval_scores_or_ranks_included": False,
        "external_model_calls": 0,
    }


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise D10GoldReviewError(f"JSONL row is not an object: {line_number}")
            records.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise D10GoldReviewError(f"could not read JSONL artifact: {path}") from error
    return records


def load_annotation_proposal(path: Path) -> AnnotationProposal:
    try:
        return AnnotationProposal.model_validate(_read_json(path, label="annotation proposal"))
    except ValidationError as error:
        sample = error.errors(include_url=False)[:10]
        raise D10GoldReviewError(f"annotation proposal is invalid: {sample}") from error


def _render_review(
    *,
    proposal: AnnotationProposal,
    questions: Mapping[str, Mapping[str, object]],
    corpus: Mapping[str, Mapping[str, object]],
    negative_counts: Mapping[str, int],
) -> str:
    lines = [
        "# D-10 Gold qrel·adjudication 사용자 검토",
        "",
        "> 상태: assistant proposal · 사용자 승인 전 · 정식 Gold 아님",
        "",
        "각 문항의 positive qrel, 필수 답변 요소와 기준 응답을 확인하십시오. ",
        "`user-adjudication.json`에서 문항별 `decision`을 `approved`로 바꾸고 ",
        "`bulk_negative_confirmed`를 `true`로 해야 seal할 수 있습니다.",
        "모든 문항 확인 뒤 `status`를 `confirmed`로 바꾸고 서로 다른 `reviewer_id`와 ",
        "시간대가 포함된 `reviewed_at`을 입력하십시오.",
        "수정이 필요하면 `decision`을 `needs_revision`으로 두고 `comment`에 변경사항을 적으십시오.",
        "",
    ]
    for case in proposal.cases:
        question = questions[case.case_id]
        lines.extend(
            [
                f"## {case.case_id}",
                "",
                f"질문: {question['question']}",
                "",
                f"제안 판정: `{case.answerability}` / `{case.expected_action}`",
                "",
                "### 필수 답변 요소",
                "",
            ]
        )
        for facet in case.facets:
            lines.append(
                f"- `{facet.facet_id}` [{facet.status}] {facet.claim} — {facet.status_reason}"
            )
        lines.extend(["", "### positive qrel", ""])
        if not case.positive_judgments:
            lines.append("- 없음")
        for judgment in case.positive_judgments:
            provision = corpus[judgment.provision_id]
            lines.extend(
                [
                    (
                        f"#### relevance {judgment.relevance} · "
                        f"{provision['document_title']} {provision['path']}"
                    ),
                    "",
                    f"- provision ID: `{judgment.provision_id}`",
                    f"- facet: `{', '.join(judgment.facet_ids)}`",
                    f"- 근거: {judgment.rationale}",
                    "",
                    str(provision["content"]),
                    "",
                ]
            )
        lines.extend(
            [
                "### relevance 0 일괄 제안",
                "",
                f"- 후보 수: `{negative_counts[case.case_id]}`",
                "- 범위: 같은 고정 corpus에서 위 positive를 제외한 모든 provision",
                "- 사용자 확인: `bulk_negative_confirmed`가 true가 되기 전에는 ",
                "  adjudicated로 보지 않음",
                "",
                "### 기준 응답 초안",
                "",
                case.reference_response.text,
                "",
                f"검토 메모: {case.annotation_notes}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_draft(
    export_directory: Path,
    proposal_path: Path,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, object]:
    contract = load_workflow_contract(contract_path)
    preflight_contract(contract_path)
    manifest = _read_json(export_directory / "export-manifest.json", label="export manifest")
    corpus_records = _load_jsonl(export_directory / "corpus.jsonl")
    questions_raw = json.loads((export_directory / "questions.json").read_text(encoding="utf-8"))
    if not isinstance(questions_raw, list) or not all(
        isinstance(item, dict) for item in questions_raw
    ):
        raise D10GoldReviewError("export questions are invalid")
    if manifest.get("corpus_jsonl_sha256") != _sha256_file(
        export_directory / "corpus.jsonl"
    ) or manifest.get("questions_file_sha256") != _sha256_file(export_directory / "questions.json"):
        raise D10GoldReviewError("export artifact SHA-256 mismatch")
    if len(corpus_records) != contract.corpus_binding.eligible_provision_count:
        raise D10GoldReviewError("export corpus count mismatch")
    forbidden = set(contract.forbidden_annotation_input_fields)
    if any(forbidden.intersection(record) for record in corpus_records):
        raise D10GoldReviewError("export contains retrieval labels, scores, or ranks")
    corpus_by_id = {str(record["provision_id"]): record for record in corpus_records}
    if len(corpus_by_id) != len(corpus_records):
        raise D10GoldReviewError("export contains duplicate provision IDs")
    questions = {str(item["case_id"]): item for item in questions_raw}
    proposal = load_annotation_proposal(proposal_path)
    if [case.case_id for case in proposal.cases] != list(questions):
        raise D10GoldReviewError("proposal case order differs from frozen questions")

    judgments: list[dict[str, object]] = []
    case_payloads: list[dict[str, object]] = []
    negative_counts: dict[str, int] = {}
    for case in proposal.cases:
        positive_by_id = {item.provision_id: item for item in case.positive_judgments}
        missing = set(positive_by_id) - set(corpus_by_id)
        if missing:
            raise D10GoldReviewError(
                f"proposal positive provision is outside frozen corpus: {case.case_id}"
            )
        case_judgments: list[dict[str, object]] = []
        for record in corpus_records:
            provision_id = str(record["provision_id"])
            positive = positive_by_id.get(provision_id)
            judgment = {
                "case_id": case.case_id,
                "provision_id": provision_id,
                "content_sha256": record["content_sha256"],
                "relevance": positive.relevance if positive else 0,
                "facet_ids": positive.facet_ids if positive else [],
                "evidence_scope": positive.evidence_scope if positive else None,
                "rationale": (
                    positive.rationale
                    if positive
                    else (
                        "필수 답변 요소를 직접 또는 보조로 뒷받침하지 않는 "
                        "전수 corpus 음성 판정 초안"
                    )
                ),
                "annotation_status": "assistant_proposed_pending_user_review",
                "judgment_basis": (
                    "explicit_positive_review" if positive else "bulk_negative_proposal"
                ),
            }
            case_judgments.append(judgment)
            judgments.append(judgment)
        relevance_counts = Counter(item["relevance"] for item in case_judgments)
        negative_counts[case.case_id] = relevance_counts[0]
        qrels = []
        for positive in case.positive_judgments:
            record = corpus_by_id[positive.provision_id]
            qrels.append(
                {
                    "provision_id": positive.provision_id,
                    "document_id": record["document_id"],
                    "version_id": record["version_id"],
                    "path": record["path"],
                    "heading": record["heading"],
                    "effective_from": record["effective_from"],
                    "effective_to": record["effective_to"],
                    "content_sha256": record["content_sha256"],
                    "relevance": positive.relevance,
                    "facet_ids": positive.facet_ids,
                    "evidence_scope": positive.evidence_scope,
                    "rationale": positive.rationale,
                    "reference_context": record["content"],
                }
            )
        case_payloads.append(
            {
                "case_id": case.case_id,
                "question": questions[case.case_id]["question"],
                "question_sha256": questions[case.case_id]["question_sha256"],
                "answerability": case.answerability,
                "expected_action": case.expected_action,
                "missing_user_facts": case.missing_user_facts,
                "insufficient_reason": case.insufficient_reason,
                "facets": [facet.model_dump(mode="json") for facet in case.facets],
                "qrels": qrels,
                "reference_response": case.reference_response.model_dump(mode="json"),
                "judgment_count": len(case_judgments),
                "relevance_counts": {str(key): relevance_counts[key] for key in (0, 1, 2)},
                "judged_candidate_set_sha256": canonical_provision_id_set_sha256(
                    [str(item["provision_id"]) for item in case_judgments]
                ),
                "annotation_status": "assistant_proposed_pending_user_review",
                "annotation_notes": case.annotation_notes,
            }
        )
    if len(judgments) != contract.expected_total_judgment_count:
        raise D10GoldReviewError("draft judgment count mismatch")

    draft = {
        "schema_version": 1,
        "experiment": contract.experiment,
        "artifact_class": "d10_full_corpus_gold_candidate_not_approved",
        "evaluation_status": "pending_user_review",
        "annotator_id": proposal.annotator_id,
        "annotation_method": proposal.annotation_method,
        "independence_limitation": proposal.independence_limitation,
        "workflow_contract_payload_sha256": contract.workflow_contract_payload_sha256,
        "corpus_snapshot_id": contract.corpus_binding.corpus_snapshot_id,
        "eligible_provision_count": contract.corpus_binding.eligible_provision_count,
        "case_count": len(case_payloads),
        "total_judgment_count": len(judgments),
        "cases": case_payloads,
        "prohibited_claims": contract.prohibited_claims_before_seal,
    }
    judgment_bytes = _jsonl_bytes(judgments)
    draft_bytes = json.dumps(draft, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    review_input = {
        "schema_version": 1,
        "experiment": contract.experiment,
        "artifact_class": "user_adjudication_input",
        "status": "pending_user_review",
        "annotator_id": proposal.annotator_id,
        "reviewer_id": "__USER_REVIEWER_ID__",
        "reviewed_at": None,
        "annotation_draft_sha256": _sha256_bytes(draft_bytes),
        "judgments_jsonl_sha256": _sha256_bytes(judgment_bytes),
        "cases": [
            {
                "case_id": case.case_id,
                "decision": "pending",
                "positive_qrels_confirmed": False,
                "bulk_negative_confirmed": False,
                "facets_and_reference_confirmed": False,
                "comment": "",
            }
            for case in proposal.cases
        ],
    }
    adjudication_draft = {
        "schema_version": 1,
        "experiment": contract.experiment,
        "artifact_class": "adjudication_manifest_draft_not_approved",
        "status": "pending_user_review",
        "dataset_sha256": _sha256_bytes(draft_bytes),
        "judgments_sha256": _sha256_bytes(judgment_bytes),
        "annotator_id": proposal.annotator_id,
        "reviewer_id": None,
        "approved_at": None,
        "cases": [
            {
                "case_id": case.case_id,
                "case_payload_sha256": canonical_json_sha256(payload),
                "decision": "pending",
            }
            for case, payload in zip(proposal.cases, case_payloads, strict=True)
        ],
    }
    output_directory = export_directory / "review"
    temporary = export_directory / f".review.tmp-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        (temporary / "judgments.jsonl").write_bytes(judgment_bytes)
        (temporary / "annotation-draft.json").write_bytes(draft_bytes)
        (temporary / "user-adjudication.json").write_text(
            json.dumps(review_input, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / "adjudication-draft.json").write_text(
            json.dumps(adjudication_draft, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (temporary / "adjudication-review.md").write_text(
            _render_review(
                proposal=proposal,
                questions=questions,
                corpus=corpus_by_id,
                negative_counts=negative_counts,
            ),
            encoding="utf-8",
        )
        review_manifest = {
            "schema_version": 1,
            "experiment": contract.experiment,
            "artifact_class": "d10_gold_review_bundle",
            "status": "pending_user_review",
            "case_count": len(case_payloads),
            "eligible_provision_count": len(corpus_records),
            "total_judgment_count": len(judgments),
            "annotation_draft_sha256": _sha256_file(temporary / "annotation-draft.json"),
            "judgments_jsonl_sha256": _sha256_file(temporary / "judgments.jsonl"),
            "initial_user_adjudication_sha256": _sha256_file(temporary / "user-adjudication.json"),
            "adjudication_draft_sha256": _sha256_file(temporary / "adjudication-draft.json"),
            "review_markdown_sha256": _sha256_file(temporary / "adjudication-review.md"),
        }
        (temporary / "review-manifest.json").write_text(
            json.dumps(review_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _atomic_publish_directory(temporary, output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "status": "pending_user_review",
        "review_directory": str(output_directory),
        "case_count": len(case_payloads),
        "eligible_provision_count": len(corpus_records),
        "total_judgment_count": len(judgments),
        "review_markdown": str(output_directory / "adjudication-review.md"),
        "user_adjudication": str(output_directory / "user-adjudication.json"),
        "sealed": False,
    }


def preflight_draft(
    review_directory: Path, contract_path: Path = DEFAULT_CONTRACT
) -> dict[str, object]:
    contract = load_workflow_contract(contract_path)
    manifest = _read_json(review_directory / "review-manifest.json", label="review manifest")
    draft = _read_json(review_directory / "annotation-draft.json", label="annotation draft")
    try:
        adjudication = UserAdjudication.model_validate(
            _read_json(review_directory / "user-adjudication.json", label="user adjudication")
        )
    except ValidationError as error:
        raise D10GoldReviewError(f"user adjudication is invalid: {error}") from error
    judgments = _load_jsonl(review_directory / "judgments.jsonl")
    if manifest.get("status") != "pending_user_review":
        raise D10GoldReviewError("review bundle status must remain pending_user_review")
    expected_hashes = {
        "annotation_draft_sha256": "annotation-draft.json",
        "judgments_jsonl_sha256": "judgments.jsonl",
        "adjudication_draft_sha256": "adjudication-draft.json",
        "review_markdown_sha256": "adjudication-review.md",
    }
    for field, filename in expected_hashes.items():
        if manifest.get(field) != _sha256_file(review_directory / filename):
            raise D10GoldReviewError(f"review artifact SHA-256 mismatch: {filename}")
    if (
        draft.get("evaluation_status") != "pending_user_review"
        or draft.get("case_count") != contract.expected_case_count
        or draft.get("total_judgment_count") != contract.expected_total_judgment_count
        or len(judgments) != contract.expected_total_judgment_count
    ):
        raise D10GoldReviewError("draft counts or status are invalid")
    counts = Counter(str(item.get("case_id")) for item in judgments)
    if set(counts.values()) != {contract.corpus_binding.eligible_provision_count}:
        raise D10GoldReviewError("each D-10 case must judge the full corpus")
    if any(item.get("relevance") not in {0, 1, 2} for item in judgments):
        raise D10GoldReviewError("judgment relevance must be 0, 1, or 2")
    if adjudication.annotation_draft_sha256 != _sha256_file(
        review_directory / "annotation-draft.json"
    ) or adjudication.judgments_jsonl_sha256 != _sha256_file(review_directory / "judgments.jsonl"):
        raise D10GoldReviewError("user adjudication input binding mismatch")
    pending = sum(
        case.decision != "approved"
        or case.positive_qrels_confirmed is not True
        or case.bulk_negative_confirmed is not True
        or case.facets_and_reference_confirmed is not True
        for case in adjudication.cases
    )
    ready = (
        pending == 0
        and adjudication.status == "confirmed"
        and adjudication.reviewed_at is not None
        and adjudication.reviewer_id != "__USER_REVIEWER_ID__"
        and adjudication.reviewer_id != adjudication.annotator_id
    )
    return {
        "status": "ready_to_seal" if ready else "valid_pending_user_review",
        "case_count": contract.expected_case_count,
        "eligible_provision_count": contract.corpus_binding.eligible_provision_count,
        "total_judgment_count": len(judgments),
        "pending_user_case_count": pending,
        "sealed": False,
    }


def seal_review(
    review_directory: Path, contract_path: Path = DEFAULT_CONTRACT
) -> dict[str, object]:
    report = preflight_draft(review_directory, contract_path)
    if report["status"] != "ready_to_seal":
        raise D10GoldReviewError("user adjudication is not ready to seal")
    draft = _read_json(review_directory / "annotation-draft.json", label="annotation draft")
    review = UserAdjudication.model_validate(
        _read_json(review_directory / "user-adjudication.json", label="user adjudication")
    )
    if review.reviewed_at is None:
        raise D10GoldReviewError("confirmed review timestamp is missing")
    judgments_path = review_directory / "judgments.jsonl"
    sealed_dataset = {
        **draft,
        "artifact_class": "d10_user_adjudicated_calibration_gold",
        "evaluation_status": "approved_gold",
        "reviewer_id": review.reviewer_id,
        "adjudicated_at": review.reviewed_at.isoformat(),
        "gold_scope": "calibration_only_not_held_out",
        "independent_human_gold": False,
        "prohibited_claims": [
            "independent_human_gold",
            "held_out_performance",
            "population_generalization",
            "production_release_gate",
        ],
    }
    dataset_bytes = json.dumps(sealed_dataset, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    adjudication_manifest = {
        "schema_version": 1,
        "manifest_version": "experiment-d-10-gold-adjudication-v1",
        "experiment": "D-10-GOLD-V1",
        "artifact_class": "user_adjudicated_calibration_gold_manifest",
        "status": "approved",
        "dataset_sha256": _sha256_bytes(dataset_bytes),
        "judgments_jsonl_sha256": _sha256_file(judgments_path),
        "annotator_id": review.annotator_id,
        "reviewer_id": review.reviewer_id,
        "approved_at": review.reviewed_at.isoformat(),
        "case_count": 10,
        "total_judgment_count": 30660,
        "cases": [
            {
                "case_id": item.case_id,
                "decision": item.decision,
                "positive_qrels_confirmed": item.positive_qrels_confirmed,
                "bulk_negative_confirmed": item.bulk_negative_confirmed,
                "facets_and_reference_confirmed": item.facets_and_reference_confirmed,
            }
            for item in review.cases
        ],
        "limitations": [
            "assistant_annotation_user_adjudication",
            "calibration_questions_previously_seen_by_retrieval_development",
            "not_independent_human_gold",
            "not_held_out",
        ],
    }
    manifest_bytes = (
        json.dumps(adjudication_manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    )
    final = review_directory / "sealed"
    temporary = review_directory / f".sealed.tmp-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        (temporary / "dataset.json").write_bytes(dataset_bytes)
        shutil.copyfile(judgments_path, temporary / "judgments.jsonl")
        (temporary / "adjudication-manifest.json").write_bytes(manifest_bytes)
        seal_manifest = {
            "schema_version": 1,
            "status": "sealed",
            "dataset_sha256": _sha256_file(temporary / "dataset.json"),
            "judgments_jsonl_sha256": _sha256_file(temporary / "judgments.jsonl"),
            "adjudication_manifest_sha256": _sha256_file(temporary / "adjudication-manifest.json"),
        }
        (temporary / "seal-manifest.json").write_text(
            json.dumps(seal_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _atomic_publish_directory(temporary, final)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "status": "sealed_approved_calibration_gold",
        "directory": str(final),
        "case_count": 10,
        "total_judgment_count": 30660,
        "held_out": False,
        "independent_human_gold": False,
    }


def preflight_sealed(sealed_directory: Path) -> dict[str, object]:
    seal = _read_json(sealed_directory / "seal-manifest.json", label="seal manifest")
    expected = {
        "dataset_sha256": "dataset.json",
        "judgments_jsonl_sha256": "judgments.jsonl",
        "adjudication_manifest_sha256": "adjudication-manifest.json",
    }
    for field, filename in expected.items():
        if seal.get(field) != _sha256_file(sealed_directory / filename):
            raise D10GoldReviewError(f"sealed artifact SHA-256 mismatch: {filename}")
    dataset = _read_json(sealed_directory / "dataset.json", label="sealed dataset")
    manifest = _read_json(
        sealed_directory / "adjudication-manifest.json",
        label="sealed adjudication manifest",
    )
    judgments = _load_jsonl(sealed_directory / "judgments.jsonl")
    if (
        dataset.get("evaluation_status") != "approved_gold"
        or dataset.get("gold_scope") != "calibration_only_not_held_out"
        or dataset.get("independent_human_gold") is not False
        or manifest.get("status") != "approved"
        or manifest.get("dataset_sha256") != _sha256_file(sealed_directory / "dataset.json")
        or len(judgments) != 30660
    ):
        raise D10GoldReviewError("sealed D-10 Gold contract is invalid")
    return {
        "status": "valid_approved_calibration_gold",
        "case_count": 10,
        "total_judgment_count": len(judgments),
        "held_out": False,
        "independent_human_gold": False,
    }


def _path_argument(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D-10 full-corpus Gold review workflow")
    parser.add_argument(
        "command",
        choices=(
            "preflight-contract",
            "export-corpus",
            "build-draft",
            "preflight-draft",
            "seal",
            "preflight-sealed",
        ),
    )
    parser.add_argument("--contract", type=_path_argument, default=DEFAULT_CONTRACT)
    parser.add_argument("--export", type=_path_argument)
    parser.add_argument("--proposal", type=_path_argument)
    parser.add_argument("--review", type=_path_argument)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        if arguments.command == "preflight-contract":
            result = preflight_contract(arguments.contract)
        elif arguments.command == "export-corpus":
            result = asyncio.run(export_corpus(arguments.contract))
        elif arguments.command == "build-draft":
            if arguments.export is None or arguments.proposal is None:
                raise D10GoldReviewError("build-draft requires --export and --proposal")
            result = build_draft(arguments.export, arguments.proposal, arguments.contract)
        elif arguments.command == "preflight-draft":
            if arguments.review is None:
                raise D10GoldReviewError("preflight-draft requires --review")
            result = preflight_draft(arguments.review, arguments.contract)
        elif arguments.command == "seal":
            if arguments.review is None:
                raise D10GoldReviewError("seal requires --review")
            result = seal_review(arguments.review, arguments.contract)
        else:
            if arguments.review is None:
                raise D10GoldReviewError("preflight-sealed requires --review")
            result = preflight_sealed(arguments.review)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except D10GoldReviewError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": "d10_gold_review_failed",
                    "message": str(error),
                    "result_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())


__all__ = [
    "AnnotationProposal",
    "D10GoldReviewError",
    "D10GoldWorkflowContract",
    "DEFAULT_CONTRACT",
    "ProposedCase",
    "UserAdjudication",
    "build_draft",
    "export_corpus",
    "load_annotation_proposal",
    "load_workflow_contract",
    "preflight_contract",
    "preflight_draft",
    "preflight_sealed",
    "seal_review",
]
