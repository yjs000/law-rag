# Task 3 review: Normalize current plan headers and remove duplicate status indexes

## Verdict

**PASS — 0 findings (P0: 0, P1: 0, P2: 0).**

Reviewed the exact range
`7e2e5952bfb2b1d59d071d71de358db931601856..949368b89f50951294546fc6b6a6be91127e7d54`
against the Task 3 brief, task report, and approved roadmap-registry design.

## Specification and scope

- Every non-completed plan now has the required current header data. The focused
  repository-boundary test validates the active/todo set, including `다음 행동`,
  accepted IDs/types/labels, no more than three references, bounded reference
  lines, and reference reasons.
- Lifecycle README files are reduced to navigation/storage guidance. They link to
  generated `docs/ROADMAP.md` and no longer duplicate independent status lists.
- The exact range changes no completed plan header. Its only completed-directory
  change is `docs/exec-plans/completed/README.md`; the completed-plan diff is
  otherwise empty.
- `docs/ROADMAP.md` matches the deterministic renderer exactly: both ordinary and
  staged checks report 15 plans, 1 `Picked Up`, and digest
  `7e5e2d0a6d431310cc11202cb13a6fe0da84010ff87570ab16a16c184a5c50d4`.
  Its generated-command/digest comment and the checker result establish that the
  committed document is renderer output, not divergent hand-maintained content.

## Registry boundary change

The small `scripts/roadmap_registry.py` change is justified and appropriately
bounded:

- Lifecycle `README.md` files are Markdown navigation documents, not plan
  artifacts. Excluding them prevents their new simplified form from becoming
  invalid registry records; a dedicated fixture covers this behavior.
- A completed artifact is now considered migrated only when it contains the
  current `다음 행동` marker. This preserves the approved no-bulk-migration
  boundary while parsing completed plans as soon as they have the full current
  header. The fixture covers headerless completed exclusion and indexed-completed
  parsing.
- The behavior applies only to registry discovery/header eligibility; it does not
  alter lifecycle validation, rendering, or completed-plan bodies.

## Verification evidence

- `uv run --project apps/api --no-sync python -m unittest scripts.tests.test_roadmap_registry -v`
  — 27 tests passed. The first sandboxed run could not create temporary fixtures;
  the permitted temp-directory run passed unchanged.
- `uv run --project apps/api --no-sync python scripts/check_roadmap.py` and
  `--staged` — passed with the same count and digest.
- Ruff and `py_compile` for the touched registry and test module — passed.
- `git diff --check` for the reviewed range — passed.

## Documentation freshness check

`check_docs.py` still exits 1 solely because `docs/QUALITY_SCORE.md` has the
pre-existing evaluation date `2026-07-18` (47 days stale on 2026-09-03).
Both `docs/QUALITY_SCORE.md` and `scripts/check_docs.py` are byte-unchanged in
the reviewed range, and the same evaluation date exists at both endpoints. This
failure is pre-existing and outside Task 3's roadmap-metadata/navigation scope.
