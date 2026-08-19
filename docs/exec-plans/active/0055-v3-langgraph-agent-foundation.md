# V3 LangGraph 에이전트 기본 골격 구현 계획

> **에이전트 작업자를 위한 안내:** 필수 서브스킬: 이 계획을 태스크 단위로 구현하려면 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans를 사용하세요. 각 단계는 체크박스(`- [ ]`) 문법으로 진행 상황을 추적합니다.

**목표:** 라우팅·검색·생성·검증을 LangGraph 노드로 구성한 새 에이전트(`apps/law-rag-agent`)를 만들고, Postgres 체크포인터로 대화 State를 영속화한 뒤, `apps/api`에 스레드/run 리소스 구조의 `/v3/*` API로 노출한다.

**아키텍처:** 새 uv workspace 앱이 `route`(LLM 구조화 출력 1회) → `search`(v2 retriever 재사용) → `generate`(LLM 구조화 출력) → `validate`(인용 정합성 검사) 노드로 구성된 `StateGraph`를 소유한다. `route`가 `legal_search`가 아니면 조건부 엣지로 차단 응답 노드로 분기한다. Postgres `AsyncPostgresSaver` 체크포인터가 `thread_id`마다 전체 State(턴 이력·근거·라우팅 결과)를 스냅샷 저장하며 유일한 영속화 소스다. `apps/api`는 `POST /v3/threads`, `POST /v3/threads/{id}/runs`(동기), `POST /v3/threads/{id}/runs/stream`(노드 단위 SSE), `GET /v3/threads/{id}/state`를 노출한다.

**기술 스택:** Python 3.14, uv workspaces, LangGraph(`langgraph`, `langgraph-checkpoint-postgres`, `psycopg[binary,pool]`), `langchain-nvidia-ai-endpoints`(`ChatNVIDIA`), FastAPI(SSE via `StreamingResponse`), pytest/pytest-asyncio.

## 전역 제약 조건

- Python: 새 패키지는 `>=3.14,<3.15`(`apps/api`, `apps/law-rag-llamaindex`와 동일).
- 테스트 실행: 항상 `python -m pytest`를 쓸 것(예: `uv run --directory apps/law-rag-agent python -m pytest`), 순수 `pytest` 금지 — 이 저장소에서 작업 디렉터리가 `sys.path`에 안 들어가 `ModuleNotFoundError`가 거짓으로 뜬다([0053](0053-v2-llamaindex-retrieval-pipeline.md)에서 검증됨).
- 의존성 동기화: 항상 저장소 루트에서 `uv sync --all-packages`, `uv sync --directory <단일 멤버>` 금지(공유 venv workspace, 단일 멤버 동기화가 다른 멤버 의존성을 정리해버림).
- `apps/api`/`apps/law-rag-llamaindex`에 langchain/langgraph 계열 의존성을 추가하지 않는다 — 전부 `apps/law-rag-agent`에만 둔다.
- 검색은 새로 짜지 않는다 — `law_rag_llamaindex.retriever.search(vector_store, embedder, query, as_of_date, limit)`를 그대로 호출한다(시그니처: `apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py`).
- 라우팅·생성·검증은 v1 코드를 재사용하지 않고 새로 구현한다. 이번 spec은 실험적 구현이며 v1/v2와 품질 동등성을 요구하지 않는다.
- 대화 영속화는 Postgres 체크포인터가 유일한 소스다. `question_history`/`conversations` 테이블은 v3 경로에서 쓰지 않는다(v1/v2 전용으로 유지, 과거 데이터 이관 없음).
- `thread_id`는 클라이언트가 `POST /v3/threads`로 발급받아 이후 요청에 사용한다. 인증은 v1/v2와 동일하게 선택적(익명 허용)이다. 로그인 사용자는 `(user_id, thread_id, created_at)` 인덱스에만 추가로 기록한다(목록 UI는 범위 밖).
- SSE 스트리밍은 노드 단위(`route`/`search`/`generate`/`validate`/`final`)까지만 — 토큰 단위 스트리밍은 범위 밖.
- `.env`/시크릿을 절대 커밋하지 않는다. 명시적 확인 없이 파괴적인 DB 명령을 실행하지 않는다.
- 설계 문서: [`docs/design-docs/v3-langgraph-agent-foundation-design.md`](../../design-docs/v3-langgraph-agent-foundation-design.md). 이 계획과 충돌하면 설계 문서의 "결정 기록"이 우선하며 이 계획을 그에 맞게 고친다.

---

## Task 1: `law-rag-agent` 워크스페이스 앱 스캐폴딩

**파일:**
- 생성: `apps/law-rag-agent/pyproject.toml`
- 생성: `apps/law-rag-agent/src/law_rag_agent/__init__.py`
- 생성: `apps/law-rag-agent/tests/test_package.py`
- 수정: `pyproject.toml:2`(루트 workspace members)

**인터페이스:**
- 산출물: import 가능한 `law_rag_agent` 패키지, `__version__ = "0.1.0"`, uv workspace 멤버로 설치 가능.

- [x] **1단계: 루트 `pyproject.toml`에 workspace 멤버 추가**

```toml
[tool.uv.workspace]
members = ["apps/api", "apps/collector", "apps/law-rag-agent", "apps/law-rag-llamaindex", "packages/law-rag-core"]
```

- [x] **2단계: 앱 디렉터리와 `pyproject.toml` 생성**

```toml
[project]
name = "law-rag-agent"
version = "0.1.0"
description = "LangGraph 기반 v3 에이전트 (law-rag v1/v2와 독립, 라우팅·생성·검증 신규 구현)"
requires-python = ">=3.14,<3.15"
dependencies = [
  "langgraph>=0.6,<1",
  "langgraph-checkpoint-postgres>=2.0,<3",
  "psycopg[binary,pool]>=3.2,<4",
  "langchain-nvidia-ai-endpoints>=0.3,<1",
  "law-rag-llamaindex",
  "pydantic-settings>=2.10,<3",
]

[tool.uv.sources]
law-rag-llamaindex = { workspace = true }

[dependency-groups]
dev = [
  "pytest>=8.4,<9",
  "pytest-asyncio>=1.1,<2",
  "ruff>=0.12,<1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [x] **3단계: 패키지 골격 생성**

`apps/law-rag-agent/src/law_rag_agent/__init__.py`:
```python
__version__ = "0.1.0"
```

- [x] **4단계: smoke 테스트 작성**

`apps/law-rag-agent/tests/test_package.py`:
```python
import law_rag_agent


def test_package_imports():
    assert law_rag_agent.__version__ == "0.1.0"
```

- [x] **5단계: 워크스페이스 동기화와 테스트 실행**

실행: `uv sync --all-packages` (`uv sync --directory apps/law-rag-agent` 단독 사용 금지 — 공유 venv workspace라 다른 멤버 의존성이 정리될 수 있음)
기대 결과: Python 3.14 아래에서 의존성 해석 성공(만약 langgraph/langchain-nvidia-ai-endpoints가 3.14를 아직 지원하지 않는다는 resolver 오류가 나면, 이후 모든 태스크가 이 설치에 의존하므로 진행 전에 오류를 그대로 기록하고 사용자에게 보고할 것).

실행: `uv run --directory apps/law-rag-agent python -m pytest -v`
기대 결과: `test_package_imports PASSED`

- [x] **6단계: 커밋**

```bash
git add pyproject.toml apps/law-rag-agent/
git commit -m "feat(law-rag-agent): scaffold new uv workspace app"
```

---

## Task 2: Config settings module

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/config.py`
- 테스트: `apps/law-rag-agent/tests/test_config.py`

