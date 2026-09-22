#!/usr/bin/env python3
# Vendored release toolkit; change the toolkit source, then render again.
# ruff: noqa
# mypy: ignore-errors
# pylint: skip-file
# fmt: off
"""Check the CI entry point and CodeQL compatibility before expensive validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


def validate_codeql(workflows):
    """Every CodeQL job shares a single immutable action version."""
    for filename, workflow in workflows.items():
        for name, job in workflow.get("jobs", {}).items():
            pins = {
                step["uses"].rsplit("@", 1)[-1]
                for step in job.get("steps", [])
                if re.match(
                    r"github/codeql-action/(init|autobuild|analyze)@",
                    step.get("uses", ""),
                )
            }
            if len(pins) > 1 or any(
                not re.fullmatch(r"[0-9a-f]{40}", pin) for pin in pins
            ):
                raise ValueError(
                    f"{filename}/{name}: CodeQL actions must share one full commit SHA"
                )


def validate_graph(workflows, validators):
    """Walk callable validators and enforce one orchestration entry point."""
    visited = set()

    def callable_workflow(filename, chain=()):
        if filename in chain:
            raise ValueError(f"Recursive validation: {chain} -> {filename}")
        if filename in visited:
            return
        workflow = workflows[filename]
        triggers = workflow.get("on", {})
        if not isinstance(triggers, dict) or "workflow_call" not in triggers:
            raise ValueError(f"{filename}: missing workflow_call")
        if set(triggers) - {"workflow_call", "workflow_dispatch"}:
            raise ValueError(f"{filename}: validation must start through Quality gate")
        visited.add(filename)
        for name, job in workflow.get("jobs", {}).items():
            reference = job.get("uses", "")
            if reference.startswith("./.github/workflows/"):
                callable_workflow(reference.rsplit("/", 1)[-1], (*chain, filename))
            elif "runs-on" in job and "timeout-minutes" not in job:
                raise ValueError(f"{filename}/{name}: an explicit timeout is required")

    for filename in validators:
        callable_workflow(filename)
    return visited


def validate(directory: Path) -> None:
    """Reject duplicate validation triggers, missing gate jobs and mixed CodeQL pins."""
    policy = json.loads((directory / ".release-policy.json").read_text())
    workflows = {
        path.name: yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        for path in (directory / ".github/workflows").glob("*.y*ml")
    }
    validate_codeql(workflows)
    visited = validate_graph(workflows, policy["validation_workflows"])
    for filename, workflow in workflows.items():
        if (
            "pull_request" in workflow.get("on", {})
            and filename not in visited
            and filename
            not in {"quality-gate.yml", "auto-approve.yml", "auto-merge.yml"}
        ):
            raise ValueError(f"{filename}: PR validator is outside the required gate")
    gate = workflows["quality-gate.yml"]["jobs"]
    expected = {
        f"./.github/workflows/{filename}" for filename in policy["validation_workflows"]
    }
    actual = {job.get("uses") for job in gate.values() if "uses" in job}
    if actual != expected or set(gate["gate"].get("needs", [])) != set(gate) - {"gate"}:
        raise ValueError(
            "CI gate must require every configured validator and contract job"
        )
    if "workflow-contracts" not in gate:
        raise ValueError("CI gate must include its configuration contracts")


if __name__ == "__main__":
    validate(Path.cwd())
    print("CI entry point, timeouts and CodeQL pins are consistent.")
