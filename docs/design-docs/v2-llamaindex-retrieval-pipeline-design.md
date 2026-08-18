# V2: LlamaIndex 기반 검색 파이프라인 (Phase 1) 설계

상태: 구현 중 (2026-08-18)
결정일: 2026-08-18

## 배경

법령 검색 시스템에는 이제 v1(기존 운영 파이프라인)과 v2(이 문서에서 새로 만드는
파이프라인) 두 버전이 병행 존재한다. 각 버전은 독립적으로 설계·운영되며, 다른 버전의
규칙·계약에 구속되지 않는다. 서로를 참고하는 건 실제로 공유하는 지점(같은 입력
테이블, 같은 임베딩 모델, 같은 응답 스키마처럼 재사용을 택한 부분)에 한정한다.

v2를 만드는 이유: LangChain/LangGraph 기반 에이전트로 서비스를 확장하기 위해,
"클린하고 이미 완성된" 임베딩·검색 코드를 LlamaIndex로 새로 짠다. v1은 손대지 않고
그대로 legacy로 남는다.

## 전체 로드맵 (참고용 — 각 단계는 별도 브레인스토밍·spec)

| 단계 | 내용 | 상태 |
|---|---|---|
| **1** | v2 검색 파이프라인 구축 (`law-rag-llamaindex` + `/v2/search` + `/v2/questions`) | **이 문서의 범위** |
| 2 | LangGraph 워크플로우 설계 — 대화 컨텍스트 영속화(Supabase 체크포인터), `clarification_required` interrupt 처리, realtime 웹검색 도구 | 별도 spec ([0047](../exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md)과 연계) |
| 3 | 1+2 통합 테스트 — LangGraph 에이전트가 v2를 검색 도구로 호출하는 end-to-end 검증 | 별도 spec |
| 4 | UI/UX 연결 및 세부 오류 케이스 테스트 — web이 실제로 v2/에이전트 경로를 사용하도록 전환 | 별도 spec |
| 5 | RAG 성능 평가 및 BM25 등 검색기 도입 검토 — v2의 dense-only 결과를 실측한 뒤 필요성이 입증되면 추가 | 별도 spec |

이 문서는 로드맵의 1단계, 즉 v2만 확정 설계한다. 2~5단계는 이 문서가 끝난 뒤 각각 새
브레인스토밍 세션에서 별도로 다룬다.

## v1 요약 (참고용, 변경 없음)

이 절은 v2 설계자가 필요할 때만 찾아보는 배경 정보다. v1은 이 작업으로 전혀 수정하지
않으며, v2는 아래 내용을 따를 의무가 없다.

- 위치: `apps/api`(NVIDIA NIM embedder, `/v1/search`, `/v1/questions`), collector
- 저장: Postgres `provision_embeddings` + `embedding_profiles` 계약 테이블
- 검색: dense-only exact cosine(HNSW 영구 금지) + PGroonga keyword fallback +
  direct-path 조문 조회
- 반영: `corpus.search_ready` 게이트, A/B 트랜잭션 + 65초 drain 무중단 반영 프로토콜
- 전체 설계는 [검색 인덱스와 임베딩 계보](retrieval-index-storage.md) 참고

## v2 설계

### 목표

- `provisions` 테이블(v1과 공유하는 입력 데이터)을 읽어 LlamaIndex 기반 검색
  파이프라인을 새 uv workspace 프로젝트(`law-rag-llamaindex`)로 만든다.
- `apps/api`에 `/v2/search`(단독 검색, 디버그·후속 도구화용)와 `/v2/questions`(v1과
  동일한 질문 응답 엔드포인트, 근거 검색만 v2로 교체)를 추가한다.
- `/v2/questions`는 v1의 라우팅·AI 답변 생성·인용 검증 로직을 전혀 새로 만들지 않고
  그대로 재사용한다 — 바뀌는 건 근거를 가져오는 검색 단계 하나뿐이다.
- 인용 위치(조·항·호·목 경로 + 법령명)와 기준일 시간 유효성 필터링을 기능 요구사항으로
  갖는다(법률 도메인 불변조건 — 검색 자체의 구현 메커니즘은 v2가 독자적으로 설계).

