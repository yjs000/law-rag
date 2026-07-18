"""고정 질문 한 건의 검색 시간을 반복 측정한다."""

import argparse
import asyncio
import json
import statistics
import sys
from datetime import date
from pathlib import Path

from app.adapters.postgres_repository import PostgresLegalRepository
from app.settings import get_settings


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parents[1] / "evaluation" / "retrieval-debug-v1.json",
    )
    return parser.parse_args()


def _case(dataset: Path, case_id: str) -> dict:
    cases = json.loads(dataset.read_text(encoding="utf-8"))
    try:
        return next(case for case in cases if case["id"] == case_id)
    except StopIteration as exc:
        raise SystemExit(f"case를 찾을 수 없습니다: {case_id}") from exc


async def _run(case: dict, repetitions: int) -> dict:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.database_url)
    values = []
    traces = []
    for _ in range(max(1, min(repetitions, 100))):
        _, trace = await repository.search_with_trace(
            case["question"], date.fromisoformat(case["as_of_date"]), 10, None
        )
        values.append(trace.total_duration_ms)
        traces.append(trace.as_dict())
    await repository.engine.dispose()
    ordered = sorted(values)
    return {
        "case_id": case["id"],
        "question": case["question"],
        "repetitions": len(values),
        "minimum_ms": min(values),
        "p50_ms": statistics.median(values),
        "p95_ms": ordered[min(len(ordered) - 1, round(len(ordered) * 0.95))],
        "maximum_ms": max(values),
        "under_1000_count": sum(value < 1000 for value in values),
        "runs": traces,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = _arguments()
    print(
        json.dumps(
            asyncio.run(
                _run(_case(arguments.dataset, arguments.case_id), arguments.repetitions)
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
