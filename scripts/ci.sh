#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-all}" in
  syntax) python3 scripts/validate-source.py ;;
  compile) shift; python3 scripts/compile-esphome.py "$@" ;;
  all) python3 scripts/validate-source.py; python3 scripts/compile-esphome.py ;;
  *) echo 'Usage: scripts/ci.sh [syntax|compile [config]|all]' >&2; exit 2 ;;
esac
