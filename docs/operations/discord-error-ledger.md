# Discord 오류 Ledger

Discord thread `1528216345924337805`에서 발생한 운영 사건만 기록한다. credential, 개인 사건자료, 법률 원문 전문은 저장하지 않으며 필요한 자리는 `REDACTED`로 표시한다.

## 상태 기준

- `Open`: 사용자 또는 운영자 조치가 남아 있음
- `Resolved`: 해결과 검증이 완료됨
- `Mitigated`: 영향은 줄였으나 재발 가능성이나 후속 조치가 남아 있음
- `Expected/Mitigated`: 정상적인 제한이며 안전한 대응 절차가 있음

## 2026-07-19 사건

### 1. 기존 checkout에 대한 중복 clone 시도

- **원문/관찰:** `fatal: destination path 'law-rag' already exists and is not an empty directory.`
- **원인:** 파일 검색 결과만으로 저장소 디렉터리 부재를 단정해 clone을 시도함.
- **영향:** clone 명령은 실패했으나 기존 파일과 Git 이력은 변경되지 않음.
- **해결:** 삭제·덮어쓰기·재클론 없이 기존 checkout의 remote, branch, clean 상태와 upstream 차이를 확인함.
- **검증:** `main`과 `origin/main`의 좌우 commit 차이가 `0 0`이고 작업 트리가 clean임을 확인함.
- **재발 방지:** clone 전에 대상 경로 자체와 `.git` 존재 여부를 직접 확인하고, 기존 checkout이면 fetch/status로 최신성을 검증한다.
- **남은 사용자 조치:** 없음.
- **상태:** `Resolved`

### 2. 활성 실행 계획 index와 실제 파일 불일치

- **원문/관찰:** `docs/exec-plans/active/README.md`는 `0002`만 연결하지만 active 디렉터리에는 `0008`, `0012`, `0013`, `0014`도 존재함. `0013`의 구현 TODO는 모두 완료됐지만 상태는 `진행 중`임.
- **원인:** 기능별 구현 후 active index와 계획 lifecycle 정리가 같은 변경에서 수행되지 않음.
- **영향:** 다음 작업과 단일 활성 milestone이 불명확하고 완료 작업의 중복 착수 위험이 있음.
- **해결:** Discord 작업의 단일 진입점 `docs/ROADMAP.md`를 추가하고 D-003에서 계획 lifecycle 정리를 명시함.
- **검증:** 보드에서 정확히 하나의 milestone만 `Picked Up`이며 완료·차단 작업이 분리됨.
- **재발 방지:** 기능 검증 후 실행 계획 상태, active index, 기술 부채를 같은 commit에서 대조한다.
- **남은 사용자 조치:** 없음.
- **상태:** `Mitigated` — active 계획 파일 정리는 D-003에 남아 있음.

### 3. 로컬 Git 작성자 설정 누락

- **원문/관찰:** `Author identity unknown`, `fatal: unable to auto-detect email address`로 검증된 문서 commit이 중단됨.
- **원인:** checkout의 repository-local 및 현재 사용자 global Git config에 `user.name`, `user.email`이 없었음.
- **영향:** 파일과 staging은 보존됐고 commit object만 생성되지 않음.
- **해결:** 최근 저장소 commit의 작성자 `yjs000` 정보를 확인해 이 저장소의 local config에만 동일한 이름과 이메일을 설정함.
- **검증:** 동일 staged diff를 재검사한 뒤 commit 생성 여부와 working tree를 확인함.
- **재발 방지:** 첫 commit 전에 `git config --get user.name`, `git config --get user.email`을 preflight한다. 다른 저장소에 영향을 주는 global 설정은 임의 변경하지 않는다.
- **남은 사용자 조치:** 없음.
- **상태:** `Resolved`

### 4. `main` Python CI의 전 테스트 수집 실패

