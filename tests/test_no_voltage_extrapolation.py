"""JBDESP-1/2: static guards on shipped ESPHome YAML (no firmware compile).

ESPHome template sensor lambdas: returning {} means "do not publish a new
state" (prior state remains). NAN marks invalid/unknown so has_state/stale
consumers do not keep a previous complete total. See ESPHome template sensor
and sensor component docs (NAN for invalid/unknown).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YAMLS = [
    ROOT / "jbd-all-batteries.yaml",
    ROOT / "jbd-all-batteries1.yaml",
    ROOT / "jbd-all-batteries2.yaml",
]


def _voltage_total_lambdas(text: str) -> list[tuple[str, str]]:
    """Extract lambda bodies for sensors whose name contains voltage_total."""
    # Match each template sensor block that names voltage_total*
    blocks = re.finditer(
        r'name:\s*"(voltage_total[^"]*)"[\s\S]*?lambda:\s*\|-\s*\n((?:[ \t]+.*\n)+?)(?=\n  - |\ninterval:|\nbinary_sensor:|\nswitch:|\ntext_sensor:|\Z)',
        text,
    )
    out = []
    for m in blocks:
        out.append((m.group(1), m.group(2)))
    return out


class VoltageTotalTests(unittest.TestCase):
    """Keep shipped series-voltage lambdas safe for incomplete observations."""

    def test_no_series_voltage_extrapolation(self):
        """No partial-series average may be extrapolated to four batteries."""
        for path in YAMLS:
            lambdas = _voltage_total_lambdas(path.read_text())
            self.assertTrue(lambdas, f"no voltage_total lambdas in {path.name}")
            for name, body in lambdas:
                with self.subTest(path=path.name, sensor=name):
                    self.assertNotRegex(body, r"/\s*count\b")

    def test_incomplete_voltage_total_publishes_nan_not_empty_optional(self):
        """Prior-complete then partial must invalidate via NAN, not return {}."""
        found = 0
        for path in YAMLS:
            lambdas = _voltage_total_lambdas(path.read_text())
            self.assertTrue(lambdas, f"no voltage_total lambdas in {path.name}")
            for name, body in lambdas:
                found += 1
                with self.subTest(path=path.name, sensor=name):
                    parts = re.split(
                        r"if\s*\(\s*count\s*==\s*4\s*\)\s*return\s+total\s*;",
                        body,
                        maxsplit=1,
                    )
                    self.assertEqual(len(parts), 2, "missing complete-series gate")
                    self.assertRegex(parts[1], r"return\s+NAN\s*;")
                    self.assertNotRegex(parts[1], r"return\s*\{\s*\}\s*;")
        self.assertEqual(found, 4, "expected four voltage_total lambdas")
