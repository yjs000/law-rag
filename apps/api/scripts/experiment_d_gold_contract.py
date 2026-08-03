"""Executable contract for the approved layperson Experiment D gold suite."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Answerability = Literal[
    "fully_answerable",
    "partially_answerable",
    "clarification_required",
    "unanswerable",
]
FacetStatus = Literal["supported", "unsupported", "needs_clarification"]
ExpectedAction = Literal[
    "answer",
    "partial_answer_with_limits",
    "ask_clarifying_question",
    "insufficient_evidence",
]
ControlPairExpectation = Literal[
    "same_direct_evidence",
    "different_direct_evidence",
    "answerability_contrast",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoldSourceBankBinding(StrictModel):
    artifact: str = Field(min_length=1)
    bank_version: str = Field(min_length=1)
    question_count: Literal[1000]
    question_set_sha256: Sha256
    question_scope_set_sha256: Sha256
    approval_manifest_artifact: str = Field(min_length=1)
    approval_manifest_sha256: Sha256


class ApprovalManifestSourceBank(StrictModel):
    bank_version: str
    question_count: Literal[1000]
    question_set_sha256: Sha256
    question_scope_set_sha256: Sha256


class ApprovedQuestion(StrictModel):
    id: str = Field(min_length=1)
    question_sha256: Sha256
    question_scope_sha256: Sha256
    status: Literal["approved"]


class ExperimentDQuestionApprovalManifest(StrictModel):
    schema_version: Literal[1]
    manifest_version: Literal["experiment-d-lay-energy-question-approval-v1"]
    status: Literal["approved"]
    decision_scope: Literal["question_text_and_scope_only"]
    approved_by: NonBlankStr
    approved_at: datetime
    source_bank: ApprovalManifestSourceBank
    questions: list[ApprovedQuestion] = Field(min_length=1000, max_length=1000)

    @model_validator(mode="after")
    def every_question_is_uniquely_approved(self) -> ExperimentDQuestionApprovalManifest:
        if self.approved_at.tzinfo is None:
            raise ValueError("question approval timestamp must include a timezone")
        ids = [question.id for question in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("approval manifest contains duplicate question IDs")
        return self


class GoldCorpusSnapshot(StrictModel):
    parser_contract_version: Literal["3"]
    as_of_date: date
    retrieval_unit: Literal["provision"]
    searchable_provision_count: int = Field(gt=0)
    fingerprint_sha256: Sha256
    passage_template_version: Literal["legal-provision-v1"]
    embedding_profile_key: Literal["nvidia-nemotron-3-embed-1b-512-v1"]


class GoldSplitManifest(StrictModel):
    algorithm: Literal["frozen-scenario-family-assignment-v1"]
    group_field: Literal["scenario_family_id"]
    calibration_count: Literal[200]
    test_count: Literal[800]
    assignment_sha256: Sha256


class GoldMetricProtocol(StrictModel):
    retrieval_mode: Literal["dense_only"]
    retrieval_unit: Literal["provision"]
    candidate_k: Literal[10]
    cutoffs: tuple[Literal[1], Literal[3], Literal[5], Literal[10]]
    direct_relevance_grade: Literal[2]
    context_relevance_grade: Literal[1]
    recall_and_mrr_positive_grade: Literal[2]
    recall_definition: Literal["macro_fraction_of_grade2_qrels"]
    hit_rate_definition: Literal["macro_any_grade2_qrel"]
    mrr_cutoff: Literal[10]
    ndcg_uses_graded_relevance: Literal[True]
    ndcg_gain: Literal["exp2_minus_1"]
    ndcg_discount: Literal["log2_rank_plus_1"]
    facet_positive_grade: Literal[2]
    hierarchy_policy: Literal["exact_qrel_ids_with_explicit_evidence_closure"]
    query_average: Literal["macro"]
    facet_recall_denominator: Literal["supported_required_facets"]
    corpus_coverage_denominator: Literal["all_required_facets"]
    unjudged_policy: Literal["nonrelevant_in_frozen_pool_benchmark"]
    suite_aggregation: Literal["never_average_with_synthetic_control_suite"]
    retrieved_duplicate_policy: Literal["fail_run"]
    score_order: Literal["raw_cosine_similarity_desc_then_provision_id_asc"]
    boundary_tie_policy: Literal["fail_on_equal_score_at_10_and_11"]
    empty_fully_population_policy: Literal["fail_run"]
    aggregate_decimal_places: Literal[12]
    primary_split: Literal["test"]
    calibration_aggregation: Literal["diagnostic_only"]
    combined_aggregation: Literal["diagnostic_only"]
    recall_mrr_ndcg_population: tuple[Literal["fully_answerable"], ...]
    separate_answerability_reports: tuple[
        Literal[
            "partially_answerable",
            "clarification_required",
            "unanswerable",
        ],
        ...,
    ]
    empty_separate_population_policy: Literal["report_not_applicable"]

    @model_validator(mode="after")
    def retrieval_metrics_use_the_fixed_answerability_population(
        self,
    ) -> GoldMetricProtocol:
        if self.recall_mrr_ndcg_population != ("fully_answerable",):
            raise ValueError("Recall/MRR/nDCG population must be fully_answerable only")
        expected_separate = {
            "partially_answerable",
            "clarification_required",
            "unanswerable",
        }
        if set(self.separate_answerability_reports) != expected_separate or len(
            self.separate_answerability_reports
        ) != len(expected_separate):
            raise ValueError(
                "partial, clarification, and unanswerable cases must be reported separately"
            )
        return self


class GoldPoolMethod(StrictModel):
    method_id: str = Field(min_length=1)
    kind: Literal[
        "manual_legal_path_lookup",
        "dense_candidate_pool",
        "lexical_annotation_pool",
        "full_corpus_manual_review",
    ]
    configuration_sha256: Sha256
    top_k: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def top_k_matches_method(self) -> GoldPoolMethod:
        if self.kind == "full_corpus_manual_review" and self.top_k is not None:
            raise ValueError("full corpus review cannot declare top_k")
        if self.kind != "full_corpus_manual_review" and self.top_k is None:
            raise ValueError("pooled candidate method must declare top_k")
        return self


def canonical_provision_id_set_sha256(provision_ids: Sequence[str]) -> str:
    """Return the frozen hash contract used for unordered provision-ID sets."""

    return hashlib.sha256(
        json.dumps(
            sorted(provision_ids),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class GoldPoolMethodCandidates(StrictModel):
    method_id: str = Field(min_length=1)
    top_k: int | None = Field(default=None, gt=0)
    candidate_provision_ids: list[str]
    candidate_set_sha256: Sha256

    @model_validator(mode="after")
    def candidate_set_is_frozen(self) -> GoldPoolMethodCandidates:
        if any(not provision_id for provision_id in self.candidate_provision_ids):
            raise ValueError("pool candidate provision IDs cannot be empty")
        if len(set(self.candidate_provision_ids)) != len(self.candidate_provision_ids):
            raise ValueError("pool candidate provision IDs must be unique per method")
        if self.top_k is not None and len(self.candidate_provision_ids) > self.top_k:
            raise ValueError("pool candidate count cannot exceed the method top_k")
        actual_sha256 = canonical_provision_id_set_sha256(self.candidate_provision_ids)
        if actual_sha256 != self.candidate_set_sha256:
            raise ValueError("pool candidate set hash mismatch")
        return self


class GoldAnnotationProtocol(StrictModel):
    pool_methods: list[GoldPoolMethod] = Field(min_length=1)
    retrieval_system_labels_hidden_from_annotators: Literal[True]
    test_qrels_sealed_from_retrieval_tuning: Literal[True]
    independent_reviewer_required: Literal[True]
    unjudged_policy: Literal["nonrelevant_in_frozen_pool_benchmark"]

    @model_validator(mode="after")
    def pool_is_independent_enough(self) -> GoldAnnotationProtocol:
        method_ids = [method.method_id for method in self.pool_methods]
        if len(set(method_ids)) != len(method_ids):
            raise ValueError("annotation pool method IDs must be unique")
        kinds = {method.kind for method in self.pool_methods}
        if "full_corpus_manual_review" not in kinds and len(kinds) < 2:
            raise ValueError(
                "pooled annotation requires at least two independent candidate methods"
            )
        return self


class GoldFacet(StrictModel):
    facet_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    status: FacetStatus
    status_reason: str = Field(min_length=1)


class GoldQrel(StrictModel):
    qrel_id: str = Field(min_length=1)
    provision_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    heading: str | None
    effective_from: date
    effective_to: date | None
    content_sha256: Sha256
    passage_text_sha256: Sha256
    relevance: Literal[1, 2]
    facet_ids: list[str] = Field(min_length=1)
    evidence_scope: Literal["leaf", "subtree", "article"]

    @model_validator(mode="after")
    def facet_links_are_unique(self) -> GoldQrel:
        if any(not facet_id for facet_id in self.facet_ids):
            raise ValueError("qrel facet IDs cannot be empty")
        if len(set(self.facet_ids)) != len(self.facet_ids):
            raise ValueError("qrel facet IDs must be unique")
        return self


class GoldReferenceContext(StrictModel):
    qrel_id: str
    content: str = Field(min_length=1)
    content_sha256: Sha256

    @model_validator(mode="after")
    def content_hash_matches(self) -> GoldReferenceContext:
        actual = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if actual != self.content_sha256:
            raise ValueError("reference context content hash mismatch")
        return self


class GoldReferenceResponse(StrictModel):
    action: ExpectedAction
    text: str = Field(min_length=1)
    cited_qrel_ids: list[str]

    @model_validator(mode="after")
    def citations_are_unique(self) -> GoldReferenceResponse:
        if len(set(self.cited_qrel_ids)) != len(self.cited_qrel_ids):
            raise ValueError("reference response qrel citations must be unique")
        return self


class GoldJudgmentCoverage(StrictModel):
    candidate_count: int = Field(ge=0)
    judged_count: int = Field(ge=0)
    judged_candidate_provision_ids: list[str]
    judged_candidate_set_sha256: Sha256
    pool_method_candidates: list[GoldPoolMethodCandidates] = Field(min_length=1)
    all_candidates_judged: Literal[True]
    alternative_positive_search_completed: Literal[True]
    completeness_status: Literal["adjudicated"]
    distractor_provision_ids: list[str]

    @model_validator(mode="after")
    def judged_pool_is_complete(self) -> GoldJudgmentCoverage:
        if self.judged_count != self.candidate_count:
            raise ValueError("every pooled candidate must be judged")
        if len(self.judged_candidate_provision_ids) != self.candidate_count:
            raise ValueError("judged candidate IDs and candidate count differ")
        if len(set(self.judged_candidate_provision_ids)) != self.candidate_count:
            raise ValueError("judged candidate IDs must be unique")
        actual_candidate_set_sha = canonical_provision_id_set_sha256(
            self.judged_candidate_provision_ids
        )
        if actual_candidate_set_sha != self.judged_candidate_set_sha256:
            raise ValueError("judged candidate set hash mismatch")
        if len(set(self.distractor_provision_ids)) != len(self.distractor_provision_ids):
            raise ValueError("distractor provision IDs must be unique")
        if not set(self.distractor_provision_ids) <= set(self.judged_candidate_provision_ids):
            raise ValueError("distractors must come from the judged candidate pool")
        method_ids = [pool.method_id for pool in self.pool_method_candidates]
        if len(set(method_ids)) != len(method_ids):
            raise ValueError("pool method candidate entries must use unique method IDs")
        pooled_candidates = {
            provision_id
            for pool in self.pool_method_candidates
            for provision_id in pool.candidate_provision_ids
        }
        if pooled_candidates != set(self.judged_candidate_provision_ids):
            raise ValueError(
                "the union of per-method candidates must equal the judged candidate pool"
            )
        return self


class GoldAnnotationReview(StrictModel):
    annotator_id: NonBlankStr
    reviewer_id: NonBlankStr
    status: Literal["adjudicated"]
    reviewed_at: datetime
    disagreement_resolution: str | None

    @model_validator(mode="after")
    def reviewer_is_independent(self) -> GoldAnnotationReview:
        if self.annotator_id == self.reviewer_id:
            raise ValueError("annotator and reviewer must be different")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("annotation review timestamp must include a timezone")
        return self


class ExperimentDGoldCase(StrictModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    question_sha256: Sha256
    question_style: str = Field(min_length=1)
    question_review_status: Literal["approved"]
    scenario_family_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    technology: str = Field(min_length=1)
    as_of_date: date
    split: Literal["calibration", "test"]
    answerability: Answerability
    expected_action: ExpectedAction
    missing_user_facts: list[str]
    insufficient_reason: str | None
    required_answer_facets: list[GoldFacet] = Field(min_length=1)
    qrels: list[GoldQrel]
    reference_contexts: list[GoldReferenceContext]
    reference_response: GoldReferenceResponse
    judgment_coverage: GoldJudgmentCoverage
    annotation_review: GoldAnnotationReview
    evaluation_tags: list[str]
    boundary_type: str | None = None
    control_pair_id: str | None = None
    control_pair_expectation: ControlPairExpectation | None = None

    @model_validator(mode="after")
    def validate_evidence_contract(self) -> ExperimentDGoldCase:
        if (self.control_pair_id is None) != (self.control_pair_expectation is None):
            raise ValueError("control pair ID and expectation must be declared together")
        actual_question_sha = hashlib.sha256(self.question.encode("utf-8")).hexdigest()
        if actual_question_sha != self.question_sha256:
            raise ValueError("question hash mismatch")

        facet_ids = [facet.facet_id for facet in self.required_answer_facets]
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("duplicate required facet ID")
        qrel_ids = [qrel.qrel_id for qrel in self.qrels]
        if len(qrel_ids) != len(set(qrel_ids)):
            raise ValueError("duplicate qrel ID")
        if len({qrel.provision_id for qrel in self.qrels}) != len(self.qrels):
            raise ValueError("the same provision cannot appear in qrels twice")

        facet_id_set = set(facet_ids)
        for qrel in self.qrels:
            if not set(qrel.facet_ids) <= facet_id_set:
                raise ValueError("qrel references an unknown facet")
            if self.as_of_date < qrel.effective_from or (
                qrel.effective_to is not None and self.as_of_date >= qrel.effective_to
            ):
                raise ValueError("qrel version is not effective on the case as-of date")

        context_by_qrel = {context.qrel_id: context for context in self.reference_contexts}
        if len(context_by_qrel) != len(self.reference_contexts):
            raise ValueError("duplicate reference context qrel ID")
        if set(context_by_qrel) != set(qrel_ids):
            raise ValueError("every qrel must have exactly one frozen reference context")
        for qrel in self.qrels:
            if context_by_qrel[qrel.qrel_id].content_sha256 != qrel.content_sha256:
                raise ValueError("qrel and reference context hashes differ")

        direct_facets = {
            facet_id for qrel in self.qrels if qrel.relevance == 2 for facet_id in qrel.facet_ids
        }
        supported = {
            facet.facet_id for facet in self.required_answer_facets if facet.status == "supported"
        }
        unsupported = {
            facet.facet_id for facet in self.required_answer_facets if facet.status == "unsupported"
        }
        needs_clarification = {
            facet.facet_id
            for facet in self.required_answer_facets
            if facet.status == "needs_clarification"
        }
        if not supported <= direct_facets:
            raise ValueError("every supported facet needs relevance-2 direct evidence")
        if unsupported & direct_facets:
            raise ValueError("unsupported facet cannot have relevance-2 evidence")

        if needs_clarification:
            expected_answerability = "clarification_required"
            expected_action = "ask_clarifying_question"
        elif supported and unsupported:
            expected_answerability = "partially_answerable"
            expected_action = "partial_answer_with_limits"
        elif supported and not unsupported:
            expected_answerability = "fully_answerable"
            expected_action = "answer"
        else:
            expected_answerability = "unanswerable"
            expected_action = "insufficient_evidence"
        if self.answerability != expected_answerability:
            raise ValueError("answerability does not follow the fixed facet precedence")
        if self.expected_action != expected_action:
            raise ValueError("expected action does not match answerability")
        if self.reference_response.action != expected_action:
            raise ValueError("reference response action does not match answerability")

        if self.answerability == "clarification_required":
            if not self.missing_user_facts:
                raise ValueError("clarification case must list missing user facts")
        elif self.missing_user_facts:
            raise ValueError("only clarification cases may list missing user facts")

        if unsupported and not self.insufficient_reason:
            raise ValueError("unsupported facets require an insufficient reason")
        if not unsupported and self.insufficient_reason is not None:
            raise ValueError("insufficient reason requires an unsupported facet")
        if self.answerability == "unanswerable" and self.qrels:
            raise ValueError("unanswerable case cannot have qrels")
        if len(self.qrels) > self.judgment_coverage.candidate_count:
            raise ValueError("qrels cannot exceed the judged candidate pool")
        if not {qrel.provision_id for qrel in self.qrels} <= set(
            self.judgment_coverage.judged_candidate_provision_ids
        ):
            raise ValueError("every qrel must come from the judged candidate pool")
        if {qrel.provision_id for qrel in self.qrels}.intersection(
            self.judgment_coverage.distractor_provision_ids
        ):
            raise ValueError("positive qrel cannot also be a distractor")
        classified_candidates = {qrel.provision_id for qrel in self.qrels} | set(
            self.judgment_coverage.distractor_provision_ids
        )
        if classified_candidates != set(self.judgment_coverage.judged_candidate_provision_ids):
            raise ValueError(
                "every judged candidate must be classified as a positive qrel or distractor"
            )

        cited = set(self.reference_response.cited_qrel_ids)
        if not cited <= set(qrel_ids):
            raise ValueError("reference response cites an unknown qrel")
        if self.answerability in {"fully_answerable", "partially_answerable"}:
            direct_qrel_ids = {qrel.qrel_id for qrel in self.qrels if qrel.relevance == 2}
            if not cited or not cited <= direct_qrel_ids:
                raise ValueError("answer response must cite only relevance-2 qrels")
            cited_supported_facets = {
                facet_id
                for qrel in self.qrels
                if qrel.qrel_id in cited and qrel.relevance == 2
                for facet_id in qrel.facet_ids
            }
            if not supported <= cited_supported_facets:
                raise ValueError("answer response citations must cover every supported facet")
        if self.answerability == "unanswerable" and cited:
            raise ValueError("insufficient-evidence response cannot cite qrels")
        return self


class ExperimentDGoldDataset(StrictModel):
    schema_version: Literal[1]
    dataset_version: Literal["experiment-d-lay-energy-gold-v1"]
    evaluation_status: Literal["approved_gold"]
    source_bank: GoldSourceBankBinding
    corpus_snapshot: GoldCorpusSnapshot
    split_manifest: GoldSplitManifest
    metric_protocol: GoldMetricProtocol
    annotation_protocol: GoldAnnotationProtocol
    cases: list[ExperimentDGoldCase] = Field(min_length=1000, max_length=1000)

    @model_validator(mode="after")
    def validate_suite_partition(self) -> ExperimentDGoldDataset:
        ids = [case.id for case in self.cases]
        questions = [case.question for case in self.cases]
        if len(set(ids)) != len(ids) or len(set(questions)) != len(questions):
            raise ValueError("gold case IDs and questions must be unique")
        if self.source_bank.question_count != len(self.cases):
            raise ValueError("source bank count and gold case count differ")

        protocol_by_id = {
            method.method_id: method for method in self.annotation_protocol.pool_methods
        }
        protocol_method_ids = set(protocol_by_id)
        for case in self.cases:
            pools = case.judgment_coverage.pool_method_candidates
            pool_method_ids = {pool.method_id for pool in pools}
            if pool_method_ids != protocol_method_ids:
                raise ValueError(
                    "every case must record candidates for every annotation pool method"
                )
            pooled_candidates: set[str] = set()
            for pool in pools:
                method = protocol_by_id[pool.method_id]
                if pool.top_k != method.top_k:
                    raise ValueError("case pool top_k must match the annotation protocol")
                if pool.top_k is not None:
                    expected_candidate_count = min(
                        pool.top_k,
                        self.corpus_snapshot.searchable_provision_count,
                    )
                    if len(pool.candidate_provision_ids) != expected_candidate_count:
                        raise ValueError(
                            "non-full pool candidate count must equal min(top_k, corpus size)"
                        )
                pooled_candidates.update(pool.candidate_provision_ids)
            if pooled_candidates != set(case.judgment_coverage.judged_candidate_provision_ids):
                raise ValueError(
                    "the union of per-method candidates must equal the judged candidate pool"
                )

        calibration = sum(case.split == "calibration" for case in self.cases)
        test = sum(case.split == "test" for case in self.cases)
        if calibration != self.split_manifest.calibration_count:
            raise ValueError("calibration split count mismatch")
        if test != self.split_manifest.test_count:
            raise ValueError("test split count mismatch")
        for split in ("calibration", "test"):
            if not any(
                case.split == split and case.answerability == "fully_answerable"
                for case in self.cases
            ):
                raise ValueError("Recall/MRR/nDCG requires a fully_answerable case in each split")

        family_splits: dict[str, set[str]] = {}
        family_counts: dict[str, int] = {}
        for case in self.cases:
            family_splits.setdefault(case.scenario_family_id, set()).add(case.split)
            family_counts[case.scenario_family_id] = (
                family_counts.get(case.scenario_family_id, 0) + 1
            )
        if any(len(splits) != 1 for splits in family_splits.values()):
            raise ValueError("scenario family leaked across calibration and test")
        if len(family_counts) != 200 or any(count != 5 for count in family_counts.values()):
            raise ValueError("gold must preserve 200 scenario families with five queries each")
        assignment_sha = hashlib.sha256(
            json.dumps(
                sorted(
                    (family_id, next(iter(splits))) for family_id, splits in family_splits.items()
                ),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if assignment_sha != self.split_manifest.assignment_sha256:
            raise ValueError("split assignment hash mismatch")

        control_pairs: dict[str, list[ExperimentDGoldCase]] = {}
        for case in self.cases:
            if case.control_pair_id is not None:
                control_pairs.setdefault(case.control_pair_id, []).append(case)
        for pair_id, pair_cases in control_pairs.items():
            if len(pair_cases) != 2:
                raise ValueError(f"control pair {pair_id} must contain exactly two cases")
            if len({case.split for case in pair_cases}) != 1:
                raise ValueError("control pair cannot cross calibration and test")
            expectations = {case.control_pair_expectation for case in pair_cases}
            if len(expectations) != 1:
                raise ValueError("control pair expectations must match")
            expectation = next(iter(expectations))
            direct_sets = [
                {qrel.provision_id for qrel in case.qrels if qrel.relevance == 2}
                for case in pair_cases
            ]
            if expectation == "same_direct_evidence" and direct_sets[0] != direct_sets[1]:
                raise ValueError("same-evidence control pair must share grade-2 qrels")
            if expectation == "different_direct_evidence" and direct_sets[0] & direct_sets[1]:
                raise ValueError("different-evidence control pair grade-2 qrels must be disjoint")
            if (
                expectation == "answerability_contrast"
                and pair_cases[0].answerability == pair_cases[1].answerability
            ):
                raise ValueError("answerability control pair must contrast answerability")
        return self


class GoldAdjudicatedCase(StrictModel):
    case_id: str = Field(min_length=1)
    case_payload_sha256: Sha256


class ExperimentDGoldAdjudicationManifest(StrictModel):
    schema_version: Literal[1]
    manifest_version: Literal["experiment-d-lay-energy-gold-adjudication-v1"]
    status: Literal["approved"]
    decision_scope: Literal["full_gold_dataset_and_case_payloads"]
    approved_by: NonBlankStr
    approved_at: datetime
    dataset_sha256: Sha256
    cases: list[GoldAdjudicatedCase] = Field(min_length=1000, max_length=1000)

    @model_validator(mode="after")
    def adjudication_is_unique_and_timestamped(
        self,
    ) -> ExperimentDGoldAdjudicationManifest:
        if self.approved_at.tzinfo is None:
            raise ValueError("gold adjudication timestamp must include a timezone")
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("gold adjudication manifest contains duplicate case IDs")
        return self


def canonical_gold_case_payload_sha256(
    case: ExperimentDGoldCase | Mapping[str, object],
) -> str:
    """Hash one complete validated gold-case payload using canonical JSON."""

    validated = (
        case if isinstance(case, ExperimentDGoldCase) else ExperimentDGoldCase.model_validate(case)
    )
    return hashlib.sha256(
        json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def canonical_gold_dataset_sha256(
    dataset: ExperimentDGoldDataset | Mapping[str, object],
) -> str:
    """Hash the complete validated gold dataset using canonical JSON."""

    validated = (
        dataset
        if isinstance(dataset, ExperimentDGoldDataset)
        else ExperimentDGoldDataset.model_validate(dataset)
    )
    return hashlib.sha256(
        json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
