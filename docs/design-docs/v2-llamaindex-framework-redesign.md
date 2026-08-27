# V2: LlamaIndex 프레임워크 파이프라인 개편 설계

상태: 승인, 구현 전
결정일: 2026-08-27

이 문서는 [V2 LlamaIndex 검색 파이프라인 Phase 1](v2-llamaindex-retrieval-pipeline-design.md)의
구현 결과를 다음 단계로 개편하는 권위 설계다. Phase 1 문서와 충돌하면 이 문서를 따른다. 아직 코드는
이 설계를 구현하지 않았으며, 구체적인 파일별 작업 순서와 명령은 사용자 검토 뒤 별도 실행계획에서
확정한다.

## 1. 목적

현재 v2는 LlamaIndex의 NVIDIA embedding, `PGVectorStore`, node 타입을 사용하지만 원문 조회·변경 감지·
청크 생성·직접 vector query·답변 생성과 라우팅의 상당 부분을 프로젝트 코드가 직접 수행한다. 이로 인해
상위 흐름에서 LlamaIndex 표준 객체가 드러나지 않고, 질문 embedding 중복과 단일 vector table의 부분
갱신 위험이 남아 있다.

이번 개편은 `DatabaseReader`, `IngestionPipeline`, `PGVectorStore`, `VectorStoreIndex`,
`RouterQueryEngine`, `QueryEngineTool`, QueryEngine, `ResponseSynthesizer`를 실제 책임에 맞게 연결하면서도,
법률 답변의 출처·기준일·grounding·fail-closed 계약은 프로젝트가 계속 통제한다.

## 2. 현재 목표와 다음 목표

### 2.1 이번 구현 목표

- v1은 LlamaIndex를 도입하지 않고 동결한다.
- 외부 원문 수집, v2 색인 구축, 요청 시 검색·답변을 서로 다른 실행 단위로 분리한다.
- v2 색인을 generation별 물리 table로 만들고 검증 뒤 active pointer를 전환한다.
- `IngestionPipeline`은 청크와 embedding 계산에 사용하되 vector 저장과 `UPSERTS`를 맡기지 않는다.
- 조회는 `VectorStoreIndex`와 QueryEngine을 사용하고 질문 embedding 중복 생성을 제거한다.
- LlamaIndex Router를 route 선택과 QueryEngine dispatch에 사용한다.
- LlamaIndex `ResponseSynthesizer`가 생성 stream을 제공하되 raw token은 생성 계층 내부에서만 소비한다.
- 기존 `/v2/questions`는 제거하고 `question_execution`을 공유하는 준비 JSON, 핵심 SSE, 최종 SSE의 세
  endpoint로 교체한다. 각 생성 phase는 별도 Vercel invocation을 사용한다.
- 원자적인 법률 주장 단위로 grounding을 통과한 summary, section, checklist만 SSE로 공개한다.
- route·검색·생성·grounding에서 발생한 복구 가능 오류를 execution 단위로 누적하고, 하나의 최종 답변
  coordinator가 검증된 부분 답변·제한 답변·결정적 fallback 중 하나를 선택한다.
- 로컬 bounded 계산에는 개별 timeout을 두지 않고 LLM·원격 embedding·DB 같은 외부 대기 경계와 phase
  deadline만 제한한다. 100명 동시접속 시에는 무제한 대기 대신 admission control을 적용한다.
- 인증·quota·이력·안전 오류·공식 출처·기준일 계약은 유지한다.
- 기존 v2 구현은 전환이 끝나면 병행 보존하지 않고 제거한다. rollback용 이전 색인 데이터는 유지한다.

### 2.2 명시적인 다음 목표

다음 항목은 확장 가능한 port와 교체 지점만 준비하고 이번 구현에는 포함하지 않는다.

- LlamaIndex Workflow 기반 human-in-the-loop
- `InputRequiredEvent`/`HumanResponseEvent`, workflow ID, resume API와 pending state
- clarification의 사용자 추가 입력 대기·재개
- realtime route의 실제 웹검색 tool
- external document route의 첨부문서 검색 tool
- FunctionAgent 또는 agentic tool loop
- 새 generation table의 HNSW 적용 여부와 별도 성능평가
- 청킹 방식 ablation과 검색 성능 비교
- v1의 LlamaIndex 전환
- 운영 중 무중단 색인 전환이나 분산 index builder

## 3. 전체 책임 경계

```text
국가법령정보 Open API
        ↓
apps/collector
외부 입력 검증 → 정규화 → canonical corpus DB 반영
        ↓ 성공한 corpus snapshot
외부 실행 순서 제어
        ↓
apps/law-rag-llamaindex index builder
DB 원문 조회 → 변경 계산 → chunk/embedding → 새 generation → 검증 → active 전환
        ↓
apps/api
prepare(route → active generation 검색 → 근거 고정)
    → core(핵심 생성 → grounding → SSE)
    → finalize(repair/상세 생성 → grounding → 최종 SSE)
```

### 3.1 Collector

Collector는 국가법령정보 Open API라는 외부 경계만 책임진다. JSON 우선·XML fallback, 도메인 정규화,
출처와 버전 계보, canonical DB 반영은 그대로 유지한다. 기존 v1 embedding 발행 코드는 v1 호환을 위해
동결할 수 있지만, 새 v2 LlamaIndex index builder를 collector service에 import하지 않는다.

Collector 성공 후 index builder를 실행하는 순서는 OS scheduler나 명시적인 실행 스크립트가 연결한다.
수집 성공과 embedding 성공은 서로 다른 run으로 기록하므로 NVIDIA 장애가 canonical corpus 수집 성공을
무효화하지 않는다.

### 3.2 LlamaIndex Index Builder

`apps/law-rag-llamaindex`는 API 내부 background task가 아니라 별도 batch executable이다. canonical DB를
읽어 v2 검색 projection을 만든다. chunker나 embedding model만 바뀐 재색인은 Open API 재수집 없이 이
프로세스만 다시 실행한다.

### 3.3 API

API는 문서 embedding을 읽어 `Document`를 다시 만드는 계층이 아니다. 요청 시 질문 embedding만 만들고,
pgvector가 저장된 문서 vector와 비교한다. `PGVectorStore`가 검색된 text와 metadata를 node로 복원하면
QueryEngine, `ResponseSynthesizer`, grounding 계층이 답변을 만든다.

## 4. 의존성 주입과 DB engine

모든 engine과 framework adapter는 각 executable의 composition root에서 한 번 생성하고 생성자에
주입한다. domain/application 객체가 connection URL로 engine을 만들거나 `PGVectorStore.from_params()`를
호출하지 않는다. 요청마다 engine, `PGVectorStore`, `VectorStoreIndex`를 만들지 않는다.

