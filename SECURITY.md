# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

Private vulnerability reporting is enabled for this repository. Use
[Report a vulnerability](https://github.com/victron-venus/esphome-jbd-bms-mqtt/security/advisories/new)
to send a confidential report to the maintainers. Follow
[GitHub's private reporting instructions](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
if you need help submitting the report.

Include the affected version or commit, steps to reproduce, expected and actual
behavior, and potential impact. Remove access tokens, credentials and personal
data from examples. Do not disclose exploit details in public issues before
coordinating with the maintainers.

## Security Considerations

This project runs on ESP32 with access to:

- WiFi network
- MQTT broker
- Bluetooth (BMS devices)

### Recommendations

1. **secrets.yaml**: Never commit real credentials
2. **MQTT**: Use authentication on your MQTT broker
3. **WiFi**: Use WPA2/WPA3 encryption
4. **OTA**: ESPHome OTA updates require password

## Known Limitations

- MQTT connection without TLS by default
- Designed for trusted home networks only