**인터페이스:**
- 산출물: `Settings`(pydantic `BaseSettings`) — `database_url: str | None`, `nvidia_api_key: str | None`, `nvidia_base_url: str`, `nvidia_route_model: str`, `nvidia_generate_model: str`; `get_settings() -> Settings`(`lru_cache`).

route/generate에 서로 다른 모델을 쓸 수 있게 필드를 분리한다(기본값은 같은 모델이어도, 나중에 라우팅용 소형 모델로 바꿀 여지를 남김 — v1의 `nvidia_route_classifier_model` 분리와 같은 이유).

- [x] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_config.py
from law_rag_agent.config import Settings, get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.nvidia_api_key is None
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia_route_model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert settings.nvidia_generate_model == "nvidia/nemotron-3-ultra-550b-a55b"


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.nvidia_api_key == "test-key"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
```

- [x] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_config.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.config'`로 실패

- [x] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str | None = None
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_route_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_generate_model: str = "nvidia/nemotron-3-ultra-550b-a55b"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [x] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_config.py -v`
기대 결과: 3 passed

- [x] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/config.py apps/law-rag-agent/tests/test_config.py
git commit -m "feat(law-rag-agent): add settings module"
```

---

## Task 3: State 스키마와 순수 헬퍼

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/state.py`
- 테스트: `apps/law-rag-agent/tests/test_state.py`

**인터페이스:**
- 산출물: `Turn`(pydantic `BaseModel`: `question: str`, `answer: str`, `citations: list[dict]`, `route: str`, `created_at: datetime`), `AgentState`(`TypedDict`: `thread_id: str`, `turns: list[Turn]`, `question: str`, `as_of_date: str`, `route: str | None`, `search_hits: list[dict]`, `draft_answer: str | None`, `draft_citations: list[dict]`, `draft_action: str | None`, `final_answer: str | None`, `final_citations: list[dict]`); `append_turn(state: AgentState, turn: Turn) -> AgentState`(불변, 새 dict 반환).

LangGraph의 State는 각 노드가 반환하는 dict가 병합(update)되는 `TypedDict`다. `turns`는 그래프가 시작할 때 체크포인터에서 복원되고, `question`/`as_of_date`/`route`/`search_hits`/`draft_*`/`final_*`는 "현재 턴 작업 필드"로 매 요청마다 새로 채워진다.

- [x] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_state.py
from datetime import UTC, datetime

from law_rag_agent.state import AgentState, Turn, append_turn


def _turn(question: str) -> Turn:
    return Turn(
        question=question,
        answer="답변",
        citations=[{"id": "C1", "path": "제1조"}],
        route="legal_search",
        created_at=datetime.now(UTC),
    )


def test_turn_requires_all_fields():
    turn = _turn("질문1")
    assert turn.question == "질문1"
    assert turn.route == "legal_search"
    assert turn.citations[0]["id"] == "C1"


def test_append_turn_does_not_mutate_input_state():
    state: AgentState = {
        "thread_id": "t1",
        "turns": [_turn("질문1")],
        "question": "",
        "as_of_date": "2026-08-19",
        "route": None,
        "search_hits": [],
        "draft_answer": None,
        "draft_citations": [],
        "draft_action": None,
        "final_answer": None,
        "final_citations": [],
    }
    original_turns = state["turns"]
    new_state = append_turn(state, _turn("질문2"))
    assert len(state["turns"]) == 1
    assert state["turns"] is original_turns
    assert len(new_state["turns"]) == 2
    assert new_state["turns"][0].question == "질문1"
    assert new_state["turns"][1].question == "질문2"
```

- [x] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_state.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.state'`로 실패

- [x] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/state.py
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
```

- [x] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_state.py -v`
기대 결과: 2 passed

- [x] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/state.py apps/law-rag-agent/tests/test_state.py
git commit -m "feat(law-rag-agent): add State schema and pure turn helper"
```

---

## Task 4: 구조화 출력 스키마

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/schemas.py`
- 테스트: `apps/law-rag-agent/tests/test_schemas.py`

**인터페이스:**
- 산출물: `RouteDecision`(pydantic: `route: Literal["legal_search", "clarification_required", "realtime_required", "external_document_required"]`, `reason: str`), `GenerationResult`(pydantic: `answer: str`, `citation_ids: list[str]`, `action: Literal["fully_answerable", "partially_answerable", "clarification_required", "unanswerable"]`).

이 두 모델은 `ChatNVIDIA(...).with_structured_output(RouteDecision)`/`.with_structured_output(GenerationResult)`에 그대로 전달되어 LLM 응답을 구조화한다.

- [x] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_schemas.py
import pytest
from pydantic import ValidationError

from law_rag_agent.schemas import GenerationResult, RouteDecision


def test_route_decision_accepts_known_routes():
    decision = RouteDecision(route="legal_search", reason="에너지 법령 질문")
    assert decision.route == "legal_search"


def test_route_decision_rejects_unknown_route():
    with pytest.raises(ValidationError):
        RouteDecision(route="not_a_real_route", reason="x")


def test_generation_result_holds_citation_ids_and_action():
    result = GenerationResult(
        answer="태양광은 신에너지법 제2조에서 정의합니다.",
        citation_ids=["C1", "C2"],
        action="fully_answerable",
    )
    assert result.citation_ids == ["C1", "C2"]
    assert result.action == "fully_answerable"
```

- [x] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_schemas.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.schemas'`로 실패

- [x] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/schemas.py
from typing import Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    route: Literal[
        "legal_search",
        "clarification_required",
        "realtime_required",
        "external_document_required",
    ]
    reason: str = Field(description="이 라우팅으로 판단한 근거를 한두 문장으로 설명")


class GenerationResult(BaseModel):
    answer: str = Field(description="근거 조문에 기반한 답변 초안")
    citation_ids: list[str] = Field(description="답변에서 실제로 인용한 근거 ID 목록")
    action: Literal[
        "fully_answerable", "partially_answerable", "clarification_required", "unanswerable"
    ]
```

- [x] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_schemas.py -v`
기대 결과: 3 passed

- [x] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/schemas.py apps/law-rag-agent/tests/test_schemas.py
git commit -m "feat(law-rag-agent): add structured output schemas"
```

---

## Task 5: `route` 노드

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/nodes/__init__.py`
- 생성: `apps/law-rag-agent/src/law_rag_agent/nodes/route.py`
- 테스트: `apps/law-rag-agent/tests/test_route_node.py`

