# 작업 관리 메타데이터와 얇은 로드맵 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> 작업 ID: `DOC-001`
> 상태: `Picked Up`
> 유형: `Documentation`
> 보조 라벨: 없음
> 선행 조건: [설계 승인](../../design-docs/task-management-metadata-and-roadmap.md)
> 참고 범위:
> - `docs/design-docs/task-management-metadata-and-roadmap.md` L19-L83 — 메타데이터·로드맵·검증의 승인된 계약
> - `AGENTS.md` L14-L25, L77-L96 — 세션 시작과 Discord 전용 로드맵 제한
> - `docs/PLANS.md` L9-L25, L42-L46 — 계획 lifecycle과 새 계획 형식

**Goal:** 모든 작업 관리 문서에 단일 상태·유형·ID·참고 범위 계약을 적용하고, 로드맵을 현재 milestone 우선의 얇은 링크 색인으로 전환한다.

**Architecture:** `docs/PLANS.md`가 실행계획 메타데이터와 상태 전이의 권위 문서가 된다. `docs/ROADMAP.md`는 세부 내용을 복사하지 않고 각 실행계획의 현재 상태를 링크하며, `CURRENT_STATE.md`는 첫 진입 위치만 알려 준다. GitHub는 수동 라벨 용어만 매핑하고 저장소와 자동 동기화하지 않는다.

**Tech Stack:** Markdown, Git, PowerShell read-only 문서 검증 명령.

**Spec:** `docs/design-docs/task-management-metadata-and-roadmap.md`

## Global Constraints

- 작업 관리 문서만 메타데이터 대상이며 설계·제품·학습 문서에는 붙이지 않는다.
- 상태는 `Todo`, `Picked Up`, `Blocked`, `Done` 중 하나이며 `Picked Up`은 정확히 0개 또는 1개다.
- 유형은 `Feature`, `Bug`, `Tech Debt`, `Experiment`, `Operations`, `Documentation` 중 하나이며, 작업 ID는 유형별 독립 시퀀스다.
- 새 문서와 상태 전이 문서에는 `작업 ID`, `상태`, `유형`, `보조 라벨`, `선행 조건`, `참고 범위`를 둔다.
- 기존 파일명 숫자와 역사 `D-*` ID는 보존한다. 완료 실행계획 전체를 소급 편집하지 않는다.
- 로드맵은 `Picked Up → Todo → Blocked → Done` 순서의 링크 색인이며 `Done`은 최근 10개만 표시한다.
- GitHub Issue/Project와 저장소 문서는 자동 동기화하지 않는다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `AGENTS.md` | 공통 로드맵의 적용 범위와 세션 시작 순서를 선언한다. |
| `docs/PLANS.md` | 실행계획 메타데이터, 상태·유형·ID, 참조 줄 범위, lifecycle을 정의한다. |
| `docs/GITHUB_WORKFLOW.md` | 저장소 유형과 수동 GitHub 이슈 라벨의 대응을 정의한다. |
| `docs/CURRENT_STATE.md` | 세션 시작에서 Picked Up 또는 첫 Todo로 가는 짧은 포인터를 제공한다. |
| `docs/ROADMAP.md` | 현재 상태별 링크와 한 줄 다음 행동만 보이는 전역 색인이다. |
| `docs/exec-plans/*/README.md` | 각각 pending, active artifact, historical completed archive의 폴더 색인이다. |
| `docs/exec-plans/{todo,active}/*.md` | 현재 계획의 표준 메타데이터와 필요한 최소 참조 범위를 보관한다. |

### Task 1: 공통 작업 관리 계약을 권위 문서에 반영

**Files:**
- Modify: `AGENTS.md:14-25,77-96`
- Modify: `docs/PLANS.md:9-46`
- Modify: `docs/GITHUB_WORKFLOW.md:9-22`
- Modify: `docs/CURRENT_STATE.md:1-27`

