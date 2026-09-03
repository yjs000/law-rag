# Task 4 review — changes requested

Reviewed `949368b..c30a74a` against the Task 4 brief and binding design.

## Findings

- **P1 — staged-path discovery fails open.** In `scripts/install_git_hooks.py:24`, the `git diff | grep` pipeline is the condition of an `if`. POSIX `sh` does not apply `set -e` to an `if` condition and has no `pipefail`; therefore a `git diff` failure (for example, an unreadable/corrupt index) is indistinguishable from "no matching path." The hook reaches `exit 0` and permits the commit without checking the staged roadmap. Capture and check the `git diff` exit status before treating a no-match as a successful skip; add a regression test that makes staged-path discovery fail.

- **P1 — quoted Git paths bypass the filter.** The same line parses presentation-oriented `--name-only` output. With Git's default `core.quotePath=true`, staging `docs/exec-plans/todo/0001-한글.md` produces a quoted path beginning with `"docs/…`, which does not match `^docs/exec-plans/`; the hook exits successfully without the checker. Use Git pathspec/exit-status filtering (or robust NUL-delimited parsing) and add a non-ASCII-path regression case.

## Confirmed

- The installer itself is not invoked by import or CI, and this worktree has no generated `pre-commit` hook.
- It preserves an existing user `pre-commit`, does not write `core.hooksPath`, and leaves `post-commit` untouched; the tests exercise those cases in temporary repositories.
- CI and `scripts/verify.ps1` place the non-staged checker immediately after `check_docs.py`.
- `exec python scripts/check_roadmap.py --staged` correctly propagates checker failures once the relevant-path branch is reached.

## Verification note

`ruff check` and `check_roadmap.py --staged` pass. The focused unittest command could not run in this sandbox: all tests fail during fixture setup because its pre-existing `TemporaryDirectory(dir=Path.cwd())` location creates inaccessible Windows sandbox directories. The Task 4 report records a successful 32-test run outside this constraint; the two findings above are static behavioral defects and are not caused by that environment limitation.
