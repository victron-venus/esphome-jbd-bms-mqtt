# CI and release policy

This repository has a validation-only policy. The `Quality gate` workflow runs
on pull requests, merge queue entries, the default branch, and a staggered
nightly UTC schedule. Every configured validation workflow must finish
successfully; a skipped or failed workflow does not pass `CI gate`.

Install actionlint 1.7.12 (and Node.js when JavaScript sources are present).
Run the same checks in a fresh Linux CPython 3.12 virtual environment:

```sh
python3 -m pip install --require-hashes --only-binary=:all: -r .github/requirements-workflow-contracts.txt
python3 scripts/install-esphome.py
bash scripts/ci.sh
```

Request or inspect CI from a local checkout:

```sh
gh workflow run quality-gate.yml
gh run list --workflow quality-gate.yml
```

No beta, RC or stable application release is synthesized from configuration or
reference source. Disabled legacy publisher entry points only explain this
migration. Their exact previous contents remain in `docs/legacy-workflows/`.
Production deployment, where provided, requires manual dispatch from the default
branch and the `production` environment; validation never deploys resources.

The supported CI compiler is the **ESPHome 2026.10.0b1 prerelease**, with its
official dependency constraints, on Linux and CPython 3.12. It includes
PlatformIO 6.2.0, which permits the patched Starlette dependency; the previous
ESPHome 2026.8.2 / PlatformIO 6.1.19 combination pinned a vulnerable version.
The compiler lock deliberately targets Linux: the upstream prerelease's Intel
macOS dependency constraint still selects an affected cryptography version.
The installer rejects unsupported operating systems, Python implementations
and Python versions before invoking pip. This CI choice does not recommend a
prerelease for production devices or establish macOS/Windows compiler support.

Both `.github/requirements-build.txt` and `.github/requirements-esphome.txt`
contain exact versions and hashes. The installer first installs the locked
build backends, then installs the compiler with build isolation disabled so
source distributions cannot fetch an unpinned backend. It finishes with
`pip check`. To refresh the compiler lock, review the upstream release and run:

```sh
uv pip compile .github/requirements-esphome.in --generate-hashes --universal --python-version 3.12 -o .github/requirements-esphome.txt
```

Keep the Linux markers in the input and generated lock, audit every selected
package version, and pass all three Linux firmware builds before accepting an
update. `bash scripts/ci.sh syntax` runs the source and regression checks;
`bash scripts/ci.sh compile` validates and compiles the configured matrix with
temporary dummy secrets, without flashing. ESPHome/PlatformIO and external
component downloads require network access.
These Python locks do not cover ESPHome's separately managed ESP-IDF toolchain
environment or change the external-component sources declared in the YAML.

## Coverage limits

- Validation-only policy: no synthetic beta/RC artifacts or tag-triggered stable releases.
- ESPHome compile matrix remains required; no flashing or hardware BLE/MQTT checks. Some external components follow upstream main.
