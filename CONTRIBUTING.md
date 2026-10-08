# Contributing to esphome-jbd-bms-mqtt

Builds ESPHome firmware that reads JBD BMS devices over Bluetooth and publishes MQTT telemetry.

## Reports and discussion

Use [GitHub Issues](https://github.com/victron-venus/esphome-jbd-bms-mqtt/issues) for bugs, enhancements and design discussion. Search existing reports first. English reports and pull requests are welcome. Include the version or commit, platform, sanitized configuration, reproduction steps, expected behavior and actual behavior. Do not include credentials, personal data or private capture files. Use [SECURITY.md](SECURITY.md) for confidential vulnerability reports.

## Proposing a change

1. Fork or clone the repository over HTTPS and create a topic branch from the default branch.
2. Keep the change focused and explain the problem and observable behavior in a pull request.
3. Follow the existing language style and checked-in formatter/linter configuration. Resolve new warnings; explain any narrowly scoped exception with evidence.
4. Add automated tests for major new functionality and regression tests for corrected bugs. Cover rejected input, unavailable dependencies and relevant failure paths as well as successful input.
5. Update user-facing configuration/interface documentation and release notes for changed behavior. Record upgrade impact and any public vulnerability identifier when applicable.
6. Report the exact checks run, their results and any checks that were not run. Wait for required CI and reviewer approval before merging.

Contributions must be compatible with [LICENSE](LICENSE). Preserve third-party copyright and license notices; do not copy code without compatible redistribution rights.

## Local validation

Run `bash scripts/ci.sh syntax` for source checks and unit tests; run `bash scripts/ci.sh compile` for the firmware compilation check. Use the firmware and dependency versions declared by the scripts. Uploading firmware is a separate hardware operation.

Automated tests use mocks or controlled fixtures where available. A passing unit test does not establish hardware safety. Describe any physical-device test separately, including firmware, configuration and expected rollback. Never run installation, deployment, Terraform apply or actuator commands merely to validate a documentation change.

## Source and interfaces

- [jbd-all-batteries.yaml](jbd-all-batteries.yaml)
- [packages](packages)
- [components](components)

See [README.md](README.md) for acquisition, configuration and usage, and [the evidence index](docs/openssf-evidence.md) for the public development-process references.
