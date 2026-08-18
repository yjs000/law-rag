# LlamaIndex 기반 검색 파이프라인 (Phase 1) 설계

상태: 제안됨 (2026-08-18)
결정일: 2026-08-18

## 배경

기존 검색 파이프라인(`apps/api`의 NVIDIA NIM embedder + `provision_embeddings` +
`embedding_profiles` 계약 + dense/keyword fallback SQL)은 [검색 인덱스·임베딩 계보
설계](retrieval-index-storage.md)에 정의된 매우 엄격한 불변조건(HNSW 영구 금지, exact
cosine, 동적 `corpus_snapshot` 게이트, A/B 트랜잭션 무중단 반영 프로토콜 등) 위에서
동작한다.

사용자는 LangChain/LangGraph 기반 에이전트로 서비스를 확장하려 하며, 그 첫 단계로
"클린하고 이미 완성된" 임베딩·검색 코드를 쓰기 위해 LlamaIndex로 검색 파이프라인을
새로 만들기로 했다. 기존 파이프라인의 세부 불변조건(계약 테이블, 게이트 프로토콜,
direct-path·keyword fallback)은 이번 신규 파이프라인에 그대로 이식하지 않고, 기존
코드는 손대지 않은 채 legacy로 유지한다. 병행 운영하며 신규 파이프라인을 검증한다.

## 전체 로드맵 (참고용 — 각 단계는 별도 브레인스토밍·spec)

| 단계 | 내용 | 상태 |
|---|---|---|
| **1** | LlamaIndex 기반 검색 파이프라인 교체 (`law-rag-llamaindex` + `/v2/search`) | **이 문서의 범위** |
| 2 | LangGraph 워크플로우 설계 — 대화 컨텍스트 영속화(Supabase 체크포인터), `clarification_required` interrupt 처리, realtime 웹검색 도구 | 별도 spec ([0047](../exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md)과 연계) |
| 3 | 1+2 통합 테스트 — LangGraph 에이전트가 phase 1 산출물을 검색 도구로 호출하는 end-to-end 검증 | 별도 spec |
| 4 | UI/UX 연결 및 세부 오류 케이스 테스트 — web이 실제로 v2/에이전트 경로를 사용하도록 전환 | 별도 spec |
| 5 | RAG 성능 평가 및 BM25 등 검색기 도입 검토 — phase 1의 dense-only 결과를 실측한 뒤 필요성이 입증되면 추가 | 별도 spec |

이 문서는 로드맵의 1단계만 확정 설계한다. 2~5단계는 이 문서가 끝난 뒤 각각 새 브레인스토밍
세션에서 별도로 다룬다.

## 목표

- 기존 `provisions` 테이블을 입력으로 하는 LlamaIndex 기반 검색 파이프라인을 새 uv
  workspace 프로젝트(`law-rag-llamaindex`)로 만든다.
- `apps/api`에 `/v2/search` 엔드포인트를 추가해 이 파이프라인을 노출한다.
- 기존 `/v1/*` 경로, `provision_embeddings`, `embedding_profiles`, collector는 전혀
  수정하지 않는다(legacy로 완전 보존, 병행 운영).
- 인용 위치(조·항·호·목 경로 + 법령명)와 기준일 시간 유효성 필터링은 새 파이프라인에서도
  기능 요구사항으로 유지한다(구현 메커니즘은 새로 설계).

## 비범위

- AI 답변 생성·인용 검증(로드맵 2~3단계에서 LangGraph 에이전트가 담당)
- direct-path 법령명+조문 직접 조회, PGroonga keyword fallback(이번 spec은 dense-only)
- 레거시의 계약 테이블(`embedding_profiles`) 방식 재현, A/B 65초 drain 무중단 반영
  프로토콜 재현
- `/v2/search`의 로그인·quota 적용(v1 현재 기본값과 동일하게 미적용 — `account_quota_enabled`
  기본 `False`인 현재 상태를 따름)
- BM25 등 다른 검색기 도입(로드맵 5단계)
- collector·수집 로직 변경

## 아키텍처