현재 사용 중인 LlamaIndex `PGVectorStore`는 sync engine과 async engine을 둘 다 주입하도록 요구하므로
다음 resource bundle을 사용한다.

```text
Collector:     AsyncEngine
Index Builder: SyncEngine + AsyncEngine(NullPool)
API:           AsyncEngine + SyncEngine(NullPool)
```

Indexer의 실제 DB 흐름은 sync이고 API의 실제 DB 흐름은 async다. 반대편 engine은 생성자 계약을 충족하기
위해 주입하되 `NullPool`로 연결을 보관하지 않는다. 객체 수가 아니라 전체 connection budget을 관리하며
API worker 수를 pool 계산에 곱한다.

resource owner만 engine을 dispose한다. `PGVectorStore`나 하위 repository가 주입받은 공유 engine의
수명을 임의로 끝내지 않는다. 이 소유권은 테스트에서 engine factory 호출 금지와 identity 확인으로
고정한다.

```python
# [직접 작성] composition root
engines = ApiEngineBundle(async_pool=..., sync_null_pool=...)

# [LlamaIndex] 반드시 engine 주입
store = PGVectorStore(engine=engines.sync, async_engine=engines.async, ...)
index = VectorStoreIndex.from_vector_store(store, embed_model=embedding)
```

## 5. Generation 기반 ingestion

### 5.1 원문 읽기와 검증 경계

조문(`provision`) 하나를 source 변경 단위로 사용한다. LlamaIndex `DatabaseReader.load_data()`가 canonical
DB query 결과를 곧바로 `Document`로 만든다. SQL alias와 reader 설정이 document ID, text, metadata를
결정한다.

Collector와 DB 제약을 통과한 내부 데이터를 단순히 Pydantic type으로 다시 검사하는 별도
`LegalSourceValidator`는 두지 않는다. 임의의 text 길이 제한도 추가하지 않는다. 대신 source coverage,
deterministic node ID, source lineage, embedding 차원과 finite vector를 generation 검증에서 확인한다.

```python
# [LlamaIndex]
documents = DatabaseReader(engine=engines.sync).load_data(
    query=CANONICAL_PROVISION_QUERY,
    document_id="source_id",
    metadata_cols=CANONICAL_METADATA,
)
```

### 5.2 Generation 저장 모델

- generation catalog는 generation ID, 물리 table 이름, source/transform fingerprint, 상태, count, 시간과
  실패 사유 코드를 보존한다.
- active pointer는 catalog의 generation 하나를 FK로 가리킨다.
- 물리 vector table은 generation마다 새로 만든다.
- table 이름은 서버가 생성한 안전한 식별자만 사용하고 사용자 입력을 DDL에 넣지 않는다.
- node ID는 source와 chunk key로 결정하며 generation ID를 포함하지 않는다.
- 성공 후 active와 immediate rollback generation을 보존하고, live `question_execution`이 참조하는
  generation은 완료·취소·만료까지 임시 pin한다. pin이 없는 더 오래된 물리 table은 정리하고 catalog
  이력은 남긴다.
- 새 table은 index builder만 생성하고 API는 `perform_setup=False`로 active table만 연다.

### 5.3 변경 계산과 재색인

source hash는 text뿐 아니라 검색·인용 결과에 영향을 주는 canonical metadata를 포함한다. transform
fingerprint는 chunker 규칙과 embedding provider/model/dimension/profile을 포함한다.

- source hash만 달라짐: 해당 source를 재청크·재임베딩한다.
- source 신규: 새로 청크·임베딩한다.
- source 삭제: 새 generation에 포함하지 않는다.
- source와 transform fingerprint가 모두 같음: active table에서 새 table로 DB-to-DB 복사한다.
- chunker fingerprint 변경: 복사 없이 전체 재청크·재임베딩한다.
- embedding fingerprint 변경: vector space가 달라지므로 복사 없이 전체 재임베딩한다.

`IngestionPipeline`에는 `vector_store`와 docstore strategy를 넣지 않는다. LlamaIndex
`DocstoreStrategy.UPSERTS`를 사용하지 않으며 pipeline은 계산만 담당한다. 저장은 모든 batch 계산이
성공한 뒤 신규 빈 generation table에 `PGVectorStore.add()`로 수행한다. 기존 active table의 row를
제자리에서 update하거나 delete하지 않는다.

```python
# [LlamaIndex Custom + LlamaIndex]
nodes = IngestionPipeline(
    transformations=[LawChunker(), nvidia_embedding],
).run(documents=changed_documents)

# [LlamaIndex] 신규 빈 generation에만 add
generation_store.add(nodes)
```

### 5.4 게시와 rollback

1. 모든 v2 endpoint를 기존 안정 코드 `v2_search_not_ready`의 HTTP 503으로 닫는다.
2. inactive generation과 물리 table을 만든다.
3. fingerprint가 같으면 unchanged vector를 DB-to-DB로 복사한다.
4. created/updated source만 pipeline으로 계산해 batch 단위로 `add()`한다.
5. deleted source가 새 generation에 없음을 포함해 generation 전체를 검증한다.
6. 검증 성공 시 짧은 transaction으로 active pointer를 전환한다.
7. API의 generation registry가 새 pointer를 보고 `VectorStoreIndex` cache를 교체한다.
8. active, immediate rollback과 live execution pin table을 남기고 pin 없는 더 오래된 물리 table을 정리한다.
9. v2 readiness를 연다.

실패한 generation은 active가 되지 않는다. 이전 active index와 pointer를 유지하고 run은 실패로 기록한다.
부분 성공을 허용하지 않으며 resume, dry-run, 부분 source 실행은 이번 범위에 없다. 재시도는 처음부터 새
generation을 만든다. rollback은 pointer를 immediate previous generation으로 되돌리는 명시적 운영 동작이다.

## 6. 요청 시 검색과 Router

### 6.1 Active index

prepare 시작 시 active generation을 한 번 확정해 execution에 저장하고 완료·취소·만료까지 같은 index와
frozen evidence를 사용한다. pointer 전환 뒤 prepare를 시작한 execution부터 새 generation을 사용한다.
`GenerationIndexRegistry`가 generation별 `PGVectorStore`와 `VectorStoreIndex`를 cache하고 live execution
pin을 추적한다. cleanup은 pin이 해제되기 전에 해당 물리 table을 삭제하지 않는다.

`VectorStoreIndex.from_vector_store(..., embed_model=nvidia_embedding)`가 질문 embedding과 vector 검색을
연결한다. API가 질문 embedding을 별도로 먼저 계산하지 않는다. retrieval top-k와 답변에 전달할 evidence
수는 별도 설정으로 둔다.

