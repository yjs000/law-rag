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
├─ snapshot_id                  catalog에 등록한 corpus 세대의 안정 ID
├─ fingerprint_sha256           catalog 세대의 고유 SHA-256 지문
├─ parser_schema_version        파서 계약 버전
├─ supported_as_of_from         catalog 등록 시 감사한 시작 기준일 메타데이터
├─ supported_as_of_through      catalog 등록 시 감사한 마지막 기준일 메타데이터
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

`runtime_flags['corpus.search_ready']`는 모델과 무관한 전체 검색 준비 게이트다. runtime은 migration 0010만 설치하는 `schema.corpus_search_ready_v1.enabled=true` capability marker와 `corpus.search_ready=true`를 모두 요구한다. direct path, keyword fallback, dense, 단일 조문 조회는 두 조건을 만족할 때만 결과를 읽는다. 준비 bundle과 기준 snapshot 검사가 끝난 뒤 별도 transaction A가 준비 값을 `false`로 commit하고, 65초 drain 뒤 transaction B가 전체 corpus와 벡터 검증까지 성공한 마지막에만 다시 `true`로 만든다. 따라서 transaction B의 중간 상태는 어느 retrieval 경로에서도 노출되지 않는다.

게이트가 없거나 닫혀 있으면 runtime은 빈 검색 결과나 `insufficient_evidence`로 가장하지 않고 HTTP `503`과 안정 코드 `corpus_unready`를 반환한다. `/v1/corpus/status`는 `corpus_search_ready`와 닫힌 사유를 별도로 노출한다. 실제 질문에 맞는 근거가 없는 상태와 운영 갱신 중인 상태를 이 경계로 구분한다.

운영 웹/API의 벡터 검색 원본은 PostgreSQL `provision_embeddings`뿐이다. API runtime은 `.data`의 bundle,
`embeddings.jsonl` 또는 로컬 cache를 읽거나 DB 검색 실패 시 그 파일로 fallback하지 않는다. 로컬 벡터는
점검 반영을 위한 운반물이며 transaction B에서 DB에 복사되고 전체 검증과 commit이 끝난 뒤에만 검색된다.

`embedding_profiles.active`는 단순 설정값이 아니라 검색 준비 게이트다. dense SQL은 다음 조건을 모두 만족하는 행만 읽는다.

- 프로필이 `active=true`다.
- 프로필의 본문 템플릿이 `legal-provision-v1`이다.
- 저장된 `source_text_sha256`가 현재 법령명·경로·표제·본문으로 다시 계산한 SHA-256과 같다.
- 버전의 `source_record_state='available'`이다.
- 버전의 `lifecycle_state`가 `active` 또는 `scheduled`이거나, `abolished`이면서 검증된 `effective_to`가 있고 질의 기준일이 그 이전의 효력 구간 안에 있다.
- 버전의 파서 스키마가 현재 지원 버전인 `3`이다.

조문 직접 조회와 keyword fallback에도 전체 corpus 준비 게이트와 같은 버전 상태 조건을 적용한다. 출처에서 삭제되어 재검증할 수 없는 레코드는 검색 근거로 노출하지 않는다. 폐지 법령은 공식 종료일이 확인된 버전에 한해 폐지 전 기준일 검색을 허용하고, 종료일을 확인할 수 없는 폐지 레코드는 안전하게 격리한다.

`prepare-current`와 bundle 임베딩은 DB lock 없이 로컬에서 끝낸다. 실제 반영기만 session writer lock을
`EMBEDDING_BACKFILL_LOCK_KEY → CORPUS_SYNC_RUN_LOCK_KEY` 순서로 얻어 collector와 backfill 중복 실행을
막는다. 준비 당시 기준 snapshot이 현재 DB와 다르거나 lock을 얻지 못하면 gate를 건드리지 않고 실패한다.

