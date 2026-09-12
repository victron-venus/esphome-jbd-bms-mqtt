#!/usr/bin/env python3
"""Read-only syntax baseline; this does not prove service/hardware behavior."""
import ast
import json
from pathlib import Path
import shutil
import subprocess

try:
    import yaml
except ImportError:
    raise SystemExit("Install the parser first: python3 -m pip install PyYAML==6.0.3")

root = Path(__file__).resolve().parents[1]
policy = json.loads((root / ".release-policy.json").read_text())
excluded = tuple(policy.get("syntax_exclude", []))
files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
failures, counts = [], {}
for name in sorted(set(files)):
    path = root / name
    if not name or not path.is_file() or path.is_symlink() or any(name == item or name.startswith(item.rstrip("/") + "/") for item in excluded):
        continue
    kind = path.suffix.lower()
    if kind not in {".py", ".json", ".yaml", ".yml", ".sh", ".js", ".mjs", ".cjs"}:
        continue
    try:
        text = path.read_text(encoding="utf-8-sig")
        if kind == ".py":
            ast.parse(text, filename=name)
        elif kind == ".json":
            json.loads(text)
        elif kind in {".yaml", ".yml"}:
            # Preserve !secret/!include/SAM tags; do not resolve includes or
            # construct objects, or contact deployed installations.
            list(yaml.compose_all(text))
        else:
            command = ["bash", "-n", str(path)] if kind == ".sh" else ["node", "--check", str(path)]
            if not shutil.which(command[0]):
                raise ValueError(f"Missing checker: {command[0]}")
            if subprocess.run(command, cwd=root, capture_output=True, text=True).returncode:
                raise ValueError("Syntax check failed")
        counts[kind] = counts.get(kind, 0) + 1
    except (SyntaxError, ValueError, UnicodeError, yaml.YAMLError) as error:
        location = getattr(error, "lineno", None)
        mark = getattr(error, "problem_mark", None)
        if mark:
            location = mark.line + 1
        # Report paths/lines without leaking source configuration values.
        failures.append(f"{name}{':' + str(location) if location else ''}: {type(error).__name__}")
if failures:
    raise SystemExit("Syntax validation failed:\n" + "\n".join(failures))
print("Syntax baseline passed: " + json.dumps(counts, sort_keys=True))
print("Deployment, credentials, firmware behavior and browser playback are outside this check.")

if not shutil.which("actionlint"):
    raise SystemExit("Install actionlint 1.7.12 to validate GitHub workflow semantics")
subprocess.run(["actionlint", "-shellcheck="], cwd=root, check=True)
