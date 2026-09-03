### Task 4: Scoped pre-commit installation and CI enforcement

**Files:**
- Create: `scripts/install_git_hooks.py`
- Modify: `scripts/tests/test_roadmap_registry.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/verify.ps1`

**Interfaces:**
- Consumes: `python scripts/check_roadmap.py --staged` and the current repository `.git/hooks` directory.
- Produces: an idempotent pre-commit hook dispatcher that exits 0 without invoking Python unless staged paths include `docs/exec-plans/` or `docs/ROADMAP.md`; CI/local verification commands that always run the non-staged checker.

- [ ] Write failing hook/CI tests using temporary Git fixtures. Preserve `post-commit`, refuse to overwrite a user `pre-commit`, never alter `core.hooksPath`, test path filtering, and assert checker commands follow docs checks.
- [ ] Run `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`; observe absent-installer red failure.
- [ ] Implement `--repo-root` installer/default discovery and generated dispatcher with `git diff --cached --name-only --diff-filter=ACMR`; never set git config. Wire `uv run --project apps/api python scripts/check_roadmap.py` after `check_docs.py` in CI/verify.
- [ ] Run focused tests, `python scripts/check_roadmap.py --staged`, and `python scripts/check_docs.py`.
- [ ] Commit only scoped files: `ci: enforce generated roadmap consistency`.
