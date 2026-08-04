# 검색 인덱스와 임베딩 계보 설계

상태: 구현 기준
결정일: 2026-08-03

## 결론

현재 주 검색 경로는 exhaustive exact dense다. dense 후보가 0개일 때만 PGroonga keyword fallback을 별도로 실행하며, 두 점수를 합치지 않는다. 두 경로는 현재 같은 repository의 내부 실행 단계이므로 독립적인 public retriever 계약이라고 부르지 않는다. DB는 `hybrid_search`와 RRF 함수를 제공하지 않는다. 향후 BM25는 독립 repository 계약과 profile로 추가하고, RRF·reranker는 고정 평가셋에서 이득을 증명한 뒤 별도 버전의 실험 계층에 추가한다. 운영 dense 검색과 실험 D는 기준일 유효 population을 먼저 `MATERIALIZED`한 exhaustive exact cosine만 사용한다. HNSW는 검토 대기 항목이 아니라 현재와 미래의 제품·실험 경로에서 제외된 방식이며, 새 인덱스·build·configuration·release를 설계하거나 만들지 않는다.

Migration `0011`은 이 동작을 바꾸지 않고 corpus·검색기·물리 build·configuration·release·평가 실행의 계보를 분리해 기록할 수 있는 additive catalog만 추가한다. catalog 행의 존재나 capability marker는 검색 방식의 구현·승인·활성화를 뜻하지 않으며, 현재 runtime은 이 catalog를 읽어 검색기를 선택하지 않는다.

## 해결하는 불일치

기존 DB에는 다음 문제가 있었다.

- 런타임은 dense-only인데 `hybrid_search` SQL 함수와 RRF가 현재 설계처럼 남아 있었다.
- 4인자와 5인자 함수가 마이그레이션 계보에서 동시에 존재할 수 있었다.
- `model`, `dimensions`, `embedding_version`만으로는 passage/query 입력 유형, 2048→512 축약, L2 재정규화, 임베딩 본문 형식을 재현할 수 없었다.
- `vector(512)` 고정 열과 모든 행을 아우르는 HNSW 인덱스는 다른 차원의 모델을 추가할 때 테이블 변경을 요구했다.
- 조문 본문이 바뀌었을 때 저장 벡터가 현재 입력으로 만들어졌는지 판별할 해시가 없었다.

## 임베딩 저장 데이터 모델 (`0008`)

```text
embedding_profiles
├─ profile_key                 검색 코드가 요구하는 고정 프로필 ID
├─ provider / model            제공자와 모델명
├─ native_dimensions           NIM 원본 차원: 2048
├─ stored_dimensions           저장·검색 차원: 512
├─ document_input_type         passage
├─ query_input_type            query
├─ truncation                  first_512
├─ normalization               l2
├─ text_template_version       legal-provision-v1
├─ profile_version             1
└─ active                      검증이 끝나 검색에 노출해도 되는 프로필인지

provision_embeddings
├─ provision_id                원문 조각 ID
├─ profile_key                 어떤 변환 계약의 벡터인지
├─ dimensions                  실제 저장 차원
├─ source_text_sha256          임베딩 입력 전체의 SHA-256
├─ embedding                   차원 가변 vector
└─ embedded_at                 마지막 생성 시각
```

DB는 `vector_dims(embedding)=dimensions`, 0이 아닌 norm, 프로필과 차원의 복합 외래키를 검사한다. 현재 프로필은 `nvidia-nemotron-3-embed-1b-512-v1`이다.

## 검색 계보 catalog (`0011`)

`0011_retrieval_catalog.py`는 기존 법령·임베딩·검색 준비 테이블을 수정하지 않고 다음 8개 테이블을 추가한다.

