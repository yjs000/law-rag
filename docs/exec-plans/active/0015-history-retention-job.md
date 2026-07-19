# 질문 이력 보존 정리 작업 실행 계획

## 목적과 사용자 결과

로그인 사용자의 질문 이력은 `expires_at` 기준 1년까지만 보존한다. 애플리케이션 요청과 무관하게 실행 가능한 DB 정리 함수가 만료 턴, 연쇄된 체크리스트 내보내기, 대화 요약과 빈 대화를 일관되게 정리하고 각 실행 결과를 비민감 집계로 감사 가능하게 남긴다.

## 범위와 비범위

### 범위

- `0006_history_retention_job.py`에 정리 함수와 실행 감사 테이블 추가
- 만료 `question_history` 삭제와 `checklist_exports` FK cascade 계약 고정
- 영향받은 `conversations`의 `turn_count`, `updated_at`, `last_turn_id` 재집계 및 빈 대화 삭제
- 동시 실행 직렬화, 재실행 멱등성, 성공·실패 감사
- scheduler 비종속 migration과 Supabase 운영 적용 승인 절차 문서화

### 비범위

- Production 또는 외부 DB migration 적용
- `pg_cron` extension 설치·활성화 또는 schedule 등록
- credential 조회·출력
- 1년 보존기간 변경, 백업 보존 정책 변경
- 애플리케이션 repository 정리 메서드 변경

## 측정 가능한 완료 조건

- [x] `expires_at <= p_cutoff_at`인 질문만 삭제한다.
- [x] 삭제 대상의 `checklist_exports`를 `DELETE ... RETURNING`으로 먼저 정리해 실제 삭제 수를 기록하고 FK cascade를 안전망으로 유지한다.
- [x] 저장 경로와 같은 순서로 영향받은 대화를 먼저 잠근 뒤 재집계하며 남은 턴이 없으면 삭제한다.
- [x] 사용자 단일 이력 삭제도 conversation-first로 통일해 retention과의 교차 deadlock을 막는다.
- [x] 같은 cutoff로 재실행할 때 추가 삭제 없이 성공 감사 행을 남긴다.
- [x] advisory transaction lock으로 겹친 실행을 직렬화한다.
- [x] 유효 cutoff로 접수된 실행의 시작·종료·삭제/갱신 수·성공/실패·SQLSTATE를 기록하고 질문/사용자/오류 전문은 기록하지 않는다.
- [x] 명시적 NULL cutoff는 감사 실행으로 만들지 않고 INSERT 전 `22023` 입력 오류로 거부한다.
- [x] migration은 `pg_cron`을 설치하거나 예약하지 않는다.
- [x] 정적 migration 계약 테스트와 문서 gate가 통과한다.
- [x] 임시 PostgreSQL 17에서 cascade·대화 재집계·빈 대화 삭제·같은 cutoff 재실행을 검증한다.

## 구현 단계와 체크리스트

1. [x] migration 계약 테스트를 작성하고 `0006` 부재로 RED를 확인한다.
2. [x] 감사 테이블과 `SECURITY DEFINER` 정리 함수를 구현한다.
3. [x] table·identity sequence·function 권한을 `PUBLIC`, `anon`, `authenticated`에서 회수하고 필요한 `service_role` 권한만 부여한다.
4. [x] schema·신뢰성·학습 문서를 갱신한다.
5. [ ] Production 적용 전 승인자가 대상 Supabase 프로젝트와 maintenance window를 확인한다.
6. [ ] 승인 후 대상 DB에서 `pg_available_extensions`와 `pg_extension`으로 `pg_cron` 가용·설치 상태를 확인한다.
7. [ ] extension 변경이 필요하면 별도 승인으로 수행하고, 검토된 service-role scheduler 경로에서 일 1회 함수를 등록한다.
8. [ ] 첫 실행 뒤 `history_retention_runs`의 성공 상태와 집계만 확인하고 사용자 원문은 조회하지 않는다.

## 검증 및 롤백

로컬 검증:

```bash
cd apps/api
uv run pytest tests/test_history_retention_migration.py -q
RETENTION_TEST_DATABASE_URL=postgresql://... uv run pytest tests/test_history_retention_postgres.py -q
PYTHONPATH=. uv run pytest tests/test_migration_contract.py tests/test_postgres_identity.py -q
uv run ruff check migrations/versions/0006_history_retention_job.py tests/test_history_retention_migration.py
cd ../..
uv run python scripts/check_docs.py
git diff --check
```

정리 함수는 실패를 중첩 PL/pgSQL block에서 되돌리고 감사 행에 안전한 SQLSTATE만 남긴다. migration downgrade는 함수와 감사 테이블을 제거하지만 삭제된 사용자 데이터는 복원하지 않는다. 따라서 운영 rollback은 schedule 비활성화 → 원인 분석 → 함수 교체 순서이며, 데이터 복원은 별도 승인된 백업 절차로만 수행한다.

## 운영 승인과 scheduler 계약

