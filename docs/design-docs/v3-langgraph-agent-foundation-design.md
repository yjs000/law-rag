# V3: LangGraph 에이전트 기본 골격 설계

상태: 제안됨 (2026-08-19)
결정일: 2026-08-19

> D-010(0057)이 v1의 현재 라우팅 계약을 단일 `QuestionRouter`와
> `routing_unavailable`로 확정했다. 아래 v1 tier1/tier2 표현은 제안 작성 당시의 역사적
> 비교이며 현재 runtime 계약이 아니다. 이 v3 제안은 구현 시 D-010 stage/failure contract에
> 맞춰야 한다.

## 배경

[V2 LlamaIndex 검색 파이프라인](v2-llamaindex-retrieval-pipeline-design.md)에서 세운
로드맵의 2단계("LangGraph 워크플로우 설계")는 실제로는 세 가지 다른 관심사를 하나로
묶은 이름이다 — 대화 컨텍스트 영속화, `clarification_required` interrupt 처리, realtime
웹검색 도구. 이 문서는 그중 **기본 골격**(그래프 정의 + Postgres 체크포인터로 대화
영속화 + v2 검색 도구 연결 + 답변 생성)만 다룬다. interrupt 처리와 웹검색 도구는 이
골격이 있어야 붙일 수 있는 후속 spec이다.

이 v3 에이전트는 v1(기존 운영 파이프라인)·v2(LlamaIndex 검색, 검색만 새로 짜고 생성은
v1 재사용)와 별개인 세 번째 독립 시스템이다. **v1의 라우팅·생성·인용 검증 알고리즘을
재사용하지 않고 LangChain/LangGraph 관용구로 새로 짠다** — v2가 검색만 교체하고 생성은
v1을 그대로 불러 쓴 것과 다른 지점이다. v1/v2는 이 작업으로 전혀 수정하지 않는다.

## 전체 로드맵에서의 위치

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | v2 LlamaIndex 검색 파이프라인 | 완료([0053](../exec-plans/completed/0053-v2-llamaindex-retrieval-pipeline.md)) |
| **2a** | **LangGraph 에이전트 기본 골격(그래프·State·영속화)** | **이 문서의 범위** |
| 2b | `clarification_required`를 LangGraph `interrupt()`로 처리 | 별도 spec, 2a 완료 후 |
| 2c | realtime 웹검색 도구 | 별도 spec, 2a 완료 후 |
| 3 | 2a+2b+2c 통합 테스트 | 별도 spec |
| 4 | UI/UX 연결(web이 v3를 사용하도록 전환, 스트리밍 UI) | 별도 spec |
| 5 | RAG 성능 평가, BM25 등 검색기 도입 검토 | 별도 spec 필요 시 |

## v3 설계

### 목표

- LangGraph `StateGraph`로 라우팅→검색→생성→검증 흐름을 노드 단위로 구성한다.
- 대화 State를 Postgres 기반 LangGraph 체크포인터로 영속화해, 재로그인·재접속 후에도
  이전 대화(턴·근거·라우팅 결과 전부)를 이어갈 수 있게 한다.
- v2에서 이미 검증된 검색(`law_rag_llamaindex.retriever.search`)을 그대로 도구로
  연결한다 — 검색 로직은 다시 짜지 않는다.
- 인용 위치(조·항·호·목)와 시간 유효성 필터링은 v1/v2와 마찬가지로 기능 요구사항이다
  (검색을 그대로 재사용하므로 자동으로 상속됨).
- LangGraph의 실행 모델(스레드·run·노드 단위 이벤트 스트림)을 실제로 쓰는 API 계약을
  만든다 — v1/v2의 "요청 1번=응답 1번" 모양을 그대로 베끼지 않는다.

### 비범위

- `clarification_required`를 실제 `interrupt()`로 일시정지·재개하는 것(2b)
- realtime 웹검색 도구(2c)
- 새 라우팅·생성·검증 알고리즘이 v1/v2와 동등한 품질(정확도·안전성)을 갖는 것 —
  이번은 실험적 구현이며, 품질 동등성 검증은 후속 spec의 몫이다
- 토큰 단위(글자 단위) 스트리밍 — 이번은 노드 단위 이벤트 스트리밍까지만
- `apps/web` 연동(로드맵 4단계)
- 기존 `question_history`/`conversations`의 과거 데이터를 체크포인터로 이관하는 것 —
  v3는 새 대화부터 시작하는 별개 시스템이다. 두 테이블은 v1/v2용으로 그대로 남는다.
- v1/v2 코드 변경

### 아키텍처

