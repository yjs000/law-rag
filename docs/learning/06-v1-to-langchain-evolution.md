# 6. v1에서 LangChain/LangGraph/LlamaIndex 버전으로: 로직이 어떻게 바뀌었나

## 한 문장 요약

v1은 라우팅·검색·생성·검증이 한 Python 함수 안에서 순서대로 실행되는 단일 파이프라인이다.
v2는 그중 검색 한 칸만 LlamaIndex로 새로 짜서 끼워 넣었고, v3(설계 단계)는 라우팅·생성·검증까지
LangGraph 노드로 다시 짜면서 대화 상태를 Postgres 체크포인터에 영속화한다. 세 버전 다
**병행 운영**되며, 새 버전이 옛 버전을 덮어쓰지 않는다.

전체 흐름을 색으로 구분한 다이어그램:
[v1→v2→v3 파이프라인 변화](diagrams/v1-v2-v3-pipeline-evolution.html)
(브라우저로 열어서 보는 정적 HTML — 저장소 파일이라 로컬에서 그대로 열린다)

## 왜 세 버전이 동시에 존재하는가

법령 답변은 "근거 없는 주장을 하지 않는다"는 안전 불변조건이 걸린 기능이라, 검증되지 않은
새 구현으로 기존 서비스를 바로 바꿔치기하지 않는다. 대신 각 단계마다 **좁은 범위만 새로
짜고, 나머지는 이미 검증된 것을 그대로 재사용**하는 방식으로 위험을 나눴다.

```text
v1 ── 기존 운영 파이프라인, 전부 검증됨
 │
 ├─ v2: 검색만 LlamaIndex로 교체, 생성·검증은 v1을 그대로 호출
 │      (LlamaIndexLegalRepository가 search/search_with_trace만 새로 구현하고
 │       나머지 8개 메서드는 기존 PostgresLegalRepository에 위임)
 │
 └─ v3: 라우팅·생성·검증까지 LangGraph 노드로 재구축(실험적),
        검색은 v2 것을 그대로 재사용, 대화는 체크포인터로 영속화
```

## v1: 한 함수 안의 순차 파이프라인

`apps/api/app/main.py`의 `_answer_question` 하나가 라우팅부터 인용 검증까지 전부 담당한다.

1. **라우팅**: tier1(Kiwi 형태소 기반 결정적 키워드 규칙, 비용 0) → 못 잡으면 tier2(LLM
   judgment 1회 호출)
2. **검색**: `PostgresLegalRepository.search_with_trace` — dense(pgvector exact cosine)가
   기본, dense 결과가 0건일 때만 PGroonga keyword fallback
3. **생성**: `NvidiaNimAnswerer`가 NVIDIA NIM을 구조화 출력으로 직접 호출
4. **검증**: `validate_draft`가 모든 주장의 인용 ID가 실제 근거에 있는지 확인, 실패하면
   AI 답변 대신 검색 결과만 반환

이 파이프라인은 `docs/learning/03-evidence-first-retrieval.md`에서 더 자세히 다룬다.

## v2: 검색 한 칸만 새로 짜기

**목표**는 LangChain 생태계로 확장하기 위한 첫걸음으로, "클린하고 이미 완성된" 임베딩·검색
코드를 LlamaIndex로 새로 만드는 것이었다. 나머지(라우팅·생성·검증)는 손대지 않았다 —
바꾸면 다시 검증해야 할 표면적이 넓어지기 때문이다.

- 새 uv workspace 앱 `apps/law-rag-llamaindex`가 provisions → LlamaIndex 노드 → NVIDIA
  NIM 임베딩 → `PGVectorStore` ingestion과 `retriever.search()`를 담당한다.
- `apps/api`의 `LlamaIndexLegalRepository` 어댑터가 기존 `LegalRepository` Protocol의
  `search`/`search_with_trace`만 새로 구현하고, `consume_quota`·`corpus_temporal_state`·
  `provision`·`last_sync` 등 나머지는 전부 기존 `PostgresLegalRepository`에 위임한다.
- `/v2/questions`는 v1의 `_answer_question`을 **그대로 호출**하되, 그 함수가 쓰는
  `repository`만 이 어댑터로 바꿔 끼운다 — 라우팅·생성·검증 코드는 한 줄도 새로 안 짰다.

