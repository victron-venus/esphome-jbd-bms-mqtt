# JBD battery monitoring without Victron or Cerbo GX

The maintained ESP32 profiles work with an ordinary MQTT broker. No Victron
inverter, Cerbo GX, Venus OS, VRM account, or `dbus-mqtt-battery` service is needed
for battery and individual-cell monitoring in Home Assistant.

```text
4 × JBD BMS ── BLE ── ESP32 ── Wi-Fi/MQTT ── MQTT broker ── Home Assistant
                                            └──────────── other MQTT consumers
```

The broker can be Mosquitto on Home Assistant OS, or a broker on a separate
server, NAS, or Raspberry Pi. Point the monitor and Home Assistant at the same
broker. Home Assistant does not need Bluetooth access to the batteries.

## Choose the matching profile

Use `jbd-all-batteries1.yaml` for the first monitor and
`jbd-all-batteries2.yaml` for the second. Each maintained profile polls four BMS
and records four cell voltages per BMS: two monitors expose eight batteries and
32 individual cells. The repository's `jbd-all-batteries.yaml` is an archived
eight-BMS profile, not the recommended starting point.

The current polling, aggregate sensors, and C++ telemetry collector require all
four BMS and their four cells. A single BMS or a different cell count is not a
configuration switch: adapt those parts together before using a different
layout. The aggregate voltage/current calculations assume a series chain;
parallel or unrelated batteries need different aggregate calculations. Individual
BMS measurements are still the source for each battery's own display.

Copy the selected profile, `components/battery_telemetry.h`, and
`packages/mqtt-availability.yaml` to the device's private configuration directory,
keeping those relative paths. Copy `secrets.example.yaml` to `secrets.yaml`,
replace its null values, and follow [firmware management access](firmware-access.md)
for the API key, recovery Wi-Fi password, and encrypted OTA procedure.

