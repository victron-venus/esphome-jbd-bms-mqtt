// Exercise the production collector without ESPHome, BLE, MQTT or hardware.
#include "components/battery_telemetry.h"

#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

namespace {
using battery_telemetry::Field;
using battery_telemetry::Snapshot;

class Input {
 public:
  Input(const uint8_t *data, size_t size) : data_(data), size_(size) {}
  bool remaining() const { return offset_ < size_; }
  uint32_t number(unsigned bytes) {
    uint32_t value = 0;
    for (unsigned i = 0; i < bytes && remaining(); ++i)
      value |= static_cast<uint32_t>(data_[offset_++]) << (8 * i);
    return value;
  }
  float measurement() {
    const uint32_t bits = number(4);
    float value;
    static_assert(sizeof(value) == sizeof(bits), "Requires IEEE-sized floats");
    std::memcpy(&value, &bits, sizeof(value));
    return value;
  }

 private:
  const uint8_t *data_;
  size_t size_;
  size_t offset_{0};
};

bool equal_measurement(float left, float right) {
  return left == right || (std::isnan(left) && std::isnan(right));
}

void check_values(const Snapshot &snapshot, unsigned index) {
  assert((snapshot.valid_fields_mask(index) & ~snapshot.seen_mask(index)) == 0);
  for (unsigned f = 0; f < battery_telemetry::FIELD_COUNT; ++f) {
    const auto field = static_cast<Field>(f);
    const float value = snapshot.value(index, field);
    if (std::isnan(value)) continue;
    assert(std::isfinite(value));
    if (field == battery_telemetry::SOC) assert(value >= 0 && value <= 100);
    if (field == battery_telemetry::STATUS)
      assert(value >= 0 && value <= 255 && std::floor(value) == value);
    if (field == battery_telemetry::VOLTAGE ||
        (field >= battery_telemetry::CELL1 && field <= battery_telemetry::CELL4))
      assert(value > 0);
    if (field == battery_telemetry::CAPACITY || field == battery_telemetry::CYCLES)
      assert(value >= 0);
  }
}

void fill_complete(Snapshot &snapshot, unsigned index, uint32_t now) {
  constexpr float values[] = {13.2f, -2.0f, 0.0f, 20.0f, 3.3f, 3.3f, 3.3f, 3.3f, 2.0f};
  snapshot.begin_sample(index);
  for (unsigned field = 0; field <= battery_telemetry::STATUS; ++field)
    snapshot.record(index, static_cast<Field>(field), values[field], now);
  assert(snapshot.sample_ready(index, now));
  assert(snapshot.sample_ready(index, now + Snapshot::MAX_AGE_MS - 1));
  assert(!snapshot.sample_ready(index, now + Snapshot::MAX_AGE_MS));
  assert(snapshot.age_ms(index, now) == 0);
}
}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  Input input(data, size);
  Snapshot snapshot;
  bool collecting[4]{};
  uint32_t sequence = 0;
  snapshot.begin_session(input.number(4), input.number(4));
  uint32_t now = input.number(4);
  assert(!snapshot.ready(now));

  // Indices and fields are caller-controlled constants in the firmware. Only
  // model valid callback identities; arbitrary measurements and timing cross
  // the external boundary. Limit work independently of the libFuzzer budget.
  for (unsigned step = 0; input.remaining() && step < 128; ++step) {
    const auto operation = input.number(1) % 6;
    const auto index = input.number(1) % 4;
    const auto field = static_cast<Field>(input.number(1) % battery_telemetry::FIELD_COUNT);
    const float value = input.measurement();
    now += input.number(2);
    if (operation == 0) {
      snapshot.begin_round();
      for (auto &active : collecting) active = false;
      assert(!snapshot.ready(now));
    } else if (operation == 1) {
      snapshot.begin_sample(index);
      collecting[index] = true;
      assert(snapshot.seen_mask(index) == 0);
      assert(snapshot.valid_fields_mask(index) == 0);
      assert(!snapshot.sample_ready(index, now));
    } else if (operation == 2) {
      const auto before = snapshot;
      snapshot.record(index, field, value, now);
      if (!collecting[index]) {
        // Late callbacks cannot alter a closed observation window.
        assert(snapshot.seen_mask(index) == before.seen_mask(index));
        assert(snapshot.valid_fields_mask(index) == before.valid_fields_mask(index));
        assert(snapshot.age_ms(index, now) == before.age_ms(index, now));
        assert(equal_measurement(snapshot.value(index, field), before.value(index, field)));
      } else if (!std::isfinite(value)) {
        assert(std::isnan(snapshot.value(index, field)));
      }
      // A callback for one BMS cannot change evidence for another BMS.
      for (unsigned other = 0; other < 4; ++other) {
        if (other == index) continue;
        assert(snapshot.seen_mask(other) == before.seen_mask(other));
        assert(snapshot.valid_fields_mask(other) == before.valid_fields_mask(other));
        assert(snapshot.age_ms(other, now) == before.age_ms(other, now));
      }
      if (field > battery_telemetry::STATUS) {
        assert(snapshot.sample_ready(index, now) == before.sample_ready(index, now));
        assert(snapshot.age_ms(index, now) == before.age_ms(index, now));
      }
    } else if (operation == 3) {
      snapshot.end_sample(index);
      collecting[index] = false;
    } else if (operation == 4) {
      fill_complete(snapshot, index, now);
      collecting[index] = true;
    } else {
      snapshot.begin_session(input.number(4), input.number(4));
      sequence = 0;
      for (auto &active : collecting) active = false;
      assert(!snapshot.ready(now));
    }
    assert(std::strlen(snapshot.boot_id()) == 16);
    assert(snapshot.next_sequence() == ++sequence);
    for (unsigned bms = 0; bms < 4; ++bms) check_values(snapshot, bms);
    assert(snapshot.valid_mask(now) <= 15);
    assert(snapshot.ready(now) == (snapshot.valid_mask(now) == 15));
  }
  return 0;
}

#ifdef FUZZ_REPLAY_MAIN
int main(int argc, char **argv) {
  for (int i = 1; i < argc; ++i) {
    std::ifstream stream(argv[i], std::ios::binary);
    assert(stream.good());
    const std::vector<uint8_t> data{std::istreambuf_iterator<char>(stream), {}};
    assert(data.size() <= 4096);
    LLVMFuzzerTestOneInput(data.data(), data.size());
  }
}
#endif
