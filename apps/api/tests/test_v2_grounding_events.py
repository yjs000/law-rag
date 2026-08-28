from app.domain.answer_events import AnswerEvent, EventProtocolError
from app.domain.grounding import CitationRegistry, FrozenCitation, GroundedSentence


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


def test_complete_cannot_be_combined_with_error_or_cancelled() -> None:
    assert AnswerEvent.complete({"outcome": "normal"}).event_type == "complete"

    for terminal in ("error", "cancelled"):
        try:
            AnswerEvent(event_type=terminal, payload={}, terminal=True, is_complete=True)
        except EventProtocolError:
            pass
        else:
            raise AssertionError(f"{terminal} must be exclusive from complete")