기준일 filter는 PostgreSQL 비교가 가능한 `effective_to_query_bound` sentinel metadata를 사용하고,
postprocessor에서 기준일·공식 출처를 다시 확인한다. 검색 metadata가 유효하지 않은 node는 답변 근거에서
제외한다. direct-path, keyword fallback, BM25와 RRF는 이번 v2 경로에 추가하지 않는다.

### 6.2 LlamaIndex Router

LlamaIndex `RouterQueryEngine`과 `QueryEngineTool`을 사용한다. 다만 표준 selector 결과만으로는 현재 route
계약을 표현할 수 없으므로 NVIDIA structured output을 사용하는 `LegalRouteSelector`와 얇은
`LegalRouterQueryEngine`을 둔다.

정상 route는 다음 네 개뿐이다.

- `legal_search`
- `clarification_required`
- `realtime_required`
- `external_document_required`

`routing_unavailable`은 모델이 선택할 수 없다. selector timeout, provider 오류, schema 실패 때만 프로젝트
코드가 만든다. route decision은 tool index, route, reason code, confidence, explanation, missing fields를
보존한다. 선택 결과는 전역 mutable state가 아니라 execution별 `RouteExecutionContext`로 선택된 engine에
전달한다.

```python
# [LlamaIndex + LlamaIndex Custom]
router = LegalRouterQueryEngine(
    selector=LegalRouteSelector(...),
    tools=[legal_tool, clarification_tool, realtime_tool, document_tool],
    context=request_context,
)
```

`legal_search`는 active `VectorStoreIndex`의 retriever, `LegalEvidencePostprocessor`, custom QueryEngine,
`GroundedStreamingResponseSynthesizer`를 연결한다. 나머지 세 route는 검색·embedding을 실행하지 않는
교체 가능한 QueryEngine이다. 이번 구현에서 clarification은 missing fields와 재질문 안내를, realtime과
external document는 필요한 capability를 알리는 안전 응답을 반환한다.

향후 human-in-the-loop, 웹검색, 첨부문서 검색을 도입할 때 Router와 상위 서비스는 유지하고 해당
`QueryEngineTool` 구현만 교체한다.

## 7. SSE와 문장별 grounding

### 7.1 세 단계 execution API 계약

기존 `/v2/questions` endpoint와 client 호출 코드는 제거하고 다음 세 endpoint로 교체한다. 브라우저에는
하나의 답변 흐름으로 보이지만 각 endpoint는 별도 Vercel invocation이며 같은 `question_execution`을
공유한다. v1 endpoint와 client 계약은 바꾸지 않는다.

```text
POST /v2/question-executions
POST /v2/question-executions/{execution_id}/core
POST /v2/question-executions/{execution_id}/finalize
```

최초 prepare는 아직 execution ID가 없으므로 client가 질문 제출 시 한 번 만든 `Idempotency-Key`를 함께
보낸다. 같은 소유자와 prepare key의 재요청은 기존 execution을 반환하고 새 route·검색을 시작하지 않는다.
execution 발급 뒤에는 `(execution_id, phase)`가 멱등 key가 된다.

준비 endpoint는 JSON으로 route·embedding·retrieval과 frozen citation registry를 확정한다. core와 finalize
endpoint만 `text/event-stream`을 반환한다. client는 답변 텍스트나 citation을 해석해 다음 단계를 판단하지
않고 서버의 닫힌 `next_action` 값에 따라 다음 요청만 실행한다.

```text
prepare next_action: generate_core
core next_action:    generate_detail | repair_core | complete
```

`generate_detail`과 `repair_core`는 모두 같은 `/finalize`를 호출한다. client는 next action을 request body로
되돌려 서버 실행 종류를 지정하지 않는다. finalize가 execution status를 다시 읽어 repair와 detail 순서를
결정한다. fatal `error`와 `cancelled`에는 다음 phase action이 없다.

```text
사용자 질문 제출
       |
       v
prepare JSON -- next_action=generate_core --> core SSE
                                                  |
                                      phase_complete.next_action
                                      +-- generate_detail --+
                                      +-- repair_core -------+--> finalize SSE --> complete
                                      +-- complete -----------> 같은 core stream에서 complete
```

LlamaIndex는 POST/GET이나 HTTP 전송을 결정하지 않는다. `ResponseSynthesizer`는 async 생성 stream을
제공하고 FastAPI가 SSE를 담당한다. raw LlamaIndex token stream은 생성 계층 내부에서만 소비하며 HTTP와
직결하지 않는다.

```python
# 사용 금지
async for token in llama_response.async_response_gen():
    yield sse(event="token", data=token)
```

외부에는 grounding을 통과한 domain event만 보낸다.

### 7.2 authoritative execution과 응답 모델

서버의 `question_execution`이 route, 근거, phase 상태, 오류와 최종 답변의 유일한 정본이다. client가
전달한 route, evidence, repair 여부나 phase 완료 주장은 신뢰하지 않는다.

```text
question_execution
├─ execution_id, optional user_id, question_hash, as_of_date
├─ private short-lived request payload(question, project stage)
├─ status
│  ├─ preparing / prepared
│  ├─ core_generating / core_answered / core_repair_required
│  ├─ finalizing / phase_recovery_required
│  ├─ completed / failed / cancelled
├─ active_generation_id와 generation pin, route_result
├─ evidence IDs, frozen citation registry
├─ verified core, verified detail components
├─ accumulated PipelineIssues
├─ prepare idempotency key, phase idempotency keys와 lease/version
└─ expires_at
```

execution은 짧은 TTL의 private 서버 상태로 저장한다. 로그인 질문은 완료 시 기존 보존 계약의 authoritative
question history에 저장하고, 익명 질문은 history에 저장하지 않은 채 재전송에 필요한 짧은 TTL 뒤 execution
payload를 삭제한다. 질문 본문은 phase 입력에 필요하므로 hash만 저장하지 않지만 log·event에는 남기지
않는다. execution ID는 추측하기 어려운 식별자이고 모든 phase에서 소유자 또는 익명 execution capability,
만료, 현재 상태와 허용된 전이를 다시 검사한다. 브라우저에는 evidence 원문이나 조작 가능한 route state를
다음 phase 입력으로 돌려주지 않는다.

여러 법률 주장을 하나의 긴 문자열에 넣지 않는다. 독립된 법률 주장 하나를 `GroundedSentence`로 표현하고
summary, section, checklist가 모두 동결된 `CitationRegistry`를 직접 인용한다. summary나 앞 section을
다음 section의 법적 근거로 사용하지 않는다.

```python
class GroundedSentence:
    text: str
    citation_ids: list[str]

class GroundedSection:
    claim: GroundedSentence
    explanations: list[GroundedSentence]
```

