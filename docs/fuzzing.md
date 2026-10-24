# Battery telemetry fuzz assessment

The host-only libFuzzer target compiles the production
`components/battery_telemetry.h` collector directly. It exercises arbitrary
floating-point measurements, callback ordering, collection windows, session
resets, and unsigned millisecond rollover. AddressSanitizer and
UndefinedBehaviorSanitizer remain enabled throughout the campaign.

The target checks that closed windows reject late callbacks, one BMS cannot
change another BMS's evidence, incomplete or expired samples cannot become
ready, optional fields cannot change readiness, and accepted values stay in
their physical/protocol domains. It also exercises valid complete samples so
rejecting every observation would fail the target.

BMS indices and field identities remain within the firmware caller's documented
range; external measurement values and timing are unconstrained. The harness
does not fabricate invalid internal array indices to manufacture a finding.
Each input is limited to 128 operations, with a 4096-byte engine limit and a
90-second mutation budget. The shared runner provides network isolation,
process timeouts, and a 2048 MiB RSS bound.

## Cost and scope

The GitHub assessment is requested explicitly on the public default branch with
`channel=rc`. It does not run a mutation campaign on ordinary pushes, pull
requests, schedules, or beta builds. Ordinary CI compiles and replays the fixed
committed seeds under sanitizers through `tests/test_fuzz_replay.py`.

This project keeps its validation-only release policy. An assessment creates no
firmware tag, package, release, deployment, or hardware acceptance claim. The
existing ESPHome compile matrix and physical BLE/MQTT acceptance remain
separate requirements.

## Run and inspect

After a reviewed change reaches the default branch:

```sh
gh workflow run fuzz-candidate.yml --repo victron-venus/esphome-jbd-bms-mqtt --ref main -f channel=rc
```

The shared workflow retains `fuzz-candidate-<attempt>` for 90 days and
`fuzz-diagnostics-<attempt>` for 30 days. The candidate report records the source
commit, manifest hash, run/attempt, engine counts, and outcome. Its distinct
candidate schema cannot qualify a versioned software release.

Reproduce the deterministic corpus locally with:

```sh
python3 -m unittest discover -s tests -p test_fuzz_replay.py -v
```

A finding must be reproduced and minimized, fixed in production code, and
preserved as a regression input before a new assessment is accepted. Review
inputs before adding them to the public corpus; never commit credentials or
private device data.
