# F-005 V2 가독성 중심 리팩터링 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** F-005 v2 LlamaIndex 파이프라인의 동작과 테스트 의미를 보존하면서, v1·v2 경계와 LlamaIndex 실행 흐름이 파일 구조와 의존성으로 바로 드러나게 한다.

**Architecture:** `app.main`은 composition root와 FastAPI app factory만 소유한다. v1과 v2 HTTP router는 별도 패키지에 두고, v2 application service는 prepare → frozen evidence → core → finalize의 유스케이스를 명시적 생성자 의존성으로 조립한다. LlamaIndex 패키지는 source, transform, generation persistence, active-query를 도메인 책임별 모듈로 나눈다.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, LlamaIndex, pytest, Ruff.

**Spec:** `docs/design-docs/v2-llamaindex-framework-redesign.md`

## Global Constraints

- v1 request/response와 동작은 회귀 테스트로 보존하며 v1은 LlamaIndex 또는 generation table을 직접 사용하지 않는다.
- domain/application은 FastAPI, SQLAlchemy, LlamaIndex, NVIDIA SDK 타입을 import하지 않는다. SDK 객체는 adapter와 composition root에서만 조립·주입한다.
- v2 LlamaIndex 흐름은 `DatabaseReader → IngestionPipeline → generation PGVectorStore.add → active VectorStoreIndex → Router/QueryEngine → ResponseSynthesizer` 순서로 읽혀야 한다.
- 기존 테스트의 검증 의미와 public HTTP 계약은 변경하지 않는다. 필요한 test import 경로만 새 모듈 경계로 바꾼다.
- 새 모듈은 한 책임만 갖고 원칙적으로 500줄 미만으로 유지한다. guard clause와 전략/값 객체를 우선해 중첩 `if/else`를 줄인다.
- 모든 engine과 framework adapter는 composition root에서 한 번 만들고 생성자 또는 명시적 dependency 객체로 주입한다.

---

## Target File Structure

- `apps/api/app/bootstrap.py`: settings에서 repository, auth, LlamaIndex resources와 v2 service를 조립하는 유일한 composition root.
- `apps/api/app/api/v1/`: v1 질문, 인증·이력, corpus HTTP router와 v1 dependency를 보관한다.
- `apps/api/app/api/v2/`: v2 search와 question-execution HTTP router, JSON/SSE presenter를 보관한다.
- `apps/api/app/application/v2/`: frozen evidence, phase producer, grounding/final response를 조합하는 SDK-무관 유스케이스를 보관한다.
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/generation/`: catalog 모델·SQL persistence·publication policy를 보관한다.
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/ingestion/`: source reader, transform pipeline, generation writer를 순서대로 보관한다.
- `apps/law-rag-llamaindex/src/law_rag_llamaindex/query/`: active index cache, retriever, route/query adapter를 보관한다.

### Task 1: LlamaIndex generation·ingestion·query 패키지 분리

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/generation/{models,repository,publication}.py`
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/ingestion/{source_reader,transform,writer,service}.py`
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/query/{active_index,retriever}.py`
- Modify: `apps/law-rag-llamaindex/src/law_rag_llamaindex/{generations,ingest,active_index,retriever}.py`
- Modify: `apps/law-rag-llamaindex/tests/test_{generations,ingest,active_index,retriever}.py`

**Interfaces:**
- Consumes: existing public imports `PostgresGenerationRepository`, `RetrievalGeneration`, `run_ingestion`, `ActiveGenerationIndexProvider`, `search`, `search_index`.
- Produces: the same public imports as compatibility facades; internal services receive engines, stores, transforms and factories by constructor/call parameter rather than constructing them.

- [x] **Step 1: Capture focused behavior before moving code**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_generations.py tests/test_ingest.py tests/test_active_index.py tests/test_retriever.py -v`

Expected: all selected tests pass before the file move.

- [x] **Step 2: Extract cohesive units without semantic edits**

Move catalog records and SQL mapping into `generation`, split ingestion into read/transform/write orchestration, and move active cache/query adapter into `query`. Keep old module names as re-export facades:

