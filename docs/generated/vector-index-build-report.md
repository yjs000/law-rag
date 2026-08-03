# 운영 벡터 인덱스 구축 결과

기준 시각: 2026-08-03T11:08:26Z

생성 근거: 아래에 기록한 운영 CLI의 실제 stdout과 `GET /v1/corpus/status` 응답

대상: Supabase 운영 corpus, NVIDIA Nemotron 512차원 dense-only 프로필

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

`alembic upgrade head`가 migration `0008`의 `provision_embeddings_nemotron_512_hnsw` partial HNSW 인덱스와 이후 schema를 설치한다. `load-cache`는 벡터를 넣은 뒤 coverage, 원문 SHA-256, 512차원, L2 norm, HNSW valid·ready 상태를 검사하고 전부 통과할 때만 embedding profile과 `corpus.search_ready`를 같은 transaction에서 활성화한다.

## 실제 결과

| 확인 항목 | 실제 값 |
|---|---:|
| Alembic revision | `0010 (head)` |
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
| embedding profile active | `true` |
| corpus search ready | `true` |
| hybrid/RRF DB 함수 | 없음 |

로컬 체크포인트는 `.data/embeddings/nvidia-nemotron-3-embed-1b-512-v1.jsonl`에 있다. 이 파일은 Git에서 제외되며 운영 검색 저장소가 아니다. append-only 재개 파일이므로 전체 줄 수는 이전 ID 3,066개와 parser v3 ID 3,066개를 합친 6,132줄이다. 현재 corpus 기준 유효 레코드는 3,066개다.

- 파일 크기: 67,393,498 bytes
- SHA-256: `3E335D908B00EA87F88648358A8CCB3DB2823A79562B781E6CBFC54350F9673F`
- 실제 운영 벡터 저장 위치: Supabase PostgreSQL `provision_embeddings`
- 변환 계약 저장 위치: `embedding_profiles`
- HNSW 인덱스: `provision_embeddings_nemotron_512_hnsw`

## 운영 검색 확인

운영 확인용 단일 질문은 실험 D 데이터셋 평가가 아니다. 실제 query embedding은 512차원이었고 검색 전략은 `dense_only`였다.

| 순위 | 문서·경로 | cosine |
|---:|---|---:|
| 1 | 신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법 `제2조/호3.` | 0.590565657053332 |
| 2 | 전기사업법 시행령 `제1조의3/항①` | 0.4642455992918255 |
| 3 | 전기사업법 `제7조의3/항①` | 0.4522541434916352 |

운영 API의 `GET /health`는 `ok`, `GET /v1/corpus/status`는 `corpus_search_ready=true`, 9개 문서 모두 `state=ready`를 반환했다.

## 재실행 해석

- 본문 템플릿 SHA가 같으면 NIM을 다시 호출하지 않고 체크포인트 벡터를 재사용한다.
- corpus가 바뀌면 collector가 검색 게이트를 먼저 닫는다.
- 적재 도중 실패하면 검색 게이트와 profile은 inactive로 남고, 같은 명령을 다시 실행하면 완료된 SHA는 재사용한다.
- `complete=true`는 현재 corpus에 필요한 체크포인트가 모두 있다는 뜻이고, `corpus_search_ready=true`는 DB 적재와 전체 검증까지 끝났다는 뜻이다.
