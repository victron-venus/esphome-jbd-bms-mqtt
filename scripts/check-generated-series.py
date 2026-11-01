#!/usr/bin/env python3
"""Validate generated topology variants with temporary dummy credentials only."""

# Preserve the documented operator-facing command name.
# pylint: disable=invalid-name
import argparse
import base64
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ("4", "4,4", "4,4,4", "4,4,4,4", "1", "16", "32", "4,8,16,32", "32,32,32,32")


def main():
    """Run ESPHome config for every variant and optionally compile the largest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile", action="store_true", help="Also compile the maximum four-by-32-cell profile")
    args = parser.parse_args()
    executable = shutil.which("esphome")
    if not executable:
        parser.error("Install the pinned ESPHome compiler from .release-policy.json")
    with tempfile.TemporaryDirectory(prefix="jbd-series-check-") as directory:
        for counts in MATRIX:
            name = "series-" + counts.replace(",", "-")
            project = Path(directory) / name
            subprocess.run([sys.executable, str(ROOT / "scripts/generate-series-config.py"),
                            "--name", name, "--topic-prefix", name, "--cells", counts,
                            "--output", str(project)], check=True, stdout=subprocess.DEVNULL)
            values = yaml.safe_load((project / "secrets.example.yaml").read_text())
            values.update(wifi_ssid="ci-validation", wifi_pass=secrets.token_urlsafe(24),
                          fallback_ap_password=secrets.token_urlsafe(24),
                          api_encryption_key=base64.b64encode(secrets.token_bytes(32)).decode())
            (project / "secrets.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
            config = str(project / "series.yaml")
            subprocess.run([executable, "config", config], check=True, stdout=subprocess.DEVNULL)
            if args.compile and counts == MATRIX[-1]:
                subprocess.run([executable, "compile", config], check=True)
    print("Generated topology matrix validated; no firmware was flashed or broker contacted.")


if __name__ == "__main__":
    main()
