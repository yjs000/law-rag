# SDD ledger — plan: docs/exec-plans/todo/0066-roadmap-registry-and-context-diet.md

## Pre-flight interface scan

| Tasks | Shared file or interface | Finding / ruling |
| --- | --- | --- |
| 1 → 2 | `scripts/roadmap_registry.py`; `PlanRecord`, `ReferenceRange`, `load_registry`, `validate_registry`, `roadmap_digest`, `roadmap_sections` | Task 2 consumes the names Task 1 produces. Keep these import-stable; no conflict. |
| 1 → 2 → 3 → 4 → 5 | `scripts/tests/test_roadmap_registry.py` | Each task extends one focused standard-library test module. Preserve prior tests and run the whole module after each change. |
| 2 → 3 | `docs/ROADMAP.md`; `render_roadmap.py`; `check_roadmap.py` | Task 2 establishes generated output; Task 3 changes inputs and must invoke the renderer. No conflict. |
| 3 → 5 | `AGENTS.md`, `docs/CURRENT_STATE.md`, `docs/PLANS.md`, lifecycle READMEs | Task 3 owns artifact navigation cleanup; Task 5 owns authoritative workflow wording. Update in separate commits and preserve Task 3 links. |
| 4 → 5 | `scripts/check_roadmap.py`; hook/CI commands | Task 4 supplies enforcement commands that Task 5 documents. No conflict. |
| 5 | roadmap-operator skill location | Ruling: resolve the repository-supported project scope during Task 5. Do not write outside this worktree without explicit authority; if no project-scope convention exists, record the unavailable user-scope installation as a documented follow-up rather than bypassing sandbox policy. Cost if wrong: the skill may require a later installation step, but repository behavior remains reproducible. |

## Task consistency scan

| Task | Test/code/files agree? | Finding / ruling |
| --- | --- | --- |
| 1 | Yes | Parser tests precede the new shared module. |
| 2 | Yes | Renderer/checker tests consume only Task 1 interfaces. `Picked Up` is rendered under `Todo` per plan. |
| 3 | Yes | Migration is restricted to active/todo inputs and explicitly excludes completed-plan bulk edits. |
| 4 | Yes | Temporary Git-repository tests isolate hook effects; installer does not overwrite hooks. |
| 5 | Yes, with scope ruling above | Text-contract tests precede workflow documentation. |

[Ledger: Task 1: fix round 1/5 (7 findings addressed, 0 open; commits 645c02a..2980fdc)]
[Ledger: Task 1: complete (commits 645c02a..2980fdc, re-review clean)]

Ruling: Task 2 cannot regenerate or make the repository `docs/ROADMAP.md` pass validation before Task 3 supplies required `다음 행동` fields to the current todo/active plans. The approved design makes those headers the source of truth, so bypassing validation would violate it. Task 2 will prove renderer/checker behavior with isolated valid fixtures and commit their entry points; Task 3 will run the first repository render, add the generated roadmap to its metadata-migration commit, and then run the checker. Cost if wrong: generated-roadmap delivery moves one task later, but no invalid source metadata is silently accepted.

[Ledger: Task 2: complete (commit 7e2e595, review clean)]
[Ledger: Task 3: complete (commit 949368b, review clean; docs freshness failure pre-existing/out of scope)]
[Ledger: Task 4: complete (commits c30a74a and 9a7fee5, re-review clean)]
[Ledger: Task 5: complete (commits 22d260b and d1f41d6, re-review clean)]

[Ledger: final-review completion gates resolved (2026-09-03): collector import path,
API psycopg runtime dependency, and maintenance-script package resolution fixed; QUALITY_SCORE
freshness refreshed with current verification evidence. Full verification passed: core 26; API 687
passed/3 skipped; collector 97 passed/5 skipped; docs/roadmap checks; web lint/typecheck/95 tests/build.
Pre-existing graphify artifacts remained outside scope.]
