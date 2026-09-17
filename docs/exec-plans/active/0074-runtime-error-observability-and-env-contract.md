> 작업 ID: `B-007`
> 상태: `Picked Up`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `Security`
> 선행 조건: [승인된 런타임 오류 관측과 환경 스코프 설계](../../design-docs/runtime-error-observability-and-environment-scopes.md)
> 다음 행동: 로그 모드와 Production raw 거부 계약의 실패 테스트부터 작성한다.
> 참고 범위:
> - `docs/design-docs/runtime-error-observability-and-environment-scopes.md` L1-L199 — 승인된 로그·환경·모델·보안 계약
> - `apps/api/app/settings.py` L1-L126 — 현재 runtime 설정과 Production validation
> - `apps/api/app/provider_observability.py` L1-L132 — 기존 B-006 provider 이벤트와 correlation scope

# Runtime Error Observability and Environment Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로컬에서는 raw stack/cause를 터미널에 한 번 출력하고 Production에서는 민감값을 제거한 단계별 stack/cause를 Vercel 로그에 남기며, hosted Nemotron 3.5 generation과 Nemotron 3 embedding 설정을 단일 주입 계약으로 유지한다.

**Architecture:** `Settings`가 로그 모드와 Production 안전 gate를 소유하고, 새 runtime 관측 모듈이 request correlation·pipeline stage·redaction·exception serialization·logger wiring을 한곳에 둔다. FastAPI 최상위 middleware가 처리되지 않은 예외를 기록하고, 기존 NVIDIA adapter의 시도 이벤트는 동일 correlation 아래 model·timeout·exception detail을 추가한다. 로컬 env 파일은 Git에 포함하지 않고 example과 운영 문서만 계약을 고정한다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings v2, Python logging/contextvars, pytest, Ruff, Pyright

**Spec:** `docs/design-docs/runtime-error-observability-and-environment-scopes.md`

## 전역 제약

- NVIDIA generation은 hosted `nvidia/nemotron-3.5-lightning-30b-a3b`, embedding은 hosted `nvidia/nemotron-3-embed-1b`만 사용한다.
- HTTP 응답에는 raw exception, stack trace, provider body 또는 SQL 정보를 추가하지 않는다.
- Production에서는 비밀값·질문·prompt·답변·법률 원문·SQL parameter를 로그에 남기지 않는다.
- `.env.local`과 `.env.prod`는 읽거나 수정할 수 있지만 절대로 stage하거나 commit하지 않는다.
- 새 로그 파일이나 외부 APM 의존성을 만들지 않는다.

---

### Task 1: 로그 모드 설정과 환경 계약

**결과:** `ERROR_LOG_MODE`이 닫힌 설정으로 검증되고 Production의 raw 모드가 시작 전에 거부되며 example 파일이 로컬·Preview·Production 계약을 설명한다.

**대상:**
- 수정: `apps/api/app/settings.py` L9-L113 — 로그 모드 필드와 Production validation 추가(약 +8/-0줄)
- 수정: `apps/api/tests/test_settings.py` L43-L75 — 기본값·허용값·Production raw 거부 회귀 테스트 추가(약 +30/-0줄)
- 수정: `apps/api/.env.example` L1-L60 — 개발 raw와 Vercel redacted 안내(약 +6/-1줄)
- 수정: `.env.example` L1-L40 — 루트 도구와 API 설정 소유권 명시(약 +5/-2줄)
- 로컬 수정: `apps/api/.env.local`, `apps/api/.env.prod`, `.env.local` — 폐기 변수 제거와 환경별 값 정리(Git 비추적, 값 출력 금지)
- 태스크 합계: 추적 파일 약 +49/-3줄

**실행 절차:**

