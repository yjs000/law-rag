# 데이터베이스 스키마

> 기준 시점: 2026-07-13
> 생성 기준: `apps/api/migrations/versions/0001_legal_corpus.py`
> 적용 명령: `cd apps/api; uv run alembic upgrade head`

| 테이블 | 역할 |
|---|---|
| `legal_documents` | 안정적인 법령 ID, 정확 명칭, 문서 종류 |
| `document_versions` | MST, 공포/시행 기간, 원문 포맷·해시·Storage 경로 |
| `provisions` | 조·항·호·목 경로와 원문 |
| `provision_embeddings` | 모델·차원·버전별 `vector(512)` |
| `legal_relationships` | 상하위법·위임·인용 관계 |
| `derived_obligations` | 행위자·조건·의무/금지/허가/신고 파생 데이터 |
| `ingestion_runs` | 수집 실행 상태와 비민감 통계 |
| `evaluation_runs` | 데이터셋·모델·색인·프롬프트별 평가 결과 |
| `runtime_flags` | 검색 전용 모드 등 런타임 상태 |
| `anonymous_usage` | 일별 회전 HMAC별 AI/검색 횟수; 원문 IP 미저장 |

`provisions.content`에는 PGroonga 색인, `provision_embeddings.embedding`에는 HNSW cosine 색인이 있다. `hybrid_search` SQL 함수가 기준일 유효 버전만 대상으로 키워드와 벡터 순위를 RRF로 합친다.

권위 있는 변경은 이 파일이 아니라 Alembic 마이그레이션에 한다.
