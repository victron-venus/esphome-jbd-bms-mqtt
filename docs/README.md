# Documentation index

These documents describe installing, configuring and operating the ESPHome JBD
BMS monitors, including battery telemetry and CI.

## Get started

| Document | Description |
| --- | --- |
| [Install the JBD monitor from your browser](browser-install.md) | Browser-based serial provisioning without a local compiler. |
| [Firmware management access](firmware-access.md) | Management access behaviour and the migration procedure before updating. |
| [JBD battery monitoring without Victron or Cerbo GX](standalone-home-assistant.md) | Running the profiles against an ordinary MQTT broker and Home Assistant. |
| [Source delivery and upstream updates](source-versioning.md) | Current reviewed source versus the historical v1.4.0 release. |

## Operate

| Document | Description |
| --- | --- |
| [One virtual battery, several physical batteries](virtual-series-battery.md) | Series battery configuration, diagrams, policies and runbook. |
| [Battery telemetry during startup and reconnect](battery-telemetry.md) | The schema-1 four-cell telemetry contract for new collectors. |
| [Roadmap through October 2027](roadmap.md) | Compatibility, interface and validation priorities. |

## Verify

| Document | Description |
| --- | --- |
| [Battery telemetry fuzz assessment](fuzzing.md) | The host-only libFuzzer target, cost policy and reproduction. |
| [OpenSSF Best Practices evidence](openssf-evidence.md) | Evidence index reviewed against the Passing criteria. |

## CI and release

| Document | Description |
| --- | --- |
| [CI and release policy](CI_WORKFLOW.md) | The validation-only policy and what the quality gate runs. |
| [CI orchestration](CI-ORCHESTRATION.md) | How the quality gate and release pipeline divide validation. |
| [Release helper TLS profile](release-tls-profile.md) | Verified TLS profile used by release helpers. |

Shared repository policy: [release-workflow.md](release-workflow.md) is generated or shared boilerplate maintained in [victron-venus/venus-os-ci-toolkit](https://github.com/victron-venus/venus-os-ci-toolkit).