**인터페이스:**
- 소비: `AgentState`(Task 3), `RouteDecision`(Task 4), `Settings`(Task 2).
- 산출물: `build_route_node(llm) -> Callable[[AgentState], dict]`(LangGraph 노드 팩토리 — 이미 구조화 출력이 바인딩된 `llm`을 주입받아 테스트 시 fake로 교체 가능), `async def route_node(state: AgentState, llm) -> dict`(반환값은 `{"route": str}` — LangGraph가 State에 병합).

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_route_node.py
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
    fake_llm = FakeStructuredLLM(RouteDecision(route="clarification_required", reason="설비용량 누락"))
    state = {"question": "인허가 받을 수 있어?", "as_of_date": "2026-08-19", "turns": []}

    update = await route_node(state, fake_llm)

    assert update == {"route": "clarification_required"}
    assert "인허가 받을 수 있어?" in str(fake_llm.last_messages)
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_route_node.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.nodes'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/nodes/__init__.py
```

```python
# apps/law-rag-agent/src/law_rag_agent/nodes/route.py
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
```

- [ ] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_route_node.py -v`
기대 결과: 2 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/nodes/ apps/law-rag-agent/tests/test_route_node.py
git commit -m "feat(law-rag-agent): add route node"
```

---

## Task 6: `search` 노드

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/nodes/search.py`
- 테스트: `apps/law-rag-agent/tests/test_search_node.py`

**인터페이스:**
- 소비: `AgentState`(Task 3), `law_rag_llamaindex.retriever.search(vector_store, embedder, query, as_of_date, limit) -> list[SearchHit]`(이미 존재 — [0053](0053-v2-llamaindex-retrieval-pipeline.md) Task 8 산출물).
- 산출물: `build_search_node(vector_store, embedder, limit=10) -> Callable[[AgentState], dict]`, `async def search_node(state: AgentState, vector_store, embedder, limit: int) -> dict`(반환값 `{"search_hits": list[dict]}`, 각 dict는 `SearchHit.model_dump()`).

이 노드는 새 검색 로직을 담지 않는다 — `law_rag_llamaindex.retriever.search`를 그대로 호출하는 얇은 래퍼다.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_search_node.py
from datetime import date

import pytest
from law_rag_core.domain.schemas import SearchHit

from law_rag_agent.nodes.search import search_node


@pytest.mark.asyncio
async def test_search_node_calls_retriever_search_and_returns_hit_dicts(monkeypatch):
    hit = SearchHit(
        provision_id="11111111-1111-1111-1111-111111111111",
        document_id="22222222-2222-2222-2222-222222222222",
        document_title="에너지법",
        source_kind="law",
        version_label="MST 1",
        effective_from=date(2024, 1, 1),
        effective_to=None,
        path="제1조",
        heading=None,
        content="본문",
        source_url="https://example.test",
        score=0.9,
        law_type_code="A0002",
    )

    captured = {}

    async def fake_search(vector_store, embedder, query, as_of_date, limit):
        captured["args"] = (vector_store, embedder, query, as_of_date, limit)
        return [hit]

    monkeypatch.setattr("law_rag_agent.nodes.search.retriever_search", fake_search)

    vector_store = object()
    embedder = object()
    state = {"question": "태양광 정의", "as_of_date": "2026-08-19"}

    update = await search_node(state, vector_store, embedder, limit=5)

    assert update == {"search_hits": [hit.model_dump(mode="json")]}
    assert captured["args"][0] is vector_store
    assert captured["args"][1] is embedder
    assert captured["args"][2] == "태양광 정의"
    assert captured["args"][4] == 5
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_search_node.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.nodes.search'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/nodes/search.py
from datetime import date

from law_rag_llamaindex.retriever import search as retriever_search


async def search_node(state, vector_store, embedder, limit: int) -> dict:
    hits = await retriever_search(
        vector_store, embedder, state["question"], date.fromisoformat(state["as_of_date"]), limit
    )
    return {"search_hits": [hit.model_dump(mode="json") for hit in hits]}


def build_search_node(vector_store, embedder, limit: int = 10):
    async def _node(state):
        return await search_node(state, vector_store, embedder, limit)

    return _node
```

- [ ] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_search_node.py -v`
기대 결과: 1 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/nodes/search.py apps/law-rag-agent/tests/test_search_node.py
git commit -m "feat(law-rag-agent): add search node wrapping v2 retriever"
```

---

## Task 7: `generate` 노드

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/nodes/generate.py`
- 테스트: `apps/law-rag-agent/tests/test_generate_node.py`

**인터페이스:**
- 소비: `AgentState.search_hits`(Task 3/6), `GenerationResult`(Task 4).
- 산출물: `build_generate_node(llm) -> Callable[[AgentState], dict]`, `async def generate_node(state: AgentState, llm) -> dict`(반환값 `{"draft_answer": str, "draft_citations": list[dict], "draft_action": str}`).

`draft_citations`는 `search_hits` 중 `generate`가 실제로 인용한(`citation_ids`에 대응하는) 것만 골라 `{"id": ..., "path": ..., "document_title": ..., "source_url": ...}` 형태로 축약한다. citation id 매핑은 `search_hits`의 인덱스를 `C1`, `C2`, ... 순서로 붙인다.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_generate_node.py
import pytest

from law_rag_agent.nodes.generate import generate_node
from law_rag_agent.schemas import GenerationResult


class FakeStructuredLLM:
    def __init__(self, result: GenerationResult):
        self._result = result
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return self._result


@pytest.mark.asyncio
async def test_generate_node_maps_citation_ids_to_search_hits():
    fake_llm = FakeStructuredLLM(
        GenerationResult(
            answer="태양광은 신에너지법 제2조에서 정의합니다.",
            citation_ids=["C1"],
            action="fully_answerable",
        )
    )
    state = {
        "question": "태양광 정의가 뭐야",
        "search_hits": [
            {"path": "제2조", "document_title": "신에너지법", "source_url": "https://example.test/1", "content": "본문1"},
            {"path": "제3조", "document_title": "신에너지법", "source_url": "https://example.test/2", "content": "본문2"},
        ],
    }

    update = await generate_node(state, fake_llm)

    assert update["draft_answer"] == "태양광은 신에너지법 제2조에서 정의합니다."
    assert update["draft_action"] == "fully_answerable"
    assert update["draft_citations"] == [
        {"id": "C1", "path": "제2조", "document_title": "신에너지법", "source_url": "https://example.test/1"}
    ]


@pytest.mark.asyncio
async def test_generate_node_ignores_citation_ids_outside_search_hits_range():
    fake_llm = FakeStructuredLLM(
        GenerationResult(answer="답변", citation_ids=["C1", "C9"], action="fully_answerable")
    )
    state = {
        "question": "질문",
        "search_hits": [
            {"path": "제1조", "document_title": "법", "source_url": "https://example.test", "content": "본문"}
        ],
    }

    update = await generate_node(state, fake_llm)

    assert len(update["draft_citations"]) == 1
    assert update["draft_citations"][0]["id"] == "C1"
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_generate_node.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.nodes.generate'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/nodes/generate.py
_GENERATE_PROMPT = """다음 근거 조문만 사용해서 질문에 답하세요. 근거에 없는 내용은 답하지 마세요.

질문: {question}

근거:
{evidence}
"""


