from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "run_python.ps1"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RUNNER),
            *arguments,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def test_runner_uses_workspace_python_and_source_roots() -> None:
    probe = (
        "import json, os, sys; "
        "print(json.dumps({'python': sys.executable, 'path': os.environ['PYTHONPATH'], "
        "'utf8_mode': sys.flags.utf8_mode}))"
    )

    result = _run("-c", probe)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert Path(payload["python"]).resolve() == (REPO_ROOT / ".venv/Scripts/python.exe").resolve()
    assert payload["utf8_mode"] == 1
    configured_paths = {Path(item).resolve() for item in payload["path"].split(";") if item}
    assert configured_paths.issuperset(
        {
            (REPO_ROOT / "apps/api").resolve(),
            (REPO_ROOT / "apps/collector/src").resolve(),
            (REPO_ROOT / "apps/law-rag-agent/src").resolve(),
            (REPO_ROOT / "apps/law-rag-llamaindex/src").resolve(),
            (REPO_ROOT / "packages/law-rag-core/src").resolve(),
        }
    )


def test_runner_propagates_python_exit_code() -> None:
    result = _run("-c", "import sys; sys.exit(7)")

    assert result.returncode == 7


def test_runner_accepts_python_switches_when_called_directly() -> None:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                f"$ErrorActionPreference='Stop'; & '{RUNNER}' "
                "-m pytest --version -q -p no:cacheprovider"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "pytest" in result.stdout


def test_runner_keeps_ruff_cache_out_of_the_shared_workspace_cache() -> None:
    result = _run("-m", "ruff", "check", str(Path(__file__)))

    assert result.returncode == 0, result.stderr
    assert "All checks passed" in result.stdout