```text
corpus_snapshots
├─ snapshot_id                  corpus 세대의 안정 ID
├─ fingerprint_sha256           세대의 고유 SHA-256 지문
├─ parser_schema_version        파서 계약 버전
├─ supported_as_of_from         검색을 보장하는 시작 기준일
├─ supported_as_of_through      검색을 보장하는 마지막 기준일
├─ document_count               세대의 문서 수
├─ provision_count              세대의 검색 조각 수
└─ created_at

retrieval_profiles
├─ profile_key                  독립 검색 계약 ID
├─ retriever_kind               dense·keyword 같은 검색기 종류
├─ engine                       실제 계산 엔진
├─ implementation_version       구현 계약 버전
├─ configuration                검색기별 JSON 설정
├─ configuration_sha256         위 설정의 SHA-256
├─ embedding_profile_key        dense일 때 연결할 임베딩 계약, 선택값
└─ created_at

retrieval_index_builds
├─ build_id
├─ snapshot_id / profile_key    어떤 corpus와 검색 계약의 build인지
├─ state                        building | ready | failed | superseded
├─ expected_count / indexed_count
├─ artifact_fingerprint_sha256  완성 산출물 지문
├─ build_metadata / error_code
└─ started_at / finished_at

retrieval_configurations
├─ configuration_key
├─ strategy / configuration_version
├─ parameters / parameters_sha256
└─ created_at

retrieval_configuration_members
├─ configuration_key / profile_key
├─ role                         primary·fallback 등 구성 안의 역할
├─ ordinal                      실행 순서
└─ required                     release 실행에 반드시 참여해야 하는 member인지 표시

retrieval_releases
├─ release_key
├─ snapshot_id / configuration_key
├─ state                        draft | ready | retired
├─ manifest_sha256
└─ created_at / ready_at

retrieval_release_builds
├─ release_key / configuration_key / snapshot_id
└─ profile_key / build_id         같은 snapshot·profile의 구체적인 build 연결

active_retrieval_release
└─ ready 상태 release 하나만 가리킬 수 있는 singleton pointer
```

관계는 다음처럼 분리한다.

```text
corpus snapshot ─┬─ index build ─────────────┐
                 └─ release                  │
                                                ├─ release build
retrieval profile ─ configuration member ────┘
                          │
configuration ────────────┴─ release ── active pointer
```

DB는 SHA-256 형식, JSON object 형식, 날짜 순서, 음수가 아닌 count, build·release 상태별 완료 시각, ready build의 전체 count와 산출물 지문을 검사한다. configuration member는 configuration 안에서 profile과 ordinal이 각각 중복되지 않는다. release build는 해당 configuration member와 같은 profile이며 release와 같은 snapshot인 build만 연결할 수 있고, active pointer는 `ready` release만 가리킨다. `required=true` member와 물리 build 필요 여부를 해석하고 release를 ready로 승격하는 catalog writer는 이번 migration에 포함하지 않는다.

`evaluation_runs`에는 `dataset_sha256`, `code_sha256`, `corpus_snapshot_id`, `retrieval_release_key`, `run_metadata`가 추가된다. 기존 행과 현재 평가 runner의 호환성을 위해 새 계보 열은 nullable이다. release key를 기록하면 snapshot도 반드시 있어야 하고, 복합 외래키가 평가 snapshot과 release snapshot의 일치를 검사한다. 실제 비교 가능한 평가를 게시하는 writer는 dataset·code·snapshot·release를 함께 기록해야 한다. release가 configuration을 가리키므로 평가 행에서 검색 조합까지 역추적할 수 있다.

마이그레이션은 catalog의 빈 구조와 `runtime_flags['schema.retrieval_catalog_v1']` capability marker만 설치한다. 현재 corpus, exact dense, keyword fallback이나 역사적 HNSW를 catalog 행으로 자동 추정해 seed하지 않는다. 특히 `active_retrieval_release`가 비어 있어도 현재 runtime의 `corpus.search_ready`와 `embedding_profiles.active` 계약은 그대로 동작한다. catalog 기반 승격 writer와 runtime 선택은 별도 설계·검증 대상이다. snapshot·profile·configuration·release ID는 내용을 바꾸지 않고 새 세대를 추가하는 append-only 계보로 다뤄야 하지만, 이번 migration은 UPDATE를 막는 writer나 권한 정책을 구현하지 않는다.

## passage 입력 계약

`legal-provision-v1`은 빈 값을 제외하고 다음을 줄바꿈으로 결합한다.

```text
법령명
조·항·호·목 경로
표제
원문 본문
```

이 전체 문자열의 SHA-256을 벡터 행에 저장한다. backfill 재실행 시 해시가 같으면 API를 호출하지 않고, 없거나 다르면 새 passage 벡터를 생성한다. 질문은 같은 모델·축약·정규화를 사용하되 NIM `input_type=query`로 생성한다.

## 부분 corpus와 낡은 벡터 노출 방지