### 비범위

- AI 답변 생성·인용 검증 로직 자체를 새로 작성하는 것(v1의 기존 코드를 그대로 재사용)
- `search_only`(순수 키워드 매칭) 모드를 v2로 이식하는 것 — 현재 `apps/web`이 이
  모드를 실제로 요청하지 않으므로 v2 범위에서 뺀다. v1에는 그대로 남는다.
- direct-path 법령명+조문 직접 조회, PGroonga keyword fallback(v2 검색 자체는
  dense-only)
- v2 전용 quota 제한(v1과 동일하게 이번 spec에서는 적용하지 않음 — `account_quota_enabled`
  기본값을 그대로 따름)
- BM25 등 다른 검색기 도입(로드맵 5단계)
- collector·수집 로직 변경, v1 코드 변경(단, `/v2/questions`가 v1의 함수를 호출하는
  건 변경이 아니라 재사용이다)

### 아키텍처

```text
apps/law-rag-llamaindex/  (신규 uv workspace 앱, 독립 pyproject.toml)
├─ ingest.py     provisions(+document_versions, legal_documents) 읽기
│                 → LlamaIndex Document/TextNode → NVIDIA NIM 임베딩(passage)
│                 → PGVectorStore 적재
└─ retriever.py  질의 임베딩(query) → 메타데이터 필터 → cosine top-k → SearchHit 매핑

apps/api/
├─ /v2/search      law-rag-llamaindex를 직접 호출, SearchHit 그대로 반환(단독,
│                   지금은 web이 호출하지 않는 디버그·후속 도구화용 엔드포인트)
├─ LlamaIndexLegalRepository  기존 LegalRepository Protocol을 구현하는 새 adapter.
│   search/search_with_trace만 law-rag-llamaindex로 새로 구현하고, 나머지 메서드
│   (consume_quota, corpus_temporal_state, provision, last_sync 등)는 기존
│   PostgresLegalRepository 인스턴스에 그대로 위임한다.
└─ /v2/questions   v1의 `_answer_question`과 완전히 같은 라우팅·생성·검증 코드를
                    호출하되, evidence 검색에 쓰는 repository만
                    LlamaIndexLegalRepository로 바꿔서 실행한다.

apps/web/
└─ /v1/questions 호출을 /v2/questions로 전환(search_only 전용 화면은 원래 없었음)
```

새 워크스페이스(`law-rag-llamaindex`)는 `apps/api`, `apps/collector`,
`packages/law-rag-core`와 별개의 uv workspace 멤버로 `pyproject.toml`의
`[tool.uv.workspace] members`에 추가한다. 의존성은 `apps/api`와 완전히 분리되어 있어
LlamaIndex·LangChain 계열 패키지가 v1 서비스에 영향을 주지 않는다.

`LlamaIndexLegalRepository`는 `apps/api`(v1 코드가 있는 곳) 안에 두는 adapter다 —
`law_rag_core.ports.repository.LegalRepository` Protocol을 구현하며, 생성자로 기존
`PostgresLegalRepository` 인스턴스(`delegate`)와 law-rag-llamaindex의 vector
store·embedder를 받는다. 이 protocol이 이미 ports/adapters 경계로 설계돼 있어서, v1의
`_answer_question`/`_retrieve_question_evidence` 등 애플리케이션 로직은 어떤
repository 구현체가 주입됐는지 몰라도 동작한다 — `/v2/questions`는 이 코드를 전혀
복제하지 않고, repository 주입만 바꿔서 호출한다.

### 데이터 모델과 Ingestion

**입력**: `provisions` + `document_versions` + `legal_documents` JOIN으로 다음 필드를
읽기 전용으로 조회한다(v1과 같은 테이블을 공유 입력으로 재사용 — 스키마 변경 없음).

```text
provision_id, document_id, document_title, source_kind, version_label,
effective_from, effective_to, path, heading, content, source_url, law_type_code
```