migration 자체는 `CREATE EXTENSION`, `cron.schedule`, 외부 scheduler 호출을 포함하지 않는다. Supabase 운영 적용은 다음을 모두 충족할 때만 진행한다.

1. 운영 변경 승인과 대상 프로젝트 확인
2. `pg_cron` 가용성·설치 schema·권한 확인
3. schedule 이름, UTC 실행 시각, 호출 역할, 중복 schedule 방지 쿼리 검토
4. staging 또는 승인된 임시 PostgreSQL에서 함수 실행 계약 검증
5. 호출 transaction commit 후 반환 `status`를 검사하고 `failed`면 job을 비정상 종료시키는 외부 wrapper 검증
6. 첫 운영 실행 감사와 경보 확인

함수는 실패 감사를 보존하기 위해 `failed` 행을 정상 반환한다. 따라서 단순 `SELECT`만 수행하는 `pg_cron` run은 SQL 성공으로 보일 수 있으며 단독 실패 감지 수단으로 사용하지 않는다. 승인된 외부 scheduler/Edge Function이 호출을 commit한 뒤 반환 상태를 확인해 `failed`를 비정상 종료·재시도·경보로 변환해야 한다. `pg_cron`을 선택하면 `history_retention_runs`의 마지막 성공·연속 실패를 별도 monitor가 감시해야 한다. 어떤 경로도 애플리케이션 요청 트래픽에 정리를 의존시키지 않는다.

## 결정 로그

| 날짜 | 결정 | 이유 |
|---|---|---|
| 2026-07-19 | `expires_at`을 cutoff의 권위 기준으로 사용 | 생성 시 이미 1년 만료가 고정되어 정책과 실행을 분리할 수 있음 |
| 2026-07-19 | transaction advisory lock으로 실행 직렬화 | 중복 scheduler와 수동 실행이 겹쳐도 집계와 감사가 경쟁하지 않게 함 |
| 2026-07-19 | 실패 시 SQLSTATE만 감사 | 오류 원문에 개인정보나 쿼리 데이터가 섞일 위험을 줄임 |
| 2026-07-19 | migration에서 scheduler와 extension을 배제 | Supabase 프로젝트별 가용성·승인·권한 차이를 안전하게 분리 |

## 진행 기록

- 2026-07-19: D-006 착수, 기존 migration·repository·운영 계약 확인.
- 2026-07-19: 신규 계약 테스트가 `0006` 부재로 2건 실패하는 RED 확인.
- 2026-07-19: migration 구현 후 focused 테스트 2건 통과.
- 2026-07-19: 부모 검증에서 migration·identity focused 테스트 10건과 Ruff·문서 검사를 통과했다.
- 2026-07-19: 임시 PostgreSQL 17에서 첫 실행은 질문 2건·내보내기 2건 삭제, 대화 1건 갱신·1건 삭제를 기록했고 같은 cutoff 재실행은 모든 변경 수 0으로 성공했다.
- 2026-07-19: `SECURITY DEFINER` 함수의 객체 참조를 `public`으로 schema-qualify하고 `pg_catalog` 우선 고정 search path로 강화했다.
- 2026-07-19: disposable PostgreSQL 16에서 cascade 2건, 대화 갱신 1건, 빈 대화 삭제 1건, 재실행 0건, 미래 cutoff 실패 SQLSTATE `22023`을 확인.
- 2026-07-19: 독립 review에서 새 턴 저장과 purge의 conversation race, export 사전 count, named-role ACL, scheduler 실패 감지, CI 통합 검증 부재를 확인했다.
- 2026-07-19: conversation-first row lock, export `DELETE ... RETURNING`, named-role/sequence revoke와 PostgreSQL 17 동시 저장·ACL·downgrade CI 테스트로 보완했다.
- 2026-07-19: PostgreSQL service를 포함한 API/core 210건, collector 34건, Web 46건, Ruff·ESLint·TypeScript·Production build·문서 검사를 통과했다.
- 2026-07-19: 후속 review의 NULL cutoff 불명확성을 `22023` 사전 입력 오류로 고정하고, 감사 행 미생성 및 겹친 retention advisory lock 대기를 PostgreSQL CI 테스트에 추가했다.
- 2026-07-19: 재review에서 사용자 단일 이력 삭제의 반대 잠금 순서로 `40P01`이 재현되어 `delete_history()`도 conversation-first로 변경하고 사용자 삭제·빈 대화·동시 export 삭제 회귀 테스트를 추가했다.
- 2026-07-19: deadlock 회귀를 포함한 PostgreSQL service 전체 API/core 212건과 Ruff·문서 검사를 통과했다.

## 미결정과 차단 요소

- Production schedule의 UTC 실행 시각과 보존할 감사 행의 장기 보존기간은 운영 승인 전 `미결정`이다.
- 대상 Supabase의 `pg_cron` 가용성·설치 상태는 credential 없이 확인하지 않았으며 운영 적용 전 확인이 필요하다.
- Production migration 및 schedule 등록은 명시적 승인 전 차단한다.
