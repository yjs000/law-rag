# 운영 벡터 인덱스 구축 결과

기준 시각: 2026-08-03T11:08:26Z

생성 근거: 아래에 기록한 운영 CLI의 실제 stdout, `GET /v1/corpus/status` 응답과 운영 DB 읽기 전용 `EXPLAIN (ANALYZE)` 감사

대상: Supabase 운영 corpus, NVIDIA Nemotron 512차원 dense-only 프로필

> **현재 결정:** 이 문서는 이미 수행된 migration·벡터 적재·물리 인덱스 감사의 역사적 실행 기록이다. 당시 만들어진 HNSW 인덱스는 삭제하지 않지만 실험 D와 근거 찾기 품질 검증의 입력·게이트·결과로 사용하지 않는다. `hnsw_ready`도 이제 backfill 승격 조건이 아니라 물리 상태 진단값이다. 질문-정답 gold 1,000문항과 근거 찾기를 모두 검증한 뒤 별도 HNSW 설계를 제시하고 사용자가 명시적으로 승인하기 전에는 추가 HNSW 실행·튜닝·비교를 하지 않는다.

## 실행 명령

HNSW 스키마와 검색 준비 게이트는 Alembic migration으로 설치한다. 인덱스 SQL만 수동으로 따로 실행하지 않는다.

```powershell
uv run --directory apps/api alembic upgrade head
uv run --project apps/collector law-rag-collector preview-current
uv run --project apps/collector law-rag-collector sync-current
uv run --project apps/collector law-rag-collector preview-current

uv run --directory apps/api python -m scripts.backfill_embeddings cache-status
uv run --directory apps/api python -m scripts.backfill_embeddings generate-cache --batch-size 32
uv run --directory apps/api python -m scripts.backfill_embeddings load-cache --batch-size 100
uv run --directory apps/api python -m scripts.backfill_embeddings status

uv run --directory apps/api python -m scripts.backfill_embeddings verify `
  --query "태양광 발전 설비는 법에서 어떻게 정의하나요?" `
  --as-of 2026-08-03 `
  --limit 3