Set the four `ble_client` MAC addresses to your BMS addresses. Keep device names
unique. Replace the installation-specific `wifi.domain` with your local domain
(or remove it to use ESPHome's default); using the ESP32's IP address avoids local
name-resolution dependencies. The checked-in ESP32 settings require silicon
revision 3.1 or newer; verify your board and compiler before building.

## Configure your MQTT broker

Edit the existing `mqtt` block in your **private copy**. For an existing Chain 1
installation, preserve its discovery identity and polling reconnect hook while
adding your broker settings:

```yaml
mqtt:
  broker: !secret mqtt_broker
  port: 1883
  username: !secret mqtt_username
  password: !secret mqtt_password
  topic_prefix: battery
  reboot_timeout: 0s
  discovery: true
  discovery_prefix: homeassistant
  # Preserve the repository's existing Chain 1 Home Assistant identity.
  discovery_unique_id_generator: legacy
  on_connect:
    - script.execute: poll_all_bms
```

For a **new installation with no existing Home Assistant entities or history**,
use MAC-based discovery IDs on every monitor instead. Change this one setting
inside the existing `mqtt` block:

```yaml
# New installation only; this is a fragment of the mqtt block above.
discovery_unique_id_generator: mac
```

The maintained Chain 2 profile already uses `mac`; preserve that setting for
existing Chain 2 installations as well.

Add `mqtt_broker`, `mqtt_username`, and `mqtt_password` to `secrets.yaml`; they
are additional keys, not replacements for the Wi-Fi/API secrets. Configure a
broker account allowed to publish the monitor's state, availability, and discovery
messages and access the subscriptions required by ESPHome. Use Home Assistant's
broker credentials in its MQTT integration; never put credentials in dashboard
cards or commit them with the configuration.

The example uses the profiles' existing plaintext MQTT port. API/OTA encryption
does not encrypt MQTT; keep the broker on a trusted network. If using a TLS
listener, configure the port and CA verification together as documented by
[ESPHome MQTT](https://esphome.io/components/mqtt/#tls-esp32).

For Chain 2 use `topic_prefix: battery2`. Keep the availability package import
with `status_topic: battery2/status` and the script's explicit
`topic: battery2/telemetry`; Chain 1 uses `battery/status` and `battery/telemetry`.
Changing only `topic_prefix` does not rename these explicit topics. The default
prefixes are simplest to retain, even without a Victron system.

Both maintained profiles already set `wifi.reboot_timeout`,
`mqtt.reboot_timeout`, and `api.reboot_timeout` to `0s`, so acquisition continues
through network/broker/API-client absence. Preserve all three settings. In
particular, a MQTT-only installation must not reboot periodically just because
no native API client is connected. See [ESPHome API configuration](https://esphome.io/components/api/#configuration-variables).

Validate the resulting private configuration before compiling or provisioning:

```sh
esphome config jbd-all-batteries1.yaml
esphome compile jbd-all-batteries1.yaml
```

Use the [documented compiler requirements](firmware-access.md) and the existing
device's installation/migration procedure. Validation and compilation alone do
not upload firmware.

## Add Home Assistant through MQTT discovery

In **Settings → Devices & services → Add integration → MQTT**, enter the same
broker endpoint and suitable credentials. Keep MQTT discovery enabled with the
`homeassistant` prefix. See the [Home Assistant MQTT integration](https://www.home-assistant.io/integrations/mqtt/)
for broker setup and its topic-listening tool.

The profiles use ESPHome's MQTT entity discovery, enabled by default. Expect one
monitor's device entries to expose voltage, current, power, SOC, remaining
capacity, cycle count, temperature 1, four cell voltages per BMS, charging and
discharging permission, balancing, and online states. Sensor names repeat on the
second monitor; actual HA entity IDs depend on the device/entity registry and any
past renames. Copy IDs from **Settings → Devices & services → Entities** rather
than guessing them from the MQTT topic.

Chain 1 intentionally retains `discovery_unique_id_generator: legacy` in the
repository to preserve existing entity IDs and history. Chain 2 uses `mac`.
For a new installation with no existing registry history, use `mac` for every
monitor. For existing installations preserve the chain that owns the legacy IDs;
different topic prefixes alone cannot prevent discovery ID collisions. See
[the repository's discovery migration notes](../README.md#mqtt-discovery-identity-when-using-both-chains)
and [ESPHome discovery settings](https://esphome.io/components/mqtt/#configuration-variables).

If Home Assistant already uses a different broker, either connect the monitors
to it or bridge the required state, status, discovery, and telemetry topics.
Discovery alone cannot transport measurements. No Cerbo is needed for either
arrangement; any existing Victron consumers must also be considered before
moving a live monitor to another broker.

## Battery and cell mapping

Each monitor numbers its local BMS **1–4**. Chain 2 does not publish topic names
ending in `bms5` through `bms8`: identify a battery by both its chain prefix and
its local BMS number. For example, physical battery 5 is local BMS 1 on Chain 2.

```text
battery/sensor/voltage_bms1/state           Chain 1 · battery 1 · voltage (V)
battery/sensor/current_bms1/state           Chain 1 · battery 1 · current (A)
battery/sensor/power_bms1/state             Chain 1 · battery 1 · power (W)
battery/sensor/soc_bms1/state               Chain 1 · battery 1 · SOC (%)
battery/sensor/temperature1_bms1/state      Chain 1 · battery 1 · temperature (°C)
battery/sensor/capacity_remaining_bms1/state Chain 1 · battery 1 · remaining Ah
battery/sensor/cycles_bms1/state            Chain 1 · battery 1 · cycles
battery/sensor/voltage_cell1_bms1/state     Chain 1 · battery 1 · cell 1 (V)
battery/sensor/voltage_cell4_bms4/state     Chain 1 · battery 4 · cell 4 (V)
battery2/sensor/voltage_cell1_bms1/state    Chain 2 · battery 5 · cell 1 (V)
battery2/sensor/voltage_cell4_bms4/state    Chain 2 · battery 8 · cell 4 (V)
```

For a battery card, select SOC, battery voltage/current/power, temperature, and
the four matching cell entities from the **same monitor and BMS**. Cell spread
is `(maximum cell voltage − minimum cell voltage) × 1000` in mV; calculate it
only when all four cells are valid and fresh. Show unavailable readings as
unknown, never as 0 V or an empty battery. The `charging_bmsN` and
`discharging_bmsN` binary sensors report MOS permissions, not proof that current
is flowing in either direction.

## Optional battery and cell card

The companion [ha-jbd-bms-card](https://github.com/ha-homelab/ha-jbd-bms-card)
provides a reusable Lovelace display for battery summaries and individual cell
voltages. Follow its installation and configuration instructions, then map each
battery to the actual SOC, voltage, current, power, temperature, and cell entity
IDs in your Home Assistant registry. It can use your standalone MQTT/API sensor
entities without a Victron inverter, Venus OS, or Cerbo GX.

Check each entity's device and MQTT state topic before assigning it to a chain;
renamed entities and historical discovery collisions can leave misleading entity
names. Preserve those IDs to retain history and give the card readable battery
labels. The card's entity mapping does not change firmware topics or discovery
identities, and the freshness requirements below still apply to its source data.

## Alternative: Home Assistant's encrypted ESPHome API

The maintained profiles also expose the encrypted native API. Add the
**ESPHome integration** with the monitor's address and its private
`api_encryption_key` to receive sensor entities directly. This does not require
Venus OS or the MQTT-to-D-Bus bridge. See [Home Assistant ESPHome setup](https://www.home-assistant.io/integrations/esphome/).

Choose one entity path for each dashboard to avoid displaying duplicate MQTT
and API copies of the same measurement. In a new API-based HA installation you
can set `mqtt.discovery: false` while retaining MQTT publication for other
consumers. Existing retained discovery records may remain, so changing this
flag alone is not an entity migration procedure.

The firmware is still an MQTT publisher: its availability package and polling
script contain MQTT actions. Removing `mqtt` or its package is not a supported
API-only switch. Keeping `api` also supplies the key inherited by encrypted OTA;
do not remove it merely because Home Assistant uses MQTT. Native API sensor
updates do not expose the atomic MQTT snapshot contract by themselves.

## Verify readings and freshness

Use the MQTT integration's topic listener or a read-only MQTT subscriber on your
broker to check `battery/#` and, if used, `battery2/#`:

1. Verify the expected monitor identities and actual HA entity-to-battery mapping.
2. Observe new values on all four cells for each BMS, not just retained values
   delivered when the subscriber connects.
3. Observe fresh, non-retained `battery/telemetry` / `battery2/telemetry` JSON
   messages with advancing `seq`, the current `boot_id`, and complete battery
   entries. With all configured BMS replying, `ready` becomes `true` and the
   top-level `valid_mask` is `15`.
4. Distinguish broker connection from battery readiness: `battery/status: online`
   means that the ESP32 has MQTT connectivity. It does not prove that BLE replies
   or cell measurements are fresh.

Individual retained sensor topics can contain readings from an earlier session.
For freshness-sensitive dashboards, alerts, or other consumers use the
[atomic telemetry contract](battery-telemetry.md): require valid fields, preserve
measurement age, reject retained/replayed snapshots, and expire the last valid
sample when new messages stop. Account for each entry's `age_ms` at receipt;
receiving a partial message must not renew an old sample's freshness deadline.
A cold consumer waits for a complete frame. A new `boot_id` cannot establish
readiness from partial data, and transport `online` must never replace these checks.

The snapshots are collected over a polling round, not simultaneous physical
measurements; JBD replies have no measurement timestamps. A monitoring card
shows telemetry and does not replace the BMS's own protections.
