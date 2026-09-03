> 작업 ID: `DOC-002`
> 상태: `Todo`
> 유형: `Documentation`
> 보조 라벨: `Reliability`
> 선행 조건: 로드맵 정본·컨텍스트 절약 설계가 승인되어야 한다.
> 다음 행동: 실행계획 헤더 파서와 결정적 renderer의 실패 테스트부터 작성
> 참고 범위:
> - `docs/superpowers/specs/2026-09-03-roadmap-registry-and-context-diet-design.md` L1-L104 — 정본·생성·검사·최소 읽기 요구사항
> - `docs/PLANS.md` L16-L68 — 계획 위치와 상태 lifecycle의 기존 계약
> - `scripts/check_docs.py` L1-L283 — 현재 문서 검사 진입점과 출력 관례

# 0066: 로드맵 정본·컨텍스트 절약 구현 계획

## 계획 본문

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실행계획의 짧은 색인 헤더를 유일한 정본으로 만들고, 결정적인 `ROADMAP.md` 생성·검사·Git 훅·최소 읽기 운영 절차를 제공한다.

**Architecture:** `scripts/roadmap_registry.py`가 계획 색인 헤더를 파싱하고 검증 가능한 불변 모델을 제공한다. `render_roadmap.py`는 그 모델만 사용해 생성물을 쓰며, `check_roadmap.py`는 동일 파서로 원본·lifecycle·참조 범위·현재 생성물 일치를 읽기 전용으로 검증한다. 설치 스크립트는 기존 hooks를 보존하는 작은 pre-commit dispatcher만 추가하고, 운영 스킬은 현재 상태·로드맵·선택한 계획 헤더·명시 범위만 읽도록 문서화한다.