사용자에게 보이는 전체 응답 순서는 다음과 같다.

1. `status`: “답변을 위한 근거를 확인하고 있습니다.”
2. `summary`: 검증된 핵심 답변 1~3문장과 그 문장들이 사용한 인용 원문
3. `section`: claim과 explanation을 각각 검증한 상세 설명
4. `checklist_item`: 검증된 체크리스트 한 항목
5. `citations`: 전체 공식 근거 원문
6. `limitations`: 답변 범위
7. `complete`: 저장된 최종 authoritative `QuestionResponse`이며 execution당 한 번만 확정

client는 다음의 얇은 transport state machine만 가진다.

```text
idle -> preparing -> core_streaming
                         |
                         +-- generate_detail --+
                         +-- repair_core -------+--> finalizing -> completed
                         +-- complete --------------------------> completed
```

client 책임은 endpoint 호출, 검증된 SSE 표시, 같은 execution/phase 재연결과 사용자 취소뿐이다. route,
grounding, repair 필요 여부, 생성 우선순위와 최종 답변 확정은 서버 책임이다. 알 수 없는 `next_action`은
추측해 진행하지 않고 protocol error로 중단한다.

### 7.3 생성·검증·repair

prepare phase가 검색 근거와 `CitationRegistry`를 동결한다. core phase의 custom
`GroundedStreamingResponseSynthesizer`는 Ultra raw stream을 내부에서 소비해 summary candidate만 만들고,
로컬 문장별 grounding을 통과한 `SummaryEvent`와 핵심 citation을 먼저 공개한다. core grounding이 실패하면
candidate를 공개하지 않고 `status=core_repair_required`, `next_action=repair_core`를 저장한다. 같은 core
invocation에서 추가 Ultra repair를 호출하지 않는다.

finalize phase는 서버 상태를 읽어 실행 순서를 정한다. `core_repair_required`이면 core repair를 최우선으로
한 번 시도하고, 실패하면 결정적 핵심 fallback을 확정한다. `core_answered`이면 바로 detail 생성으로 간다.
남은 provider budget에서 중요 section, 나머지 section, checklist, 선택 설명 순으로 생성하며 시간이 부족하면
후순위 component를 안전 문구로 대체한다.

```python
# [LlamaIndex Custom + 직접 작성]
async for candidate in synthesizer.astream_phase(execution.phase_input()):
    verified = verifier.verify(candidate, execution.citations)  # local bounded code
    if verified:
        await execution_repository.append_verified(execution.id, verified)
        yield AnswerEvent.from_verified(verified)  # raw token이 아님
    else:
        await execution_repository.record_issue(execution.id, GROUNDING_FAILED)
```

`GroundingChecker`는 최소한 다음을 결정적으로 검사한다.

- citation이 하나 이상 있는가
- 모든 citation ID가 frozen registry에 존재하는가
- 숫자·기간·비율이 인용 원문에 있는가
- 의무·금지·허용 등 강한 규범 표현을 원문이 뒷받침하는가
- `모든`, `항상`, `예외 없이` 같은 과장·범위 확대 표현이 근거에 없는가

이번 단계에서는 별도의 무거운 semantic similarity 모델을 grounding 판정에 추가하지 않는다. 각 문장은
자신이 선언한 citation과 frozen registry 안의 관련 근거를 기준으로 검사하며, 다른 summary나 section을
근거로 통과시키지 않는다.

core의 첫 검사 실패는 다음 `finalize` invocation에서 해당 문장만 한 번 repair한다. detail 문장의 검사
실패는 같은 finalize phase의 남은 provider budget이 충분할 때만 한 번 repair하고, 아니면 즉시 같은
citation을 가리키는 결정적 fallback 문장으로 대체한다. 전체 summary나 section을 다시 생성하지 않는다.

section 생성이나 repair가 실패해도 이미 전송한 summary를 철회하지 않는다. 해당 section은 다음과 같은
안전 문구로 대체한다.

> 상세 설명 일부를 확정하지 못했습니다. 위 핵심 답변과 인용된 공식 원문을 확인해 주세요.

checklist 항목도 검증을 통과하거나 결정적 fallback으로 바뀐 뒤에만 공개한다. `limitations`는 새 법률
주장을 만들지 않는 승인된 결정적 문구를 사용한다.

### 7.4 전송과 완료

준비 요청은 질문을 받아 execution을 만들고 route·embedding·retrieval을 끝낸다.

```http
POST /v2/question-executions
Content-Type: application/json
Idempotency-Key: submit-opaque-id

{"question":"...", "as_of_date":"2026-08-27"}
```

```json
{"execution_id":"exec-123", "status":"prepared", "next_action":"generate_core"}
```

```python
# [직접 작성] JSON preparation adapter
prepared = await preparation_service.prepare(request, user)
return {
    "execution_id": prepared.id,
    "status": prepared.status,
    "next_action": prepared.next_action,  # generate_core
}
```

core 요청은 execution 상태를 `core_generating`으로 원자 전이한 뒤 핵심 답변만 SSE로 생성한다. 검증된
summary가 있으면 즉시 UI에 표시하고 마지막 `phase_complete`에서 `generate_detail` 또는 `repair_core`를
지시한다. 상세가 필요 없고 최종 정본까지 저장했다면 `next_action=complete` 뒤 같은 stream에서 `complete`
event를 보내며 client는 finalize를 호출하지 않는다.

```text
event: summary
data: {"sentences":[...], "citations":[...]}

event: phase_complete
data: {"status":"core_answered", "next_action":"generate_detail"}
```

finalize endpoint는 client가 전달한 repair 종류를 신뢰하지 않고 execution status로 repair 여부와 detail
우선순위를 결정한다. core가 repair된 경우에만 새 검증 summary를 먼저 보내고 section, checklist,
citations, limitations를 순차 공개한다. 로그인 요청은 authoritative `QuestionResponse`를 이력에 먼저
저장하고, 익명 요청은 final response를 execution에만 저장한 뒤 `completed`로 전이한다. 마지막 `complete`
event에는 최종 정본과 nullable history ID를 넣는다. client는 앞서 조립한 UI 상태를
`complete.response`로 교체한다.

```python
# [직접 작성] 얇은 phase SSE adapter
execution = await execution_repository.get_owned(execution_id, user.id)
events = phase_service.stream_authoritative_next_phase(execution)
return StreamingResponse(sse_presenter.present(events))
```

각 handler는 경계 입력·인증·quota·readiness, execution 소유권·만료·상태 전이와 admission을 stream 시작
전에 끝낸다. provider body, raw exception, 질문 원문은 event나 log에 남기지 않는다.

### 7.5 예외 수집과 최종 답변 결정