- [ ] `Settings(_env_file=None)`의 redacted 기본값, development raw 허용, Production raw 거부를 검사하는 테스트를 먼저 추가한다.
- [ ] `scripts/run_python.ps1 -m pytest apps/api/tests/test_settings.py -q`를 실행해 새 테스트가 필드 부재 또는 validation 부재로 실패함을 확인한다.
- [ ] `ErrorLogMode`과 `error_log_mode` 필드, Production raw 거부 validation을 최소 구현한다.
- [ ] 두 example 파일을 정리하고 실제 gitignored env 파일은 값 노출 없이 generation·embedding·로그 모드 계약에 맞춘다. 루트 `.env.local`의 API 전용 generation/provider 변수는 제거한다.
- [ ] 같은 pytest 명령과 `git check-ignore -v apps/api/.env.local apps/api/.env.prod .env.local`을 실행해 테스트 통과와 ignore 상태를 확인한다.
- [ ] `git diff --check`와 `git status --short`로 `.env*`가 stage 대상에 나타나지 않는지 확인한다.
- [ ] 추적 파일만 `fix: enforce safe runtime log modes`로 커밋한다.

**완료 증거:** 설정 테스트가 통과하고 Production raw 구성은 ValidationError이며 세 로컬 env 파일은 Git ignored 상태다.

**의존성:** 없음.

### Task 2: raw/redacted exception serializer와 logger wiring

**결과:** 같은 예외·cause chain을 로컬 raw 또는 운영 redacted 정책으로 직렬화하고, Uvicorn 로컬 실행에서도 JSON 이벤트가 정확히 한 번 터미널 handler로 전달된다.

**대상:**
- 생성: `apps/api/app/runtime_observability.py` 새 파일 — stage/correlation context, redactor, exception serializer, logger 구성과 emit 함수(약 +190줄)
- 생성: `apps/api/tests/test_runtime_observability.py` 새 파일 — raw/redacted·nested cause·SQL·secret·logger 중복 회귀(약 +220줄)
- 수정: `apps/api/tests/conftest.py` L1-L18 — 테스트 기본 로그 모드 고정(약 +2/-0줄)
- 태스크 합계: 약 +412/-0줄

**인터페이스:**
- 생성: `PipelineStage` literal과 `runtime_observation_scope(correlation_source, initial_stage)` context manager
- 생성: `set_pipeline_stage(stage)`와 `current_pipeline_stage()`
- 생성: `serialize_exception(error, mode)` 및 `emit_runtime_exception(error, operation)`
- 생성: `configure_runtime_logging(mode)`

**실행 절차:**

- [ ] authorization·API key·DB URL·question/prompt/content·SQL parameter가 redacted되고 raw 모드에는 원문과 traceback/cause가 보존되는 실패 테스트를 작성한다.
- [ ] root/Uvicorn handler가 없는 로컬 조건에서 한 번 출력되고 기존 handler가 있으면 새 handler를 만들지 않는 실패 테스트를 작성한다.
- [ ] `scripts/run_python.ps1 -m pytest apps/api/tests/test_runtime_observability.py -q`를 실행해 모듈 부재 실패를 확인한다.
- [ ] 닫힌 stage/context 계약, 깊이 제한 cause traversal, 4 KiB detail 제한, 정규식·key 기반 redaction과 JSON logger를 최소 구현한다.
- [ ] 같은 pytest 명령을 실행해 통과를 확인하고, 비밀 fixture 문자열이 `caplog.text`에 없는지 결과를 검토한다.
- [ ] `scripts/run_python.ps1 -m ruff check apps/api/app/runtime_observability.py apps/api/tests/test_runtime_observability.py`와 대상 Pyright 검증을 실행한다.
- [ ] `git diff --check`와 대상 diff를 검토한다.
- [ ] `feat: add safe runtime exception diagnostics`로 커밋한다.

**완료 증거:** raw와 redacted fixture 테스트, nested cause, SQLAlchemy 형태 오류, handler 중복 방지 테스트가 모두 통과한다.

**의존성:** Task 1의 `Settings.error_log_mode`.

### Task 3: FastAPI 요청 경계와 pipeline stage 연결

**결과:** 처리되지 않은 Python·DB 예외가 request correlation과 마지막 stage를 가진 `runtime_exception` 이벤트로 한 번 기록되며 기존 안전 HTTP 응답 계약은 유지된다.

