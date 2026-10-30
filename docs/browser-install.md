# Install the JBD monitor from your browser

**You do not need Python, Homebrew or PlatformIO on the computer connected to
USB.** Use ESPHome Device Builder on Home Assistant or another server to build
your device configuration, then use [ESPHome Web](https://web.esphome.io/) to
write the resulting factory image from desktop Chrome or Edge.

A ready-made public image cannot currently configure this monitor completely:
its BMS addresses, MQTT endpoint and private API/OTA key are compiled into the
firmware. The repository does not provide a runtime setup wizard for those
fields. Browser flashing removes the local compiler installation; it does not
remove the need to configure your batteries.

## 1. Prepare your device in ESPHome Device Builder

1. Open your existing ESPHome Device Builder, or install it on Home Assistant
   using the [official installation guide](https://esphome.io/guides/installing_esphome/).
2. Identify the board before building. The maintained profiles target a classic
   ESP32 (`esp32dev`) and currently require chip revision **3.1 or newer**. They
   are not interchangeable with ESP32-C3, S2, S3, C6 or ESP8266 images.
3. Use `jbd-all-batteries1.yaml` or `jbd-all-batteries2.yaml` from the same repository
   revision as `components/battery_telemetry.h` and
   `packages/mqtt-availability.yaml`. Place those files in the Device Builder
   configuration directory with their relative directories intact. Home
   Assistant's file editor can do this without a local command-line toolchain.
4. Configure your own four BMS addresses and broker, and preserve the intended
   chain/topic identity. These maintained profiles expect **four batteries with
   four cells each**; another topology requires adapting the configuration.
   Follow [standalone MQTT and Home Assistant setup](standalone-home-assistant.md).
5. Complete the private `secrets.yaml` using the project's
   [management-access instructions](firmware-access.md). Keep unique Wi-Fi,
   fallback-AP and API/OTA credentials private. For an existing monitor, preserve
   its established key and discovery IDs. Do not copy the repository's example
   device addresses or another installation's secrets into your device.

## 2. Build and download the factory image

In the device's menu choose **Install → Manual download → Factory format**.
The builder compiles on the Home Assistant/server machine and downloads a
`.factory.bin` image to the computer running your browser. UI wording can vary
slightly between Device Builder versions. Use a compiler version validated for
the selected repository revision; the current version is recorded in
[`.release-policy.json`](../.release-policy.json).

The factory image includes the bootloader and partition layout for first serial
installation. An OTA-only `.bin`, a source ZIP, and a GitHub Actions log are not
substitutes. The image contains your configured credentials: keep it local and
out of public GitHub releases, issues, shared download links and CI artifacts.

## 3. Flash over USB

1. Back up a working device's existing configuration and recovery image first.
2. Connect the supported ESP32 board with a USB data cable.
3. Open **[ESPHome Web](https://web.esphome.io/)**, click **Connect**, and select
   that board's serial port.
4. Choose **Install**, select your downloaded factory image, review the
   installation/erase confirmation, and start the write. Use the existing-project
   installation path, not a generic “prepare for first use” image.
5. Keep USB power connected until the write completes and the board reboots.
   Check the serial logs, Wi-Fi connection, MQTT availability and actual fresh
   BMS readings. An installer success message confirms a write, not battery
   topology or telemetry correctness.

The generic [Espressif browser flasher](https://espressif.github.io/esptool-js/)
is an alternative for the **merged ESP32 factory image at address `0x0`**.
Use ESPHome Web if you do not need manual flash-address controls. Never apply
`0x0` to an OTA-only application image or a different multi-part layout.

## What downloads and releases mean here

This repository currently has a **validation-only** release policy. CI compiles
with deliberately synthetic credentials and removes those test outputs. Those
builds are not installable public products. Source tags and ZIP downloads still
need your own device configuration and compilation.

A future direct-install release must provide a real runtime onboarding flow
for all required settings, board-specific factory images, reproducible build
inputs and checksums, and must contain no private credentials or synthetic
battery identities. Until that exists, use the personalised factory image
produced above rather than an image for somebody else's installation.

## Browser and USB troubleshooting

Use desktop Chrome or Edge on Windows, macOS, or Linux and open
[ESPHome Web](https://web.esphome.io/) directly over HTTPS. The browser must expose the Web Serial API (`navigator.serial`). If it does
not, use a current desktop Chrome or Edge; do not assume mobile/iOS support. The ESP device connects to the
computer running the browser; it does not need to connect to the Home Assistant
server's USB port.

- **No serial port:** use a USB data cable, try a direct USB port, and check that
  the USB-to-serial adapter appears in the operating system. Install the adapter
  manufacturer's CP210x or CH340 driver only if the operating system needs it.
- **Port busy or access denied:** close other browser tabs, serial monitors and
  ESPHome log sessions. On Linux, check your distribution's serial-port group
  permissions and sign in again after changing them; do not run the browser as
  root or make all serial devices world-writable.
- **Cannot connect to the bootloader:** follow the exact board's BOOT/EN procedure.
  For an ESP32 DevKit with those buttons, hold BOOT, briefly press EN/RESET, then
  release BOOT once the flasher connects. Do not short unidentified pins.
- **Write errors:** use a shorter data cable and stable USB power. With a generic
  flasher, reduce the serial baud rate before trying again.
- **Image rejected or repeated resets:** stop and verify the chip family, flash
  capacity, board configuration and factory-image format. Do not try arbitrary
  offsets or erase a working device merely to bypass a mismatch.

## Updates and recovery

Keep the original device configuration and its private secrets alongside a
known-good firmware backup. Initial USB installation and encrypted network OTA
are different transports: choosing a browser flasher does not require enabling
an HTTP server, weakening API authentication, or publishing credentials.

For an already working device, use the project's documented OTA update and
migration procedure with its existing identity and credentials. A full serial
factory installation may replace its partition layout or settings. Back up
first and review any erase option before confirming it.

## Upstream instructions

- [ESPHome Device Builder installation](https://esphome.io/guides/installing_esphome/)
- [ESPHome getting started](https://esphome.io/install/getting-started/)
- [ESPHome Web USB installer](https://web.esphome.io/)
- [Espressif generic browser flasher](https://espressif.github.io/esptool-js/)
