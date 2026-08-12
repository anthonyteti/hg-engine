from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.pokeagent.asset_catalog import AssetCatalogError, SOURCE, compile_catalog


class Stage6AssetCatalogTests(unittest.TestCase):
    def test_catalog_is_complete_and_planner_facing(self) -> None:
        catalog = compile_catalog(write=False)
        self.assertEqual(catalog["base_module_count"], 58)
        self.assertEqual(catalog["variant_count"], 41)
        self.assertEqual(catalog["asset_count"], 99)
        self.assertEqual(len({item["id"] for item in catalog["assets"]}), 99)
        for item in catalog["assets"]:
            self.assertEqual(item["status"], "approved")
            self.assertNotIn("narc", json.dumps(item).lower())
            self.assertEqual(item["rotations"], [0, 90, 180, 270])

    def test_same_seed_is_byte_deterministic(self) -> None:
        first = json.dumps(compile_catalog(write=False), sort_keys=True, separators=(",", ":")).encode()
        second = json.dumps(compile_catalog(write=False), sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(first, second)

    def test_unknown_component_is_rejected(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        source["families"][0]["components"]["roof"] = ["unknown_roof"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "variants.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(AssetCatalogError, "unknown module"):
                compile_catalog(path, write=False)

    def test_seed_change_changes_composition_not_schema(self) -> None:
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        source["seed"] = "bounded-alternate-seed"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "variants.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            alternate = compile_catalog(path, write=False)
        canonical = compile_catalog(write=False)
        self.assertEqual(alternate["asset_count"], canonical["asset_count"])
        pairs = zip(alternate["assets"], canonical["assets"])
        self.assertTrue(any(a["components"] != b["components"] for a, b in pairs))


if __name__ == "__main__":
    unittest.main()
