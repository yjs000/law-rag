from law_rag_agent.nodes.validate import validate_node


def test_validate_node_passes_through_answer_with_citations():
    state = {
        "draft_answer": "태양광은 신에너지법 제2조에서 정의합니다.",
        "draft_citations": [
            {
                "id": "C1",
                "path": "제2조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
            }
        ],
        "draft_action": "fully_answerable",
        "search_hits": [
            {
                "path": "제2조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
            }
        ],
    }

    update = validate_node(state)

    assert update["final_answer"] == "태양광은 신에너지법 제2조에서 정의합니다."
    assert update["final_citations"] == state["draft_citations"]


def test_validate_node_blocks_citation_that_does_not_match_retrieved_evidence():
    state = {
        "draft_answer": "이건 무조건 허용됩니다.",
        "draft_citations": [
            {
                "id": "C1",
                "path": "제99조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
            }
        ],
        "draft_action": "fully_answerable",
        "search_hits": [
            {
                "path": "제2조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
            }
        ],
    }

    update = validate_node(state)

    assert "검색된 근거" in update["final_answer"]
    assert update["final_citations"] == [
        {
            "id": "C1",
            "path": "제2조",
            "document_title": "신에너지법",
            "source_url": "https://example.test/1",
        }
    ]


def test_validate_node_blocks_uncited_claims():
    state = {
        "draft_answer": "이건 무조건 허용됩니다.",
        "draft_citations": [],
        "draft_action": "fully_answerable",
        "search_hits": [
            {
                "path": "제2조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
            }
        ],
    }

    update = validate_node(state)

    assert "검색된 근거" in update["final_answer"]
    assert update["final_citations"] == [
        {
            "id": "C1",
            "path": "제2조",
            "document_title": "신에너지법",
            "source_url": "https://example.test/1",
        }
    ]


def test_validate_node_suppresses_unanswerable_arbitrary_legal_claim():
    state = {
        "draft_answer": "이건 무조건 허용됩니다.",
        "draft_citations": [],
        "draft_action": "unanswerable",
        "search_hits": [
            {
                "path": "제2조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
            }
        ],
    }

    update = validate_node(state)

    assert update["final_answer"] == (
        "검색된 근거가 부족하여 답변을 확정할 수 없습니다. 제공된 검색 결과를 직접 확인하세요."
    )
    assert update["final_citations"] == [
        {
            "id": "C1",
            "path": "제2조",
            "document_title": "신에너지법",
            "source_url": "https://example.test/1",
        }
    ]
