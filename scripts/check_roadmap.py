"""Read-only validation and generated-roadmap comparison command."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.roadmap_registry import (  # noqa: E402
    PlanRecord,
    load_registry,
    roadmap_digest,
    validate_registry,
)
from scripts.render_roadmap import RENDER_COMMAND, render_roadmap  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
ROADMAP_RELATIVE_PATH = Path("docs/ROADMAP.md")


def _read_roadmap(root: Path, staged: bool) -> bytes | None:
    if not staged:
        try:
            return (root / ROADMAP_RELATIVE_PATH).read_bytes()
        except (OSError, UnicodeError):
            return None

    try:
        result = subprocess.run(
            ["git", "show", f":{ROADMAP_RELATIVE_PATH.as_posix()}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _display_line(line: bytes | None) -> str:
    if line is None:
        return "<없음>"
    return line.decode("utf-8", errors="replace").rstrip("\r\n") or "<빈 줄>"


def _first_difference(expected: bytes, actual: bytes) -> tuple[int, str, str] | None:
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    line_count = max(len(expected_lines), len(actual_lines))
    for index in range(line_count):
        expected_line = expected_lines[index] if index < len(expected_lines) else None
        actual_line = actual_lines[index] if index < len(actual_lines) else None
        if expected_line != actual_line:
            return index + 1, _display_line(expected_line), _display_line(actual_line)
    return None


def _mismatch_message(expected: bytes, actual: bytes) -> str:
    difference = _first_difference(expected, actual)
    if difference is None:
        difference = (1, "<바이트 불일치>", "<바이트 불일치>")
    line_number, expected_line, actual_line = difference
    return (
        "docs/ROADMAP.md가 생성 결과와 다릅니다 "
        f"(첫 번째 차이: {line_number}번째 줄)\n"
        f"예상: {expected_line}\n"
        f"현재: {actual_line}\n"
        f"수정: {RENDER_COMMAND}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="계획과 roadmap을 작업 트리 대신 Git index에서 읽습니다.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def _print_errors(errors: Sequence[object]) -> None:
    for error in errors:
        print(str(error), file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate plans and compare the generated roadmap without writing files."""

    args = _parser().parse_args(argv)
    root = args.repo_root.resolve()
    records: list[PlanRecord] = load_registry(root, staged=args.staged)
    errors = validate_registry(records, root)
    if errors:
        _print_errors(errors)
        return 1

    expected = render_roadmap(records).encode("utf-8")
    actual = _read_roadmap(root, staged=args.staged)
    if actual is None:
        print(
            "docs/ROADMAP.md를 읽을 수 없습니다(검사 대상 위치에 파일을 stage했는지 확인하세요).\n"
            f"수정: {RENDER_COMMAND}",
            file=sys.stderr,
        )
        return 1
    if actual != expected:
        print(_mismatch_message(expected, actual), file=sys.stderr)
        return 1

    digest = roadmap_digest(records)
    picked_up_count = sum(record.status == "Picked Up" for record in records)
    print(f"parsed plans: {len(records)}")
    print(f"Picked Up: {picked_up_count}")
    print(f"roadmap digest: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
