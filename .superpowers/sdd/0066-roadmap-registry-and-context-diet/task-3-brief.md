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