**Interfaces:**
- Consumes: 설계의 메타데이터 계약과 로드맵 역할 (`docs/design-docs/task-management-metadata-and-roadmap.md:19-83`).
- Produces: 모든 작업 관리 문서가 사용할 공통 상태·유형·ID·참고 범위 정의와 세션 시작 포인터.

- [ ] **Step 1: 현재 계약이 Discord 보드와 로컬 exec-plan lifecycle을 분리하는지 확인한다.**

Run:

```powershell
rg -n "Discord 전용|작업 상태 계약|GitHub 프로젝트|세션 시작" AGENTS.md docs/PLANS.md docs/CURRENT_STATE.md
```

Expected: `AGENTS.md`는 `ROADMAP.md`를 Discord 전용으로 제한하고, `PLANS.md`는 디렉터리 lifecycle만 정의한다.

- [ ] **Step 2: `AGENTS.md`의 Discord 전용 오버레이를 오류 ledger 한정으로 바꾸고, 공통 `ROADMAP.md`와 `PLANS.md`를 권위 문서에 연결한다.**

Replace the second Discord-overlay bullet with text that excludes only `discord-agents.md` and `docs/operations/discord-error-ledger.md` outside thread `1528216345924337805`; do not exempt `docs/ROADMAP.md`. Add `docs/ROADMAP.md` as the current-priority index in the authoritative-documents list. In startup step 5, read the roadmap's `Picked Up` entry first and the linked plan only when resuming it; when there is no `Picked Up`, use the first `Todo` entry.

- [ ] **Step 3: `docs/PLANS.md`에 표준 메타데이터와 이중 상태 의미를 추가한다.**

Insert a `## 작업 관리 메타데이터` section after `## 위치` containing the six required header fields, the four states, six primary types, allowed secondary labels, type prefixes, and the line-range maintenance rule. Keep `todo/active/completed` as the artifact lifecycle in `## 작업 상태 계약`, and explicitly say a plan with prior history can label its next milestone `Todo`.

- [ ] **Step 4: GitHub 라벨 문서를 저장소 유형과 수동으로 맞춘다.**

Change the issue-label table to six exclusive type labels plus optional `status: blocked`:

```md
| `type: bug` | `Bug` — 오류 또는 회귀 |
| `type: feature` | `Feature` — 사용자 기능 또는 내부 개선 |
| `type: tech-debt` | `Tech Debt` — 확인된 부채의 해결 |
| `type: experiment` | `Experiment` — 측정·판정이 목표인 실험 |
| `type: operations` | `Operations` — credential·운영환경·배포 준비 |
| `type: docs` | `Documentation` — 문서만 변경 |
```

Retain the existing requirement that `status: blocked` needs a stated reason and release condition; state that GitHub Project status remains authoritative for GitHub and no automatic synchronization is introduced.

- [ ] **Step 5: `CURRENT_STATE.md`를 얇은 세션 포인터로 정리한다.**

Keep the initial `AGENTS.md` and `CURRENT_STATE.md` read requirement. Replace the detailed D-010 paragraph with a direct link to `docs/ROADMAP.md`, saying to open `Picked Up` first and otherwise the first `Todo`. Preserve the conditional-reading guidance and state that the roadmap is an index, not a request to read all plans.

- [ ] **Step 6: 계약 문구를 검증한다.**

Run:

```powershell
rg -n "Picked Up|Tech Debt|type: experiment|자동 동기화|참고 범위" AGENTS.md docs/PLANS.md docs/GITHUB_WORKFLOW.md docs/CURRENT_STATE.md
```

Expected: all four documents contain the applicable contract term; no statement leaves `ROADMAP.md` Discord-only.

- [ ] **Step 7: 계약 문서 변경을 커밋한다.**

```powershell
git add AGENTS.md docs/PLANS.md docs/GITHUB_WORKFLOW.md docs/CURRENT_STATE.md
git commit -m "docs: define task tracking contract"
```

### Task 2: 현재 실행계획에 메타데이터를 최소 이행

