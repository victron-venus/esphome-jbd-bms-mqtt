# Source delivery and upstream updates

The April 2026 v1.4.0 release remains a historical version. Current reviewed source
is delivered by immutable Git commit SHA under the validation-only policy; CI
does not publish or install firmware. Record the exact source, ESPHome compiler,
external-component commit and private configuration for a local firmware build.
Consult [CHANGELOG.md](../CHANGELOG.md) for change and upgrade guidance.

The supported CI compiler is the locked Linux ESPHome **2026.10.0b1 prerelease**.
The README badge identifies that tested version, not a stable-release promise.
Do not use the obsolete 2024.x compiler for the current encrypted-OTA profiles.
Review actual device compatibility before any separately authorized upgrade.

The JBD component is pinned to upstream
[70831773385cfa803a543d87f4ca9e65a2f8415a](https://github.com/syssi/esphome-jbd-bms/commit/70831773385cfa803a543d87f4ca9e65a2f8415a).
That revision fixes the authentication-timeout uint32 formatting with `%lu` and
an explicit unsigned-long cast. Intermediate upstream changes fix BLE frame
assembly and update recent ESPHome log/format/schema interfaces. No compiler
warning is suppressed. The pin must pass all three firmware compiles and host
regressions before acceptance. Upstream licensing and notices remain applicable.

Tests execute the real battery collector with AddressSanitizer and
UndefinedBehaviorSanitizer and run the Clang static analyzer. Formula lambdas
also have host regression tests. These checks cover maintained code paths; they
do not establish all third-party firmware behavior or physical-device safety.
