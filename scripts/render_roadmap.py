"""Render the generated roadmap from execution-plan index metadata."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.roadmap_registry import (  # noqa: E402
    PlanRecord,
    load_registry,
    roadmap_digest,
    roadmap_sections,
    validate_registry,
)


ROOT = Path(__file__).resolve().parents[1]
ROADMAP_RELATIVE_PATH = Path("docs/ROADMAP.md")
RENDER_COMMAND = "python scripts/render_roadmap.py"
_DONE_LIMIT = 12
_COMPLETED_INDEX_LINK = "exec-plans/completed/README.md"


def _roadmap_link(record: PlanRecord) -> str:
    path = record.path.as_posix()
    if path.startswith("docs/"):
        path = path.removeprefix("docs/")
    return path


def _record_row(record: PlanRecord) -> str:
    task_id = record.task_id or "<작업 ID 없음>"
    plan_type = record.plan_type or "<유형 없음>"
    title = record.title or "<제목 없음>"
    action = record.next_action or "<다음 행동 없음>"
    label = "재개 조건" if record.status == "Blocked" else "다음 행동"
    return (
        f"- [{task_id} · {plan_type} — {title}]"
        f"({_roadmap_link(record)}) — {label}: {action}"
    )


def render_roadmap(records: Iterable[PlanRecord]) -> str:
    """Return deterministic Markdown for the supplied registry records."""

    records_list = list(records)
    digest = roadmap_digest(records_list)
    sections = roadmap_sections(records_list)
    lines = [
        f"<!-- 생성 명령: {RENDER_COMMAND}; 입력 메타데이터 digest: {digest} -->",
        "",
        "# 프로젝트 로드맵",
        "",
        "공통 프로젝트의 현재 작업 진입점입니다. 상세 범위·결정·검증은 연결된 실행계획이 권위 문서이며,",
        "실행계획 작성 전인 승인 설계는 연결된 설계 문서를 따릅니다.",
        "",
    ]

    for section_name in ("Todo", "Blocked", "Done"):
        lines.extend((f"## {section_name}", ""))
        section_records: Sequence[PlanRecord] = sections[section_name]
        if section_name == "Done":
            section_records = section_records[-_DONE_LIMIT:]
        lines.extend(_record_row(record) for record in section_records)
        if section_name == "Done":
            lines.append(f"- [완료 계획 색인]({_COMPLETED_INDEX_LINK})")
        lines.append("")

    return "\n".join(lines)


def _atomic_replace(path: Path, content: str) -> None:
    """Replace ``path`` atomically using a temporary file in its directory."""

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content.encode("utf-8"))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _print_validation_errors(errors: Sequence[object]) -> None:
    for error in errors:
        print(str(error), file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the registry and atomically regenerate ``docs/ROADMAP.md``."""

    args = _parser().parse_args(argv)
    root = args.repo_root.resolve()
    records = load_registry(root)
    errors = validate_registry(records, root)
    if errors:
        _print_validation_errors(errors)
        return 1

    digest = roadmap_digest(records)
    roadmap_path = root / ROADMAP_RELATIVE_PATH
    try:
        _atomic_replace(roadmap_path, render_roadmap(records))
    except OSError as exc:
        print(f"{roadmap_path}: 생성물 교체에 실패했습니다: {exc}", file=sys.stderr)
        return 1

    picked_up_count = sum(record.status == "Picked Up" for record in records)
    print(f"parsed plans: {len(records)}")
    print(f"Picked Up: {picked_up_count}")
    print(f"roadmap digest: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RENDER_COMMAND", "render_roadmap", "main"]