이 필드들은 노드의 `text`(임베딩 입력, 아래 passage 템플릿)와 별개로 노드
`metadata`에 원본 그대로 저장한다. 즉 `content`는 조문 원문만 담고, 임베딩용으로
결합된 문자열은 `text`에만 들어간다 — 조회 시 두 값이 섞이거나 원본 필드가 유실되지
않는다.

**Passage 템플릿**: 빈 값을 제외하고 다음을 줄바꿈으로 결합한다(검색 품질을 위해 v1과
같은 조합을 v2가 독자적으로 채택).

```text
법령명
조·항·호·목 경로
표제
원문 본문
```

**임베딩**: LlamaIndex의 NVIDIA embedding 통합으로 `nvidia/nemotron-3-embed-1b`를
호출한다(같은 provider·모델을 v2가 독자적으로 채택). ingestion 시
`input_type=passage`, 질의 시 `input_type=query`. 저장 차원은 NIM이 반환하는 네이티브
차원을 그대로 쓴다(축약·재정규화 없음 — 단순한 기본값이며, 성능·비용 문제가 실측되면
후속 spec에서 조정한다).

**저장**: LlamaIndex `PGVectorStore`를 같은 Supabase Postgres 인스턴스에 연결한다.
LlamaIndex 소스 확인 결과 `hnsw_kwargs`의 실제 라이브러리 기본값은 `None`이며, 이
경우 HNSW 인덱스를 만들지 않고 brute-force exact 검색을 한다. 이번 spec은 이 기본값
그대로 `hnsw_kwargs`를 넘기지 않는다(HNSW 미사용). 다만 vector store 생성 함수는
`hnsw_kwargs` 파라미터를 받아들이는 형태로 만들어, 값을 필요할 때(로드맵 5단계 성능
평가 이후) 한 줄만 바꿔 HNSW를 켤 수 있게 준비해 둔다. v1의 "HNSW 영구 금지" 규칙은
v2에 적용되지 않는다 — v2가 HNSW를 미사용하는 건 규칙이 아니라 현재 선택일 뿐이다.

**재실행 최적화**: 노드 id로 `provision_id`를 쓰고, 메타데이터에 `source_text_sha256`
(passage 템플릿 전체의 SHA-256)을 저장한다. 재실행 시 해시가 같은 조문은 재임베딩을
건너뛴다.

**준비 상태**: `law_rag_llamaindex_ingestion_runs` 테이블(id, started_at, finished_at,
node_count, status)에 완료 여부만 기록하는 단순 완료 마커. 완료된 run이 하나도 없으면
`/v2/search`는 검색을 수행하지 않고 HTTP 503을 반환한다.

### 조회 인터페이스

`law_rag_llamaindex.retriever.search(query: str, as_of_date: date, limit: int) ->
list[SearchHit]`:

1. 질의를 `input_type=query`로 임베딩한다.
2. LlamaIndex 리트리버에 메타데이터 필터를 건다: `effective_from <= as_of_date` AND
   (`effective_to IS NULL` OR `effective_to > as_of_date`).
3. cosine 유사도 top-`limit` 노드를 가져온다.
4. 각 노드의 메타데이터를 `law_rag_core.domain.schemas.SearchHit`으로 매핑한다
   (`score`는 노드 유사도 점수).

`SearchHit`, `SearchRequest`는 `law_rag_core`(v1·v2 공유 패키지)의 정의를 그대로
재사용한다 — 새 스키마를 따로 만들지 않는다. 매핑은 ingestion 시 metadata에 저장한
원본 필드(위 "데이터 모델과 Ingestion" 참고)를 1:1로 옮기는 것이라 정보 손실이 없다.
LlamaIndex 노드가 추가로 갖는 내부 필드(`node_id`, `relationships`,
`start_char_idx`/`end_char_idx` 등)는 `SearchHit`이 요구하는 조문 정보가 아니므로
매핑에서 제외하되, 필요해지면 후속 spec에서 `SearchHit`을 확장하거나 별도 필드로
노출한다.

### API (`apps/api`)

