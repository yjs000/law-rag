from law_rag_agent.nodes.validate import validate_node


def test_validate_node_passes_through_answer_with_citations():
    state = {
        "draft_answer": "태양광은 신에너지법 제2조에서 정의합니다.",
        "draft_citations": [{"id": "C1", "path": "제2조"}],
        "draft_action": "fully_answerable",
        "search_hits": [{"path": "제2조", "document_title": "신에너지법"}],
    }

    update = validate_node(state)

    assert update["final_answer"] == "태양광은 신에너지법 제2조에서 정의합니다."
    assert update["final_citations"] == [{"id": "C1", "path": "제2조"}]


def test_validate_node_blocks_uncited_claims():
    state = {
        "draft_answer": "이건 무조건 허용됩니다.",
        "draft_citations": [],
        "draft_action": "fully_answerable",
        "search_hits": [{"path": "제2조", "document_title": "신에너지법"}],
    }

    update = validate_node(state)

    assert "근거" in update["final_answer"]
    assert update["final_citations"] == []


def test_validate_node_passes_through_unanswerable_with_no_citations():
    state = {
        "draft_answer": "이 질문은 현재 법령 정보만으로 답할 수 없습니다.",
        "draft_citations": [],
        "draft_action": "unanswerable",
        "search_hits": [],
    }

    update = validate_node(state)

    assert update["final_answer"] == "이 질문은 현재 법령 정보만으로 답할 수 없습니다."
    assert update["final_citations"] == []
