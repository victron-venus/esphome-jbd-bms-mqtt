# Firmware management access

The three repository profiles require a private native API key and encrypted
native OTA. They no longer enable the HTTP web server or captive portal: those
interfaces exposed controls and a separate plaintext firmware upload route.
The fallback Wi-Fi AP remains available with its own password; connect to it for
encrypted API/OTA access, not a browser configuration page. Sensor acquisition,
BLE selection, MQTT topics and polling are unchanged.

These profiles require ESPHome's encrypted OTA support (2026.9.0 or newer). The
actual CI compiler remains the pinned **2026.10.0b1 prerelease** described in
[CI_WORKFLOW.md](CI_WORKFLOW.md). That Linux build is not a recommendation to
upgrade a live device to a prerelease. Review compiler/device compatibility and
the existing configuration before any separately authorized installation.

## Private configuration

Before updating an existing checkout, back up its configuration and secrets
outside Git. The former tracked `secrets.yaml` placeholder is replaced with
`secrets.example.yaml`; never put real credentials in that tracked template.
In a private configuration directory for each device, copy the relevant YAML,
`components/battery_telemetry.h` and `packages/mqtt-availability.yaml`, preserving
relative paths. Copy the example to `secrets.yaml`, set permissions with
`chmod 600 secrets.yaml`, and replace every null value.

- `wifi_ssid` and `wifi_pass`: the existing Wi-Fi network credentials.
- `fallback_ap_password`: a strong, unique password for this device's recovery
  AP, different from the Wi-Fi network password.
- `api_encryption_key`: this device's existing API key when it already has one,
  or a newly generated key for a new device/initial migration.

Do not set the recovery-AP password to an empty string: ESPHome treats that as
an explicitly open Wi-Fi AP. The template's null is intentionally incomplete.

Generate a new key from 32 operating-system random bytes:

```sh
python3 -c 'import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())'
```

Generate an independent recovery-AP password, for example:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(24))'
```

Use distinct credentials for each monitor; do not share the example or CI
credentials. Retain each device's name, discovery IDs, BLE addresses and existing
telemetry settings. In particular, a deployed four-BMS file historically named
`jbd-all-batteries.yaml` must not be replaced with the repository's eight-BMS
legacy configuration. Configure Home Assistant/API clients with the same API key.

The API and native OTA deliberately share the key. `ota.encryption: {}` inherits
the API key and requires encryption; there is no OTA password or plaintext
fallback in the final profile. Missing/invalid keys fail configuration validation.
Protect both `secrets.yaml` and compiled firmware, which embeds these credentials.
Git ignores local secrets and `.esphome` builds, but cannot prevent force-adding
them. CI generates temporary credentials, checks the compiled feature flags and
deletes its temporary firmware; CI output is never a deployment image.

## Existing device migration

Prefer serial provisioning of the final secure profile after preparing a backup
and recovery procedure. The HTTP page, browser restart controls, web OTA and
captive portal disappear after installation. Use `esphome logs` with the API key
for diagnostics and native encrypted OTA for subsequent updates.

An old device cannot receive an encrypted update merely because the new YAML
requires it. Where serial access is unavailable, ESPHome documents a
[two-stage migration](https://esphome.io/components/ota/esphome/#enabling-encryption-on-an-existing-device):

1. In a **separate local bridge configuration**, add/preserve the API encryption
   key but temporarily omit `ota.encryption`. Preserve the installed OTA password
   if there is one; do not invent a replacement password for the old firmware.
   Keep HTTP/captive components disabled. Build with a compatible ESPHome version
   supporting this migration and install through the reviewed device procedure.
   The first upload can be plaintext and expose all embedded secrets. Use only a
   controlled trusted network; this bridge is not the final secure profile.
   Verify the actual device reports `Encryption: offered, plaintext accepted`.
2. Keep exactly the same API key, restore the final `ota.encryption: {}` and remove
   any legacy OTA password. Install and verify `Encryption: required` on the
   actual device before considering migration complete.

The tested 2026.10.0b1 CLI supports this bridge sequence. Do not add
`allow_plaintext_upload` to the final configuration to bypass a failed handshake.
This profile does not support changing the encryption key over OTA: use serial
reprovisioning if it is lost, compromised or must be replaced. An old plaintext
rollback image can also restore insecure access, so treat rollback as an explicit
security decision rather than an automatic recovery step.

## Scope and verification

The native API/OTA checks do not encrypt MQTT, the BMS Bluetooth link or all Wi-Fi
traffic. MQTT still uses the existing plaintext broker/port and needs a trusted,
segmented network and broker access controls. Do not expose device or broker ports
to the internet. A successful build does not establish deployed key randomness,
physical RNG health, electrical safety or correct readings on a particular BMS.

See the upstream [native API](https://esphome.io/components/api/),
[OTA](https://esphome.io/components/ota/esphome/) and
[web-server security](https://esphome.io/components/web_server/) documentation.
