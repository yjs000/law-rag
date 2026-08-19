_ROUTE_PROMPT = """당신은 에너지 법령 질문을 다음 네 가지 중 하나로 분류하는 라우터입니다.

- legal_search: 법령 검색으로 답할 수 있는 질문
- clarification_required: 답하려면 설비용량 등 사용자 사실관계가 더 필요한 질문
- realtime_required: 실시간 정보(시세, 오늘 날씨 등)가 있어야 답할 수 있는 질문
- external_document_required: 법령이 아닌 외부 문서(계약서, 내부 규정 등)가 있어야 답할 수 있는 질문

질문: {question}
기준일: {as_of_date}
"""


async def route_node(state, llm) -> dict:
    prompt = _ROUTE_PROMPT.format(question=state["question"], as_of_date=state["as_of_date"])
    decision = await llm.ainvoke([{"role": "user", "content": prompt}])
    return {"route": decision.route}


def build_route_node(llm):
    async def _node(state):
        return await route_node(state, llm)

    return _node
