# Contributing to esphome-jbd-bms-mqtt

Thank you for your interest in contributing!

## How to Contribute

### Reporting Bugs

1. Check existing [issues](https://github.com/victron-venus/esphome-jbd-bms-mqtt/issues) to avoid duplicates
2. Use the bug report template
3. Include:
   - ESPHome version
   - ESP32 board model
   - JBD BMS model and firmware
   - MQTT broker details
   - Relevant logs

### Suggesting Features

1. Open a feature request issue
2. Describe the use case
3. Explain why it would benefit others

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test with actual hardware
5. Validate YAML: `esphome config your-config.yaml`
6. Commit with clear messages
7. Push and create a Pull Request

### Code Style

- Follow ESPHome YAML conventions
- Use meaningful names for sensors
- Add comments for non-obvious configurations
- Keep configurations modular

### Testing

- Test with actual JBD BMS hardware
- Verify Bluetooth connection stability
- Check MQTT message publishing
- Monitor ESP32 memory usage

## Development Setup

```bash
# Clone
git clone https://github.com/victron-venus/esphome-jbd-bms-mqtt.git
cd esphome-jbd-bms-mqtt

# Create secrets.yaml
cp secrets.yaml.example secrets.yaml
# Edit with your WiFi and MQTT credentials

# Compile and upload
esphome run jbd-bms.yaml
```

## Questions?

- Open a [Discussion](https://github.com/victron-venus/esphome-jbd-bms-mqtt/discussions)
- Ask on [Victron Community](https://community.victronenergy.com/)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
