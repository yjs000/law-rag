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
- 기존 `POST /v2/questions`를 SSE 전용 endpoint로 변경한다. 별도 non-stream endpoint는 만들지 않는다.
- 원자적인 법률 주장 단위로 grounding을 통과한 summary, section, checklist만 SSE로 공개한다.
- route·검색·생성·grounding에서 발생한 복구 가능 오류를 요청 단위로 누적하고, 하나의 최종 답변
  coordinator가 검증된 부분 답변·제한 답변·결정적 fallback 중 하나를 선택한다.
- 로컬 bounded 계산에는 개별 timeout을 두지 않고 LLM·원격 embedding·DB 같은 외부 대기 경계와 전체
  요청 deadline만 제한한다. 100명 동시접속 시에는 무제한 대기 대신 admission control을 적용한다.
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
route → active generation 검색 → 생성 → 문장별 grounding → SSE 응답
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
- 성공 후 active와 immediate rollback generation의 물리 table만 보존한다. catalog 이력은 남긴다.
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
8. active와 immediate rollback table을 남기고 더 오래된 물리 table을 정리한다.
9. v2 readiness를 연다.

실패한 generation은 active가 되지 않는다. 이전 active index와 pointer를 유지하고 run은 실패로 기록한다.
부분 성공을 허용하지 않으며 resume, dry-run, 부분 source 실행은 이번 범위에 없다. 재시도는 처음부터 새
generation을 만든다. rollback은 pointer를 immediate previous generation으로 되돌리는 명시적 운영 동작이다.

## 6. 요청 시 검색과 Router

### 6.1 Active index

요청 시작 시 active generation을 한 번 확정하고 요청 종료까지 같은 index를 사용한다. pointer 전환 뒤
시작한 요청부터 새 generation을 사용한다. `GenerationIndexRegistry`가 generation별 `PGVectorStore`와
`VectorStoreIndex`를 cache하고 pointer가 달라졌을 때 교체한다.

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
보존한다. 선택 결과는 전역 mutable state가 아니라 요청별 `RouteExecutionContext`로 선택된 engine에
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

### 7.1 단일 endpoint 계약

`POST /v2/questions` 하나만 유지하고 응답 media type을 `text/event-stream`으로 바꾼다. 별도의
`/stream` endpoint와 non-stream service를 두지 않는다. v2 request schema는 유지하지만 response transport가
JSON에서 SSE로 바뀌므로 web client도 같은 구현 milestone에서 `fetch()` response stream 소비 방식으로
변경한다. v1 endpoint와 client 계약은 바꾸지 않는다.

LlamaIndex는 POST/GET이나 HTTP 전송을 결정하지 않는다. `ResponseSynthesizer`는 async 생성 stream을
제공하고 FastAPI가 SSE를 담당한다. raw LlamaIndex token stream은 생성 계층 내부에서만 소비하며 HTTP와
직결하지 않는다.

```python
# 사용 금지
async for token in llama_response.async_response_gen():
    yield sse(event="token", data=token)
```

외부에는 grounding을 통과한 domain event만 보낸다.

### 7.2 응답 모델

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

전체 응답 순서는 다음과 같다.

1. `status`: “답변을 위한 근거를 확인하고 있습니다.”
2. `summary`: 검증된 핵심 답변 1~3문장과 그 문장들이 사용한 인용 원문
3. `section`: claim과 explanation을 각각 검증한 상세 설명
4. `checklist_item`: 검증된 체크리스트 한 항목
5. `citations`: 전체 공식 근거 원문
6. `limitations`: 답변 범위
7. `complete`: 저장된 최종 authoritative `QuestionResponse`

### 7.3 생성·검증·repair

검색 근거가 확정되면 `CitationRegistry`를 동결한다. custom `GroundedStreamingResponseSynthesizer`는
LlamaIndex raw stream을 내부에서 소비해 summary candidate를 만들고, 문장별 검증과 repair가 끝난 뒤
`SummaryEvent`를 반환한다. 이어 section과 checklist를 같은 방식으로 하나씩 생성한다.

