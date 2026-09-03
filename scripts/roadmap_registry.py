"""Parse and validate the metadata index at the top of execution plans.

The registry deliberately knows about Markdown only up to the first ``##``
heading.  The rest of a plan is implementation history and is not part of the
roadmap input.  This module has no dependencies outside Python's standard
library so that the renderer, checker, and git hook can share it.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Iterable, Sequence


PLAN_DIRECTORIES = ("todo", "active", "completed")
ALLOWED_STATUSES = ("Todo", "Picked Up", "Blocked", "Done")
ALLOWED_TYPES = (
    "Feature",
    "Bug",
    "Tech Debt",
    "Experiment",
    "Operations",
    "Documentation",
)
ALLOWED_LABELS = (
    "Security",
    "Reliability",
    "Performance",
    "Data",
    "UX",
    "Evaluation",
)
_TYPE_PREFIXES = {
    "Feature": "F",
    "Bug": "B",
    "Tech Debt": "TD",
    "Experiment": "E",
    "Operations": "O",
    "Documentation": "DOC",
}
_TASK_ID_RE = re.compile(r"^(?P<prefix>F|B|TD|E|O|DOC|D)-(?P<number>\d{3,})$")
_PLAN_FILENAME_RE = re.compile(r"^(?P<number>\d+)-[^/\\]+\.md$")
_H2_RE = re.compile(r"^\s*##(?!#)(?:\s|$)")
_H1_RE = re.compile(r"^\s*#(?!#)\s+(.+?)\s*$")
_FIELD_RE = re.compile(
    r"^\s*>\s*(?P<field>작업 ID|상태|유형|보조 라벨|선행 조건|다음 행동|참고 범위)\s*:\s*(?P<value>.*?)\s*$"
)
_REFERENCE_RE = re.compile(
    r"^\s*(?P<path>`[^`]*`|[^\s]+)\s+L(?P<start>\d+)-L(?P<end>\d+)\s*$"
)
_REFERENCE_LINE_RE = re.compile(r"^\s*>\s*-\s*(?P<body>.*?)\s*$")
# Sentence rule for ``다음 행동``: terminal punctuation is one or more of
# ``. ! ? 。 ！ ？`` followed by whitespace or the end of the value.  A value
# without terminal punctuation is allowed as one unpunctuated action; more
# than one punctuation run means that the value contains multiple sentences.
_SENTENCE_TERMINATOR_RE = re.compile(r"[.!?。！？]+(?=\s|$)")
_DEFAULT_CORRECTION = (
    "헤더를 수정한 뒤 python scripts/render_roadmap.py 를 실행하세요"
)


@dataclass(frozen=True, slots=True)
class ReferenceRange:
    """A repository-relative source range cited by an execution plan."""

    path: str
    start_line: int | None
    end_line: int | None
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _strip_code(str(self.path).strip()))
        object.__setattr__(self, "reason", str(self.reason).strip())


@dataclass(frozen=True, slots=True)
class RegistryError:
    """One actionable metadata or lifecycle validation error."""

    record_id: str
    file: str
    field: str
    message: str
    correction: str = _DEFAULT_CORRECTION

    def __str__(self) -> str:
        return (
            f"{self.record_id} {self.file} [{self.field}]: {self.message} "
            f"(수정: {self.correction})"
        )


@dataclass(frozen=True, slots=True)
class PlanRecord:
    """Immutable, render-ready metadata for one execution plan."""

    plan_number: int | None
    task_id: str | None
    status: str | None
    plan_type: str | None
    labels: tuple[str, ...]
    prerequisites: str | None
    next_action: str | None
    references: tuple[ReferenceRange, ...]
    title: str | None
    path: Path
    staged: bool = field(default=False, compare=False, repr=False)
    parse_errors: tuple[RegistryError, ...] = field(
        default_factory=tuple, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "labels", tuple(str(label).strip() for label in self.labels))
        object.__setattr__(self, "references", tuple(self.references))
        object.__setattr__(self, "parse_errors", tuple(self.parse_errors))


@dataclass(frozen=True, slots=True)
class _ParseIssue:
    field: str
    message: str


def _strip_code(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1].strip()
    return value


def _git_output(root: Path, *args: str) -> str | None:
    """Return git output, or ``None`` when root is not a usable repository."""

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _plan_paths(root: Path, staged: bool) -> list[Path]:
    """Find plan paths in deterministic order from disk or the git index."""

    root = root.resolve()
    if staged:
        output = _git_output(
            root,
            "ls-files",
            "--cached",
            "-z",
            "--",
            *(f"docs/exec-plans/{directory}" for directory in PLAN_DIRECTORIES),
        )
        if output is None:
            return []
        paths = [Path(raw) for raw in output.split("\0") if raw]
        paths = [
            path
            for path in paths
            if path.suffix.lower() == ".md" and _is_plan_relative_path(path)
        ]
        return sorted(paths, key=lambda path: path.as_posix())

    paths: list[Path] = []
    for directory in PLAN_DIRECTORIES:
        base = root / "docs" / "exec-plans" / directory
        if not base.is_dir():
            continue
        paths.extend(
            path.relative_to(root)
            for path in base.rglob("*.md")
            if path.is_file()
        )
    return sorted(paths, key=lambda path: path.as_posix())


def _is_plan_relative_path(path: Path) -> bool:
    parts = path.as_posix().split("/")
    return (
        len(parts) >= 4
        and parts[0:2] == ["docs", "exec-plans"]
        and parts[2] in PLAN_DIRECTORIES
        and path.suffix.lower() == ".md"
    )


def _header_lines(lines: Iterable[str]) -> tuple[str, ...]:
    """Read lines through the first exact H2, excluding that heading and body."""

    header: list[str] = []
    for line in lines:
        normalized = line.rstrip("\r\n")
        if _H2_RE.match(normalized):
            break
        header.append(normalized)
    return tuple(header)


def _read_staged_header(root: Path, relative_path: Path) -> tuple[str, ...] | None:
    """Stream one indexed plan header and stop as soon as its first H2 appears."""

    try:
        process = subprocess.Popen(
            ["git", "show", f":{relative_path.as_posix()}"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        return None

    lines: list[str] = []
    stopped_at_h2 = False
    read_failed = False
    stdout = process.stdout
    if stdout is None:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
        return None
    try:
        for line in stdout:
            normalized = line.rstrip("\r\n")
            if _H2_RE.match(normalized):
                stopped_at_h2 = True
                break
            lines.append(normalized)
    except (OSError, UnicodeError):
        read_failed = True
    finally:
        stdout.close()

    if (stopped_at_h2 or read_failed) and process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        returncode = process.wait()
    except OSError:
        return None
    if read_failed or (returncode != 0 and not stopped_at_h2):
        return None
    return tuple(lines)


def _read_plan(
    root: Path, relative_path: Path, staged: bool
) -> tuple[str, ...] | None:
    if staged:
        return _read_staged_header(root, relative_path)
    path = root / relative_path
    try:
        with path.open("r", encoding="utf-8") as stream:
            return _header_lines(stream)
    except (OSError, UnicodeError):
        return None


def _has_index_header(lines: Sequence[str]) -> bool:
    """Return whether the preamble has at least one known metadata field."""

    for line in lines:
        if _H2_RE.match(line):
            break
        if _FIELD_RE.match(line):
            return True
    return False


def _parse_reference(body: str) -> tuple[ReferenceRange, _ParseIssue | None]:
    raw = body.strip()
    reason = ""
    if "—" in raw:
        range_part, reason = raw.split("—", 1)
        reason = reason.strip()
    else:
        range_part = raw
    match = _REFERENCE_RE.match(range_part.strip())
    if match is None:
        path_match = re.match(r"^(?P<path>`[^`]*`|[^\s]+)", range_part.strip())
        path = _strip_code(path_match.group("path")) if path_match else ""
        issue = _ParseIssue(
            "참고 범위",
            f"'{raw}' 형식이 올바르지 않습니다. 경로, L시작-L끝, 이유가 필요합니다",
        )
        return ReferenceRange(path, None, None, reason), issue

    reference = ReferenceRange(
        _strip_code(match.group("path")),
        int(match.group("start")),
        int(match.group("end")),
        reason,
    )
    issue = None
    if not reason:
        issue = _ParseIssue("참고 범위", f"'{raw}'에는 읽는 이유가 없습니다")
    return reference, issue


def _parse_plan(
    relative_path: Path, lines: Sequence[str], staged: bool
) -> PlanRecord:
    """Parse a single plan's index header and retain issues for validation."""

    values: dict[str, str] = {}
    references: list[ReferenceRange] = []
    issues: list[_ParseIssue] = []
    field_positions: dict[str, int] = {}
    in_reference_section = False
    h1_positions: list[tuple[int, str]] = []
    seen_h1 = False

    for index, line in enumerate(lines):
        if not line.strip():
            continue

        title_match = _H1_RE.match(line)
        if title_match is not None:
            h1_positions.append((index, title_match.group(1).strip()))
            seen_h1 = True
            continue

        if seen_h1:
            issues.append(_ParseIssue("색인 헤더", "H1 뒤에는 빈 줄만 허용됩니다"))
            continue

        match = _FIELD_RE.match(line)
        if match is not None:
            field = match.group("field")
            if field in field_positions:
                issues.append(_ParseIssue(field, "필드가 두 번 선언되었습니다"))
            else:
                field_positions[field] = index
                values[field] = match.group("value").strip()
            in_reference_section = field == "참고 범위"
            continue

        reference_match = _REFERENCE_LINE_RE.match(line)
        if reference_match is not None:
            if not in_reference_section:
                issues.append(_ParseIssue("참고 범위", "참고 범위 필드 아래에 있어야 합니다"))
            else:
                reference, issue = _parse_reference(reference_match.group("body"))
                references.append(reference)
                if issue is not None:
                    issues.append(issue)
            continue

        issues.append(_ParseIssue("색인 헤더", "허용되지 않은 색인 헤더 입력입니다"))

    plan_match = _PLAN_FILENAME_RE.match(relative_path.name)
    plan_number = int(plan_match.group("number")) if plan_match else None
    task_id = _strip_code(values.get("작업 ID", "")) or None
    status = _strip_code(values.get("상태", "")) or None
    plan_type = _strip_code(values.get("유형", "")) or None
    labels_value = values.get("보조 라벨", "")
    labels = _parse_labels(labels_value)
    prerequisites = values.get("선행 조건", "").strip() or None
    next_action = values.get("다음 행동", "").strip() or None
    title = h1_positions[0][1] if h1_positions else None
    if not field_positions:
        issues.append(_ParseIssue("색인 헤더", "필수 색인 헤더가 없습니다"))
    if not h1_positions:
        issues.append(_ParseIssue("제목", "색인 헤더 뒤에 정확히 하나의 H1 제목이 필요합니다"))
    elif len(h1_positions) != 1:
        issues.append(
            _ParseIssue(
                "제목",
                f"색인 헤더 뒤의 H1 제목은 하나여야 합니다(현재 {len(h1_positions)}개)",
            )
        )
    if h1_positions and (not field_positions or h1_positions[0][0] <= max(field_positions.values())):
        issues.append(_ParseIssue("제목", "H1 제목은 blockquote 색인 헤더 뒤에 와야 합니다"))

    file_display = relative_path.as_posix()
    record_display_id = task_id or (str(plan_number) if plan_number is not None else "<unknown>")
    parse_errors = tuple(
        RegistryError(record_display_id, file_display, issue.field, issue.message)
        for issue in issues
    )
    return PlanRecord(
        plan_number=plan_number,
        task_id=task_id,
        status=status,
        plan_type=plan_type,
        labels=labels,
        prerequisites=prerequisites,
        next_action=next_action,
        references=tuple(references),
        title=title,
        path=relative_path,
        staged=staged,
        parse_errors=parse_errors,
    )


