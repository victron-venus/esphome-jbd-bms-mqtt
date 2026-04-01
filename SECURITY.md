# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **Do NOT** open a public issue
2. Email the maintainers directly or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

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