```python
# [LlamaIndex Custom]
async for candidate in synthesizer.astream_components(nodes):
    verified = await verifier.verify_or_repair(candidate, citations)
    yield AnswerEvent.from_verified(verified)  # raw token이 아님
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

첫 검사 실패 시 해당 문장만 한 번 repair한다. 남은 budget이 충분하고 두 번째 실패가 형식 오류뿐일 때만
두 번째 repair를 허용한다. 전체 summary나 section을 다시 생성하지 않는다. 계속 실패하면 같은 citation을
가리키는 결정적 fallback 문장으로 대체한다.

section 생성이나 repair가 실패해도 이미 전송한 summary를 철회하지 않는다. 해당 section은 다음과 같은
안전 문구로 대체한다.

> 상세 설명 일부를 확정하지 못했습니다. 위 핵심 답변과 인용된 공식 원문을 확인해 주세요.

checklist 항목도 검증을 통과하거나 결정적 fallback으로 바뀐 뒤에만 공개한다. `limitations`는 새 법률
주장을 만들지 않는 승인된 결정적 문구를 사용한다.

### 7.4 전송과 완료

FastAPI handler는 경계 입력·인증·quota·readiness처럼 HTTP 상태 코드가 필요한 검사를 stream 시작 전에
끝낸다. stream이 열린 뒤의 복구 가능 실패는 즉시 일반 `error`로 끝내지 않고 요청별
`PipelineIssueCollector`에 기록한다. 이후 `FinalAnswerCoordinator`가 이미 검증된 내용과 남은 근거를
기준으로 제한 답변 또는 결정적 fallback을 선택한다. fatal failure는 `error`, 사용자 취소는 `cancelled`
event로 끝낸다. provider body, raw exception, 질문 원문은 event나 log에 남기지 않는다.

`ResponseAssembler`는 이미 검증되어 공개한 domain event만 누적한다. 모든 단계가 끝나면 authoritative
`QuestionResponse`를 이력에 먼저 저장하고 `complete` event에 최종 정본과 history ID를 넣는다. client는
앞서 조립한 UI 상태를 `complete.response`로 교체해 전송 누락이나 중복을 복구한다.

```python
# [직접 작성] 얇은 HTTP adapter
events = question_service.stream_answer(request, user)
return StreamingResponse(sse_presenter.present(events))
```

### 7.5 예외 수집과 최종 답변 결정

모든 stage는 알려진 외부 실패를 raw exception으로 상위에 흘리지 않고 안정된 `PipelineIssue`로 변환한다.
issue에는 stage, 공개 가능한 reason code, recoverable 여부와 fallback 선택에 필요한 최소 정보만 담는다.
stack trace, provider body, DB 오류 전문과 질문 원문은 issue나 최종 LLM 입력에 넣지 않는다.

```python
# [직접 작성] 요청 단위 append-only 오류 원장
issues = PipelineIssueCollector()

route = await stage_boundary.capture(router.route(question), issues)
retrieval = (
    await stage_boundary.capture(retriever.retrieve(route), issues)
    if route.allows_retrieval
    else RetrievalResult.skipped(route.reason_code)
)

async for event in answer_pipeline.stream_verified(retrieval, issues):
    yield event

# [직접 작성] 유일한 정상/제한/fallback 완료 결정 지점
terminal = final_answer_coordinator.finalize(
    verified_content=assembler.snapshot(),
    evidence=retrieval.evidence,
    issues=issues.public_view(),
    remaining_time=request_deadline.remaining(),
)
yield terminal
```

분류와 종료 흐름은 다음과 같다.

```text
route / retrieval / generation / grounding
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
PipelineIssueCollector   typed error        cancelled
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

`degraded_complete`라는 별도 SSE event를 추가하지 않는다. 정상과 복구 가능 fallback 모두 기존 `complete`
event를 사용하고 최종 response의 `outcome`을 `normal` 또는 `degraded`로 구분한다. `error`와 `cancelled`는
`complete`와 상호 배타적이다.

