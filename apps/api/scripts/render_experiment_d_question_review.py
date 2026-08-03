"""기존 실험 D JSON을 사람이 읽는 질문 검토 문서로 렌더링한다.

검색이나 임베딩은 실행하지 않는다.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_DATASET = Path(__file__).parents[1] / "evaluation" / "experiment-d-v3-1000.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "generated" / "experiment-d-v3-question-review.md"

CATEGORY_DESCRIPTIONS = {
    "exact_path_control": "법령명·조문 번호를 명시했을 때 정확한 조문을 찾는 대조군",
    "heading_lexical_control": "조문 표제의 정확한 핵심어를 사용한 키워드 대조군",
    "semantic_paraphrase": "원문과 다른 질문 표현으로 같은 의무·허용·금지를 묻는 의미 검색군",
    "hierarchy_child": "조·항·호·목의 부모와 자식 문맥을 함께 복원해야 하는 계층 경계군",
    "hard_contrast": "비슷한 인접 규정·표현과 정답 근거를 구분해야 하는 어려운 대조군",
    "temporal_before_effective": "조문 효력 발생 전 기준일이므로 근거 부족이어야 하는 시간 경계군",
    "outside_corpus": "현재 corpus 밖 질문이므로 근거 부족이어야 하는 범위 경계군",
}

STATIC_FLAG_DESCRIPTIONS = {
    "structure_marker_as_answer": "장·절 구조 표지가 조문 답으로 연결됨 — corpus/계층 복구 필요",
    "deleted_provision_control": "삭제 조문이 일반 exact-path 대조군에 포함됨 — 별도 경계군 권장",
    "semantic_near_copy": (
        "의미 변형 질문이 기준 답과 문자열 유사도 0.80 이상 — 난이도 과대평가 위험"
    ),
    "weak_hard_contrast": "hard-contrast의 정답·distractor 유사도 0.30 미만 — 대조 난이도 부족",
    "missing_enumerated_context": (
        "다음 각 호·목을 여는 근거에 하위 조각이 없음 — 기준 답과 qrels 불완전"
    ),
    "synthetic_outside_corpus": "실재하지 않는 제9000조대 질문 — 극단 경계값용 합성 음성 대조군",
}

_STRUCTURE_MARKER = re.compile(r"^제\d+(?:의\d+)?(?:장|절)(?:\s|$)")
_DELETED = re.compile(r"(?:^|\s)삭제(?:\s|<|$)")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실험 D 질문 검토용 Markdown 생성")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _cell(value: object, limit: int | None = None) -> str:
    rendered = " ".join(str(value).split()).replace("|", "\\|")
    if limit is not None and len(rendered) > limit:
        return rendered[: limit - 1].rstrip() + "…"
    return rendered


def _evidence(case: dict[str, Any]) -> str:
    primary = case.get("primary_evidence")
    if not isinstance(primary, dict):
        return "근거 없음이 기대값"
    return f"{primary['document_title']} {primary['path']}"


def _static_flags(case: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    reference = str(case["reference"])
    if _STRUCTURE_MARKER.search(reference):
        flags.append("structure_marker_as_answer")
    if _DELETED.search(reference):
        flags.append("deleted_provision_control")
    if case["category"] == "semantic_paraphrase":
        similarity = difflib.SequenceMatcher(
            None, str(case["user_input"]), reference
        ).ratio()
        if similarity >= 0.80:
            flags.append("semantic_near_copy")
    if case["generation"]["template_id"] == "nonexistent_article":
        flags.append("synthetic_outside_corpus")
    if case["category"] == "hard_contrast" and float(
        case["generation"].get("distractor_similarity", 0.0)
    ) < 0.30:
        flags.append("weak_hard_contrast")
    primary = case.get("primary_evidence")
    if (
        isinstance(primary, dict)
        and case["generation"].get("evidence_scope") == "subtree"
        and re.search(r"다음\s+각\s+(?:호|목)", reference)
        and not re.search(r"(?:^|\s)(?:1\.|가\.)\s*\S", reference)
    ):
        primary_path = f"{primary['path']}/"
        if not any(str(qrel["path"]).startswith(primary_path) for qrel in case["qrels"]):
            flags.append("missing_enumerated_context")
    return flags


def _table(cases: list[dict[str, Any]], *, answer_limit: int = 180) -> list[str]:
    lines = [
        "| ID | 분할 | 질문 | 기준 답 | 기대 근거 | 검토 |",
        "|---|---|---|---|---|---|",
    ]
    for case in cases:
        review = case["review"]
        review_labels = [
            *(
                review["reasons"]
                if review["status"] == "needs_human_review"
                else ["자동 검사"]
            ),
            *_static_flags(case),
        ]
        review_label = ", ".join(review_labels)
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(case["id"]),
                    _cell(case["split"]),
                    _cell(case["user_input"]),
                    _cell(case["reference"], answer_limit),
                    _cell(_evidence(case)),
                    _cell(review_label),
                )
            )
            + " |"
        )
    return lines


def render_review(dataset: dict[str, Any]) -> str:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) != 1000:
        raise ValueError("dataset must contain exactly 1000 cases")
    if any(not isinstance(case, dict) for case in cases):
        raise ValueError("every case must be an object")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[case["category"]].append(case)
    if set(grouped) != set(CATEGORY_DESCRIPTIONS):
        raise ValueError("dataset categories do not match the review contract")

    manual = [
        case for case in cases if case["review"]["status"] == "needs_human_review"
    ]
    flagged: dict[str, list[dict[str, Any]]] = {
        flag: [case for case in cases if flag in _static_flags(case)]
        for flag in STATIC_FLAG_DESCRIPTIONS
    }
    lines = [
        "# 실험 D 질문 검토본",
        "",
        f"> dataset: `{dataset['dataset_version']}`",
        "> 상태: 질문 검토 전 — 1,000문항 검색 실험은 실행하지 않음",
        "> 이 문서는 기존 JSON을 읽어 만든 보기용 문서이며 검색·임베딩을 호출하지 않는다.",
        "",
        "## 먼저 확인할 설계",
        "",
        "| 범주 | 개수 | 확인 목적 |",
        "|---|---:|---|",
    ]
    for category, description in CATEGORY_DESCRIPTIONS.items():
        lines.append(f"| `{category}` | {len(grouped[category])} | {description} |")

    lines.extend(
        [
            "",
            "## 먼저 고쳐야 할 정적 검토 결과",
            "",
            "검색을 실행하지 않고 질문·기준 답 문자열과 메타데이터만 검사한 결과다.",
            "",
            "| 경고 | 개수 | 의미 |",
            "|---|---:|---|",
        ]
    )
    for flag, description in STATIC_FLAG_DESCRIPTIONS.items():
        lines.append(f"| `{flag}` | {len(flagged[flag])} | {description} |")
    lines.extend(
        [
            "",
            "`structure_marker_as_answer`, `deleted_provision_control`, "
            "`semantic_near_copy`, `weak_hard_contrast`, "
            "`missing_enumerated_context`는 0이어야 한다. "
            "`synthetic_outside_corpus`는 의도된 비교군이므로 유지 여부만 확인한다.",
        ]
    )
    for flag in (
        "structure_marker_as_answer",
        "deleted_provision_control",
        "semantic_near_copy",
        "weak_hard_contrast",
        "missing_enumerated_context",
    ):
        lines.extend(
            [
                "",
                f"### {flag} 예시",
                "",
                STATIC_FLAG_DESCRIPTIONS[flag] + ".",
                "",
                *_table(flagged[flag][:10], answer_limit=240),
            ]
        )

    lines.extend(
        [
            "",
            "## 범주별 대표 질문",
            "",
            "각 범주의 앞 5개를 보여준다. 전체 질문은 문서 아래쪽에 범주별로 모두 있다.",
        ]
    )
    for category, description in CATEGORY_DESCRIPTIONS.items():
        lines.extend(
            [
                "",
                f"### {category}",
                "",
                description + ".",
                "",
                *_table(grouped[category][:5]),
            ]
        )

    lines.extend(
        [
            "",
            f"## 수동 검토 필요 {len(manual)}문항",
            "",
            "자동 규칙만으로 의미 적합성을 확정하기 어려운 문항이다. 이 표를 먼저 읽는다.",
            "",
            *_table(manual, answer_limit=300),
            "",
            "## 전체 1,000문항",
            "",
            "아래 표는 질문 검토용이며 검색 순위·점수·실험 결과를 포함하지 않는다.",
        ]
    )
    for category, description in CATEGORY_DESCRIPTIONS.items():
        lines.extend(
            [
                "",
                "<details>",
                f"<summary>{category} — {len(grouped[category])}개</summary>",
                "",
                description + ".",
                "",
                *_table(grouped[category]),
                "",
                "</details>",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    arguments = _arguments()
    dataset = json.loads(arguments.dataset.read_text(encoding="utf-8"))
    output = render_review(dataset)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(output, encoding="utf-8")
    print(
        json.dumps(
            {
                "dataset": str(arguments.dataset),
                "output": str(arguments.output),
                "question_count": len(dataset["cases"]),
                "search_executed": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
