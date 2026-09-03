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