- **원문/관찰:** 최신 CI Python job에서 `ModuleNotFoundError: No module named 'app'`로 28개 모듈이 수집 실패했고 최근 run이 연속 실패함.
- **원인:** workflow가 저장소 루트에서 pytest를 실행하면서 `apps/api`를 import path에 넣지 않았고 `apps/api/pyproject.toml`의 `asyncio_mode=auto`도 로드하지 않음.
- **영향:** Web job은 통과하지만 Python suite, collector 검사와 문서 검사가 항상 중단되어 `main`의 품질 상태를 신뢰할 수 없음.
- **해결:** Python job에 `PYTHONPATH=apps/api:packages/law-rag-core/src`를 설정하고 pytest에 `-c apps/api/pyproject.toml`을 명시함.
- **검증:** 수정 전 import 해결만으로는 async 4건 실패를 재현했고, 설정 파일까지 명시한 CI 동일 명령에서 207건 통과를 확인함.
- **재발 방지:** 로컬 대표 검증과 CI가 같은 import path·pytest config를 사용하게 유지하고 workflow 변경 시 루트 checkout에서 명령을 그대로 재현한다.
- **남은 사용자 조치:** PR CI에서 GitHub-hosted runner 결과 확인.
- **상태:** `Mitigated` — 로컬 재현은 통과했고 원격 CI 확인이 남음.

### 5. 임시 PostgreSQL 검증 harness 실행 실패

- **원문/관찰:** 초기 검증에서 `execute_code` 승인 차단, system Python의 `ModuleNotFoundError: alembic`, statement 구분자 누락 SQL syntax error, readiness 직후 `ConnectionResetError`, 로컬 5432 port 충돌, 신규 통합 테스트 SQL 5줄의 Ruff E501이 순서대로 발생함.
- **원인:** 임시 builder가 프로젝트 `uv` 환경과 statement 경계를 처음부터 보존하지 않았고 container 안정화·로컬 port 선점 확인이 부족했다. 새 테스트의 긴 SQL ACL 호출도 100자 제한을 넘었음.
- **영향:** 초기 시도에서는 migration 전체 gate가 완료되지 않았고 Production이나 저장소 데이터는 변경되지 않음. 임시 Docker DB만 사용 후 삭제함.
- **해결:** 검사 가능한 임시 파일과 일반 terminal, `uv run --project apps/api`, statement 구분자, container 안정화, 로컬 대체 port 55432를 사용하고 SQL ACL 호출을 여러 줄로 정리함.
- **검증:** PostgreSQL 16·17 임시 container와 보존된 CI 통합 테스트에서 동시 저장·cascade·대화 재집계·ACL·미래 cutoff·멱등성·downgrade가 통과했고, 최종 API/core 210건·Ruff·문서 검사가 통과함.
- **재발 방지:** 프로젝트 Python 의존 코드는 처음부터 해당 `uv --project`로 실행하고 migration statement를 materialize할 때 statement 경계를 보존한다.
- **남은 사용자 조치:** 없음.
- **상태:** `Resolved`

### 6. 외부 Claude 독립 review 시작 실패

- **원문/관찰:** review-only `claude -p`가 `Your organization does not have access to Claude`로 종료됨.
- **원인:** 현재 Claude CLI 인증 조직에 모델 접근 권한이 없음.
- **영향:** 외부 reviewer는 시작되지 않았고 저장소 파일은 변경되지 않음.
- **해결:** 외부 CLI 재로그인이나 credential 요청 없이 Hermes 격리 reviewer로 대체한다.
- **검증:** 명령 exit code 1과 review 산출물·파일 변경 없음 확인.
- **재발 방지:** 외부 CLI review 전에 `auth status` 또는 최소 read-only probe로 사용 가능성을 확인하고 실패 시 configured delegation을 사용한다.
- **남은 사용자 조치:** 없음.
- **상태:** `Expected/Mitigated`

### 7. Retention과 새 질문 저장의 conversation 경합

