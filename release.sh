#!/usr/bin/env bash
set -euo pipefail
echo 'This repository validates firmware configuration; unverified tag-and-publish releases are disabled.' >&2
echo 'Run bash scripts/ci.sh or dispatch quality-gate.yml. See docs/CI_WORKFLOW.md.' >&2
exit 1
