#!/usr/bin/env python3
"""Create a new private ESPHome project for one virtual series battery."""

# Preserve the documented operator-facing command name.
# pylint: disable=invalid-name
import argparse
import copy
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TELEMETRY_HEADER = "components/series_telemetry.h"
PROJECT_FILENAMES = frozenset(("series.yaml", "secrets.example.yaml", "topology.json", "series_telemetry.h"))


class Secret(str):
    """A secret key, never its value."""


class Loader(yaml.SafeLoader):
    """Read the maintained profile without resolving private files."""


class Dumper(yaml.SafeDumper):
    """Preserve secrets and readable multiline C++ lambdas."""


Loader.add_constructor("!secret", lambda loader, node: Secret(node.value))
Loader.add_constructor("!include", lambda loader, node: loader.construct_mapping(node, deep=True))
Dumper.add_representer(Secret, lambda dumper, value: dumper.represent_scalar("!secret", str(value)))
Dumper.add_representer(str, lambda dumper, value: dumper.represent_scalar(
    "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None))


def replace_strings(value, old, new):
    """Replace symbolic identifiers recursively, leaving typed YAML data intact."""
    if isinstance(value, dict):
        return {key: replace_strings(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_strings(item, old, new) for item in value]
    if isinstance(value, str):
        return type(value)(value.replace(old, new))
    return value


def parse_cells(value):
    """Accept one to four explicit member cell counts; never silently truncate."""
    if not re.fullmatch(r"\d+(?:,\d+){0,3}", value, flags=re.ASCII):
        raise argparse.ArgumentTypeError("Use 1–4 comma-separated cell counts, for example 4,4,4,4")
    counts = [int(count) for count in value.split(",")]
    if any(count < 1 or count > 32 for count in counts):
        raise argparse.ArgumentTypeError("Each member must contain 1–32 cells")
    return counts


def build_member_sensor(prototype, index, cell_count):
    """Replace one member's entire cell inventory without mutating an iteration."""
    member = replace_strings(copy.deepcopy(prototype), "bms1", f"bms{index + 1}")
    sensor = {key: value for key, value in member.items() if not key.startswith("cell_voltage_")}
    for item in sensor.values():
        if isinstance(item, dict) and "on_raw_value" in item:
            callback = item["on_raw_value"]["then"][0]["lambda"].splitlines()[0]
            item["on_raw_value"]["then"][0]["lambda"] = callback.replace(".record(0,", f".record({index},")
    for cell in range(cell_count):
        sensor[f"cell_voltage_{cell + 1}"] = {
            "name": f"voltage_cell{cell + 1}_bms{index + 1}",
            "on_raw_value": {"then": [{"lambda": f"series_telemetry::snapshot().record({index}, "
              f"series_telemetry::cell_field({cell}), x, millis());"}]}}
    sensor["cell_count"] = {"name": f"cell_count_bms{index + 1}", "on_raw_value": {"then": [{
        "lambda": f"series_telemetry::snapshot().record({index}, series_telemetry::CELL_COUNT, x, millis());"}]}}
    return sensor


def build_config(name, topic_prefix, counts):
    """Reuse pinned board/access settings while replacing the entire inventory."""
    config = yaml.load((ROOT / "jbd-all-batteries1.yaml").read_text(), Loader=Loader)
    config = replace_strings(config, "battery_telemetry::", "series_telemetry::")
    config["esphome"]["name"] = name
    config["esphome"]["friendly_name"] = name.replace("-", " ").title()
    config["esphome"]["includes"] = [TELEMETRY_HEADER]
    config["esphome"]["on_boot"]["then"] = [
        {"lambda": "series_telemetry::snapshot().configure({" + ", ".join(map(str, counts))
         + "}); series_telemetry::snapshot().begin_session(random_uint32(), random_uint32());"},
        {"script.execute": "poll_all_bms"},
    ]
    config["wifi"].pop("domain", None)
    config["wifi"]["ap"]["ssid"] = name
    availability = yaml.safe_load((ROOT / "packages/mqtt-availability.yaml").read_text())
    config["packages"] = {"mqtt_availability": replace_strings(
        availability, "${status_topic}", f"{topic_prefix}/status")}
    config["mqtt"].update(broker=Secret("mqtt_broker"), username=Secret("mqtt_username"),
                          password=Secret("mqtt_password"), topic_prefix=topic_prefix,
                          discovery_unique_id_generator="mac")
    config["esp32_ble"]["max_connections"] = len(counts)
    config["ble_client"] = [{"mac_address": Secret(f"bms{i}_mac"), "id": f"ble_bms{i}"}
                            for i in range(1, len(counts) + 1)]
    config["jbd_bms_ble"] = [{"id": f"bms{i}", "ble_client_id": f"ble_bms{i}", "update_interval": "never"}
                              for i in range(1, len(counts) + 1)]
    prototype = next(sensor for sensor in config["sensor"] if sensor["platform"] == "jbd_bms_ble")
    sensors = [sensor for sensor in config["sensor"] if sensor["platform"] not in ("jbd_bms_ble", "template")]
    for index, cell_count in enumerate(counts):
        sensors.append(build_member_sensor(prototype, index, cell_count))
    for metric, unit, decimals in (("voltage", "V", 2), ("power", "W", 1), ("current", "A", 2),
                                   ("soc", "%", 0), ("capacity", "Ah", 1)):
        sensors.append({"platform": "template", "name": f"{metric}_total", "id": f"series_{metric}",
                        "unit_of_measurement": unit, "accuracy_decimals": decimals, "update_interval": "never",
                        "lambda": f"return series_telemetry::snapshot().{metric}(millis());"})
    config["sensor"] = sensors
    binary = next(sensor for sensor in config["binary_sensor"] if sensor["platform"] == "jbd_bms_ble")
    config["binary_sensor"] = [replace_strings(copy.deepcopy(binary), "bms1", f"bms{i}")
                                for i in range(1, len(counts) + 1)] + [{"platform": "status", "name": "esp32_status"}]
    config.pop("globals", None)
    actions = [{"lambda": "series_telemetry::snapshot().begin_round();"}]
    for index in range(len(counts)):
        actions.extend([
            {"lambda": f"series_telemetry::snapshot().begin_sample({index}); id(bms{index + 1}).update();"},
            {"wait_until": {"condition": {"lambda": f"return series_telemetry::snapshot().sample_ready({index}, millis());"},
                            "timeout": "3s"}},
            {"lambda": f"series_telemetry::snapshot().end_sample({index});"},
        ])
    actions.append({"lambda": "\n".join(f"id(series_{metric}).update();"
                                        for metric in ("voltage", "power", "current", "soc", "capacity"))})
    publication = copy.deepcopy(next(action for action in config["script"][0]["then"] if "if" in action))
    message = publication["if"]["then"][0]["mqtt.publish_json"]
    message["topic"] = f"{topic_prefix}/telemetry"
    payload = message["payload"].replace('root["schema"] = 1;', 'root["schema"] = series_telemetry::snapshot().schema();')
    payload = payload.replace("i < 4", "i < series_telemetry::snapshot().member_count()")
    payload = payload.replace("cell < 4", "cell < series_telemetry::snapshot().cell_count(i)")
    payload = payload.replace("static_cast<series_telemetry::Field>(series_telemetry::CELL1 + cell)", "series_telemetry::cell_field(cell)")
    payload = payload.replace('battery["id"] = i + 1;', 'battery["id"] = i + 1;\n'
                              '  battery["cell_count"] = series_telemetry::snapshot().cell_count(i);\n'
                              '  const float reported_cells = series_telemetry::snapshot().value(i, series_telemetry::CELL_COUNT);\n'
                              '  if (std::isfinite(reported_cells)) battery["reported_cell_count"] = reported_cells;\n'
                              '  else battery["reported_cell_count"] = nullptr;\n'
                              '  battery["required_mask"] = series_telemetry::snapshot().required_mask(i);')
    message["payload"] = payload
    actions.extend([publication, {"delay": "100ms"}, {"script.execute": "poll_all_bms"}])
    config["script"] = [{"id": "poll_all_bms", "mode": "restart", "then": actions}]
    return config


def output_location(value):
    """Confine CLI destinations to home/temporary roots without resolving user links."""
    path = value.expanduser().absolute()
    if ".." in path.parts:
        raise ValueError("output cannot contain parent-directory traversal")
    roots = (Path.home(), Path(tempfile.gettempdir()), Path("/tmp"))
    for root in roots:
        canonical = root.resolve(strict=True)
        for alias in (root.absolute(), canonical):
            if not path.is_relative_to(alias):
                continue
            relative = path.relative_to(alias)
            output = canonical / relative
            if not relative.parts or output.is_relative_to(ROOT):
                raise ValueError("output must be a new directory outside the source checkout")
            return canonical, relative.parts
    raise ValueError("output must be inside your home directory or an operating-system temporary directory")


@contextmanager
def private_output_directory(value):
    """Pin each directory inode; reject symlinks and an already-existing final entry."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("private output creation requires POSIX directory-descriptor support (Linux/macOS)")
    root, parts = output_location(value)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(root, flags)
    try:
        for index, part in enumerate(parts):
            try:
                os.mkdir(part, mode=0o700, dir_fd=directory)
            except FileExistsError:
                if index == len(parts) - 1:
                    raise FileExistsError("output directory already exists; no files were overwritten") from None
            child = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = child
        yield root.joinpath(*parts), directory
    finally:
        os.close(directory)


def write_private_text(directory, filename, text):
    """Create one fixed project filename exclusively within the pinned directory."""
    if filename not in PROJECT_FILENAMES:
        raise ValueError("only fixed generated project filenames may be written")
    descriptor = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         mode=0o600, dir_fd=directory)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(text)


def project_texts(args, config):
    """Render all content before creating any private output directory."""
    secrets = yaml.safe_load((ROOT / "secrets.example.yaml").read_text())
    secrets.update(mqtt_broker="mqtt.example.invalid", mqtt_username="replace-me", mqtt_password="replace-me")
    for index in range(len(args.cells)):
        secrets[f"bms{index + 1}_mac"] = f"02:00:00:00:00:{index + 1:02X}"
    return {
        "series.yaml": "# Generated private series configuration; validate before compiling/flashing.\n"
                       + yaml.dump(config, Dumper=Dumper, sort_keys=False, width=110),
        "secrets.example.yaml": yaml.safe_dump(secrets, sort_keys=False),
        "topology.json": json.dumps({"name": args.name, "topic_prefix": args.topic_prefix,
            "connection": "series", "member_cell_counts": args.cells,
            "telemetry_schema": 1 if all(c == 4 for c in args.cells) else 2,
            "soc_policy": "minimum_member", "capacity_policy": "minimum_remaining_ah",
            "current_policy": "voltage_weighted_bms_estimate"}, indent=2) + "\n",
    }


def write_project(destination, contents):
    """Write fixed project files without following or overwriting directory entries."""
    header = (ROOT / TELEMETRY_HEADER).read_text(encoding="utf-8")
    with private_output_directory(destination) as (output, directory):
        os.mkdir("components", mode=0o700, dir_fd=directory)
        components = os.open("components", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        try:
            write_private_text(components, "series_telemetry.h", header)
        finally:
            os.close(components)
        for filename, text in contents.items():
            write_private_text(directory, filename, text)
        return output


def main():
    """Write a separate project, refusing existing paths or repository output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Unique ESPHome name, lowercase letters/digits/hyphens")
    parser.add_argument("--topic-prefix", required=True, help="Unique MQTT prefix for this collector")
    parser.add_argument("--cells", required=True, type=parse_cells, help="Physical member cell counts, e.g. 4,4,4,4 or 16")
    parser.add_argument("--output", required=True, type=Path,
                        help="New private project directory under home or OS temporary storage, outside this checkout")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", args.name):
        parser.error("name must start with a lowercase letter and contain at most 31 letters/digits/hyphens")
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", args.topic_prefix):
        parser.error("topic-prefix must contain nonempty letters/digits/underscore/hyphen segments")
    config = build_config(args.name, args.topic_prefix, args.cells)
    contents = project_texts(args, config)
    try:
        output = write_project(args.output, contents)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Created {output}/series.yaml; fill secrets.yaml, then run esphome config and esphome compile.")
    if any(count != 4 for count in args.cells):
        print("Schema 2: HA/standalone only; current dbus-mqtt-battery schema-1 decoder is incompatible.")


if __name__ == "__main__":
    main()
