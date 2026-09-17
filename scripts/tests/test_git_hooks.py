from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import install_git_hooks


class GitHookManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        workspace_tmp = Path(__file__).resolve().parents[2] / ".tmp-roadmap-registry-tests"
        workspace_tmp.mkdir(exist_ok=True)
        self.tempdir = tempfile.TemporaryDirectory(dir=workspace_tmp)
        self.root = Path(self.tempdir.name) / "repository"
        self.linked = Path(self.tempdir.name) / "linked"
        self.root.mkdir()
        self._git(self.root, "init", "-q")
        self._git(self.root, "config", "user.email", "tests@example.invalid")
        self._git(self.root, "config", "user.name", "Hook Tests")
        (self.root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-q", "-m", "baseline")
        self._git(self.root, "worktree", "add", "-q", "-b", "linked-test", str(self.linked))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @staticmethod
    def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_install_from_linked_worktree_uses_common_hooks_directory(self) -> None:
        installed, message = install_git_hooks.install(self.linked)

        hook = self.root / ".git" / "hooks" / "pre-commit"
        self.assertTrue(installed, message)
        self.assertTrue(hook.is_file())
        self.assertIn(install_git_hooks.HOOK_MARKER, hook.read_text(encoding="utf-8"))

    def test_disable_graphify_hooks_backs_up_only_recognized_hooks_and_is_idempotent(
        self,
    ) -> None:
        hooks = self.root / ".git" / "hooks"
        graphify = hooks / "post-commit"
        user_hook = hooks / "post-checkout"
        graphify.write_text(
            "#!/bin/sh\n# graphify-hook-start\necho generated\n", encoding="utf-8"
        )
        user_hook.write_text("#!/bin/sh\necho user-owned\n", encoding="utf-8")

        disabled, message = install_git_hooks.disable_graphify_auto_hooks(self.linked)

        backup = hooks / "post-commit.graphify-disabled"
        self.assertTrue(disabled, message)
        self.assertFalse(graphify.exists())
        self.assertEqual(
            backup.read_text(encoding="utf-8"),
            "#!/bin/sh\n# graphify-hook-start\necho generated\n",
        )
        self.assertEqual(
            user_hook.read_text(encoding="utf-8"), "#!/bin/sh\necho user-owned\n"
        )

        disabled_again, second_message = install_git_hooks.disable_graphify_auto_hooks(
            self.linked
        )

        self.assertTrue(disabled_again, second_message)
        self.assertEqual(backup.read_text(encoding="utf-8").count("graphify-hook-start"), 1)


if __name__ == "__main__":
    unittest.main()