def _format_evidence(search_hits: list[dict]) -> str:
    lines = []
    for index, hit in enumerate(search_hits, start=1):
        lines.append(f"[C{index}] {hit['document_title']} {hit['path']}: {hit['content']}")
    return "\n".join(lines)


async def generate_node(state, llm) -> dict:
    search_hits = state["search_hits"]
    prompt = _GENERATE_PROMPT.format(
        question=state["question"], evidence=_format_evidence(search_hits)
    )
    result = await llm.ainvoke([{"role": "user", "content": prompt}])

    id_to_index = {f"C{i}": i - 1 for i in range(1, len(search_hits) + 1)}
    citations = []
    for citation_id in result.citation_ids:
        index = id_to_index.get(citation_id)
        if index is None:
            continue
        hit = search_hits[index]
        citations.append(
            {
                "id": citation_id,
                "path": hit["path"],
                "document_title": hit["document_title"],
                "source_url": hit["source_url"],
            }
        )

    return {
        "draft_answer": result.answer,
        "draft_citations": citations,
        "draft_action": result.action,
    }


def build_generate_node(llm):
    async def _node(state):
        return await generate_node(state, llm)

    return _node
```

- [ ] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_generate_node.py -v`
기대 결과: 2 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/nodes/generate.py apps/law-rag-agent/tests/test_generate_node.py
git commit -m "feat(law-rag-agent): add generate node"
```

---

## Task 8: `validate` 노드

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/nodes/validate.py`
- 테스트: `apps/law-rag-agent/tests/test_validate_node.py`

**인터페이스:**
- 소비: `AgentState.draft_answer`/`draft_citations`/`draft_action`(Task 7).
- 산출물: `def validate_node(state: AgentState) -> dict`(동기 — LLM 호출 없이 순수 검사, 반환값 `{"final_answer": str, "final_citations": list[dict]}`).

검증 규칙(새로 구현, v1보다 단순한 버전 — 실험 단계): `draft_action`이 `unanswerable`이면 근거 없이 빈 답변을 그대로 통과시킨다(주장이 없으므로 검증할 게 없음). 그 외에는 `draft_citations`가 하나도 없으면(인용 없는 주장) 초안을 버리고 검색 결과 목록만 담은 안전 응답으로 대체한다. 인용이 하나라도 있으면 초안을 그대로 통과시킨다.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_validate_node.py
from law_rag_agent.nodes.validate import validate_node


def test_validate_node_passes_through_answer_with_citations():
    state = {
        "draft_answer": "태양광은 신에너지법 제2조에서 정의합니다.",
        "draft_citations": [{"id": "C1", "path": "제2조"}],
        "draft_action": "fully_answerable",
        "search_hits": [{"path": "제2조", "document_title": "신에너지법"}],
    }

    update = validate_node(state)

    assert update["final_answer"] == "태양광은 신에너지법 제2조에서 정의합니다."
    assert update["final_citations"] == [{"id": "C1", "path": "제2조"}]


def test_validate_node_blocks_uncited_claims():
    state = {
        "draft_answer": "이건 무조건 허용됩니다.",
        "draft_citations": [],
        "draft_action": "fully_answerable",
        "search_hits": [{"path": "제2조", "document_title": "신에너지법"}],
    }

    update = validate_node(state)

    assert "근거" in update["final_answer"]
    assert update["final_citations"] == []


def test_validate_node_passes_through_unanswerable_with_no_citations():
    state = {
        "draft_answer": "이 질문은 현재 법령 정보만으로 답할 수 없습니다.",
        "draft_citations": [],
        "draft_action": "unanswerable",
        "search_hits": [],
    }

    update = validate_node(state)

    assert update["final_answer"] == "이 질문은 현재 법령 정보만으로 답할 수 없습니다."
    assert update["final_citations"] == []
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_validate_node.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.nodes.validate'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/nodes/validate.py
_UNGROUNDED_FALLBACK = "이 주장은 인용 근거 없이 만들어져 표시하지 않습니다. 아래 검색된 원문을 직접 확인하세요."


def validate_node(state) -> dict:
    if state["draft_action"] == "unanswerable":
        return {"final_answer": state["draft_answer"], "final_citations": []}

    if not state["draft_citations"]:
        return {"final_answer": _UNGROUNDED_FALLBACK, "final_citations": []}

    return {"final_answer": state["draft_answer"], "final_citations": state["draft_citations"]}
```

- [ ] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_validate_node.py -v`
기대 결과: 3 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/nodes/validate.py apps/law-rag-agent/tests/test_validate_node.py
git commit -m "feat(law-rag-agent): add validate node"
```

---

## Task 9: 체크포인터 팩토리

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/checkpointer.py`
- 테스트: `apps/law-rag-agent/tests/test_checkpointer.py`

**인터페이스:**
- 소비: `Settings`(Task 2).
- 산출물: `def build_checkpointer_context(settings: Settings)`(반환값은 `AsyncPostgresSaver.from_conn_string(...)`의 async context manager — 호출자가 `async with`로 열고 `.setup()`을 부른다).

`AsyncPostgresSaver`는 psycopg3 DSN(`postgresql://...`, asyncpg 접두어 아님)을 받는다 — `law_rag_llamaindex.ingest._async_database_url`과 반대 방향 변환이 필요할 수 있다. `apps/api`의 `DATABASE_URL`은 이미 psycopg가 이해하는 `postgresql://` 형태이므로, asyncpg용 `+asyncpg` 접두어가 붙어 있다면 제거한다.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_checkpointer.py
from law_rag_agent.checkpointer import _psycopg_database_url
from law_rag_agent.config import Settings


def test_psycopg_database_url_strips_asyncpg_driver():
    assert (
        _psycopg_database_url("postgresql+asyncpg://user:pass@host:5432/db")
        == "postgresql://user:pass@host:5432/db"
    )


def test_psycopg_database_url_leaves_plain_url_unchanged():
    url = "postgresql://user:pass@host:5432/db"
    assert _psycopg_database_url(url) == url


def test_build_checkpointer_context_requires_database_url():
    import pytest

    settings = Settings(_env_file=None, database_url=None)
    with pytest.raises(ValueError, match="database_url"):
        from law_rag_agent.checkpointer import build_checkpointer_context

        build_checkpointer_context(settings)
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_checkpointer.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.checkpointer'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/checkpointer.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from law_rag_agent.config import Settings


def _psycopg_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def build_checkpointer_context(settings: Settings):
    if not settings.database_url:
        raise ValueError("database_url is required to build the checkpointer")
    return AsyncPostgresSaver.from_conn_string(_psycopg_database_url(settings.database_url))
