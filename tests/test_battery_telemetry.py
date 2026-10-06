"""Execute the firmware's actual collector through blackout/reconnect scenarios."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class TelemetryTests(unittest.TestCase):
    """Verify the shared collector and both producer configurations."""

    def test_current_round_completeness_freshness_and_sessions(self):
        """Execute completeness, invalid-value, expiry and session contracts in C++."""
        source = r"""
        #include "components/battery_telemetry.h"
        #include <cassert>
        #include <cstring>
        using namespace battery_telemetry;
        void fill(Snapshot &s, unsigned b, uint32_t now, int omit=-1) {
          s.begin_sample(b);
          const float values[] = {13.2f, -2.0f, 0.0f, 20.0f,
                                  3.3f, 3.3f, 3.3f, 3.3f, 2.0f};
          for (unsigned f=0; f<=STATUS; ++f)
            if (static_cast<int>(f)!=omit) s.record(b, static_cast<Field>(f), values[f], now);
        }
        int main() {
          Snapshot s;
          s.begin_session(0x1234, 0x5678);
          assert(!s.ready(0));
          assert(std::isnan(s.value(0,VOLTAGE)));
          assert(s.age_ms(0,0)==60000);
          assert(s.observed_age_ms(0,0)==60000);
          assert(s.seen_mask(0)==0 && s.valid_fields_mask(0)==0);
          assert(std::strcmp(s.boot_id(),"0000123400005678")==0);
          // One voltage and an MQTT connection never mean ready.
          s.begin_sample(0); s.record(0,VOLTAGE,13.2f,0);
          assert(!s.sample_ready(0,0));
          assert(s.seen_mask(0)==1 && s.valid_fields_mask(0)==1);
          assert(s.age_ms(0,30)==60000 && s.observed_age_ms(0,30)==30);
          // Every required field is independently necessary, including permissions.
          for (unsigned missing=0; missing<=STATUS; ++missing) {
            s.begin_round();
            for (unsigned b=0;b<4;++b) fill(s,b,100,b==2?missing:-1);
            assert(!s.ready(100));
          }
          s.begin_round();
          for(unsigned b=0;b<4;++b) { fill(s,b,100); s.end_sample(b); }
          assert(s.ready(100)); assert(s.valid_mask(100)==15);
          assert(s.seen_mask(0)==511 && s.valid_fields_mask(0)==511);
          assert(s.value(0,SOC)==0); // A real empty battery is valid evidence.
          assert(!s.permission(0,1)); assert(s.permission(0,2));
          assert(s.ready(60099)); assert(!s.ready(60100));
          // Late publications cannot mutate a frozen sample.
          s.record(0,VOLTAGE,0,101); assert(s.value(0,VOLTAGE)>0);
          assert(s.next_sequence()==1); assert(s.next_sequence()==2);
          // A reconnect restarts acquisition; cached complete samples cannot satisfy it.
          s.begin_round(); assert(!s.ready(200));
          fill(s,0,200); fill(s,1,200); fill(s,3,200);
          assert(!s.ready(200)); assert(s.next_sequence()==3);
          for(float invalid : {NAN, INFINITY, 0.0f, -1.0f}) {
            fill(s,2,200); s.record(2,CELL4,invalid,200);
            assert(!s.ready(200));
            assert(s.seen_mask(2)==511);
            assert(s.valid_fields_mask(2)==(511 & ~(1U<<CELL4)));
          }
          fill(s,2,200); s.record(2,STATUS,1.5f,200); assert(!s.ready(200));
          fill(s,2,200); s.record(2,SOC,101,200); assert(!s.ready(200));
          // Age uses oldest field, not the latest message; rollover is supported.
          s.begin_round(); fill(s,0,0xfffffff0U);
          assert(s.sample_ready(0,0x10)); assert(s.age_ms(0,0x10)==32);
          s.record(0,VOLTAGE,13.2f,0x10); assert(s.age_ms(0,0x10)==32);
          // Missing fields stay missing, observed fields carry their actual age.
          s.begin_round(); s.begin_sample(0);
          s.record(0,CELL1,2.1f,100); // Fresh low cell remains visible in a partial reply.
          s.record(0,TEMPERATURE,60.0f,110);
          s.record(0,STATUS,0.0f,120); // Explicit fresh veto is distinct from no status.
          assert(!s.ready(130)); assert(s.observed_age_ms(0,130)==30);
          assert(s.value(0,CELL1)==2.1f && s.value(0,TEMPERATURE)==60.0f);
          assert(std::isfinite(s.value(0,STATUS)) && !s.permission(0,1));
          assert(s.seen_mask(0)==((1U<<CELL1)|(1U<<TEMPERATURE)|(1U<<STATUS)));
          s.begin_sample(1); s.record(1,VOLTAGE,13.2f,120);
          assert(std::isnan(s.value(1,STATUS)));
          s.begin_session(1,2); assert(!s.ready(0)); assert(s.next_sequence()==1);
          assert(std::strcmp(s.boot_id(),"0000000100000002")==0);
        }
        """
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "test.cpp"
            binary = Path(directory) / "test"
            cpp.write_text(source)
            subprocess.run(
                [
                    compiler,
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT),
                    str(cpp),
                    "-o",
                    str(binary),
                ],
                check=True,
                timeout=30,
            )
            subprocess.run([str(binary)], check=True, timeout=5)

    def test_both_chains_wire_every_raw_measurement_and_only_publish_live(self):
        """Require matching field callbacks and live-only snapshots on both chains."""
        class Loader(yaml.SafeLoader):
            pass

        Loader.add_constructor("!secret", lambda loader, node: node.value)
        Loader.add_constructor(
            "!include", lambda loader, node: loader.construct_mapping(node, deep=True)
        )
        fields = (
            "total_voltage",
            "current",
            "state_of_charge",
            "temperature_1",
            "cell_voltage_1",
            "cell_voltage_2",
            "cell_voltage_3",
            "cell_voltage_4",
            "operation_status_bitmask",
        )
        for chain in (1, 2):
            config = yaml.load(
                (ROOT / f"jbd-all-batteries{chain}.yaml").read_text(), Loader=Loader
            )
            self.assertEqual(config["mqtt"]["reboot_timeout"], "0s")
            self.assertEqual(config["wifi"]["reboot_timeout"], "0s")
            boot = config["esphome"]["on_boot"]["then"]
            self.assertFalse(
                any("wait_until" in action or "delay" in action for action in boot)
            )
            self.assertEqual(
                config["mqtt"]["on_connect"], [{"script.execute": "poll_all_bms"}]
            )
            sensors = [
                sensor
                for sensor in config["sensor"]
                if sensor["platform"] == "jbd_bms_ble"
            ]
            self.assertEqual(len(sensors), 4)
            for index, sensor in enumerate(sensors):
                for field in fields:
                    callback = sensor[field]["on_raw_value"]["then"][0]["lambda"]
                    self.assertIn(f".record({index},", callback)
                    self.assertIn(f".sample_ready({index},", callback)
            actions = config["script"][0]["then"]
            publish = next(action["if"] for action in actions if "if" in action)
            self.assertEqual(publish["condition"], {"mqtt.connected": None})
            message = publish["then"][0]["mqtt.publish_json"]
            self.assertFalse(message["retain"])
            self.assertEqual(message["qos"], 0)
            for name in ("seen_mask", "valid_mask", "observed_age_ms"):
                self.assertIn(f'battery["{name}"]', message["payload"])
            self.assertIn('battery["charging"] = nullptr', message["payload"])
            self.assertIn('battery["discharging"] = nullptr', message["payload"])
            self.assertEqual(
                message["topic"], config["mqtt"]["topic_prefix"] + "/telemetry"
            )


if __name__ == "__main__":
    unittest.main()