```text
apps/law-rag-agent/  (신규 uv workspace 앱, 독립 pyproject.toml)
├─ state.py       LangGraph State 스키마(스레드 전체 턴 이력 + 현재 턴 작업 필드)
├─ nodes/
│  ├─ route.py     LLM 구조화 출력 1회 호출로 라우팅 판단(legal_search 등)
│  ├─ search.py    law_rag_llamaindex.retriever.search 호출(신규 로직 없음)
│  ├─ generate.py  LLM 구조화 출력으로 답변 초안·인용·체크리스트·action 생성
│  └─ validate.py  인용-주장 정합성 검증, 실패 시 검색 결과만 통과
├─ graph.py        StateGraph 조립 + 조건부 엣지(route≠legal_search→차단 응답)
└─ checkpointer.py Postgres 체크포인터 팩토리(Supabase 재사용)

apps/api/
└─ /v3/*   law-rag-agent를 워크스페이스 의존성으로 호출하는 새 라우트
```

새 워크스페이스는 `apps/api`, `apps/collector`, `apps/law-rag-llamaindex`,
`packages/law-rag-core`와 별개의 uv workspace 멤버다. `law-rag-llamaindex`를 의존성으로
받아 `search` 노드에서 그대로 호출한다. LangChain/LangGraph 계열 패키지는 이 새
워크스페이스에만 들어가고 `apps/api`·`apps/law-rag-llamaindex`에는 추가하지 않는다.

### 노드 설계

- **route**: LangChain `ChatNVIDIA` + `with_structured_output`으로 한 번의 LLM 호출에서
  `legal_search` / `clarification_required` / `realtime_required` /
  `external_document_required` 중 하나를 판단한다. 역사적 v1의 tier1(결정적 키워드)+tier2(LLM)
  2단계 비교는 D-010에서 이미 단일 `QuestionRouter`로 대체되었으며, 이 v3 제안도 같은
  단일-router·fail-closed 경계를 따라야 한다.
- **search**: `route=legal_search`일 때만 실행. `law_rag_llamaindex.retriever.search`를
  그대로 호출해 `SearchHit` 목록을 받는다. 이 노드는 새 로직을 담지 않는다 — 순수
  호출 래퍼다.
- **generate**: 검색 결과를 근거로 LLM 구조화 출력을 호출해 답변 초안, 인용 ID 목록,
  체크리스트, 완결성 신호(`action`: fully_answerable/partially_answerable/
  clarification_required/unanswerable)를 만든다. v1의 필드 계약에서 개념은 가져오되
  프롬프트·구현은 새로 짠다.
- **validate**: `generate`가 만든 주장마다 인용 ID가 실제로 존재하고 근거 원문과
  모순되지 않는지 확인한다. 실패하면 AI 답변 대신 검색 결과만 반환한다(v1과 같은
  안전 원칙 — 근거 없는 주장을 사용자에게 보이지 않음).

조건부 엣지: `route` 결과가 `legal_search`가 아니면 `search`/`generate`/`validate`를
건너뛰고 차단 응답을 만든다. `generate`의 `action=clarification_required`는 이번
spec에서는 그래프를 끝까지 실행해 일반 응답 State로 반환한다(대화는 계속 가능하지만
실제 일시정지는 없음) — 2b에서 `interrupt()`로 교체한다.

### State와 영속화

State는 다음을 담는다:

```text
thread_id: UUID
turns: list[Turn]          # 이 스레드의 전체 대화 이력
  - question: str
  - answer: str
  - citations: list[Citation]
  - route: RouteDecision
  - created_at: datetime
current: dict               # 현재 턴 작업 중 필드(검색 결과, 초안, 검증 결과 등)
```

LangGraph의 Postgres 체크포인터(같은 Supabase 인스턴스, `apps/api`가 쓰는 것과 같은
`DATABASE_URL`)가 이 State 전체를 `thread_id`마다 스냅샷으로 저장한다. **체크포인터가
유일한 영속화 소스**다 — 기존 `question_history`/`conversations` 테이블은 v3
대화에서는 쓰지 않는다(v1/v2용으로는 그대로 남는다).

로그인 사용자는 서버가 `(user_id, thread_id, created_at)`만 담는 얇은 인덱스 테이블에
추가로 기록한다 — 목록 UI를 만드는 게 아니라, 나중에 "내 스레드 목록"이 필요해질 때
쓸 최소한의 연결고리만 남겨두는 것이다. 익명 사용자는 클라이언트가 `thread_id`를
기억하는 동안만(예: localStorage) 대화가 이어진다.

### API (`apps/api`)

```text
POST /v3/threads
  response: { thread_id: UUID }

POST /v3/threads/{thread_id}/runs
  request:  { question: str, as_of_date: date }
  response: { answer, citations, checklist, action, route }   # 동기, 끝까지 기다림

POST /v3/threads/{thread_id}/runs/stream
  request:  { question: str, as_of_date: date }
  response: text/event-stream, 노드 완료마다 이벤트 1개
            (event: node_complete, data: {node: "route"|"search"|"generate"|"validate", ...})
            마지막 이벤트는 event: final

GET /v3/threads/{thread_id}/state
  response: { thread_id, turns: [...] }   # 체크포인트에서 그대로 복원
```