모든 stage는 알려진 외부 실패를 raw exception으로 상위에 흘리지 않고 안정된 `PipelineIssue`로 변환해
execution에 append한다. 세 HTTP 요청은 같은 issue 원장을 복원하고 이어 쓴다. issue에는 stage, phase,
공개 가능한 reason code, recoverable 여부와 fallback 선택에 필요한 최소 정보만 담는다. stack trace,
provider body, DB 오류 전문과 질문 원문은 issue나 최종 LLM 입력에 넣지 않는다.

```python
# [직접 작성] execution 단위 append-only 오류 원장
issues = await issue_repository.for_execution(execution.id)
result = await stage_boundary.capture(current_phase.run(execution), issues)
await issue_repository.append(execution.id, result.issues)

# [직접 작성] terminal path의 유일한 정상/제한/fallback 완료 결정 지점
terminal = final_answer_coordinator.finalize(
    verified_content=execution.verified_snapshot(),
    evidence=execution.frozen_evidence,
    issues=await issues.public_view(),
    remaining_time=phase_deadline.remaining(),
)
yield terminal
```

분류와 종료 흐름은 다음과 같다.

```text
prepare / core / finalize stage
                  |
                  v
          stage exception boundary
                  |
       +----------+-----------+----------------+
       |                      |                |
       v                      v                v
RecoverableIssue         FatalFailure       Cancelled
       |                      |                |
       v                      v                v
execution issue ledger  typed error        cancelled
       |                 complete 없음       complete 없음
       v
검증된 content + evidence + 누적 issue
       |
       v
FinalAnswerCoordinator
       |
       +-- 검증된 답변 있음 ------> 내용 유지 + 제한사항
       |                            -> complete(outcome="degraded")
       |
       +-- 근거는 있으나 생성 실패 -> 남은 model budget 있음?
       |                              +-- 예 -> 안전 생성 후 grounding
       |                              +-- 아니오 -> 결정적 fallback
       |
       +-- 근거 없음/route 불가 ----> 법률 주장 없는 결정적 안내
                                      -> complete(outcome="degraded")
```

`RecoverableIssue`에는 selector timeout/provider/schema 실패, 검색 timeout·근거 없음, 생성 provider 오류,
문장 repair 실패와 선택 section/checklist 실패가 포함된다. selector 실패는 임의로 `legal_search`를 선택하지
않고 기존 `routing_unavailable` no-search 경로로 보낸다. 이미 공개한 검증된 summary와 section은 후속 실패
때 철회하지 않는다.

준비 fatal failure는 execution을 `failed`로 만들고 core를 허용하지 않는다. core fatal failure는 finalize를
허용하지 않는다. core timeout·grounding 실패가 안전한 상태로 기록되면 `next_action=repair_core`로
finalize를 허용한다. finalize timeout/provider 실패는 이미 검증된 core와 승인된 제한 문구로
`complete(outcome="degraded")`를 만든다. core repair가 아직 성공하지 않아 검증된 core가 없으면 법률
주장이 없는 결정적 핵심 fallback을 먼저 저장하고 degraded 완료한다.

`degraded_complete`라는 별도 SSE event를 추가하지 않는다. 정상과 복구 가능 fallback 모두 기존 `complete`
event를 사용하고 최종 response의 `outcome`을 `normal` 또는 `degraded`로 구분한다. `error`와 `cancelled`는
`complete`와 상호 배타적이다.

`FatalFailure`에는 보안 경계 위반, 출처·데이터 무결성 위반, 프로그래밍 불변조건 위반과 알 수 없는 예외가
포함된다. 이를 법률 답변으로 위장하지 않는다. authoritative response 저장이 실패해도 저장된 정본을
약속하는 `complete`를 보내지 않고 typed `error`로 끝낸다. cancellation은 오류 답변을 새로 만들지 않고
resource를 반납하며, 단순 disconnect는 저장된 phase 상태로 재연결할 수 있다. admission 거부는 phase 시작
전 HTTP `503 system_busy`로 반환한다.

오류가 누적됐다는 이유만으로 마지막에 LLM을 반드시 한 번 더 호출하지 않는다. 검증된 내용과 근거가 있고
현재 phase deadline 안에 model budget이 남았을 때만 안전 생성을 시도한다. model 호출 자체가 실패했거나
남은 시간이 종료 reserve 이하면 승인된 결정적 문구로 종료한다.

### 7.6 timeout과 100명 동시접속 계약

로컬 파싱, typed 결과 변환, issue 수집, citation 조립, SSE 직렬화와 bounded 입력의 결정적 grounding
검사에는 개별 `asyncio.timeout()`을 두지 않는다. 이 작업은 입력 크기 상한과 테스트로 실행 시간을
제어한다. 계산 복잡도가 `O(1)` 또는 bounded라는 사실은 network, provider queue, DB lock과 connection
pool 대기까지 보장하지 않으므로 외부 대기 경계는 별도로 제한한다.

각 HTTP phase는 새 Vercel invocation과 새 monotonic deadline을 가진다. 현재 `maxDuration=60`을 유지하며
Ultra에 정확히 60초를 설정해 platform hard kill과 경쟁시키지 않는다. 아래 값은 v2 execution에만 적용하며
v1의 기존 `52 < 55 < 60` 계약은 바꾸지 않는다.

| 경계 | 상한 | 적용 방식 |
|---|---:|---|
| 각 Vercel Function hard limit | 60초 | 애플리케이션 timeout이 아닌 최후 kill switch |
| prepare API deadline | 12초 | route·embedding·retrieval·근거 고정 전체 |
| Router LLM | 8초 | prepare deadline 안의 selector provider 호출 |
| 원격 query embedding | 5초 | prepare deadline 안의 provider 호출 |
| core/finalize API deadline | 57초 | 각 SSE invocation에 독립 적용 |
| core/finalize Ultra provider budget | 총 55초 | phase 안의 모든 Ultra 호출과 retry가 공유 |
| core/finalize 저장·종료 reserve | 2초 | 남은 시간이 이 값 이하면 새 model 호출 금지 |
| phase admission 대기 | 1초 | 수용 불가 시 provider 호출 전에 거부 |
| admission 거부 응답 | 2초 이내 | stream 시작 전 HTTP `503 system_busy` |

세 phase가 모두 각 상한까지 사용하면 provider 작업을 포함한 application deadline 합은 최대 126초
(`12 + 57 + 57`)다. 이는 한 요청의 57초 timeout을 숨겨 연장한 것이 아니라, 검증된 core를 먼저 보여주며
각 phase 실패를 독립 복구하기 위해 선택한 end-to-end trade-off다. 재연결은 저장된 `phase_started_at`과
deadline을 이어 쓰며 해당 phase의 57초를 새로 초기화하지 않는다. admission 거부 뒤 사용자 대기시간은
이 합계에 숨기지 않고 `system_busy`로 즉시 드러낸다.

