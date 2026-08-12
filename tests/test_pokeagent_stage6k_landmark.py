import hashlib
import json
from pathlib import Path
import unittest

from tools.pokeagent.assets import compile_asset, compile_placements
from tools.pokeagent.stage6k_landmark import MANIFEST, ROOT, compile_landmark


class Stage6KLandmarkTests(unittest.TestCase):
    def test_pipeline_is_deterministic_and_preserves_raw_boundary(self) -> None:
        first = compile_landmark(write=False)
        second = compile_landmark(write=False)
        self.assertEqual(first, second)
        self.assertTrue(first["raw"]["immutable"])
        self.assertTrue(first["stage4q"]["no_op"])
        self.assertTrue(first["stage4r"]["no_op"])
        self.assertEqual(first["stage4o"]["final"]["triangles"], 60)
        self.assertTrue(first["stage4f"]["accepted"])

    def test_tracked_derived_outputs_match_pipeline(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        compile_landmark(write=False)
        for record in manifest["derived"].values():
            payload = (ROOT / record["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])

    def test_compiled_landmark_fits_unchanged_project_capacity(self) -> None:
        compiled = compile_asset(ROOT / "assets/manifests/stage6k_hunyuan_lighthouse.json", ROOT)
        report = compiled["report"]
        self.assertEqual(report["display_list_bytes"], 4092)
        self.assertEqual(report["display_list_capacity_bytes"], 4096)
        self.assertTrue(report["geometry_storage"]["requires_relocation"])
        self.assertEqual(report["normalized_counts"]["triangles"], 60)
        self.assertEqual(report["material_mappings"]["generated_surface"]["texture"], "stage4d_stone")

    def test_landmark_placement_preserves_project_relocation_capacity(self) -> None:
        fixture = json.loads(
            (ROOT / "fixtures/stage6k_generated_landmark_world.json").read_text(encoding="utf-8")
        )
        compiled = compile_placements(ROOT / fixture["asset_catalog"], fixture["assets"], ROOT)
        shape = compiled["report"]["shapes"][0]
        self.assertEqual(shape["display_list_bytes"], 4092)
        self.assertEqual(shape["capacity_bytes"], 4096)
        self.assertEqual(shape["storage_policy"], "project_relocated_display_list")


if __name__ == "__main__":
    unittest.main()
