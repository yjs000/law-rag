> 작업 ID: `B-006`
> 상태: `Picked Up`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `Security`
> 선행 조건: [승인된 provider 시도별 관측 설계](../../design-docs/provider-attempt-observability.md); `B-005`와 별도 worktree에서 병렬 구현하고 통합 뒤 최종 재검증
> 다음 행동: Task 1의 provider attempt event 개인정보 회귀 테스트를 RED로 만든다.
> 참고 범위:
> - `docs/design-docs/provider-attempt-observability.md` L1-L174 — 승인된 로그·실패 분류·개인정보 계약
> - `apps/api/app/adapters/nvidia_nim_answerer.py` L26-L174 — 대표 NVIDIA 제한 재시도와 전체 deadline
> - `apps/api/app/application/question_phase_coordinator.py` L48-L145 — provider 예외를 뭉개는 V2 phase catch-all

# NVIDIA Provider Attempt Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Also use `picked-up-plan-runner` to keep exactly this plan active until every task is complete and `agent-operating-harness:execution-harness` for bounded execution evidence.

**Goal:** NVIDIA 호출마다 실제 시도 횟수와 각 시도의 성공·실패 종류를 개인정보 없는 Vercel JSON 로그로 남기고, draft조차 만들지 못한 provider 소진을 grounding 실패와 분리해 사용자에게 안전하게 안내한다.

**Architecture:** 새 `provider_attempts` domain 모듈은 provider 가용성 소진 예외만 정의하고, 새 `provider_observability` 모듈은 닫힌 이벤트 schema, async-safe correlation scope, 예외 분류, 단일 logger를 소유한다. 각 NVIDIA adapter가 실제 호출 직후 성공·실패 이벤트를 출력하며 기존 재시도 횟수와 timeout은 유지한다. V1/V2 application 경계가 client request ID를 correlation scope에 바인딩하고, V2 coordinator는 typed provider 소진만 `provider_unavailable` terminal error로 저장한다. Web transport는 이 reason code를 고정된 안전 문구의 `ApiError`로 바꾸며 새 execution을 자동 생성하지 않는다.

**Tech Stack:** Python 3.14, FastAPI, Pydantic 2, OpenAI Python SDK의 NVIDIA-compatible client, pytest, Next.js 16, TypeScript 5.9, Vitest 4, Vercel stdout logging.

**Spec:** `docs/design-docs/provider-attempt-observability.md`

## Global Constraints

- `B-005`와 별도 worktree·branch에서 병렬 구현한다. 겹치는 Web 파일은 이 브랜치에서 독립 검증하고, B-005 통합 뒤 rebase/merge conflict를 해결해 전체 검증을 다시 실행한다.
- DB table, migration, `question_execution_issues`, 외부 telemetry backend를 추가하지 않는다.
- NVIDIA 호출 횟수, adapter timeout, V2 phase timeout, Web reconnect/retry 예산을 변경하지 않는다.
- 질문·prompt·검색 hit·법률 원문·citation quote·provider body·예외 메시지·traceback·API key·인증정보·사용자 식별자를 로그 모델이나 logger 인수로 받지 않는다.
- correlation은 client request ID 또는 execution ID의 SHA-256 앞 16자리만 출력한다. 원본 ID는 `ContextVar` scope 밖으로 노출하지 않는다.
- 모든 NVIDIA 경계는 성공도 기록한다. 실패 뒤 성공하면 앞선 실패 로그를 지우거나 집계하지 않는다.
- provider HTTP·timeout·connection 소진만 `provider_unavailable`이다. draft 생성 뒤 schema·citation·grounding 검증 실패의 기존 `repair_core` 흐름은 유지한다.
- route, query embedding, clarification의 현재 안전 fallback을 유지한다.
- `phase_service.py`, `bootstrap.py`, `page.tsx`처럼 이미 500줄을 넘는 source file은 확장하지 않는다.
- 로컬 단위 테스트에서는 NVIDIA, Supabase, Vercel에 실제로 접속하지 않는다.
- 기존 dirty `graphify-out/` 파일은 수정·stage·commit하지 않는다.

