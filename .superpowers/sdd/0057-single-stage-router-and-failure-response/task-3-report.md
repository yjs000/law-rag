# D-010 Task 3 Report

## Status

Task 3 documentation, executable contract assertions, test-fixture alignment, and local final
verification are complete. The parent execution plan remains active for the parent agent's final
integration decision; this report does not mark that overall plan complete. No live NVIDIA
provider, Docker container, persistent service, or database was used.

## Commit record

The Task 3 documentation commits are recorded chronologically and by their actual subjects:

- `f58c5d4 docs: record single-stage routing contract` — authoritative D-010 contract and design
  alignment.
- `ea5fc59 docs: record D-010 Task 3 verification evidence` — Task 3 checklist and initial
  verification evidence.
- `cf0a066 docs: add D-010 Task 3 report` — initial report artifact.
- `6dd410d fix(tests): align API fixtures with single-stage routing` — final review fix: reusable
  successful `legal_search` router fixture plus explicit search-only fixtures for the two tests
  whose intended path requires that feature.

The active-plan and this report are the follow-up evidence update for `6dd410d`; no “immediately
after” ordering is implied for the earlier documentation commits.

## Files and contract alignment

- `ARCHITECTURE.md`, `docs/design-docs/index.md`, and
  `docs/design-docs/pre-retrieval-question-routing.md` describe the current single NVIDIA router,
  the grounded normal sequence, and the `routing_unavailable` no-search failure route.
- `docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md` preserves the 2026-08-08
  E-10 tier1/tier2 experiment as historical evidence, while a dated current D-010 section
  supersedes that runtime description.
- `scripts/check_docs.py` now checks both the current D-010 routing prose and the E-10 historical
  boundary/current-section separation.
- `apps/api/tests/conftest.py` provides the clean `legal_search_router` fake. The AI fallback and
  grounding modules use it for normal downstream-path tests. The Supabase history module enables
  search-only explicitly because its fake environment intentionally has no NVIDIA key; the
  temporal readiness case enables search-only because that request explicitly exercises the
  search-only route.
- `docs/exec-plans/active/0057-single-stage-router-and-failure-response.md` contains runnable
  project-relative API/core commands and final counts without the former path-root mismatch.

## Failure diagnosis and resolution

The initial project-root API run reported `628 passed, 11 failed, 3 skipped, 1 warning`. Each red
case was traced before editing:

| Failure group | Count | Cause | Resolution |
| --- | ---: | --- | --- |
| `test_all_generation_failures_fall_back_without_another_model` (four parametrizations) | 4 | No fake successful router; the real provider path returned `routing_unavailable`, so generation/fallback was never exercised. | Module-level `legal_search_router` fixture. |
| `test_billing_or_quota_failure_disables_terra_for_later_requests` (two parametrizations) | 2 | Same missing successful `legal_search` judgment. | Same fixture. |
| `test_no_hits_generation_failure_still_falls_back_to_search_only` | 1 | Same missing successful `legal_search` judgment. | Same fixture. |
| `test_nvidia_generation_uses_nvidia_embedding_without_openai_key` | 1 | Same missing successful `legal_search` judgment. | Same fixture. |
| `test_structurally_invalid_citation_falls_back_to_search_only` | 1 | Same missing successful `legal_search` judgment. | Grounding module uses the same fixture. |
| `test_fake_supabase_history_is_owner_scoped_and_account_delete_cascades` | 1 | Fake Supabase flow has no NVIDIA key and `search_only_enabled=False`; the fail-closed AI-unavailable guard returned 503 before routing. This was not a router-only failure. | Enable the explicit search-only fixture for this storage/ownership flow. |
| `test_public_retrieval_routes_fail_closed_when_temporal_corpus_is_unready[question]` | 1 | The request sets `answer_mode=search_only`, but the fixture left `search_only_enabled=False`; the feature-gate 503 returned a string detail before corpus readiness was checked. | Inject `search_only_enabled` for this intended search-only boundary case. |

The final API run shows these paths now reach their intended downstream assertions rather than
being classified as routing or feature-availability failures.

## Verification evidence

- D-010 assertions:
  `uv run --project apps/api python -c "from scripts.check_docs import check_d010_routing_contract, check_d010_active_experiment_contract; errors = check_d010_routing_contract() + check_d010_active_experiment_contract(); print('d010 routing assertions passed' if not errors else '\\n'.join(errors)); raise SystemExit(bool(errors))"`
  → exit 0, `d010 routing assertions passed`.
- Full Ruff:
  `uv run --project apps/api ruff check apps/api/app apps/api/scripts apps/api/tests apps/api/migrations packages/law-rag-core/src packages/law-rag-core/tests`
  → exit 0, `All checks passed!`.
- Docstring Ruff:
  `uv run --project apps/api ruff check --select D100,D101,D102,D103,D107,D200,D205,D209,D400,D401,D403 apps/api/app/main.py apps/api/app/adapters/llamaindex_repository.py`
  → exit 0, `All checks passed!`.
- Focused D-010 suite (safe elevated pytest temp path): `43 passed, 1 warning` in 4.06s. The
  warning is the existing Starlette/httpx deprecation.
- Full API suite, with `tests` resolved from the API project directory:
  `$env:PYTHONPATH='.;..\..\packages\law-rag-core\src;..\collector\src'; uv run --directory apps/api python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\25\d010-api-full-relative tests -q`
  → `639 passed, 3 skipped, 1 warning` in 44.63s.
- Full core suite:
  `uv run --project packages/law-rag-core python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\25\d010-core-full-final packages/law-rag-core/tests -q`
  → `26 passed` in 0.26s.
- Repository docs checker:
  `uv run --project apps/api python scripts/check_docs.py`
  → exit 1 with exactly 32 pre-existing broken-link reports. The two D-010 assertion functions
  pass; no new D-010 link or current-contract error is reported, and unrelated documentation
  debt remains untouched.
- `git diff --check` → exit 0.

The NVIDIA-keyed fixture evaluator remains intentionally unrun because it would require a live
provider and user-authorized credentials.
