from datetime import date
from uuid import uuid4

from app.application.v2.evidence import freeze_citations
from app.domain.answer_events import AnswerEvent, EventProtocolError
from app.domain.catalog import SourceKind
from app.domain.grounding import CitationRegistry, FrozenCitation, GroundedSentence
from app.domain.schemas import SearchHit


def _registry() -> CitationRegistry:
    return CitationRegistry(
        [
            FrozenCitation(
                id="C1",
                quote="전기사업을 하려는 자는 산업통상자원부장관의 허가를 받아야 한다.",
            )
        ]
    )


def test_grounding_rejects_absent_or_unknown_citations() -> None:
    registry = _registry()

    assert not registry.verify(GroundedSentence("허가가 필요합니다.", ()))
    assert not registry.verify(GroundedSentence("허가가 필요합니다.", ("C99",)))


def test_grounding_rejects_unsupported_number_norm_and_overclaim() -> None:
    registry = _registry()

    assert not registry.verify(GroundedSentence("30일 안에 허가를 받아야 합니다.", ("C1",)))
    assert not registry.verify(GroundedSentence("반드시 신고해야 합니다.", ("C1",)))
    assert not registry.verify(GroundedSentence("모든 전기사업은 허가가 필요합니다.", ("C1",)))


def test_grounding_accepts_a_directly_supported_norm() -> None:
    assert _registry().verify(GroundedSentence("허가를 받아야 합니다.", ("C1",)))


def test_grounding_accepts_article_numbers_from_frozen_source_metadata() -> None:
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제7조",
        content="① 전기사업을 하려는 자는 허가를 받아야 한다.",
        source_url="https://www.law.go.kr/법령/전기사업법/제7조",
    )

    frozen = freeze_citations([hit])

    assert frozen[0].document_title == "전기사업법"
    assert frozen[0].path == "제7조"
    assert CitationRegistry(frozen).verify(
        GroundedSentence("전기사업법 제7조 제1항은 전기사업 허가를 규정합니다.", ("C1",))
    )


def test_complete_cannot_be_combined_with_error_or_cancelled() -> None:
    assert AnswerEvent.complete({"outcome": "normal"}).event_type == "complete"

    for terminal in ("error", "cancelled"):
        try:
            AnswerEvent(event_type=terminal, payload={}, terminal=True, is_complete=True)
        except EventProtocolError:
            pass
        else:
            raise AssertionError(f"{terminal} must be exclusive from complete")