## File Structure and Change Budget

| File | Responsibility | Estimated delta |
| --- | --- | ---: |
| `apps/api/app/domain/provider_attempts.py` | provider 가용성 소진의 sanitized typed error | new, 20-30 lines |
| `apps/api/app/provider_observability.py` | 닫힌 event, correlation scope, 분류기, JSON logger | new, 100-130 lines |
| `apps/api/tests/test_provider_observability.py` | schema·hash·분류·금지정보 회귀 | new, 140-190 lines |
| `apps/api/app/adapters/nvidia_nim_answerer.py` | core/detail/clarification 시도별 계측 | +55/-10 lines |
| `apps/api/tests/test_nvidia_nim_attempt_observability.py` | 503→timeout→성공, 전부 실패, 402/429 | new, 180-240 lines |
| `apps/api/app/adapters/nvidia_nim_route_classifier.py` | 기존 route 축약 로그를 공통 event로 교체 | +30/-25 lines |
| `apps/api/app/adapters/nvidia_nim_embedder.py` | query embedding 단일 시도 계측 | +25 lines |
| `apps/api/app/adapters/nvidia_nim_clarification.py` | clarification 단일 시도 계측 | +25 lines |
| `apps/api/tests/test_nvidia_provider_operation_observability.py` | route/embed/clarification operation 회귀 | new, 180-240 lines |
| `apps/api/app/api/v1/questions.py` | V1 client request correlation scope | +5 lines |
| `apps/api/app/api/v2/executions.py` | V2 prepare correlation scope | +5 lines |
| `apps/api/app/application/question_phase_coordinator.py` | V2 producer scope와 typed terminal mapping | +30/-5 lines |
| `apps/api/tests/test_question_phase_coordinator.py` | provider 소진과 repair 분리 | +50-70 lines; 180줄 미만 유지 |
| `apps/web/lib/v2-execution.ts` | typed SSE phase error | +18/-3 lines |
| `apps/web/lib/api-client.ts` | 안전한 provider 불가 안내 | +14/-2 lines |
| `apps/web/lib/v2-execution.test.ts` | reason code 전달 회귀 | +25 lines |
| `apps/web/lib/api-client-flow.test.ts` | 사용자용 고정 문구와 no-auto-retry 회귀 | +35 lines |
| `docs/RELIABILITY.md` | 로그-only 운영 계약과 failure semantics | +12-18 lines |
| `docs/references/operations-runbook.md` | Vercel에서 execution별 시도 로그 판독법 | +20-30 lines |

## Public Interfaces

구현자는 아래 이름과 타입을 먼저 고정한다. 서로 다른 adapter가 자체 문자열 분류기를 다시 만들지 않는다.

```python
# apps/api/app/domain/provider_attempts.py
from typing import Literal

ProviderAvailabilityFailureKind = Literal["provider_http", "timeout", "connection"]


class ProviderAttemptsExhausted(RuntimeError):
    def __init__(
        self,
        *,
        failure_kind: ProviderAvailabilityFailureKind,
        upstream_status: int | None,
    ) -> None:
        super().__init__("provider attempts exhausted")
        self.failure_kind = failure_kind
        self.upstream_status = upstream_status
```

`apps/api/app/provider_observability.py`의 공개 interface는 다음으로 고정한다.

- `ProviderOperation`: `route | query_embedding | answer_core | answer_detail | clarification`
- `ProviderFailureKind`: `provider_http | timeout | connection | invalid_response | schema_validation | cancelled | unknown`
- `ProviderAttemptOutcome`: `succeeded | failed`
- `provider_attempt_scope(source: object | None = None) -> ContextManager[None]`
- `classify_provider_failure(error: BaseException) -> tuple[ProviderFailureKind, int | None]`
- `emit_provider_attempt(*, operation, attempt, max_attempts, outcome, failure_kind, upstream_status, elapsed_ms, remaining_ms, retry_scheduled) -> None`

