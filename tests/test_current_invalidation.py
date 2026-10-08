"""Execute shipped current lambdas with synthetic template-sensor publication.

ESPHome's TemplateSensor::update publishes only when the returned optional has
a value. This fixture models that boundary, not sensor filters or hardware.
https://github.com/esphome/esphome/blob/2026.10.0b1/esphome/components/template/sensor/template_sensor.cpp
"""

import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CurrentInvalidationTests(unittest.TestCase):
    """A prior numeric current must become unknown when its voltage is invalid."""

    def test_current_invalidates_and_recovers_for_all_four_aggregates(self):
        """Compile real lambda bodies; exercise optional-value publication behavior."""
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler, "A local C++17 compiler is required")
        found = 0
        for name in (
            "jbd-all-batteries.yaml",
            "jbd-all-batteries1.yaml",
            "jbd-all-batteries2.yaml",
        ):
            text = (ROOT / name).read_text()
            blocks = re.finditer(
                r'name:\s*"(current_total[^"]*)".*?lambda:\s*\|-\n'
                r"((?:      [^\n]*\n)+)",
                text,
                re.DOTALL,
            )
            for block in blocks:
                found += 1
                body = textwrap.dedent(block.group(2))
                ids = set(re.findall(r"id\((\w+)\)", body))
                voltage = [sensor for sensor in ids if "voltage" in sensor]
                power = [sensor for sensor in ids if "power" in sensor]
                self.assertEqual(len(voltage), 1)
                self.assertEqual(len(power), 1)
                self.assertEqual(len(ids), 2)
                with self.subTest(config=name, sensor=block.group(1)):
                    source = f"""
                    #include <cmath>
                    #include <iostream>
                    #include <optional>
                    struct Sensor {{ float state; }};
                    Sensor {voltage[0]}, {power[0]};
                    #define id(value) value
                    std::optional<float> sample() {{ {body} }}
                    float published = NAN;
                    void update() {{
                      auto result = sample();
                      if (result.has_value()) published = *result;
                    }}
                    int main() {{
                      for (float invalid : {{NAN, 0.0f, 10.0f}}) {{
                        {voltage[0]}.state = 208.0f;
                        {power[0]}.state = 416.0f;
                        update();
                        if (published != 2.0f) return 1;
                        {voltage[0]}.state = invalid;
                        update();
                        if (!std::isnan(published)) {{
                          std::cerr << "Invalid voltage retained numeric current";
                          return 2;
                        }}
                        {voltage[0]}.state = 200.0f;
                        {power[0]}.state = 600.0f;
                        update();
                        if (published != 3.0f) return 3;
                      }}
                    }}
                    """
                    with tempfile.TemporaryDirectory(prefix="current-contract-") as tmp:
                        cpp = Path(tmp) / "check.cpp"
                        binary = Path(tmp) / "check"
                        cpp.write_text(textwrap.dedent(source))
                        build = subprocess.run(
                            [compiler, "-std=c++17", str(cpp), "-o", str(binary)],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=False,
                        )
                        self.assertEqual(build.returncode, 0, build.stderr)
                        result = subprocess.run(
                            [str(binary)],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(found, 4, "Expected four shipped current-total lambdas")
