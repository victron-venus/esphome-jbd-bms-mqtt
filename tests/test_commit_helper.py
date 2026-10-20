"""Exercise the commit helper without credentials or a network remote."""

import os
import shutil

# Fixed commands in isolated test repositories.
import subprocess  # nosec B404
import tempfile
import unittest
from pathlib import Path


class CommitHelperTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repository with spaces"
        self.repo.mkdir()
        self.script = self.repo / "commit.sh"
        shutil.copyfile(Path(__file__).resolve().parents[1] / "commit.sh", self.script)
        self.message = self.repo / "commit.txt"
        self.message.write_text("Test change\n")
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_ALLOW_PROTOCOL="file",
            GIT_TERMINAL_PROMPT="0",
        )

    def run_helper(self):
        # Local script, no shell interpolation.
        return subprocess.run(  # nosec B603, B607
            ["bash", str(self.script)],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def fake_git(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text(
            "#!/bin/bash\n"
            'printf "%s\\n" "$1" >> "$HELPER_CALLS"\n'
            'if [[ "$1" == "$HELPER_FAIL" ]]; then exit "$HELPER_ERROR"; fi\n'
            'if [[ "$1" == diff ]]; then exit "$HELPER_DIFF"; fi\n'
            "exit 0\n"
        )
        fake.chmod(0o755)
        self.calls = self.root / "calls"
        self.env.update(
            PATH=str(bin_dir) + os.pathsep + self.env["PATH"],
            HELPER_CALLS=str(self.calls),
            HELPER_FAIL="",
            HELPER_ERROR="0",
            HELPER_DIFF="1",
        )

    def test_missing_or_empty_message_stops_before_git(self):
        self.fake_git()
        for message in (None, ""):
            with self.subTest(message=message):
                if message is None:
                    self.message.unlink()
                else:
                    self.message.write_text(message)
                result = self.run_helper()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.calls.exists())
                self.assertNotIn("Done", result.stdout)

    def test_stage_failures_and_no_change_stop_at_the_right_boundary(self):
        self.fake_git()
        cases = [
            ("add", 17, 1, 17, ["add"]),
            ("diff", 2, 1, 2, ["add", "diff"]),
            ("diff", 128, 1, 128, ["add", "diff"]),
            ("commit", 23, 1, 23, ["add", "diff", "commit"]),
            ("push", 31, 1, 31, ["add", "diff", "commit", "push"]),
            ("", 0, 0, 0, ["add", "diff"]),
            ("", 0, 1, 0, ["add", "diff", "commit", "push"]),
        ]
        for failure, error, diff, expected, calls in cases:
            with self.subTest(failure=failure, error=error, diff=diff):
                self.calls.unlink(missing_ok=True)
                self.env.update(HELPER_FAIL=failure, HELPER_ERROR=str(error), HELPER_DIFF=str(diff))
                result = self.run_helper()
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual(self.calls.read_text().splitlines(), calls)
                self.assertEqual("Done" in result.stdout, not failure and diff == 1)
                if not failure and diff == 0:
                    self.assertIn("No changes", result.stdout)

    def test_unborn_commit_no_change_and_later_change_with_local_remote(self):
        git_binary = shutil.which("git")
        self.assertIsNotNone(git_binary)

        def git(*args):
            # Fixed arguments and local-only protocol.
            return subprocess.run(  # nosec B603
                [git_binary, *args],
                cwd=self.repo,
                env=self.env,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

        remote = self.root / "remote.git"
        git("init", "--bare", "--initial-branch=main", str(remote))
        git("init", "--initial-branch=main")
        git("config", "user.name", "Commit helper test")
        git("config", "user.email", "helper@example.invalid")
        git("config", "commit.gpgsign", "false")
        git("config", "push.default", "current")
        git("remote", "add", "origin", str(remote))
        for expected_count in (1, 1, 2):
            if expected_count == 2:
                (self.repo / "payload.txt").write_text("A later change\n")
            before = git("rev-list", "--all", "--count")
            result = self.run_helper()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(git("rev-list", "HEAD", "--count"), str(expected_count))
            self.assertEqual(
                git("rev-parse", "HEAD"), git("--git-dir", str(remote), "rev-parse", "main")
            )
            self.assertEqual("No changes" in result.stdout, before == str(expected_count))
            self.assertEqual("Done" in result.stdout, before != str(expected_count))


if __name__ == "__main__":
    unittest.main()
