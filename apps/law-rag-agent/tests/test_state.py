from datetime import UTC, datetime

from law_rag_agent.state import AgentState, Turn, append_turn


def _turn(question: str) -> Turn:
    return Turn(
        question=question,
        answer="답변",
        citations=[{"id": "C1", "path": "제1조"}],
        route="legal_search",
        created_at=datetime.now(UTC),
    )


def test_turn_requires_all_fields():
    turn = _turn("질문1")
    assert turn.question == "질문1"
    assert turn.route == "legal_search"
    assert turn.citations[0]["id"] == "C1"


def test_append_turn_does_not_mutate_input_state():
    state: AgentState = {
        "thread_id": "t1",
        "turns": [_turn("질문1")],
        "question": "",
        "as_of_date": "2026-08-19",
        "route": None,
        "search_hits": [],
        "draft_answer": None,
        "draft_citations": [],
        "draft_action": None,
        "final_answer": None,
        "final_citations": [],
    }
    original_turns = state["turns"]
    new_state = append_turn(state, _turn("질문2"))
    assert len(state["turns"]) == 1
    assert state["turns"] is original_turns
    assert len(new_state["turns"]) == 2
    assert new_state["turns"][0].question == "질문1"
    assert new_state["turns"][1].question == "질문2"
