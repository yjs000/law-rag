# Worktree 운영 정책

이 문서는 작업마다 현재 Git 위치를 명확히 하고, 읽기 전용 검토가 생성 파일이나 다른 task의 인덱스를
바꾸지 않게 하며, 완료되거나 버려진 worktree를 안전하게 정리하는 기준을 정의한다.

## 작업 위치 선언

모든 task는 파일 읽기나 명령 실행 전에 다음을 확인한다.

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse --short HEAD
git status --short --branch
git worktree list --porcelain
```

첫 진행 보고에 아래 형식으로 한 번 선언한다. worktree, branch 또는 `HEAD`가 작업 중 바뀌면 쓰기를
중단하고 다시 선언한다.

```text
작업 위치: root=<absolute repository root>
worktree=<absolute current worktree path>
branch=<branch or detached>
HEAD=<short commit>
purpose=<이번 task의 한 줄 목적>
integration_target=<통합 대상 branch>
graph_mode=<off|read-only|integration-update>
```

`main` checkout은 통합·최종 검증 소유자가 사용한다. 병렬 구현 task는 각각 별도 branch worktree를
사용한다. 한 task가 다른 task의 worktree에서 수정·stage·commit하지 않는다.

## 읽기 전용 계약

읽기 전용 검토는 시작과 종료의 `git status --short --branch`가 같아야 한다. 다음 동작은 읽기 전용으로
취급하지 않는다.

- 파일 생성·수정·삭제 또는 Git index 변경
- formatter, renderer, generator, hook, dependency sync 실행
- stale 상태를 자동 복구하거나 결과를 캐시·기록하는 CLI 실행
- `graphify update`와 자동 갱신 가능성이 있는 `graphify query`, `graphify path`, `graphify explain`

Graphify가 필요한 읽기 전용 검토에서는 기존 `graphify-out/graph.json`을 직접 읽는 traversal만 사용한다.
Graphify CLI 갱신은 통합 대상 branch에서 소스 통합 뒤 한 번만 실행한다. 명령이 예상 밖 파일을 바꾸면
추가 복구 명령을 연쇄 실행하지 말고, 시작 snapshot과 현재 상태를 비교해 현재 task가 만든 파일만
식별한다. 다른 task가 같은 checkout을 변경 중이면 즉시 쓰기를 중단한다.

## Worktree 분류

`git worktree list --porcelain`의 각 항목을 다음 중 하나로 분류한다.

- `Current`: 현재 task가 실행 중인 worktree. 제거 금지.
- `Active`: 활성 Codex task 또는 진행 중인 계획과 연결됨. 제거 금지.
- `Keep`: dirty, 접근 오류, 미병합 commit, 미확인 untracked 파일, lock 또는 실행 중 프로세스가 있음.
- `Review`: detached이거나 소유 task를 확인할 수 없음. 사용자 확인 전 제거 금지.
- `Removable`: 아래 제거 조건을 모두 통과함.

병합 여부만으로 `Removable`로 판정하지 않는다. 병합된 branch라도 작업 파일이나 untracked 결과가 남을
수 있다. `Permission denied` 때문에 전체 상태를 읽지 못한 worktree는 `Keep`으로 판정한다.

## 제거 조건과 절차

worktree는 다음 조건을 모두 만족할 때만 제거 후보가 된다.

1. 현재 worktree가 아니다.
2. 활성 Codex task, 실행계획 또는 사용자가 보존하라고 한 작업과 연결되지 않는다.
3. tracked·staged·untracked 변경이 없고 상태 확인 중 접근 오류가 없다.
4. branch worktree는 모든 필요한 commit이 통합 대상 branch에 포함됐거나 사용자가 폐기를 승인했다.
5. detached worktree는 연결된 Codex task가 종료됐고 보존할 commit·artifact가 없음을 확인했다.
6. 실행 중인 프로세스, lock, 별도 worktree 전용 자격 증명이나 외부 상태가 없다.

정리 전 후보별로 절대 경로, branch/detached 상태, `HEAD`, dirty 여부, 통합 여부, 연결 task를 표로
제시한다. 사용자가 정확한 대상을 승인하면 다음 순서로 진행한다.

1. `git worktree remove <absolute-path>`를 `--force` 없이 실행한다.
2. 제거 후 `git worktree list --porcelain`로 등록 해제를 확인한다.
3. branch 삭제는 worktree 제거와 별도 작업으로 취급하고 다시 범위와 필요성을 확인한다.
4. `git worktree prune --dry-run` 결과를 먼저 확인하고, stale metadata 정리가 승인된 경우에만 prune한다.

재귀 파일 삭제로 worktree 디렉터리를 직접 지우지 않는다. `--force`, 미병합 branch 삭제, dirty
worktree 제거는 파괴적 예외이며 정확한 대상과 손실 내용을 사용자가 별도로 승인해야 한다.

Windows 저장소는 긴 검증 cache 경로 때문에 정상 제거가 중단되지 않도록 repository-local
`core.longpaths=true`를 사용한다. `git worktree remove`가 등록과 `.git` marker는 제거했지만
`Filename too long`으로 디렉터리만 남긴 경우에는 예외적으로 절대 경로가 `.worktrees` 바로 아래의 승인
대상인지, worktree 목록에 없고 `.git` marker도 없는지 다시 확인한 뒤 그 orphan만 확장 경로로 제거한다.

## 현재 감사 기준선 (2026-09-17)

정책 작성 시 등록된 worktree는 10개였다. 이 중 tracked 변경이 있는 항목, main 미병합 branch,
detached Codex 관리 worktree가 모두 존재했고, 일부 상태 확인에서는 pytest/tmp 경로 접근 오류가
발생했다. 따라서 이 기준선만으로 안전하게 자동 삭제할 수 있는 worktree는 확정하지 않는다. 실제 정리는
각 후보를 다시 감사하고 활성 task 연결을 확인한 뒤 수행한다.

## Git hook과 Graphify 실행

Git hook은 공통 Git directory에 설치되므로 primary checkout과 연결 worktree가 같은 정책을 사용한다.
Roadmap pre-commit은 staged 경로가 실행계획 또는 `docs/ROADMAP.md`일 때만 읽기 전용 checker를 실행한다.

```powershell
.\scripts\run_python.ps1 scripts/install_git_hooks.py
.\scripts\run_python.ps1 scripts/install_git_hooks.py --disable-graphify-auto-hooks
```

두 번째 명령은 `graphify-hook-start` 또는 `graphify-checkout-hook-start` marker가 있는
`post-commit`·`post-checkout`만 각각 `*.graphify-disabled`로 이동한다. 다른 hook은 변경하지 않으며,
시작 marker가 shebang 바로 뒤에 있고 대응하는 끝 marker가 파일의 마지막 줄인 완전한 Graphify 관리
hook만 대상으로 한다. 사용자 명령이 앞뒤에 있는 복합 hook은 거부한다. 모든 대상과 backup 충돌을 먼저
검사한 뒤 변경하므로 중간 상태를 남기지 않으며, 기존 backup과 내용이 다르면 덮어쓰지 않고 실패한다.
복구할 때는 활성 hook 이름이 비어 있고 backup의 marker가 맞는지 확인한 뒤 원래 이름으로 되돌린다.

Graphify CLI는 사용자의 명시 요청 또는 통합 branch의 소스 통합 뒤에만 실행한다. 기능 worktree에서는
`graphify update/query/path/explain`을 실행하지 않고, 필요 시 추적된 JSON을 직접 읽는다.
통합 branch에서 소스 통합 직후 실행하는 정확한 명령 `graphify update .`와 필요한 Windows 권한 상승은
지속 승인 범위다. 에이전트는 다시 묻지 않고 실행하되, 기능 worktree·`graphify label`·외부 LLM/API·
예상 밖 파일 변경은 이 승인에 포함하지 않는다. 플랫폼 runtime gate가 표시되면 저장소 문서로 우회하지
않고 해당 gate를 그대로 따른다.

## 권한 계약

| Boundary | Destination or resource | Operation | Data/credential involved | Mutation/retention | Purpose | Status and date | Runtime gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 위치·상태 감사 | 등록된 local worktree | Git metadata와 status 읽기 | 경로·branch·commit hash | 없음 | 분류와 충돌 방지 | Not required — 2026-09-17 | 접근 오류 시 `Keep`으로 중단 |
| 정책 작성 | `AGENTS.md`, `docs/PLANS.md`, 이 문서 | 문서 생성·수정 | 없음 | repository 문서 변경 | 운영 계약 고정 | Approved — 2026-09-17 사용자 요청 | 저장소 검증과 diff 확인 |
| 읽기 전용 Graphify | `graphify-out/graph.json` | 직접 읽기 | 코드·문서 graph metadata | 없음 | 구조 질의 | Approved — 2026-09-17 사용자 요청 범위 | CLI 자동 갱신 금지 |
| Graphify 자동 hook 비활성화 | common Git hooks directory | marker hook 백업·비활성화 | repository content metadata | local hook 이름 변경 | 읽기·commit 부작용 제거 | Approved — 2026-09-17 사용자 요청 | marker와 backup 충돌 검사 |
| Graphify 갱신 | 통합 대상 branch의 `graphify-out/` | `graphify update .` 및 필요한 Windows 권한 상승 | repository content | 추적 산출물 변경 | 통합 후 graph 일치 | Approved — 2026-09-17 사용자 지속 승인 | 소스 통합 직후 1회, 기능 worktree·label·외부 LLM 제외, platform gate 유지 |
| worktree 제거·prune | 승인된 정확한 local path | 등록 해제·디렉터리 제거 | local files | 파괴적, 복구 비용 있음 | 불필요 worktree 정리 | Approved — 2026-09-17 사용자 요청 | clean·merged·inactive 후보만 |
| branch 삭제 | 승인된 정확한 local branch | ref 삭제 | commit history | 미병합 시 손실 가능 | 종료 branch 정리 | Not required — 현재 정책 작업 | worktree 제거와 별도 승인 |
| 외부 네트워크·서비스 | 없음 | 없음 | 없음 | 없음 | 정책 작성에 불필요 | Not required — 2026-09-17 | 사용하지 않음 |

## 결정 기록

- 2026-09-17: 사용자가 현재 worktree를 명시하고 불필요 worktree의 안전한 제거 정책을 만들며,
  읽기 전용 검토에서 Graphify 자동 갱신으로 복구 시간이 발생하지 않게 해 달라고 요청했다. 이에 따라
  위치 선행 선언, read-only 무변경 계약, 자동 삭제 금지, 후보별 승인, 통합 branch 단일 Graphify 갱신을
  채택했다.
- 2026-09-17: clean·병합·비활성 후보 하나의 제거 중 Windows 긴 경로로 Git 등록만 해제되는 사례를
  확인했다. `core.longpaths=true`와 엄격히 검증된 orphan 정리 예외를 추가했다.
- 2026-09-17: 사용자가 통합 branch의 `graphify update .`와 필요한 권한 상승을 항상 승인하도록
  저장소에 기록해 달라고 요청했다. 정확한 update 명령만 지속 승인하고 기능 worktree, label, 외부
  LLM/API 및 예상 밖 변경은 제외했다.