core에서는 Ultra summary 호출 하나만 55초 provider budget을 사용한다. finalize에서는 core repair와 detail
호출이 각각 새 55초를 받지 않고 같은 55초를 공유한다. repair가 길어지면 detail component를 줄이고,
남은 시간이 reserve 이하면 새 호출을 시작하지 않는다. section/checklist별 8초 같은 근거 없는 고정
timeout은 두지 않는다. DB connection 획득·statement와 외부 HTTP는 해당 driver/client timeout을 사용하되
로컬 application stage 전체를 다시 timeout으로 감싸지 않는다.

Ultra provider에 실제 60초를 온전히 주는 값은 현재 목표가 아니다. 이를 도입하려면 생성 endpoint의
platform limit을 최소 75초로 먼저 늘리고 `platform >= 75초`, API 67초, provider 60초, reserve 5초의
새 계약을 부하 검증해야 한다. platform 60초인 상태에서 provider timeout만 60초로 올리지 않는다.

prepare 이후 각 phase는 `(execution_id, phase)` idempotency key와 원자 상태 전이를 사용한다. client
연결이 끊겨 같은 phase를 다시 POST해도 동시에 두 Ultra 작업을 만들지 않는다. 검증된 phase event는 emit
전에 저장해 재전송할 수 있게 한다.

```text
같은 phase 재요청
├─ 시작 전   -> 한 번만 실행 시작
├─ 실행 중   -> typed in_progress/reconnect 상태
└─ 완료됨    -> 저장된 phase event/result 재전송
```

NVIDIA provider가 동일 요청의 exactly-once idempotency를 보장하지 않는 한, process crash 직후 외부 호출이
끝났는지 알 수 없는 상태에서 자동으로 두 번째 Ultra 호출을 시작하지 않는다. execution을
`phase_recovery_required`로 표시하고 명시적 복구 정책이 결정될 때까지 fail-closed한다. 따라서 여기서의
멱등성은 정상·연결 재시도에서 동일 논리 결과와 at-most-one active call을 보장하며 provider exactly-once를
과장하지 않는다.

자동 transport retry는 같은 execution과 phase로 최대 한 번만 허용한다. client가 새 execution을 발급해
처음부터 다시 시작하거나 답변 텍스트를 보고 다른 phase를 호출하지 않는다. 사용자 취소는 현재 phase를
취소하고 다음 `next_action`을 실행하지 않는다.

100명 동시접속은 100개의 Ultra 호출을 무조건 동시에 실행한다는 뜻이 아니다. Vercel의 여러 instance가
공유할 수 있도록 provider admission은 인메모리 semaphore가 아니라 짧은 TTL의 DB capacity lease로
구현한다. lease 획득·갱신·반납은 짧은 transaction이며 Ultra 호출 동안 DB transaction이나 connection을
붙잡지 않는다. DB admission 상태를 확인할 수 없으면 provider를 호출하지 않고 `503 system_busy`로
fail-closed한다.

provider 전체 capacity 아래 prepare, core, finalize phase sub-limit을 분리하고 core에 더 높은 우선순위와
예약 용량을 준다. finalize에도 최소 예약 용량을 둬 지속적인 core 유입이 detail을 영구 starvation시키지
않게 한다. 실제 slot 수와 DB pool 크기는 NVIDIA quota와 100-execution 부하 테스트 결과로 정한다.
finalize가 admission에서 거부되면 검증된 core를 유지하고 같은 execution/phase로 재시도할 수 있다.

100개의 동시 사용자 execution 부하 검증은 다음을 만족해야 한다.

- prepare는 12초, accepted core/finalize는 각각 57초를 넘거나 Vercel hard kill에 도달하지 않는다.
- 재연결이 phase deadline을 초기화하지 않고, admission 대기를 제외한 세 phase 상한 합이 126초임을 지킨다.
- 용량 초과 phase는 provider 호출을 시작하지 않고 2초 안에 `503 system_busy`와 같은 `next_action`을 받는다.
- 같은 execution/phase retry가 Ultra 호출을 중복 생성하지 않는다.
- recoverable finalize failure는 검증된 core를 유지해 `complete(outcome="degraded")`로 끝난다.
- fatal failure와 cancellation은 `complete`로 위장되지 않는다.
- DB pool exhaustion과 무제한 task/queue 증가가 없고 cancellation 뒤 slot/lease가 반환된다.

## 8. 추상화와 모듈 경계

상위 application service는 구체 SDK가 아니라 다음 port를 생성자로 받는다.

| Port/객체 | 책임 | 기본 adapter |
|---|---|---|
| `CorpusDocumentReader` | canonical 조문 snapshot 읽기 | LlamaIndex `DatabaseReader` adapter |
| `SourceChangeDetector` | source/transform fingerprint 비교 | 순수 프로젝트 코드 |
| `GenerationRepository` | catalog, active pointer, rollback | SQLAlchemy adapter |
| `GenerationVectorStoreFactory` | 주입된 engine으로 generation store 생성 | `PGVectorStore` adapter |
| `NodeTransformationPipeline` | chunk와 embedding 계산 | `IngestionPipeline` adapter |
| `ActiveVectorIndexProvider` | 요청별 active index 확정·cache | `VectorStoreIndex` adapter |
| `LegalRouteSelector` | typed route decision | NVIDIA + LlamaIndex selector adapter |
| `RouteQueryEngineFactory` | route별 QueryEngineTool 조립 | LlamaIndex custom factory |
| `GroundedResponseSynthesizer` | component 생성 stream | LlamaIndex `ResponseSynthesizer` adapter |
| `SentenceGroundingVerifier` | 문장 검사·repair·fallback | 프로젝트 안전 계층 |
| `QuestionExecutionRepository` | phase 상태·근거·검증 결과·lease의 authoritative 저장 | SQLAlchemy adapter |
| `QuestionPhaseCoordinator` | 상태 전이와 typed `next_action` 결정 | 프로젝트 application 계층 |
| `PipelineIssueCollector` | execution별 recoverable issue 누적·공개 정보 제한 | 프로젝트 application 계층 |
| `FinalAnswerCoordinator` | 검증된 내용·근거·issue로 terminal 결과 결정 | 프로젝트 application 계층 |
| `ConcurrencyLimiter` | provider 총량·phase별 예약 admission과 bounded core 우선순위 | DB TTL capacity lease adapter |
| `AnswerEventPresenter` | domain event를 SSE로 직렬화 | FastAPI SSE adapter |

