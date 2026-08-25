"""0043 범위 4: D-10 최대 3문항에 대해 v1(build_messages)과 v2(build_messages_v2)
답변을 동일 검색 결과 위에서 실제 NVIDIA 호출로 생성해 나란히 비교한다.

0045 hosted 검증 통과로 열린 선행조건에 따라 착수한다. 라우팅·검색은 문항당 1회만 실행해
v1/v2가 같은 근거(hits)를 공유하게 하고, 생성만 두 번(v1, v2) 호출한다.

호출 상한: 문항 3개 x (라우팅 최대 1회 + 생성 2회) = 최대 9회. NVIDIA 무료 티어라 금전
비용은 0원.

Usage: uv run python scripts/run_experiment_0043_v1_v2_compare.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import app.main as main_module  # noqa: E402
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer  # noqa: E402
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter  # noqa: E402
from app.adapters.openai_answerer import build_messages, build_messages_v2  # noqa: E402
from app.domain.routing import route_question  # noqa: E402
from app.domain.schemas import QuestionRequest  # noqa: E402

FIXTURE_PATH = _API_ROOT / "evaluation" / "route-fixture-v1.json"
OUTPUT_PATH = _API_ROOT / "evaluation" / "experiment-0043-v1-v2-compare-results.json"
CASE_IDS = ["lay-energy-0201", "lay-energy-0251", "lay-energy-0521"]


def load_cases() -> list[dict]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in fixture["cases"]}
    return [by_id[cid] for cid in CASE_IDS]


def _answerer_for(message_builder) -> NvidiaNimAnswerer:
    settings = main_module.settings
    return NvidiaNimAnswerer(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_answer_model,
        timeout_seconds=settings.answer_timeout_seconds,
        max_output_tokens=settings.answer_max_output_tokens,
        max_attempts=settings.answer_generation_max_attempts,
        message_builder=message_builder,
    )


RETRY_INTERVAL_SECONDS = 10
MAX_RETRIES = 12


async def _with_retry(coro_fn):
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await coro_fn()
        except Exception as exc:  # noqa: BLE001 - shared worker pool 503s are transient
            last_exc = exc
            print(f"  transient error (attempt {attempt}/{MAX_RETRIES}): {exc}")
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)
    raise last_exc  # type: ignore[misc]


def _router() -> NvidiaNimQuestionRouter:
    settings = main_module.settings
    return NvidiaNimQuestionRouter(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_route_classifier_model,
        timeout_seconds=settings.route_classifier_timeout_seconds,
    )


async def run_one(case: dict, router, embedder) -> dict:
    question = case["question"]
    request = QuestionRequest(question=question)
    record: dict[str, object] = {"id": case["id"], "question": question}

    decision = await _with_retry(lambda: route_question(question, router))
    record["route"] = decision.route
    if decision.route != "legal_search":
        record["generation_attempted"] = False
        return record

    query_embedding = (await _with_retry(lambda: embedder.embed([question])))[0]
    hits, _trace = await main_module.repository.search_with_trace(
        question,
        request.as_of_date,
        10,
        query_embedding,
        main_module.NVIDIA_NEMOTRON_512_PROFILE.key,
    )
    hits = [h for h in hits if main_module.is_allowed_source_url(h.source_url)]
    record["retrieved_evidence_count"] = len(hits)
    if not hits:
        record["generation_attempted"] = False
        record["fallback_reason"] = "no_evidence"
        return record

    generation_hits = main_module.select_generation_hits(
        hits, main_module.settings.answer_evidence_max_characters
    )
    record["selected_evidence_count"] = len(generation_hits)
    record["generation_attempted"] = True

    for variant, builder in (("v1", build_messages), ("v2", build_messages_v2)):
        answerer = _answerer_for(builder)
        try:
            draft = await _with_retry(
                lambda answerer=answerer: answerer.answer(request, generation_hits)
            )
        except Exception as exc:
            record[variant] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        valid = main_module.validate_draft(draft, generation_hits)
        record[variant] = {
            "valid": valid,
            "action": draft.action,
            "summary": draft.summary,
            "scope": draft.scope,
            "sections": [s.model_dump() for s in draft.sections],
            "checklist": [c.model_dump() for c in draft.checklist],
            "limitations": draft.limitations,
            "missing_information": draft.missing_information,
        }
    return record


async def main() -> None:
    cases = load_cases()
    router = _router()
    embedder = main_module._embedder()

    results = []
    for case in cases:
        print(f"running {case['id']}...")
        try:
            results.append(await run_one(case, router, embedder))
        except Exception as exc:  # noqa: BLE001 - keep partial results on hard failure
            print(f"  {case['id']} failed permanently: {exc}", flush=True)
            results.append({"id": case["id"], "question": case["question"], "error": str(exc)})

        report = {
            "schema_version": "1",
            "experiment": "0043-v1-v2-compare",
            "run_at": datetime.now(UTC).isoformat(),
            "answer_provider": "nvidia_nim",
            "answer_model": main_module.settings.nvidia_answer_model,
            "cases": results,
        }
        OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {OUTPUT_PATH} ({len(results)}/{len(cases)} cases)", flush=True)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
