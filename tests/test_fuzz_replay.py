"""Replay fixed collector inputs; mutation is reserved for explicit public RCs."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FuzzSeedReplay(unittest.TestCase):
    def test_committed_telemetry_inputs_under_sanitizers(self):
        setup = json.loads((ROOT / ".github/fuzz.json").read_text())["setup"]
        builds = [command for command in setup if "fuzz/battery_telemetry.cpp" in command]
        self.assertEqual(len(builds), 1, "Expected one telemetry fuzz compiler command")
        compiler = shutil.which(builds[0][0])
        self.assertIsNotNone(compiler, "Install the compiler declared by the fuzz manifest")
        seeds = sorted((ROOT / "fuzz/corpus/battery-telemetry").iterdir())
        self.assertGreaterEqual(len(seeds), 4)
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in seeds))
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "replay"
            subprocess.run([
                compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O1",
                "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
                "-DFUZZ_REPLAY_MAIN", "-I", str(ROOT),
                str(ROOT / "fuzz/battery_telemetry.cpp"), "-o", str(binary),
            ], check=True, timeout=60)
            subprocess.run([str(binary), *map(str, seeds)], check=True, timeout=15)
