#!/usr/bin/env python3
"""Read-only syntax baseline; this does not prove service/hardware behavior."""

# This CLI keeps its documented hyphenated filename.
# pylint: disable=invalid-name
import ast
import json
import shutil
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "Install the parser first: python3 -m pip install PyYAML==6.0.3"
    ) from exc

SUFFIXES = {".py", ".json", ".yaml", ".yml", ".sh", ".js", ".mjs", ".cjs"}


def source_paths(root, excluded):
    """Enumerate regular tracked/nonignored files without following symlinks."""
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    )
    for name in sorted(set(raw.decode().split("\0"))):
        path = root / name
        if not name or not path.is_file() or path.is_symlink():
            continue
        if any(
            name == item or name.startswith(item.rstrip("/") + "/") for item in excluded
        ):
            continue
        if path.suffix.lower() in SUFFIXES:
            yield name, path


def validate_file(root, name, path):
    """Parse source/configuration without constructing YAML objects or resolving includes."""
    kind = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if kind == ".py":
        ast.parse(text, filename=name)
    elif kind == ".json":
        json.loads(text)
    elif kind in {".yaml", ".yml"}:
        # Preserve !secret/!include/SAM tags without contacting live installations.
        list(yaml.compose_all(text))
    else:
        command = (
            ["bash", "-n", str(path)]
            if kind == ".sh"
            else ["node", "--check", str(path)]
        )
        if not shutil.which(command[0]):
            raise ValueError(f"Missing checker: {command[0]}")
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        if result.returncode:
            raise ValueError("Syntax check failed")
    return kind


def error_location(name, error):
    """Describe the path and line without leaking source configuration values."""
    location = getattr(error, "lineno", None)
    mark = getattr(error, "problem_mark", None)
    if mark:
        location = mark.line + 1
    suffix = ":" + str(location) if location else ""
    return f"{name}{suffix}: {type(error).__name__}"


def main():
    """Run syntax and workflow semantic checks against the current checkout."""
    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / ".release-policy.json").read_text())
    failures, counts = [], {}
    for name, path in source_paths(root, policy.get("syntax_exclude", [])):
        try:
            kind = validate_file(root, name, path)
            counts[kind] = counts.get(kind, 0) + 1
        except (SyntaxError, ValueError, yaml.YAMLError) as error:
            failures.append(error_location(name, error))
    if failures:
        raise SystemExit("Syntax validation failed:\n" + "\n".join(failures))
    print("Syntax baseline passed: " + json.dumps(counts, sort_keys=True))
    print(
        "Deployment, credentials, firmware behavior and browser playback are outside this check."
    )
    if not shutil.which("actionlint"):
        raise SystemExit(
            "Install actionlint 1.7.12 to validate GitHub workflow semantics"
        )
    subprocess.run(["actionlint", "-shellcheck="], cwd=root, check=True)


if __name__ == "__main__":
    main()
