"""Keep management interfaces authenticated without exposing HTTP update routes."""

import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "access_compiler", ROOT / "scripts/compile-esphome.py"
)
COMPILER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPILER)


class ReferenceLoader(yaml.SafeLoader):
    """Preserve references without reading a developer's private secrets."""


ReferenceLoader.add_constructor("!secret", lambda loader, node: ("secret", node.value))
ReferenceLoader.add_constructor(
    "!include", lambda loader, node: loader.construct_mapping(node, deep=True)
)


class ManagementProfileTests(unittest.TestCase):
    def test_all_declared_profiles_require_private_keys_without_http(self):
        policy = json.loads((ROOT / ".release-policy.json").read_text())
        for name in policy["esphome_configs"]:
            with self.subTest(name=name):
                config = yaml.load((ROOT / name).read_text(), Loader=ReferenceLoader)
                self.assertEqual(
                    config["api"]["encryption"],
                    {"key": ("secret", "api_encryption_key")},
                )
                self.assertEqual(config["api"]["reboot_timeout"], "0s")
                self.assertEqual(
                    config["ota"], {"platform": "esphome", "encryption": {}}
                )
                self.assertNotIn("web_server", config)
                self.assertNotIn("captive_portal", config)
                self.assertEqual(
                    config["wifi"]["ap"]["password"], ("secret", "fallback_ap_password")
                )

    def test_example_secrets_cannot_be_used_as_deployment_defaults(self):
        example = yaml.safe_load((ROOT / "secrets.example.yaml").read_text())
        self.assertEqual(
            set(example),
            {"wifi_ssid", "wifi_pass", "fallback_ap_password", "api_encryption_key"},
        )
        self.assertTrue(all(value is None for value in example.values()))

    def test_compile_secrets_are_ephemeral_and_do_not_read_operator_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            stages = [Path(temporary) / name for name in ("first", "second")]
            generated = []
            for stage in stages:
                stage.mkdir()
                COMPILER.stage_configs(ROOT, stage, ["jbd-all-batteries1.yaml"])
                values = yaml.safe_load((stage / "secrets.yaml").read_text())
                self.assertEqual(
                    len(base64.b64decode(values["api_encryption_key"], validate=True)),
                    32,
                )
                self.assertGreaterEqual(len(values["fallback_ap_password"]), 32)
                self.assertNotEqual(values["wifi_pass"], values["fallback_ap_password"])
                generated.append(values)
            self.assertNotEqual(
                generated[0]["api_encryption_key"], generated[1]["api_encryption_key"]
            )

    def test_compiler_feature_check_rejects_each_insecure_build(self):
        required = {
            "USE_API_NOISE",
            "USE_OTA_ENCRYPTION",
            "USE_OTA_ENCRYPTION_REQUIRED",
        }
        forbidden = {
            "USE_API_PLAINTEXT",
            "USE_OTA_PASSWORD",
            "USE_WEBSERVER",
            "USE_WEBSERVER_OTA",
            "USE_CAPTIVE_PORTAL",
        }
        variants = [("missing_" + flag, required - {flag}) for flag in required]
        variants.extend(("extra_" + flag, required | {flag}) for flag in forbidden)
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            with self.assertRaisesRegex(ValueError, "no feature definitions"):
                COMPILER.verify_encrypted_build(stage)
            header = stage / ".esphome/build/test/src/esphome/core/defines.h"
            header.parent.mkdir(parents=True)
            header.write_text("\n".join("#define " + flag for flag in required))
            COMPILER.verify_encrypted_build(stage)
            for name, flags in variants:
                with self.subTest(name=name):
                    header.write_text("\n".join("#define " + flag for flag in flags))
                    with self.assertRaisesRegex(
                        ValueError, "require encrypted API/OTA"
                    ):
                        COMPILER.verify_encrypted_build(stage)


if __name__ == "__main__":
    unittest.main()
