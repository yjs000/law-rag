"""Retry failed single-router fixture cases until they resolve or the cap is reached.

Progress is written to ``evaluation/route-fixture-v1-results.json`` after every pass.
The runner prints ``LIVE_FIXTURE_COMPLETE`` or ``LIVE_FIXTURE_GAVE_UP`` as a monitor
sentinel. NVIDIA_API_KEY is required by the live-only router builder.

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

from app.domain.routing import route_question  # noqa: E402
from scripts.evaluate_routing_fixture import (  # noqa: E402
    FIXTURE_PATH,
    OUTPUT_PATH,
    _build_router,
)

RETRY_INTERVAL_SECONDS = 10
# Safety cap so a background loop cannot run forever if the provider stays congested.
MAX_ATTEMPTS = 180


def _record(case: dict, decision) -> dict:
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_route": case["expected_route"],
        "predicted_route": decision.route,
        "reason_code": decision.reason_code,
        "confidence": decision.confidence,
        "correct": decision.route == case["expected_route"],
    }


def _write_report(fixture_order: list[str], resolved: dict[str, dict]) -> dict:
    results = [resolved[case_id] for case_id in fixture_order if case_id in resolved]
    total = len(fixture_order)
    resolved_count = len(results)
    misclassified = [result for result in results if not result["correct"]]
    unnecessary_search = [
        result
        for result in results
        if result["predicted_route"] == "legal_search"
        and result["expected_route"] != "legal_search"
    ]
    unnecessary_block = [
        result
        for result in results
        if result["expected_route"] == "legal_search"
        and result["predicted_route"] != "legal_search"
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
        "misclassified_cases": [result["id"] for result in misclassified],
        "cases": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


async def main() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture_order = [case["id"] for case in fixture["cases"]]
    router = _build_router()

    resolved: dict[str, dict] = {}
    pending = {case["id"]: case for case in fixture["cases"]}
    _write_report(fixture_order, resolved)

    attempt = 0
    while pending and attempt < MAX_ATTEMPTS:
        attempt += 1
        still_pending: dict[str, dict] = {}
        for case_id, case in pending.items():
            try:
                decision = await route_question(case["question"], router)
                resolved[case_id] = _record(case, decision)
                print(f"attempt {attempt}: {case_id} -> {decision.route} (succeeded)")
            except Exception as exc:
                still_pending[case_id] = case
                print(
                    f"attempt {attempt}: {case_id} failed ({exc.__class__.__name__}), "
                    "will retry"
                )
        pending = still_pending
        _write_report(fixture_order, resolved)
        if pending:
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)

    if pending:
        print(
            f"LIVE_FIXTURE_GAVE_UP after {attempt} attempts, {len(pending)} cases "
            f"unresolved: {sorted(pending)}"
        )
    else:
        report = _write_report(fixture_order, resolved)
        print("LIVE_FIXTURE_COMPLETE")
        print("misclassification_rate:", report["misclassification_rate"])
        print("unnecessary_search_rate:", report["unnecessary_search_rate"])
        print("unnecessary_block_rate:", report["unnecessary_block_rate"])
        print("misclassified:", report["misclassified_cases"])


if __name__ == "__main__":
    asyncio.run(main())
