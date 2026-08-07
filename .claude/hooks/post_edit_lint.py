#!/usr/bin/env python
"""PostToolUse hook (Write|Edit): run the matching linter for the touched file.

Routes by path prefix to the right sub-project's lint tool:
  apps/api/**.py, apps/collector/**.py, packages/law-rag-core/**.py -> uv run ruff check
  apps/web/**.{ts,tsx,js,jsx}                                        -> pnpm --dir apps/web exec eslint

Non-blocking: lint failures are surfaced back to the model via
additionalContext instead of stopping the tool call, since a mid-refactor
file can legitimately fail lint before a following edit fixes it.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PY_PROJECTS = [
    ("apps/api", {".py"}),
    ("apps/collector", {".py"}),
    ("packages/law-rag-core", {".py"}),
]
WEB_PROJECT = ("apps/web", {".ts", ".tsx", ".js", ".jsx"})


def read_hook_input() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def resolve_file_path(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    return tool_response.get("filePath") or tool_input.get("file_path")


def to_repo_relative(raw_path: str) -> Path | None:
    try:
        p = Path(raw_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return p.resolve().relative_to(REPO_ROOT)
    except (OSError, ValueError):
        return None


def build_command(rel_path: Path) -> tuple[list[str], Path] | None:
    posix = rel_path.as_posix()
    suffix = rel_path.suffix

    for project, suffixes in PY_PROJECTS:
        if posix.startswith(project + "/") and suffix in suffixes:
            project_dir = REPO_ROOT / project
            file_in_project = rel_path.relative_to(project).as_posix()
            return ["uv", "run", "ruff", "check", file_in_project], project_dir

    project, suffixes = WEB_PROJECT
    if posix.startswith(project + "/") and suffix in suffixes:
        file_in_project = rel_path.relative_to(project).as_posix()
        return ["pnpm", "--dir", project, "exec", "eslint", file_in_project], REPO_ROOT

    return None


def main() -> None:
    payload = read_hook_input()
    raw_path = resolve_file_path(payload)
    if not raw_path:
        return

    rel_path = to_repo_relative(raw_path)
    if rel_path is None or not (REPO_ROOT / rel_path).exists():
        return

    dispatch = build_command(rel_path)
    if dispatch is None:
        return
    command, cwd = dispatch

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            shell=(sys.platform == "win32"),
        )
    except Exception as exc:  # pragma: no cover - defensive only
        print(json.dumps({"systemMessage": f"lint hook failed to run ({' '.join(command)}): {exc}"}))
        return

    if result.returncode == 0:
        return

    detail = (result.stdout or "") + (result.stderr or "")
    detail = detail.strip()[:4000]
    payload_out = {
        "systemMessage": f"lint 실패: {rel_path.as_posix()}",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"`{' '.join(command)}` (cwd={cwd}) 실패:\n{detail}",
        },
    }
    print(json.dumps(payload_out))


if __name__ == "__main__":
    sys.exit(main())
