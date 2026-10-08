# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Hash-lock the Linux CPython 3.12 firmware compiler and build backends. Use the
  official ESPHome 2026.10.0b1 prerelease constraints to remove the vulnerable
  Starlette pin, and reject unsupported installer platforms before pip runs.

## [1.0.1] - 2026-03-29

### Added
- `commit.sh` and `release.sh` helper scripts
- Additional badges in README
- Cross-reference to dbus-mqtt-battery

## [1.0.0] - 2026-03-25

### Added
- Initial release
- ESP32 Bluetooth proxy for JBD BMS
- MQTT publishing to Venus OS
- Support for multiple BMS units
- Cell voltage monitoring
- Temperature sensors
- SoC and capacity reporting
- Charge/discharge status

[1.0.1]: https://github.com/victron-venus/esphome-jbd-bms-mqtt/releases/tag/v1.0.1
[1.0.0]: https://github.com/victron-venus/esphome-jbd-bms-mqtt/releases/tag/v1.0.0
