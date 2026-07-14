import json
import logging
from collections import Counter
from threading import Lock
from typing import Literal

from pydantic import BaseModel

from app.domain.schemas import AnswerMode

logger = logging.getLogger("law_rag.question_outcome")
_served_by_mode: Counter[str] = Counter()
_metrics_lock = Lock()


class QuestionOutcomeEvent(BaseModel):
    request_id: str
    mode: AnswerMode
    result: Literal["served"] = "served"


def emit_question_outcome(request_id: str, mode: AnswerMode) -> None:
    """질문·원문·사용자·비밀을 받을 수 없는 최소 관측 경계."""
    event = QuestionOutcomeEvent(request_id=request_id, mode=mode)
    with _metrics_lock:
        _served_by_mode[mode.value] += 1
    logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))


def question_metrics_snapshot() -> dict[str, int]:
    """외부 메트릭 백엔드 연결 전 사용하는 프로세스 로컬 누계."""
    with _metrics_lock:
        return dict(_served_by_mode)
