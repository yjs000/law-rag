from app.application.final_answer import FinalAnswerCoordinator, VerifiedAnswer
from app.domain.grounding import CitationRegistry, FrozenCitation, GroundedSentence
from app.domain.pipeline_issues import ExecutionPhase, PipelineIssue


def test_pipeline_issue_normalizes_a_valid_phase_before_persistence() -> None:
    issue = PipelineIssue(
        phase="finalize",
        stage="provider",
        public_reason_code="provider_unavailable",
        recoverable=True,
    )

    assert issue.phase is ExecutionPhase.FINALIZE


def test_verified_core_survives_a_recoverable_finalize_failure() -> None:
    evidence = CitationRegistry([FrozenCitation(id="C1", quote="허가를 받아야 한다.")])
    verified = VerifiedAnswer(
        summary=(GroundedSentence("허가를 받아야 합니다.", ("C1",)),),
        sections=(),
        checklist=(),
    )
    issue = PipelineIssue(
        phase="finalize",
        stage="provider",
        public_reason_code="provider_unavailable",
        recoverable=True,
    )

    result = FinalAnswerCoordinator().finalize(
        verified=verified,
        evidence=evidence,
        issues=(issue,),
        remaining_seconds=0,
    )

    assert result.outcome == "degraded"
    assert result.summary == verified.summary
    assert result.citations == evidence.citations
