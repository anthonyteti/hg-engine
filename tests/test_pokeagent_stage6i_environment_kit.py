from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.pokeagent.environment_kit import EnvironmentKitError, SOURCE, compile_kit, load_and_validate


class EnvironmentKitTests(unittest.TestCase):
    def test_canonical_kit_covers_required_vocabulary(self) -> None:
        data = load_and_validate()
        report = compile_kit(write=False)
        self.assertEqual(report["module_count"], 58)
        self.assertEqual(set(report["family_counts"]), {
            "terrain", "vegetation", "architecture", "architecture_part", "prop", "interior",
        })
        self.assertEqual(len(report["biome_counts"]), 8)
        self.assertTrue(all(count > 0 for count in report["biome_counts"].values()))
        self.assertEqual(data["presentation_direction"], "Adriatic Field Journal")

    def test_output_is_deterministic(self) -> None:
        first = compile_kit(write=False)
        second = compile_kit(write=False)
        self.assertEqual(first, second)
        self.assertEqual(first["showcases"]["stage6i_rural_kit"]["quads"], 24)
        self.assertEqual(first["showcases"]["stage6i_coastal_kit"]["quads"], 12)

    def test_duplicate_symbol_is_rejected(self) -> None:
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        data["modules"].append(dict(data["modules"][0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kit.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(EnvironmentKitError, "duplicate module id"):
                load_and_validate(path)

    def test_mixed_material_showcase_is_rejected(self) -> None:
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        data["showcases"][0]["placements"].append({
            "module": "rock_karst", "position": [0, 0, 0], "scale": [1, 1, 1],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kit.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(EnvironmentKitError, "only one material"):
                load_and_validate(path)


if __name__ == "__main__":
    unittest.main()
