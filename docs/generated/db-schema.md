# 데이터베이스 스키마

> 기준 시점: 2026-08-03
> 생성 기준: `apps/api/migrations/versions/0001_legal_corpus.py` ~ `0011_retrieval_catalog.py`
> 적용 명령: `cd apps/api; uv run alembic upgrade head`

| 테이블 | 역할 |
|---|---|
| `legal_documents` | 안정적인 법령 ID, 정확 명칭, 문서 종류 |
| `document_versions` | 문서·MST·시행일별 버전, 법적 생명주기, 출처 가용성, 효력 기간, 부칙 여부, 원문 계보 |
| `provisions` | 조·항·호·목 경로와 원문 |
| `embedding_profiles` | provider·model·query/passage 입력·차원 축약·정규화·본문 템플릿 버전 |
| `provision_embeddings` | 프로필·원문 입력 SHA-256별 차원 가변 `vector`와 생성 시각 |
| `corpus_snapshots` | parser 버전·지원 기준일·문서/조문 수·고유 fingerprint로 식별한 corpus 세대 |
| `retrieval_profiles` | retriever 종류·engine·구현 버전·설정 SHA와 선택적 임베딩 프로필을 묶은 독립 검색 계약 |
| `retrieval_index_builds` | corpus snapshot과 retrieval profile별 물리 산출물의 구축 상태·수량·지문·진단 |
| `retrieval_configurations` | 여러 retrieval profile의 실행 전략과 버전·파라미터 지문 |
| `retrieval_configuration_members` | configuration에 속한 profile의 역할·순서·필수 참여 여부 |
| `retrieval_releases` | 하나의 corpus snapshot과 retrieval configuration을 묶은 draft/ready/retired 세대 |
| `retrieval_release_builds` | release member를 같은 snapshot·profile의 구체적인 index build에 연결 |
| `active_retrieval_release` | `ready` release 하나만 가리킬 수 있는 singleton pointer |
| `legal_relationships` | 상하위법·위임·인용 관계 |
| `derived_obligations` | 행위자·조건·의무/금지/허가/신고 파생 데이터 |
| `ingestion_runs` | 수집 실행 상태와 비민감 통계 |
| `evaluation_runs` | 데이터셋·코드 SHA, corpus snapshot, retrieval release와 실행 metadata까지 추적하는 평가 결과 |
| `runtime_flags` | 검색 전용 모드 등 런타임 상태 |
| `anonymous_usage` | 일별 회전 HMAC별 AI/검색 횟수; 원문 IP 미저장 |
| `user_profiles` | 내부 UUID와 Supabase `auth.users` 공급자 ID를 분리한 최소 프로필 |
| `user_consents` | 이용약관·개인정보 처리방침 버전과 동의 시각 |
| `conversations` | 로그인 사용자 대화 요약, 최근 활동 시각과 턴 수 |
| `question_history` | 대화별 질문·응답 턴, 순번, 단계별 검색 진단 JSONB와 1년 만료 시각 |
| `checklist_exports` | 질문 이력에서 생성한 내보내기 감사 메타데이터 |
| `account_usage` | 로그인 계정별 일일 AI/검색 전용 사용량 |
| `history_retention_runs` | 질문 이력 정리 실행 시각·cutoff·삭제/갱신 수·성공/실패의 비민감 감사 |

`legal_documents.exact_title`과 `provisions.(heading, content)`에는 PGroonga 색인이 있다. 임베딩은 `embedding_profiles`의 전체 변환 계약과 `provision_embeddings.source_text_sha256`으로 계보를 추적한다. 현재 NVIDIA 프로필 행만 대상으로 `embedding::vector(512)` cosine HNSW partial expression index가 물리적으로 존재한다. 다만 현재 운영·실험 dense SQL은 exhaustive exact cosine을 사용하며, 이 인덱스의 후속 설계·평가는 1,000문항 gold와 근거 찾기 검증 뒤 별도 승인 전까지 보류한다.

`0009`부터 `document_versions`의 자연키는 `(document_id, mst, effective_from)`이고 `effective_from`은 필수다. `effective_to`는 `NULL`이거나 `effective_from`보다 뒤여야 한다. `document_versions_one_open_per_document` partial unique index는 `effective_to IS NULL`인 open version을 문서마다 하나로 제한한다. 동일 시행일의 복수 MST는 수집기의 연혁 검증에서 거부하므로 exclusion constraint는 두지 않는다.

법적 상태 `lifecycle_state`는 `active`, `scheduled`, `abolished`만 허용한다. 출처 상태 `source_record_state`는 `available`, `deleted`만 허용하며 `source_deleted_on`은 공식 삭제 목록의 날짜를 보존한다. `has_supplementary_provisions`는 원문에 부칙 구조가 있었는지를 기록한다. 기존 행은 각각 `active`, `available`, `false`로 이관하지만 새 행을 위한 DB 기본값은 두지 않는다. 쓰기 경로가 세 값을 명시하지 않으면 `NOT NULL` 제약으로 실패한다. 출처 삭제는 법적 폐지나 효력 종료일을 뜻하지 않는다.

