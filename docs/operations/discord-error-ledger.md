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

## 검증 체크리스트

- [ ] 사건별 날짜, 관찰, 원인, 영향, 해결/완화, 검증, 재발 방지, 상태가 있다.
- [ ] credential과 개인 원문은 `REDACTED` 처리했다.
- [ ] 새 증거는 중복 사건 대신 기존 사건에 반영했다.
- [ ] `Open`·`Mitigated` 사건의 남은 조치를 명시했다.
- [ ] Markdown 링크와 `git diff --check`를 검증했다.
