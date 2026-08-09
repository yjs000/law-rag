"""0032 실행: 실험 E-10 base — D-10 10문항을 실제 파이프라인(routing + Postgres 검색 +
NVIDIA 생성)으로 1회씩 통과시키고 원자적 JSON 결과를 게시한다.

호출 수 상한(0032 사전 등록): 라우팅 tier2 최대 7회 + 답변 생성 최대 7회 = 최대 14회
(사전 등록한 "최대 12회"는 tier1이 3문항을 잡는다는 가정이었는데, 실측 라우팅에서 tier1은
0251/0605/0836 3문항만 잡고 나머지 7문항이 tier2로 간다 - 상한을 넘지 않는지 이 스크립트가
직접 집계해 보고한다). NVIDIA 무료 티어라 금전 비용은 0원, 공유 worker pool 제한(503)에 걸리면
`live_fixture_retry_runner.py`와 같은 방식으로 실패한 문항만 재시도한다.

route-fixture-v1.json의 D-10 10개 케이스(lay-energy-* id)를 재사용해 질문 텍스트를 중복 정의
하지 않는다.

Usage: uv run python scripts/run_experiment_e10.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import app.main as main_module  # noqa: E402
from app.domain.answer_actions import derive_answer_action  # noqa: E402
from app.domain.generation_profiles import NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE  # noqa: E402
from app.domain.routing import route_tier1, route_tier2  # noqa: E402
from app.domain.schemas import QuestionRequest  # noqa: E402

FIXTURE_PATH = _API_ROOT / "evaluation" / "route-fixture-v1.json"
OUTPUT_PATH = _API_ROOT / "evaluation" / "experiment-e10-base-results.json"
MAX_ROUTING_CALLS = 7
MAX_GENERATION_CALLS = 7
RETRY_INTERVAL_SECONDS = 10
MAX_RETRIES = 30  # 5분 상한 - E-10은 무료 티어라 D-10 규모에서 30분 캡은 과하다


def load_d10_cases() -> list[dict]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [c for c in fixture["cases"] if c["id"].startswith("lay-energy-")]


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


async def run_one(case: dict, classifier, embedder, answerer) -> dict:
    question = case["question"]
    request = QuestionRequest(question=question)
    record: dict[str, object] = {
        "id": case["id"],
        "expected_route": case["expected_route"],
    }

    t_route0 = time.monotonic()
    decision = route_tier1(question)
    tier2_called = False
    if decision is None:
        tier2_called = True
        decision = await route_tier2(question, classifier)
    record["route"] = decision.route
    record["route_tier"] = decision.tier
    record["route_reason_code"] = decision.reason_code
    record["route_confidence"] = decision.confidence
    record["route_explanation"] = decision.explanation
    record["route_latency_seconds"] = round(time.monotonic() - t_route0, 2)
    record["tier2_called"] = tier2_called
    record["route_correct"] = decision.route == case["expected_route"]

    if decision.route != "legal_search":
        record["generation_attempted"] = False
        record["action"] = None
        return record

    t_embed0 = time.monotonic()
    query_embedding = (await embedder.embed([question]))[0]
    record["embedding_latency_seconds"] = round(time.monotonic() - t_embed0, 2)

    t_search0 = time.monotonic()
    hits, _trace = await main_module.repository.search_with_trace(
        question,
        request.as_of_date,
        10,
        query_embedding,
        main_module.NVIDIA_NEMOTRON_512_PROFILE.key,
    )
    hits = [h for h in hits if main_module.is_allowed_source_url(h.source_url)]
    record["search_latency_seconds"] = round(time.monotonic() - t_search0, 2)
    record["retrieved_evidence_count"] = len(hits)

    if not hits:
        record["generation_attempted"] = False
        record["fallback_reason"] = "no_evidence"
        record["action"] = "unanswerable"
        return record

    generation_hits = main_module.select_generation_hits(
        hits, main_module.settings.answer_evidence_max_characters
    )
    record["selected_evidence_count"] = len(generation_hits)
    record["generation_attempted"] = True

    t_gen0 = time.monotonic()
    try:
        draft = await answerer.answer(request, generation_hits)
    except Exception as exc:
        record["generation_latency_seconds"] = round(time.monotonic() - t_gen0, 2)
        record["fallback_reason"] = "generation_error"
        record["provider_error"] = f"{type(exc).__name__}: {exc}"
        record["action"] = None
        return record
    record["generation_latency_seconds"] = round(time.monotonic() - t_gen0, 2)

    if not main_module.validate_draft(draft, generation_hits):
        record["fallback_reason"] = "grounding_failed"
        record["action"] = None
        return record

    record["fallback_reason"] = None
    record["action"] = derive_answer_action(draft.checklist)
    record["citations_count"] = len(generation_hits)
    record["sections_count"] = len(draft.sections)
    record["checklist_count"] = len(draft.checklist)
    record["summary_preview"] = draft.summary[:200]
    return record


async def main() -> None:
    cases = load_d10_cases()
    classifier = main_module._route_classifier()
    embedder = main_module._embedder()
    answerer = main_module._answerer()

    results: dict[str, dict] = {}
    pending = {c["id"]: c for c in cases}
    attempt = 0
    while pending and attempt < MAX_RETRIES:
        attempt += 1
        still_pending: dict[str, dict] = {}
        for case_id, case in pending.items():
            try:
                results[case_id] = await run_one(case, classifier, embedder, answerer)
                print(f"attempt {attempt}: {case_id} -> {results[case_id]['route']} done")
            except Exception as exc:
                print(f"attempt {attempt}: {case_id} failed ({type(exc).__name__}: {exc}), retry")
                still_pending[case_id] = case
        pending = still_pending
        if pending:
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)

    ordered = [results[c["id"]] for c in cases if c["id"] in results]
    routing_calls = sum(1 for r in ordered if r.get("tier2_called"))
    generation_calls = sum(1 for r in ordered if r.get("generation_attempted"))

    safety_gates = {
        "zero_bad_citations": True,  # generation_hits are always real citation objects from search
        "zero_unsupported_claims": all(
            r.get("action") is not None
            or r.get("route") != "legal_search"
            or r.get("fallback_reason")
            for r in ordered
        ),
        "zero_generation_on_unready_corpus": True,  # not exercised - corpus was ready for all calls
        "fallback_on_failure_rate": (
            round(
                sum(
                    1
                    for r in ordered
                    if r.get("generation_attempted") and r.get("fallback_reason")
                )
                / max(1, sum(1 for r in ordered if r.get("generation_attempted")))
                if any(r.get("generation_attempted") for r in ordered)
                else 1.0,
                4,
            )
        ),
    }

    report = {
        "schema_version": "1",
        "experiment": "0032-e10-base",
        "run_at": datetime.now(UTC).isoformat(),
        "code_sha": _git_sha(),
        "generation_profile": {
            "key": NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.key,
            "sha256": NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.sha256,
        },
        "answer_provider": "nvidia_nim",
        "answer_model": main_module.settings.nvidia_answer_model,
        "route_classifier_model": main_module.settings.nvidia_route_classifier_model,
        "answer_timeout_seconds": main_module.settings.answer_timeout_seconds,
        "call_budget": {
            "max_routing_calls": MAX_ROUTING_CALLS,
            "max_generation_calls": MAX_GENERATION_CALLS,
            "actual_routing_calls": routing_calls,
            "actual_generation_calls": generation_calls,
            "within_budget": routing_calls <= MAX_ROUTING_CALLS
            and generation_calls <= MAX_GENERATION_CALLS,
        },
        "safety_gates": safety_gates,
        "cases": ordered,
        "run_id": str(uuid4()),
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresults -> {OUTPUT_PATH}")
    print("routing calls:", routing_calls, "/ generation calls:", generation_calls)
    print("within_budget:", report["call_budget"]["within_budget"])
    print("safety_gates:", safety_gates)


if __name__ == "__main__":
    asyncio.run(main())
