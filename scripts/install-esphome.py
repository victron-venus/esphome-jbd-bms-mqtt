#!/usr/bin/env python3
"""Install the supported Linux CI compiler from complete hash-verified locks."""

import platform

# Only fixed pip commands and repository-owned requirement paths are executed.
import subprocess  # nosec B404
import sys
from pathlib import Path


def main():
    """Reject unsupported hosts before installing any compiler dependency."""
    if (sys.platform != "linux" or platform.python_implementation() != "CPython"
            or sys.version_info[:2] != (3, 12)):
        raise SystemExit("The locked ESPHome compiler requires Linux and CPython 3.12.")
    root = Path(__file__).resolve().parents[1]
    subprocess.run(  # nosec B603
        [sys.executable, "-m", "pip", "install", "--require-hashes",
         "--only-binary=:all:", "-r", str(root / ".github/requirements-build.txt")],
        check=True,
    )
    subprocess.run(  # nosec B603
        [sys.executable, "-m", "pip", "install", "--require-hashes",
         "--no-build-isolation", "-r", str(root / ".github/requirements-esphome.txt")],
        check=True,
    )
    subprocess.run(  # nosec B603
        [sys.executable, "-m", "pip", "check"], check=True,
    )


if __name__ == "__main__":
    main()
