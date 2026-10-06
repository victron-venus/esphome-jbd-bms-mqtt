# Battery telemetry during startup and reconnect

The two current four-BMS monitors collect battery measurements even while Wi-Fi
or the Cerbo MQTT broker is unavailable. Wi-Fi, MQTT and API disconnection do not
restart the ESP32. Hardware watchdogs still operate. The legacy eight-BMS example
has not been converted to this protocol.

Each completed polling round publishes one JSON object on `battery/telemetry` or
`battery2/telemetry`, with QoS 0 and `retain: false`. The old individual sensor
topics remain available for Home Assistant and older consumers. Their retained
values are not evidence that a battery has been measured in the current session.

The JSON contract is:

```json
{
  "schema": 1,
  "boot_id": "0123456789abcdef",
  "seq": 1,
  "ready": true,
  "valid_mask": 15,
  "batteries": [
    {
      "id": 1,
      "age_ms": 120,
      "observed_age_ms": 120,
      "seen_mask": 511,
      "valid_mask": 511,
      "voltage": 13.2,
      "current": -2.0,
      "soc": 50,
      "temperature": 20,
      "temperatures": [20],
      "cells": [3.3, 3.3, 3.3, 3.3],
      "charging": true,
      "discharging": true,
      "online": true,
      "capacity": 140,
      "cycles": 100
    }
  ]
}
```

The example abbreviates the array: every real message contains entries for BMS
IDs 1, 2, 3 and 4. `boot_id` is a random 64-bit session identifier, and `seq`
increases on every publication within that boot, including across reconnects.
`age_ms` is the time since the oldest required field callback, using the ESP32 monotonic clock.
There is no dependence on NTP or the Cerbo wall clock.

Each BMS must supply voltage, current, SOC, temperature, all four cell voltages
and the actual JBD MOS permission bits in the current polling round. The numeric
operation-status sensor is sampled on every reply so unchanged binary sensor
states cannot hide the absence of a new reply. Zero SOC and disabled charge or
discharge permission are valid measurements; missing measurements, nonfinite
values, nonpositive voltages, and SOC outside 0–100 are not.

The collection window establishes when ESPHome observed a reply. The upstream
JBD protocol supplies neither a measurement timestamp nor a request identifier;
BasicInfo and CellInfo are separate replies. Consequently, a delayed response
that arrives after the next window opens cannot be distinguished from a reply
to the latest request. The reported age does not include unknown time spent in
the BMS or BLE transport, and readiness does not assert a simultaneous or
request-correlated physical measurement. Callbacks arriving while a sample is
closed are ignored. Correlation or bounded transport draining would require a
separate upstream protocol/driver change and hardware validation.

`ready` requires all four BMS to be complete and younger than 60 seconds.
`valid_mask` reports which entries meet those rules. `online` means that this
entry contains a complete fresh BMS reply, not just that the ESP32 has MQTT.
Optional capacity and cycle measurements are included only when valid.
The current monitors expose only `temperature_1` per BMS: `temperature` is that
raw measurement, and `temperatures` contains the same single value (not an average).
Unavailable required numeric fields are JSON null, never invented zeroes.
Incomplete entries have age 60000, `online: false`, and make `ready: false`.
The last samples are frozen at the end of each BMS request; a new round discards
all previous evidence. Aggregate sensors publish NaN when the round is incomplete.

Each entry also exposes field evidence for consumers that tolerate a short lost
BLE reply after a complete snapshot. Bits 0–8 of `seen_mask` and `valid_mask`
correspond to voltage, current, SOC, temperature, cell 1–4 and MOS status. A seen
but invalid bit is explicit invalid data, not a missing reply. `observed_age_ms`
is the age of the oldest actually observed required field, or 60000 when none
arrived. Missing/invalid MOS status produces null charge/discharge permissions;
a received valid status produces real booleans even in an incomplete snapshot.

A consumer may preserve missing fields from its last complete snapshot only
within their original freshness limit. It must never refresh those timestamps
from this new partial message, admit initial/new-boot readiness from partial
data, or clear a protection veto without complete fresh evidence. Fresh partial
cell voltages, temperatures and disabled MOS permissions still constrain the
battery immediately. Explicit invalid fields must fail closed.
Across a producer reboot, previously validated readings may retain their original
expiry, but partial new-boot messages cannot renew any of those deadlines. A cold
consumer has no validated history and waits for a complete frame.

MQTT reconnect restarts the polling round before publishing a new snapshot.
There is no retained snapshot or replay of an earlier complete round. The
consumer must also reject retained/replayed messages, validate required fields,
and expire data when new snapshots stop arriving. MQTT `status: online` remains
a transport availability signal and must not be used as BMS readiness.

This prevents a communications gap from being represented as a measured empty
battery. It does not replace the BMS or inverter protections, and cannot keep a
Cerbo powered when its AC supply is switched off by the inverter.