**대상:**
- 수정: `apps/api/app/main.py` L400-L434 — runtime logger 초기화와 최상위 요청 관측 middleware(약 +35/-0줄)
- 수정: `apps/api/app/api/v1/questions.py` L37-L55 — V1 request correlation과 routing stage 지정(약 +8/-2줄)
- 수정: `apps/api/app/api/v2/executions.py` L110-L145 — V2 request correlation과 phase stage 지정(약 +12/-2줄)
- 수정: `apps/api/app/application/question_phase_coordinator.py` L32-L165 — retrieval·generation·persistence 단계 전환과 caught exception 기록(약 +22/-2줄)
- 수정: `apps/api/app/application/v2/phase_service.py` L190-L520 — core/finalize generation·grounding·persistence 단계 전환과 caught exception 기록(약 +28/-2줄)
- 생성: `apps/api/tests/test_runtime_exception_boundary.py` 새 파일 — V1/V2 unhandled·caught SQL·AttributeError 회귀(약 +190줄)
- 태스크 합계: 약 +295/-8줄

**실행 절차:**

- [ ] V1 AttributeError와 V2 DBAPI-style 오류가 각각 올바른 stage·operation·correlation·stack/cause를 기록하되 HTTP payload에는 내부 내용이 없는 실패 테스트를 작성한다.
- [ ] 동일 예외가 하위 catch와 최상위 middleware를 모두 통과해도 이벤트가 하나뿐인 실패 테스트를 작성한다.
- [ ] `scripts/run_python.ps1 -m pytest apps/api/tests/test_runtime_exception_boundary.py -q`를 실행해 관측 경계 부재 실패를 확인한다.
- [ ] 앱 시작 시 logger를 설정하고 request scope를 생성하며 예외 기록 후 기존 FastAPI 처리로 다시 전달하는 middleware를 최소 구현한다.
- [ ] V1/V2 핵심 외부 경계 직전에 stage를 갱신하고, 안전 fallback으로 소비되는 예외는 해당 catch에서 한 번 기록한다.
- [ ] 새 테스트와 `apps/api/tests/test_question_phase_coordinator.py`, `apps/api/tests/test_v2_question_executions.py`를 실행해 통과를 확인한다.
- [ ] HTTP 응답 snapshot에 stack, SQL, secret fixture가 없는지 검사하고 대상 Ruff·Pyright를 실행한다.
- [ ] `git diff --check`와 대상 diff를 검토한다.
- [ ] `feat: trace runtime failures by pipeline stage`로 커밋한다.

**완료 증거:** AttributeError·SQL 오류의 정확한 stage와 stack/cause가 로그에 있고 중복 이벤트와 HTTP 정보 노출이 없다.

**의존성:** Task 2의 runtime 관측 인터페이스.

### Task 4: NVIDIA provider 이벤트 진단 필드 연결

**결과:** 모든 NVIDIA route·embedding·answer·clarification 시도가 model·timeout·exception type·모드별 detail·pipeline stage를 포함한다.

**대상:**
- 수정: `apps/api/app/provider_observability.py` L15-L132 — 이벤트 schema와 exception detail 직렬화 연결(약 +35/-5줄)
- 수정: `apps/api/app/adapters/nvidia_nim_route_classifier.py` L151-L241 — route model/timeout/error 전달(약 +18/-2줄)
- 수정: `apps/api/app/adapters/nvidia_nim_embedder.py` L24-L132 — embedding model/timeout/error 전달(약 +18/-2줄)
- 수정: `apps/api/app/adapters/nvidia_nim_answerer.py` L44-L246 — core/detail model/timeout/error 전달(약 +28/-4줄)
- 수정: `apps/api/app/adapters/nvidia_nim_clarification.py` L21-L119 — clarification model/timeout/error 전달(약 +18/-2줄)
- 수정: `apps/api/tests/test_provider_observability.py` L18-L207 — 닫힌 schema와 redaction 회귀(약 +65/-20줄)
- 수정: `apps/api/tests/test_nvidia_nim_attempt_observability.py` L1-L455 — 네 adapter 필드 회귀(약 +60/-12줄)
- 태스크 합계: 약 +242/-47줄