```python
# generations.py
from law_rag_llamaindex.generation.models import RetrievalGeneration
from law_rag_llamaindex.generation.repository import PostgresGenerationRepository

__all__ = ["PostgresGenerationRepository", "RetrievalGeneration"]
```

- [x] **Step 3: Make LlamaIndex control flow explicit**

Use a small orchestration method whose body reads as the pipeline:

```python
async def build_generation(self) -> RetrievalGeneration:
    sources = self._source_reader.read_changed_sources()
    nodes = self._transformer.transform(sources)
    generation = await self._writer.write(nodes)
    return await self._publisher.publish_after_validation(generation)
```

- [x] **Step 4: Update only test import paths and run focused regression suite**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_generations.py tests/test_ingest.py tests/test_active_index.py tests/test_retriever.py -v`

Expected: the same assertions pass after the extraction.

- [x] **Step 5: Commit**

```powershell
git add apps/law-rag-llamaindex
git commit -m "refactor(llamaindex): expose ingestion and generation flow"
```

### Task 2: API composition root와 v2 application service 추출

**Files:**
- Create: `apps/api/app/bootstrap.py`
- Create: `apps/api/app/application/v2/{dependencies,evidence,phase_service,grounding}.py`
- Modify: `apps/api/app/main.py`, `apps/api/app/application/question_phase_coordinator.py`
- Modify: `apps/api/tests/test_{v2_question_executions,v2_grounding_events,question_phase_coordinator}.py`

**Interfaces:**
- Consumes: `QuestionExecutionRepository`, `LegalRepository`, `QuestionPhaseCoordinator`, existing LlamaIndex repository adapter and existing answerer port.
- Produces: `AppDependencies` and `V2QuestionExecutionService`, injected into v2 routes; existing v2 requests and SSE event payloads remain byte-for-byte equivalent where asserted.

- [x] **Step 1: Capture v2 contract behavior**

Run: `uv run --directory apps/api python -m pytest tests/test_v2_question_executions.py tests/test_v2_grounding_events.py tests/test_question_phase_coordinator.py -v`

Expected: selected API tests pass before extraction.

- [x] **Step 2: Move resource creation into a dependency object**

Create an immutable dependency container and make `main.py` ask it for routers and lifespan cleanup:

```python
@dataclass(frozen=True)
class AppDependencies:
    repository: LegalRepository
    question_executions: QuestionExecutionRepository
    v2_service: V2QuestionExecutionService | None
```

`bootstrap.py` alone normalizes DB URLs, creates engines and LlamaIndex adapters, and owns cleanup callbacks.

- [x] **Step 3: Extract phase use cases behind one service**

Move frozen evidence, core and finalize helpers from `main.py` into a service with explicit public verbs:

```python
class V2QuestionExecutionService:
    async def prepare(self, request: PrepareQuestion) -> PreparedExecution: ...
    async def stream_core(self, execution_id: UUID, capability: str) -> AsyncIterator[AnswerEvent]: ...
    async def stream_finalize(self, execution_id: UUID, capability: str) -> AsyncIterator[AnswerEvent]: ...
```

- [x] **Step 4: Keep decisions flat**

Represent retry/replay/busy outcomes with existing phase coordinator result types. Use early returns for terminal states and isolated grounding predicates instead of nested request-handler conditionals.

- [x] **Step 5: Update test imports only where a moved helper is imported, then verify**

Run: `uv run --directory apps/api python -m pytest tests/test_v2_question_executions.py tests/test_v2_grounding_events.py tests/test_question_phase_coordinator.py -v`

Expected: unchanged test assertions pass.

- [x] **Step 6: Commit**

```powershell
git add apps/api/app apps/api/tests
git commit -m "refactor(api): isolate v2 execution application service"
```

### Task 3: v1/v2 HTTP router 분리와 slim application entry point

**Files:**
- Create: `apps/api/app/api/{__init__,dependencies}.py`
- Create: `apps/api/app/api/v1/{__init__,questions,account,corpus}.py`
- Create: `apps/api/app/api/v2/{__init__,search,executions,sse}.py`
- Modify: `apps/api/app/main.py`, `apps/api/app/bootstrap.py`
- Modify: affected API tests only for moved monkeypatch/import paths.

**Interfaces:**
- Consumes: `AppDependencies`, v1 answer service and `V2QuestionExecutionService` from Task 2.
- Produces: `create_app(dependencies: AppDependencies) -> FastAPI`; `main.py` exports the production `app` and backward-compatible test seams only.

- [x] **Step 1: Capture route registration and v1/v2 behavior**

Run: `uv run --directory apps/api python -m pytest tests/test_api_route_registration.py tests/test_api.py tests/test_v2_search.py tests/test_v2_question_executions.py -v`

Expected: the registered endpoints and their existing behaviors pass before router extraction.

- [x] **Step 2: Route by version and responsibility**

Move only v1 routes to `api/v1` and only v2 routes to `api/v2`; compose them without behavior decisions in `main.py`:

```python
def create_app(dependencies: AppDependencies) -> FastAPI:
    app = FastAPI(..., lifespan=dependencies.lifespan)
    app.include_router(build_v1_router(dependencies))
    app.include_router(build_v2_router(dependencies))
    return app
