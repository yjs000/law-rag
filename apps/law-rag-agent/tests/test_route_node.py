import pytest

from law_rag_agent.nodes.route import route_node
from law_rag_agent.schemas import RouteDecision


class FakeStructuredLLM:
    def __init__(self, decision: RouteDecision):
        self._decision = decision
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return self._decision


@pytest.mark.asyncio
async def test_route_node_returns_route_from_llm_decision():
    fake_llm = FakeStructuredLLM(RouteDecision(route="legal_search", reason="에너지 법령 질문"))
    state = {"question": "태양광 설비 인허가 요건이 뭐야", "as_of_date": "2026-08-19", "turns": []}

    update = await route_node(state, fake_llm)

    assert update == {"route": "legal_search"}
    assert fake_llm.last_messages is not None


@pytest.mark.asyncio
async def test_route_node_passes_question_text_to_llm():
    fake_llm = FakeStructuredLLM(
        RouteDecision(route="clarification_required", reason="설비용량 누락")
    )
    state = {"question": "인허가 받을 수 있어?", "as_of_date": "2026-08-19", "turns": []}

    update = await route_node(state, fake_llm)

    assert update == {"route": "clarification_required"}
    assert "인허가 받을 수 있어?" in str(fake_llm.last_messages)