`FatalFailure`에는 보안 경계 위반, 출처·데이터 무결성 위반, 프로그래밍 불변조건 위반과 알 수 없는 예외가
포함된다. 이를 법률 답변으로 위장하지 않는다. authoritative response 저장이 실패해도 저장된 정본을
약속하는 `complete`를 보내지 않고 typed `error`로 끝낸다. client disconnect와 cancellation은 오류 답변을
새로 만들지 않고 resource를 반납한다. admission 거부는 stream 시작 전 HTTP `503 system_busy`로 반환한다.

오류가 누적됐다는 이유만으로 마지막에 LLM을 반드시 한 번 더 호출하지 않는다. 검증된 내용과 근거가 있고
전체 deadline 안에 model budget이 남았을 때만 안전 생성을 시도한다. model 호출 자체가 실패했거나 남은
시간이 종료 reserve 이하면 승인된 결정적 문구로 종료한다.

### 7.6 timeout과 100명 동시접속 계약

로컬 파싱, typed 결과 변환, issue 수집, citation 조립, SSE 직렬화와 bounded 입력의 결정적 grounding
검사에는 개별 `asyncio.timeout()`을 두지 않는다. 이 작업은 입력 크기 상한과 테스트로 실행 시간을
제어한다. 계산 복잡도가 `O(1)` 또는 bounded라는 사실은 network, provider queue, DB lock과 connection
pool 대기까지 보장하지 않으므로 외부 대기 경계는 별도로 제한한다.

v2의 timeout 계약은 다음과 같다.

| 경계 | 상한 | 적용 방식 |
|---|---:|---|
| Vercel Function hard limit | 60초 | 애플리케이션 timeout이 아닌 최후 kill switch |
| API 요청 monotonic deadline | 52초 | 모든 stage가 공유하며 새 예산을 만들지 않음 |
| 이력 저장·terminal event reserve | 5초 | 남은 시간이 이 값 이하면 새 model 호출 금지 |
| Router LLM | 6초 | selector provider 호출에만 적용 |
| 원격 query embedding | 5초 | `VectorStoreIndex` 내부 adapter의 provider 호출에 적용 |
| 핵심 답변 LLM | 22초 | summary 생성과 첫 grounding/repair가 공유 |
| repair LLM | 6초 | 핵심 답변 budget과 전체 deadline 안에서만 실행 |
| 선택 section/checklist LLM | 항목당 8초 | 남은 시간 내에서만 실행, 초과 시 해당 항목 fallback |
| admission 대기 | 1초 | 수용 불가 시 model 호출 전에 거부 |
| admission 거부 응답 | 2초 이내 | stream 시작 전 HTTP `503 system_busy` |

위 숫자는 서로 더해 별도 요청 시간을 만드는 할당량이 아니라 하나의 52초 deadline 안에서 각 외부 호출이
가질 수 있는 상한이다. DB connection 획득·statement와 외부 HTTP는 해당 driver/client timeout을 사용하되,
로컬 application stage 전체를 다시 timeout으로 감싸지 않는다. 재시도도 같은 stage와 전체 deadline을
공유하며 reserve 이하에서는 시작하지 않는다.

100명 동시접속은 100개의 LLM 호출을 무조건 동시에 실행한다는 뜻이 아니다. application은 주입된
`ConcurrencyLimiter`로 provider별 실행 수를 제한하고 1초를 넘는 내부 대기열을 만들지 않는다. 실제
동시 실행 수와 DB pool 크기는 NVIDIA quota와 부하 테스트 결과로 정한다. accepted SSE request는 브라우저가
자동으로 전체 요청을 재시도하지 않는다. `accepted` 전 연결 실패만 같은 idempotency key로 최대 한 번
재시도하며 서버는 중복 실행을 막는다.

100개 동시 POST 부하 검증은 다음을 만족해야 한다.

