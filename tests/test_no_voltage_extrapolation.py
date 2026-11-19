"""Static guards for measured voltage on the original MQTT state topics.

ESPHome template sensor lambdas: returning {} means "do not publish a new
state" (prior state remains). NAN marks invalid/unknown so has_state/stale
consumers do not keep a previous complete total. See ESPHome template sensor
and sensor component docs (NAN for invalid/unknown).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAMLS = [
    ROOT / "jbd-all-batteries.yaml",
    ROOT / "jbd-all-batteries1.yaml",
    ROOT / "jbd-all-batteries2.yaml",
]


def _mapping_values(node: yaml.Node) -> dict[str, yaml.Node]:
    """Read mapping nodes without resolving ESPHome tags or constructing objects."""
    if not isinstance(node, yaml.MappingNode):
        raise ValueError("expected a YAML mapping")
    values = {}
    for key, value in node.value:
        if not isinstance(key, yaml.ScalarNode) or key.value in values:
            raise ValueError("expected unique scalar YAML keys")
        values[key.value] = value
    return values


def measured_total_lambdas(text: str, metric: str) -> list[tuple[str, str]]:
    """Read measured total lambdas from implicit or explicit state topics."""
    document = yaml.compose(text, Loader=yaml.SafeLoader)
    sensors = _mapping_values(document).get("sensor")
    if not isinstance(sensors, yaml.SequenceNode):
        raise ValueError("expected a sensor sequence")
    out = []
    for sensor in sensors.value:
        fields = _mapping_values(sensor)
        topic = fields.get("state_topic")
        name = fields.get("name")
        if isinstance(topic, yaml.ScalarNode):
            if not topic.value.endswith(f"/sensor/{metric}_total/state"):
                continue
            label = topic.value
        elif isinstance(name, yaml.ScalarNode) and name.value.startswith(f"{metric}_total"):
            label = name.value
        else:
            continue
        body = fields.get("lambda")
        if not isinstance(body, yaml.ScalarNode) or body.tag != "tag:yaml.org,2002:str":
            raise ValueError(f"missing literal lambda for {label}")
        out.append((label, body.value))
    return out


def _voltage_total_lambdas(text: str) -> list[tuple[str, str]]:
    """Read measured voltage lambdas without crossing sensor blocks."""
    return measured_total_lambdas(text, "voltage")


class LambdaExtractionTests(unittest.TestCase):
    """Keep fixture extraction independent of YAML formatting and sensor neighbors."""

    def test_yaml_formatting_and_opaque_esphome_tags(self):
        text = """wifi:
  password: !secret wifi_password
sensor:
  - lambda: |-
      if (count == 4) return total;

      return NAN;
    name: 'voltage_total_one'
  - name: voltage_total_two
    lambda: 'return NAN;'
"""
        expected = [
            ("voltage_total_one", "if (count == 4) return total;\n\nreturn NAN;"),
            ("voltage_total_two", "return NAN;"),
        ]
        for source in (text, text.replace("\n", "\r\n"), text.rstrip("\n")):
            with self.subTest(source=source):
                self.assertEqual(_voltage_total_lambdas(source), expected)

    def test_missing_lambda_cannot_borrow_next_sensor_body(self):
        text = """sensor:
  - name: voltage_total_missing
  - name: unrelated
    lambda: return NAN;
"""
        with self.assertRaisesRegex(ValueError, "missing literal lambda"):
            _voltage_total_lambdas(text)

    def test_duplicate_fields_and_includes_are_rejected(self):
        for fields in (
            "    name: unrelated\n    lambda: return NAN;\n",
            "    lambda: !include another-sensor.yaml\n",
        ):
            source = "sensor:\n  - name: voltage_total_one\n" + fields
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                _voltage_total_lambdas(source)

    def test_long_nonmatching_scalar_does_not_backtrack(self):
        body = "      // harmless line\n" * 10000
        source = "sensor:\n  - name: voltage_total_long\n    lambda: |-\n" + body
        extracted = _voltage_total_lambdas(source)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0][1].count("// harmless line"), 10000)


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
