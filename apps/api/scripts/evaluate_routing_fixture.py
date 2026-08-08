"""0028 M4.5 완료 조건: 고정 fixture로 라우팅 오분류율·불필요 검색률·tier별 호출 비율을 잰다.

기본은 MockRouteClassifier(무료, 네트워크 호출 없음)로 돈다. `--live`를 주면 실제
NvidiaNimRouteClassifier로 tier 2를 호출한다 - NVIDIA_API_KEY가 환경(.env.local 등)에 있어야
하며, 이 경우 fixture 크기만큼(최대 14회) 실제 NIM 호출이 나간다.

Usage:
    uv run python scripts/evaluate_routing_fixture.py           # mock tier 2
    uv run python scripts/evaluate_routing_fixture.py --live    # 실제 NVIDIA 호출
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

from app.adapters.mock_route_classifier import MockRouteClassifier  # noqa: E402
from app.adapters.nvidia_nim_route_classifier import NvidiaNimRouteClassifier  # noqa: E402
from app.domain.routing import RouteClassifier, route_tier1, route_tier2  # noqa: E402

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


def _build_classifier(*, live: bool) -> tuple[RouteClassifier, str]:
    if not live:
        return (
            MockRouteClassifier(),
            "PROVISIONAL - tier 2 is MockRouteClassifier, not a real NVIDIA call",
        )
    _load_env_local()
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("--live requires NVIDIA_API_KEY in the environment or .env.local")
    classifier = NvidiaNimRouteClassifier(
        api_key=api_key,
        base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        model=os.environ.get(
            "NVIDIA_ROUTE_CLASSIFIER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"
        ),
        timeout_seconds=float(os.environ.get("ROUTE_CLASSIFIER_TIMEOUT_SECONDS", "15")),
    )
    return classifier, "LIVE - tier 2 used a real NVIDIA NIM call for every unresolved case"


async def evaluate(*, live: bool) -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    classifier, cost_gate_status = _build_classifier(live=live)
    results = []
    for case in fixture["cases"]:
        decision = route_tier1(case["question"])
        if decision is None:
            if live:
                # 무료 티어 rate limit(관측: 초당 다수 호출 시 503 ResourceExhausted)을
                # 피하려고 호출 사이 짧게 쉰다.
                await asyncio.sleep(2)
            decision = await route_tier2(case["question"], classifier)
        correct = decision.route == case["expected_route"]
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected_route": case["expected_route"],
                "predicted_route": decision.route,
                "tier": decision.tier,
                "reason_code": decision.reason_code,
                "confidence": decision.confidence,
                "correct": correct,
            }
        )

    total = len(results)
    misclassified = [r for r in results if not r["correct"]]
    tier1_resolved = [r for r in results if r["tier"] == 1]
    tier2_resolved = [r for r in results if r["tier"] == 2]
    # 불필요 검색: 실제로는 검색을 실행하면 안 되는데(legal_search가 아닌데) legal_search로
    # 잘못 예측해 검색이 실행된 경우.
    unnecessary_search = [
        r
        for r in results
        if r["predicted_route"] == "legal_search" and r["expected_route"] != "legal_search"
    ]
    # 불필요 차단: 실제로는 검색해도 되는데(legal_search인데) 다른 route로 잘못 예측해
    # 검색을 막아버린 경우.
    unnecessary_block = [
        r
        for r in results
        if r["expected_route"] == "legal_search" and r["predicted_route"] != "legal_search"
    ]

    return {
        "fixture_size": total,
        "misclassification_rate": round(len(misclassified) / total, 4),
        "unnecessary_search_rate": round(len(unnecessary_search) / total, 4),
        "unnecessary_block_rate": round(len(unnecessary_block) / total, 4),
        "tier1_resolution_rate": round(len(tier1_resolved) / total, 4),
        "tier2_resolution_rate": round(len(tier2_resolved) / total, 4),
        "misclassified_cases": [r["id"] for r in misclassified],
        "cost_gate_status": cost_gate_status,
        "cases": results,
    }


def main() -> None:
    live = "--live" in sys.argv
    report = asyncio.run(evaluate(live=live))
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"fixture size: {report['fixture_size']} -> {OUTPUT_PATH}")
    print("misclassification_rate:", report["misclassification_rate"])
    print("unnecessary_search_rate:", report["unnecessary_search_rate"])
    print("unnecessary_block_rate:", report["unnecessary_block_rate"])
    print("tier1_resolution_rate:", report["tier1_resolution_rate"])
    print("tier2_resolution_rate:", report["tier2_resolution_rate"])
    print("misclassified:", report["misclassified_cases"])
    print(report["cost_gate_status"])


if __name__ == "__main__":
    main()