교체 가능성은 불필요한 범용 factory가 아니라 실제 외부 경계에 둔다. 테스트에서는 reader, embedding,
selector, LLM, vector store, clock과 repository를 fake로 주입한다. domain 계층은 LlamaIndex, SQLAlchemy,
FastAPI, NVIDIA 타입을 직접 import하지 않는다.

## 9. 실패와 관측 가능성

- Index build 실패: 새 generation을 inactive/failed로 기록하고 이전 active를 유지한다.
- 복사·embedding·add·삭제 반영·검증 중 하나라도 실패: run 전체 실패, 부분 게시 없음.
- Router recoverable 실패: execution에 `routing_unavailable`을 기록하고 검색을 건너뛴 뒤
  `next_action=generate_core`의 안전 안내 경로로 진행.
- prepare fatal 실패: execution `failed`, core 호출 금지.
- 검색 근거 없음: 근거 부족 domain response만 생성.
- core grounding 실패: 검증 전 내용은 미공개, `core_repair_required`와 `next_action=repair_core`.
- core fatal 실패: execution `failed`, finalize 호출 금지.
- finalize repair/section/checklist 실패: 검증된 core가 있으면 유지하고, 없으면 법률 주장이 없는 결정적
  core fallback을 저장한 뒤 남은 component fallback과 degraded 완료.
- section 실패: 이미 공개된 summary 유지, 안전 section fallback 공개.
- core stream 후 recoverable 예외: issue와 안전 상태를 저장하고 typed `next_action`으로 finalize 여부 결정.
- finalize stream 후 recoverable 예외: issue를 누적하고 이미 검증된 core를 유지한
  `complete(outcome="degraded")`로 종료. 검증된 core가 없으면 결정적 core fallback을 먼저 저장.
- stream 후 fatal·알 수 없는 예외: 안전한 typed `error`, raw 예외 미노출, `complete` 없음.
- client disconnect: phase 상태를 보존하고 같은 execution/phase 재연결을 허용하되 새 Ultra 호출은 금지.
- process crash 뒤 provider 완료 여부 불명: `phase_recovery_required`, 자동 Ultra 재호출 금지.
- 사용자 취소: 현재 phase에 cancellation을 전달하고 다음 phase 미실행, `complete` 없음.
- admission 초과: phase 시작 전 `503 system_busy`와 같은 `next_action`, provider 호출 미실행.

관측 stage는 source loading, change detection, vector copy, transformation, generation verification,
active switch, execution prepare/core/finalize, phase state transition, routing, retrieval, citation freeze, summary
generation/validation, repair, section generation/validation, checklist generation/validation, issue collection,
terminal decision, admission wait/reject, reconnect/deduplication, history save, stream completion을 분리한다. 로그에는
질문 원문, 원문 전문, 인증정보와 provider body를 남기지 않는다.

## 10. v1 호환성과 전환

v1은 LlamaIndex를 import하거나 새 generation table을 사용하지 않는다. v2 개편에 필요한 인증·quota·이력·
grounding의 직접 작성 코드를 공통 port/factory로 추출할 수는 있지만, v1의 request/response와 동작이
동일함을 회귀 테스트로 고정한다.

v2는 다음 호환성 변경을 의도적으로 수용한다.

| 문제 상황 | 원인 | 해결 |
|---|---|---|
| 기존 `/v2/questions` client가 단일 JSON/SSE 요청을 기대함 | Ultra phase마다 독립 실행 시간이 필요함 | 기존 endpoint를 제거하고 prepare/core/finalize client state machine으로 함께 교체, v1은 유지 |
| client가 답변 내용을 보고 다음 단계를 추론할 위험 | 세 HTTP 요청을 client가 순서대로 호출함 | 서버의 닫힌 `next_action`만 실행하고 알 수 없는 값은 중단 |
| 연결 재시도가 Ultra 호출을 중복 생성함 | phase가 여러 HTTP 요청에 걸침 | `(execution_id, phase)` 멱등 key와 서버 lease/state로 재전송·재연결 |
| 기존 single vector table에 부분 변경이 남을 수 있음 | generation 격리가 없음 | 초기 full generation을 만든 뒤 검증·pointer 전환 |
| API가 질문 embedding을 중복 호출함 | 직접 embed 후 LlamaIndex store query | `VectorStoreIndex`에 embed model을 주입하고 한 번만 실행 |
| `PGVectorStore`가 engine을 내부 생성함 | `from_params()` 사용 | composition root가 sync/async engine을 모두 주입 |
| 기존 전체 `DraftAnswer` 검증 전에는 아무 내용도 공개할 수 없음 | 여러 주장이 큰 문자열에 묶임 | 원자적 `GroundedSentence` 생성·검증 뒤 domain event 공개 |

마이그레이션 동안 모든 v2 endpoint를 닫고 새 형식 generation을 처음부터 만든다. 성공 뒤 active pointer를
전환하고 기존 구현 코드는 제거한다. 전환 직전 색인은 rollback 대상으로 물리 보존한다. 새 runtime에서
읽을 수 있는 metadata·embedding 계약인지는 migration preflight에서 검증하며, 호환되지 않으면 첫 번째
새 형식 generation을 rollback baseline으로 확정하기 전까지 v2를 다시 열지 않는다.

## 11. 검증 계약

구체 명령은 실행계획에서 현재 workspace 도구에 맞게 확정한다. 최소 검증 범위는 다음과 같다.

- engine factory가 composition root 밖에서 호출되지 않는지와 모든 `PGVectorStore` engine identity
- Index Builder의 sync 실행과 API의 async 실행, unused `NullPool`, 종료 시 단일 dispose
- source hash와 transform fingerprint별 copy/full reindex 분기
- deterministic node ID, source coverage, lineage, vector dimension과 finite 값
- `UPSERTS` 미사용, pipeline에 `vector_store` 미주입, 신규 generation에만 `add()`
- 실패 generation 미게시, pointer 원자 전환, rollback, active+previous+live execution pin retention
- active pointer 변경 시 `VectorStoreIndex` cache 교체와 요청 내 generation 고정
- 질문 embedding 단일 호출, 기준일 경계, invalid metadata 제외, retrieval/evidence budget 분리
- 네 정상 route와 `routing_unavailable` fail-closed, execution별 context 동시성 격리
- prepare/core/finalize endpoint와 execution 소유권·TTL·허용 상태 전이, 기존 `/v2/questions` 제거
- prepare `Idempotency-Key` 재요청의 동일 execution 반환과 route·검색 단일 실행
- prepare에서 generation pin 확정, pointer 전환 중 동일 evidence 유지, 완료·취소·만료 뒤 pin 해제와 cleanup
- client가 response text가 아니라 닫힌 `next_action`만 따르고 알 수 없는 값에서 중단하는 계약
- `(execution_id, phase)` 재요청의 단일 Ultra 실행, running reconnect와 completed phase 재전송
- raw LlamaIndex token이 SSE로 노출되지 않는 계약
- summary/section/checklist가 citation registry를 직접 참조하고 검증 전에는 event가 없는 계약
- 숫자·규범·과장 표현 실패, 문장별 repair 횟수, section fallback, authoritative `complete`
- 세 phase의 route·검색·생성·grounding issue 영속 누적과 단일 `FinalAnswerCoordinator` 종료 결정
- recoverable `complete(outcome="degraded")`, fatal typed `error`, cancelled, history 저장 실패의 상호 배타적
  terminal 계약