`runtime_flags['corpus.search_ready']`는 모델과 무관한 전체 검색 준비 게이트다. runtime은 migration 0010만 설치하는 `schema.corpus_search_ready_v1.enabled=true` capability marker와 `corpus.search_ready=true`를 모두 요구한다. direct path, keyword fallback, dense, 단일 조문 조회는 두 조건을 만족할 때만 결과를 읽는다. collector가 검색 결과를 바꿀 데이터를 commit할 때 같은 transaction에서 준비 값을 `false`로 만들고, 전체 corpus와 벡터·인덱스 검증이 성공한 마지막 transaction에서만 다시 `true`로 만든다. 따라서 여러 법령이 차례로 commit되어도 중간 세대는 어느 retrieval 경로에서도 노출되지 않는다.

게이트가 없거나 닫혀 있으면 runtime은 빈 검색 결과나 `insufficient_evidence`로 가장하지 않고 HTTP `503`과 안정 코드 `corpus_unready`를 반환한다. `/v1/corpus/status`는 `corpus_search_ready`와 닫힌 사유를 별도로 노출한다. 실제 질문에 맞는 근거가 없는 상태와 운영 갱신 중인 상태를 이 경계로 구분한다.

`embedding_profiles.active`는 단순 설정값이 아니라 검색 준비 게이트다. dense SQL은 다음 조건을 모두 만족하는 행만 읽는다.

- 프로필이 `active=true`다.
- 프로필의 본문 템플릿이 `legal-provision-v1`이다.
- 저장된 `source_text_sha256`가 현재 법령명·경로·표제·본문으로 다시 계산한 SHA-256과 같다.
- 버전의 `source_record_state='available'`이다.
- 버전의 `lifecycle_state`가 `active` 또는 `scheduled`이거나, `abolished`이면서 검증된 `effective_to`가 있고 질의 기준일이 그 이전의 효력 구간 안에 있다.
- 버전의 파서 스키마가 현재 지원 버전인 `3`이다.

조문 직접 조회와 keyword fallback에도 전체 corpus 준비 게이트와 같은 버전 상태 조건을 적용한다. 출처에서 삭제되어 재검증할 수 없는 레코드는 검색 근거로 노출하지 않는다. 폐지 법령은 공식 종료일이 확인된 버전에 한해 폐지 전 기준일 검색을 허용하고, 종료일을 확인할 수 없는 폐지 레코드는 안전하게 격리한다.

collector와 벡터 writer는 `law_rag_core.persistence.CORPUS_MUTATION_LOCK_KEY`라는 같은 PostgreSQL transaction advisory lock을 사용한다. collector가 임베딩 입력에 영향을 주는 코퍼스를 바꾸기 전에는 같은 트랜잭션에서 활성 임베딩 프로필을 모두 `active=false`로 바꿔야 한다. API의 `PostgresLegalRepository.upsert_document`는 운영 writer가 아니므로 항상 실패하며, 검증된 collector만 법령 코퍼스를 쓸 수 있다.

여러 법령을 한 번에 갱신하는 collector CLI는 `CORPUS_SYNC_RUN_LOCK_KEY`를 전체 실행 동안 유지한다. 프로필 승격은 이 실행 잠금을 먼저, `CORPUS_MUTATION_LOCK_KEY`를 다음으로 획득한다. 따라서 9개 법령 중 일부만 파서 v3로 바뀐 중간 상태에서 profile을 다시 활성화할 수 없다. 벡터 batch 쓰기는 각 batch의 현재 SHA를 다시 확인하므로 수집과 겹치면 안전하게 실패하거나 최종 승격 검사에서 거부된다.

collector는 `pg_advisory_xact_lock(CORPUS_MUTATION_LOCK_KEY)` 아래에서 변경 여부를 계산하고, `corpus.search_ready=false`, 필요한 경우의 `embedding_profiles.active=false`, 코퍼스 변경을 같은 transaction에서 commit한다. SQL문의 내부 실행 순서와 무관하게 reader는 변경 전 상태 또는 변경된 corpus와 닫힌 게이트만 볼 수 있다. 활성 프로필이 없는 환경에서도 전체 corpus 게이트가 닫히므로 안전한 상태다.

