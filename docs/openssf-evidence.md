# OpenSSF Best Practices evidence: esphome-jbd-bms-mqtt

This index supports review against the [OpenSSF Passing criteria](https://www.bestpractices.dev/en/criteria/0). It is not an awarded badge, a security guarantee or a completed self-attestation. Initial source inventory: `a025c2764208909c37900198910f9f1d13ae2028`. Re-check the final merged commit and its CI before submitting an assessment.

## Project and contribution process

Builds ESPHome firmware that reads JBD BMS devices over Bluetooth and publishes MQTT telemetry.

- [Public repository and history](https://github.com/victron-venus/esphome-jbd-bms-mqtt) provide source, commits and interim changes.
- [README](../README.md) describes installation, configuration and usage.
- [Contribution process](../CONTRIBUTING.md) documents reports, review, style and the policy to add automated tests for major changes.
- [Issues](https://github.com/victron-venus/esphome-jbd-bms-mqtt/issues) and [pull requests](https://github.com/victron-venus/esphome-jbd-bms-mqtt/pulls) provide searchable public discussion and change review.
- [Security policy](../SECURITY.md) documents confidential reporting, response goals, trust boundaries and delivery practices.

The root [LICENSE](../LICENSE) records the project license. Third-party components retain their own notices.

## Implementation and interfaces

- [jbd-all-batteries.yaml](../jbd-all-batteries.yaml)
- [packages](../packages)
- [components](../components)

Interface documentation must explain accepted configuration and inputs, outputs, failure handling and relevant permission boundaries. Verify it against the implementation when changing behavior; source links alone do not establish that every interface is documented.

## Build, test and analysis evidence

The local validation entry point is [scripts/ci.sh](../scripts/ci.sh). Its actual test and compiler/linter commands, not the presence of a workflow name, define the available coverage.

[GitHub Actions](https://github.com/victron-venus/esphome-jbd-bms-mqtt/actions) provides run logs and results. The checked-in workflow definitions are:

- [auto-approve.yml](../.github/workflows/auto-approve.yml)
- [auto-merge.yml](../.github/workflows/auto-merge.yml)
- [ci.yml](../.github/workflows/ci.yml)
- [codeql.yml](../.github/workflows/codeql.yml)
- [coderabbit-autofix.yml](../.github/workflows/coderabbit-autofix.yml)
- [coderabbit-review.yml](../.github/workflows/coderabbit-review.yml)
- [dependency-review.yml](../.github/workflows/dependency-review.yml)
- [publish-release.yml](../.github/workflows/publish-release.yml)
- [quality-gate.yml](../.github/workflows/quality-gate.yml)
- [release-bot.yml](../.github/workflows/release-bot.yml)
- [release.yml](../.github/workflows/release.yml)
- [scorecard.yml](../.github/workflows/scorecard.yml)
- [trivy-fs.yml](../.github/workflows/trivy-fs.yml)
- [validate.yml](../.github/workflows/validate.yml)

Do not equate a green metadata or release job with successful application tests. Record actual test results, coverage limitations and security-analysis results for the submitted revision. Test execution does not establish physical-device behavior.

## Items requiring explicit verification before submission

- Confirm the private reporting channel works and examine issue/advisory history. Historical response-time claims require actual reports and responses, including any reports outside GitHub.
- Obtain primary-developer attestations about secure-design and vulnerability-prevention knowledge; repository text cannot establish a person's knowledge.
- Verify every user-facing release has useful release notes and upgrade impact, and includes any assigned vulnerability identifiers for fixes.
- Review dependency, code-scanning and secret-scanning findings and their age. A workflow success result is not proof that all findings are resolved.
- Review the actual cryptographic libraries, protocols, key lengths, randomness, certificate checks and password storage applicable to this project. Do not copy another project's answers.
- Verify build reproducibility from source, test policy adherence in recent substantive changes, dynamic analysis and any manual-memory-code checks.
- Link only this project's real awarded badge once the assessment is accepted.

The live assessment, when created, is the source of truth for the badge level. Unverified criteria remain open.
