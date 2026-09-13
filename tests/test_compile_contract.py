"""Offline contracts for firmware CLI selection and filesystem confinement."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "compile_adapter", Path(__file__).parents[1] / "scripts/compile-esphome.py"
)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class ConfigSelectionTests(unittest.TestCase):
    """Reject unsafe file selection before any compiler or network access."""

    def test_declared_regular_yaml_is_selected(self):
        """Return declared paths only, with the original order retained."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "firmware.yaml").write_text("esphome: {}\n", encoding="utf-8")
            policy = {"esphome_configs": ["firmware.yaml"]}
            self.assertEqual(
                ADAPTER.selected_configs(root, policy, []), ["firmware.yaml"]
            )
            self.assertEqual(
                ADAPTER.confined_config(root, "firmware.yaml"), (root / "firmware.yaml").resolve()
            )

    def test_traversal_options_absolute_paths_and_wrong_extensions_are_rejected(self):
        """Untrusted CLI or policy entries cannot become compiler arguments."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for value in (
                "../secret.yaml",
                "/tmp/secret.yaml",
                "--help.yaml",
                "a/-x.yaml",
                "a.txt",
                "a\ny.yaml",
            ):
                with (
                    self.subTest(value=value),
                    self.assertRaises((ValueError, OSError)),
                ):
                    ADAPTER.confined_config(root, value)

    def test_symlinks_and_undeclared_configs_are_rejected(self):
        """Keep compiler input inside the reviewed source inventory."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "firmware.yaml").write_text("esphome: {}\n", encoding="utf-8")
            (root / "link.yaml").symlink_to(root / "firmware.yaml")
            with self.assertRaises(ValueError):
                ADAPTER.confined_config(root, "link.yaml")
            with self.assertRaises(ValueError):
                ADAPTER.selected_configs(
                    root, {"esphome_configs": ["firmware.yaml"]}, ["other.yaml"]
                )


if __name__ == "__main__":
    unittest.main()