```

- [x] **Step 3: Preserve transport rules in presenters**

Keep JSON, pre-stream HTTP errors, post-stream typed SSE errors and cancellation responses in `api/v2` presenter functions. Router methods delegate to application services and do not create SDK objects.

- [x] **Step 4: Enforce the file-size and dependency boundary**

Run: `Get-ChildItem apps/api/app -Recurse -Filter *.py | ForEach-Object { if ((Get-Content $_.FullName).Count -gt 500) { $_.FullName } }`

Expected: `main.py` and newly created/refactored F005 v2 modules are absent. Existing unrelated v1 infrastructure over 500 lines is recorded but not expanded.

- [x] **Step 5: Run focused route regressions**

Run: `uv run --directory apps/api python -m pytest tests/test_api_route_registration.py tests/test_api.py tests/test_v2_search.py tests/test_v2_question_executions.py -v`

Expected: all existing assertions pass.

- [x] **Step 6: Commit**

```powershell
git add apps/api/app apps/api/tests
git commit -m "refactor(api): separate v1 and v2 transport routers"
```

### Task 4: Whole-repository verification and documentation

**Files:**
- Modify: `docs/design-docs/v2-llamaindex-framework-redesign.md`
- Modify: `docs/exec-plans/completed/0063-f005-v2-readability-refactor.md`

**Interfaces:**
- Consumes: Tasks 1–3 public compatibility facades and the unchanged tests.
- Produces: evidence that all application contracts remain intact and an architecture decision record for the new module boundaries.

- [x] **Step 1: Run format, lint and test gates**

Run:

```powershell
uv run --directory apps/law-rag-llamaindex ruff check src tests
uv run --directory apps/law-rag-llamaindex python -m pytest -v
uv run --directory apps/api ruff check app tests
uv run --directory apps/api python -m pytest -v
npm --prefix apps/web test -- --run
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
```

Expected: every command exits 0; any existing environment-only failure is recorded with its exact command and cause.

Result (2026-08-28): all gates passed: LlamaIndex Ruff (`All checks passed!`) and pytest
(`70 passed, 2 skipped, 1 existing NVIDIA model-validity warning`); API Ruff (`All checks passed!`)
and pytest (`684 passed, 3 skipped, 1 Starlette/httpx deprecation warning`); web Vitest
(`18 files, 95 tests passed`), ESLint and `tsc --noEmit`. The sandbox-only API test attempt
ended in `PermissionError [WinError 5]` while pytest read its fresh base temp directory, and
the sandbox-only web test attempt ended in Vitest fork-worker `spawn EPERM`; elevated reruns
executed the assertions successfully. Full commands and results are in the SDD Task 4 report.

- [x] **Step 2: Update the decision record**

Add a dated entry stating that v1/v2 transport separation, composition-root injection and LlamaIndex stage packages are readability boundaries, not behavior changes.

- [x] **Step 3: Complete this plan and commit**

```powershell
git add docs
git commit -m "docs: record f005 readability refactor"
```

Result (2026-08-28): documentation-only Task 4 changes committed after the successful gates;
the SDD report records the commit SHA and clean task scope.