자세한 설계 근거와 결정 기록: [V2 설계 문서](../design-docs/v2-llamaindex-retrieval-pipeline-design.md).
실행 결과와 실측 검증(실제 3,066개 조문 ingestion, `/v2/search`·`/v2/questions` smoke test):
[0053 실행 계획](../exec-plans/completed/0053-v2-llamaindex-retrieval-pipeline.md).

## v3: 노드 단위로 다시 짜고 대화를 영속화하기 (설계 단계, 아직 미구현)

v2가 "검색만 교체"였다면 v3는 "생성 파이프라인 자체를 LangGraph 관용구로 다시 짜는" 실험이다.

- **라우팅**: v1의 tier1+tier2 2단계 대신, LangChain `ChatNVIDIA` + 구조화 출력 1회 호출로
  단순화(비용 최적화는 이번 실험의 목표가 아님)
- **검색**: 새로 안 짬 — v2의 `law_rag_llamaindex.retriever.search`를 그대로 노드로 감싸
  호출
- **생성·검증**: 완전히 새 구현. v1과 개념(구조화 출력, 인용 ID, 완결성 신호)은 비슷하지만
  프롬프트와 코드는 처음부터 다시 짠다
- **대화 영속화**: LangGraph의 Postgres 체크포인터가 스레드(`thread_id`)마다 전체 State
  (턴 이력, 근거, 라우팅 결과)를 스냅샷으로 저장한다 — 클라이언트가 매번 이전 대화를
  다시 보내던 v1/v2 방식과 달리, 서버가 대화를 기억한다

v3는 **실험적 구현**으로 명시적으로 설계됐다 — v1/v2와 같은 수준의 답변 품질·안전성이
검증되기 전까지는 사용자에게 노출하지 않는다. 자세한 설계: [V3 설계 문서](../design-docs/v3-langgraph-agent-foundation-design.md).

## 세 버전 비교표

| 구분 | v1 | v2 | v3(설계 단계) |
|---|---|---|---|
| 위치 | `apps/api` | `apps/law-rag-llamaindex` + `apps/api` | `apps/law-rag-agent` + `apps/api` |
| 라우팅 | tier1+tier2 | v1과 동일 | LLM 1회(새로 구현) |
| 검색 | dense+keyword SQL | LlamaIndex(새로 구현) | v2 재사용 |
| 생성 | NIM 직접 호출 | v1과 동일 | 새로 구현 |
| 인용 검증 | `validate_draft` | v1과 동일 | 새로 구현 |
| 대화 컨텍스트 | 클라이언트가 매 요청 재전송 | v1과 동일 | Postgres 체크포인터(서버가 영속화) |
| API 모양 | 요청 1번=응답 1번 | 요청 1번=응답 1번 | 스레드/run 리소스 + 노드 단위 SSE |
| 상태 | 운영 중 | 운영 중(실사용 확인) | 설계 완료, 구현 전 |

## 읽을 때 지킬 구분

- 이 장은 **왜 이렇게 나눴는가**를 빠르게 이해하기 위한 요약이다. 정확한 필드·계약·결정
  근거는 각 버전의 설계 문서가 권위다.
- v2는 "운영 중" — 실제 DB에 ingestion을 돌리고 `/v2/search`·`/v2/questions`를
  실측 검증했다. v3는 "설계만 끝남" — 코드가 아직 없다.
- v1은 계속 운영되는 fallback이 아니라 **독립적으로 계속 운영되는 시스템**이다. v2/v3가
  실패해도 v1이 자동으로 대신 응답하는 구조가 아니다.

## 상세 자료를 찾는 곳

- v2 상세 설계와 결정 기록: [V2 설계 문서](../design-docs/v2-llamaindex-retrieval-pipeline-design.md)
- v2 실행 결과·staging 검증 증거: [0053 실행 계획](../exec-plans/completed/0053-v2-llamaindex-retrieval-pipeline.md)
- v3 상세 설계와 결정 기록: [V3 설계 문서](../design-docs/v3-langgraph-agent-foundation-design.md)
- v1 원본 파이프라인: [근거 우선 검색과 답변](03-evidence-first-retrieval.md)
