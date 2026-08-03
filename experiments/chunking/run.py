import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from law_rag_core.parsers.law_json import LawJsonParseError, parse_legal_document

from experiments.chunking.text_fixture_adapter import TextFixtureError, adapt_text_fixture


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPOSITORY_ROOT / "docs" / "generated" / "experiment-a-chunking.md"
PARSER_NAME = "law_rag_core.parsers.law_json.parse_legal_document"


class ExperimentRunError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="일반 텍스트를 기존 Open API JSON 파서로 청킹해 관찰한다"
    )
    parser.add_argument("input", type=Path, help="UTF-8 일반 텍스트 파일")
    parser.add_argument("--title", default="전기사업법", help="조문형 입력의 문서명")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-output", type=Path)
    return parser


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _read_input(path: Path) -> tuple[bytes, str]:
    if not path.exists():
        raise ExperimentRunError("input_not_found", "입력 파일을 찾을 수 없습니다")
    if not path.is_file():
        raise ExperimentRunError("input_not_file", "입력 경로가 파일이 아닙니다")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ExperimentRunError("input_read_failed", "입력 파일을 읽을 수 없습니다") from exc
    try:
        return raw, raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExperimentRunError("invalid_utf8", "입력 파일이 UTF-8이 아닙니다") from exc


def _chunk_payload(provision: Any) -> dict[str, Any]:
    return {
        "id": str(provision.id),
        "ordinal": provision.ordinal,
        "path": provision.path,
        "heading": provision.heading,
        "parent_path": provision.parent_path,
        "content": provision.content,
    }


