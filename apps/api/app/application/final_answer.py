from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.grounding import CitationRegistry, FrozenCitation, GroundedSection, GroundedSentence
from app.domain.pipeline_issues import PipelineIssue


@dataclass(frozen=True)
class VerifiedAnswer:
    summary: tuple[GroundedSentence, ...]
    sections: tuple[GroundedSection, ...]
    checklist: tuple[GroundedSentence, ...]


@dataclass(frozen=True)
class FinalAnswer:
    outcome: str
    summary: tuple[GroundedSentence, ...]
    sections: tuple[GroundedSection, ...]
    checklist: tuple[GroundedSentence, ...]
    citations: tuple[FrozenCitation, ...]
    limitations: tuple[str, ...]


class FinalAnswerCoordinator:
    """Choose one authoritative terminal response from already verified content."""

    def finalize(
        self,
        *,
        verified: VerifiedAnswer,
        evidence: CitationRegistry,
        issues: Iterable[PipelineIssue],
        remaining_seconds: float,
    ) -> FinalAnswer:
        del remaining_seconds
        recorded_issues = tuple(issues)
        if verified.summary:
            degraded = bool(recorded_issues)
            return FinalAnswer(
                outcome="degraded" if degraded else "normal",
                summary=verified.summary,
                sections=verified.sections,
                checklist=verified.checklist,
                citations=evidence.citations,
                limitations=(
                    "일부 상세 설명을 확정하지 못했습니다. 인용된 공식 원문을 확인해 주세요.",
                )
                if degraded
                else (),
            )
        return FinalAnswer(
            outcome="degraded",
            summary=(),
            sections=(),
            checklist=(),
            citations=evidence.citations,
            limitations=(
                "확정된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요.",
            ),
        )
