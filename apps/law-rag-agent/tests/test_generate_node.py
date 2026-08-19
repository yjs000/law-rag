import pytest

from law_rag_agent.nodes.generate import generate_node
from law_rag_agent.schemas import GenerationResult


class FakeStructuredLLM:
    def __init__(self, result: GenerationResult):
        self._result = result
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return self._result


@pytest.mark.asyncio
async def test_generate_node_maps_citation_ids_to_search_hits():
    fake_llm = FakeStructuredLLM(
        GenerationResult(
            answer="태양광은 신에너지법 제2조에서 정의합니다.",
            citation_ids=["C1"],
            action="fully_answerable",
        )
    )
    state = {
        "question": "태양광 정의가 뭐야",
        "search_hits": [
            {
                "path": "제2조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/1",
                "content": "본문1",
            },
            {
                "path": "제3조",
                "document_title": "신에너지법",
                "source_url": "https://example.test/2",
                "content": "본문2",
            },
        ],
    }

    update = await generate_node(state, fake_llm)

    assert update["draft_answer"] == "태양광은 신에너지법 제2조에서 정의합니다."
    assert update["draft_action"] == "fully_answerable"
    assert update["draft_citations"] == [
        {
            "id": "C1",
            "path": "제2조",
            "document_title": "신에너지법",
            "source_url": "https://example.test/1",
        }
    ]


@pytest.mark.asyncio
async def test_generate_node_ignores_citation_ids_outside_search_hits_range():
    fake_llm = FakeStructuredLLM(
        GenerationResult(answer="답변", citation_ids=["C1", "C9"], action="fully_answerable")
    )
    state = {
        "question": "질문",
        "search_hits": [
            {
                "path": "제1조",
                "document_title": "법",
                "source_url": "https://example.test",
                "content": "본문",
            }
        ],
    }

    update = await generate_node(state, fake_llm)

    assert len(update["draft_citations"]) == 1
    assert update["draft_citations"][0]["id"] == "C1"