벡터 batch upsert도 같은 lock을 잡은 뒤 모든 조문 ID와 현재 `legal-provision-v1` 해시를 검사한다. 하나라도 없어졌거나 해시가 달라졌으면 INSERT 전에 전체 batch를 실패시킨다. 이로써 임베딩 생성 중 원문이 바뀌어도 예전 벡터에 새 해시를 붙일 수 없다.

## 차원 가변 저장과 역사적 물리 인덱스

pgvector는 `vector` 타입으로 서로 다른 차원을 한 열에 저장할 수 있지만, 인덱스는 같은 차원의 행에만 만들어야 한다. migration `0008`은 당시 설계에 따라 현재 프로필용 expression + partial HNSW 인덱스를 설치했다.

> **역사 기록 전용 — 실행·재생성 금지:** 아래 SQL은 이미 적용된 migration의 내용을 설명하기 위한 기록이다. 현재 또는 미래 환경에서 실행하거나 HNSW 인덱스를 다시 만들기 위한 지침으로 사용하지 않는다.

```sql
CREATE INDEX provision_embeddings_nemotron_512_hnsw
ON provision_embeddings
USING hnsw ((embedding::vector(512)) vector_cosine_ops)
WHERE profile_key='nvidia-nemotron-3-embed-1b-512-v1';
```