def _parse_labels(value: str) -> tuple[str, ...]:
    value = value.strip()
    if not value or value in {"없음", "-", "None"}:
        return ()
    return tuple(
        label
        for label in (_strip_code(part.strip()) for part in value.split(","))
        if label
    )


def load_registry(root: str | Path, staged: bool = False) -> list[PlanRecord]:
    """Load parseable plan index headers from the repository.

    Legacy completed plans that do not contain any index field are intentionally
    skipped.  This keeps the registry compatible with the staged migration
    boundary; a completed plan is still parsed as soon as it gains the header.
    """

    root_path = Path(root).resolve()
    records: list[PlanRecord] = []
    for relative_path in _plan_paths(root_path, staged):
        header_lines = _read_plan(root_path, relative_path, staged)
        directory = relative_path.as_posix().split("/")[2]
        if header_lines is None:
            if directory == "completed":
                continue
            header_lines = ()
        if directory == "completed" and not _has_index_header(header_lines):
            continue
        records.append(_parse_plan(relative_path, header_lines, staged))
    return sorted(records, key=_record_sort_key)


def _record_sort_key(record: PlanRecord) -> tuple[bool, int, str, str]:
    return (
        record.plan_number is None,
        record.plan_number if record.plan_number is not None else 0,
        record.task_id or "",
        record.path.as_posix(),
    )