`0010`은 `runtime_flags['schema.corpus_search_ready_v1']` capability marker와 `runtime_flags['corpus.search_ready']=false`를 같은 migration transaction에 설치한다. 모든 운영 retrieval은 capability의 `enabled=true`와 모델 독립 게이트의 `ready=true`를 모두 요구한다. collector는 검색 가시성 변경과 같은 transaction에서 false로 만들고, 벡터 backfill은 전체 coverage·원문 SHA·차원·L2 norm 검증과 같은 transaction에서 embedding profile과 이 값을 함께 활성화한다. 물리 HNSW의 `hnsw_ready`는 현재 진단값이며 승격 조건이 아니다. 준비되지 않은 상태는 빈 검색 결과가 아니라 `503 corpus_unready`이며 상태 API에서 별도로 확인한다.

`0011`은 현재 검색 쿼리를 바꾸지 않는 additive retrieval catalog다. `corpus_snapshots`의 지원 날짜 양끝과 count, 각 profile/configuration의 JSON object·SHA-256, build와 release의 허용 상태값과 상태별 완료 조건을 DB 제약으로 검사한다. `ready` 또는 `superseded` build는 `indexed_count=expected_count`이고 산출물 fingerprint가 있어야 하며, 실패 build만 `error_code`를 가진다. release build는 다음 세 관계를 복합 외래키로 동시에 만족해야 한다.

- release가 선택한 configuration과 corpus snapshot
- configuration에 실제로 등록된 profile member
- 같은 profile과 같은 corpus snapshot으로 만든 index build

`active_retrieval_release`는 `ready` 상태와의 복합 외래키로 준비된 release 하나만 가리킨다. `evaluation_runs.retrieval_release_key`를 기록할 때는 `corpus_snapshot_id`도 필수이고, 두 값이 같은 release 세대를 가리키도록 복합 외래키가 검사한다. 기존 평가 행을 보존하기 위해 새 계보 열은 nullable이다.

조회용 B-tree index는 build의 `(profile_key, snapshot_id, state, started_at DESC)`, release의 `(snapshot_id, state, created_at DESC)`, 평가 계보의 `(corpus_snapshot_id, retrieval_release_key, created_at DESC)`에 추가된다. `0011`에는 새 HNSW나 lexical index가 없다.

마이그레이션은 `runtime_flags['schema.retrieval_catalog_v1']` capability marker만 seed하고 snapshot·profile·build·configuration·release·active pointer 행은 자동 생성하지 않는다. 현재 runtime도 catalog를 읽어 검색 방식을 선택하지 않는다. 따라서 설치 직후 동작은 exhaustive exact dense와 dense 결과 0건일 때의 독립 keyword fallback 그대로다. BM25·RRF·새 HNSW profile이나 build는 추가하지 않는다.

`0008`은 기존 4인자·5인자 `hybrid_search` 함수를 모두 제거한다. 현재 API는 dense-only SQL을 실행하고 dense 후보가 0개일 때만 독립 PGroonga keyword fallback을 실행한다. RRF는 현재 DB 동작이 아니다. 향후 BM25·RRF는 별도 retriever와 평가 버전을 추가해 비교한다.

`question_history.diagnostics`는 입력 검증, 파싱, 임베딩, 검색, 생성, 결과 단계를 보존한다. 대화 목록은 `(user_id, updated_at DESC, id DESC)`, 대화 턴은 `(conversation_id, turn_index DESC, id DESC)` 복합 색인으로 커서 페이지네이션한다. 기존 질문 이력은 마이그레이션 시 각각 하나의 대화로 이관된다.

사용자 테이블은 `auth.users` 삭제를 기준으로 연쇄 삭제된다. 대화를 삭제하면 질문 턴과 해당 턴의 체크리스트 내보내기 메타데이터가 연쇄 삭제된다. `purge_expired_question_history(cutoff)`는 저장 경로와 같은 순서로 영향받은 대화를 먼저 잠그고, cutoff에 만료된 질문의 내보내기를 `DELETE ... RETURNING`으로 정리해 실제 삭제 수를 얻은 뒤 질문 삭제·대화 요약 재집계·빈 대화 삭제를 수행한다. 실행은 advisory transaction lock으로 직렬화되며 `history_retention_runs`에는 원문·사용자 식별자 없이 집계와 SQLSTATE만 기록한다. 감사 table·identity sequence·함수는 `PUBLIC`, `anon`, `authenticated` 권한을 명시적으로 회수하고 필요한 `service_role` 권한만 부여했다.

`0006`은 `pg_cron` extension을 설치하거나 schedule을 등록하지 않는다. Production 예약은 별도 승인 후 대상 Supabase의 extension 가용성·설치 상태와 호출 권한을 확인하는 운영 변경이다. 사용자 소유 테이블에는 RLS와 `auth.uid()` 소유권 정책을 적용했다. FastAPI의 pooler 직접 연결은 검증된 사용자 ID를 모든 소유 데이터 쿼리 조건에 사용한다.

권위 있는 변경은 이 파일이 아니라 Alembic 마이그레이션에 한다.
