"""Replay fixed collector inputs; mutation is reserved for explicit public RCs."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FuzzSeedReplay(unittest.TestCase):
    def test_committed_telemetry_inputs_under_sanitizers(self):
        compiler = shutil.which("clang++")
        self.assertIsNotNone(compiler, "Install clang++ for deterministic seed replay")
        seeds = sorted((ROOT / "fuzz/corpus/battery-telemetry").iterdir())
        self.assertGreaterEqual(len(seeds), 4)
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in seeds))
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "replay"
            subprocess.run([
                compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
                "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-DFUZZ_REPLAY_MAIN", "-I", str(ROOT),
                str(ROOT / "fuzz/battery_telemetry.cpp"), "-o", str(binary),
            ], check=True, timeout=60)
            subprocess.run([str(binary), *map(str, seeds)], check=True, timeout=15)