### Task 0: 병렬 worktree 확인과 계획 활성화

**Files:**
- Read: `docs/CURRENT_STATE.md` L1-L28
- Read: `docs/ROADMAP.md`의 마지막 비완료 행까지
- Read: `docs/exec-plans/active/0071-v2-question-response-passthrough.md` header와 완료 기록
- Modify: `docs/exec-plans/todo/0072-provider-attempt-observability.md` header only
- Generate: `docs/ROADMAP.md`

- [x] `git status --short --branch`로 사용자 변경과 `graphify-out/` dirty 파일을 기록한다.
- [x] `B-005`가 별도 worktree/branch에서 진행 중인지 확인하고, 현재 worktree가 `codex/b006-provider-attempt-observability`인지 검증한다.
- [x] 현재 `nvidia_nim_*`, coordinator, V2 Web 파일의 줄 범위를 다시 측정한다. B-005와 겹치는 파일은 최종 통합 재검증 대상으로 기록한다.
- [x] 이 branch에서만 0071 header 상태를 `Todo`로 두고, 0072 계획 파일을 `docs/exec-plans/active/`로 이동해 header 상태를 `Picked Up`으로 바꾼다. 저장소 전체 Picked Up은 한 개로 유지한다.
- [x] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 scripts/render_roadmap.py`를 실행한다.
- [x] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 scripts/check_roadmap.py`가 성공하는지 확인한다.
- [x] 계획의 병렬 worktree 계약 정정과 활성화를 `docs: pick up provider attempt observability`로 커밋한다. `graphify-out/`은 stage하지 않는다.

### Task 1: 개인정보 없는 공통 provider attempt 계약

**Files:**
- Create: `apps/api/app/domain/provider_attempts.py`
- Create: `apps/api/app/provider_observability.py`
- Create: `apps/api/tests/test_provider_observability.py`

- [x] 아래 test matrix를 `test_provider_observability.py`에 작성한다.

```python
import asyncio
import json
import logging
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.provider_observability import (
    ProviderAttemptEvent,
    classify_provider_failure,
    emit_provider_attempt,
    provider_attempt_scope,
)


def test_attempt_event_hashes_correlation_and_emits_only_closed_fields(caplog):
    source = UUID("5194ce0e-4a06-4104-b7c0-9150d5b05f67")
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with provider_attempt_scope(source):
            emit_provider_attempt(
                operation="answer_core", attempt=1, max_attempts=3,
                outcome="failed", failure_kind="provider_http",
                upstream_status=503, elapsed_ms=3021, remaining_ms=36979,
                retry_scheduled=True,
            )
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "attempt": 1,
        "correlation": "7d8d49c21f606642",
        "elapsed_ms": 3021,
        "failure_kind": "provider_http",
        "max_attempts": 3,
        "operation": "answer_core",
        "outcome": "failed",
        "provider": "nvidia",
        "remaining_ms": 36979,
        "retry_scheduled": True,
        "upstream_status": 503,
    }
    assert str(source) not in caplog.text


def test_attempt_event_rejects_extra_and_inconsistent_success_fields():
    with pytest.raises(ValidationError):
        ProviderAttemptEvent.model_validate({
            "correlation": "a" * 16, "provider": "nvidia",
            "operation": "route", "attempt": 1, "max_attempts": 1,
            "outcome": "succeeded", "failure_kind": None,
            "upstream_status": None, "elapsed_ms": 1, "remaining_ms": 9,
            "retry_scheduled": False, "question": "금지된 원문",
        })


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), ("timeout", None)),
        (type("APIConnectionError", (RuntimeError,), {})(), ("connection", None)),
        (type("HttpFailure", (RuntimeError,), {"status_code": 503})(), ("provider_http", 503)),
        (ValueError(), ("invalid_response", None)),
        (asyncio.CancelledError(), ("cancelled", None)),
        (RuntimeError(), ("unknown", None)),
    ],
)
def test_failure_classifier_uses_type_and_status_only(error, expected):
    assert classify_provider_failure(error) == expected
```

