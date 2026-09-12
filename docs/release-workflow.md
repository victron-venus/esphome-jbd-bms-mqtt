# CI and release operations — victron-venus/esphome-jbd-bms-mqtt

The source of truth is `.release-policy.json`. `quality-gate.yml` runs the callable
validation workflows and produces the required **CI gate** status on every PR
and merge-queue commit. Missing, failed and skipped validation workflows fail
the gate. Workflow and lockfile changes are included in validation.

## Local checks

Use Python 3.11+ for the CLI and the project toolchains documented in `scripts/ci.sh`.
The scripts fail on missing dependencies and do not publish anything during checks.

```bash
python3 scripts/release.py check
python3 scripts/release.py status
```

Callable validation workflows:
- `.github/workflows/validate.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/trivy-fs.yml`

## Nightly validation and deployment

This repository uses validation-only policy: PR/merge queue checks and staggered
nightly validation. It does not publish synthetic application beta/RC releases.
Infrastructure deployments remain manual and use the checks and explicit source
approval declared by their deployment workflow. Terraform validation uses backend-disabled
copies; a green syntax/validate job is not a reviewed plan or a deployment.

## Project limits and rollout requirements

- Validation-only policy: no synthetic beta/RC artifacts or tag-triggered stable releases.
- ESPHome compile matrix remains required; no flashing or hardware BLE/MQTT checks. Some external components follow upstream main.
- Dependency review remains a PR-only comparison; callable full-source validation workflows run for nightly and candidate checks.

For public repositories, merge and verify the workflows before enabling the
additive Terraform **CI gate** ruleset. Where release/deployment workflows use
environments, configure reviewers and default-branch-only policies. The governance
repositories contain `release-standards.tf` and opt-in examples for public
repositories only. Do not extend these requirements to private repositories by
buying a plan or to workflows that have not landed.

Existing review/security rules remain in force. Physical hardware, real
credentials/streams and production access are not implied by unit tests or builds.

The release engine/client are vendored from `victron-venus/venus-os-ci-toolkit`.
They are excluded from consumer-specific formatting/type policy. Application
release workflows run the mandatory Release tooling contracts job; validation-only
projects receive the local client, whose contracts run in the toolkit. Update the toolkit source and rerun
`scripts/install_release.py`; `--check` detects drift.

References: [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[protected environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments),
[artifact provenance](https://docs.github.com/en/rest/actions/artifacts).
