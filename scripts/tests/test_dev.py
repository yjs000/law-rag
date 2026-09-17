from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPT = REPO_ROOT / "scripts" / "dev.ps1"


def _write_fake_command(
    path: Path,
    stdout: str,
    stderr: str,
    exit_code: int = 0,
    delay_seconds: int = 0,
    completion_path: Path | None = None,
) -> None:
    if delay_seconds and completion_path:
        escaped_path = str(completion_path).replace("'", "''")
        delay = (
            'powershell -NoProfile -Command "'
            f"Start-Sleep -Seconds {delay_seconds}; "
            f"Set-Content -LiteralPath '{escaped_path}' -Value completed"
            '"\r\n'
        )
        completion = ""
    else:
        delay = (
            f'powershell -NoProfile -Command "Start-Sleep -Seconds {delay_seconds}"\r\n'
            if delay_seconds
            else ""
        )
        completion = f'echo completed> "{completion_path}"\r\n' if completion_path else ""
    path.write_text(
        f"@echo off\r\n{delay}{completion}echo {stdout}\r\necho {stderr} 1>&2\r\n"
        f"exit /b {exit_code}\r\n",
        encoding="utf-8",
    )


def _run_dev(
    tmp_path: Path,
    *,
    api_exit_code: int = 0,
    frontend_delay_seconds: int = 0,
    frontend_completion_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    test_root = tmp_path / "repo"
    scripts_dir = test_root / "scripts"
    commands_dir = tmp_path / "commands"
    scripts_dir.mkdir(parents=True)
    commands_dir.mkdir()
    shutil.copy2(DEV_SCRIPT, scripts_dir / "dev.ps1")
    _write_fake_command(
        commands_dir / "uv.cmd", "api stdout", "api stderr", exit_code=api_exit_code
    )
    _write_fake_command(
        commands_dir / "pnpm.cmd",
        "frontend stdout",
        "frontend stderr",
        delay_seconds=frontend_delay_seconds,
        completion_path=frontend_completion_path,
    )

    env = os.environ.copy()
    env["PATH"] = f"{commands_dir}{os.pathsep}{env['PATH']}"
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts_dir / "dev.ps1"),
        ],
        cwd=test_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result, test_root


def test_dev_runner_streams_and_saves_api_and_frontend_logs(tmp_path: Path) -> None:
    result, test_root = _run_dev(tmp_path)

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "api stdout" in output
    assert "api stderr" in output
    assert "frontend stdout" in output
    assert "frontend stderr" in output
    assert "CLIXML" not in output
    assert "api stdout" in (test_root / "logs" / "api.log").read_text(encoding="utf-8")
    assert "api stderr" in (test_root / "logs" / "api.log").read_text(encoding="utf-8")
    assert "frontend stdout" in (test_root / "logs" / "frontend.log").read_text(
        encoding="utf-8"
    )
    assert "frontend stderr" in (test_root / "logs" / "frontend.log").read_text(
        encoding="utf-8"
    )


def test_dev_runner_fails_when_a_service_exits_unsuccessfully(tmp_path: Path) -> None:
    result, test_root = _run_dev(tmp_path, api_exit_code=7)

    assert result.returncode != 0
    assert "api stderr" in (test_root / "logs" / "api.log").read_text(encoding="utf-8")


def test_dev_runner_stops_the_peer_promptly_after_a_service_failure(tmp_path: Path) -> None:
    frontend_completed = tmp_path / "frontend-completed"
    started_at = time.monotonic()

    result, _ = _run_dev(
        tmp_path,
        api_exit_code=7,
        frontend_delay_seconds=3,
        frontend_completion_path=frontend_completed,
    )

    assert result.returncode != 0
    elapsed = time.monotonic() - started_at
    time.sleep(4)
    assert not frontend_completed.exists()
    assert elapsed < 2
