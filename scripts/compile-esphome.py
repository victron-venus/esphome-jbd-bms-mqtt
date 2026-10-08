#!/usr/bin/env python3
"""Compile declared firmware from confined paths with isolated dummy credentials."""

# Preserve the existing operator-facing CLI filename.
# pylint: disable=invalid-name
import base64
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

import yaml

SECRETS = "secrets.yaml"


def confined_config(root, name):
    """Require a regular YAML file within the source tree and reject option-like paths."""
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._/-]*\.ya?ml", name
    ):
        raise ValueError("Config must be a relative YAML path")
    parts = PurePosixPath(name).parts
    if any(part in {".", ".."} or part.startswith("-") for part in parts):
        raise ValueError("Config cannot contain traversal or option components")
    path = root / name
    resolved = path.resolve(strict=True)
    if (
        path.is_symlink()
        or not resolved.is_relative_to(root.resolve())
        or not resolved.is_file()
    ):
        raise ValueError("Config must be a regular file inside the repository")
    return resolved


def selected_configs(root, policy, requested):
    """Resolve only policy-declared paths; CLI values never become command arguments."""
    declared = policy["esphome_configs"]
    if not isinstance(declared, list) or not declared:
        raise ValueError("Declare at least one ESPHome configuration")
    for name in declared:
        confined_config(root, name)
    if requested and any(name not in declared for name in requested):
        raise ValueError("Choose a config from .release-policy.json esphome_configs")
    return [name for name in declared if not requested or name in requested]


def dummy_secret(key, value):
    """Replace known secret kinds with inert values required by firmware validation."""
    replacements = (
        ("ssid", "ci-validation"),
        ("bindkey", "0123456789abcdef0123456789abcdef"),
        ("mac", "AA:BB:CC:DD:EE:FF"),
        ("host", "localhost"),
        ("port", "1883"),
        ("pass", "ci-validation-password"),
        ("user", "ci-validation-user"),
    )
    return next(
        (replacement for token, replacement in replacements if token in key), value
    )


def stage_configs(root, stage, selected):
    """Prepare independent configuration copies while excluding real secrets."""
    if (root / "patterns").is_dir():
        shutil.copytree(
            root / "patterns",
            stage / "patterns",
            ignore=shutil.ignore_patterns(".esphome", SECRETS),
        )
        for example in stage.glob("patterns/*/secrets.example.yaml"):
            data = yaml.safe_load(example.read_text(encoding="utf-8")) or {}
            data = {key: dummy_secret(key, value) for key, value in data.items()}
            example.with_name(SECRETS).write_text(
                yaml.safe_dump(data), encoding="utf-8"
            )
    else:
        shared = "packages/mqtt-availability.yaml"
        (stage / "packages").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(confined_config(root, shared), stage / shared)
        header = root / "components/battery_telemetry.h"
        if (
            header.is_symlink()
            or not header.is_file()
            or not header.resolve().is_relative_to(root.resolve())
        ):
            raise ValueError(
                "Telemetry header must be a regular file inside the repository"
            )
        (stage / "components").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(header, stage / "components/battery_telemetry.h")
        for name in selected:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(confined_config(root, name), target)
        # Generated only inside the temporary build, never an operator default.
        (stage / SECRETS).write_text(
            yaml.safe_dump(
                {
                    "wifi_ssid": "ci-validation",
                    "wifi_pass": secrets.token_urlsafe(24),
                    "fallback_ap_password": secrets.token_urlsafe(24),
                    "api_encryption_key": base64.b64encode(
                        secrets.token_bytes(32)
                    ).decode(),
                }
            ),
            encoding="utf-8",
        )


def verify_encrypted_build(stage):
    """Reject a generated build with plaintext API/OTA or an HTTP recovery route."""
    headers = list((stage / ".esphome/build").glob("*/src/esphome/core/defines.h"))
    if not headers:
        raise ValueError("ESPHome generated no feature definitions")
    required = {"USE_API_NOISE", "USE_OTA_ENCRYPTION", "USE_OTA_ENCRYPTION_REQUIRED"}
    forbidden = {
        "USE_API_PLAINTEXT",
        "USE_OTA_PASSWORD",
        "USE_WEBSERVER",
        "USE_WEBSERVER_OTA",
        "USE_CAPTIVE_PORTAL",
    }
    for header in headers:
        flags = {
            line.split()[1]
            for line in header.read_text().splitlines()
            if line.startswith("#define ") and len(line.split()) >= 2
        }
        if not required <= flags or forbidden & flags:
            raise ValueError(
                "Firmware must require encrypted API/OTA without HTTP access"
            )


def main(arguments=None):
    """Validate selection before invoking ESPHome; compile without flashing hardware."""
    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / ".release-policy.json").read_text(encoding="utf-8"))
    selected = selected_configs(
        root, policy, sys.argv[1:] if arguments is None else arguments
    )
    executable = shutil.which("esphome")
    if not executable:
        raise SystemExit("Install the pinned ESPHome version from .release-policy.json")
    with tempfile.TemporaryDirectory(prefix="esphome-ci-") as temporary:
        stage = Path(temporary)
        stage_configs(root, stage, selected)
        for name in selected:
            config = str(confined_config(stage, name))
            subprocess.run(
                [executable, "config", config], check=True, stdout=subprocess.DEVNULL
            )
            subprocess.run([executable, "compile", config], check=True)
            verify_encrypted_build(stage)
    print(
        "Firmware compiled without flashing; runtime behavior needs physical hardware."
    )


if __name__ == "__main__":
    main()
