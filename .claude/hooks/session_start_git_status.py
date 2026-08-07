#!/usr/bin/env python
"""SessionStart hook: summarize `git status --short --branch` into model context.

AGENTS.md step 1 asks every session to start with `git status --short --branch`
before reading docs. This automates that check so it always runs.
"""
import json
import subprocess
import sys


def main() -> None:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:  # pragma: no cover - defensive only
        print(json.dumps({"systemMessage": f"git status hook failed to run: {exc}"}))
        return

    output = (result.stdout or "").strip()
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        print(json.dumps({"systemMessage": f"git status failed: {stderr or 'unknown error'}"}))
        return

    lines = output.splitlines()
    branch_line = lines[0] if lines else "(unknown branch)"
    changes = lines[1:]
    summary = f"{len(changes)}개 변경" if changes else "clean"

    context = "git status --short --branch:\n" + (output or "(no output)")

    payload = {
        "systemMessage": f"세션 시작 · {branch_line.lstrip('#').strip()} · {summary}",
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    sys.exit(main())
