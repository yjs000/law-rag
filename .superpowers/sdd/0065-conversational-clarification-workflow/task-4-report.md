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

## Review correction round 1

### RED

- `test_claim_gate_rejects_an_empty_claim_list` failed because `all([])` vacuously returned `True`.
- `test_claim_gate_requires_complete_unique_structural_coverage` failed because the gate had no published-field target contract.
- `test_unbound_published_detail_is_replaced_before_terminal_sse_publication` failed because a summary-only claim allowed a section and checklist to publish.
- `test_case_application_with_an_unknown_fact_id_is_rejected_without_raising` raised `KeyError("missing")` instead of returning `False`.
- Workflow tests showed `mark_waiting` and `complete` incrementing case versions before V2 generated a grounded response.
- The continuation-contract test failed because the old schema required `policy` instead of the Task 5 waiting payload.

### GREEN

- `GroundedClaim` now requires an explicit structural target (`summary`, `section_claim`, `section_explanation`, or `checklist_label`) and an index where applicable.
- The clarification gate requires a nonempty, unique, exact structural target set for every published core or detail field. It still checks only claim structure, frozen citation IDs, and case facts; it never compares generated wording to evidence text.
- Invalid/unbound detail responses degrade before terminal SSE publication.
- Unknown case-application fact IDs return `False`.
- Clarification workflow returns a pending `next_status`; V2 persists `waiting_for_user` or `completed` only after a grounded finalize, leaves the case untransitioned on degradation, and emits the optional waiting continuation `{case_id, status, question_format, remaining_count}`.
- Malformed waiting metadata is validated before the repository transition, so it also leaves the case untransitioned.
- Combined command: `uv run --directory apps/api python -m pytest tests/test_clarification_answering.py tests/test_clarification_domain.py tests/test_clarification_workflow.py tests/test_v2_question_executions.py tests/test_grounding_gate.py -v`
  - Result: 58 passed.
- Extended compatibility command added NVIDIA answerer/clarification and layperson-prompt coverage.
  - Result: 96 passed.
- Core continuation contract: `uv run --directory packages/law-rag-core python -m pytest tests/test_contracts.py -v`
  - Result: 6 passed.
- API/core Ruff checks and `git diff --check` passed.

## Full-suite environment note

API full suite reached 642 passed and core suite reached 21 passed before their remaining tests errored during fixture setup/cleanup with `PermissionError: [WinError 5]` for the managed Windows pytest temporary directory. Re-running with explicit worktree-local base-temp directories reached the same permission error during pytest session cleanup. The focused and compatibility suites above are green.

## Graphify note

`graphify update .` was attempted again after the review correction. Its rebuild remains blocked by `[WinError 5] Access denied` for managed pytest cache directories (for example, `packages/law-rag-core/pytest-cache-files-5iycrah5`); its partial `graphify-out/cache/stat-index.json` change is intentionally not staged.
