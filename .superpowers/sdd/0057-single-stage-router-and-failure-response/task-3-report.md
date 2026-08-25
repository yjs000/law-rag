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
- `46e7040 docs: finalize D-010 verification evidence` — corrected active-plan commands, E-10
  supersession/checker evidence, and the first complete green verification report.
- `56ae8ab docs: align D-010 lifecycle status` — removed the solved regression-gate blocker from
  lifecycle pointers and recorded the final green counts while preserving parent-level Active
  integration status.
- `21689e0 docs: align superseded D-010 records` — updates the technology ADR, superseded
  always-generate design, settings comments, and historical fixture metadata without changing
  production behavior or historical result values.
- `713d64f docs: record D-010 metadata commit` — records the lifecycle metadata correction in the
  report/progress history.
- `fd31dd2 docs: record D-010 alignment commit` — records `21689e0` in the report and active-plan
  commit sequence.
- `e2daefe docs: correct D-010 assertion evidence` — corrects the report/plan count to four
  D-010 assertion functions and clarifies historical metadata preservation.
- `e44497c docs: reconcile D-010 lifecycle evidence` — records the complete chronological Task 3
  sequence through `e2daefe` and removes the inaccurate single-follow-up phrasing.
- `10b72d4 docs: record final D-010 lifecycle SHA` — records the final lifecycle SHA in the
  active plan/report before this current-document alignment pass.
- `a2a9c1d docs: align current D-010 contract records` — aligns current deployment, reliability,
  RAG, architecture, future-plan/debt, V3 proposal, design index, and generated-snapshot status;
  expands the D-010 docs assertion to cover those records.
- `e632c86 docs: record D-010 contract alignment evidence` — records the final post-alignment
  assertion, docs-checker, Ruff, and diff evidence in the lifecycle report.
- `d35509f docs: close D-010 lifecycle metadata` — records the final lifecycle evidence commit
  and closes the prior report/plan metadata correction.

The active-plan and this report preserve the chronological Task 3 record through `d35509f`; no
“immediately after” ordering is implied for the earlier documentation commits. The current
document-contract alignment is recorded in `a2a9c1d`, and the final evidence metadata is recorded
in `e632c86`; `d35509f` closes the lifecycle metadata.

Final Task 3 evidence commit: `d35509f`.

## Files and contract alignment

- `ARCHITECTURE.md`, `docs/design-docs/index.md`, and
  `docs/design-docs/pre-retrieval-question-routing.md` describe the current single NVIDIA router,
  the grounded normal sequence, and the `routing_unavailable` no-search failure route.
- `docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md` preserves the 2026-08-08
  E-10 tier1/tier2 experiment as historical evidence, while a dated current D-010 section
  supersedes that runtime description.
- `scripts/check_docs.py` now checks both the current D-010 routing prose and the E-10 historical
  boundary/current-section separation, plus the technology ADR, superseded always-generate design
  markers, and current deployment/reliability/RAG/TODO/debt/V3/generated-snapshot records.
- Current authoritative prose explicitly distinguishes router failure (`routing_unavailable`, no
  search) from feature-gated `search_only`; old tiered runtime text remains only in marked
  historical/superseded records.
- `apps/api/app/settings.py` comments now describe the single router and fail-closed
  `routing_unavailable` behavior; no settings behavior changed.
- `apps/api/evaluation/route-fixture-v1.json` and `route-fixture-v1-results.json` retain all case,
  metric, and result values while adding explicit historical/superseded metadata.
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

- D-010 assertions and JSON metadata parsing (including the new current-contract assertion):
  `uv run --project apps/api python -c "import json; from pathlib import Path; [json.loads(Path(p).read_text(encoding='utf-8')) for p in ['apps/api/evaluation/route-fixture-v1.json','apps/api/evaluation/route-fixture-v1-results.json']]; from scripts.check_docs import check_d010_routing_contract, check_d010_active_experiment_contract, check_d010_superseded_designs, check_d010_current_contract_docs; errors = check_d010_routing_contract() + check_d010_active_experiment_contract() + check_d010_superseded_designs() + check_d010_current_contract_docs(); print('d010 assertions passed' if not errors else '\\n'.join(errors)); raise SystemExit(bool(errors))"`
  → exit 0, `d010 assertions passed`.
- Current-doc alignment verification: `uv run --project apps/api ruff check scripts/check_docs.py`
  → exit 0, `All checks passed!`; `git diff --check` → exit 0.
- Full Ruff:
  `uv run --project apps/api ruff check apps/api/app apps/api/scripts apps/api/tests apps/api/migrations packages/law-rag-core/src packages/law-rag-core/tests`
  → exit 0, `All checks passed!`.
- Docstring Ruff:
  `uv run --project apps/api ruff check --select D100,D101,D102,D103,D107,D200,D205,D209,D400,D401,D403 apps/api/app/main.py apps/api/app/adapters/llamaindex_repository.py`
  → exit 0, `All checks passed!`.
- Focused D-010 suite (safe elevated pytest temp path): `43 passed, 1 warning` in 3.89s. The
  warning is the existing Starlette/httpx deprecation.
- Full API suite, with `tests` resolved from the API project directory:
  `$env:PYTHONPATH='.;..\..\packages\law-rag-core\src;..\collector\src'; uv run --directory apps/api python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\25\d010-api-full-relative tests -q`
  → `639 passed, 3 skipped, 1 warning` in 44.83s.
- Full core suite:
  `uv run --project packages/law-rag-core python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\25\d010-core-full-final packages/law-rag-core/tests -q`
  → `26 passed` in 0.25s.
- Repository docs checker:
  `uv run --project apps/api python scripts/check_docs.py`
  → exit 1 with exactly 32 pre-existing broken-link reports. All four D-010 assertion functions
  pass; no new D-010 link or current-contract error is reported, and unrelated documentation
  debt remains untouched.
- Current review-loop rerun counted `docs_checker_exit=1 broken_link_reports=32`; the same 32
  links are pre-existing documentation debt and remain outside this alignment scope.
- `git diff --check` → exit 0.

The NVIDIA-keyed fixture evaluator remains intentionally unrun because it would require a live
provider and user-authorized credentials.