def _display_path(root: Path, path: Path) -> str:
    candidate = path if path.is_absolute() else root / path
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _record_identity(record: PlanRecord, root: Path) -> tuple[str, str]:
    return (
        record.task_id
        or (str(record.plan_number) if record.plan_number is not None else "<unknown>"),
        _display_path(root, record.path),
    )


def _error(
    record: PlanRecord,
    root: Path,
    field_name: str,
    message: str,
    correction: str = _DEFAULT_CORRECTION,
) -> RegistryError:
    record_id, file_display = _record_identity(record, root)
    return RegistryError(record_id, file_display, field_name, message, correction)


def _normal_relative_path(raw_path: str) -> Path | None:
    raw_path = _strip_code(raw_path.strip()).replace("\\", "/")
    if not raw_path or raw_path.startswith(("/", "~")) or "://" in raw_path:
        return None
    windows_path = PureWindowsPath(raw_path)
    if windows_path.is_absolute() or windows_path.drive:
        return None
    path = Path(raw_path)
    if any(part in {"..", ""} for part in path.parts):
        return None
    return path


def _staged_line_count(
    root: Path, reference_path: Path, end_line: int
) -> int | None:
    """Count only as many indexed source lines as the requested range needs."""

    try:
        process = subprocess.Popen(
            ["git", "show", f":{reference_path.as_posix()}"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        return None

    stdout = process.stdout
    if stdout is None:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
        return None

    line_count = 0
    reached_end = False
    read_failed = False
    try:
        for _line in stdout:
            line_count += 1
            if line_count >= end_line:
                reached_end = True
                break
    except (OSError, UnicodeError):
        read_failed = True
    finally:
        stdout.close()

    if reached_end and process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    elif read_failed and process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        returncode = process.wait()
    except OSError:
        return None
    if read_failed or (returncode != 0 and not reached_end):
        return None
    return line_count


def _line_count(root: Path, reference_path: Path, staged: bool, end_line: int) -> int | None:
    if staged:
        return _staged_line_count(root, reference_path, end_line)

    line_count = 0
    try:
        with (root / reference_path).open("r", encoding="utf-8") as source:
            for _line in source:
                line_count += 1
                if line_count >= end_line:
                    break
    except (OSError, UnicodeError):
        return None
    return line_count


def _validate_reference(
    record: PlanRecord,
    reference: ReferenceRange,
    root: Path,
    index: int,
) -> list[RegistryError]:
    errors: list[RegistryError] = []
    field_name = f"참고 범위[{index}]"
    relative_path = _normal_relative_path(reference.path)
    if relative_path is None:
        errors.append(
            _error(
                record,
                root,
                field_name,
                f"참조 경로 '{reference.path}'는 저장소 상대 경로여야 합니다",
            )
        )
        return errors

    if reference.start_line is None or reference.end_line is None:
        errors.append(
            _error(record, root, field_name, "참조 범위는 L시작-L끝 형식이어야 합니다")
        )
        return errors
    if reference.start_line < 1:
        errors.append(
            _error(record, root, field_name, f"시작 줄 L{reference.start_line}은 1 이상이어야 합니다")
        )
    if reference.end_line < reference.start_line:
        errors.append(
            _error(
                record,
                root,
                field_name,
                f"끝 줄 L{reference.end_line}은 시작 줄 L{reference.start_line} 이상이어야 합니다",
            )
        )
    line_count = _line_count(root, relative_path, record.staged, reference.end_line)
    if line_count is None:
        errors.append(
            _error(
                record,
                root,
                field_name,
                f"참조 파일 '{relative_path.as_posix()}'이 존재하지 않습니다",
            )
        )
        return errors
    if reference.end_line > line_count:
        errors.append(
            _error(
                record,
                root,
                field_name,
                f"끝 줄 L{reference.end_line}이 파일의 마지막 줄 L{line_count}을 넘습니다",
            )
        )
    if not reference.reason:
        errors.append(_error(record, root, field_name, "참조 범위를 읽는 이유가 필요합니다"))
    return errors


def validate_registry(
    records: Iterable[PlanRecord], root: str | Path
) -> list[RegistryError]:
    """Validate metadata, lifecycle, references, and registry-wide invariants."""

    root_path = Path(root).resolve()
    records_list = list(records)
    errors: list[RegistryError] = []
    seen_ids: dict[str, PlanRecord] = {}

    for record in records_list:
        errors.extend(record.parse_errors)
        path = record.path
        relative_path: Path | None
        candidate = path if path.is_absolute() else root_path / path
        try:
            relative_path = candidate.resolve().relative_to(root_path)
        except ValueError:
            relative_path = None

        if relative_path is None or not _is_plan_relative_path(relative_path):
            errors.append(
                _error(
                    record,
                    root_path,
                    "경로",
                    "계획 파일은 docs/exec-plans/{todo,active,completed} 아래의 Markdown이어야 합니다",
                    "계획 파일을 허용 lifecycle 디렉터리로 이동하세요",
                )
            )
        else:
            directory = relative_path.as_posix().split("/")[2]
            expected_statuses = {
                "todo": ("Todo",),
                "active": ("Todo", "Picked Up", "Blocked"),
                "completed": ("Done",),
            }[directory]
            if record.status not in expected_statuses:
                errors.append(
                    _error(
                        record,
                        root_path,
                        "상태",
                        f"{directory}/ 위치에서는 상태 {expected_statuses}만 허용됩니다(lifecycle 위반)",
                        f"상태에 맞는 docs/exec-plans/{directory}/ 위치로 파일을 이동하세요",
                    )
                )

        if record.plan_number is None:
            errors.append(
                _error(
                    record,
                    root_path,
                    "파일명",
                    "파일명은 숫자 계획 ID와 설명을 가진 NNNN-name.md 형식이어야 합니다",
                )
            )

        if not record.task_id:
            errors.append(_error(record, root_path, "작업 ID", "필수 작업 ID가 없습니다"))
        else:
            if not _TASK_ID_RE.fullmatch(record.task_id):
                errors.append(
                    _error(
                        record,
                        root_path,
                        "작업 ID",
                        f"작업 ID '{record.task_id}' 형식이 올바르지 않습니다",
                    )
                )
            elif record.task_id in seen_ids:
                errors.append(
                    _error(
                        record,
                        root_path,
                        "작업 ID",
                        f"작업 ID '{record.task_id}'가 다른 계획과 중복됩니다",
                    )
                )
            else:
                seen_ids[record.task_id] = record

        if not record.status:
            errors.append(_error(record, root_path, "상태", "필수 상태가 없습니다"))
        elif record.status not in ALLOWED_STATUSES:
            errors.append(
                _error(
                    record,
                    root_path,
                    "상태",
                    f"알 수 없는 상태 '{record.status}'; 허용값은 {', '.join(ALLOWED_STATUSES)}입니다",
                )
            )

        if not record.plan_type:
            errors.append(_error(record, root_path, "유형", "필수 유형이 없습니다"))
        elif record.plan_type not in ALLOWED_TYPES:
            errors.append(
                _error(
                    record,
                    root_path,
                    "유형",
                    f"알 수 없는 유형 '{record.plan_type}'; 허용값은 {', '.join(ALLOWED_TYPES)}입니다",
                )
            )
        elif record.task_id and _TASK_ID_RE.fullmatch(record.task_id):
            prefix = _TASK_ID_RE.fullmatch(record.task_id).group("prefix")
            expected_prefix = _TYPE_PREFIXES[record.plan_type]
            if prefix not in {expected_prefix, "D"}:
                errors.append(
                    _error(
                        record,
                        root_path,
                        "작업 ID",
                        f"유형 '{record.plan_type}'은 작업 ID 접두사 '{expected_prefix}'를 사용해야 합니다",
                    )
                )

        for label in record.labels:
            if label not in ALLOWED_LABELS:
                errors.append(
                    _error(
                        record,
                        root_path,
                        "보조 라벨",
                        f"알 수 없는 보조 라벨 '{label}'; 허용값은 {', '.join(ALLOWED_LABELS)}입니다",
                    )
                )

        if not record.prerequisites:
            errors.append(_error(record, root_path, "선행 조건", "필수 선행 조건이 없습니다"))

        if not record.next_action:
            errors.append(_error(record, root_path, "다음 행동", "필수 다음 행동이 없습니다"))
        elif len(record.next_action) > 120:
            errors.append(
                _error(
                    record,
                    root_path,
                    "다음 행동",
                    f"다음 행동은 120자 이하여야 합니다(현재 {len(record.next_action)}자)",
                )
            )
        elif len(_SENTENCE_TERMINATOR_RE.findall(record.next_action)) > 1:
            errors.append(
                _error(
                    record,
                    root_path,
                    "다음 행동",
                    "다음 행동은 한 문장이어야 합니다(종결 부호 . ! ? 。 ！ ？ 뒤의 공백 또는 끝을 기준으로 한 문장만 허용하며, 부호 없는 단일 행동은 허용됩니다)",
                )
            )

        if not record.references:
            errors.append(_error(record, root_path, "참고 범위", "최소 하나의 참고 범위가 필요합니다"))
        elif len(record.references) > 3:
            errors.append(
                _error(
                    record,
                    root_path,
                    "참고 범위",
                    f"참고 범위는 최대 3개입니다(현재 {len(record.references)}개)",
                )
            )
        for index, reference in enumerate(record.references, start=1):
            errors.extend(_validate_reference(record, reference, root_path, index))

    picked_up = [record for record in records_list if record.status == "Picked Up"]
    if len(picked_up) > 1:
        errors.append(
            _error(
                picked_up[0],
                root_path,
                "상태",
                f"저장소 전체의 Picked Up은 0개 또는 1개여야 합니다(현재 {len(picked_up)}개)",
                "한 계획만 Picked Up으로 두고 나머지는 Todo 또는 Blocked로 바꾸세요",
            )
        )

    return errors


def _canonical_reference(reference: ReferenceRange) -> dict[str, object]:
    return {
        "path": _strip_code(reference.path).replace("\\", "/"),
        "start_line": reference.start_line,
        "end_line": reference.end_line,
        "reason": reference.reason,
    }


def _canonical_record(record: PlanRecord) -> dict[str, object]:
    references = [_canonical_reference(reference) for reference in record.references]
    references.sort(
        key=lambda item: (
            str(item["path"]),
            item["start_line"] if item["start_line"] is not None else -1,
            item["end_line"] if item["end_line"] is not None else -1,
            str(item["reason"]),
        )
    )
    return {
        "path": record.path.as_posix(),
        "plan_number": record.plan_number,
        "task_id": record.task_id,
        "status": record.status,
        "type": record.plan_type,
        "labels": sorted(record.labels),
        "prerequisites": record.prerequisites,
        "next_action": record.next_action,
        "references": references,
        "title": record.title,
    }


def roadmap_digest(records: Iterable[PlanRecord]) -> str:
    """Hash a canonical serialization of all input index headers."""

    canonical = [_canonical_record(record) for record in records]
    canonical.sort(
        key=lambda item: (
            item["path"],
            item["plan_number"] if item["plan_number"] is not None else -1,
            item["task_id"] or "",
        )
    )
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def roadmap_sections(records: Iterable[PlanRecord]) -> dict[str, list[PlanRecord]]:
    """Group records for rendering, with Picked Up discoverable under Todo."""

    sections: dict[str, list[PlanRecord]] = {
        "Todo": [],
        "Blocked": [],
        "Done": [],
    }
    for record in sorted(records, key=_record_sort_key):
        if record.status in {"Todo", "Picked Up"}:
            sections["Todo"].append(record)
        elif record.status in {"Blocked", "Done"}:
            sections[record.status].append(record)
    return sections


__all__ = [
    "ALLOWED_LABELS",
    "ALLOWED_STATUSES",
    "ALLOWED_TYPES",
    "PLAN_DIRECTORIES",
    "PlanRecord",
    "ReferenceRange",
    "RegistryError",
    "load_registry",
    "roadmap_digest",
    "roadmap_sections",
    "validate_registry",
]
