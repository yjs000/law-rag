from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
DATED_DOCS = {
    ROOT / "ARCHITECTURE.md": re.compile(r"최종 갱신:\s*(\d{4}-\d{2}-\d{2})"),
    ROOT / "docs" / "QUALITY_SCORE.md": re.compile(r"평가일:\s*(\d{4}-\d{2}-\d{2})"),
}
MAX_AGE_DAYS = 45


def _section(text: str, heading: str) -> str:
    """Return one Markdown section, stopping at the next same-level heading."""
    start = text.find(heading)
    if start < 0:
        return ""
    body = text[start:]
    next_heading = re.search(r"\n## (?!#)", body[len(heading) :])
    if next_heading is None:
        return body
    end = len(heading) + next_heading.start() + 1
    return body[:end]


def markdown_files() -> list[Path]:
    return [*sorted(ROOT.glob("*.md")), *sorted((ROOT / "docs").rglob("*.md"))]


def check_links(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for raw_target in MARKDOWN_LINK.findall(text):
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "/")):
            continue
        resolved = (path.parent / unquote(target)).resolve()
        if not resolved.is_relative_to(ROOT) or not resolved.exists():
            errors.append(f"{path.relative_to(ROOT)}: broken link -> {raw_target}")
    return errors


def check_freshness(today: date) -> list[str]:
    errors: list[str] = []
    for path, pattern in DATED_DOCS.items():
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match is None:
            errors.append(f"{path.relative_to(ROOT)}: 기준 날짜가 없습니다")
            continue
        updated = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        age = (today - updated).days
        if age < 0 or age > MAX_AGE_DAYS:
            errors.append(
                f"{path.relative_to(ROOT)}: 기준 날짜 {updated}가 {age}일 경과했습니다"
            )
    return errors


def check_d010_routing_contract() -> list[str]:
    """Keep the current D-010 routing contract executable in docs review."""
    errors: list[str] = []
    index_path = ROOT / "docs" / "design-docs" / "index.md"
    architecture_path = ROOT / "ARCHITECTURE.md"
    index_text = index_path.read_text(encoding="utf-8")
    architecture_text = architecture_path.read_text(encoding="utf-8")

    if "single-stage-router-and-failure-response.md" not in index_text:
        errors.append(
            "docs/design-docs/index.md: D-010 single-stage design link is missing"
        )

    for required in ("routing_unavailable", "answer_generation", "answer_validation"):
        if required not in architecture_text:
            errors.append(f"ARCHITECTURE.md: D-010 contract is missing {required}")

    routing_section = _section(architecture_text, "## 질문 사전 라우팅")
    if not routing_section:
        errors.append("ARCHITECTURE.md: D-010 routing section is missing")
    else:
        if re.search(r"\btier[12]\b", routing_section, flags=re.IGNORECASE):
            errors.append(
                "ARCHITECTURE.md: current routing section still describes tier1/tier2"
            )
        if re.search(
            r"(?:timeout|타임아웃|시간 초과)[^\n]{0,100}legal_search|"
            r"legal_search[^\n]{0,100}(?:timeout|타임아웃|시간 초과)",
            routing_section,
            flags=re.IGNORECASE,
        ):
            errors.append(
                "ARCHITECTURE.md: router timeout must not proceed as legal_search"
            )
    return errors


def check_d010_active_experiment_contract() -> list[str]:
    """Keep the active E-10 plan clearly historical after D-010 superseded it."""
    errors: list[str] = []
    path = ROOT / "docs" / "exec-plans" / "active" / "0032-experiment-e-10-ai-answer-evaluation.md"
    text = path.read_text(encoding="utf-8")
    current_section = _section(text, "## 현재 D-010 실행 계약")
    if not current_section:
        errors.append(
            "docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md: "
            "current D-010 supersession section is missing"
        )
    elif re.search(r"\btier[12]\b", current_section, flags=re.IGNORECASE):
        errors.append(
            "docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md: "
            "current D-010 section still describes tier1/tier2"
        )
    if "## 역사적 E-10 실행 기록" not in text:
        errors.append(
            "docs/exec-plans/active/0032-experiment-e-10-ai-answer-evaluation.md: "
            "historical E-10 boundary is missing"
        )
    return errors


def check_d010_superseded_designs() -> list[str]:
    """Keep superseded pre-D-010 design and evaluation records visibly historical."""
    errors: list[str] = []
    technology_path = ROOT / "docs" / "design-docs" / "technology-stack.md"
    always_generate_path = ROOT / "docs" / "design-docs" / "always-generate-answer.md"
    technology_text = technology_path.read_text(encoding="utf-8")
    always_generate_text = always_generate_path.read_text(encoding="utf-8")
    technology_normalized = " ".join(technology_text.split())

    if "routing_unavailable" not in technology_text or "단일 `QuestionRouter`" not in technology_text:
        errors.append(
            "docs/design-docs/technology-stack.md: current D-010 router contract is missing"
        )
    if "kiwipiepy`는 D-010에서 제거했으며 런타임 의존성이 아니다" not in technology_normalized:
        errors.append(
            "docs/design-docs/technology-stack.md: Kiwi runtime status is not explicit"
        )
    if "상태: 역사적·superseded — D-010(0057)으로 대체됨" not in always_generate_text:
        errors.append(
            "docs/design-docs/always-generate-answer.md: superseded status is missing"
        )
    if "single-stage-router-and-failure-response.md" not in always_generate_text:
        errors.append(
            "docs/design-docs/always-generate-answer.md: D-010 successor link is missing"
        )
    return errors


def main() -> int:
    errors = [error for path in markdown_files() for error in check_links(path)]
    errors.extend(check_freshness(date.today()))
    errors.extend(check_d010_routing_contract())
    errors.extend(check_d010_active_experiment_contract())
    errors.extend(check_d010_superseded_designs())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"docs check passed: {len(markdown_files())} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