**Files:**
- Modify: `docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md:1-40`
- Modify: `docs/exec-plans/active/0055-v3-langgraph-agent-foundation.md:1-44`
- Modify: `docs/exec-plans/todo/0012-distributed-question-cancellation.md:1-40`
- Modify: `docs/exec-plans/todo/0029-d-full-gold-on-demand.md:1-40`
- Modify: `docs/exec-plans/todo/0031-eval-harness-consolidation.md:1-44`
- Modify: `docs/exec-plans/todo/0033-traffic-based-routing-calibration-review.md:1-40`
- Modify: `docs/exec-plans/todo/0042-wire-reranking-into-live-search-path.md:1-40`
- Modify: `docs/exec-plans/todo/0044-provider-neutral-answer-model-selection.md:1-40`
- Modify: `docs/exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md:1-40`
- Modify: `docs/exec-plans/todo/0050-query-format-edge-case-regression-bank.md:1-40`
- Modify: `docs/exec-plans/todo/0058-v2-chunking-ablation-d10.md:1-40`

**Interfaces:**
- Consumes: Task 1's header contract and the source plans' current purpose, dependency, and blocker sections.
- Produces: readable current-plan headers without rewriting their historic bodies or completed plans.

- [ ] **Step 1: inspect the first 40 lines of each current plan and record only the references that a worker must read before acting.**

Run:

```powershell
Get-ChildItem docs/exec-plans/active,docs/exec-plans/todo -File -Filter '*.md' |
  Where-Object Name -ne 'README.md' |
  ForEach-Object { "## $($_.FullName)"; Get-Content $_.FullName -TotalCount 40 }
```

Expected: each plan's existing goal, dependency, completion condition, and linked design document are visible without reading the full file.

- [ ] **Step 2: add these exact primary IDs and labels before each plan title.**

| Plan file | ID | Status | Type | Secondary labels |
|---|---|---|---|---|
| `0032-experiment-e-10-ai-answer-evaluation.md` | `E-001` | `Todo` | `Experiment` | `Evaluation` |
| `0055-v3-langgraph-agent-foundation.md` | `F-001` | `Todo` | `Feature` | `Data`, `Reliability` |
| `0012-distributed-question-cancellation.md` | `F-002` | `Todo` | `Feature` | `Reliability` |
| `0029-d-full-gold-on-demand.md` | `E-002` | `Todo` | `Experiment` | `Evaluation` |
| `0031-eval-harness-consolidation.md` | `E-003` | `Todo` | `Experiment` | `Evaluation` |
| `0033-traffic-based-routing-calibration-review.md` | `E-004` | `Todo` | `Experiment` | `Performance`, `Evaluation` |
| `0042-wire-reranking-into-live-search-path.md` | `F-003` | `Todo` | `Feature` | `Evaluation` |
| `0044-provider-neutral-answer-model-selection.md` | `F-004` | `Todo` | `Feature` | `Reliability` |
| `0047-clarification-loop-dedup-and-unanswered-handling.md` | `B-001` | `Todo` | `Bug` | `Reliability`, `UX` |
| `0050-query-format-edge-case-regression-bank.md` | `B-002` | `Todo` | `Bug` | `Evaluation` |
| `0058-v2-chunking-ablation-d10.md` | `E-005` | `Todo` | `Experiment` | `Data`, `Evaluation` |

For each header, write `선행 조건` using the existing blocker or promotion condition. Write one to three `참고 범위` entries with exact `path Lstart-Lend — reason` values selected from the linked design and product documents. Do not create a reference merely for the metadata policy, and do not alter a completed plan.

- [ ] **Step 3: add a header for this plan itself and retain it as the sole `Picked Up` item.**

Keep this plan's `DOC-001`, `Picked Up`, `Documentation` header unchanged while Tasks 1 through 3 are in progress. Its reference ranges are the approved design contract and the existing document boundaries listed at the top of this file.

- [ ] **Step 4: validate the current-plan headers.**

Run:

