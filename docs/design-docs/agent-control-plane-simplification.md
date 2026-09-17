# 에이전트 제어면 단순화

상태: 승인

## 문제

현재 저장소의 작업 지침은 각각 타당하지만, 일반 구현 workflow를 지시하는 개인 skill과 프로젝트
skill이 겹친다. 또한 Graphify의 광범위한 자동 호출과 Git `post-commit`·`post-checkout` hook이
읽기 전용 검토 중에도 추적 파일을 갱신해 원복과 재검증 비용을 만든다. 연결 worktree에서는 hook
설치 위치가 worktree 전용 Git 디렉터리로 계산되어 공통 hook이 설치되지 않는 문제도 있다.

## 목표

- 구현 workflow의 소유자를 Superpowers 하나로 제한한다.
- 프로젝트별 roadmap 선택·상태 전이는 `roadmap-operator`만 담당하게 한다.
- Graphify는 사용자가 명시적으로 요청하거나 통합 브랜치에서 갱신할 때만 실행한다.
- 자동화는 부작용 없는 정합성 검사에만 사용한다.
- 작업 시작 시 실제 checkout, branch, 목적, 통합 대상을 명시하고 안전하게 worktree를 정리한다.
- 권위 문서의 중복을 줄여 세션 시작 토큰과 판단 분기를 줄인다.

## 비목표

- 제품 코드, 법률 검색 품질, 데이터베이스 또는 배포 동작을 바꾸지 않는다.
- dirty, 미병합, 접근 불가 또는 Codex가 관리하는 detached worktree를 강제로 제거하지 않는다.
- 원격 branch 삭제, push, 배포 또는 외부 서비스 변경을 수행하지 않는다.

## 선택한 구조

### Workflow와 skill

| 책임 | 정본 | 처리 |
|---|---|---|
| 구현의 설계·계획·TDD·리뷰·검증 | Superpowers | 유지 |
| 프로젝트 roadmap 선택·전이 | `roadmap-operator` | 유지하고 범위를 좁게 유지 |
| 장기 세션 인계 | `session-handoff` | 유지 |
| 화면 증거, wiki, 명시적 빠른 모드, artifact template | 각 전용 skill | 유지 |
| 계획 자동 선택·실행 | `picked-up-plan-runner` | 탐색 경로 밖으로 이동 |
| issue 시작·재개·완료 | `work-issue` | 탐색 경로 밖으로 이동 |
| roadmap 기반 계획 작성 | `writing-roadmap-scoped-plans` | 탐색 경로 밖으로 이동 |
| 범용 실행 harness plugin | `agent-operating-harness` | 활성 도구가 없고 workflow와 중복되므로 제거 |
| 코드 그래프 질의 | `graphify` | implicit invocation을 끄고 명시 호출만 허용 |

비활성화하는 개인 skill은 삭제하지 않고 날짜가 붙은 보관 디렉터리로 이동해 되돌릴 수 있게 한다.

### Git hook

- `post-commit`과 `post-checkout`의 Graphify 자동 갱신 hook은 marker를 확인한 뒤 백업하고
  비활성화한다. 사용자 소유 hook은 덮어쓰거나 삭제하지 않는다.
- roadmap 정합성 검사는 staged plan 또는 `docs/ROADMAP.md`가 포함된 commit에서만 실행하는
  `pre-commit` hook으로 유지한다.
- 연결 worktree에서도 공통 hook 디렉터리를 사용하도록 `git rev-parse --git-common-dir`를 기준으로
  설치한다.
- Graphify 갱신은 기능 branch 통합 후 통합 대상 branch에서 명시적으로 한 번 실행한다.

### 생성 문서 줄바꿈

`docs/ROADMAP.md`는 렌더러가 LF byte를 생성한다. `.gitattributes`에서 이 파일을 `text eol=lf`로
고정해 Windows의 새 worktree checkout에서도 byte 비교가 안정적으로 통과하게 한다.

### Worktree 수명주기

모든 작업은 시작 보고에 저장소 root, 실제 worktree, branch/HEAD, 목적, 통합 대상, Graphify 모드를
포함한다. 정리는 `clean + merged + inactive`가 모두 확인된 project-local worktree만 대상으로 하며,
branch는 자동 삭제하지 않는다. 나머지는 보존하고 이유를 기록한다.

### 문서 읽기 경계

루트 `AGENTS.md`에는 항상 적용되는 규칙과 권위 문서 포인터만 유지한다. 조건부 절차의 상세 설명은
`docs/references/`로 옮기고, 해당 작업에서만 읽는다. 같은 workflow를 여러 skill과 문서에서 다시
서술하지 않는다.

## 권한과 외부 의존성

| 자원 또는 동작 | 판정 | 근거 |
|---|---|---|
| 저장소 문서·script·test 수정과 로컬 commit | 승인됨 | 사용자 요청과 저장소의 지속 승인 |
| 세 중복 개인 skill을 보관 디렉터리로 이동 | 승인됨 | 중복 skill 정리 요청 |
| Graphify skill의 명시 호출 metadata 추가 | 승인됨 | 자동 부작용 제거 요청 |
| `agent-operating-harness` plugin 제거 | 승인됨 | 중복 harness 정리 요청 |
| marker가 확인된 Graphify hook 백업·비활성화 | 승인됨 | 자동 갱신 제거 요청 |
| roadmap pre-commit hook 설치 | 승인됨 | 부작용 없는 정합성 자동화 |
| clean·merged·inactive worktree 제거 | 승인됨 | 불필요 worktree 정리 요청 |
| branch 삭제, push, 배포, DB·외부 서비스 변경 | 불필요 | 현재 범위 밖 |

## 검증

- hook manager 단위 테스트로 common Git directory 사용, 기존 hook 보호, Graphify hook 백업의
  멱등성을 검증한다.
- 새 worktree checkout에서 `scripts/check_roadmap.py`가 통과하는지 확인한다.
- 비활성 skill이 기본 skill 탐색 경로에서 사라지고 Graphify metadata가 implicit 호출을 금지하는지
  검증한다.
- 제거 직전에 대상 worktree가 clean, merged, inactive인지 다시 검사한다.
- 저장소 전체 검증과 최종 diff 검토를 수행한다.

## Rollback

- 보관된 skill 디렉터리를 원래 위치로 되돌릴 수 있다.
- 백업된 Graphify hook은 새 사용자 hook이 없을 때만 원래 이름으로 복구할 수 있다.
- 제거한 plugin은 필요 시 다시 설치한다.
- worktree branch는 삭제하지 않으므로 같은 branch에서 worktree를 다시 만들 수 있다.

## 결정 기록

- 2026-09-17: 사용자가 비핵심 선택을 일괄 승인했다. 일반 구현 workflow는 Superpowers,
  프로젝트 상태 adapter는 `roadmap-operator`, Graphify는 명시 실행으로 단일화한다. 자동 hook은
  정합성 검사만 허용하고, 상태를 변경하는 생성 작업은 명시적인 통합 단계로 이동한다.
