# 데이터베이스 스키마

> 기준 시점: 2026-07-18
> 생성 기준: `apps/api/migrations/versions/0001_legal_corpus.py` ~ `0004_retrieval_diagnostics.py`
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
| `user_profiles` | 내부 UUID와 Supabase `auth.users` 공급자 ID를 분리한 최소 프로필 |
| `user_consents` | 이용약관·개인정보 처리방침 버전과 동의 시각 |
| `question_history` | 로그인 사용자 질문·응답, 단계별 검색 진단 JSONB와 1년 만료 시각 |
| `checklist_exports` | 질문 이력에서 생성한 내보내기 감사 메타데이터 |
| `account_usage` | 로그인 계정별 일일 AI/검색 전용 사용량 |

`legal_documents.exact_title`과 `provisions.(heading, content)`에는 PGroonga 색인, `provision_embeddings.embedding`에는 HNSW cosine 색인이 있다. `hybrid_search` SQL 함수가 기준일 유효 버전만 대상으로 제목·표제·본문 키워드와 선택적 벡터 순위를 RRF로 합친다. `question_history.diagnostics`는 입력 검증, 파싱, 임베딩, 검색, 생성, 결과 단계를 보존한다.

사용자 테이블은 `auth.users` 삭제를 기준으로 연쇄 삭제된다. 사용자 소유 테이블에는 RLS와 `auth.uid()` 소유권 정책을 적용했다. FastAPI의 pooler 직접 연결은 검증된 사용자 ID를 모든 소유 데이터 쿼리 조건에 사용한다.

권위 있는 변경은 이 파일이 아니라 Alembic 마이그레이션에 한다.