```

- [ ] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_checkpointer.py -v`
기대 결과: 3 passed
(`AsyncPostgresSaver.from_conn_string`이 문자열만으로 즉시 연결을 열지 않고 context manager 진입 시에만 연결한다는 전제 — 만약 import나 호출 시점에 실제 연결을 시도해 이 테스트가 실패하면, `psycopg` 미설치/연결 실패 에러 메시지를 그대로 보고서에 남기고 이 단계에서 멈출 것.)

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/checkpointer.py apps/law-rag-agent/tests/test_checkpointer.py
git commit -m "feat(law-rag-agent): add Postgres checkpointer factory"
```

---

## Task 10: 그래프 조립

**파일:**
- 생성: `apps/law-rag-agent/src/law_rag_agent/graph.py`
- 테스트: `apps/law-rag-agent/tests/test_graph.py`

**인터페이스:**
- 소비: `AgentState`(Task 3), `build_route_node`/`build_search_node`/`build_generate_node`(Task 5/6/7), `validate_node`(Task 8, 노드 함수 자체를 직접 등록 — 팩토리 불필요).
- 산출물: `def build_graph(route_node, search_node, generate_node, validate_node, checkpointer=None)`(각 인자는 이미 만들어진 노드 callable — 테스트에서 fake로 교체 가능. 반환값은 컴파일된 `CompiledStateGraph`).

조건부 엣지: `route` 노드 실행 후 `state["route"]`가 `"legal_search"`가 아니면 `blocked` 노드(차단 응답을 `final_answer`에 채우는 간단한 동기 함수, 이 파일 안에 정의)로 분기하고 그래프를 끝낸다. `"legal_search"`면 `search`→`generate`→`validate` 순서로 이어간다.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/law-rag-agent/tests/test_graph.py
import pytest

from law_rag_agent.graph import build_graph


async def fake_route_legal_search(state):
    return {"route": "legal_search"}


async def fake_route_blocked(state):
    return {"route": "clarification_required"}


async def fake_search(state):
    return {"search_hits": [{"path": "제1조", "document_title": "법", "source_url": "https://x", "content": "본문"}]}


async def fake_generate(state):
    return {"draft_answer": "답변", "draft_citations": [{"id": "C1"}], "draft_action": "fully_answerable"}


def fake_validate(state):
    return {"final_answer": state["draft_answer"], "final_citations": state["draft_citations"]}


@pytest.mark.asyncio
async def test_graph_runs_full_pipeline_when_route_is_legal_search():
    graph = build_graph(fake_route_legal_search, fake_search, fake_generate, fake_validate)
    result = await graph.ainvoke(
        {
            "thread_id": "t1",
            "turns": [],
            "question": "질문",
            "as_of_date": "2026-08-19",
            "route": None,
            "search_hits": [],
            "draft_answer": None,
            "draft_citations": [],
            "draft_action": None,
            "final_answer": None,
            "final_citations": [],
        }
    )
    assert result["final_answer"] == "답변"
    assert result["final_citations"] == [{"id": "C1"}]


@pytest.mark.asyncio
async def test_graph_skips_search_and_generate_when_route_is_blocked():
    graph = build_graph(fake_route_blocked, fake_search, fake_generate, fake_validate)
    result = await graph.ainvoke(
        {
            "thread_id": "t1",
            "turns": [],
            "question": "질문",
            "as_of_date": "2026-08-19",
            "route": None,
            "search_hits": [],
            "draft_answer": None,
            "draft_citations": [],
            "draft_action": None,
            "final_answer": None,
            "final_citations": [],
        }
    )
    assert result["search_hits"] == []
    assert "clarification_required" in result["final_answer"] or result["final_answer"]
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_graph.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_agent.graph'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/law-rag-agent/src/law_rag_agent/graph.py
from langgraph.graph import END, StateGraph

from law_rag_agent.state import AgentState

_BLOCKED_MESSAGES = {
    "clarification_required": "답하려면 정보가 더 필요합니다: {reason}",
    "realtime_required": "이 질문은 실시간 정보가 필요해 현재 법령 검색만으로는 답할 수 없습니다.",
    "external_document_required": "이 질문은 법령 외 문서가 필요해 현재 법령 검색만으로는 답할 수 없습니다.",
}


def _blocked_node(state):
    route = state["route"]
    message = _BLOCKED_MESSAGES.get(route, "이 질문은 법령 검색으로 답할 수 없습니다.")
    return {"final_answer": message.format(reason=route), "final_citations": []}


def _route_branch(state) -> str:
    return "search" if state["route"] == "legal_search" else "blocked"


def build_graph(route_node, search_node, generate_node, validate_node, checkpointer=None):
    graph = StateGraph(AgentState)
    graph.add_node("route", route_node)
    graph.add_node("search", search_node)
    graph.add_node("generate", generate_node)
    graph.add_node("validate", validate_node)
    graph.add_node("blocked", _blocked_node)

    graph.set_entry_point("route")
    graph.add_conditional_edges("route", _route_branch, {"search": "search", "blocked": "blocked"})
    graph.add_edge("search", "generate")
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", END)
    graph.add_edge("blocked", END)

    return graph.compile(checkpointer=checkpointer)
```

- [ ] **4단계: 테스트 통과 확인**

