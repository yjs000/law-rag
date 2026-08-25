"""Evaluate the single NVIDIA question router against a fixed fixture.

The evaluator is intentionally live-only: every case is sent to the production
router implementation, and NVIDIA_API_KEY is required.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter  # noqa: E402
from app.domain.routing import QuestionRouter  # noqa: E402

FIXTURE_PATH = _API_ROOT / "evaluation" / "route-fixture-v1.json"
OUTPUT_PATH = _API_ROOT / "evaluation" / "route-fixture-v1-results.json"


def _load_env_local() -> None:
    env_path = _API_ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value and key not in os.environ:
            os.environ[key] = value


def _build_router() -> QuestionRouter:
    _load_env_local()
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is required for routing fixture evaluation")
    return NvidiaNimQuestionRouter(
        api_key=api_key,
        base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        model=os.environ.get(
            "NVIDIA_ROUTE_CLASSIFIER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"
        ),
        timeout_seconds=float(os.environ.get("ROUTE_CLASSIFIER_TIMEOUT_SECONDS", "15")),
    )


async def evaluate() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    router = _build_router()
    results = []
    for case in fixture["cases"]:
        judgment = await router.route(case["question"])
        correct = judgment.route == case["expected_route"]
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected_route": case["expected_route"],
                "predicted_route": judgment.route,
                "reason_code": "router_judgment",
                "confidence": judgment.confidence,
                "correct": correct,
            }
        )

    total = len(results)
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

    return {
        "fixture_size": total,
        "misclassification_rate": round(len(misclassified) / total, 4),
        "unnecessary_search_rate": round(len(unnecessary_search) / total, 4),
        "unnecessary_block_rate": round(len(unnecessary_block) / total, 4),
        "misclassified_cases": [result["id"] for result in misclassified],
        "cases": results,
    }


def main() -> None:
    report = asyncio.run(evaluate())
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fixture size: {report['fixture_size']} -> {OUTPUT_PATH}")
    print("misclassification_rate:", report["misclassification_rate"])
    print("unnecessary_search_rate:", report["unnecessary_search_rate"])
    print("unnecessary_block_rate:", report["unnecessary_block_rate"])
    print("misclassified:", report["misclassified_cases"])


if __name__ == "__main__":
    main()