- [x] 고정 UUID의 SHA-256 앞 16자리가 test fixture의 `7d8d49c21f606642`와 일치하는지 독립 계산으로 확인한다.
- [x] `ProviderAttemptEvent`가 `extra="forbid"`, 1-based attempt, `attempt <= max_attempts`, non-negative timing, 성공 시 `failure_kind/upstream_status=None`과 `retry_scheduled=False`를 검증하도록 한다.
- [x] `provider_attempt_scope(source=None)`는 이미 열린 scope가 있으면 그대로 재사용하고, 없으면 호출 단위 UUID를 생성해 hash만 ContextVar에 저장하도록 한다. token reset으로 동시 async task와 중첩 scope를 격리한다.
- [x] 분류 순서를 `cancelled → timeout → integer status → connection type → Pydantic ValidationError → invalid response → unknown`으로 고정한다. 예외 문자열은 읽지 않는다.
- [x] `emit_provider_attempt`은 `ProviderAttemptEvent` 검증 뒤 `json.dumps(event.model_dump(mode="json"), sort_keys=True)` 한 줄만 `law_rag.provider_attempt` INFO logger에 출력한다.
- [x] RED 확인: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m pytest -p no:cacheprovider apps/api/tests/test_provider_observability.py -q`가 import 실패로 끝나는지 확인한다.
- [x] 두 새 모듈을 최소 구현하고 같은 명령이 PASS인지 확인한다.
- [x] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m ruff check apps/api/app/domain/provider_attempts.py apps/api/app/provider_observability.py apps/api/tests/test_provider_observability.py`를 실행한다.
- [x] `git diff --check`와 scoped diff를 검토하고 `feat: add safe provider attempt event contract`로 커밋한다.

### Task 2: answer core/detail의 모든 제한 재시도 기록

**Files:**
- Modify: `apps/api/app/adapters/nvidia_nim_answerer.py` L70-L174
- Create: `apps/api/tests/test_nvidia_nim_attempt_observability.py`

- [x] `503 → timeout → success`, `503 × 3 terminal`, `402`, `429`, schema validation, cancellation을 가짜 client로 재현한다. 첫 시나리오의 핵심 assertion은 아래와 같다.

```python
@pytest.mark.asyncio
async def test_answer_core_logs_503_timeout_and_success_in_attempt_order(caplog):
    answerer = scripted_answerer([
        provider_http_error(503, "secret response"),
        TimeoutError("secret timeout detail"),
        core_response(summary="검증된 요약"),
    ])
    request = QuestionRequest(
        client_request_id=UUID("5194ce0e-4a06-4104-b7c0-9150d5b05f67"),
        question="로그에 남으면 안 되는 질문",
    )
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        result = await answerer.answer_core(request, [_hit()])
    events = [json.loads(record.message) for record in caplog.records]
    assert result.summary == "검증된 요약"
    assert [(event["attempt"], event["outcome"], event["failure_kind"]) for event in events] == [
        (1, "failed", "provider_http"),
        (2, "failed", "timeout"),
        (3, "succeeded", None),
    ]
    assert [event["retry_scheduled"] for event in events] == [True, True, False]
    assert {event["operation"] for event in events} == {"answer_core"}
    assert "secret response" not in caplog.text
    assert "secret timeout detail" not in caplog.text
    assert request.question not in caplog.text
```

