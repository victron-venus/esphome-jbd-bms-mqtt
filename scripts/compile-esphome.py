#!/usr/bin/env python3
"""Compile selected firmware in a disposable copy with dummy credentials."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import yaml

root = Path(__file__).resolve().parents[1]
policy = json.loads((root / ".release-policy.json").read_text())
selected = sys.argv[1:] or policy["esphome_configs"]
if any(name not in policy["esphome_configs"] for name in selected):
    raise SystemExit("Choose a config from .release-policy.json esphome_configs")
if not shutil.which("esphome"):
    raise SystemExit("Install the pinned ESPHome version from .release-policy.json")
with tempfile.TemporaryDirectory(prefix="esphome-ci-") as temporary:
    stage = Path(temporary)
    if (root / "patterns").is_dir():
        shutil.copytree(root / "patterns", stage / "patterns", ignore=shutil.ignore_patterns(".esphome", "secrets.yaml"))
        for example in stage.glob("patterns/*/secrets.example.yaml"):
            data = yaml.safe_load(example.read_text()) or {}
            for key in data:
                if "ssid" in key:
                    data[key] = "ci-validation"
                elif "bindkey" in key:
                    data[key] = "0123456789abcdef0123456789abcdef"
                elif "mac" in key:
                    data[key] = "AA:BB:CC:DD:EE:FF"
                elif "host" in key:
                    data[key] = "localhost"
                elif "port" in key:
                    data[key] = "1883"
                elif "pass" in key:
                    data[key] = "ci-validation-password"
                elif "user" in key:
                    data[key] = "ci-validation-user"
            example.with_name("secrets.yaml").write_text(yaml.safe_dump(data))
    else:
        for name in selected:
            shutil.copyfile(root / name, stage / name)
        (stage / "secrets.yaml").write_text("wifi_ssid: ci-validation\nwifi_pass: ci-validation-password\n")
    for name in selected:
        subprocess.run(["esphome", "config", str(stage / name)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["esphome", "compile", str(stage / name)], check=True)
print("Firmware compiled without flashing; runtime behavior needs physical hardware.")
