"""Validate generated inventories and execute the actual configurable collector."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("generate_series", ROOT / "scripts/generate-series-config.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class SeriesConfigTests(unittest.TestCase):
    """Keep generated radio inventory, callback evidence and publication aligned."""

    def test_inventory_matrix_and_no_installation_identifiers(self):
        for counts in ([4], [4, 4], [4, 4, 4], [4, 4, 4, 4], [1], [16], [32], [4, 8, 16, 32], [32, 32, 32, 32]):
            with self.subTest(counts=counts):
                config = GENERATOR.build_config("test-series", "test/series", counts)
                self.assertEqual(config["mqtt"]["discovery_unique_id_generator"], "mac")
                self.assertIsInstance(config["mqtt"]["broker"], GENERATOR.Secret)
                self.assertEqual(config["esp32_ble"]["max_connections"], len(counts))
                for component in ("ble_client", "jbd_bms_ble"):
                    self.assertEqual(len(config[component]), len(counts))
                sensors = [s for s in config["sensor"] if s["platform"] == "jbd_bms_ble"]
                self.assertEqual(len(sensors), len(counts))
                for index, count in enumerate(counts):
                    self.assertEqual(sensors[index]["jbd_bms_ble_id"], f"bms{index + 1}")
                    self.assertIn("series_telemetry::CELL_COUNT", sensors[index]["cell_count"]["on_raw_value"]["then"][0]["lambda"])
                    cells = [key for key in sensors[index] if key.startswith("cell_voltage_")]
                    self.assertEqual(len(cells), count)
                    for cell in range(count):
                        callback = sensors[index][f"cell_voltage_{cell + 1}"]["on_raw_value"]["then"][0]["lambda"]
                        self.assertIn(f".record({index}, series_telemetry::cell_field({cell})", callback)
                text = yaml.dump(config, Dumper=GENERATOR.Dumper)
                self.assertNotIn("A5:C2:", text)
                self.assertNotIn("192.168.", text)
                self.assertNotIn("alvit", text)
                self.assertNotIn("bms1_data_ready", text)
                self.assertNotIn("battery_telemetry::", text)
                self.assertNotIn(f"bms{len(counts) + 1}", text)
                actions = config["script"][0]["then"]
                publish = next(action["if"] for action in actions if "if" in action)
                message = publish["then"][0]["mqtt.publish_json"]
                self.assertEqual(message["topic"], "test/series/telemetry")
                self.assertFalse(message["retain"])
                self.assertIn(".member_count()", message["payload"])
                self.assertIn(".cell_count(i)", message["payload"])
                self.assertIn("series_telemetry::cell_field(cell)", message["payload"])
                self.assertEqual(config["wifi"]["reboot_timeout"], "0s")
                self.assertEqual(config["mqtt"]["on_connect"], [{"script.execute": "poll_all_bms"}])
                heartbeat = config["packages"]["mqtt_availability"]["interval"][0]
                self.assertEqual(heartbeat["interval"], "30s")

    def test_cli_creates_private_project_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project"
            command = [sys.executable, str(ROOT / "scripts/generate-series-config.py"), "--name", "test-series",
                       "--topic-prefix", "test/series", "--cells", "4,16", "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertTrue((output / "components/series_telemetry.h").is_file())
            self.assertFalse((output / "secrets.yaml").exists())
            config = yaml.load((output / "series.yaml").read_text(), Loader=GENERATOR.Loader)
            self.assertEqual(config["ble_client"][1]["mac_address"], "bms2_mac")
            self.assertEqual(json.loads((output / "topology.json").read_text())["telemetry_schema"], 2)
            original = (output / "series.yaml").read_bytes()
            result = subprocess.run(command, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((output / "series.yaml").read_bytes(), original)

    def test_invalid_topologies_and_identifiers_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            for option, invalid in (("--cells", "4,4,4,4,4"), ("--cells", "0"), ("--cells", "33"),
                                    ("--cells", "4,-1"), ("--name", "test;fail"), ("--topic-prefix", "battery/#")):
                output = Path(directory) / "project"
                command = [sys.executable, str(ROOT / "scripts/generate-series-config.py"), "--name", "test-series",
                           "--topic-prefix", "test/series", "--cells", "4", "--output", str(output)]
                command[command.index(option) + 1] = invalid
                result = subprocess.run(command, capture_output=True, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_actual_collector_under_sanitizers(self):
        source = r'''
        #include "components/series_telemetry.h"
        #include <cassert>
        #include <cstring>
        using namespace series_telemetry;
        void fill(Snapshot &s, unsigned b, uint32_t now, int omit=-1) {
          s.begin_sample(b);
          if (omit!=CELL_COUNT) s.record(b,CELL_COUNT,s.cell_count(b),now);
          for (unsigned f : {VOLTAGE, CURRENT, SOC, TEMPERATURE, STATUS, CAPACITY, CYCLES}) {
            const float v = f==VOLTAGE ? 3.2f*s.cell_count(b) : f==CURRENT ? -2.0f :
              f==SOC ? 75.0f-b : f==TEMPERATURE ? 20.0f : f==STATUS ? 3.0f : f==CAPACITY ? 100.0f-b : 20.0f;
            if (static_cast<int>(f)!=omit) s.record(b,f,v,now);
          }
          for (unsigned c=0;c<s.cell_count(b);++c)
            if (static_cast<int>(cell_field(c))!=omit) s.record(b,cell_field(c),3.2f,now);
        }
        void check(std::initializer_list<unsigned> counts) {
          Snapshot s;
          assert(!s.ready(0));
          assert(s.configure(counts)); s.begin_session(1,2);
          unsigned total_cells=0;
          for(unsigned b=0;b<s.member_count();++b) { fill(s,b,100); total_cells+=s.cell_count(b); }
          assert(s.ready(100)); assert(s.valid_mask(100)==(1U<<s.member_count())-1);
          assert(std::abs(s.voltage(100)-3.2f*total_cells)<0.001f);
          assert(std::abs(s.current(100)+2.0f)<0.001f); // Never sum series currents.
          assert(std::abs(s.power(100)+6.4f*total_cells)<0.001f);
          assert(s.soc(100)==76.0f-s.member_count());
          assert(s.capacity(100)==101.0f-s.member_count()); // Never sum series Ah.
          for(unsigned b=0;b<s.member_count();++b) {
            for(unsigned field=0;field<FIELD_COUNT;++field) {
              if (!(s.required_mask(b)&(uint64_t{1}<<field))) continue;
              fill(s,b,100,field); assert(!s.ready(100)); assert(std::isnan(s.voltage(100)));
              fill(s,b,100); s.record(b,field,NAN,100); assert(!s.ready(100));
              fill(s,b,100);
            }
          }
          fill(s,0,100,CELL_COUNT); assert(!s.ready(100)); assert(std::isnan(s.voltage(100)));
          fill(s,0,100); s.record(0,CELL_COUNT,s.cell_count(0)==32 ? 31 : 32,100);
          assert(!s.ready(100)); assert(std::isnan(s.voltage(100)));
          fill(s,0,100,CAPACITY); assert(s.ready(100)); assert(std::isnan(s.capacity(100)));
          fill(s,0,100); s.record(0,SOC,0,100); s.record(0,CAPACITY,0,100);
          assert(s.soc(100)==0 && s.capacity(100)==0); // Real empty pack must not be discarded.
          s.end_sample(0); s.record(0,VOLTAGE,0,101); assert(s.ready(101));
          assert(s.ready(60099)); assert(!s.ready(60100));
          s.begin_round(); assert(!s.ready(102)); assert(std::isnan(s.voltage(102)));
          for(unsigned b=0;b<s.member_count();++b) fill(s,b,0xfffffff0U);
          assert(s.ready(0x10)); assert(s.age_ms(0,0x10)==32);
          assert(s.next_sequence()==1); assert(s.next_sequence()==2);
          s.begin_session(3,4); assert(s.next_sequence()==1 && !s.ready(0));
          assert(std::strcmp(s.boot_id(),"0000000300000004")==0);
          s.record(999,999,1,0); s.begin_sample(999); s.end_sample(999);
          assert(!s.sample_ready(999,0)); assert(std::isnan(s.value(999,999)));
        }
        int main() {
          check({4}); check({4,4}); check({4,4,4}); check({4,4,4,4});
          check({1}); check({16}); check({32}); check({4,8,16,32}); check({32,32,32,32});
          Snapshot s; assert(!s.configure({})); assert(!s.configure({0}));
          assert(!s.configure({33})); assert(!s.configure({4,4,4,4,4})); assert(!s.ready(0));
          s.configure({4,4}); fill(s,0,100); fill(s,1,100);
          assert(s.schema()==1); assert(s.required_mask(0)==511);
          assert(s.seen_mask(0)==511 && s.valid_fields_mask(0)==511);
          s.record(1,VOLTAGE,25.6f,100); s.record(1,CURRENT,-4.0f,100);
          assert(std::abs(s.current(100)-(-10.0f/3.0f))<0.001f); // Label this estimate.
          s.configure({16}); fill(s,0,100); assert(s.schema()==2);
          s.record(0,cell_field(15),0,100); assert(!s.ready(100));
          assert(std::isnan(s.current(100))); assert(std::isnan(s.soc(100)));
        }
        '''
        compiler = shutil.which("c++")
        self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as directory:
            cpp, binary = Path(directory) / "test.cpp", Path(directory) / "test"
            cpp.write_text(source)
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                            "-fno-omit-frame-pointer", "-I", str(ROOT), str(cpp), "-o", str(binary)],
                           check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
