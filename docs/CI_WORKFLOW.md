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

The supported CI compiler is the **ESPHome 2026.11.0b1 prerelease**, with its
official dependency constraints, on Linux and CPython 3.12. It permits fixed
Pillow 13.0.0 and filelock 4.2.6 without overrides. A compatible stable compiler
should replace this CI prerelease only after the same full compile checks.
The lock deliberately targets Linux: upstream's Intel-macOS cryptography 50.0.2
pin conflicts with `aioesphomeapi`'s `<49` requirement there.
The compiler job uses custom runners only when their configured labels include
`linux` or the exact Linux x64 ARC scale-set name `victron-reserve-ci-x64`.
ARC uses a scale-set name rather than a set of OS labels. Other custom targets
fall back to hosted `ubuntu-latest`. The existing event trust checks still apply:
fork PRs and non-default branch pushes stay hosted. `CI_RUNNER_MODE=github`
remains the default; this routing compatibility change does not activate ARC or
establish runtime readiness. The installer also rejects
unsupported operating systems, Python implementations and Python versions
before invoking pip. This CI choice does not recommend a
prerelease for production devices or establish macOS/Windows compiler support.

Both `.github/requirements-build.txt` and `.github/requirements-esphome.txt`
contain exact versions and hashes. The installer first installs the locked
build backends, then installs the compiler with build isolation disabled so
source distributions cannot fetch an unpinned backend. It finishes with
`pip check`. To refresh the compiler lock, review the upstream release and run
from the repository root with uv 0.12.7:

```sh
uv --directory .github pip compile requirements-esphome.in --generate-hashes --universal --python-version=3.12 --output-file=requirements-esphome.txt
```

For a transitive compiler security fix, append `--upgrade-package <name>` to
the compile command above, replacing `<name>` with the affected package. Without
that flag, uv can retain the existing lock pin. Verify that the regenerated lock
selects a version in the advisory's fixed range on every affected marker branch.
If the compiler constraints exclude the fix, coordinate a compatible compiler
input, policy and matrix update instead of overriding those constraints. Retain
the hash-checked installation, `pip check` and full firmware compile matrix.

The dedicated `.github/pyproject.toml` limits universal resolution to Linux
without limiting architecture; x86_64 and aarch64 remain supported. Keep
`--directory .github` so uv reads this scoped metadata. Root-level regeneration
without it attempts unsupported operating-system branches. This file affects
compiler lock regeneration, not runtime installation or other tooling.

Renovate updates the independent build-backend lock and CI dependencies. The
compiler input `.github/requirements-esphome.in` and its generated
`.github/requirements-esphome.txt` stay on this manual procedure together:
`crcmod==1.7` has no compatible wheels, so resolving this lock requires a source
build. The update runner forbids package build-backend execution. Review and
regenerate this pair in the controlled Linux environment above, then pass the
full firmware compile matrix. This exception also applies to compiler security
updates; GitHub vulnerability alerts remain enabled.

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
