# Task 5 review — minimal-reading operator workflow

## Verdict

**Changes requested.** The new project-scoped skill is located inside the worktree, the
operator/document contract test passes, and the committed file set is within Task 5 scope.
However, two project-document inconsistencies leave the documented workflow non-compliant.

## Review scope and read-range record

- `docs/CURRENT_STATE.md` L1-L28 and `docs/ROADMAP.md` through its last non-completed row:
  startup context and selected-milestone source.
- `docs/exec-plans/todo/0066-roadmap-registry-and-context-diet.md` L1-L13, then L238-L305:
  selected-plan header plus Task 5 acceptance criteria. The latter is an explicit review-only
  expansion needed to compare the committed change with the task.
- `docs/superpowers/specs/2026-09-03-roadmap-registry-and-context-diet-design.md` L1-L104 and
  `docs/PLANS.md` L16-L68: declared references for authoritative behavior.
- `.superpowers/sdd/0066-roadmap-registry-and-context-diet/task-5-report.md` L1-L105 and the
  changed files in `9a7fee5..22d260b`: Task 5 evidence and implementation under review.

## Findings

### [P1] The normal startup instructions still require the whole current-state document

`AGENTS.md` L17 tells every session to read `docs/CURRENT_STATE.md` without the L1-L28 bound,
and `docs/CURRENT_STATE.md` L3 likewise calls the entire file a default read. This happens
before `AGENTS.md` L23 reaches the new operator workflow. It directly conflicts with the
design and skill, which require only `docs/CURRENT_STATE.md` L1-L28 as the first operator
scope. In a normal session the agent therefore consumes lines L29-L39 before it is allowed to
apply the four-scope rule. Change both startup statements to name L1-L28 explicitly (while
retaining the required root `AGENTS.md` read), and add a text assertion that prevents an
unbounded default `CURRENT_STATE.md` read from returning.

### [P2] `docs/PLANS.md` still calls the expanded header a six-field header

The Task 5 change adds `다음 행동` to the six prior header fields, so the example at
`docs/PLANS.md` L34-L42 now has seven fields. But L100 still says `위 여섯 필드 헤더`.
This leaves the project’s documentation internally inconsistent about the required index
shape. Update the count to seven and cover it in the document text-contract test.

## Evidence

- `git diff --check 9a7fee5..22d260b`: passed (no output).
- `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`:
  passed, 36 tests. A sandboxed first attempt could not create temporary fixture directories;
  the permitted rerun completed normally.
- `uv run --project apps/api python scripts/check_roadmap.py`: passed (15 plans, 1 `Picked Up`).
- `uv run --project apps/api python scripts/check_docs.py`: still reports the pre-existing
  `docs/QUALITY_SCORE.md` freshness failure (47 days); it is unrelated to this diff.

## Scope assessment

`22d260b` changes exactly the five Task 5 paths: `AGENTS.md`, `docs/CURRENT_STATE.md`,
`docs/PLANS.md`, `scripts/tests/test_roadmap_registry.py`, and the new
`.codex/skills/roadmap-operator/SKILL.md`. `9a7fee5` has no Task 5 implementation overlap.
The base tree contained no `.codex` or `.agents` skills directory, while the commit adds the
operator under the documented project scope; no user-home artifact or unrelated runtime code
was introduced.