실행: `uv run --directory apps/law-rag-agent python -m pytest tests/test_graph.py -v`
기대 결과: 2 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-agent/src/law_rag_agent/graph.py apps/law-rag-agent/tests/test_graph.py
git commit -m "feat(law-rag-agent): assemble StateGraph with conditional routing"
```

---

## Task 11: `(user_id, thread_id)` 인덱스 마이그레이션

**파일:**
- 생성: `apps/api/migrations/versions/0014_v3_thread_index.py`

**인터페이스:**
- 산출물: `v3_agent_threads(thread_id uuid pk, user_id uuid null references user_profiles(id), created_at timestamptz)`.

- [ ] **1단계: 마이그레이션 작성**

```python
# apps/api/migrations/versions/0014_v3_thread_index.py
"""v3 LangGraph 에이전트의 (user_id, thread_id) 최소 인덱스.

Revision ID: 0014
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE v3_agent_threads (
          thread_id uuid PRIMARY KEY,
          user_id uuid REFERENCES user_profiles(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute("CREATE INDEX v3_agent_threads_user_id_idx ON v3_agent_threads (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS v3_agent_threads")
```

- [ ] **2단계: 마이그레이션 적용 확인(로컬/dev DB가 있으면)**

실행: `uv run --directory apps/api python -m alembic upgrade head`
기대 결과: 에러 없음, `alembic_version`이 `0014`로 전진. 로컬 `DATABASE_URL`이 없으면 이 단계는 건너뛰고 계획 진행 기록에 미검증으로 남길 것 — 마이그레이션은 CI/staging에서 병합 전에 검증한다.

- [ ] **3단계: 커밋**

```bash
git add apps/api/migrations/versions/0014_v3_thread_index.py
git commit -m "feat(api): add v3_agent_threads migration"
```

---

## Task 12: `POST /v3/threads`, `POST /v3/threads/{id}/runs`

**파일:**
- 생성: `apps/api/app/adapters/law_rag_agent_client.py`
- 수정: `apps/api/app/main.py`(모듈 전역 wiring + 새 라우트 2개)
- 수정: `apps/api/pyproject.toml`(law-rag-agent 의존성 추가)
- 테스트: `apps/api/tests/test_v3_threads.py`

**인터페이스:**
- 소비: `law_rag_agent.graph.build_graph`, `law_rag_agent.checkpointer.build_checkpointer_context`, `law_rag_agent.nodes.*`, `law_rag_agent.config.get_settings`(Task 1~10).
- 산출물: `apps/api/app/adapters/law_rag_agent_client.py`의 `async def run_thread(thread_id: str, question: str, as_of_date: date) -> dict`(그래프를 `thread_id` config로 동기 실행하고 최종 State를 반환); `POST /v3/threads`, `POST /v3/threads/{thread_id}/runs` 라우트.

- [ ] **1단계: 워크스페이스 의존성 추가**

`apps/api/pyproject.toml`의 `dependencies`에 `"law-rag-agent"` 추가, `[tool.uv.sources]`에:
```toml
law-rag-agent = { workspace = true }
```

실행: `uv sync --all-packages`
기대 결과: 충돌 없이 해석됨.

- [ ] **2단계: 실패하는 계약 테스트 작성**

```python
# apps/api/tests/test_v3_threads.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import app.main as main_module

    async def fake_run_thread(thread_id, question, as_of_date):
        return {
            "final_answer": "답변",
            "final_citations": [{"id": "C1", "path": "제1조"}],
            "route": "legal_search",
        }

    monkeypatch.setattr(main_module, "_v3_configured", lambda: True)
    monkeypatch.setattr(main_module, "run_v3_thread", fake_run_thread)
    return TestClient(main_module.app)


def test_create_thread_returns_uuid(client):
    response = client.post("/v3/threads")
    assert response.status_code == 200
    body = response.json()
    assert "thread_id" in body


def test_run_returns_final_answer_and_citations(client):
    thread_id = client.post("/v3/threads").json()["thread_id"]
    response = client.post(
        f"/v3/threads/{thread_id}/runs",
        json={"question": "태양광 정의가 뭐야", "as_of_date": "2026-08-19"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "답변"
    assert body["citations"] == [{"id": "C1", "path": "제1조"}]
    assert body["route"] == "legal_search"


def test_run_returns_503_when_not_configured(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "_v3_configured", lambda: False)
    client = TestClient(main_module.app)
    thread_id = "11111111-1111-1111-1111-111111111111"
    response = client.post(
        f"/v3/threads/{thread_id}/runs",
        json={"question": "질문", "as_of_date": "2026-08-19"},
    )
    assert response.status_code == 503
```

- [ ] **3단계: 테스트 실패 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_threads.py -v`
기대 결과: `/v3/threads` 라우트가 없어 404로 실패

- [ ] **4단계: `law_rag_agent_client.py` 작성**

```python
# apps/api/app/adapters/law_rag_agent_client.py
from datetime import date
from functools import lru_cache

from langchain_nvidia_ai_endpoints import ChatNVIDIA
from law_rag_agent.checkpointer import build_checkpointer_context
from law_rag_agent.config import get_settings as get_agent_settings
from law_rag_agent.graph import build_graph
from law_rag_agent.nodes.generate import build_generate_node
from law_rag_agent.nodes.route import build_route_node
from law_rag_agent.nodes.search import build_search_node
from law_rag_agent.nodes.validate import validate_node
from law_rag_agent.schemas import GenerationResult, RouteDecision
from law_rag_llamaindex.config import get_settings as get_llamaindex_settings
from law_rag_llamaindex.embedding import build_embedder
from law_rag_llamaindex.store import build_vector_store


@lru_cache
def _build_nodes():
    agent_settings = get_agent_settings()
    llamaindex_settings = get_llamaindex_settings()

    route_llm = ChatNVIDIA(
        model=agent_settings.nvidia_route_model,
        api_key=agent_settings.nvidia_api_key,
        base_url=agent_settings.nvidia_base_url,
    ).with_structured_output(RouteDecision)
    generate_llm = ChatNVIDIA(
        model=agent_settings.nvidia_generate_model,
        api_key=agent_settings.nvidia_api_key,
        base_url=agent_settings.nvidia_base_url,
    ).with_structured_output(GenerationResult)

    vector_store = build_vector_store(llamaindex_settings)
    embedder = build_embedder(llamaindex_settings)

    return (
        build_route_node(route_llm),
        build_search_node(vector_store, embedder),
        build_generate_node(generate_llm),
        validate_node,
    )


async def run_v3_thread(thread_id: str, question: str, as_of_date: date) -> dict:
    route_node, search_node, generate_node, validate = _build_nodes()
    settings = get_agent_settings()
    async with build_checkpointer_context(settings) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(route_node, search_node, generate_node, validate, checkpointer=checkpointer)
        result = await graph.ainvoke(
            {
                "thread_id": thread_id,
                "turns": [],
                "question": question,
                "as_of_date": as_of_date.isoformat(),
                "route": None,
                "search_hits": [],
                "draft_answer": None,
                "draft_citations": [],
                "draft_action": None,
                "final_answer": None,
                "final_citations": [],
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        return result
```

- [ ] **5단계: `apps/api/app/main.py`에 wiring과 라우트 추가**

기존 import 블록 근처(예: `from app.adapters.postgres_repository import PostgresLegalRepository` 다음 줄)에 추가:

```python
from uuid import uuid4

from app.adapters.law_rag_agent_client import run_v3_thread as _run_v3_thread

run_v3_thread = _run_v3_thread


def _v3_configured() -> bool:
    from law_rag_agent.config import get_settings as get_agent_settings

    agent_settings = get_agent_settings()
    return bool(agent_settings.database_url and agent_settings.nvidia_api_key)
```

`_v2_not_ready_http_error` 근처에 라우트를 추가한다(같은 503 안정 코드 패턴, 새 코드는 `v3_agent_not_ready`):

```python
def _v3_not_ready_http_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "v3_agent_not_ready", "message": "v3 에이전트를 아직 사용할 수 없습니다."},
    )


class V3RunRequest(BaseModel):
    question: str
    as_of_date: date


@app.post("/v3/threads")
async def create_v3_thread() -> dict:
    return {"thread_id": str(uuid4())}


@app.post("/v3/threads/{thread_id}/runs")
async def run_v3_thread_endpoint(thread_id: str, payload: V3RunRequest) -> dict:
    if not _v3_configured():
        raise _v3_not_ready_http_error()
    result = await run_v3_thread(thread_id, payload.question, payload.as_of_date)
    return {
        "thread_id": thread_id,
        "answer": result["final_answer"],
        "citations": result["final_citations"],
        "route": result["route"],
    }
```

`BaseModel`, `date`가 이미 `main.py` 상단에 import돼 있는지 `grep -n "^from pydantic import\|^from datetime import" apps/api/app/main.py`로 확인하고, 없으면 추가한다.

- [ ] **6단계: 테스트 통과 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_threads.py -v`
기대 결과: 3 passed

- [ ] **7단계: `apps/api` 전체 회귀 테스트**

실행: `uv run --directory apps/api python -m pytest -v`
기대 결과: 기존 테스트 전부 통과(새 import·전역 변수가 앱 시작을 깨지 않아야 함).

- [ ] **8단계: 커밋**

```bash
git add apps/api/pyproject.toml apps/api/app/adapters/law_rag_agent_client.py apps/api/app/main.py apps/api/tests/test_v3_threads.py
git commit -m "feat(api): add /v3/threads and /v3/threads/{id}/runs"
```

---

## Task 13: `POST /v3/threads/{id}/runs/stream` (SSE)

**파일:**
- 수정: `apps/api/app/adapters/law_rag_agent_client.py`(스트리밍 실행 함수 추가)
- 수정: `apps/api/app/main.py`(새 라우트)
- 테스트: `apps/api/tests/test_v3_threads_stream.py`

**인터페이스:**
- 소비: `build_graph`가 반환하는 `CompiledStateGraph`의 `astream(input, config, stream_mode="updates")` — 각 스텝마다 `{node_name: partial_state}` dict를 yield한다.
- 산출물: `async def stream_v3_thread(thread_id: str, question: str, as_of_date: date) -> AsyncIterator[str]`(SSE `data:` 라인 문자열을 yield); `POST /v3/threads/{thread_id}/runs/stream` 라우트, `StreamingResponse(..., media_type="text/event-stream")`.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/api/tests/test_v3_threads_stream.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import app.main as main_module

    async def fake_stream(thread_id, question, as_of_date):
        yield 'event: node_complete\ndata: {"node": "route"}\n\n'
        yield 'event: node_complete\ndata: {"node": "search"}\n\n'
        yield 'event: final\ndata: {"answer": "답변", "citations": []}\n\n'

    monkeypatch.setattr(main_module, "_v3_configured", lambda: True)
    monkeypatch.setattr(main_module, "stream_v3_thread", fake_stream)
    return TestClient(main_module.app)


def test_stream_returns_sse_events_ending_in_final(client):
    with client.stream(
        "POST",
        "/v3/threads/11111111-1111-1111-1111-111111111111/runs/stream",
        json={"question": "질문", "as_of_date": "2026-08-19"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: node_complete" in body
    assert "event: final" in body
    assert body.rstrip().endswith('data: {"answer": "답변", "citations": []}')
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_threads_stream.py -v`
기대 결과: 404로 실패(라우트 없음)

- [ ] **3단계: `law_rag_agent_client.py`에 스트리밍 함수 추가**

`run_v3_thread` 아래에 이어서:

```python
import json


async def stream_v3_thread(thread_id: str, question: str, as_of_date: date):
    route_node, search_node, generate_node, validate = _build_nodes()
    settings = get_agent_settings()
    async with build_checkpointer_context(settings) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(route_node, search_node, generate_node, validate, checkpointer=checkpointer)
        initial_state = {
            "thread_id": thread_id,
            "turns": [],
            "question": question,
            "as_of_date": as_of_date.isoformat(),
            "route": None,
            "search_hits": [],
            "draft_answer": None,
            "draft_citations": [],
            "draft_action": None,
            "final_answer": None,
            "final_citations": [],
        }
        config = {"configurable": {"thread_id": thread_id}}
        final_state: dict = {}
        async for step in graph.astream(initial_state, config, stream_mode="updates"):
            for node_name in step:
                yield f"event: node_complete\ndata: {json.dumps({'node': node_name})}\n\n"
            final_state.update(next(iter(step.values())))
        answer = final_state.get("final_answer", "")
        citations = final_state.get("final_citations", [])
        yield f"event: final\ndata: {json.dumps({'answer': answer, 'citations': citations})}\n\n"
```

이 `final_state.update(...)`는 각 스텝의 부분 업데이트를 단순 누적하는 근사치다 — 실제 State 전체(`turns` 등)는 체크포인터가 갖고 있으므로, 정확한 최종 상태가 필요하면 후속에서 `graph.aget_state(config)`로 교체할 수 있다. 이번 spec은 SSE 이벤트 스트리밍 자체가 목표이므로 이 근사치로 충분하다.

- [ ] **4단계: `main.py`에 스트리밍 라우트 추가**

```python
from fastapi.responses import StreamingResponse

from app.adapters.law_rag_agent_client import stream_v3_thread as _stream_v3_thread

stream_v3_thread = _stream_v3_thread


@app.post("/v3/threads/{thread_id}/runs/stream")
async def stream_v3_thread_endpoint(thread_id: str, payload: V3RunRequest) -> StreamingResponse:
    if not _v3_configured():
        raise _v3_not_ready_http_error()
    return StreamingResponse(
        stream_v3_thread(thread_id, payload.question, payload.as_of_date),
        media_type="text/event-stream",
    )
```

- [ ] **5단계: 테스트 통과 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_threads_stream.py -v`
기대 결과: 1 passed

- [ ] **6단계: 커밋**

```bash
git add apps/api/app/adapters/law_rag_agent_client.py apps/api/app/main.py apps/api/tests/test_v3_threads_stream.py
git commit -m "feat(api): add /v3/threads/{id}/runs/stream SSE endpoint"
```

---

## Task 14: `GET /v3/threads/{id}/state`

**파일:**
- 수정: `apps/api/app/adapters/law_rag_agent_client.py`(상태 조회 함수 추가)
- 수정: `apps/api/app/main.py`(새 라우트)
- 테스트: `apps/api/tests/test_v3_thread_state.py`

**인터페이스:**
- 소비: `CompiledStateGraph.aget_state(config) -> StateSnapshot`(LangGraph 표준 API, `.values`에 현재 State dict).
- 산출물: `async def get_v3_thread_state(thread_id: str) -> dict`; `GET /v3/threads/{thread_id}/state` 라우트.

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/api/tests/test_v3_thread_state.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import app.main as main_module

    async def fake_get_state(thread_id):
        return {"thread_id": thread_id, "turns": [{"question": "이전 질문", "answer": "이전 답변"}]}

    monkeypatch.setattr(main_module, "_v3_configured", lambda: True)
    monkeypatch.setattr(main_module, "get_v3_thread_state", fake_get_state)
    return TestClient(main_module.app)


def test_get_state_returns_turns(client):
    response = client.get("/v3/threads/11111111-1111-1111-1111-111111111111/state")
    assert response.status_code == 200
    body = response.json()
    assert body["turns"][0]["question"] == "이전 질문"


def test_get_state_returns_503_when_not_configured(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "_v3_configured", lambda: False)
    client = TestClient(main_module.app)
    response = client.get("/v3/threads/11111111-1111-1111-1111-111111111111/state")
    assert response.status_code == 503
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_thread_state.py -v`
기대 결과: 404로 실패

- [ ] **3단계: `law_rag_agent_client.py`에 상태 조회 함수 추가**

```python
async def get_v3_thread_state(thread_id: str) -> dict:
    route_node, search_node, generate_node, validate = _build_nodes()
    settings = get_agent_settings()
    async with build_checkpointer_context(settings) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(route_node, search_node, generate_node, validate, checkpointer=checkpointer)
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return {"thread_id": thread_id, "turns": snapshot.values.get("turns", [])}
```

- [ ] **4단계: `main.py`에 라우트 추가**

```python
from app.adapters.law_rag_agent_client import get_v3_thread_state as _get_v3_thread_state

get_v3_thread_state = _get_v3_thread_state


@app.get("/v3/threads/{thread_id}/state")
async def get_v3_thread_state_endpoint(thread_id: str) -> dict:
    if not _v3_configured():
        raise _v3_not_ready_http_error()
    return await get_v3_thread_state(thread_id)
```

- [ ] **5단계: 테스트 통과 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_thread_state.py -v`
기대 결과: 2 passed

- [ ] **6단계: `apps/api` 전체 회귀 테스트**

실행: `uv run --directory apps/api python -m pytest -v`
기대 결과: 전부 통과.

- [ ] **7단계: 커밋**

```bash
git add apps/api/app/adapters/law_rag_agent_client.py apps/api/app/main.py apps/api/tests/test_v3_thread_state.py
git commit -m "feat(api): add GET /v3/threads/{id}/state"
```

---

## Task 15: 로그인 사용자의 `(user_id, thread_id)` 기록

**파일:**
- 수정: `apps/api/app/main.py`(`/v3/threads` 핸들러에 선택적 인증 추가)
- 생성: `apps/api/app/adapters/v3_thread_index.py`(인덱스 테이블 write 헬퍼)
- 테스트: `apps/api/tests/test_v3_thread_index.py`

**인터페이스:**
- 소비: `apps/api/app/main.py`의 기존 `_optional_user(authorization: str | None) -> MockUser | None`(이미 존재, 재사용).
- 산출물: `async def record_v3_thread(engine, thread_id: str, user_id: str | None) -> None`(로그인 사용자만 기록, 익명은 아무것도 안 함).

- [ ] **1단계: 실패하는 테스트 작성**

```python
# apps/api/tests/test_v3_thread_index.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.v3_thread_index import record_v3_thread


@pytest.mark.asyncio
async def test_record_v3_thread_inserts_row_when_user_id_present():
    engine = MagicMock()
    connection = AsyncMock()
    engine.begin.return_value.__aenter__.return_value = connection

    await record_v3_thread(engine, "11111111-1111-1111-1111-111111111111", "user-1")

    connection.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_v3_thread_does_nothing_when_anonymous():
    engine = MagicMock()

    await record_v3_thread(engine, "11111111-1111-1111-1111-111111111111", None)

    engine.begin.assert_not_called()
```

- [ ] **2단계: 테스트 실패 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_thread_index.py -v`
기대 결과: `ModuleNotFoundError: No module named 'app.adapters.v3_thread_index'`로 실패

- [ ] **3단계: 구현 작성**

```python
# apps/api/app/adapters/v3_thread_index.py
from sqlalchemy import text


async def record_v3_thread(engine, thread_id: str, user_id: str | None) -> None:
    if user_id is None:
        return
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO v3_agent_threads (thread_id, user_id) VALUES (:thread_id, :user_id)"
            ),
            {"thread_id": thread_id, "user_id": user_id},
        )
```

- [ ] **4단계: `/v3/threads` 핸들러에서 호출하도록 `main.py` 수정**

```python
from app.adapters.v3_thread_index import record_v3_thread


@app.post("/v3/threads")
async def create_v3_thread(request: Request) -> dict:
    thread_id = str(uuid4())
    user = await _optional_user(request.headers.get("authorization"))
    if user is not None and repository is not None and hasattr(repository, "engine"):
        await record_v3_thread(repository.engine, thread_id, str(user.id))
    return {"thread_id": thread_id}
```

`create_v3_thread`가 이미 Task 12에서 `request: Request` 없이 정의됐다면 시그니처에 `request: Request`를 추가하는 수정이 필요하다 — Task 12에서 만든 버전을 이걸로 교체한다.

- [ ] **5단계: 테스트 통과 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v3_thread_index.py -v`
기대 결과: 2 passed

- [ ] **6단계: `apps/api` 전체 회귀 테스트**

실행: `uv run --directory apps/api python -m pytest -v`
기대 결과: 전부 통과.

- [ ] **7단계: 커밋**

```bash
git add apps/api/app/adapters/v3_thread_index.py apps/api/app/main.py apps/api/tests/test_v3_thread_index.py
git commit -m "feat(api): record (user_id, thread_id) for logged-in v3 threads"
```

---

## Task 16: 문서 마무리

**파일:**
- 수정: `docs/exec-plans/active/README.md`
- 수정: `docs/design-docs/index.md`
- 수정: `docs/design-docs/v3-langgraph-agent-foundation-design.md`(상태 줄)

- [ ] **1단계: 활성 계획 인덱스에 추가**

`docs/exec-plans/active/README.md`에:
```markdown
- [0055: V3 LangGraph 에이전트 기본 골격](0055-v3-langgraph-agent-foundation.md) — `law-rag-agent` 워크스페이스, `/v3/threads`·`/v3/threads/{id}/runs`·`/runs/stream`·`/state`
```

- [ ] **2단계: 설계 문서 상태 갱신**

`docs/design-docs/v3-langgraph-agent-foundation-design.md:3`에서 `상태: 제안됨`을 `상태: 구현 중`으로 바꾼다. `docs/design-docs/index.md`의 v3 행 상태 컬럼도 같이 `구현 중`으로 바꾼다.

- [ ] **3단계: 전체 검증**

```bash
uv run --directory apps/law-rag-agent python -m pytest
uv run --directory apps/api python -m pytest
```
기대 결과: 전부 통과.

- [ ] **4단계: 커밋**

```bash
git add docs/exec-plans/active/README.md docs/design-docs/index.md docs/design-docs/v3-langgraph-agent-foundation-design.md
git commit -m "docs: link 0055 plan and mark v3 design doc as in progress"
```

---

## Self-Review Notes(계획 작성자를 위한 것이며 태스크가 아님)

- **명세 커버리지:** 목표(그래프·노드·영속화·API) → Task 1–15. 비범위(interrupt, 웹검색, 품질 동등성, 토큰 스트리밍, web 연동, 과거 데이터 이관, v1/v2 코드 변경) → 이 계획 어디에도 해당 코드를 만들지 않음. State/영속화 → Task 3, 9, 10, 14. API 계약(스레드/run 구조 + SSE) → Task 12, 13, 14. thread_id 인증/인덱스 → Task 15. 결정 기록 항목(라우팅 단순화, 검색 재사용, 노드 단위 스트리밍, 워크스페이스 위치) → 각각 Task 5, 6, 13, 1에 대응.
- **알려진 위험:** Task 12~15는 실제 NVIDIA/Postgres 자격 증명 없이는 `_v3_configured()`가 항상 `False`를 반환해 503만 확인 가능하다 — 실 데이터 경로(체크포인터 직렬화, LLM 구조화 출력 실제 호출)는 이 계획 완료 후 [0053](0053-v2-llamaindex-retrieval-pipeline.md)의 staging 검증과 같은 방식으로 실제 자격 증명을 두고 별도로 확인해야 한다.
- **구현 시점까지 미해결로 남은 항목(설계 문서의 미결정 섹션에서 이어짐):** 체크포인터 구현체의 정확한 스키마 호환성, `route`/`generate` 프롬프트의 세부 튜닝, SSE payload 필드의 최종 확정은 이 계획의 태스크 범위 밖이며 Task 12~13에서 합리적 기본값으로 구현한 뒤 실제 사용 결과를 보고 후속 조정한다.
