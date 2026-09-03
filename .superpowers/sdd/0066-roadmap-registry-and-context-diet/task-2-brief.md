### Task 2: Generated roadmap writer and read-only checker

**Files:**
- Create: `scripts/render_roadmap.py`
- Create: `scripts/check_roadmap.py`
- Modify: `scripts/tests/test_roadmap_registry.py`
- Modify: `docs/ROADMAP.md`

**Interfaces:**
- Consumes: `load_registry`, `validate_registry`, `roadmap_digest`, and `roadmap_sections` from `scripts.roadmap_registry`.
- Produces: `render_roadmap(records) -> str`, CLI `python scripts/render_roadmap.py`, and CLI `python scripts/check_roadmap.py [--staged]` with exit status 0/1.

- [ ] **Step 1: Add failing renderer/checker tests**

  Test that rendering the same valid records twice produces byte-identical output; that it writes a header comment containing the exact render command and stable digest; that rows contain only task ID, type, plan-title link, and `다음 행동`/`재개 조건`; that `Done` has at most twelve newest records plus the completed index link; and that checker detects a one-character manual roadmap edit without modifying it. Add a staged fixture where the index has changed plan/roadmap bytes and `--staged` must validate those index bytes rather than the working tree.

- [ ] **Step 2: Run the focused renderer/checker tests and confirm failure**

  Run: `uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v`

  Expected: FAIL because the renderer and checker entry points are absent.

- [ ] **Step 3: Implement deterministic rendering and read-only comparison**

  Render `Todo`, `Blocked`, and `Done` in the exact order supplied by the registry’s deterministic sort; place the sole `Picked Up` record in the `Todo` section so an in-progress milestone remains discoverable without adding a fourth section. Prefix the file with a non-time-based generated comment. Make `render_roadmap.py` validate first and atomically replace only `docs/ROADMAP.md`. Make `check_roadmap.py` never call write APIs, report the first differing line and the render command on mismatch, and in `--staged` mode obtain plan and roadmap content via `git show :<path>` while still checking tracked file locations.

- [ ] **Step 4: Regenerate the repository roadmap, then run the focused suite**

  Run:

  ```powershell
  uv run --project apps/api python scripts/render_roadmap.py
  uv run --project apps/api python -m unittest scripts.tests.test_roadmap_registry -v
  uv run --project apps/api python scripts/check_roadmap.py
  ```

  Expected: renderer reports a stable digest; all tests pass; checker reports only parsed-plan count, `Picked Up` count, and the same digest.

- [ ] **Step 5: Commit the generated-roadmap contract**

  Run:

  ```powershell
  git add scripts/render_roadmap.py scripts/check_roadmap.py scripts/tests/test_roadmap_registry.py docs/ROADMAP.md
  git commit -m "feat: generate and verify roadmap"
  ```