- **원문/관찰:** 독립 review에서 purge가 만료 질문만 잠근 뒤 대화를 재집계·삭제해, 동시 새 턴 저장의 요약을 덮어쓰거나 빈 대화 삭제 cascade로 새 미만료 턴을 삭제할 수 있음을 확인함.
- **원인:** purge끼리의 advisory lock과 질문 row lock만 있었고 정상 저장 경로가 먼저 갱신하는 conversation row를 같은 순서로 잠그지 않았음. export 삭제 수도 실제 삭제가 아닌 사전 count였음.
- **영향:** Production 적용 시 활성 대화의 최신 턴 데이터 손실과 감사 수 과대계상 가능성이 있었음. 아직 migration을 Production에 적용하지 않아 실제 사용자 데이터 영향은 없음.
- **해결:** 영향 conversation을 ID 순서로 `FOR UPDATE`한 뒤 질문/export를 정리하고, export는 `DELETE ... RETURNING`으로 실제 삭제 수를 기록함. `PUBLIC`, `anon`, `authenticated`의 table·sequence·function 권한도 명시적으로 회수함.
- **검증:** PostgreSQL 17에서 정상 저장 경로의 conversation lock을 먼저 잡은 상태로 purge를 병행해 purge가 대기함을 확인했고, commit 뒤 새 미만료 턴 보존·요약 일치·만료 질문/export 각 1건 삭제·ACL·멱등성·미래 cutoff·downgrade 통합 테스트가 통과함.
- **재발 방지:** DB 정리 작업은 관련 정상 write path와 동일한 row lock 순서를 사용하고, 실제 PostgreSQL 동시성·catalog ACL 검증을 CI release gate로 유지한다.
- **남은 사용자 조치:** Production 적용 전 대상 Supabase catalog ACL과 scheduler wrapper를 승인·검증해야 함.
- **상태:** `Mitigated` — 로컬/CI 계약은 보완했고 immutable SHA 재review와 원격 CI가 남음.

### 8. NULL cutoff의 비감사 NOT NULL 오류

- **원문/관찰:** 독립 review에서 `purge_expired_question_history(NULL)`이 감사 INSERT의 NOT NULL 위반으로 종료되고 명시적 입력 오류나 감사 행을 남기지 않음을 확인함.
- **원인:** NULL 입력 계약이 없고 검증보다 `history_retention_runs(cutoff_at)` INSERT가 먼저 실행됨.
- **영향:** 잘못된 scheduler 호출의 원인이 schema 내부 오류로만 보이고 문서의 “각 실행 감사” 표현과 불일치함. Production 미적용 상태라 사용자 데이터 영향은 없음.
- **해결:** NULL을 유효 retention 실행이 아닌 입력 오류로 정의하고 감사 INSERT 전에 SQLSTATE `22023`으로 거부함.
- **검증:** PostgreSQL 17에서 NULL 호출이 `22023`을 반환하고 감사 행 수가 증가하지 않으며, 미래 cutoff 실패 감사와 정상 실행은 기존 계약대로 동작함을 확인함.
- **재발 방지:** 함수 경계의 invalid input과 접수된 실행 실패를 구분해 schema·테스트·운영 문서에 함께 고정한다.
- **남은 사용자 조치:** 없음.
- **상태:** `Mitigated` — 로컬/CI 계약은 보완했고 immutable SHA 재review와 원격 CI가 남음.

## 검증 체크리스트

- [ ] 사건별 날짜, 관찰, 원인, 영향, 해결/완화, 검증, 재발 방지, 상태가 있다.
- [ ] credential과 개인 원문은 `REDACTED` 처리했다.
- [ ] 새 증거는 중복 사건 대신 기존 사건에 반영했다.
- [ ] `Open`·`Mitigated` 사건의 남은 조치를 명시했다.
- [ ] Markdown 링크와 `git diff --check`를 검증했다.
