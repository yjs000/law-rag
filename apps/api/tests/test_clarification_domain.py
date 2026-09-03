import pytest

from app.domain.clarification import (
    ClarificationCase,
    FactStatus,
    GroundedClaim,
    RequiredFact,
    group_remaining_facts,
    validate_claim,
)
from app.domain.grounding import CitationRegistry, FrozenCitation


def _fact(identifier: str, *, blocking: bool = True, status: FactStatus = FactStatus.UNANSWERED):
    return RequiredFact(identifier, identifier, "판단에 필요", blocking, "사업 정보", 1, status)


def test_case_is_sufficient_only_when_every_blocking_fact_is_answered():
    case = ClarificationCase((_fact("capacity", status=FactStatus.ANSWERED), _fact("site")))
    assert not case.all_blocking_facts_answered()
    assert case.with_fact_status("site", FactStatus.ANSWERED).all_blocking_facts_answered()


def test_remaining_format_omits_answered_and_declined_facts():
    case = ClarificationCase(
        (
            _fact("capacity", status=FactStatus.ANSWERED),
            _fact("site"),
            _fact("operator", status=FactStatus.DECLINED),
        )
    )
    assert [fact.id for fact in case.remaining_facts()] == ["site"]


def test_six_remaining_facts_are_grouped_into_at_most_five():
    assert len(group_remaining_facts(tuple(_fact(f"fact-{n}") for n in range(6)))) == 5


def test_case_application_claim_requires_citation_and_answered_fact():
    case = ClarificationCase((_fact("capacity", status=FactStatus.ANSWERED), _fact("site")))
    citations = CitationRegistry((FrozenCitation(id="C1", quote="법령 근거"),))
    assert validate_claim(
        GroundedClaim(
            "용량",
            "case_application",
            ("C1",),
            surface="summary",
            surface_index=None,
            required_fact_ids=("capacity",),
        ),
        case,
        citations,
    )
    assert not validate_claim(
        GroundedClaim(
            "입지",
            "case_application",
            ("C1",),
            surface="summary",
            surface_index=None,
            required_fact_ids=("site",),
        ),
        case,
        citations,
    )


def test_case_application_with_an_unknown_fact_id_is_rejected_without_raising() -> None:
    case = ClarificationCase((_fact("capacity", status=FactStatus.ANSWERED),))
    citations = CitationRegistry((FrozenCitation(id="C1", quote="법령 근거"),))

    assert not validate_claim(
        GroundedClaim(
            "알 수 없는 사실",
            "case_application",
            ("C1",),
            surface="summary",
            surface_index=None,
            required_fact_ids=("missing",),
        ),
        case,
        citations,
    )


def test_grounded_claim_requires_an_explicit_published_target() -> None:
    with pytest.raises(TypeError):
        GroundedClaim("일반 규칙", "general_rule", ("C1",))
