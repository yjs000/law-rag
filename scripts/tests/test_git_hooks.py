from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
            "#!/bin/sh\n# graphify-hook-start\necho generated\n# graphify-hook-end\n",
            encoding="utf-8",
        )
        user_hook.write_text("#!/bin/sh\necho user-owned\n", encoding="utf-8")

        disabled, message = install_git_hooks.disable_graphify_auto_hooks(self.linked)

        backup = hooks / "post-commit.graphify-disabled"
        self.assertTrue(disabled, message)
        self.assertFalse(graphify.exists())
        self.assertEqual(
            backup.read_text(encoding="utf-8"),
            "#!/bin/sh\n# graphify-hook-start\necho generated\n# graphify-hook-end\n",
        )
        self.assertEqual(
            user_hook.read_text(encoding="utf-8"), "#!/bin/sh\necho user-owned\n"
        )

        disabled_again, second_message = install_git_hooks.disable_graphify_auto_hooks(
            self.linked
        )

        self.assertTrue(disabled_again, second_message)
        self.assertEqual(backup.read_text(encoding="utf-8").count("graphify-hook-start"), 1)

    def test_disable_graphify_hooks_refuses_composite_user_hook(self) -> None:
        hooks = self.root / ".git" / "hooks"
        composite = hooks / "post-commit"
        content = (
            "#!/bin/sh\n# graphify-hook-start\necho generated\n"
            "# graphify-hook-end\necho user-owned\n"
        )
        composite.write_text(content, encoding="utf-8")

        disabled, message = install_git_hooks.disable_graphify_auto_hooks(self.linked)

        self.assertFalse(disabled)
        self.assertIn("user-owned or composite", message)
        self.assertEqual(composite.read_text(encoding="utf-8"), content)
        self.assertFalse((hooks / "post-commit.graphify-disabled").exists())

    def test_disable_graphify_hooks_preflights_all_backups_before_mutating(self) -> None:
        hooks = self.root / ".git" / "hooks"
        post_commit = hooks / "post-commit"
        post_checkout = hooks / "post-checkout"
        post_commit.write_text(
            "#!/bin/sh\n# graphify-hook-start\necho commit\n# graphify-hook-end\n",
            encoding="utf-8",
        )
        post_checkout.write_text(
            "#!/bin/sh\n# graphify-checkout-hook-start\necho checkout\n"
            "# graphify-checkout-hook-end\n",
            encoding="utf-8",
        )
        conflict = hooks / "post-checkout.graphify-disabled"
        conflict.write_text("different backup\n", encoding="utf-8")

        disabled, message = install_git_hooks.disable_graphify_auto_hooks(self.linked)

        self.assertFalse(disabled)
        self.assertIn("Refusing to overwrite", message)
        self.assertTrue(post_commit.exists())
        self.assertTrue(post_checkout.exists())
        self.assertFalse((hooks / "post-commit.graphify-disabled").exists())

    def test_disable_graphify_hooks_refuses_symlink_backup(self) -> None:
        hooks = self.root / ".git" / "hooks"
        post_commit = hooks / "post-commit"
        post_commit.write_text(
            "#!/bin/sh\n# graphify-hook-start\necho commit\n# graphify-hook-end\n",
            encoding="utf-8",
        )
        backup = hooks / "post-commit.graphify-disabled"
        backup.write_bytes(post_commit.read_bytes())
        original_is_symlink = Path.is_symlink

        with patch.object(
            Path,
            "is_symlink",
            autospec=True,
            side_effect=lambda path: path == backup or original_is_symlink(path),
        ):
            disabled, message = install_git_hooks.disable_graphify_auto_hooks(self.linked)

        self.assertFalse(disabled)
        self.assertIn("Refusing to overwrite", message)
        self.assertTrue(post_commit.exists())
        self.assertTrue(backup.exists())

    def test_repository_attributes_keep_roadmap_lf_in_new_worktree(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        attributes = (project_root / ".gitattributes").read_bytes()
        (self.root / ".gitattributes").write_bytes(attributes)
        roadmap = self.root / "docs" / "ROADMAP.md"
        roadmap.parent.mkdir()
        roadmap.write_bytes(b"# Roadmap\n\n- item\n")
        self._git(self.root, "config", "core.autocrlf", "true")
        self._git(self.root, "add", ".gitattributes", "docs/ROADMAP.md")
        self._git(self.root, "commit", "-q", "-m", "add roadmap")
        checkout = Path(self.tempdir.name) / "lf-checkout"

        self._git(self.root, "worktree", "add", "-q", "-b", "lf-test", str(checkout))

        checked_out = (checkout / "docs" / "ROADMAP.md").read_bytes()
        self.assertNotIn(b"\r\n", checked_out)
        self.assertEqual(checked_out, b"# Roadmap\n\n- item\n")


if __name__ == "__main__":
    unittest.main()
