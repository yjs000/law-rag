"""Install the repository's scoped roadmap pre-commit hook."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_NAME = "pre-commit"
HOOK_MARKER = "# law-rag scoped roadmap pre-commit hook"
HOOK_TEXT = f"""#!/bin/sh
{HOOK_MARKER}
# Keep unrelated hooks in .git/hooks untouched and run the roadmap checker only
# when the staged index contains a plan or the generated roadmap.
set -eu

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

staged_paths=$(git -c core.quotePath=false diff --cached --name-only --diff-filter=ACMR) || {{
    status=$?
    echo "Unable to inspect staged paths; refusing to commit." >&2
    exit "$status"
}}

if printf '%s\\n' "$staged_paths" | grep -Eq '^(docs/exec-plans/|docs/ROADMAP\\.md$)'; then
    exec python scripts/check_roadmap.py --staged
fi

exit 0
"""


def _git_output(cwd: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, UnicodeError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def discover_repo_root(start: str | Path | None = None) -> Path | None:
    """Resolve the Git repository containing ``start`` (or the cwd)."""

    start_path = Path(start) if start is not None else Path.cwd()
    try:
        start_path = start_path.resolve()
    except OSError:
        return None
    output = _git_output(start_path, "rev-parse", "--show-toplevel")
    if output is None:
        return None
    try:
        return Path(output).resolve()
    except OSError:
        return None


def _git_dir(repo_root: Path) -> Path | None:
    output = _git_output(repo_root, "rev-parse", "--git-dir")
    if output is None:
        return None
    git_dir = Path(output)
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    try:
        return git_dir.resolve()
    except OSError:
        return None


def _is_managed_hook(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return HOOK_MARKER in path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False


def _write_hook(path: Path) -> None:
    path.write_text(HOOK_TEXT, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def install(repo_root: str | Path) -> tuple[bool, str]:
    """Install the managed hook and return ``(installed, message)``."""

    root = Path(repo_root).resolve()
    git_dir = _git_dir(root)
    if git_dir is None:
        return False, f"Git repository metadata was not found under {root}"

    hooks_dir = git_dir / "hooks"
    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Unable to create the Git hooks directory {hooks_dir}: {exc}"

    hook_path = hooks_dir / HOOK_NAME
    if hook_path.exists() or hook_path.is_symlink():
        if _is_managed_hook(hook_path):
            try:
                hook_path.chmod(0o755)
            except OSError as exc:
                return False, f"Unable to make {hook_path} executable: {exc}"
            return True, f"Roadmap pre-commit hook already installed at {hook_path}"
        return (
            False,
            "Refusing to overwrite the existing user-owned "
            f"{hook_path}. Install the roadmap check manually or merge it into that hook.",
        )

    try:
        _write_hook(hook_path)
    except OSError as exc:
        return False, f"Unable to install the roadmap pre-commit hook at {hook_path}: {exc}"
    return True, f"Installed scoped roadmap pre-commit hook at {hook_path}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Repository root to modify; defaults to the Git repository containing the cwd.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Install the generated dispatcher without changing Git configuration."""

    args = _parser().parse_args(argv)
    repo_root = discover_repo_root(args.repo_root)
    if repo_root is None:
        start = args.repo_root or Path.cwd()
        print(f"Unable to locate a Git repository from {start}", file=sys.stderr)
        return 1

    installed, message = install(repo_root)
    stream = sys.stdout if installed else sys.stderr
    print(message, file=stream)
    return 0 if installed else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["HOOK_MARKER", "HOOK_TEXT", "discover_repo_root", "install", "main"]
