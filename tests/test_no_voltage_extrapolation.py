"""JBDESP-1/2: static guards on shipped ESPHome YAML (no firmware compile).

ESPHome template sensor lambdas: returning {} means "do not publish a new
state" (prior state remains). NAN marks invalid/unknown so has_state/stale
consumers do not keep a previous complete total. See ESPHome template sensor
and sensor component docs (NAN for invalid/unknown).
"""

from __future__ import annotations

import re
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


def test_no_series_voltage_extrapolation():
    for path in YAMLS:
        text = path.read_text()
        assert "(total / count) * 4" not in text, path.name


def test_incomplete_voltage_total_publishes_nan_not_empty_optional():
    """Prior-complete then partial must invalidate via NAN, not return {}."""
    found = 0
    for path in YAMLS:
        lambdas = _voltage_total_lambdas(path.read_text())
        assert lambdas, f"no voltage_total lambdas in {path.name}"
        for name, body in lambdas:
            found += 1
            assert "count == 4" in body, f"{path.name}:{name}"
            assert "(total / count) * 4" not in body, f"{path.name}:{name}"
            # After the complete-path return, incomplete must use NAN.
            after_complete = body.split("if (count == 4) return total;", 1)[1]
            assert "return NAN;" in after_complete, f"{path.name}:{name} missing NAN"
            assert "return {};" not in after_complete, (
                f"{path.name}:{name} still uses return {{}} which retains stale totals"
            )
    assert found == 4, f"expected 4 voltage_total lambdas, found {found}"


def test_ble_busy_skip_does_not_clear_lock():
    text = (ROOT / "jbd-all-batteries.yaml").read_text()
    assert 'ESP_LOGW("cycle", "BLE busy, skipping this cycle");' in text
    idx = text.index('ESP_LOGW("cycle", "BLE busy, skipping this cycle");')
    window = text[idx : idx + 120]
    assert "id(ble_busy) = false;" not in window
