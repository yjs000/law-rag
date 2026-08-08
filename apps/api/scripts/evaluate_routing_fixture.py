"""0028 M4.5 완료 조건: 고정 fixture로 라우팅 오분류율·불필요 검색률·tier별 호출 비율을 잰다.

**중요**: tier 2는 실제 NVIDIA API key가 아직 배선되지 않아 MockRouteClassifier(항상
legal_search로 기본 처리, 힌트가 있을 때만 그 힌트를 그대로 따름)로 돌아간다. 이 스크립트가
찍는 misclassification_rate·tier2_resolution_rate는 그래서 **잠정치**다 - 실제 API key가
붙으면 다시 실행해서 갱신해야 한다(app/main.py의 `_route_classifier()` TODO 참고).

Usage: uv run python scripts/evaluate_routing_fixture.py
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

from app.adapters.mock_route_classifier import MockRouteClassifier  # noqa: E402
from app.domain.routing import route_tier1, route_tier2  # noqa: E402

FIXTURE_PATH = _API_ROOT / "evaluation" / "route-fixture-v1.json"
OUTPUT_PATH = _API_ROOT / "evaluation" / "route-fixture-v1-results.json"


async def evaluate() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    classifier = MockRouteClassifier()
    results = []
    for case in fixture["cases"]:
        decision = route_tier1(case["question"])
        if decision is None:
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
        "cost_gate_status": "PROVISIONAL - tier 2 is MockRouteClassifier, not a real NVIDIA call",
        "cases": results,
    }


def main() -> None:
    report = asyncio.run(evaluate())
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
