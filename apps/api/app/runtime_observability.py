from __future__ import annotations

import json
import logging
import re
import traceback
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Literal, TypedDict
from uuid import uuid4

ErrorLogMode = Literal["raw", "redacted"]
PipelineStage = Literal[
    "request_validation",
    "routing",
    "retrieval",
    "answer_generation",
    "grounding_validation",
    "persistence",
    "response_serialization",
]


class SerializedCause(TypedDict):
    exception_type: str
    message: str
    stack_trace: str


class SerializedException(SerializedCause):
    cause_chain: list[SerializedCause]


@dataclass
class _RuntimeObservationState:
    correlation: str
    stage: PipelineStage
    logged_exception_ids: set[int] = field(default_factory=set)

_LOGGER = logging.getLogger("law_rag.runtime_exception")
_LOGGER.setLevel(logging.ERROR)
_CORRELATION: ContextVar[str | None] = ContextVar("runtime_correlation", default=None)
_STAGE: ContextVar[PipelineStage] = ContextVar(
    "runtime_pipeline_stage", default="request_validation"
)
_LOGGED_EXCEPTION_IDS: ContextVar[set[int] | None] = ContextVar(
    "runtime_logged_exception_ids", default=None
)
_OBSERVATION_STATE: ContextVar[_RuntimeObservationState | None] = ContextVar(
    "runtime_observation_state", default=None
)

_SECRET_PATTERNS = (
    (
        re.compile(
            r'''(?i)(["'](?:question|prompt|content|answer|authorization|api[_-]?key|token|password)["']\s*:\s*)["'][^"']*["']'''
        ),
        r'''\1"[REDACTED]"''',
    ),
    (re.compile(r"(?i)Bearer\s+[^\s,;]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)nvapi-[A-Za-z0-9_-]+"), "[REDACTED]"),
    (
        re.compile(r"(?i)postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^@\s]+@"),
        "postgresql://[REDACTED]@",
    ),
    (re.compile(r"(?is)\[parameters:\s*.*?\]"), "[parameters: [REDACTED]]"),
    (
        re.compile(
            r"(?is)\b(question|prompt|content|answer)\s*[=:]\s*.*?(?=\s+\[|$)"
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(authorization|api[_-]?key|token|password)\s*[=:]\s*[^\s,;]+"
        ),
        r"\1=[REDACTED]",
    ),
)
_MAX_DETAIL_CHARACTERS = 4096
_MAX_CAUSE_DEPTH = 8


def _hash_source(source: object) -> str:
    return sha256(str(source).encode("utf-8")).hexdigest()[:16]


def _redact(text: str) -> str:
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted[:_MAX_DETAIL_CHARACTERS]


def _format_stack(error: BaseException) -> str:
    return "".join(traceback.format_tb(error.__traceback__))


def _serialize_cause(error: BaseException, mode: ErrorLogMode) -> SerializedCause:
    message = str(error)
    stack_trace = _format_stack(error)
    if mode == "redacted":
        message = _redact(message)
        stack_trace = _redact(stack_trace)
    return {
        "exception_type": type(error).__name__,
        "message": message[:_MAX_DETAIL_CHARACTERS],
        "stack_trace": stack_trace[:_MAX_DETAIL_CHARACTERS],
    }


def serialize_exception(
    error: BaseException, *, mode: ErrorLogMode
) -> SerializedException:
    """Serialize one exception and its explicit or implicit cause chain."""

    primary = _serialize_cause(error, mode)
    causes: list[SerializedCause] = []
    seen = {id(error)}
    cause = error.__cause__ or error.__context__
    while cause is not None and len(causes) < _MAX_CAUSE_DEPTH and id(cause) not in seen:
        seen.add(id(cause))
        causes.append(_serialize_cause(cause, mode))
        cause = cause.__cause__ or cause.__context__
    return {**primary, "cause_chain": causes}


@contextmanager
def runtime_observation_scope(
    correlation_source: object | None = None,
    *,
    initial_stage: PipelineStage = "request_validation",
) -> Iterator[None]:
    """Bind correlation, stage, and duplicate suppression to one request."""

    if _OBSERVATION_STATE.get() is not None:
        yield
        return

    source = uuid4() if correlation_source is None else correlation_source
    state_token = _OBSERVATION_STATE.set(
        _RuntimeObservationState(
            correlation=_hash_source(source),
            stage=initial_stage,
        )
    )
    try:
        yield
    finally:
        _OBSERVATION_STATE.reset(state_token)


def set_pipeline_stage(stage: PipelineStage) -> None:
    state = _OBSERVATION_STATE.get()
    if state is not None:
        state.stage = stage
        return
    _STAGE.set(stage)


def current_pipeline_stage() -> PipelineStage:
    state = _OBSERVATION_STATE.get()
    return state.stage if state is not None else _STAGE.get()


def current_runtime_correlation() -> str:
    state = _OBSERVATION_STATE.get()
    if state is not None:
        return state.correlation
    return _CORRELATION.get() or _hash_source(uuid4())


def bind_runtime_correlation(source: object) -> None:
    correlation = _hash_source(source)
    state = _OBSERVATION_STATE.get()
    if state is not None:
        state.correlation = correlation
        return
    _CORRELATION.set(correlation)


def emit_runtime_exception(
    error: BaseException,
    *,
    operation: str,
    mode: ErrorLogMode,
) -> None:
    """Emit one structured exception event per exception object and request."""

    state = _OBSERVATION_STATE.get()
    logged_ids = state.logged_exception_ids if state is not None else _LOGGED_EXCEPTION_IDS.get()
    if logged_ids is None:
        logged_ids = set()
        _LOGGED_EXCEPTION_IDS.set(logged_ids)
    error_id = id(error)
    if error_id in logged_ids:
        return
    logged_ids.add(error_id)

    payload = {
        "event_type": "runtime_exception",
        "correlation": current_runtime_correlation(),
        "pipeline_stage": current_pipeline_stage(),
        "operation": operation,
        **serialize_exception(error, mode=mode),
    }
    _LOGGER.error(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _has_handler_chain(logger: logging.Logger) -> bool:
    current: logging.Logger | None = logger
    while current is not None:
        if current.handlers:
            return True
        if not current.propagate:
            return False
        current = current.parent
    return False


def configure_runtime_logging(_mode: ErrorLogMode) -> None:
    """Ensure law-rag INFO/ERROR events reach a terminal exactly once."""

    logger = logging.getLogger("law_rag")
    logger.setLevel(logging.INFO)
    if _has_handler_chain(logger):
        return

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

def install_runtime_exception_middleware(
    application: Any, *, mode: ErrorLogMode
) -> None:
    """Log uncaught request failures while preserving FastAPI's safe response."""

    configure_runtime_logging(mode)

    @application.middleware("http")
    async def runtime_exception_boundary(
        request: Any,
        call_next: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        correlation_source = (
            request.headers.get("x-request-id")
            or request.headers.get("idempotency-key")
            or uuid4()
        )
        with runtime_observation_scope(correlation_source):
            try:
                return await call_next(request)
            except Exception as error:
                emit_runtime_exception(
                    error,
                    operation=f"{request.method} {request.url.path}",
                    mode=mode,
                )
                raise