- 로컬 bounded 코드에 개별 timeout이 없고 phase별 model/embedding 외부 호출만 독립 deadline을 쓰는 계약
- prepare 12초, core/finalize 57초, phase별 Ultra 총 55초와 2초 reserve의 경계
- 100개 동시 execution에서 core 우선 admission, 1초 대기, 2초 이내 `503 system_busy`, queue/slot/lease 회수
- 여러 Vercel instance의 DB capacity lease 전역 상한, 짧은 transaction, stale lease 회수와 DB 장애 fail-closed
- stream 시작 전 HTTP 오류와 시작 후 typed error/cancelled, disconnect, 이력 저장 순서
- v1 회귀와 web SSE 소비 end-to-end

## 12. 구현계획에서만 정할 세부값

다음은 설계 미결정이 아니라 환경과 테스트 결과에 맞춰 실행계획에서 고정할 구현 상수다.

- 실제 class/file 배치와 migration 파일 번호
- 안전한 generation table 이름 형식
- DB pool size, overflow와 전체 connection budget 수치
- embedding batch size와 provider retry 간격
- retrieval top-k와 generation evidence count의 초기값
- repair token 상한
- 부하 테스트로 확정할 provider별 `ConcurrencyLimiter` 동시 실행 수
- DB capacity lease TTL·heartbeat·stale 회수 주기와 phase별 예약 slot 수
- prepare 중간 execution TTL과 완료/실패 execution 정리 시점
- phase lease 만료 시간, SSE heartbeat 주기와 running phase reconnect 표현
- generation 보존 정리 시점과 운영 명령 이름

## 13. 결정 기록

- 2026-08-27: 프레임워크 사용 범위를 `IngestionPipeline`, `VectorStoreIndex`, QueryEngine,
  `ResponseSynthesizer`, Router까지 확장한다.
- 2026-08-27: v1은 non-LlamaIndex 구현으로 동결하고 동작 호환적인 직접 코드 추출만 허용한다.
- 2026-08-27: collector, LlamaIndex index builder, API를 별도 실행 단위로 유지한다.
- 2026-08-27: DB type을 반복 검사하는 source validator를 제거하고 generation 불변조건만 검증한다.
- 2026-08-27: 모든 engine은 composition root에서 만들고 `PGVectorStore`에 sync/async engine을 반드시
  주입한다. 사용하지 않는 방향은 `NullPool`을 쓴다.
- 2026-08-27: [보완됨] generation별 물리 vector table, catalog와 active pointer를 사용한다. active와
  immediate rollback을 보존하고, 3-phase API의 live execution이 참조하는 generation은 완료·취소·만료까지
  임시 pin한다.
- 2026-08-27: unchanged vector는 fingerprint가 같을 때 DB-to-DB로 복사하고 changed source만 재처리한다.
  transform fingerprint가 바뀌면 전체 재색인한다.
- 2026-08-27: `IngestionPipeline`은 chunk와 embedding 계산만 담당하고 vector store를 받지 않는다.
  `DocstoreStrategy.UPSERTS`를 쓰지 않으며 신규 generation에는 `PGVectorStore.add()`를 사용한다.
- 2026-08-27: generation 전체 검증 성공 뒤에만 active pointer를 원자적으로 전환하며 실패 시 이전 index를
  유지한다.
- 2026-08-27: LlamaIndex Router는 `LegalRouteSelector`와 `LegalRouterQueryEngine`으로 확장해 기존 route
  taxonomy와 fail-closed metadata를 보존한다.
- 2026-08-27: [대체됨] 기존 `POST /v2/questions`를 SSE 전용으로 변경하고 별도 stream/non-stream 경로를
  두지 않는다. 아래의 3-phase execution API 결정으로 대체한다.
- 2026-08-27: LlamaIndex raw generation token은 HTTP와 직결하지 않고 문장별 grounding을 통과한 summary,
  section, checklist domain event만 공개한다.
- 2026-08-27: [대체됨] route·검색·생성·grounding의 복구 가능 오류는 요청별
  `PipelineIssueCollector`에 누적하고
  `FinalAnswerCoordinator` 하나가 검증된 부분 답변, 제한 답변, 결정적 fallback을 선택한다. fatal·취소·
  admission 거부는 법률 답변으로 위장하지 않는다. 오류 원장의 execution 영속 범위는 아래 결정으로
  대체한다.
- 2026-08-27: [대체됨] 로컬 bounded 코드에는 개별 timeout을 두지 않고, 52초 요청 deadline 안에서 LLM·원격
  embedding과 DB·HTTP 외부 대기 경계만 제한한다. 100명 동시접속은 주입된 limiter, 1초 admission 대기,
  2초 이내 `503 system_busy`와 부하 검증 계약으로 다룬다. 단일 deadline은 아래 phase별 deadline으로
  대체한다.
- 2026-08-27: 기존 `/v2/questions`를 제거하고 JSON prepare, SSE core, SSE finalize 세 endpoint와 서버
  `question_execution` 정본을 사용한다. client는 typed `next_action`만 따라 호출하며 법률·안전 판단을
  하지 않는다.
- 2026-08-27: prepare는 12초, core/finalize는 각각 별도 57초 API deadline과 총 55초 Ultra budget, 2초
  reserve를 사용한다. 여러 Vercel instance가 공유하는 DB TTL capacity lease로 phase limiter를 분리하고
  100명 동시접속에서 core를 detail보다 우선하되 finalize 최소 용량을 보존한다.
- 2026-08-27: 오류, 검증 결과와 phase 상태는 execution에 영속 누적한다. 같은 `(execution_id, phase)`의
  retry/reconnect는 동시 중복 Ultra 호출을 만들지 않고, provider 완료 여부 불명 상태에서는 자동 재호출을
  금지하며, 최종 `complete`는 execution당 한 번만 확정한다. 최초 prepare 재시도는 별도
  `Idempotency-Key`로 같은 execution을 반환한다.
- 2026-08-27: human-in-the-loop, realtime/attachment tool, agent workflow와 generation별 HNSW
  성능평가는 다음 목표로 분리한다.
