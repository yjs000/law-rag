"""Pure clarification-case state and structural claim validation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import UUID

if TYPE_CHECKING:
    from app.domain.grounding import CitationRegistry


class FactStatus(StrEnum):
    UNANSWERED = "unanswered"
    ANSWERED = "answered"
    DECLINED = "declined"
    INVALID = "invalid"
    CONFLICTING = "conflicting"
    NO_LONGER_NEEDED = "no_longer_needed"


@dataclass(frozen=True)
class RequiredFact:
    id: str
    label: str
    why_needed: str
    blocking: bool
    group: str
    priority: int
    status: FactStatus = FactStatus.UNANSWERED
    value: object | None = None
    source_turn_id: UUID | None = None


@dataclass(frozen=True)
class ClarificationCase:
    required_facts: tuple[RequiredFact, ...]

    def all_blocking_facts_answered(self) -> bool:
        return all(f.status is FactStatus.ANSWERED for f in self.required_facts if f.blocking)

    def remaining_facts(self) -> tuple[RequiredFact, ...]:
        done = {FactStatus.ANSWERED, FactStatus.DECLINED, FactStatus.NO_LONGER_NEEDED}
        return tuple(f for f in self.required_facts if f.status not in done)

    def fact(self, identifier: str) -> RequiredFact:
        for fact in self.required_facts:
            if fact.id == identifier:
                return fact
        raise KeyError(identifier)

    def with_fact_status(self, identifier: str, status: FactStatus) -> ClarificationCase:
        return replace(
            self,
            required_facts=tuple(
                replace(f, status=status) if f.id == identifier else f for f in self.required_facts
            ),
        )


def group_remaining_facts(facts: tuple[RequiredFact, ...]) -> tuple[RequiredFact, ...]:
    return facts if len(facts) <= 5 else tuple(sorted(facts, key=lambda f: f.priority)[:5])


@dataclass(frozen=True)
class GroundedClaim:
    text: str
    claim_kind: str
    citation_ids: tuple[str, ...]
    surface: Literal["summary", "section_claim", "section_explanation", "checklist_label"]
    surface_index: int | None
    required_fact_ids: tuple[str, ...] = ()


def validate_claim(
    claim: GroundedClaim, case: ClarificationCase, citations: CitationRegistry
) -> bool:
    if not claim.text.strip() or not claim.citation_ids:
        return False
    known = {item.id for item in citations.citations}
    if any(identifier not in known for identifier in claim.citation_ids):
        return False
    facts_by_id = {fact.id: fact for fact in case.required_facts}
    if claim.claim_kind == "general_rule":
        return not claim.required_fact_ids
    if claim.claim_kind == "case_application":
        return bool(claim.required_fact_ids) and all(
            facts_by_id.get(identifier) is not None
            and facts_by_id[identifier].status is FactStatus.ANSWERED
            for identifier in claim.required_fact_ids
        )
    if claim.claim_kind == "conditional":
        return bool(claim.required_fact_ids) and all(
            identifier in facts_by_id for identifier in claim.required_fact_ids
        )
    return False