- [x] terminal 503 test는 정확히 3개의 failed event와 마지막 `retry_scheduled=False`를 확인하고 `ProviderAttemptsExhausted(failure_kind="provider_http", upstream_status=503)`를 기대한다.
- [x] 402/429 parametrized test는 각각 event 1개, `provider_http`, 원래 status, `retry_scheduled=False`와 client call 1회를 확인한다.
- [x] invalid content와 Pydantic schema failure도 기존 횟수만큼 로그되지만 `ProviderAttemptsExhausted`로 바뀌지 않고 기존 validation exception 계열로 끝나는지 확인한다.
- [x] cancellation은 failed/cancelled event 하나를 남기고 `asyncio.CancelledError`를 그대로 다시 올리며 재시도하지 않는지 확인한다.
- [x] `answer()`는 `answer_detail`, `answer_core()`는 `answer_core`, clarification argument가 있으면 두 경로 모두 `clarification`, `answer_blocked_route()`는 `answer_detail`을 사용하도록 operation을 `_generate`에 명시적으로 전달한다.
- [x] `_generate`는 각 attempt 직전 `attempt_started`, 호출 전체 `deadline`을 단조 시계로 잡고, 결과/예외 직후 `elapsed_ms`, clamp된 `remaining_ms`, 실제 다음 시도 여부를 계산한 뒤 즉시 emit한다.
- [x] 기존 `_MIN_RETRY_SECONDS`, `_NON_RETRYABLE_STATUS_CODES`, `max_attempts`, 전체 deadline을 그대로 사용한다. 로그를 위해 retry 결정을 앞당기거나 새 sleep/backoff를 넣지 않는다.
- [x] availability kind의 마지막 실패만 sanitized `ProviderAttemptsExhausted`로 감싸고 exception chaining을 공개 로그에 유출하지 않도록 `from None`으로 올린다. validation/unknown은 원래 exception type을 유지한다.
- [x] RED/PASS: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m pytest -p no:cacheprovider apps/api/tests/test_nvidia_nim_attempt_observability.py apps/api/tests/test_nvidia_nim_answerer.py -q`.
- [x] Ruff와 `git diff --check` 후 `feat: log every NVIDIA answer attempt`로 커밋한다.

### Task 3: route, query embedding, clarification의 단일 관측 계약 적용

**Files:**
- Modify: `apps/api/app/adapters/nvidia_nim_route_classifier.py` L146-L285
- Modify: `apps/api/app/adapters/nvidia_nim_embedder.py` L14-L90
- Modify: `apps/api/app/adapters/nvidia_nim_clarification.py` L10-L58
- Create: `apps/api/tests/test_nvidia_provider_operation_observability.py`
- Modify: `apps/api/tests/test_routing_pipeline.py` L70-L147

- [x] 세 adapter별 성공 1건과 실패 1건을 가짜 client로 실행하고 operation과 event 개수를 검증한다.

```python
@pytest.mark.parametrize(
    ("invoke", "operation", "max_attempts"),
    [
        (invoke_route_success, "route", 2),
        (invoke_embedding_success, "query_embedding", 1),
        (invoke_clarification_success, "clarification", 1),
    ],
)
def test_nvidia_operation_success_emits_one_closed_event(caplog, invoke, operation, max_attempts):
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        asyncio.run(invoke())
    event = json.loads(caplog.records[-1].message)
    assert event["operation"] == operation
    assert event["outcome"] == "succeeded"
    assert event["attempt"] == 1
    assert event["max_attempts"] == max_attempts
    assert event["failure_kind"] is None
    assert event["retry_scheduled"] is False