**실행 절차:**

- [ ] provider 이벤트의 model·timeout_ms·exception_type·error_detail·pipeline_stage 필드와 성공 이벤트의 null 계약을 테스트에 먼저 반영한다.
- [ ] 네 adapter의 HTTP·timeout·validation failure가 실제 생성 모델/임베딩 모델과 effective timeout을 전달하는 실패 테스트를 추가한다.
- [ ] `scripts/run_python.ps1 -m pytest apps/api/tests/test_provider_observability.py apps/api/tests/test_nvidia_nim_attempt_observability.py -q`로 schema/signature 실패를 확인한다.
- [ ] provider schema와 emitter signature를 확장하고 Task 2 serializer를 사용해 모드별 detail을 만든다.
- [ ] 각 adapter의 모든 success/failure emit call에 모델·timeout·원본 예외를 전달한다.
- [ ] 위 테스트와 NVIDIA adapter 전체 테스트를 실행해 통과를 확인한다.
- [ ] `rg -n "emit_provider_attempt\(" apps/api/app` 결과의 모든 호출이 새 필드를 전달하는지 확인하고 Ruff·Pyright를 실행한다.
- [ ] `git diff --check`와 대상 diff를 검토한다.
- [ ] `feat: enrich nvidia attempt diagnostics`로 커밋한다.

**완료 증거:** 모든 NVIDIA operation 이벤트가 모델·timeout·stage를 가지며 local raw와 Production redacted detail 테스트가 통과한다.

**의존성:** Task 2의 `serialize_exception`, Task 3의 stage context.

### Task 5: 문서·전체 회귀와 B-007 완료 전이

**결과:** 운영 검색법과 로컬 로그 위치가 현행화되고 저장소 전체 검증이 통과하며 B-007이 Done으로 전이된다.

**대상:**
- 수정: `docs/design-docs/provider-attempt-observability.md` L1-L174 — 새 설계가 detail 정책을 대체함을 명시(약 +8/-3줄)
- 수정: `docs/references/operations-runbook.md` provider 로그 검색 구간 — Vercel 검색 key와 로컬 터미널 진단 절차(약 +25/-8줄)
- 수정: `ARCHITECTURE.md` 결정 기록 구간 — 로그 모드·scope 결정 요약(약 +8/-0줄)
- 수정/이동: 이 계획 헤더와 결과 기록, `docs/ROADMAP.md` renderer 산출물(약 +20/-5줄)
- 태스크 합계: 약 +61/-16줄

**실행 절차:**

- [ ] 문서에 logger 이름이 아니라 `event_type`, `correlation`, `provider`, `pipeline_stage`로 검색하도록 적고 로컬 로그가 실행 터미널 stdout/stderr에만 남는다고 명시한다.
- [ ] `scripts/run_python.ps1 scripts/check_docs.py`와 `scripts/run_python.ps1 scripts/check_roadmap.py`를 실행한다.
- [ ] `scripts/verify.ps1`을 실행해 포맷·lint·타입·단위·통합·문서 검증 전체가 통과하는지 확인한다.
- [ ] 실패가 있으면 원인을 수정하고 관련 좁은 테스트부터 다시 통과시킨 뒤 전체 검증을 새로 실행한다.
- [ ] `git status --short`, `git diff --check`, commit diff를 검토해 비밀값과 `.env*`가 없는지 확인한다.
- [ ] 계획 결과·검증 명령을 기록하고 상태를 Done으로 바꿔 `completed/`로 이동한 뒤 roadmap renderer/checker를 실행한다.
- [ ] 문서·계획 변경을 `docs: document runtime diagnostics operations`로 커밋한다.

**완료 증거:** `scripts/verify.ps1` 최신 실행이 성공하고 B-007은 completed에 있으며 로드맵 checker가 통과한다.

**의존성:** Tasks 1-4 전체.

## 결과 기록

- 구현 결과: 진행 중
- 검증 결과: 진행 중
- 잔여 작업: O-001 Vercel 환경 scope rollout과 배포 smoke 검증
