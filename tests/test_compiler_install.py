"""Fail closed before pip on hosts excluded from the compiler support policy."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "compiler_install", Path(__file__).parents[1] / "scripts/install-esphome.py"
)
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class CompilerInstallTests(unittest.TestCase):
    def test_unsupported_hosts_never_invoke_pip(self):
        for host, implementation, version in (
            ("darwin", "CPython", (3, 12)),
            ("win32", "CPython", (3, 12)),
            ("linux", "PyPy", (3, 12)),
            ("linux", "CPython", (3, 11)),
            ("linux", "CPython", (3, 13)),
        ):
            with (
                self.subTest(host=host, implementation=implementation, version=version),
                patch.object(INSTALLER.sys, "platform", host),
                patch.object(INSTALLER.sys, "version_info", version),
                patch.object(INSTALLER.platform, "python_implementation", return_value=implementation),
                patch.object(INSTALLER.subprocess, "run") as run,
            ):
                with self.assertRaises(SystemExit):
                    INSTALLER.main()
                run.assert_not_called()

    def test_failed_hash_install_stops_before_runtime_install(self):
        with (
            patch.object(INSTALLER.sys, "platform", "linux"),
            patch.object(INSTALLER.sys, "version_info", (3, 12)),
            patch.object(INSTALLER.platform, "python_implementation", return_value="CPython"),
            patch.object(INSTALLER.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")) as run,
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                INSTALLER.main()
            self.assertEqual(run.call_count, 1)
            self.assertTrue(run.call_args.kwargs["check"])
            self.assertIn("--require-hashes", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
