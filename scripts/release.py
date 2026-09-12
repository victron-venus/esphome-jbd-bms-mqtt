#!/usr/bin/env python3
# Vendored release toolkit; change the toolkit source, then render again.
# ruff: noqa
# mypy: ignore-errors
# pylint: skip-file
# fmt: off
"""Local entry point for the same checks, packages and release requests as CI.

This client never creates tags or publishes assets. Publication stays in the
reviewed default-branch workflow, including the protected stable environment.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
RC = re.compile(r"v((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))-rc\.([1-9]\d*)\Z")


def run(*args: str, capture: bool = False) -> str:
    """Run a checked command from the release repository root."""
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def policy() -> dict:
    """Read the checked-in release policy used by local and hosted operations."""
    return json.loads((ROOT / ".release-policy.json").read_text())


def base_version(value: str) -> str:
    # Repository metadata may already contain a SemVer prerelease suffix.
    """Normalize repository version metadata to a strict SemVer base version."""
    value = value.strip().removeprefix("v").split("-", 1)[0]
    if not VERSION.fullmatch(value):
        raise ValueError(f"Expected X.Y.Z version, got {value!r}")
    return value


def resolve_version(config: dict, requested: str = "") -> str:
    """Resolve an explicit version or the configured committed version source."""
    # Each metadata format is explicit so malformed sources cannot fall through silently.
    # pylint: disable=too-many-return-statements,too-many-branches
    if requested:
        if not VERSION.fullmatch(requested):
            raise ValueError(
                "Requested version must be X.Y.Z without a prefix or suffix"
            )
        return requested
    if config.get("version"):
        return base_version(config["version"])
    file = config.get("version_file")
    if file:
        path = ROOT / file
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("version_file must stay inside the repository")
        data = path.read_text()
        if path.suffix == ".json":
            return base_version(json.loads(data)["version"])
        if path.suffix == ".toml":
            parsed = tomllib.loads(data)
            for section in ("project", "package"):
                if isinstance(parsed.get(section, {}).get("version"), str):
                    return base_version(parsed[section]["version"])
            if isinstance(
                parsed.get("workspace", {}).get("package", {}).get("version"), str
            ):
                return base_version(parsed["workspace"]["package"]["version"])
        match = re.search(
            r"(?im)^\s*(?:__version__|VERSION|version)\s*[:=]\s*[\"']?"
            r"([0-9]+\.[0-9]+\.[0-9]+(?:-[\w.]+)?)",
            data,
        )
        if match:
            return base_version(match[1])
        return base_version(data)
    if config.get("version_from_tags"):
        tags = run(
            "git", "tag", "--merged", "HEAD", "--list", "v*", capture=True
        ).splitlines()
        versions = [
            tuple(map(int, tag[1:].split(".")))
            for tag in tags
            if tag.startswith("v") and VERSION.fullmatch(tag[1:])
        ]
        if versions:
            major, minor, patch = max(versions)
            return f"{major}.{minor}.{patch + 1}"
    raise ValueError("Set version_file in .release-policy.json or pass --version X.Y.Z")


def gh_json(*args: str) -> dict:
    """Read and decode a GitHub CLI JSON response."""
    return json.loads(run("gh", *args, capture=True))


def repository(config: dict) -> str:
    """Resolve and validate the OWNER/REPO identity for GitHub operations."""
    repo = config.get("repository") or run(
        "gh",
        "repo",
        "view",
        "--json",
        "nameWithOwner",
        "--jq",
        ".nameWithOwner",
        capture=True,
    )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository name")
    return repo


def dispatch(args: argparse.Namespace, config: dict) -> None:
    """Request the default-branch workflow only from a matching clean checkout."""
    if config.get("mode", "release") != "release":
        raise ValueError(
            "This project has validation/deployment policy, not application releases"
        )
    repo = repository(config)
    details = gh_json("api", f"repos/{repo}")
    branch = details["default_branch"]
    head = gh_json("api", f"repos/{repo}/commits/{branch}")["sha"]
    local = run("git", "rev-parse", "HEAD", capture=True)
    dirty = run("git", "status", "--porcelain", capture=True)
    if dirty or local != head:
        raise ValueError(
            "Release requests require a clean checkout at GitHub's "
            "default-branch HEAD. Commit, review and merge changes first, "
            "then update this checkout."
        )
    fields = ["-f", f"channel={args.command}", "-f", f"expected_sha={head}"]
    if args.command == "stable":
        if not args.rc or not RC.fullmatch(args.rc):
            raise ValueError("stable requires --rc vX.Y.Z-rc.N")
        fields += ["-f", f"rc_tag={args.rc}"]
    else:
        fields += ["-f", f"version={resolve_version(config, args.version)}"]
    command = [
        "gh",
        "workflow",
        "run",
        "release-pipeline.yml",
        "--repo",
        repo,
        "--ref",
        branch,
        *fields,
    ]
    if args.dry_run:
        print(
            json.dumps(
                {"repository": repo, "source_sha": head, "command": command}, indent=2
            )
        )
        return
    run(*command)
    print(
        f"Requested {args.command} for {repo} at {head}. "
        f"Track: https://github.com/{repo}/actions/workflows/release-pipeline.yml"
    )
    if args.command == "stable":
        print("The stable job waits for the release environment's required reviewer.")


def main() -> int:
    """Route local checks, packaging, inspection and guarded workflow requests."""
    # Keep command dispatch sequential so publication side effects remain visible.
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("check", help="Run the checked-in local validation script")
    build = subs.add_parser(
        "package", help="Build candidate artifacts locally, without publishing"
    )
    build.add_argument("--version", default="")
    build.add_argument("--channel", choices=["nightly", "beta", "rc"], default="rc")
    for channel in ("nightly", "beta", "rc", "stable"):
        sub = subs.add_parser(
            channel, help="Request the default-branch release workflow"
        )
        sub.add_argument("--version", default="")
        sub.add_argument("--rc", default="")
        sub.add_argument("--dry-run", action="store_true")
    subs.add_parser("status", help="Read recent release workflow runs")
    subs.add_parser("doctor", help="Read release environment configuration")
    resolve = subs.add_parser("resolve", help=argparse.SUPPRESS)
    resolve.add_argument("--version", default="")
    collect = subs.add_parser("collect", help=argparse.SUPPRESS)
    collect.add_argument("source")
    collect.add_argument("destination")
    args = parser.parse_args()
    try:
        config = policy()
        if args.command == "check":
            run("bash", "scripts/ci.sh")
        elif args.command == "package":
            version = resolve_version(config, args.version)
            scripts = ["scripts/package-release.sh", "scripts/release-build.sh"]
            script = next((p for p in scripts if (ROOT / p).is_file()), None)
            if not script:
                raise ValueError(
                    "Packaging is a platform matrix in release-build.yml; use a "
                    "remote rc request for the complete target set"
                )
            run("bash", script, version, args.channel)
        elif args.command == "resolve":
            print(resolve_version(config, args.version))
        elif args.command == "collect":
            source, destination = Path(args.source), Path(args.destination)
            destination.mkdir(parents=True, exist_ok=False)
            files = list(source.rglob("*"))
            seen = set()
            for file in files:
                if file.is_symlink():
                    raise ValueError(f"Symlink asset: {file}")
                if not file.is_file():
                    continue
                if file.name.casefold() in seen:
                    raise ValueError(
                        f"Duplicate asset basename across platforms: {file.name}"
                    )
                seen.add(file.name.casefold())
                shutil.copyfile(file, destination / file.name)
            if not seen:
                raise ValueError("No build assets were downloaded")
        elif args.command == "status":
            run(
                "gh",
                "run",
                "list",
                "--repo",
                repository(config),
                "--workflow",
                "quality-gate.yml"
                if config.get("mode") == "validation-only"
                else "release-pipeline.yml",
                "--limit",
                "10",
            )
        elif args.command == "doctor":
            repo = repository(config)
            environment = gh_json("api", f"repos/{repo}/environments/release")
            reviewers = [
                rule
                for rule in environment.get("protection_rules", [])
                if rule.get("type") == "required_reviewers" and rule.get("reviewers")
            ]
            if not reviewers:
                raise ValueError(
                    "Environment 'release' must have required reviewers before stable publication"
                )
            print(
                json.dumps(
                    {
                        "repository": repo,
                        "release_environment": environment["html_url"],
                        "reviewers_configured": True,
                    },
                    indent=2,
                )
            )
        else:
            dispatch(args, config)
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"release: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