반영 transaction A와 B는 각각 `CORPUS_MUTATION_LOCK_KEY`를 얻는다. A는 기준 snapshot을 마지막으로
재확인하고 `corpus.search_ready=false`, `reason=corpus_publish`, `update_id`를 commit한다. 65초 drain 뒤
B는 문서·버전·조문·삭제·벡터를 100행씩 처리하되 transaction 전체를 한 번만 commit한다. 각 벡터의 현재
`legal-provision-v1` SHA를 다시 확인하고 전체 coverage·512차원·L2 norm·parser/profile·시간 범위를 검증한
뒤 profile과 gate를 마지막에 활성화한다. 하나라도 실패하면 B 전체가 rollback되고 A의 닫힌 gate는 남는다.

운영 검색 reader는 shared advisory lock을 사용하지 않는다. API 경계에서 날짜와 준비 상태를 먼저 검사하고,
실제 repository 검색 직전 준비 상태를 다시 검사하며, 검색 SQL 자체도 같은 gate를 요구한다. gate를 닫은 뒤
기존 요청 최대 실행시간보다 긴 65초를 기다려 writer와 reader의 겹침을 제거한다. 이 단순한 점검 모드는
구·신세대 테이블과 active generation pointer를 추가하지 않는다. 실험 D의 재현성 lock, writer lock과
history-retention lock은 별도 목적이므로 유지한다.

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

## 현재 corpus의 동적 기준일 지원 계약

현재 runtime은 `corpus_snapshots` catalog의 특정 행이나 날짜가 들어간 포인터로 지원 범위를 고정하지 않는다. UTC+9 한국 날짜의 오늘을 기준으로 현재 repository가 다음 값을 읽기 전용으로 계산한다.

```text
supported_as_of_through = 한국 날짜의 오늘
supported_as_of_from = 오늘 이하인 수집·현재 parser·검색 가능 버전의
                       effective_from 전역 최솟값

today_eligible = effective_from <= 오늘
                 그리고
                 effective_to IS NULL 또는 오늘 < effective_to

corpus_snapshot_id = SHA-256(
  parser contract + retrieval unit
  + today_eligible count + content fingerprint
)
```

content fingerprint는 오늘 유효한 provision의 ID·출처·버전·`effective_from`·경로·표제·본문 SHA-256 등 검색 콘텐츠를 정렬해 계산한다. 달력 날짜, `effective_to`, embedding profile은 snapshot ID 입력에 넣지 않는다. 날짜와 `effective_to`는 어느 행이 오늘 population에 포함되는지는 결정하지만, 같은 eligible ID와 검색 콘텐츠를 가진 population을 날짜만 달라졌다는 이유로 새 corpus로 식별하지 않는다. embedding profile은 별도 retrieval contract다.

시작일은 현재 저장된 검색 가능 version의 전역 최솟값일 뿐, 법률마다 과거 버전이 모두 수집됐거나 timeline gap·overlap이 없다는 검증 결과가 아니다. 전체 검색 준비 게이트가 닫혔거나 오늘 eligible provision이 0개이거나 시작일·fingerprint를 완성할 수 없으면 repository는 준비되지 않은 temporal state를 반환한다. 검색 엔드포인트는 이를 HTTP `503`, 코드 `corpus_unready`로 닫으며 상태 API의 시작일과 snapshot ID는 `null`일 수 있다.

두 경계일을 포함한다. 준비된 범위 밖 날짜는 과거 일부 문서만 검색해 빈 결과나 `insufficient_evidence`로 오인하지 않고, quota·임베딩·repository 검색 전에 HTTP `422`, 코드 `unsupported_corpus_date`로 차단한다. `/v1/corpus/status`는 동적으로 계산한 snapshot ID, 양쪽 경계와 준비 상태·사유를 노출한다. 요청 기본 날짜는 한국 날짜의 오늘이다. 법률 버전의 `effective_from/effective_to` 판정은 이 runtime gate를 통과한 뒤 요청 기준일에 다시 적용한다.

2026-08-04 KST 운영 Supabase 읽기 전용 검증에서 관측한 동적 값은 `ready=true`, `supported_as_of_from=2024-07-01`, `supported_as_of_through=2026-08-04`, 오늘 eligible provision 3,066개와 content-derived `corpus-sha256:*` ID다. 이는 runtime에 하드코딩하지 않는 시점별 관측 기록이다.

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

