# 검색 인덱스와 임베딩 계보 설계

상태: 구현 기준
결정일: 2026-08-03

## 결론

현재 검색기는 dense-only다. DB는 dense와 lexical 점수를 합치지 않으며 `hybrid_search`와 RRF 함수를 제공하지 않는다. 검색기별 후보 회수는 독립 repository 경로로 유지하고, 향후 BM25·RRF·reranker는 고정 평가셋에서 이득을 증명한 뒤 별도 버전의 실험 계층에 추가한다.

## 해결하는 불일치

기존 DB에는 다음 문제가 있었다.

- 런타임은 dense-only인데 `hybrid_search` SQL 함수와 RRF가 현재 설계처럼 남아 있었다.
- 4인자와 5인자 함수가 마이그레이션 계보에서 동시에 존재할 수 있었다.
- `model`, `dimensions`, `embedding_version`만으로는 passage/query 입력 유형, 2048→512 축약, L2 재정규화, 임베딩 본문 형식을 재현할 수 없었다.
- `vector(512)` 고정 열과 모든 행을 아우르는 HNSW 인덱스는 다른 차원의 모델을 추가할 때 테이블 변경을 요구했다.
- 조문 본문이 바뀌었을 때 저장 벡터가 현재 입력으로 만들어졌는지 판별할 해시가 없었다.

## 새 데이터 모델

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
└─ active                      현재 backfill 대상 여부

provision_embeddings
├─ provision_id                원문 조각 ID
├─ profile_key                 어떤 변환 계약의 벡터인지
├─ dimensions                  실제 저장 차원
├─ source_text_sha256          임베딩 입력 전체의 SHA-256
├─ embedding                   차원 가변 vector
└─ embedded_at                 마지막 생성 시각
```

DB는 `vector_dims(embedding)=dimensions`, 0이 아닌 norm, 프로필과 차원의 복합 외래키를 검사한다. 현재 프로필은 `nvidia-nemotron-3-embed-1b-512-v1`이다.

## passage 입력 계약

`legal-provision-v1`은 빈 값을 제외하고 다음을 줄바꿈으로 결합한다.

```text
법령명
조·항·호·목 경로
표제
원문 본문
```

이 전체 문자열의 SHA-256을 벡터 행에 저장한다. backfill 재실행 시 해시가 같으면 API를 호출하지 않고, 없거나 다르면 새 passage 벡터를 생성한다. 질문은 같은 모델·축약·정규화를 사용하되 NIM `input_type=query`로 생성한다.

## 차원 가변 저장과 프로필 전용 인덱스

pgvector는 `vector` 타입으로 서로 다른 차원을 한 열에 저장할 수 있지만, 인덱스는 같은 차원의 행에만 만들어야 한다. 공식 문서가 권장하는 방식대로 현재 프로필에 expression + partial HNSW 인덱스를 둔다.

```sql
CREATE INDEX provision_embeddings_nemotron_512_hnsw
ON provision_embeddings
USING hnsw ((embedding::vector(512)) vector_cosine_ops)
WHERE profile_key='nvidia-nemotron-3-embed-1b-512-v1';
```

dense 쿼리도 같은 표현과 프로필 조건을 사용한다. 미래에 다른 차원 모델을 평가하면 기존 열을 바꾸지 않고 새 프로필과 해당 차원의 partial expression index를 추가한다. [pgvector 공식 저장소](https://github.com/pgvector/pgvector)

## BM25 확장 경계

BM25는 벡터 프로필이 아니며 `provision_embeddings`에 저장하지 않는다. 향후 도입 순서는 다음과 같다.

1. BM25/lexical retriever가 독립 후보와 원점수를 반환한다.
2. dense-only와 같은 1,000문항 qrels로 Recall@k, MRR, nDCG@k, latency를 각각 비교한다.
3. 둘을 결합할 필요가 입증될 때만 application 계층에 버전 고정 fusion 전략을 추가한다.
4. 결합 결과에는 각 retriever의 순위·점수·버전과 fusion 버전을 trace로 남긴다.

따라서 확장 가능성은 지금 RRF를 미리 실행하는 것이 아니라, 검색기별 저장·실행·평가 경계를 분리해 교체 가능하게 하는 데서 확보한다.

## 운영 명령

DB 마이그레이션:

```powershell
uv run --directory apps/api alembic upgrade head
```

상태 확인:

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings status
```

벡터 생성:

```powershell
uv run --directory apps/api python -m scripts.backfill_embeddings run --batch-size 32
```

backfill은 원문을 수정하지 않고 파생 벡터만 배치별 upsert한다. 중간 실패 후 같은 명령을 다시 실행하면 현재 해시와 일치하는 행은 건너뛴다.

## 결정 기록

- 2026-08-03: DB의 고정 hybrid/RRF 함수를 제거하고 dense-only SQL을 repository에 명시했다.
- 2026-08-03: 모델 이름이 아니라 전체 변환 계약을 나타내는 profile key로 질의 벡터 공간을 선택한다.
- 2026-08-03: 차원 가변 열과 프로필별 partial expression index로 미래 모델을 격리한다.
- 2026-08-03: BM25는 별도 retriever로 평가하며 현재 검색에 미리 결합하지 않는다.