- accepted request가 52초를 넘거나 Vercel hard kill에 도달하지 않는다.
- 용량 초과 request는 model·검색을 시작하지 않고 2초 안에 `503 system_busy`를 받는다.
- recoverable failure는 검증된 내용 유지 또는 결정적 fallback을 거쳐
  `complete(outcome="degraded")`로 끝난다.
- fatal failure와 cancellation은 `complete`로 위장되지 않는다.
- DB pool exhaustion과 무제한 task/queue 증가가 없고 cancellation 뒤 slot이 반환된다.
- 하나의 사용자 요청이 client retry 때문에 여러 LLM pipeline으로 증폭되지 않는다.

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
| `PipelineIssueCollector` | 요청별 recoverable issue 누적·공개 정보 제한 | 프로젝트 application 계층 |
| `FinalAnswerCoordinator` | 검증된 내용·근거·issue로 terminal 결과 결정 | 프로젝트 application 계층 |
| `ConcurrencyLimiter` | provider별 admission과 bounded 대기 | semaphore 기반 infrastructure adapter |
| `AnswerEventPresenter` | domain event를 SSE로 직렬화 | FastAPI SSE adapter |

교체 가능성은 불필요한 범용 factory가 아니라 실제 외부 경계에 둔다. 테스트에서는 reader, embedding,
selector, LLM, vector store, clock과 repository를 fake로 주입한다. domain 계층은 LlamaIndex, SQLAlchemy,
FastAPI, NVIDIA 타입을 직접 import하지 않는다.

## 9. 실패와 관측 가능성

- Index build 실패: 새 generation을 inactive/failed로 기록하고 이전 active를 유지한다.
- 복사·embedding·add·삭제 반영·검증 중 하나라도 실패: run 전체 실패, 부분 게시 없음.
- Router 실패: `routing_unavailable`, 검색과 정상 생성 미실행.
- 검색 근거 없음: 근거 부족 domain response만 생성.
- 문장 grounding 실패: 해당 문장 repair 후 fallback, 검증 전 내용은 미공개.
- section 실패: 이미 공개된 summary 유지, 안전 section fallback 공개.
- stream 후 recoverable 예외: issue를 누적하고 이미 검증된 내용을 유지한
  `complete(outcome="degraded")` 또는 결정적 fallback으로 종료.
- stream 후 fatal·알 수 없는 예외: 안전한 typed `error`, raw 예외 미노출, `complete` 없음.
- client disconnect/취소: request-scoped cancellation을 전달하고 `complete`가 없는 미완료 stream으로 종료.
- admission 초과: SSE 시작 전 `503 system_busy`, model·검색 미실행.

관측 stage는 source loading, change detection, vector copy, transformation, generation verification,
active switch, routing, retrieval, citation freeze, summary generation/validation, section generation/validation,
checklist generation/validation, issue collection, terminal decision, admission wait/reject, history save, stream
completion을 분리한다. 로그에는 질문 원문, 원문 전문, 인증정보와 provider body를 남기지 않는다.

## 10. v1 호환성과 전환

v1은 LlamaIndex를 import하거나 새 generation table을 사용하지 않는다. v2 개편에 필요한 인증·quota·이력·
grounding의 직접 작성 코드를 공통 port/factory로 추출할 수는 있지만, v1의 request/response와 동작이
동일함을 회귀 테스트로 고정한다.

v2는 다음 호환성 변경을 의도적으로 수용한다.

| 문제 상황 | 원인 | 해결 |
|---|---|---|
| 기존 `/v2/questions` client가 JSON을 기대함 | endpoint를 SSE 전용으로 변경 | 같은 milestone에서 web을 SSE client로 교체하고 v1은 유지 |
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
- 실패 generation 미게시, pointer 원자 전환, rollback, active+previous retention
- active pointer 변경 시 `VectorStoreIndex` cache 교체와 요청 내 generation 고정
- 질문 embedding 단일 호출, 기준일 경계, invalid metadata 제외, retrieval/evidence budget 분리
- 네 정상 route와 `routing_unavailable` fail-closed, 요청별 context 동시성 격리
- raw LlamaIndex token이 SSE로 노출되지 않는 계약
- summary/section/checklist가 citation registry를 직접 참조하고 검증 전에는 event가 없는 계약
- 숫자·규범·과장 표현 실패, 문장별 repair 횟수, section fallback, authoritative `complete`
- route·검색·생성·grounding의 복구 가능 issue 누적과 단일 `FinalAnswerCoordinator` 종료 결정
- recoverable `complete(outcome="degraded")`, fatal typed `error`, cancelled, history 저장 실패의 상호 배타적
  terminal 계약
