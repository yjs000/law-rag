"""V2 question-execution application use cases.

This package owns the framework-independent prepare, core, and finalize flow.
HTTP/SSE presentation and SDK construction intentionally stay outside it.
"""

from app.application.v2.phase_service import V2QuestionExecutionService

__all__ = ["V2QuestionExecutionService"]