```text
apps/law-rag-llamaindex/  (신규 uv workspace 앱, 독립 pyproject.toml)
├─ ingest.py     provisions(+document_versions, legal_documents) 읽기
│                 → LlamaIndex Document/TextNode → NVIDIA NIM 임베딩(passage)
│                 → PGVectorStore 적재
└─ retriever.py  질의 임베딩(query) → 메타데이터 필터 → cosine top-k → SearchHit 매핑

apps/api/
└─ /v2/search    law-rag-llamaindex를 워크스페이스 의존성으로 호출, SearchHit 그대로 반환

apps/web/
└─ 기존 검색 결과 렌더링 재사용 + v2 호출용 개발자 토글(사용자 노출 기능 아님)
```

새 워크스페이스는 `apps/api`, `apps/collector`, `packages/law-rag-core`와 별개의 uv
workspace 멤버로 `pyproject.toml`의 `[tool.uv.workspace] members`에 추가한다. 의존성은
`apps/api`와 완전히 분리되어 있어 LlamaIndex·LangChain 계열 패키지가 legacy 서비스에
영향을 주지 않는다.

## 데이터 모델과 Ingestion

**입력**: `provisions` + `document_versions` + `legal_documents` JOIN으로 다음 필드를
읽기 전용으로 조회한다(기존 스키마 변경 없음).

```text
provision_id, document_id, document_title, source_kind, version_label,
effective_from, effective_to, path, heading, content, source_url, law_type_code
```

**Passage 템플릿**: 기존 `legal-provision-v1`과 동일하게 빈 값을 제외하고 다음을
줄바꿈으로 결합한다.

```text
법령명
조·항·호·목 경로
표제
원문 본문
```

**임베딩**: LlamaIndex의 NVIDIA embedding 통합으로 `nvidia/nemotron-3-embed-1b`를
호출한다. ingestion 시 `input_type=passage`, 질의 시 `input_type=query`. 저장 차원은
NIM이 반환하는 네이티브 차원을 그대로 쓴다(레거시의 2048→512 축약 + L2 재정규화는
가져오지 않는다 — 더 단순하며, 성능·비용 문제가 실측되면 후속 spec에서 축약을 추가한다).

**저장**: LlamaIndex `PGVectorStore`를 같은 Supabase Postgres 인스턴스에 연결한다.
`hnsw_kwargs`를 지정하지 않아 인덱스 없는 테이블로 생성되며, 결과적으로 exact
brute-force cosine 검색이 된다(레거시의 "HNSW 금지" 규칙을 따른 것이 아니라 새로 고른
구현이 우연히 같은 특성을 갖는 것 — 이 신규 파이프라인은 레거시 규칙에 구속되지 않는다).

**재실행 최적화**: 노드 id로 `provision_id`를 쓰고, 메타데이터에 `source_text_sha256`
(passage 템플릿 전체의 SHA-256)을 저장한다. 재실행 시 해시가 같은 조문은 재임베딩을
건너뛴다(레거시와 같은 절약 아이디어를 새 코드로 재구현).

**준비 상태**: `law_rag_llamaindex_ingestion_runs` 테이블(id, started_at, finished_at,
node_count, status)에 완료 여부만 기록하는 단순 완료 마커. 레거시의 A/B 트랜잭션·65초
drain 프로토콜은 재현하지 않는다 — 이 파이프라인은 아직 답변 생성에 쓰이지 않아
무중단 반영의 긴급성이 낮다. 완료된 run이 하나도 없으면 `/v2/search`는 검색을 수행하지
않고 HTTP 503을 반환한다.

## 조회 인터페이스

`law_rag_llamaindex.retriever.search(query: str, as_of_date: date, limit: int) ->
list[SearchHit]`:

1. 질의를 `input_type=query`로 임베딩한다.
2. LlamaIndex 리트리버에 메타데이터 필터를 건다: `effective_from <= as_of_date` AND
   (`effective_to IS NULL` OR `effective_to > as_of_date`).
3. cosine 유사도 top-`limit` 노드를 가져온다.
4. 각 노드의 메타데이터를 `law_rag_core.domain.schemas.SearchHit`으로 매핑한다
   (`score`는 노드 유사도 점수).

