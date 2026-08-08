"""0028 M4.5: retry the --live fixture run every 10s until all tier-2 cases succeed.

`evaluate_routing_fixture.py --live` hit NVIDIA's shared free-tier worker-pool limit
("Worker local total request limit reached (X/32)", HTTP 503) partway through the
14-case fixture on 2026-08-08 (see 0028 decision log). That congestion is described in
NVIDIA's own developer forum as transient - this script retries only the cases that
failed, every 10 seconds, until they all succeed or a safety cap is hit, instead of
re-running the whole batch (which would burn free-tier calls on cases already resolved).

Progress is written to evaluation/route-fixture-v1-results.json after every pass so it
can be inspected while this runs in the background. Prints "LIVE_FIXTURE_COMPLETE" on
success or "LIVE_FIXTURE_GAVE_UP" if the retry cap is hit, as a sentinel for a
process-monitor to grep for.

Usage: uv run python scripts/live_fixture_retry_runner.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from app.domain.routing import route_tier1, route_tier2  # noqa: E402
from scripts.evaluate_routing_fixture import (  # noqa: E402
    FIXTURE_PATH,
    OUTPUT_PATH,
    _build_classifier,
)

RETRY_INTERVAL_SECONDS = 10
# Safety cap so a background loop can't run forever if the free-tier pool stays
# congested: 180 * 10s = 30 minutes of wall-clock retrying.
MAX_ATTEMPTS = 180


def _record(case: dict, decision) -> dict:
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_route": case["expected_route"],
        "predicted_route": decision.route,
        "tier": decision.tier,
        "reason_code": decision.reason_code,
        "confidence": decision.confidence,
        "correct": decision.route == case["expected_route"],
    }


def _write_report(
    fixture_order: list[str], resolved: dict[str, dict], cost_gate_status: str
) -> dict:
    results = [resolved[case_id] for case_id in fixture_order if case_id in resolved]
    total = len(fixture_order)
    resolved_count = len(results)
    misclassified = [r for r in results if not r["correct"]]
    tier1_resolved = [r for r in results if r["tier"] == 1]
    tier2_resolved = [r for r in results if r["tier"] == 2]
    unnecessary_search = [
        r
        for r in results
        if r["predicted_route"] == "legal_search" and r["expected_route"] != "legal_search"
    ]
    unnecessary_block = [
        r
        for r in results
        if r["expected_route"] == "legal_search" and r["predicted_route"] != "legal_search"
    ]
    report = {
        "fixture_size": total,
        "resolved_count": resolved_count,
        "pending_count": total - resolved_count,
        "misclassification_rate": round(len(misclassified) / resolved_count, 4)
        if resolved_count
        else None,
        "unnecessary_search_rate": round(len(unnecessary_search) / resolved_count, 4)
        if resolved_count
        else None,
        "unnecessary_block_rate": round(len(unnecessary_block) / resolved_count, 4)
        if resolved_count
        else None,
        "tier1_resolution_rate": round(len(tier1_resolved) / resolved_count, 4)
        if resolved_count
        else None,
        "tier2_resolution_rate": round(len(tier2_resolved) / resolved_count, 4)
        if resolved_count
        else None,
        "misclassified_cases": [r["id"] for r in misclassified],
        "cost_gate_status": cost_gate_status,
        "cases": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


async def main() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture_order = [c["id"] for c in fixture["cases"]]
    classifier, cost_gate_status = _build_classifier(live=True)

    resolved: dict[str, dict] = {}
    pending = {c["id"]: c for c in fixture["cases"]}

    # tier 1 is free/local - resolve those immediately, no retry loop needed.
    for case_id, case in list(pending.items()):
        decision = route_tier1(case["question"])
        if decision is not None:
            resolved[case_id] = _record(case, decision)
            del pending[case_id]
    print(
        f"tier1 resolved {len(resolved)}/{len(fixture_order)} immediately, "
        f"{len(pending)} need tier2"
    )
    _write_report(fixture_order, resolved, cost_gate_status)

    attempt = 0
    while pending and attempt < MAX_ATTEMPTS:
        attempt += 1
        still_pending: dict[str, dict] = {}
        for case_id, case in pending.items():
            try:
                decision = await route_tier2(case["question"], classifier)
                resolved[case_id] = _record(case, decision)
                print(f"attempt {attempt}: {case_id} -> {decision.route} (succeeded)")
            except Exception as exc:
                still_pending[case_id] = case
                print(f"attempt {attempt}: {case_id} failed ({exc.__class__.__name__}), will retry")
        pending = still_pending
        _write_report(fixture_order, resolved, cost_gate_status)
        if pending:
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)

    if pending:
        print(f"LIVE_FIXTURE_GAVE_UP after {attempt} attempts, {len(pending)} cases unresolved: "
              f"{sorted(pending)}")
    else:
        report = _write_report(fixture_order, resolved, cost_gate_status)
        print("LIVE_FIXTURE_COMPLETE")
        print("misclassification_rate:", report["misclassification_rate"])
        print("unnecessary_search_rate:", report["unnecessary_search_rate"])
        print("unnecessary_block_rate:", report["unnecessary_block_rate"])
        print("tier1_resolution_rate:", report["tier1_resolution_rate"])
        print("tier2_resolution_rate:", report["tier2_resolution_rate"])
        print("misclassified:", report["misclassified_cases"])


if __name__ == "__main__":
    asyncio.run(main())