```

- [x] route의 기존 `law_rag.route_provider` test를 공통 logger와 full event assertion으로 바꾼다. 두 번 실패하면 failed event 2개가 남고 마지막 availability failure가 typed exhaustion인지 확인한다.
- [x] route는 기존 최대 2회와 402/429 non-retry 동작을 유지한다. 호출 전체의 관측용 deadline만 계산하되 기존 provider 호출 timeout이나 retry 횟수를 줄이지 않는다.
- [x] embedder/clarification은 max_attempts=1로 성공 또는 실패 event 하나를 기록한다. provider HTTP/timeout/connection은 typed exhaustion으로 감싸도 상위 fallback이 유지되어야 하고, 응답 검증 실패는 원래 validation error를 유지한다.
- [x] 세 public adapter method 각각을 `provider_attempt_scope()`로 감싸되 이미 application scope가 있으면 그 correlation을 재사용한다. 직접 script/test에서 호출하면 호출별 임시 correlation 하나를 만든다.
- [x] embedder는 테스트 주입을 위해 `client_factory: Callable[[], Any] | None = None`만 추가하고 production 기본값과 `max_retries=0`을 유지한다. 별도 재시도 설정은 추가하지 않는다.
- [x] clarification도 같은 client seam을 추가하되 호출 횟수는 1을 유지한다.
- [x] RED/PASS: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m pytest -p no:cacheprovider apps/api/tests/test_nvidia_provider_operation_observability.py apps/api/tests/test_routing_pipeline.py apps/api/tests/test_nvidia_nim_embedder.py apps/api/tests/test_nvidia_nim_clarification.py -q`.
- [x] Ruff와 `git diff --check` 후 `feat: trace all NVIDIA provider operations`로 커밋한다.

### Task 4: V1/V2 request correlation을 모든 production NVIDIA 호출에 연결

**Files:**
- Modify: `apps/api/app/api/v1/questions.py` L22-L68
- Modify: `apps/api/app/api/v2/executions.py` L109-L164
- Modify: `apps/api/app/application/question_phase_coordinator.py` L48-L145
- Create: `apps/api/tests/test_provider_correlation_boundaries.py`

- [x] V1 `_handle_question`의 route→embedding→answer callback 전체가 `payload.client_request_id` scope 안에서 실행되는 test를 작성한다.
- [x] V2 prepare의 route→clarification→retrieval 호출이 같은 `payload.client_request_id` hash를 공유하는 test를 작성한다.
- [x] coordinator producer test는 execution private payload의 `request.client_request_id`를 우선하고, 없거나 invalid하면 `execution_id`를 fallback source로 쓰는지 확인한다.

```python
def _provider_correlation_source(execution: QuestionExecutionRecord) -> object:
    request_payload = execution.private_payload.get("request")
    if isinstance(request_payload, Mapping):
        client_request_id = request_payload.get("client_request_id")
        if isinstance(client_request_id, str) and client_request_id:
            return client_request_id
    return execution.execution_id
```

- [x] V1은 기존 timeout/cancellation/task registry try/finally 안에서 `_answer_question` 호출만 scope로 감싼다. request timing의 의미는 바꾸지 않는다.
- [x] V2 prepare는 `asyncio.timeout` 안의 `_prepare_clarification_turn`과 service `prepare`를 같은 scope로 감싼다. 인증 조회는 NVIDIA 경계가 아니므로 scope 밖이어도 된다.
- [x] coordinator는 claim 성공 뒤 producer 호출만 scope로 감싼다. repository read/write와 replay는 provider log를 만들지 않는다.
- [x] 두 concurrent async request에 서로 다른 UUID를 넣어 correlation이 섞이지 않는 회귀 test를 포함한다.
- [x] RED/PASS: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m pytest -p no:cacheprovider apps/api/tests/test_provider_correlation_boundaries.py apps/api/tests/test_question_phase_coordinator.py apps/api/tests/test_v2_question_executions.py -q`.
- [x] Ruff와 `git diff --check` 후 `feat: bind provider logs to request correlation`로 커밋한다.

### Task 5: provider 소진과 core grounding repair 분리

**Files:**
- Modify: `apps/api/app/application/question_phase_coordinator.py` L110-L131
- Modify: `apps/api/tests/test_question_phase_coordinator.py` L1-L102
- Modify only if B-005 tests require contract coverage: `apps/api/tests/test_v2_question_executions.py` relevant provider-failure section

- [x] core producer가 `ProviderAttemptsExhausted(provider_http, 503)`를 올리는 test를 추가하고 status `FAILED`, event `AnswerEvent.error("provider_unavailable")`, finalize/repair 미호출을 검증한다.
- [x] finalize producer가 같은 typed error를 올려도 `FAILED`와 같은 safe reason code로 끝나는지 검증한다.
- [x] 일반 `ValueError`를 올리는 core producer는 기존 `CORE_REPAIR_REQUIRED`와 `next_action=repair_core`를 유지하는 회귀 test를 추가한다.

```python
try:
    with provider_attempt_scope(_provider_correlation_source(claim.execution)):
        result = await producer(claim.execution)