운영 DB를 바꾸지 않고 준비 bundle과 벡터를 로컬에 생성:

```powershell
uv run --project apps/collector law-rag-collector prepare-current `
  --output .data/corpus-updates/current
uv run --directory apps/api python -m scripts.backfill_embeddings generate-cache `
  --bundle .data/corpus-updates/current --batch-size 32
```

완성된 bundle을 점검 모드에서 원자 반영:

```powershell
uv run --project apps/collector law-rag-collector apply-prepared `
  --bundle .data/corpus-updates/current
```

실제 query 임베딩과 dense-only 검색 확인:

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings verify `
  --query "태양광 발전 설비는 법에서 어떻게 정의하나요?" --limit 3
```

bundle은 `.data/corpus-updates/<update-id>/` 아래 `manifest.json`, `documents.jsonl`, `deletions.json`,
`raw/`, `embeddings.jsonl`로 저장하며 Git에서 제외한다. manifest의 게시 전용 기준 snapshot에는 조문 검색
내용뿐 아니라 `effective_to`, lifecycle·source 상태, raw SHA 등 writer가 바꿀 수 있는 저장 필드가 들어간다.
이는 날짜를 제외하는 runtime content snapshot과 목적이 다른 stale bundle 방지 조건이다. parser·embedding
profile, 변경 개수와 파일별 SHA-256도 넣고 다른 파일이 완성된 마지막에 생성한다. 원문 raw는 bundle 안에 있지만
embedding JSONL에는 조각 ID, profile, 본문 입력 SHA-256, 512차원 L2 정규화 벡터만 저장한다. 동일 ID·SHA와
동일 profile·SHA 벡터를 재사용하고 새로 생기거나 본문이 바뀐 조각만 NIM으로 보낸다.

`apply-prepared`는 bundle checksum, cache 완전성, 기준 snapshot, migration 0010 capability marker와 필수
프로필 계약을 gate 변경 전에 검사한다. 원문 Storage 업로드도 gate 변경 전에 끝내며 transaction B 안에서는
외부 API·NIM·Storage 호출이나 대기를 하지 않는다. 기존 `sync-current`, `load-cache`, `run` 코드는 바로
삭제하지 않지만 정기 workflow의 운영 진입점은 `apply-prepared` 하나다. transaction B의 마지막 검사는
다음을 모두 확인하고 전부 통과할 때만 `active=true`와 `corpus.search_ready=true`를 함께 쓴다.

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
- 2026-08-03: [대체됨] 당시 감사한 corpus의 지원 기준일을 `2026-06-03..2026-08-03` 양끝 포함으로 고정하고, 범위 밖 요청은 검색 전에 `422 unsupported_corpus_date`로 차단했다.
- 2026-08-03: corpus snapshot, 독립 retrieval profile/build, configuration/member, release/build와 ready-only active pointer를 additive catalog로 분리했다. 평가 실행은 동일 release snapshot을 복합 외래키로 추적할 수 있게 했지만, catalog writer·runtime 선택·BM25·RRF·새 HNSW는 구현하지 않았다.
- 2026-08-04: HNSW 보류를 철회하고 현재와 미래의 제품·실험 검색 경로에서 영구 제외했다. 기존 물리 인덱스와 `hnsw_ready`는 cleanup 전까지 남는 역사적 잔여물일 뿐 사용·재구축·튜닝·평가·release 연결하지 않으며, 새 HNSW 인덱스나 build도 만들지 않는다.
- 2026-08-04: runtime 지원 범위와 오늘 content snapshot을 수집·현재 parser·검색 가능 population에서 동적으로 계산한다. catalog의 저장된 snapshot metadata나 embedding profile을 runtime content identity로 사용하지 않으며, 준비 불완전은 `503`, 범위 밖은 검색 전 `422`로 구분한다.
- 2026-08-04: 운영 갱신을 로컬 bundle 준비와 점검 모드 원자 반영으로 분리했다. 운영 reader shared lock을
  제거하고 `gate=false → 65초 drain → 단일 반영 transaction → gate=true`를 사용한다. writer lock과
  실험 D shared lock은 유지하며 generation pointer는 추가하지 않는다.