def _render_report(result: dict[str, Any], command: str) -> str:
    context = result["input_context"]
    lines = [
        "# 실험 A — 기존 법령 파서 청킹 결과",
        "",
        f"> 생성 명령: `{command}`",
        f"> 기준 시점: `{result['generated_at']}`",
        f"> 입력: `{result['input_path']}`",
        f"> 입력 SHA-256: `{result['input_sha256']}`",
        f"> 실제 청킹 함수: `{result['parser']['function']}`",
        f"> Parser schema version: `{result['parser']['schema_version']}`",
        "",
        "이 문서는 사용자 제공 텍스트로 수행한 로컬 실험 결과이며 운영 법률 코퍼스나 답변 근거가 아니다.",
        "텍스트 어댑터는 최소 Open API JSON 구조만 만들고, 아래 청크는 현재 운영 파서의 반환값이다.",
        "",
        "## 입력 개요",
        "",
        f"- 형식: `{result['mode']}`",
        f"- 장: {context['chapter'] or '없음'}",
        f"- 절: {context['section'] or '없음'}",
        f"- 제거한 UI 줄: {result['removed_ui_lines']}개",
        "",
        "## 결과 요약",
        "",
        f"- 상태: `{result['status']}`",
        f"- 청크 수: {result['chunk_count']}개",
        f"- 기존 파서 입력 SHA-256: `{result['parser']['raw_sha256']}`",
        "",
        "## 청크",
        "",
    ]
    for index, chunk in enumerate(result["chunks"], 1):
        heading = f" — {chunk['heading']}" if chunk["heading"] else ""
        lines.extend(
            [
                f"### {index}. {chunk['path']}{heading}",
                "",
                f"- ID: `{chunk['id']}`",
                f"- ordinal: `{chunk['ordinal']}`",
                f"- parent_path: `{chunk['parent_path']}`",
                "",
                "```text",
                chunk["content"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _render_terminal(result: dict[str, Any], report: Path, json_output: Path) -> str:
    lines = [
        f"입력: {result['input_path']}",
        f"SHA-256: {result['input_sha256']}",
        (
            f"청크: {result['chunk_count']}개 | 제거한 UI 줄: "
            f"{result['removed_ui_lines']}개 | 상태: {result['status']}"
        ),
        f"보고서: {_display_path(report)}",
        f"JSON: {_display_path(json_output)}",
        "",
    ]
    count = result["chunk_count"]
    for index, chunk in enumerate(result["chunks"], 1):
        heading = f" — {chunk['heading']}" if chunk["heading"] else ""
        lines.extend(
            [
                f"[{index}/{count}] {chunk['path']}{heading}",
                "본문:",
                chunk["content"],
                "",
            ]
        )
    return "\n".join(lines)


def _stage_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        with suppress(OSError):
            temporary.unlink()
        raise
    return temporary


def _restore(path: Path, previous: bytes | None) -> None:
    if previous is None:
        with suppress(FileNotFoundError):
            path.unlink()
        return
    temporary = _stage_text(path, previous.decode("utf-8"))
    os.replace(temporary, path)


def _write_outputs(outputs: list[tuple[Path, str]]) -> None:
    resolved = [path.resolve() for path, _ in outputs]
    if len(set(resolved)) != len(resolved):
        raise ExperimentRunError("duplicate_output_path", "보고서와 JSON 경로는 달라야 합니다")
    previous = {path: path.read_bytes() if path.exists() else None for path, _ in outputs}
    staged: list[tuple[Path, Path]] = []
    replaced: list[Path] = []
    try:
        staged = [(path, _stage_text(path, content)) for path, content in outputs]
        for target, temporary in staged:
            os.replace(temporary, target)
            replaced.append(target)
    except (OSError, UnicodeError) as exc:
        for _, temporary in staged:
            with suppress(FileNotFoundError):
                temporary.unlink()
        for target in reversed(replaced):
            with suppress(OSError, UnicodeError):
                _restore(target, previous[target])
        raise ExperimentRunError("output_write_failed", "결과 파일을 저장할 수 없습니다") from exc


def run_experiment(
    input_path: Path,
    *,
    title: str,
    report_path: Path,
    json_output_path: Path,
) -> tuple[dict[str, Any], str]:
    raw, text = _read_input(input_path)
    input_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        adapted = adapt_text_fixture(
            text,
            document_title=title,
            input_sha256=input_sha256,
        )
        document = parse_legal_document(
            adapted.payload,
            expected_title=adapted.expected_title,
            source_kind=adapted.source_kind,
            source_url=f"local-experiment:{_display_path(input_path)}",
        )
    except TextFixtureError as exc:
        raise ExperimentRunError(exc.code, str(exc)) from exc
    except LawJsonParseError as exc:
        raise ExperimentRunError("current_parser_failed", str(exc)) from exc

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    result: dict[str, Any] = {
        "status": "success",
        "generated_at": generated_at,
        "input_path": _display_path(input_path),
        "input_sha256": input_sha256,
        "mode": adapted.mode,
        "input_context": {"chapter": adapted.chapter, "section": adapted.section},
        "removed_ui_lines": adapted.removed_ui_lines,
        "chunk_count": len(document.provisions),
        "parser": {
            "function": PARSER_NAME,
            "schema_version": document.parser_schema_version,
            "raw_sha256": document.raw_sha256,
        },
        "chunks": [_chunk_payload(item) for item in document.provisions],
    }
    command = (
        "uv run --project packages/law-rag-core python -m experiments.chunking.run "
        f"{result['input_path']}"
    )
    report = _render_report(result, command)
    json_result = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    _write_outputs([(report_path, report), (json_output_path, json_result)])
    return result, _render_terminal(result, report_path, json_output_path)


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    input_path = args.input.resolve()
    report_path = args.report.resolve()
    json_output_path = (
        args.json_output.resolve()
        if args.json_output
        else (
            REPOSITORY_ROOT
            / ".data"
            / "experiments"
            / "chunking"
            / f"{input_path.stem}.chunks.json"
        )
    )
    try:
        _, terminal = run_experiment(
            input_path,
            title=args.title,
            report_path=report_path,
            json_output_path=json_output_path,
        )
    except ExperimentRunError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": exc.code,
                    "input": _display_path(input_path),
                    "message": str(exc),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(terminal)
    return 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