- `thread_id`는 클라이언트가 `POST /v3/threads`로 발급받아 이후 요청에 사용한다.
- 인증은 v1/v2와 동일하게 선택적이다(익명 허용). 로그인 사용자만 위 인덱스 테이블에
  기록된다.
- 준비 안 된 상태(v2 검색 인덱스가 준비 전 등)는 v2와 같은 `v2_search_not_ready` 503을
  `search` 노드 실패로 그대로 전파한다(새 코드를 안 만듦).

### 테스트

- `apps/law-rag-agent`:
  - 노드별 단위 테스트: `route`/`generate`/`validate`는 fake LLM 응답으로, 구조화 출력
    파싱과 조건 분기를 검증
  - `search` 노드는 `law_rag_llamaindex.retriever.search`를 그대로 호출하는지만
    확인(재검증하지 않음 — 이미 v2에서 테스트됨)
  - 그래프 통합 테스트(fake 노드): happy path, route 차단 경로, validate 실패 경로
  - 체크포인터 직렬화·복원 단위 테스트(fake Postgres 또는 in-memory 체크포인터로)
- `apps/api`:
  - `/v3/threads`, `/v3/threads/{id}/runs`, `/v3/threads/{id}/runs/stream`,
    `/v3/threads/{id}/state` 계약 테스트 — 익명/로그인 분기, `thread_id` 왕복,
    SSE 이벤트 순서(`route`→...→`final`)
- 실제 NIM 호출 품질 평가(D-10/E-10류)는 이번 spec 범위 밖이다.

## 결정 기록

- 2026-08-19: 로드맵 2단계를 2a(이 문서, 기본 골격)/2b(interrupt)/2c(웹검색)로
  분리한다. 2a가 먼저다.
- 2026-08-19: 라우팅·생성·인용 검증 알고리즘은 v1 코드를 재사용하지 않고 새로
  구현한다(v2가 생성 로직을 v1 그대로 재사용한 것과 다른 지점). 품질 동등성은 이번
  spec의 목표가 아니며 후속에서 다룬다.
- 2026-08-19: 검색은 새로 짜지 않는다 — `law_rag_llamaindex.retriever.search`를 그대로
  재사용한다.
- 2026-08-19: (역사 기록) 라우팅은 v1의 tier1+tier2 2단계 대신 LangChain `ChatNVIDIA` +
  구조화 출력 1회 호출로 단순화한다고 결정했다. 현재 v1 계약은 이후 D-010의 단일
  `QuestionRouter`와 `routing_unavailable` fail-closed 경계로 대체되었으며, v3 구현도 이를
  기준으로 삼는다.
- 2026-08-19: 대화 영속화는 LangGraph Postgres 체크포인터를 유일한 소스로 쓴다.
  `question_history`/`conversations`는 폐기하지 않되 v3 대화에는 쓰지 않는다(v1/v2
  전용으로 유지). 과거 데이터 이관은 하지 않는다.
- 2026-08-19: 로그인 사용자는 `(user_id, thread_id)` 인덱스만 추가로 기록한다(목록 UI는
  범위 밖). 익명은 클라이언트가 `thread_id`를 직접 관리한다.
- 2026-08-19: API 계약은 v1/v2의 "요청 1번=응답 1번" 모양이 아니라 LangGraph의 실행
  모델에 맞춘 스레드/run 리소스 구조로 만든다 — 2b의 interrupt 재개, 로드맵 4단계의
  스트리밍 UI를 계약을 갈아엎지 않고 확장할 수 있게 하기 위해서다.
- 2026-08-19: 노드 단위 SSE 스트리밍(`/runs/stream`)은 이번 spec에 포함한다. 토큰 단위
  스트리밍은 웹 UI 작업(로드맵 4단계)과 함께 붙이는 게 자연스러워 이번 범위에서
  뺀다.
- 2026-08-19: 새 워크스페이스 앱 `apps/law-rag-agent`로 만든다. `apps/api`가 `/v3/*`로
  노출한다.

## 미결정

- 체크포인터 구현체(예: `langgraph-checkpoint-postgres` 패키지의 정확한 스키마·버전
  호환성)는 실행 계획 단계에서 실제 설치·연동 확인 후 확정한다.
- `route`/`generate`가 쓸 정확한 프롬프트와 구조화 출력 스키마(pydantic 모델)는 계획
  단계에서 세부 설계한다.
- SSE 이벤트의 정확한 payload 필드(어디까지 노출할지, 예: 중간 검색 결과를 이벤트에
  포함할지)는 계획 단계에서 확정한다.