except ProviderAttemptsExhausted:
    result = PhaseResult(
        target=ExecutionStatus.FAILED,
        events=(AnswerEvent.error("provider_unavailable"),),
    )
except Exception:
    result = _safe_phase_failure(phase)
```

- [x] generic catch-all을 작은 `_safe_phase_failure(phase)` helper로 추출해 기존 core repair/finalize failure 동작을 그대로 보존한다.
- [x] typed error의 `upstream_status`나 failure kind는 SSE payload에 넣지 않는다. 상세는 앞선 `law_rag.provider_attempt` 로그에서만 확인한다.
- [x] V2 end-to-end repository test에서 provider 소진 execution을 다시 core/finalize 호출해도 새 provider call이 생기지 않고 persisted terminal event가 replay되는지 확인한다.
- [x] RED/PASS: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m pytest -p no:cacheprovider apps/api/tests/test_question_phase_coordinator.py apps/api/tests/test_v2_question_executions.py -q`.
- [x] Ruff와 `git diff --check` 후 `fix: separate provider exhaustion from grounding repair`로 커밋한다.

### Task 6: Web에 안전한 provider 불가 안내 전달

**Files:**
- Modify: `apps/web/lib/v2-execution.ts` L24-L97
- Modify: `apps/web/lib/api-client.ts` L10-L139
- Modify: `apps/web/lib/v2-execution.test.ts` L1-L127
- Modify: `apps/web/lib/api-client-flow.test.ts` L133-L201

- [ ] SSE `error` event의 `reason_code`를 보존하는 typed transport error test를 먼저 추가한다.

```typescript
it("preserves the safe SSE provider_unavailable reason without reconnecting", async () => {
  let coreCalls = 0;
  const fetch = async (url: string) => {
    if (url.endsWith("/v2/question-executions")) {
      return Response.json({ execution_id: "exec-1", next_action: "generate_core" });
    }
    coreCalls += 1;
    return new Response('event: error\ndata: {"reason_code":"provider_unavailable"}\n\n');
  };
  await expect(runV2Execution(input, dependencies(fetch))).rejects.toMatchObject({
    name: "V2ExecutionPhaseError",
    reasonCode: "provider_unavailable",
  });
  expect(coreCalls).toBe(1);
});
```

- [ ] `V2ExecutionPhaseError`는 `reasonCode: string`만 공개하고 raw SSE object를 message에 stringify하지 않는다. `cancelled`는 기존 generic cancellation/abort 의미를 유지한다.
- [ ] `ApiErrorCode`에 `provider_unavailable`을 추가하고 `askQuestion`이 typed phase error를 아래 고정 문구로 바꾸는 test를 추가한다.

```typescript
await expect(askQuestion(history.request)).rejects.toMatchObject({
  name: "ApiError",
  status: 503,
  code: "provider_unavailable",
  message: "AI 제공자를 일시적으로 사용할 수 없습니다. 다시 시도해 주세요.",
});
```

- [ ] 이 변환에서 `askQuestion` 또는 `runV2Execution`이 새 POST prepare를 자동 호출하지 않는지 fetch call count로 확인한다.
- [ ] 알 수 없는 reason code는 B-005가 확정한 backend-display-message/error passthrough 계약을 유지한다. `provider_unavailable` 외 provider 세부 status, attempt, exception text는 사용자에게 표시하지 않는다.
- [ ] RED/PASS: `pnpm.cmd --filter @law-rag/web test -- v2-execution.test.ts api-client-flow.test.ts`.
- [ ] `pnpm.cmd lint:web`, `pnpm.cmd typecheck`, `pnpm.cmd test:web`를 실행한다.
- [ ] `git diff --check` 후 `fix: show safe provider unavailable message`로 커밋한다.

