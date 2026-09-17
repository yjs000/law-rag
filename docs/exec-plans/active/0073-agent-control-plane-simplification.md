> 작업 ID: `DOC-003`
> 상태: `Picked Up`
> 유형: `Documentation`
> 보조 라벨: `Reliability`
> 선행 조건: 에이전트 제어면 단순화 설계가 승인되어야 한다.
> 다음 행동: review 수정 뒤 전체 검증과 완료 전이를 수행한다.
> 참고 범위:
> - `docs/design-docs/agent-control-plane-simplification.md` L1-L106 — 승인된 skill·hook·worktree 책임 경계
> - `scripts/install_git_hooks.py` L1-L266 — common hook 설치와 Graphify hook 보존·비활성화 동작
> - `docs/references/worktree-policy.md` L1-L136 — 위치 선언과 안전한 worktree 정리 계약

# 0073: 에이전트 제어면 단순화 실행 계획

## 계획 본문

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 중복 workflow와 자동 상태 변경을 제거하고, 명시적인 작업 위치·skill·hook·worktree 수명주기로 시간과 토큰 소비를 줄인다.

**Architecture:** Superpowers가 일반 구현 workflow를, `roadmap-operator`가 저장소 roadmap adapter를 단독 소유한다. Git hook은 공통 Git directory의 roadmap 정합성 검사만 자동 실행하고 Graphify 갱신은 통합 branch의 명시 단계로 제한한다. 개인 skill과 worktree 정리는 삭제보다 복구 가능한 비활성화와 보수적인 제거 판정을 사용한다.

**Tech Stack:** Python standard library, `unittest`, Git hooks, Markdown, Codex skill metadata.

**Spec:** `docs/design-docs/agent-control-plane-simplification.md`

## Global Constraints

- 제품 runtime과 외부 서비스는 변경하지 않는다.
- 사용자 소유 hook, dirty·미병합·접근 불가 worktree, Codex-managed detached worktree는 보존한다.
- 기능 worktree에서 Graphify를 실행하거나 `graphify-out/`을 commit하지 않는다.
- 개인 skill 변경은 복구 가능하게 보관하고 Graphify 본문은 불필요하게 다시 작성하지 않는다.
- branch 삭제, push, 배포, DB 변경은 하지 않는다.

### Task 1: Worktree-safe roadmap와 hook manager

**Files:**
- Modify: `.gitattributes`
- Modify: `scripts/install_git_hooks.py`
- Modify: `scripts/tests/test_roadmap_registry.py`
- Modify: `docs/ROADMAP.md` (renderer only)

- [x] 연결 worktree에서도 common Git hooks directory를 선택하고 marker가 확인된 Graphify hook만 백업·비활성화하는 실패 테스트를 작성한다.
- [x] focused test가 기존 구현에서 실패하는 것을 확인한다.
- [x] 최소 구현과 `docs/ROADMAP.md text eol=lf` checkout 계약을 추가한다.
- [x] focused test와 새 worktree의 read-only roadmap checker를 통과시킨다.

### Task 2: Skill과 harness 책임 단일화

**Resources:**
- Modify: `C:/Users/Family/.codex/skills/graphify/agents/openai.yaml`
- Move: `picked-up-plan-runner`, `work-issue`, `writing-roadmap-scoped-plans` to a dated disabled-skill archive
- Remove: installed `agent-operating-harness` plugin

- [x] Graphify skill의 implicit invocation 금지 metadata를 생성하고 skill validator로 확인한다.
- [x] 세 중복 skill을 날짜가 붙은 복구 가능한 보관 위치로 이동한다.
- [x] 활성 도구를 제공하지 않는 중복 harness plugin을 제거한다.
- [x] 활성 skill 목록과 보관 목록을 다시 검사한다.

### Task 3: 권위 문서와 운영 명령 정리

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/references/worktree-policy.md`
- Modify: `docs/PLANS.md`
- Modify: `scripts/install_git_hooks.py`

- [x] AGENTS의 중복 workflow 설명을 정본 포인터로 축약하고 Graphify 명시 실행 계약을 일치시킨다.
- [x] hook 설치·Graphify 자동 hook 비활성화 절차와 rollback을 reference 문서에 기록한다.
- [x] common hooks에 roadmap pre-commit을 설치하고 marker Graphify hook을 백업·비활성화한다.
- [x] 문서 link와 roadmap checker를 실행한다.

### Task 4: 보수적인 worktree 정리

**Targets:**
- Candidate: `.worktrees/codex-gold100-evaluation-registry`
- Candidate: `.worktrees/codex-repair-qa-network-errors`

- [x] 제거 직전에 각 후보가 clean, merged, inactive이고 접근 오류가 없는지 다시 검사한다.
- [x] 조건을 모두 만족하는 후보만 `git worktree remove`로 제거하고 branch는 보존한다.
- [x] `git worktree list --porcelain`과 잔여 worktree 상태를 확인한다.

### Task 5: 통합 검증과 완료 전이

**Files:**
- Modify: 이 계획의 체크박스·결과 기록과 lifecycle 위치
- Modify: `docs/ROADMAP.md` (renderer only)

- [ ] focused Python test, roadmap checker, 문서 검사, 전체 `scripts/verify.ps1`을 실행한다.
- [ ] 최종 diff와 민감정보·의도치 않은 Graphify 산출물 부재를 검토한다.
- [ ] whole-branch review를 수행하고 발견된 문제를 수정·재검증한다.
- [ ] 결과와 잔여 작업을 기록하고 계획을 `completed/`로 이동한 뒤 roadmap을 재생성한다.

## 결과 기록

- `codex-repair-qa-network-errors`는 clean·main 병합·비활성 조건을 통과해 worktree만 제거하고 branch는
  보존했다. Git 등록 해제 뒤 Windows `Filename too long`으로 남은 orphan은 절대 경로·등록 부재·`.git`
  marker 부재를 재검증한 뒤 제거했고 repository-local `core.longpaths=true`를 설정했다.
- `codex-gold100-evaluation-registry`는 대량의 untracked 검증 cache·Graphify 로컬 상태와 접근 오류가 있어
  `Keep`으로 분류하고 변경하지 않았다. 다른 dirty·미병합·활성·Codex-managed worktree도 보존했다.
