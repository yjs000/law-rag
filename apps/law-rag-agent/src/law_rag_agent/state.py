from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel


class Turn(BaseModel):
    question: str
    answer: str
    citations: list[dict]
    route: str
    created_at: datetime


class AgentState(TypedDict):
    thread_id: str
    turns: list[Turn]
    question: str
    as_of_date: str
    route: str | None
    search_hits: list[dict]
    draft_answer: str | None
    draft_citations: list[dict]
    draft_action: str | None
    final_answer: str | None
    final_citations: list[dict]


def append_turn(state: AgentState, turn: Turn) -> AgentState:
    return {**state, "turns": [*state["turns"], turn]}