### Task 7: 운영 판독 문서와 전체 검증

**Files:**
- Modify: `docs/RELIABILITY.md` L35-L61
- Modify: `docs/references/operations-runbook.md` L78-L100
- Modify: `docs/exec-plans/active/0072-provider-attempt-observability.md`
- Generate: `docs/ROADMAP.md`

- [ ] `docs/RELIABILITY.md`에 모든 NVIDIA attempt의 성공/실패 로그, DB 미영속, provider exhaustion terminal semantics를 기록한다.
- [ ] runbook에 `law_rag.provider_attempt` 필터 후 correlation 기준 정렬 절차와 판독 예시를 추가한다: attempt 1 `provider_http/503/retry=true`, attempt 2 `timeout/retry=true`, attempt 3 `succeeded/retry=false`이면 “NVIDIA 503 뒤 두 번째 timeout, 세 번째 성공”이다.
- [ ] 로그에 원문·예외 메시지가 없으며 Vercel 보존기간이 지나면 복구할 수 없다는 제한을 적는다.
- [ ] focused API suite를 다시 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_python.ps1 -m pytest -p no:cacheprovider `
  apps/api/tests/test_provider_observability.py `
  apps/api/tests/test_nvidia_nim_attempt_observability.py `
  apps/api/tests/test_nvidia_provider_operation_observability.py `
  apps/api/tests/test_provider_correlation_boundaries.py `
  apps/api/tests/test_question_phase_coordinator.py `
  apps/api/tests/test_v2_question_executions.py -q
```

- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1` 전체 검증을 실행한다. runner 권한 오류가 나면 저장소의 Windows Python 검증 정책대로 같은 명령을 platform runtime 권한 상승으로 한 번만 재실행한다.
- [ ] 독립 whole-branch review를 실행하고 개인정보 유출, 누락된 NVIDIA operation, retry semantics 변화, provider/grounding 오분류를 우선 확인한다.
- [ ] review 지적을 test-first로 수정하고 focused suite와 `scripts/verify.ps1`을 최신 상태로 다시 통과시킨다.
- [ ] `rg -n "question|prompt|exception|traceback|authorization|api.key" apps/api/app/provider_observability.py apps/api/app/adapters/nvidia_nim_*.py` 결과를 사람이 검토해 금지 데이터가 logger payload로 전달되지 않는지 확인한다.
- [ ] `git diff --check`, `git status --short`, 전체 diff를 검토하고 `.env`, credential, 개인 사건자료, `graphify-out/`이 stage되지 않았는지 확인한다.
- [ ] 문서 변경을 `docs: document provider attempt log operations`로 커밋한다.
- [ ] 계획의 각 task에 결과 commit과 검증 증거를 기록하고 미완료 checkbox가 0개인지 확인한다.
- [ ] header를 `상태: Done`, `다음 행동: none`으로 바꾸고 `docs/exec-plans/completed/`로 이동한다.
- [ ] roadmap renderer와 checker를 실행하고 lifecycle 변경만 `docs: complete provider attempt observability plan`으로 커밋한다.

## Completion Evidence

완료 시 아래를 실제 결과로 채운다.

- Focused API tests: 미실행
- Focused Web tests: 미실행
- Full `scripts/verify.ps1`: 미실행
- Whole-branch review: 미실행
- Provider operation coverage: 미확인
- Privacy payload audit: 미실행
- Commits: 미생성

## Out of Scope Follow-ups

- Vercel 배포와 운영 execution smoke test는 별도 사용자 승인 뒤 수행한다.
- Vercel 로그 장기 보존, 외부 telemetry, DB attempt history는 이번 계획에 추가하지 않는다.
- 실제 관측치 없이 retry 횟수, timeout, backoff, provider/model을 조정하지 않는다.
