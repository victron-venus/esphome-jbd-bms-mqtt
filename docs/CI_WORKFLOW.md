# CI and release policy

This repository has a validation-only policy. The `Quality gate` workflow runs
on pull requests, merge queue entries, the default branch, and a staggered
nightly UTC schedule. Every configured validation workflow must finish
successfully; a skipped or failed workflow does not pass `CI gate`.

Install actionlint 1.7.12 (and Node.js when JavaScript sources are present).
Run the same local checks:

```sh
python3 -m pip install PyYAML==6.0.3
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

Install `esphome==2026.8.2` in a Python 3.12 virtual environment. `bash scripts/ci.sh syntax` runs just the baseline; `bash scripts/ci.sh compile` validates and compiles the configured matrix with temporary dummy secrets, without flashing. ESPHome/PlatformIO and external component downloads require network access.

## Coverage limits

- Validation-only policy: no synthetic beta/RC artifacts or tag-triggered stable releases.
- ESPHome compile matrix remains required; no flashing or hardware BLE/MQTT checks. Some external components follow upstream main.
