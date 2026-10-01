"""Execute the shared YAML's small automation subset against MQTT failure cases."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).parents[1]


def actions(items, connected, published):
    """Unsupported new actions must get explicit test semantics, never pass silently."""
    for action in items:
        if set(action) == {"if"}:
            rule = action["if"]
            if rule["condition"] != {"mqtt.connected": None}:
                raise AssertionError("Availability must use the publisher connection")
            if connected:
                actions(rule["then"], connected, published)
        elif set(action) == {"mqtt.publish"}:
            published.append(action["mqtt.publish"])
        else:
            raise AssertionError(f"Uncovered action: {list(action)}")


class AvailabilityTests(unittest.TestCase):
    """A stale will heals, while a genuinely disconnected publisher stays offline."""

    def setUp(self):
        self.package = yaml.safe_load(
            (ROOT / "packages/mqtt-availability.yaml").read_text()
        )
        self.timer = self.package["interval"][0]

    def tick(self, connected):
        published = []
        actions(self.timer["then"], connected, published)
        return published

    def test_late_old_will_is_replaced_by_connected_publisher(self):
        retained = "offline"  # old connection's will arrived after the new birth
        messages = self.tick(connected=True)
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertTrue(message["retain"])
        self.assertEqual(message["qos"], 1)
        retained = message["payload"]
        self.assertEqual(retained, "online")
        self.assertEqual(message, self.package["mqtt"]["birth_message"])
        self.assertEqual(self.timer["interval"], "30s")

    def test_real_disconnect_is_not_relabelled_online(self):
        for _ in range(3):
            self.assertEqual(self.tick(connected=False), [])
        self.assertEqual(set(self.package["mqtt"]), {"birth_message"})
        # No replacement/disablement of ESPHome's native will/shutdown messages.

    def test_connection_drop_between_ticks_and_reconnect(self):
        self.assertEqual(len(self.tick(True)), 1)
        self.assertEqual(self.tick(False), [])
        self.assertEqual(self.tick(False), [])
        self.assertEqual(len(self.tick(True)), 1)

    def test_chains_have_separate_status_topics_and_shared_logic(self):
        class Loader(yaml.SafeLoader):
            """Read references without resolving private secrets."""
        Loader.add_constructor("!secret", lambda loader, node: node.value)
        Loader.add_constructor(
            "!include", lambda loader, node: loader.construct_mapping(node, deep=True)
        )
        for chain, topic in [(1, "battery/status"), (2, "battery2/status")]:
            config = yaml.load(
                (ROOT / f"jbd-all-batteries{chain}.yaml").read_text(), Loader=Loader
            )
            include = config["packages"]["mqtt_availability"]
            self.assertEqual(include["file"], "packages/mqtt-availability.yaml")
            self.assertEqual(include["vars"], {"status_topic": topic})
            self.assertEqual(topic, config["mqtt"]["topic_prefix"] + "/status")


if __name__ == "__main__":
    unittest.main()
