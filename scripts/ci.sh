#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-all}" in
  syntax) python3 scripts/validate-source.py; python3 -m unittest discover -s tests -p 'test_compile_contract.py' -v ;;
  compile) shift; python3 scripts/compile-esphome.py "$@" ;;
  all) python3 scripts/validate-source.py; python3 -m unittest discover -s tests -p 'test_compile_contract.py' -v; python3 scripts/compile-esphome.py ;;
  *) echo 'Usage: scripts/ci.sh [syntax|compile [config]|all]' >&2; exit 2 ;;
esac
