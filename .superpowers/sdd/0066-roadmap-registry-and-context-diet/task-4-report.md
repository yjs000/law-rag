# Task 4 report: Scoped pre-commit installation and CI enforcement

## Red evidence

- Before adding `scripts/install_git_hooks.py`, the focused command
  `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`
  failed during test-module import with `ImportError: cannot import name 'install_git_hooks'`.
- The new CI/verification-order test also established the expected failure boundary for the
  not-yet-wired checker commands.

## Green evidence

- `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v` — 32 tests passed (`OK`).
  The suite uses only temporary Git repositories for hook installation and commit-path behavior.
- `uv run --project apps/api ruff check scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py` — passed.
- `uv run --project apps/api python -m py_compile scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py` — passed.
- `git diff --check` for the four scoped files — passed.
- `uv run --project apps/api python scripts/check_roadmap.py` — passed: 15 plans, 1 `Picked Up`,
  digest `7e5e2d0a6d431310cc11202cb13a6fe0da84010ff87570ab16a16c184a5c50d4`.
- `uv run --project apps/api python scripts/check_roadmap.py --staged` — passed with the same
  plan count and digest.

## Implemented behavior

- Added `scripts/install_git_hooks.py` with explicit `--repo-root` and Git-root discovery from the
  current directory.
- The generated `.git/hooks/pre-commit` dispatcher is idempotent, preserves an existing
  `post-commit`, refuses to overwrite a user-owned `pre-commit` with manual-install guidance,
  never writes `core.hooksPath`, and runs `python scripts/check_roadmap.py --staged` only when
  `git diff --cached --name-only --diff-filter=ACMR` includes `docs/exec-plans/` or `docs/ROADMAP.md`.
- Added the non-staged roadmap checker immediately after `check_docs.py` in CI and `scripts/verify.ps1`.

## Documentation and graphify notes

- `uv run --project apps/api python scripts/check_docs.py` remains a pre-existing failure because
  `docs/QUALITY_SCORE.md` reports evaluation date `2026-07-18` (47 days stale on 2026-09-03).
  `QUALITY_SCORE.md` and `scripts/check_docs.py` were not changed.
- The required `graphify update .` attempt could not scan the temporary fixture directories left by
  Windows sandbox test cleanup (`WinError 5`); existing `graphify-out/` changes were preserved.

## Scoped paths

- `scripts/install_git_hooks.py`
- `scripts/tests/test_roadmap_registry.py`
- `.github/workflows/ci.yml`
- `scripts/verify.ps1`

## Commit

- `c30a74a` — `ci: enforce generated roadmap consistency`

## Fix round 1

### Red evidence

- Review regression `test_pre_commit_dispatcher_rejects_staged_path_discovery_failure` failed
  against `c30a74a`: a corrupt temporary Git index made the hook return 0.
- Review regression `test_pre_commit_dispatcher_handles_git_quoted_non_ascii_plan_path` failed
  against `c30a74a`: with `core.quotePath=true`, a staged `docs/exec-plans/todo/0001-한글.md`
  did not invoke the checker.

### Green evidence

- `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v` — 34 tests passed (`OK`).
- `uv run --project apps/api ruff check scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py` — passed.
- `uv run --project apps/api python -m py_compile scripts/install_git_hooks.py scripts/tests/test_roadmap_registry.py` — passed.
- `uv run --project apps/api python scripts/check_roadmap.py` and `--staged` — both passed with
  15 plans, 1 `Picked Up`, and digest `7e5e2d0a6d431310cc11202cb13a6fe0da84010ff87570ab16a16c184a5c50d4`.

### Fix

- The dispatcher now checks the staged-path discovery command's exit status before filtering, and
  refuses the commit when Git cannot read the index.
- The command-scoped `core.quotePath=false` setting keeps non-ASCII staged paths parseable without
  modifying repository configuration.

### Fix commit

- `9a7fee5` — `fix: harden roadmap hook path discovery`
