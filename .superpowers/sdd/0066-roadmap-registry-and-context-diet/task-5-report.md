# Task 5 report: Minimal-reading operator workflow and project documentation

## Scope decision

The repository has no existing project-scoped skills convention (`.codex/skills/` and
`.agents/skills/` were absent; `.claude/` contains only settings and hooks). Following the
Task 5 scope rule, the reusable operator was created at
`.codex/skills/roadmap-operator/SKILL.md`. No user-home skill was created. The hidden
`.codex` directory required one-time elevated patch access because the Windows sandbox denied
normal writes; the file remains inside this worktree.

## TDD evidence

### Red

The two text-contract tests were added before the skill or synchronized documentation. The first
sandboxed focused run could not create its disposable fixture directories because of Windows ACLs.
The same command with permitted filesystem access ran 36 tests and failed exactly the two new
contracts: the operator skill did not exist and `AGENTS.md` lacked the new authority markers.

### Green

After writing the project skill and updating the three authoritative documents:

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

Result: 36 tests passed (`OK`). The suite covers the four ordered scope markers, default
prohibitions, explicit expansion fields, transition reporting, source-header authority, and
generated-roadmap ownership.

The skill-authoring validator also passed:

```text
uv run --project apps/api python -X utf8 C:\Users\Family\.codex\skills\.system\skill-creator\scripts\quick_validate.py .codex\skills\roadmap-operator
```

The skill is 458 words, has valid frontmatter, and includes the required quick reference and
common-mistakes guidance. Writing-skills pressure scenarios were not dispatched because the parent
task explicitly prohibits subagents; the requested repository text-contract tests are the
independent behavioral gate for this project-scoped reference skill.

## Implemented contract

- `AGENTS.md` routes milestone start/resume work through the project skill, declares header metadata
  as the sole source of truth, prohibits direct roadmap edits, and requires expansion and
  pre/post transition range reports.
- `docs/CURRENT_STATE.md` makes generated roadmap status authoritative and keeps the four-scope
  entry point within the initial L1-L28 read range.
- `docs/PLANS.md` documents generated-roadmap ownership, lifecycle README navigation-only status,
  the seven-field index-header shape (including `다음 행동`), and explicit out-of-range disclosure.
- `.codex/skills/roadmap-operator/SKILL.md` defines the four ordered reads, lifecycle transitions,
  renderer/checker commands, concise range-report format, and common failure modes.
- `scripts/tests/test_roadmap_registry.py` adds the two text-contract tests.

## Verification

```text
uv run --project apps/api python scripts/check_roadmap.py
```

Result: passed; 15 parsed plans, 1 `Picked Up`, digest
`7e5e2d0a6d431310cc11202cb13a6fe0da84010ff87570ab16a16c184a5c50d4`.

```text
uv run --project apps/api python scripts/check_docs.py
```

Result: pre-existing freshness failure only:
`docs/QUALITY_SCORE.md` has 기준 날짜 `2026-07-18`, 47 days stale on 2026-09-03. The file and
checker are outside this task.

```text
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

The elevated full run passed all 26 `law-rag-core` tests, then stopped during API test collection
on two pre-existing `ModuleNotFoundError: No module named 'law_rag_collector'` errors in
`tests/test_context_experiment.py` and `tests/test_search_experiment.py`. The first non-elevated
attempt stopped earlier when pytest cleanup encountered sandbox-created temporary directories.

```text
graphify update .
```

The normal attempt could not scan pre-existing sandbox temporary directories. The elevated retry
completed successfully (`7,943` nodes, `15,653` edges, `516` communities) and updated the existing
dirty `graphify-out/` artifacts. Those generated files were not included in the scoped commit.

`git diff --check` for the changed tracked files produced no whitespace errors.

## Commit

Scoped commit created:

```text
AGENTS.md
docs/CURRENT_STATE.md
docs/PLANS.md
scripts/tests/test_roadmap_registry.py
.codex/skills/roadmap-operator/SKILL.md
```

Commit: `22d260b` — `docs: add roadmap operator workflow`

## Review fix (2026-09-03)

`task-5-review.md` reported two documentation-contract inconsistencies:

- P1: the normal startup instructions in `AGENTS.md` and `docs/CURRENT_STATE.md` did not bound
  the default current-state read to L1-L28.
- P2: `docs/PLANS.md` still called the expanded metadata a six-field header even though `다음 행동`
  makes it seven fields.

Regression tests were added before the documentation changes in
`scripts/tests/test_roadmap_registry.py`:

```text
uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
```

The elevated red run failed exactly the two new contracts while the existing tests remained
otherwise green. After the changes, the focused suite passed 38/38 tests. The fixes bind both
startup statements to `docs/CURRENT_STATE.md` L1-L28 and describe the seven-field header with
`다음 행동` explicitly.

Post-fix checks:

- `uv run --project apps/api python scripts/check_roadmap.py`: passed (15 plans, 1 `Picked Up`,
  unchanged digest).
- `uv run --project apps/api python -X utf8 'C:\\Users\\Family\\.codex\\skills\\.system\\skill-creator\\scripts\\quick_validate.py' .codex\\skills\\roadmap-operator`:
  passed.
- `git diff --cached --check`: passed before commit.
- `uv run --project apps/api python scripts/check_docs.py`: the same pre-existing
  `docs/QUALITY_SCORE.md` freshness failure (47 days stale).
- Full `scripts/verify.ps1`: 26 core tests passed; API collection still has the two pre-existing
  `law_rag_collector` import errors.

Scoped review-fix commit: `d1f41d6` — `fix: bound roadmap startup context`.