`SearchHit`, `SearchRequest`는 `law_rag_core`(기존 공유 패키지)의 정의를 그대로
재사용한다 — 새 스키마를 따로 만들지 않는다.

## API (`apps/api`)

```text
POST /v2/search
  request:  SearchRequest (query, as_of_date, limit, source_kinds)
  response: list[SearchHit]
```

- `law-rag-llamaindex`를 `apps/api`의 uv workspace 의존성으로 추가하고, 새 라우트
  핸들러가 `retriever.search(...)`를 직접 호출한다.
- 로그인·quota 검사는 하지 않는다(v1의 현재 기본 동작 — `account_quota_enabled=False`
  — 과 동일).
- 준비 마커가 없으면 안정 코드로 HTTP 503을 반환한다(코드명은 구현 시 확정, 예:
  `llamaindex_index_not_ready`).
- `/v1/*`는 이 작업으로 전혀 수정하지 않는다.

## Web (`apps/web`)

기존 검색 결과 렌더링 컴포넌트는 변경하지 않는다(`SearchHit` 스키마가 동일하므로).
`/v2/search`를 호출할 수 있는 개발자용 토글(예: 쿼리 파라미터 또는 로컬 설정)만
추가한다 — 사용자에게 노출되는 신규 기능이 아니라 phase 1 산출물을 수동으로
확인·비교하기 위한 것이다.

## 테스트

- `law-rag-llamaindex`:
  - ingestion 매핑 단위 테스트(provisions row → Document/Node, passage 템플릿 결합
    순서·빈 값 제외, 해시 스킵 로직)
  - retriever 단위 테스트(기준일 유효성 필터 정확성 — 폐지·개정 법령이 올바르게
    제외/포함되는 경계 케이스 포함, `SearchHit` 매핑 필드 정확성)
- `apps/api`:
  - `/v2/search` 계약 테스트(정상 응답 스키마, ingestion 미완료 시 503)
- 검증 명령(구현 단계에서 최종 확정):
  ```powershell
  uv run --directory apps/law-rag-llamaindex pytest
  uv run --directory apps/api pytest -k v2
  ```

## 결정 기록

- 2026-08-18: LlamaIndex는 인터페이스·인터그레이션(문서 로딩, 임베딩 호출, 벡터스토어)
  용도로 채택하고, 레거시의 계약 테이블·게이트 프로토콜·direct-path·keyword fallback은
  이식하지 않기로 했다. 새 파이프라인은 레거시 불변조건에 구속되지 않는 독립 시스템으로
  취급한다.
- 2026-08-18: 입력은 collector가 이미 정규화한 `provisions` 테이블을 재사용한다(수집·파싱
  재구축 안 함).
- 2026-08-18: 인용 경로(조·항·호·목)와 기준일 시간 유효성 필터링은 구현 메커니즘과
  무관하게 기능 요구사항으로 유지한다(법률 도메인 불변조건).
- 2026-08-18: 임베딩 passage 템플릿(`법령명\n경로\n표제\n원문`)은 레거시와 동일하게
  유지해 검색 품질 저하를 방지한다.
- 2026-08-18: 임베딩 저장 차원은 네이티브 차원 그대로 쓰고 512 축약은 하지 않는다
  (단순화, 필요시 후속 추가).
- 2026-08-18: `/v2/search`는 dense-only이며 direct-path·keyword fallback은 이번 spec
  범위 밖이다.
- 2026-08-18: `/v2/search`는 v1의 현재 기본 동작과 동일하게 로그인·quota를 적용하지
  않는다.
- 2026-08-18: 새 파이프라인은 `apps/api`와 독립된 uv workspace 앱
  (`apps/law-rag-llamaindex`, 패키지명 `law-rag-llamaindex`)으로 만든다.

## 미결정

- `/v2/search`의 503 안정 코드명 확정
- ingestion CLI의 정확한 명령·옵션 형태(실행 계획 단계에서 확정)
- LlamaIndex `PGVectorStore`가 생성하는 실제 테이블명(라이브러리 기본 명명 규칙 확인 필요)
