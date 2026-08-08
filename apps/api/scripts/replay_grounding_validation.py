"""검증기(validate_draft) 코드를 고친 뒤 실제 근거·draft로 재검증한다 - 새 NVIDIA 호출 0회.

2026-08-08 사용자 지적: 검증기를 고칠 때마다 "이제 통과하는지" 확인하려고 매번 다시
호출하는 게 반복되는 낭비였다. `diagnose_grounding_failures.py`가 저장한 근거(hits)와
draft 원문을 그대로 읽어 `validate_draft()`만 다시 돌린다 - 검증기 로직이 바뀔 때마다
이 스크립트만 재실행하면 된다.

Usage: uv run python scripts/replay_grounding_validation.py [입력 JSON 경로, 기본값
evaluation/experiment-e10-grounding-diagnosis.json]
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from app.adapters.openai_answerer import (  # noqa: E402
    AnswerSection,
    ChecklistItem,
    DraftAnswer,
    validate_draft,
)
from app.domain.catalog import SourceKind  # noqa: E402
from app.domain.schemas import SearchHit  # noqa: E402

DEFAULT_INPUT = _API_ROOT / "evaluation" / "experiment-e10-grounding-diagnosis.json"


def _hit_from_dict(data: dict) -> SearchHit:
    return SearchHit(
        provision_id=UUID(data["provision_id"]),
        document_id=UUID(data["document_id"]),
        document_title=data["document_title"],
        source_kind=SourceKind(data["source_kind"]),
        version_label=data["version_label"],
        effective_from=date.fromisoformat(data["effective_from"]),
        effective_to=date.fromisoformat(data["effective_to"]) if data["effective_to"] else None,
        path=data["path"],
        heading=data["heading"],
        content=data["content"],
        source_url=data["source_url"],
        score=data["score"],
    )


def _draft_from_dict(data: dict) -> DraftAnswer:
    return DraftAnswer(
        summary=data["summary"],
        scope=data["scope"],
        sections=[AnswerSection(**s) for s in data["sections"]],
        checklist=[ChecklistItem(**c) for c in data["checklist"]],
        limitations=data["limitations"],
        action=data["action"],
        missing_information=data.get("missing_information", []),
    )


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if "hits" not in json.loads(input_path.read_text(encoding="utf-8"))["cases"][0]:
        raise SystemExit(
            f"{input_path}에는 근거(hits)가 저장돼 있지 않다 - schema_version 1(구판)로 "
            "만들어진 파일이라 replay가 불가하다. diagnose_grounding_failures.py를 다시 "
            "실행해 새로 저장해야 한다."
        )
    report = json.loads(input_path.read_text(encoding="utf-8"))

    print(f"입력: {input_path} ({len(report['cases'])}건)")
    counts: dict[str, int] = {}
    for case in report["cases"]:
        hits = [_hit_from_dict(h) for h in case["hits"]]
        draft = _draft_from_dict(case["draft"])
        passed = validate_draft(draft, hits)
        counts["PASSED" if passed else "REJECTED"] = counts.get(
            "PASSED" if passed else "REJECTED", 0
        ) + 1
        was_passed_before = case["diagnosis"]["passed"]
        changed = " (바뀜!)" if passed != was_passed_before else ""
        print(f"{case['id']}: {'PASSED' if passed else 'REJECTED'}{changed}")

    print("\n집계:", counts)


if __name__ == "__main__":
    main()
