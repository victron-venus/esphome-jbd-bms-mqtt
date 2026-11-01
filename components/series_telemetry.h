#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#include <limits>

// Generated profiles opt into this collector. The deployed four-by-four
// profiles keep battery_telemetry.h and their existing schema/policies.
namespace series_telemetry {
enum Field : unsigned {
  VOLTAGE, CURRENT, SOC, TEMPERATURE, CELL1, CELL2, CELL3, CELL4,
  STATUS, CAPACITY, CYCLES, CELL_COUNT = 39, FIELD_COUNT = 40
};
constexpr unsigned cell_field(unsigned cell) {
  return cell < 4 ? CELL1 + cell : 11 + cell - 4;
}

class Snapshot {
 public:
  static constexpr unsigned MAX_MEMBERS = 4;
  static constexpr unsigned MAX_CELLS = 32;
  static constexpr uint32_t MAX_AGE_MS = 60000;

  // Invalid configuration disables readiness; it never truncates the inventory.
  bool configure(std::initializer_list<unsigned> counts) {
    members_ = 0;
    begin_round();
    if (counts.size() == 0 || counts.size() > MAX_MEMBERS) return false;
    for (unsigned count : counts)
      if (count == 0 || count > MAX_CELLS) return false;
    for (unsigned count : counts) cells_[members_++] = count;
    return true;
  }
  unsigned member_count() const { return members_; }
  unsigned cell_count(unsigned index) const { return index < members_ ? cells_[index] : 0; }
  unsigned schema() const {
    for (unsigned i = 0; i < members_; ++i) if (cells_[i] != 4) return 2;
    return 1;
  }
  void begin_session(uint32_t high, uint32_t low) {
    std::snprintf(boot_id_, sizeof(boot_id_), "%08lx%08lx",
                  static_cast<unsigned long>(high), static_cast<unsigned long>(low));
    sequence_ = 0;
    begin_round();
  }
  void begin_round() { samples_ = {}; }
  void begin_sample(unsigned index) {
    if (index >= members_) return;
    samples_[index] = {};
    samples_[index].collecting = true;
  }
  void end_sample(unsigned index) {
    if (index < members_) samples_[index].collecting = false;
  }
  void record(unsigned index, unsigned field, float value, uint32_t now) {
    if (index >= members_ || field >= FIELD_COUNT || !samples_[index].collecting) return;
    auto &sample = samples_[index];
    sample.values[field] = value;
    sample.times[field] = now;
    const uint64_t bit = uint64_t{1} << field;
    sample.seen |= bit;
    sample.valid &= ~bit;
    if (valid_value(field, value)) sample.valid |= bit;
  }
  uint64_t required_mask(unsigned index) const {
    if (index >= members_) return 0;
    uint64_t mask = 15 | (uint64_t{1} << STATUS);
    for (unsigned cell = 0; cell < cells_[index]; ++cell)
      mask |= uint64_t{1} << cell_field(cell);
    return mask;
  }
  uint64_t seen_mask(unsigned index) const {
    return index < members_ ? samples_[index].seen & required_mask(index) : 0;
  }
  uint64_t valid_fields_mask(unsigned index) const {
    return index < members_ ? samples_[index].valid & required_mask(index) : 0;
  }
  uint32_t observed_age_ms(unsigned index, uint32_t now) const {
    if (index >= members_) return MAX_AGE_MS;
    const uint64_t seen = seen_mask(index) | (samples_[index].seen & (uint64_t{1} << CELL_COUNT));
    if (seen == 0) return MAX_AGE_MS;
    uint32_t age = 0;
    for (unsigned field = 0; field < FIELD_COUNT; ++field)
      if (seen & (uint64_t{1} << field)) age = std::max(age, now - samples_[index].times[field]);
    return age;
  }
  uint32_t age_ms(unsigned index, uint32_t now) const {
    if (index >= members_ || seen_mask(index) != required_mask(index)
        || !std::isfinite(value(index, CELL_COUNT))) return MAX_AGE_MS;
    return observed_age_ms(index, now);
  }
  bool sample_ready(unsigned index, uint32_t now) const {
    return index < members_ && valid_fields_mask(index) == required_mask(index)
      && value(index, CELL_COUNT) == cells_[index]
      && age_ms(index, now) < MAX_AGE_MS;
  }
  unsigned valid_mask(uint32_t now) const {
    unsigned result = 0;
    for (unsigned i = 0; i < members_; ++i) if (sample_ready(i, now)) result |= 1U << i;
    return result;
  }
  bool ready(uint32_t now) const {
    return members_ != 0 && valid_mask(now) == (1U << members_) - 1;
  }
  float value(unsigned index, unsigned field) const {
    return index < members_ && field < FIELD_COUNT && (samples_[index].valid & (uint64_t{1} << field))
      ? samples_[index].values[field] : invalid();
  }
  bool permission(unsigned index, unsigned bit) const {
    const float status = value(index, STATUS);
    return std::isfinite(status) && (static_cast<unsigned>(status) & bit) != 0;
  }
  float voltage(uint32_t now) const { return sum(now, false); }
  float power(uint32_t now) const { return sum(now, true); }
  // A voltage-weighted BMS-current estimate, not a separate shunt measurement.
  float current(uint32_t now) const {
    const float volts = voltage(now);
    return std::isfinite(volts) && volts > 0 ? power(now) / volts : invalid();
  }
  float soc(uint32_t now) const { return minimum(SOC, now); }
  float capacity(uint32_t now) const { return minimum(CAPACITY, now); }
  const char *boot_id() const { return boot_id_; }
  uint32_t next_sequence() { return ++sequence_; }

 private:
  struct Sample {
    std::array<float, FIELD_COUNT> values{};
    std::array<uint32_t, FIELD_COUNT> times{};
    uint64_t seen{0}, valid{0};
    bool collecting{false};
  };
  static float invalid() { return std::numeric_limits<float>::quiet_NaN(); }
  static bool valid_value(unsigned field, float value) {
    if (!std::isfinite(value)) return false;
    if (field == CELL_COUNT) return value >= 1 && value <= MAX_CELLS && std::floor(value) == value;
    if (field == VOLTAGE || (field >= CELL1 && field <= CELL4) || field >= 11) return value > 0;
    if (field == SOC) return value >= 0 && value <= 100;
    if (field == STATUS) return value >= 0 && value <= 255 && std::floor(value) == value;
    if (field == CAPACITY || field == CYCLES) return value >= 0;
    return true;
  }
  float sum(uint32_t now, bool watts) const {
    if (!ready(now)) return invalid();
    float result = 0;
    for (unsigned i = 0; i < members_; ++i)
      result += value(i, VOLTAGE) * (watts ? value(i, CURRENT) : 1.0f);
    return std::isfinite(result) ? result : invalid();
  }
  float minimum(unsigned field, uint32_t now) const {
    if (!ready(now)) return invalid();
    float result = std::numeric_limits<float>::infinity();
    for (unsigned i = 0; i < members_; ++i) {
      const float measured = value(i, field);
      if (!std::isfinite(measured) || now - samples_[i].times[field] >= MAX_AGE_MS) return invalid();
      result = std::min(result, measured);
    }
    return result;
  }
  std::array<Sample, MAX_MEMBERS> samples_{};
  std::array<unsigned, MAX_MEMBERS> cells_{};
  unsigned members_{0};
  char boot_id_[17]{};
  uint32_t sequence_{0};
};

inline Snapshot &snapshot() {
  static Snapshot collector;
  return collector;
}
}  // namespace series_telemetry
