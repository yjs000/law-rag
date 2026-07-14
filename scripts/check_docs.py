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


def markdown_files() -> list[Path]:
    return [ROOT / "AGENTS.md", ROOT / "ARCHITECTURE.md", *sorted((ROOT / "docs").rglob("*.md"))]


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


def main() -> int:
    errors = [error for path in markdown_files() for error in check_links(path)]
    errors.extend(check_freshness(date.today()))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"docs check passed: {len(markdown_files())} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
