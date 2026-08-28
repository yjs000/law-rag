from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class EventProtocolError(ValueError):
    pass


_TERMINAL_EVENT_TYPES = frozenset({"complete", "error", "cancelled"})


@dataclass(frozen=True)
class AnswerEvent:
    event_type: str
    payload: Mapping[str, object]
    terminal: bool = False
    is_complete: bool = False

    def __post_init__(self) -> None:
        if self.event_type not in _TERMINAL_EVENT_TYPES and (self.terminal or self.is_complete):
            raise EventProtocolError("only terminal event types may be terminal")
        if self.event_type == "complete":
            if not self.terminal or not self.is_complete:
                raise EventProtocolError("complete must be the complete terminal event")
            return
        if self.event_type in _TERMINAL_EVENT_TYPES:
            if not self.terminal or self.is_complete:
                raise EventProtocolError("error and cancelled are terminal but never complete")

    @classmethod
    def complete(cls, response: Mapping[str, object]) -> AnswerEvent:
        return cls(event_type="complete", payload=response, terminal=True, is_complete=True)

    @classmethod
    def error(cls, reason_code: str) -> AnswerEvent:
        return cls(event_type="error", payload={"reason_code": reason_code}, terminal=True)

    @classmethod
    def cancelled(cls) -> AnswerEvent:
        return cls(event_type="cancelled", payload={}, terminal=True)