```

`alembic upgrade head`가 migration `0008`의 `provision_embeddings_nemotron_512_hnsw` partial HNSW 인덱스와 이후 schema를 설치한다. `load-cache`는 벡터를 넣은 뒤 coverage, 원문 SHA-256, 512차원, L2 norm과 DB 임베딩 프로필 계약을 검사하고 전부 통과할 때만 embedding profile과 `corpus.search_ready`를 같은 transaction에서 활성화한다. HNSW valid·ready 상태는 `status`와 `verify`에 표시되는 물리 상태 진단값이며 승격 조건이 아니다.

## 실제 결과

| 확인 항목 | 실제 값 |
|---|---:|
| 실행 당시 Alembic revision | `0010` |
| corpus 문서 | 9 |
| parser schema | `3` |
| 현재 조문 | 3,066 |
| JSON 수집 | 9/9 |
| XML fallback | 0 |
| 동기화 실패 | 0 |
| 기존 체크포인트 벡터 재사용 | 2,956 |
| NVIDIA NIM 신규 생성 | 110 |
| DB 적재 | 3,066 |
| 누락 벡터 | 0 |
| stale 벡터 | 0 |
| L2 비단위 벡터 | 0 |
| HNSW valid·ready | `true` |
| HNSW OID / relfilenode | `25460 / 25460` |
| HNSW 크기 | `8,380,416 bytes` |
| PostgreSQL / pgvector | `17.6 / 0.8.2` |
| embedding profile active | `true` |
| corpus search ready | `true` |
| hybrid/RRF DB 함수 | 없음 |

로컬 체크포인트는 `.data/embeddings/nvidia-nemotron-3-embed-1b-512-v1.jsonl`에 있다. 이 파일은 Git에서 제외되며 운영 검색 저장소가 아니다. append-only 재개 파일이므로 전체 줄 수는 이전 ID 3,066개와 parser v3 ID 3,066개를 합친 6,132줄이다. 현재 corpus 기준 유효 레코드는 3,066개다.

- 파일 크기: 67,393,498 bytes
- SHA-256: `3E335D908B00EA87F88648358A8CCB3DB2823A79562B781E6CBFC54350F9673F`
- 실제 운영 벡터 저장 위치: Supabase PostgreSQL `provision_embeddings`
- 변환 계약 저장 위치: `embedding_profiles`
- HNSW 인덱스: `provision_embeddings_nemotron_512_hnsw`

## 후속 retrieval catalog와 이 기록의 관계

Migration `0011_retrieval_catalog.py`는 이 실행 뒤에 추가된 계보 catalog다. corpus snapshot, 독립 retrieval profile, index build, configuration과 member, release와 build 연결, active release pointer를 분리해 기록하고 `evaluation_runs`에 dataset·code·snapshot·release 계보를 연결한다.

`0011` 적용은 벡터를 다시 만들거나 HNSW를 새로 구축·활성화하는 명령이 아니다. 마이그레이션은 8개 catalog 테이블과 `schema.retrieval_catalog_v1` capability marker만 설치하며, 이 문서의 과거 벡터와 HNSW를 snapshot·build·release 행으로 자동 추정해 넣지 않는다. 따라서 이 표의 `HNSW valid·ready=true`는 당시 물리 상태 기록일 뿐 ready release 또는 현재 검색 선택을 뜻하지 않는다.

현재 runtime은 catalog나 `active_retrieval_release`를 읽지 않는다. 검색 동작은 계속 exhaustive exact dense이고 dense 결과가 0건일 때만 독립 keyword fallback을 실행한다. BM25·RRF·새 HNSW profile/build/configuration은 이번 catalog migration에 포함되지 않는다.

## 운영 검색 확인

운영 확인용 단일 질문은 실험 D 데이터셋 평가가 아니다. 실제 query embedding은 512차원이었고 검색 전략은 `dense_only`였다.

| 순위 | 문서·경로 | cosine |
|---:|---|---:|
| 1 | 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 `제2조/호3.` | 0.590565657053332 |
| 2 | 전기사업법 시행령 `제1조의3/항①` | 0.4642455992918255 |
| 3 | 전기사업법 `제7조의3/항①` | 0.4522541434916352 |

운영 API의 `GET /health`는 `ok`, `GET /v1/corpus/status`는 `corpus_search_ready=true`, 9개 문서 모두 `state=ready`를 반환했다.

## 과거 인덱스 준비와 실행 계획 감사

물리 HNSW 인덱스는 존재하고 valid·ready이며 단순 vector-only 최근접 이웃 query에서는 사용된다. 그러나 현재 production 형태의 법률·버전·기준일 join query는 3,066개 규모에서 HNSW가 아니라 유효 행의 exact cosine sort 계획을 선택했다. 따라서 `HNSW ready=true`와 `실제 query가 HNSW 사용`은 같은 뜻이 아니다.

읽기 전용 비교에서 최종 runner의 materialized exact query는 현재 기준일(2026-08-03) 3,066개 행에서 중앙값 약 `70.846 ms`였고, 별도로 측정한 HNSW 후보 CTE는 약 `1.421 ms`였으며 현재 기준일 top 11은 같았다. 하지만 과거 기준일에서는 HNSW 후보를 먼저 제한한 뒤 효력 필터를 적용하면 결과가 부족했다.

| 기준일 | 유효 population | exact 반환 | HNSW 후보 CTE 반환 |
|---|---:|---:|---:|
| 2025-07-19 | 16 | 11 | 0 |
| 2025-10-01 | 426 | 11 | 3 |
| 2026-01-02 | 956 | 11 | 7 |
| 2026-06-03 | 3,066 | 11 | 11 |
| 2026-08-03 | 3,066 | 11 | 11 |

이 비교는 실험 D 질문은행을 실행한 품질 실험이 아니라 단일 query로 과거에 수행한 실행 계획·완전성 감사다. 위 속도·반환 수를 HNSW 품질 검증이나 채택 근거로 사용하지 않는다. 현재 실험 D primary dense baseline은 모든 문항 기준일의 유효 population을 `MATERIALIZED`해 완전히 비교하는 exhaustive exact cosine으로 고정하며, runner는 HNSW 상태·계획·결과 비교를 기록하지 않는다.

## 현재 corpus 기준일 계약

운영 DB 읽기 전용 감사에서 허용 목록 9개마다 open version 1개, 검색 가능한 provision 3,066개, open version 중 가장 늦은 `effective_from=2026-06-03`을 확인했다. snapshot 검증 기준일은 `2026-08-03`이다. 따라서 현재 corpus의 검색 보장 범위는 다음과 같다.

```text
2026-06-03 <= as_of_date <= 2026-08-03
```

양끝을 포함한다. 위 표의 더 오래된 날짜는 일부 유효 행만 남아 완전한 현재 9개 corpus를 대표하지 않으므로 이제 검색 대상으로 허용하지 않는다. API는 범위 밖 요청을 embedding·repository 호출 전에 `422 unsupported_corpus_date`로 거부하고 `/v1/corpus/status`에서 snapshot ID와 두 경계를 노출한다.

## 재실행 해석

- 본문 템플릿 SHA가 같으면 NIM을 다시 호출하지 않고 체크포인트 벡터를 재사용한다.
- corpus가 바뀌면 collector가 검색 게이트를 먼저 닫는다.
- 적재 도중 실패하면 검색 게이트와 profile은 inactive로 남고, 같은 명령을 다시 실행하면 완료된 SHA는 재사용한다.
- `complete=true`는 현재 corpus에 필요한 체크포인트가 모두 있다는 뜻이고, `corpus_search_ready=true`는 DB 적재와 전체 검증까지 끝났다는 뜻이다.
