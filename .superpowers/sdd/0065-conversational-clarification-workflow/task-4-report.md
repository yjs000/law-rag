# F-006 Task 4 report — V2 policy-aware generation and grounding

## RED

- Command: `uv run --directory apps/api python -m pytest tests/test_clarification_answering.py tests/test_v2_question_executions.py tests/test_grounding_gate.py -v`
- Result: expected collection failure. `tests/test_clarification_answering.py` could not import `ClarificationGrounding` or the structured-claim gate from `app.application.v2.grounding`.
- Meaning: V2 had no persisted clarification policy/fact state and no deterministic structured-claim validation boundary.

## GREEN

- Focused task command: `uv run --directory apps/api python -m pytest tests/test_clarification_answering.py tests/test_v2_question_executions.py tests/test_grounding_gate.py -v`
  - Result: 34 passed.
- Compatibility command: `uv run --directory apps/api python -m pytest tests/test_clarification_answering.py tests/test_v2_question_executions.py tests/test_grounding_gate.py tests/test_nvidia_nim_answerer.py tests/test_layperson_prompt_v2.py tests/test_clarification_domain.py -v`
  - Result: 67 passed.
- Static checks: API and core Ruff checks passed; `git diff --check` passed (Git reported existing CRLF conversion warnings only).

Implemented the Task 4 boundary:

- Optional continuation fields preserve existing request and response schemas.
- `prepare`, `core`, and `finalize` carry only policy, fact IDs, statuses, and blocking metadata; capability and fact values are excluded from persisted payloads and prompts.
- OpenAI and NVIDIA NIM use continuation-specific schemas that require structured `GroundedClaim` output without changing legacy schemas.
- Before any terminal SSE response, every structured claim is checked only against its structure, the frozen citation registry, and clarification fact state. There is no text or phrase matching.
- Invalid claims produce the existing degraded response rather than a terminal legal answer.

## Full-suite environment note

API full suite reached 642 passed and core suite reached 21 passed before their remaining tests errored during fixture setup/cleanup with `PermissionError: [WinError 5]` for the managed Windows pytest temporary directory. Re-running with explicit worktree-local base-temp directories reached the same permission error during pytest session cleanup. The focused and compatibility suites above are green.

## Graphify note

`graphify update .` was attempted as required after the code change, but its rebuild failed with `[WinError 5] Access denied` in the managed environment, even after removing the exact pytest-only temporary directories created by the failed full-suite runs. Its partial `graphify-out/cache/stat-index.json` change is intentionally not staged.
