#pragma once

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>

// Separate current-round evidence from ESPHome entities, whose last state can
// survive a missing BLE reply. No clock synchronization or retained MQTT needed.
namespace battery_telemetry {
enum Field : uint8_t {
  VOLTAGE, CURRENT, SOC, TEMPERATURE, CELL1, CELL2, CELL3, CELL4,
  STATUS, CAPACITY, CYCLES, FIELD_COUNT
};

class Snapshot {
 public:
  static constexpr uint32_t MAX_AGE_MS = 60000;
  static constexpr uint16_t REQUIRED = (1U << (STATUS + 1)) - 1;

  void begin_session(uint32_t high, uint32_t low) {
    std::snprintf(boot_id_, sizeof(boot_id_), "%08lx%08lx",
                  static_cast<unsigned long>(high), static_cast<unsigned long>(low));
    sequence_ = 0;
    begin_round();
  }
  void begin_round() { samples_ = {}; }
  void begin_sample(unsigned index) {
    samples_[index] = {};
    samples_[index].collecting = true;
  }
  void end_sample(unsigned index) { samples_[index].collecting = false; }

  void record(unsigned index, Field field, float value, uint32_t now) {
    auto &sample = samples_[index];
    if (!sample.collecting) return;
    sample.values[field] = value;
    sample.times[field] = now;
    const uint16_t bit = 1U << field;
    sample.seen |= bit;
    sample.valid &= ~bit;
    if (valid_value(field, value)) sample.valid |= bit;
  }

  bool sample_ready(unsigned index, uint32_t now) const {
    const auto &sample = samples_[index];
    return (sample.valid & REQUIRED) == REQUIRED && age_ms(index, now) < MAX_AGE_MS;
  }
  bool ready(uint32_t now) const { return valid_mask(now) == 15; }
  unsigned valid_mask(uint32_t now) const {
    unsigned result = 0;
    for (unsigned i = 0; i < samples_.size(); ++i)
      if (sample_ready(i, now)) result |= 1U << i;
    return result;
  }
  uint32_t age_ms(unsigned index, uint32_t now) const {
    const auto &sample = samples_[index];
    if ((sample.seen & REQUIRED) != REQUIRED) return MAX_AGE_MS;
    return observed_age_ms(index, now);
  }
  uint16_t seen_mask(unsigned index) const { return samples_[index].seen & REQUIRED; }
  uint16_t valid_fields_mask(unsigned index) const { return samples_[index].valid & REQUIRED; }
  uint32_t observed_age_ms(unsigned index, uint32_t now) const {
    const auto &sample = samples_[index];
    if (seen_mask(index) == 0) return MAX_AGE_MS;
    uint32_t age = 0;
    for (unsigned field = 0; field <= STATUS; ++field) {
      if ((sample.seen & (1U << field)) == 0) continue;
      // Unsigned subtraction handles the millis() rollover.
      const uint32_t field_age = now - sample.times[field];
      if (field_age > age) age = field_age;
    }
    return age;
  }
  float value(unsigned index, Field field) const {
    return (samples_[index].valid & (1U << field))
      ? samples_[index].values[field] : std::numeric_limits<float>::quiet_NaN();
  }
  bool permission(unsigned index, unsigned bit) const {
    const float status = value(index, STATUS);
    return std::isfinite(status) && (static_cast<unsigned>(status) & bit) != 0;
  }
  const char *boot_id() const { return boot_id_; }
  uint32_t next_sequence() { return ++sequence_; }

 private:
  struct Sample {
    std::array<float, FIELD_COUNT> values{};
    std::array<uint32_t, FIELD_COUNT> times{};
    uint16_t seen{0};
    uint16_t valid{0};
    bool collecting{false};
  };
  static bool valid_value(Field field, float value) {
    if (!std::isfinite(value)) return false;
    if (field == VOLTAGE || (field >= CELL1 && field <= CELL4)) return value > 0;
    if (field == SOC) return value >= 0 && value <= 100;
    if (field == STATUS) return value >= 0 && value <= 255 && std::floor(value) == value;
    if (field == CAPACITY || field == CYCLES) return value >= 0;
    return true;
  }
  std::array<Sample, 4> samples_{};
  char boot_id_[17]{};
  uint32_t sequence_{0};
};

// ESPHome emits user includes after its globals declarations. Keep the custom
// type out of generated globals, and access this single collector from lambdas.
inline Snapshot &snapshot() {
  static Snapshot collector;
  return collector;
}
}  // namespace battery_telemetry
