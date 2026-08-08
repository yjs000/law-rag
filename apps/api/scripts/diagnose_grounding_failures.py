"""0032 E-10 후속: grounding_failed(2026-08-08 E-10 base 4/6) 원인 진단.

1차 E-10 실행이 거부된 draft 내용을 저장하지 않아 원인을 알 수 없었다 - 이 스크립트는 같은
D-10 문항(기본: 1차에서 grounding_failed였던 4개)을 다시 생성 호출하되, 이번엔
`validate_draft`(app/adapters/openai_answerer.py)가 쓰는 실제 검증 함수들을 그대로 재사용해
**어느 단계에서 왜** 거부됐는지와 draft 원문 전체를 함께 기록한다. 검증 로직 자체는 복제하지
않는다(원본과 결과가 갈릴 위험을 피하려고 private 함수를 직접 import해서 쓴다).

비용: 이 실행 자체가 새 NVIDIA 생성 호출(기본 4회, 무료 티어)이다 - 1차 결과를 저장 안 해서
다시 부르는 것이지, "결과 저장" 자체에는 추가 호출이 없다.

Usage: uv run python scripts/diagnose_grounding_failures.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import app.main as main_module  # noqa: E402
from app.adapters.openai_answerer import (  # noqa: E402
    _NORMATIVE_SIGNAL_PATTERNS,
    _contains_normative_assertion,
    _evidence_for_citations,
    _text_matches_evidence,
    _texts_match_citations,
)
from app.domain.schemas import QuestionRequest  # noqa: E402

OUTPUT_PATH = _API_ROOT / "evaluation" / "experiment-e10-grounding-diagnosis.json"
RETRY_INTERVAL_SECONDS = 10
MAX_ATTEMPTS = 12

# 1차 E-10 base(2026-08-08)에서 grounding_failed였던 4문항. route-fixture-v1.json의 D-10
# 케이스와 같은 질문 텍스트.
TARGET_CASES = {
    "lay-energy-0521": (
        "발전량은 기록되지만 신재생에너지 공급인증서(REC)가 발급되지 않고 있는데, "
        "발급 대상과 신청 조건을 어떻게 확인하나요?"
    ),
    "lay-energy-0601": (
        "태양광 설치비 지원을 받을 수 있는지 알아보는데, 지원 대상인지 어떤 조건으로 판단하나요?"
    ),
    "lay-energy-0346": (
        "전력망 연결 공사비가 예상보다 많이 나왔는데, 공사비가 어떻게 계산됐는지 "
        "어떤 항목을 확인해야 하나요?"
    ),
    "lay-energy-0943": (
        "태양광 패널의 빛 반사가 생활에 불편을 주는데, 빛 반사를 줄이거나 시정 조치를 "
        "요청하려면 어디에 민원을 내야 하나요?"
    ),
}


def diagnose_validate_draft(draft, hits) -> dict:
    """validate_draft()와 같은 순서·같은 함수를 써서 실패 지점을 남긴다."""
    if not hits or not draft.sections or not draft.checklist:
        return {"passed": False, "failed_at": "empty_hits_sections_or_checklist"}
    hit_by_id = {f"C{index}": hit for index, hit in enumerate(hits, 1)}
    all_evidence = " ".join(
        f"{hit.document_title} {hit.heading or ''} {hit.content}" for hit in hits
    )
    if not _text_matches_evidence(draft.summary, all_evidence):
        return {"passed": False, "failed_at": "summary_vs_evidence", "text": draft.summary}
    if _contains_normative_assertion(draft.scope):
        return {"passed": False, "failed_at": "scope_has_normative_assertion", "text": draft.scope}
    for limitation in draft.limitations:
        if _contains_normative_assertion(limitation) and not _text_matches_evidence(
            limitation, all_evidence
        ):
            return {
                "passed": False,
                "failed_at": "limitation_unsupported_normative",
                "text": limitation,
            }
    for i, section in enumerate(draft.sections):
        if not _texts_match_citations(
            (section.claim, section.explanation), section.citation_ids, hit_by_id
        ):
            return {
                "passed": False,
                "failed_at": f"section_{i}_citation_mismatch",
                "claim": section.claim,
                "explanation": section.explanation,
                "citation_ids": section.citation_ids,
            }
    for i, item in enumerate(draft.checklist):
        if not _texts_match_citations((item.label,), item.citation_ids, hit_by_id):
            return {
                "passed": False,
                "failed_at": f"checklist_{i}_citation_mismatch",
                "label": item.label,
                "citation_ids": item.citation_ids,
            }
        item_evidence = _evidence_for_citations(item.citation_ids, hit_by_id)
        if item.status == "required" and not _NORMATIVE_SIGNAL_PATTERNS["obligation"].search(
            item_evidence
        ):
            return {
                "passed": False,
                "failed_at": f"checklist_{i}_required_no_obligation_signal",
                "label": item.label,
                "evidence_preview": item_evidence[:300],
            }
        if item.status == "not_applicable" and not (
            _NORMATIVE_SIGNAL_PATTERNS["exemption"].search(item_evidence)
            or _NORMATIVE_SIGNAL_PATTERNS["negation"].search(item_evidence)
        ):
            return {
                "passed": False,
                "failed_at": f"checklist_{i}_not_applicable_no_exemption_signal",
                "label": item.label,
                "evidence_preview": item_evidence[:300],
            }
    return {"passed": True}


async def run_one(case_id: str, question: str, answerer) -> dict:
    request = QuestionRequest(question=question)
    embedder = main_module._embedder()
    query_embedding = (await embedder.embed([question]))[0]
    hits, _trace = await main_module.repository.search_with_trace(
        question,
        request.as_of_date,
        10,
        query_embedding,
        main_module.NVIDIA_NEMOTRON_512_PROFILE.key,
    )
    hits = [h for h in hits if main_module.is_allowed_source_url(h.source_url)]
    generation_hits = main_module.select_generation_hits(
        hits, main_module.settings.answer_evidence_max_characters
    )

    t0 = time.monotonic()
    draft = await answerer.answer(request, generation_hits)
    latency = round(time.monotonic() - t0, 2)

    diagnosis = diagnose_validate_draft(draft, generation_hits)
    return {
        "id": case_id,
        "question": question,
        "generation_latency_seconds": latency,
        "citation_ids_available": [f"C{i}" for i in range(1, len(generation_hits) + 1)],
        "draft": {
            "summary": draft.summary,
            "scope": draft.scope,
            "sections": [
                {"claim": s.claim, "explanation": s.explanation, "citation_ids": s.citation_ids}
                for s in draft.sections
            ],
            "checklist": [
                {"label": c.label, "status": c.status, "citation_ids": c.citation_ids}
                for c in draft.checklist
            ],
            "limitations": draft.limitations,
        },
        "diagnosis": diagnosis,
    }


async def main() -> None:
    answerer = main_module._answerer()
    results: dict[str, dict] = {}
    pending = dict(TARGET_CASES)
    attempt = 0
    while pending and attempt < MAX_ATTEMPTS:
        attempt += 1
        still_pending: dict[str, str] = {}
        for case_id, question in pending.items():
            try:
                results[case_id] = await run_one(case_id, question, answerer)
                diagnosis = results[case_id]["diagnosis"]
                outcome = "PASSED" if diagnosis["passed"] else diagnosis["failed_at"]
                print(f"attempt {attempt}: {case_id} -> {outcome}")
            except Exception as exc:
                print(f"attempt {attempt}: {case_id} failed ({type(exc).__name__}: {exc}), retry")
                still_pending[case_id] = question
        pending = still_pending
        if pending:
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)

    report = {"schema_version": "1", "cases": list(results.values())}
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUTPUT_PATH}")
    failed_at_counts: dict[str, int] = {}
    for r in results.values():
        key = r["diagnosis"]["failed_at"] if not r["diagnosis"]["passed"] else "PASSED"
        failed_at_counts[key] = failed_at_counts.get(key, 0) + 1
    print("failure breakdown:", failed_at_counts)


if __name__ == "__main__":
    asyncio.run(main())