```powershell
$plans = Get-ChildItem docs/exec-plans/active,docs/exec-plans/todo -File -Filter '*.md' |
  Where-Object Name -ne 'README.md'
$required = '작업 ID:', '상태:', '유형:', '보조 라벨:', '선행 조건:', '참고 범위:'
$missing = foreach ($plan in $plans) {
  $head = (Get-Content $plan.FullName -TotalCount 20) -join "`n"
  $absent = $required | Where-Object { -not $head.Contains($_) }
  if ($absent) { "$($plan.Name): $($absent -join ', ')" }
}
if ($missing) { $missing; exit 1 }
"validated $($plans.Count) current-plan headers"
```

Expected: `validated 12 current-plan headers`; no missing metadata line.

- [ ] **Step 5: commit the header migration.**

```powershell
git add docs/exec-plans/active docs/exec-plans/todo
git commit -m "docs: label current execution plans"
```

### Task 3: 상태별 링크 색인과 폴더 인덱스를 전환

**Files:**
- Modify: `docs/ROADMAP.md:1-35`
- Modify: `docs/exec-plans/active/README.md:1-15`
- Modify: `docs/exec-plans/todo/README.md:1-40`
- Modify: `docs/exec-plans/completed/README.md:1-29`

**Interfaces:**
- Consumes: Task 1 status rules and Task 2 ID/header table.
- Produces: a concise global roadmap with the current documentation milestone as its only `Picked Up` entry and folder indexes that do not duplicate roadmap detail.

- [ ] **Step 1: verify the old roadmap is a long Discord-only table and its links resolve.**

Run:

```powershell
Get-Content docs/ROADMAP.md -TotalCount 40
Test-Path docs/exec-plans/completed/0057-single-stage-router-and-failure-response.md
```

Expected: the old table includes D-001 through D-010, and the D-010 plan path exists.

- [ ] **Step 2: replace the roadmap with the four required status sections.**

Create `# 프로젝트 로드맵` with a short statement that it is the common project entry point and linked plans are authoritative. Add sections in this exact order: `## Picked Up`, `## Todo`, `## Blocked`, `## Done`.

- `Picked Up` contains only `[DOC-001 · Documentation — 작업 관리 메타데이터와 얇은 로드맵](exec-plans/active/0059-task-management-metadata-and-roadmap.md)` and the next action `계약·현재 계획 메타데이터·상태 색인을 반영 중`.
- `Todo` contains the 11 Task 2 plans as links, ordered `E-001`, `F-001`, `F-002`, `E-002`, `E-003`, `E-004`, `F-003`, `F-004`, `B-001`, `B-002`, `E-005`, each with the existing README one-line next action.
- `Blocked` preserves the four external items as legacy IDs: `D-002 · Operations`, `D-004 · Feature`, `D-005 · Operations`, `D-009 · Operations`; each entry links to the existing plan where it exists and carries only its release condition.
- `Done` preserves the latest completed legacy item `D-010 · Feature` linking to 0057, plus at most nine more recent completed items. Do not copy test counts or long implementation results into this index.

- [ ] **Step 3: rewrite folder README files as focused indexes.**

`active/README.md` lists active plan artifacts with each plan's new ID, status, and one-line current next milestone; it does not claim every active artifact is `Picked Up`. `todo/README.md` lists its eleven `Todo` plans with IDs and one-line next actions, retains its registration contract, and links to `ROADMAP.md` for global ordering. `completed/README.md` gains a `## 2026 Q3` recent section and a `## 2026 Q2 및 이전` archive section, retaining every existing plan link without adding headers to the completed plan files.

- [ ] **Step 4: validate status order, link targets, and active-count constraint.**

Run:

```powershell
$roadmap = Get-Content -Raw docs/ROADMAP.md
$positions = '## Picked Up', '## Todo', '## Blocked', '## Done' | ForEach-Object { $roadmap.IndexOf($_) }
if (($positions | Where-Object { $_ -lt 0 }).Count -gt 0 -or $positions -ne ($positions | Sort-Object)) { exit 1 }
$picked = ([regex]::Matches($roadmap, '(?m)^- \[DOC-001 · Documentation')).Count
if ($picked -ne 1) { throw "expected one Picked Up item, got $picked" }
$paths = [regex]::Matches($roadmap, '\]\(([^)#]+)(?:#[^)]*)?\)') | ForEach-Object { $_.Groups[1].Value }
$broken = $paths | Where-Object { -not (Test-Path (Join-Path 'docs' $_)) }
if ($broken) { $broken; exit 1 }
'roadmap sections, Picked Up count, and local links validated'
```