- 로컬 bounded 코드에 개별 timeout이 없고 model/embedding 외부 호출만 공유 deadline을 쓰는 계약
- 100개 동시 POST에서 52초 deadline, 1초 admission wait, 2초 이내 `503 system_busy`, queue/slot 회수
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
- SSE heartbeat 주기와 client reconnect 세부 처리
- generation 보존 정리 시점과 운영 명령 이름

## 13. 결정 기록

- 2026-08-27: 프레임워크 사용 범위를 `IngestionPipeline`, `VectorStoreIndex`, QueryEngine,
  `ResponseSynthesizer`, Router까지 확장한다.
- 2026-08-27: v1은 non-LlamaIndex 구현으로 동결하고 동작 호환적인 직접 코드 추출만 허용한다.
- 2026-08-27: collector, LlamaIndex index builder, API를 별도 실행 단위로 유지한다.
- 2026-08-27: DB type을 반복 검사하는 source validator를 제거하고 generation 불변조건만 검증한다.
- 2026-08-27: 모든 engine은 composition root에서 만들고 `PGVectorStore`에 sync/async engine을 반드시
  주입한다. 사용하지 않는 방향은 `NullPool`을 쓴다.
- 2026-08-27: generation별 물리 vector table, catalog와 active pointer를 사용한다. active와 immediate
  rollback table만 물리 보존한다.
- 2026-08-27: unchanged vector는 fingerprint가 같을 때 DB-to-DB로 복사하고 changed source만 재처리한다.
  transform fingerprint가 바뀌면 전체 재색인한다.
- 2026-08-27: `IngestionPipeline`은 chunk와 embedding 계산만 담당하고 vector store를 받지 않는다.
  `DocstoreStrategy.UPSERTS`를 쓰지 않으며 신규 generation에는 `PGVectorStore.add()`를 사용한다.
- 2026-08-27: generation 전체 검증 성공 뒤에만 active pointer를 원자적으로 전환하며 실패 시 이전 index를
  유지한다.
- 2026-08-27: LlamaIndex Router는 `LegalRouteSelector`와 `LegalRouterQueryEngine`으로 확장해 기존 route
  taxonomy와 fail-closed metadata를 보존한다.
- 2026-08-27: 기존 `POST /v2/questions`를 SSE 전용으로 변경하고 별도 stream/non-stream 경로를 두지 않는다.
- 2026-08-27: LlamaIndex raw generation token은 HTTP와 직결하지 않고 문장별 grounding을 통과한 summary,
  section, checklist domain event만 공개한다.
- 2026-08-27: route·검색·생성·grounding의 복구 가능 오류는 요청별 `PipelineIssueCollector`에 누적하고
  `FinalAnswerCoordinator` 하나가 검증된 부분 답변, 제한 답변, 결정적 fallback을 선택한다. fatal·취소·
  admission 거부는 법률 답변으로 위장하지 않는다.
- 2026-08-27: 로컬 bounded 코드에는 개별 timeout을 두지 않고, 52초 요청 deadline 안에서 LLM·원격
  embedding과 DB·HTTP 외부 대기 경계만 제한한다. 100명 동시접속은 주입된 limiter, 1초 admission 대기,
  2초 이내 `503 system_busy`와 부하 검증 계약으로 다룬다.
- 2026-08-27: human-in-the-loop, realtime/attachment tool, agent workflow와 generation별 HNSW
  성능평가는 다음 목표로 분리한다.