```text
POST /v2/search
  request:  SearchRequest (query, as_of_date, limit, source_kinds)
  response: list[SearchHit]

POST /v2/questions
  request:  QuestionRequest  (v1과 동일 스키마)
  response: QuestionResponse (v1과 동일 스키마)
```

- **`/v2/search`**: `law-rag-llamaindex`의 `retriever.search(...)`를 직접 호출한다.
  v1의 `/v1/search`처럼 인증·quota를 요구하지 않는다. 지금은 `apps/web`이 호출하지
  않는 단독 엔드포인트다(디버그, 후속 spec에서 도구화할 때 대비). 준비 마커가 없으면
  HTTP 503, 안정 코드 `v2_search_not_ready`를 반환한다.
- **`/v2/questions`**: 핸들러 본문은 v1의 `_answer_question` 로직을 그대로 호출하되,
  그 함수가 쓰는 `repository`를 `LlamaIndexLegalRepository`(위 아키텍처 참고)로
  바꿔서 실행한다. 인증·quota·이력 저장·라우팅·생성·검증·오류 처리 전부 v1과 동일한
  코드 경로다 — 새로 구현하는 부분이 없다.
- `/v1/*`는 이 작업으로 전혀 수정하지 않는다.

### 인증과 이력

- `/v2/search`는 v1의 `/v1/search`와 동일하게 인증을 요구하지 않고, 이력도 저장하지
  않는다(단독·디버그용이므로).
- `/v2/questions`는 인증·quota·이력 저장을 전부 v1의 기존 메커니즘 그대로 쓴다 —
  `_optional_user`로 로그인 여부를 확인하고, 로그인 사용자의 질문·답변은 기존
  `postgres_identity.save_question`으로 `question_history`에 저장한다. v2 전용 로그
  테이블이나 별도 이력 조회 엔드포인트는 만들지 않는다.

### Web (`apps/web`)

`/v1/questions` 호출을 `/v2/questions`로 전환한다. 요청·응답 스키마가 동일하므로
기존 채팅 UI 컴포넌트는 변경하지 않는다. `search_only` 모드를 사용자가 명시적으로
선택하는 진입점은 원래 없었으므로 web 쪽에서 추가로 고려할 게 없다.

### 테스트

- `law-rag-llamaindex`:
  - ingestion 매핑 단위 테스트(provisions row → Document/Node, passage 템플릿 결합
    순서·빈 값 제외, 해시 스킵 로직)
  - retriever 단위 테스트(기준일 유효성 필터 정확성 — 폐지·개정 법령이 올바르게
    제외/포함되는 경계 케이스 포함, `SearchHit` 매핑 필드 정확성)
- `apps/api`:
  - `/v2/search` 계약 테스트(정상 응답 스키마, ingestion 미완료 시 503)
  - `LlamaIndexLegalRepository`가 `search`/`search_with_trace`만 오버라이드하고
    나머지 메서드는 delegate로 위임하는지에 대한 단위 테스트
  - `/v2/questions`가 v1과 같은 인증·이력 저장 동작을 하는지에 대한 계약 테스트
    (로그인 시 `question_history`에 저장, 익명은 저장 안 함 — v1과 동일 기준)
- 검증 명령(구현 단계에서 최종 확정):
  ```powershell
  uv run --directory apps/law-rag-llamaindex pytest
  uv run --directory apps/api pytest -k v2
  ```

## 결정 기록

- 2026-08-18: v1과 v2는 각각 독립적으로 설계·운영하며, 서로 다른 버전의 규칙에
  구속되지 않는다. 참고는 실제로 공유하는 지점(입력 테이블, 임베딩 모델, 응답
  스키마)에서만 한다.
- 2026-08-18: v2의 입력은 v1과 같은 `provisions` 테이블을 재사용한다(수집·파싱
  재구축 안 함).
- 2026-08-18: 인용 경로(조·항·호·목)와 기준일 시간 유효성 필터링은 v1·v2 공통으로
  기능 요구사항이다(구현 메커니즘은 각자 독자적).
- 2026-08-18: v2의 임베딩 passage 템플릿(`법령명\n경로\n표제\n원문`)은 검색 품질을
  위해 v1과 같은 조합을 채택한다.