현재 dense 쿼리는 같은 프로필과 차원 표현을 사용하되 거리 계산 CTE 안에 KNN `ORDER BY/LIMIT`를 두지 않아 물리 인덱스를 검색 경로로 사용하지 않는다. 위 SQL과 운영 DB의 물리 인덱스는 이미 만들어진 역사적 사실이므로 이번 문서 작업에서 삭제하지 않는다. 존재·valid·ready 여부를 운영 준비나 품질 통과 조건으로 사용하지 않고, 기존 인덱스를 사용·재구축·튜닝·평가·release 연결하지 않으며 새 HNSW 인덱스도 만들지 않는다. 기존 인덱스 제거는 별도 additive cleanup migration으로만 수행할 후속 운영 작업이다. [pgvector 공식 저장소](https://github.com/pgvector/pgvector)

### 물리 인덱스 존재와 현재 평가 계약은 다르다

기존 HNSW가 valid·ready였다는 기록은 특정 시점에 물리 구조가 설치됐다는 뜻일 뿐, 근거를 잘 찾는다는 증거가 아니다. PostgreSQL planner도 현재 3,066개 corpus와 법률·버전·기준일 join 조건에서는 전체 유효 행을 계산한 뒤 exact sort하는 계획을 선택했다.

실험 D는 문항별 기준일에 유효한 전체 population을 빠짐없이 비교하는 `MATERIALIZED` exhaustive exact cosine으로 고정한다. runner의 검색 상태·결과에는 HNSW identity, valid·ready 상태나 exact 대비 비교값을 넣지 않는다. exact 방식은 검색 대상 전체를 비교해 근사화 실패를 품질 원인에서 제거하며, HNSW 영구 제외 결정에 따라 gold 완성 뒤에도 이 비교 계약을 바꾸지 않는다.

## 현재 corpus의 기준일 지원 범위

현재 snapshot `mvp-current-corpus-2026-08-03`에는 9개 문서의 open version과 3,066개 조문이 있다. 이 문서들이 모두 존재하는 공통 지원 범위는 다음과 같이 하드코딩한다.

```text
2026-06-03 <= as_of_date <= 2026-08-03
```

두 경계일을 모두 포함한다. 과거 일부 문서만 남는 날짜를 검색해 빈 결과나 `insufficient_evidence`로 오인하지 않는다. `POST /v1/search`, `POST /v1/questions`, `GET /v1/provisions/{id}`는 범위 밖 날짜를 임베딩·repository 호출 전에 HTTP `422`, 코드 `unsupported_corpus_date`로 차단한다. `/v1/corpus/status`는 `corpus_snapshot_id`, `supported_as_of_from`, `supported_as_of_through`를 노출해 클라이언트가 같은 계약을 표시할 수 있게 한다. 법률 버전의 `effective_from/effective_to` 판정은 이 coverage gate를 통과한 뒤에만 적용한다.

## BM25 확장 경계

BM25는 벡터 프로필이 아니며 `provision_embeddings`에 저장하지 않는다. 향후 도입 순서는 다음과 같다.

1. BM25/lexical retriever가 독립 후보와 원점수를 반환한다.
2. dense-only와 같은 1,000문항 qrels로 Recall@k, MRR, nDCG@k, latency를 각각 비교한다.
3. 둘을 결합할 필요가 입증될 때만 application 계층에 버전 고정 fusion 전략을 추가한다.
4. 결합 결과에는 각 retriever의 순위·점수·버전과 fusion 버전을 trace로 남긴다.

따라서 확장 가능성은 지금 RRF를 미리 실행하는 것이 아니라, 검색기별 저장·실행·평가 경계를 분리해 교체 가능하게 하는 데서 확보한다.

`0011` catalog를 사용하는 후속 절차에서는 BM25를 먼저 독립 `retrieval_profile`로 등록하고, 특정 `corpus_snapshot`에 대한 build를 별도로 만든다. 기존 exact dense release와 같은 승인 gold로 평가한 `evaluation_run`을 비교한 뒤에만 새 configuration과 release 후보를 만들 수 있다. RRF가 필요하다는 결과가 나온 경우에도 별도 version의 configuration/profile로 추가하며 기존 dense release를 덮어쓰지 않는다. 이 절차를 실행하는 writer와 promotion command는 아직 구현하지 않았다.

## 운영 명령

DB 마이그레이션:

```powershell
uv run --directory apps/api alembic upgrade head
```

이 명령으로 `0011`까지 올리면 retrieval catalog schema와 capability marker가 추가된다. 임베딩 벡터를 생성·적재하거나 인덱스를 새로 구축하지 않으며, catalog 세대 행이나 active pointer도 만들지 않는다.

DB 상태 확인(0010 적용 후):

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings status
```

운영 DB를 바꾸지 않고 벡터를 로컬 체크포인트에 생성:

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings generate-cache --batch-size 32
uv run --directory apps/api python -m scripts.backfill_embeddings cache-status
```

0010 적용 후 완성된 체크포인트를 DB에 적재:

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings load-cache --batch-size 100
```

실제 query 임베딩과 dense-only 검색 확인:

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings verify `
  --query "태양광 발전 설비는 법에서 어떻게 정의하나요?" --limit 3
```

체크포인트는 `.data/embeddings/`의 Git 제외 JSONL이다. 원문은 넣지 않고 조각 ID, 프로필, 본문 입력 SHA-256, 512차원 L2 정규화 벡터만 저장한다. 배치마다 flush와 `fsync`를 수행하므로 중단 후 같은 `generate-cache` 명령을 실행하면 해시가 같은 벡터를 재사용한다. 파서 스키마 변경으로 조각 ID만 달라지고 프로필과 본문 SHA-256이 같아도 기존 벡터를 재사용하고, 새 ID의 별도 체크포인트 레코드를 남긴다. 본문이 바뀐 조각은 같은 파일 끝에 새 레코드를 추가하며 마지막 유효 레코드가 현재값이다.

`load-cache`는 체크포인트가 현재 검색 가능 corpus 전체와 일치하지 않거나 DB가 migration 0010 capability marker·전체 검색 준비 게이트·임베딩 스키마와 필수 프로필을 갖추지 않으면 적재를 거부한다. 단순히 같은 이름의 runtime flag 행이 존재하는지만으로 0010 적용을 추정하지 않는다. DB에 이미 현재 해시의 벡터가 있는 조문은 다시 쓰지 않고 누락되었거나 낡은 행만 적재한다. 기존 `run`은 NVIDIA 생성과 DB upsert를 한 번에 수행하는 운영 경로로 유지하지만, 마이그레이션과 외부 API 호출을 분리해야 할 때는 체크포인트 경로를 사용한다.

`run`과 `load-cache`는 첫 DB batch 전에 프로필을 비활성화한다. 현재 backfill은 모든 batch가 끝나면 같은 corpus mutation lock 안에서 다음을 한 번에 검사하고, 전부 통과할 때만 `active=true`로 승격한다.

1. 검색 가능한 모든 조문에 현재 원문 해시의 벡터가 있는가
2. 저장 차원이 프로필과 일치하는가
3. 모든 벡터의 L2 norm이 허용 오차 안에서 1인가
4. DB 프로필 계약이 런타임의 provider·모델·입력 유형·축약·정규화·템플릿 버전과 같은가

`status`와 `verify`의 `hnsw_ready`는 기존 물리 구조가 남아 있는지 보여 주는 레거시 진단값일 뿐 프로필 승격·exact 검색의 조건이 아니다. 이 값을 HNSW 도입 가능성이나 준비 상태로 해석하지 않는다. 기존 인덱스와 진단값의 제거는 별도 cleanup migration 대상이며, 제거 전에도 검색·평가·승격 경로에서는 계속 무시한다. 위 승격 검사 중 하나라도 실패하면 프로필은 inactive, `corpus.search_ready`는 false로 남는다. `verify`도 capability와 두 준비 게이트가 모두 열리지 않으면 dense 검색을 실행하지 않는다.

마이그레이션 `0009`는 기존 프로필을 먼저 비활성화한다. `0010`은 capability marker와 false인 전체 검색 준비 게이트를 같은 migration transaction에 설치한다. 파서 v3 재수집과 전체 벡터 검증이 끝나기 전에는 direct·keyword·dense 어느 경로도 중간 corpus를 노출하지 않는다.

운영 rollout 중에는 collector를 정지한 상태에서 gate-aware API 배포가 production에 완전히 전환됐는지 먼저 확인한다. 그 다음 0010을 적용하고 수집·backfill을 순서대로 실행한다. 구버전 API가 남아 있는 동안 collector를 시작하면 그 reader는 새 게이트를 모르므로 부분 corpus를 볼 수 있어 금지한다. 새 API를 먼저 배포하면 marker가 아직 없어 검색은 의도적으로 `503 corpus_unready`가 된다.

## 결정 기록

- 2026-08-03: DB의 고정 hybrid/RRF 함수를 제거하고 dense-only SQL을 repository에 명시했다.
- 2026-08-03: 모델 이름이 아니라 전체 변환 계약을 나타내는 profile key로 질의 벡터 공간을 선택한다.
- 2026-08-03: 차원 가변 열과 프로필별 partial expression index로 미래 모델을 격리한다.
- 2026-08-03: BM25는 별도 retriever로 평가하며 현재 검색에 미리 결합하지 않는다.
- 2026-08-03: NIM 호출과 운영 DB 변경을 분리하기 위해 원문 없는 재개 가능 로컬 벡터 체크포인트를 추가했다.
- 2026-08-03: 코퍼스 변경과 벡터 적재를 공용 advisory lock으로 직렬화하고, 전체 coverage·해시·norm 검증 뒤에만 dense 프로필을 활성화하도록 했다.
- 2026-08-03: 모델 독립 `corpus.search_ready` 게이트로 direct·keyword까지 같은 corpus 세대 전환에 묶었다.
- 2026-08-03: migration capability marker로 flag 행을 임의 생성한 구버전 DB와 0010 적용 DB를 구분하고, 준비 중 상태를 HTTP 503으로 명시했다.
- 2026-08-03: [대체됨] 당시에는 위 HNSW 설치 사실을 보존하되 실험 D와 근거 찾기 품질 검증에서 HNSW 상태·결과를 제외하고, 전수 검증 뒤 별도 설계 승인을 검토하기로 했다. 이 결정은 2026-08-04 영구 제외 결정으로 대체됐다.
- 2026-08-03: `hnsw_ready`를 backfill 승격과 exact 검색의 조건에서 제거하고 물리 상태 진단값으로만 남겼다.
- 2026-08-03: 현재 corpus의 완전한 지원 기준일을 `2026-06-03..2026-08-03` 양끝 포함으로 고정하고, 범위 밖 요청은 검색 전에 `422 unsupported_corpus_date`로 차단한다.
- 2026-08-03: corpus snapshot, 독립 retrieval profile/build, configuration/member, release/build와 ready-only active pointer를 additive catalog로 분리했다. 평가 실행은 동일 release snapshot을 복합 외래키로 추적할 수 있게 했지만, catalog writer·runtime 선택·BM25·RRF·새 HNSW는 구현하지 않았다.
- 2026-08-04: HNSW 보류를 철회하고 현재와 미래의 제품·실험 검색 경로에서 영구 제외했다. 기존 물리 인덱스와 `hnsw_ready`는 cleanup 전까지 남는 역사적 잔여물일 뿐 사용·재구축·튜닝·평가·release 연결하지 않으며, 새 HNSW 인덱스나 build도 만들지 않는다.