**Tech Stack:** Python 3.14 standard library, `unittest`, Git hooks, GitHub Actions, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-03-roadmap-registry-and-context-diet-design.md`

## Global Constraints

- `docs/exec-plans/{todo,active,completed}/`의 파일명과 lifecycle은 `docs/PLANS.md`의 기존 계약을 유지한다.
- 상태는 `Todo`, `Picked Up`, `Blocked`, `Done`만 허용하고 저장소 전체에서 `Picked Up`은 0개 또는 1개다.
- 유형은 `Feature`, `Bug`, `Tech Debt`, `Experiment`, `Operations`, `Documentation`만 허용하며 기존 `D-*` ID는 역사 기록으로 보존한다.
- `다음 행동`은 한 문장, 120자 이하이며 `참고 범위`는 최대 3개이고 상대 경로·양끝 줄 번호·이유를 모두 가져야 한다.
- `docs/ROADMAP.md`는 생성물이다. 상태·제목·다음 행동을 직접 고치지 않고 실행계획 헤더를 고친 뒤 renderer를 실행한다.
- renderer만 `docs/ROADMAP.md`를 쓸 수 있고 checker는 어떤 파일도 변경하지 않는다.
- 출력에는 계획 본문·개인 데이터·문서 전문을 포함하지 않는다. 성공 출력은 계획 수·`Picked Up` 수·digest만 포함한다.
- 완료 계획의 전체 헤더 이행, GitHub Project 동기화, Epic/Story/Task 계층, 자동 수정·자동 commit은 범위 밖이다.
- 기존 개인 `post-commit` graphify 훅과 `core.hooksPath`를 바꾸지 않는다.

---

## File Structure

- Create: `scripts/roadmap_registry.py` — Markdown index-header parser, typed records, shared lifecycle/field/reference validation, staged-file reader, deterministic digest and rendering data selection.
- Create: `scripts/render_roadmap.py` — registry records to `docs/ROADMAP.md` renderer; the only writer for the generated roadmap.
- Create: `scripts/check_roadmap.py` — read-only command that runs registry validation and compares expected versus checked-in/staged roadmap.
- Create: `scripts/install_git_hooks.py` — idempotently installs the scoped pre-commit dispatcher without replacing unrelated hooks.
- Create: `scripts/tests/test_roadmap_registry.py` — unit and integration-style fixture tests for parsing, rendering, validation, staged checks, and hook dispatch selection.
- Modify: `.github/workflows/ci.yml` — run the checker after the existing documentation check.
- Modify: `scripts/verify.ps1` — run the checker in the local full verification path.
- Modify: `AGENTS.md`, `docs/CURRENT_STATE.md`, `docs/PLANS.md` — make generated-roadmap ownership and minimal-reading procedure authoritative without contradicting lifecycle policy.
- Modify: `docs/exec-plans/todo/*.md`, `docs/exec-plans/active/*.md` — add conforming `다음 행동` and normalized reference ranges only to the current non-completed plan set.
- Modify: `docs/ROADMAP.md` — renderer output only; do not hand-edit.
- Modify: `docs/exec-plans/{todo,active,completed}/README.md` — reduce them to artifact-location guidance and links, removing duplicate status lists.
- Create: `C:/Users/Family/.codex/skills/roadmap-operator/SKILL.md` only if the repository’s approved skill-installation convention permits a user-scope skill; otherwise create the project-scoped skill at the convention identified during Task 5 and document that location in `AGENTS.md`.

### Task 1: Shared index-header registry and deterministic rendering data

**Files:**
- Create: `scripts/roadmap_registry.py`
- Create: `scripts/tests/test_roadmap_registry.py`

**Interfaces:**
- Consumes: a repository root and Markdown plan paths under `docs/exec-plans/todo`, `active`, and `completed`.
- Produces: `PlanRecord`, `ReferenceRange`, `RegistryError`, `load_registry(root, staged=False) -> list[PlanRecord]`, `validate_registry(records, root) -> list[RegistryError]`, `roadmap_digest(records) -> str`, and `roadmap_sections(records) -> dict[str, list[PlanRecord]]`.

- [ ] **Step 1: Write failing parser and validation tests**

  Add fixtures that express a valid header, every missing required field, an over-120-character `다음 행동`, four reference ranges, a non-relative/missing path, `L0`, an inverted range, an unknown label/type/status, duplicate IDs, two `Picked Up` records, and each forbidden directory/state pair. Assert errors include the record ID, repository-relative file, field name, and a concrete corrective command such as `python scripts/render_roadmap.py` for generated-roadmap drift.

- [ ] **Step 2: Run the focused tests and confirm the missing module failure**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: FAIL because `scripts.roadmap_registry` does not exist.

- [ ] **Step 3: Implement only the shared model, parser, and validators**

  Implement immutable `dataclass` records and a parser that reads only file start through the first `##` heading, requires a single H1 after the blockquote header, derives the numeric plan ID from the filename, and reads file content from either disk or the staged index. Validate path/state lifecycle according to `docs/PLANS.md`, header field grammar, reference path existence and inclusive line bounds, unique task IDs, and 0–1 `Picked Up`. Hash a canonical, sorted serialization of every input header so ordering and wall-clock time cannot affect the digest.

- [ ] **Step 4: Run parser and validation tests**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: PASS for valid, boundary, and invalid-header fixtures.

- [ ] **Step 5: Commit the isolated registry foundation**

  Run:

  ```powershell
  git add scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py
  git commit -m "feat: add roadmap registry parser"
  ```

### Task 2: Generated roadmap writer and read-only checker

**Files:**
- Create: `scripts/render_roadmap.py`
- Create: `scripts/check_roadmap.py`
- Modify: `scripts/tests/test_roadmap_registry.py`
- Modify: `docs/ROADMAP.md`

**Interfaces:**
- Consumes: `load_registry`, `validate_registry`, `roadmap_digest`, and `roadmap_sections` from `scripts.roadmap_registry`.
- Produces: `render_roadmap(records) -> str`, CLI `python scripts/render_roadmap.py`, and CLI `python scripts/check_roadmap.py [--staged]` with exit status 0/1.

- [ ] **Step 1: Add failing renderer/checker tests**

  Test that rendering the same valid records twice produces byte-identical output; that it writes a header comment containing the exact render command and stable digest; that rows contain only task ID, type, plan-title link, and `다음 행동`/`재개 조건`; that `Done` has at most twelve newest records plus the completed index link; and that checker detects a one-character manual roadmap edit without modifying it. Add a staged fixture where the index has changed plan/roadmap bytes and `--staged` must validate those index bytes rather than the working tree.

- [ ] **Step 2: Run the focused renderer/checker tests and confirm failure**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: FAIL because the renderer and checker entry points are absent.

- [ ] **Step 3: Implement deterministic rendering and read-only comparison**

  Render `Todo`, `Blocked`, and `Done` in the exact order supplied by the registry’s deterministic sort; place the sole `Picked Up` record in the `Todo` section so an in-progress milestone remains discoverable without adding a fourth section. Prefix the file with a non-time-based generated comment. Make `render_roadmap.py` validate first and atomically replace only `docs/ROADMAP.md`. Make `check_roadmap.py` never call write APIs, report the first differing line and the render command on mismatch, and in `--staged` mode obtain plan and roadmap content via `git show :<path>` while still checking tracked file locations.

- [ ] **Step 4: Regenerate the repository roadmap, then run the focused suite**

  Run:

  ```powershell
  uv run --project apps/api python scripts/render_roadmap.py
  uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
  uv run --project apps/api python scripts/check_roadmap.py
  ```

  Expected: renderer reports a stable digest; all tests pass; checker reports only parsed-plan count, `Picked Up` count, and the same digest.

- [ ] **Step 5: Commit the generated-roadmap contract**

  Run:

  ```powershell
  git add scripts/render_roadmap.py scripts/check_roadmap.py scripts/tests/test_roadmap_registry.py docs/ROADMAP.md
  git commit -m "feat: generate and verify roadmap"
  ```

### Task 3: Normalize current plan headers and remove duplicate status indexes

**Files:**
- Modify: `docs/exec-plans/todo/*.md`
- Modify: `docs/exec-plans/active/*.md`
- Modify: `docs/exec-plans/todo/README.md`
- Modify: `docs/exec-plans/active/README.md`
- Modify: `docs/exec-plans/completed/README.md`
- Modify: `docs/ROADMAP.md`
- Modify: `scripts/tests/test_roadmap_registry.py`

**Interfaces:**
- Consumes: current non-completed plan headers and `python scripts/render_roadmap.py`.
- Produces: a fully parseable non-completed plan registry, one generated roadmap, and lifecycle README files that do not claim independent status authority.

- [ ] **Step 1: Add an end-to-end fixture for the repository migration boundary**

  Add assertions that all `todo` and `active` Markdown plans have `다음 행동`, at most three reference entries with `Lstart-Lend` and reasons, and accepted IDs/types/labels. Add a fixture proving completed plans without a new header are excluded from mandatory bulk migration but that any completed plan which does contain the new header is still parseable.

- [ ] **Step 2: Run the migration-boundary test and confirm failure**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: FAIL listing current plan files that lack a required new-header field or normalized reference range.

- [ ] **Step 3: Migrate only active and todo artifacts, then simplify indexes**

  Add one concise `다음 행동` to every plan in `todo/` and `active/`; split or narrow each reference list to a maximum of three entries with exact line bounds and reasons. Preserve plan body history, IDs, filenames, and lifecycle directories. Rewrite lifecycle README files to describe their storage role and link to the generated roadmap instead of repeating Todo/active/Done status rows. Do not mass-edit completed plan headers.

- [ ] **Step 4: Regenerate and verify the migrated document set**

  Run:

  ```powershell
  uv run --project apps/api python scripts/render_roadmap.py
  uv run --project apps/api python scripts/check_roadmap.py
  uv run --project apps/api python scripts/check_docs.py
  ```

  Expected: registry and link checks pass; `git diff` shows `ROADMAP.md` only as renderer output and no completed-plan bulk rewrite.

- [ ] **Step 5: Commit the metadata migration separately**

  Run:

  ```powershell
  git add docs/exec-plans docs/ROADMAP.md scripts/tests/test_roadmap_registry.py
  git commit -m "docs: migrate active roadmap metadata"
  ```

### Task 4: Scoped pre-commit installation and CI enforcement

**Files:**
- Create: `scripts/install_git_hooks.py`
- Modify: `scripts/tests/test_roadmap_registry.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify.ps1`

**Interfaces:**
- Consumes: `python scripts/check_roadmap.py --staged` and the current repository `.git/hooks` directory.
- Produces: an idempotent pre-commit hook dispatcher that exits 0 without invoking Python unless staged paths include `docs/exec-plans/` or `docs/ROADMAP.md`; CI/local verification commands that always run the non-staged checker.

- [ ] **Step 1: Write failing hook and CI command tests**

  Use a temporary Git repository fixture with an existing executable `post-commit` and, separately, an existing user-owned `pre-commit`. Verify installation preserves `post-commit`, does not alter `core.hooksPath`, preserves a user pre-commit by refusing with a clear manual-install message rather than overwriting it, and produces a dispatcher that invokes the staged checker only for the two allowed path classes. Assert CI and `verify.ps1` include the non-staged checker immediately after the existing docs check.

- [ ] **Step 2: Run the hook-focused tests and confirm failure**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: FAIL because `scripts/install_git_hooks.py` does not exist and CI/local commands do not yet invoke the checker.

- [ ] **Step 3: Implement the conservative installer and wire checks**

  Implement an explicit `--repo-root` option plus default repository discovery. Install a generated pre-commit only when no pre-commit exists; encode the staged-path filter with `git diff --cached --name-only --diff-filter=ACMR`, then call `python scripts/check_roadmap.py --staged`. Never set Git configuration. Add `uv run --project apps/api python scripts/check_roadmap.py` after `check_docs.py` in CI and `verify.ps1`.

- [ ] **Step 4: Run hook, staged, CI-command, and full documentation verification**

  Run:

  ```powershell
  uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
  uv run --project apps/api python scripts/check_roadmap.py --staged
  uv run --project apps/api python scripts/check_docs.py
  ```

  Expected: all fixtures pass; `--staged` either reports the staged registry digest or a precise discrepancy without editing files; documentation checks pass.

- [ ] **Step 5: Commit enforcement separately**

  Run:

  ```powershell
  git add scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py .github/workflows/ci.yml scripts/verify.ps1
  git commit -m "ci: enforce generated roadmap consistency"
  ```

### Task 5: Minimal-reading operator workflow and project documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/PLANS.md`
- Create: the approved-scope `roadmap-operator/SKILL.md`
- Modify: `scripts/tests/test_roadmap_registry.py`

**Interfaces:**
- Consumes: generated `docs/ROADMAP.md`, selected plan index header, and its declared reference ranges.
- Produces: an operator procedure that first reads `docs/CURRENT_STATE.md` L1-L28 and the generated roadmap through the final non-completed row, then only the selected plan header and its declared ranges; any additional read must record path, bounds, and reason before use.

- [ ] **Step 1: Write failing text-contract tests**

  Add assertions that the operator instructions name the four ordered read scopes, prohibit reading other plan bodies/completed plans/full architecture documents by default, require a concise pre/post status-transition range report, and require declaring an out-of-range read’s path, start line, end line, and reason. Add assertions that `AGENTS.md` directs roadmap regeneration rather than direct editing.

- [ ] **Step 2: Run the text-contract test and confirm failure**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: FAIL because the operator skill and synchronized project instructions are absent.

- [ ] **Step 3: Document and install the minimal-reading workflow**

  Determine the repository’s approved scope for a reusable Codex skill before writing it; use that scope rather than silently creating an inaccessible user-home artifact. Write `roadmap-operator` with the four-step read order, lifecycle transition procedure, renderer/checker commands, and concise read-range report. Update project documents so they identify header metadata as authoritative, `ROADMAP.md` as generated, lifecycle READMEs as navigation only, and the explicit expansion rule for out-of-range context.

- [ ] **Step 4: Run the operator/document contract checks and the complete repository verification**

  Run:

  ```powershell
  uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
  uv run --project apps/api python scripts/check_roadmap.py
  uv run --project apps/api python scripts/check_docs.py
  powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
  ```

  Expected: all roadmap fixtures, generated-roadmap validation, document links, lint, types, tests, and web checks pass.

- [ ] **Step 5: Review, update graph, and commit the final workflow**

  Run:

  ```powershell
  graphify update .
  git diff --check
  git status --short
  git add AGENTS.md docs/CURRENT_STATE.md docs/PLANS.md <approved-roadmap-operator-skill-path> scripts/tests/test_roadmap_registry.py graphify-out
  git commit -m "docs: add roadmap operator workflow"
  ```

  Expected: graph artifact update is limited to the implementation’s documentation/code relationships; no credentials or private case material is staged.

## Spec Coverage Review

- Single milestone list, type/ID compatibility, header fields, reference limits, and lifecycle preservation: Tasks 1 and 3.
- Generated deterministic roadmap with digest, limited Done rows, and no direct source-of-truth edits: Task 2.
- Read-only validation, staged validation, precise errors, observability, and all required invalid cases: Tasks 1 and 2.
- Scoped hook without hooksPath/post-commit disruption plus CI: Task 4.
- Context-diet read order, range expansion disclosure, and state-transition reporting: Task 5.
- Explicit exclusions (GitHub synchronization, hierarchy, completed-plan bulk conversion, auto-fix/commit): Global Constraints and Task 3.

## Plan Self-Review

- Placeholder scan: no `TBD`, `TODO`, deferred implementation, or unspecified error-handling instructions remain.
- Type/interface consistency: every renderer/checker/hook task consumes the registry functions introduced in Task 1; the staged reader and record model remain the sole data boundary.
- Scope check: this is one integrated documentation-governance subsystem; splitting parser/renderer/hook/operator into separate plans would leave no independently usable workflow.