- 2026-08-18: v2의 임베딩 저장 차원은 네이티브 차원 그대로 쓰고 축약하지 않는다.
- 2026-08-18: v2의 `/v2/search`는 dense-only이며 direct-path·keyword fallback은 이번
  spec 범위 밖이다.
- 2026-08-18: v2는 `apps/api`와 독립된 uv workspace 앱(`apps/law-rag-llamaindex`,
  패키지명 `law-rag-llamaindex`)으로 만든다.
- 2026-08-18: (정정, 최초 결정을 대체) LlamaIndex `PGVectorStore`의 실제 기본값은
  `hnsw_kwargs=None` → HNSW 미생성(brute-force exact)이다. v2는 이번 spec에서 이
  기본값 그대로 HNSW를 쓰지 않되, vector store 생성 함수가 `hnsw_kwargs`를 받아 나중에
  한 줄로 켤 수 있게 준비해 둔다. v1의 HNSW 영구 금지 규칙은 v2에 적용하지 않는다 —
  v2의 HNSW 미사용은 규칙이 아니라 현재 선택이다.
- 2026-08-18: node→`SearchHit` 매핑은 ingestion 시 metadata에 저장한 원본 필드를
  1:1로 옮기며, 임베딩용 결합 텍스트(`text`)와 원본 `content`를 분리 보관해 정보
  손실을 막는다.
- 2026-08-18: `/v2/search`는 v1의 `/v1/search`와 동일하게 인증·quota·이력 저장이
  없는 단독 엔드포인트다. 지금은 `apps/web`이 호출하지 않는다.
- 2026-08-18: `/v2/search`의 준비 미완료 안정 코드는 `v2_search_not_ready`로 확정한다.
- 2026-08-18: (범위 재조정) `search_only` 모드는 v2로 이식하지 않는다 —
  `apps/web`이 실제로 요청하지 않는 모드이기 때문이다. 대신 `/v2/questions`를
  추가해 v1의 `_answer_question`(라우팅·AI 답변 생성·인용 검증·이력 저장)을 그대로
  재사용하고, evidence 검색에 쓰는 `repository`만 새 `LlamaIndexLegalRepository`
  adapter로 바꾼다. 이 adapter는 `LegalRepository` Protocol 중 `search`/
  `search_with_trace`만 v2로 새로 구현하고 나머지 메서드(quota, corpus 상태, 개별
  조문 조회, last_sync 등)는 기존 `PostgresLegalRepository` 인스턴스에 위임한다 —
  AI 생성·검증 코드 자체는 전혀 새로 만들지 않는다.
- 2026-08-18: `apps/web`은 `/v1/questions` 호출을 `/v2/questions`로 전환한다. 요청·
  응답 스키마가 v1과 동일하므로 채팅 UI 컴포넌트는 변경하지 않는다.
- 2026-08-18: `/v2/questions`의 인증·quota·이력 저장은 v1의 기존 메커니즘
  (`_optional_user`, `postgres_identity.save_question`)을 그대로 재사용한다. v2
  전용 로그 테이블이나 별도 이력 조회 엔드포인트는 만들지 않는다.

## 미결정

- ingestion CLI의 정확한 명령·옵션 형태(실행 계획 단계에서 확정)
- `LlamaIndexLegalRepository.search_with_trace`가 반환할 `SearchTrace`의 정확한 필드값
  (v1의 키워드 fallback 단계 계측과 그대로 맞출 수 없으므로 v2 dense 검색에 맞는
  간소화된 값을 실행 계획 단계에서 확정)

## 확정된 구현 세부사항 (검증 완료)

- LlamaIndex `PGVectorStore.from_params(table_name="law_rag_llamaindex", ...)`의
  실제 물리 테이블명은 `data_law_rag_llamaindex`다(라이브러리 소스 확인:
  `tablename = "data_%s" % index_name`). 노드 id는 `node_id` 컬럼(VARCHAR), 메타데이터는
  `metadata_` 컬럼(JSON/JSONB), 임베딩은 `embedding` 컬럼에 저장된다.