Expected: one `Picked Up` item; section order and all local links validate.

- [ ] **Step 5: commit the roadmap and index migration.**

```powershell
git add docs/ROADMAP.md docs/exec-plans/active/README.md docs/exec-plans/todo/README.md docs/exec-plans/completed/README.md
git commit -m "docs: make roadmap a status index"
```

### Task 4: 완료 상태를 기록하고 문서 검증을 마친다

**Files:**
- Modify: `docs/exec-plans/active/0059-task-management-metadata-and-roadmap.md`
- Move: `docs/exec-plans/active/0059-task-management-metadata-and-roadmap.md` to `docs/exec-plans/completed/0059-task-management-metadata-and-roadmap.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/exec-plans/active/README.md`
- Modify: `docs/exec-plans/completed/README.md`
- Modify: `docs/CURRENT_STATE.md`

**Interfaces:**
- Consumes: completed Tasks 1 through 3 and their validation results.
- Produces: no `Picked Up` entry, a `Done` entry for `DOC-001`, a completed-plan result record, and a start pointer that falls back to the first Todo.

- [ ] **Step 1: record concrete results and any remaining historical limitation in this plan.**

Add a dated result section to this plan: all current `todo/active` plans have headers; completed plans were intentionally not bulk-labeled; the roadmap keeps only a short Done index; and the executed validation commands with outputs are recorded. Do not claim a GitHub label was created or a remote board changed.

- [ ] **Step 2: move the plan and update all indexes atomically.**

Use `git mv` to move this plan to `completed/`. Remove `DOC-001` from `Picked Up`, add it to `Done` with a one-line result, remove it from `active/README.md`, add it to the `2026 Q3` section in `completed/README.md`, and change `CURRENT_STATE.md` to say there is no Picked Up milestone and point to the first Todo.

- [ ] **Step 3: run the full documentation verification.**

Run:

```powershell
$plans = Get-ChildItem docs/exec-plans/active,docs/exec-plans/todo -File -Filter '*.md' |
  Where-Object Name -ne 'README.md'
$required = '작업 ID:', '상태:', '유형:', '보조 라벨:', '선행 조건:', '참고 범위:'
$missing = foreach ($plan in $plans) {
  $head = (Get-Content $plan.FullName -TotalCount 20) -join "`n"
  $absent = $required | Where-Object { -not $head.Contains($_) }
  if ($absent) { "$($plan.Name): $($absent -join ', ')" }
}
if ($missing) { $missing; exit 1 }
$roadmap = Get-Content -Raw docs/ROADMAP.md
if (($roadmap.IndexOf('## Picked Up')) -gt ($roadmap.IndexOf('## Todo')) -or
    ($roadmap.IndexOf('## Todo')) -gt ($roadmap.IndexOf('## Blocked')) -or
    ($roadmap.IndexOf('## Blocked')) -gt ($roadmap.IndexOf('## Done'))) { exit 1 }
([regex]::Matches($roadmap, '(?m)^- \[[^\]]+\]')).Count
'current-plan metadata and roadmap order validated'
git diff --check
```

Expected: zero metadata omissions, the four roadmap sections in order, and no `git diff --check` output.

- [ ] **Step 4: inspect the staged diff and commit the completion transition.**

```powershell
git diff --check
git diff -- docs/ROADMAP.md docs/CURRENT_STATE.md docs/exec-plans/active docs/exec-plans/completed
git add docs/ROADMAP.md docs/CURRENT_STATE.md docs/exec-plans/active docs/exec-plans/completed
git commit -m "docs: complete task tracking rollout"
```