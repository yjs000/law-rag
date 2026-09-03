# Task 3 report: Normalize current plan headers and remove duplicate status indexes

## Red evidence

- Before metadata edits, the named migration-boundary test was run from a temporary working directory with the repository on `PYTHONPATH`:
  `uv run --project C:\Users\Family\.codex\worktrees\e116\law-rag\apps\api --no-sync python -m unittest scripts.tests.test_roadmap_registry.RoadmapRegistryFixtures.test_repository_non_completed_plans_meet_migration_boundary -v`.
  It failed as expected with 120 registry validation errors, including missing strict header fields, malformed reference ranges, and missing next actions.
- After adding the README/completed-plan boundary fixtures but before the boundary implementation, the two focused boundary tests failed as expected: lifecycle READMEs were parsed as plans and the legacy completed fixture was not excluded.

## Green evidence

- `uv run --project C:\Users\Family\.codex\worktrees\e116\law-rag\apps\api --no-sync python -m unittest scripts.tests.test_roadmap_registry -v` — 27 tests passed (`OK`). Because this Windows environment denies fixture directory creation from the sandbox, the same command was run with the required elevated temp-directory permission.
- `uv run --project apps/api --no-sync ruff check scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py` — all checks passed.
- `uv run --project apps/api --no-sync python -m py_compile scripts/roadmap_registry.py scripts/tests/test_roadmap_registry.py` — passed.
- `git diff --check` and the staged diff check — no whitespace errors.
- No completed plan header was modified; only `docs/exec-plans/completed/README.md` was simplified.

## Generated roadmap

Generated exclusively with:

`uv run --project apps/api python scripts/render_roadmap.py`

Result:

```text
parsed plans: 15
Picked Up: 1
roadmap digest: 7e5e2d0a6d431310cc11202cb13a6fe0da84010ff87570ab16a16c184a5c50d4
```

`uv run --project apps/api python scripts/check_roadmap.py` and the staged form
`uv run --project apps/api python scripts/check_roadmap.py --staged` both passed with the same count and digest.

## Documentation check

`uv run --project apps/api python scripts/check_docs.py` reached the existing freshness guard and exited 1:

`docs\\QUALITY_SCORE.md: 기준 날짜 2026-07-18가 47일 경과했습니다`

This unrelated stale-date finding was not changed because Task 3 is scoped to roadmap metadata and lifecycle navigation.

## Modified paths

- `docs/ROADMAP.md`
- `docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md`
- `docs/exec-plans/active/0055-v3-langgraph-agent-foundation.md`
- `docs/exec-plans/active/0064-web-dynamic-today-date-bound.md`
- `docs/exec-plans/active/README.md`
- `docs/exec-plans/completed/README.md`
- `docs/exec-plans/todo/0012-distributed-question-cancellation.md`
- `docs/exec-plans/todo/0029-d-full-gold-on-demand.md`
- `docs/exec-plans/todo/0031-eval-harness-consolidation.md`
- `docs/exec-plans/todo/0033-traffic-based-routing-calibration-review.md`
- `docs/exec-plans/todo/0042-wire-reranking-into-live-search-path.md`
- `docs/exec-plans/todo/0044-provider-neutral-answer-model-selection.md`
- `docs/exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md`
- `docs/exec-plans/todo/0050-query-format-edge-case-regression-bank.md`
- `docs/exec-plans/todo/0058-v2-chunking-ablation-d10.md`
- `docs/exec-plans/todo/0060-v2-dynamic-today-date-bound.md`
- `docs/exec-plans/todo/0065-remove-checklist-export-frontend.md`
- `docs/exec-plans/todo/0066-roadmap-registry-and-context-diet.md`
- `docs/exec-plans/todo/README.md`
- `scripts/roadmap_registry.py`
- `scripts/tests/test_roadmap_registry.py`

## Commit

- Commit: `949368b89f50951294546fc6b6a6be91127e7d54`
- Message: `docs: migrate active roadmap metadata`

## Concerns

- `scripts/roadmap_registry.py` is a narrowly scoped additional path beyond the brief's file list. It excludes lifecycle `README.md` navigation files from the registry and recognizes the current `다음 행동` marker when skipping legacy completed plans; this is necessary to satisfy the migration boundary without editing completed plan headers.
- Existing `graphify-out/` changes and `.superpowers/sdd/0066-roadmap-registry-and-context-diet/` artifacts remain outside the commit.
