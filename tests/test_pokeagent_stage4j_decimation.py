from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom

from tools.pokeagent.assets import AssetError, compile_asset, compile_asset_outputs
from tools.pokeagent.geometry import inspect_mesh_display_list
from tools.pokeagent.mesh_decimate import DecimationError, simplify_approximate_ir
from tools.pokeagent.mesh_simplify import simplify_coplanar_ir
from tools.pokeagent.nsbmd_model import inspect_nsbmd_model
from tools.pokeagent.stage4j_fixture import build_dense_shrine
from tools.pokeagent.world import build_map_member, load_fixture, split_hgss_map_member


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4j_dense_stone_shrine.json"
FAILURE = ROOT / "assets/manifests/stage4j_fidelity_failure.json"
SOURCE = ROOT / "assets/source/stage4j_dense_stone_shrine.glb"
FIXTURE = ROOT / "fixtures/stage4j_approximate_decimation_world.json"


class Stage4JApproximateDecimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiled = compile_asset(MANIFEST, ROOT)

    def test_canonical_source_requires_approximate_reduction_to_4k(self) -> None:
        report = self.compiled["report"]
        simplification = report["simplification"]
        self.assertEqual(report["source_normalized_counts"]["triangles"], 208)
        self.assertEqual(simplification["source_projected_display_list_bytes"], 14156)
        self.assertEqual(simplification["post_exact_display_list_bytes"], 10928)
        self.assertGreater(simplification["post_exact_overflow_bytes"], 0)
        self.assertEqual(report["normalized_counts"], {"vertices": 37, "faces": 59, "quads": 0, "triangles": 59})
        self.assertEqual(report["display_list_bytes"], 4024)
        self.assertLessEqual(report["display_list_bytes"], 4096)
        self.assertTrue(report["geometry_storage"]["requires_relocation"])
        self.assertEqual(report["geometry_storage"]["tested_project_capacity_bytes"], 4096)

    def test_fidelity_metrics_and_structural_identity_pass_declared_thresholds(self) -> None:
        approximate = self.compiled["report"]["simplification"]["approximate"]
        metrics, thresholds = approximate["metrics"], approximate["thresholds"]
        self.assertLessEqual(metrics["maximum_vertex_displacement"], thresholds["max_geometric_error"])
        self.assertLessEqual(metrics["bounds_max_delta"], thresholds["max_bounds_delta"])
        self.assertLessEqual(metrics["surface_area_delta_percent"], thresholds["max_surface_area_delta_percent"])
        self.assertGreaterEqual(metrics["minimum_silhouette_iou"], thresholds["min_silhouette_iou"])
        self.assertLessEqual(metrics["maximum_normal_deviation_degrees"], thresholds["max_normal_deviation_degrees"])
        self.assertLessEqual(metrics["maximum_uv_distortion_percent"], thresholds["max_uv_distortion_percent"])
        self.assertEqual(len({face["material_alias"] for face in self.compiled["ir"]["faces"]}), 1)
        self.assertEqual(len({face["texture"] for face in self.compiled["ir"]["faces"]}), 1)
        self.assertEqual(self.compiled["collision"], {"min_x": -2.45, "max_x": 2.45, "min_z": -2.45, "max_z": 2.45})
        inspected = inspect_mesh_display_list(self.compiled["display_list"])
        self.assertEqual(inspected["triangle_count"], 59)
        self.assertEqual(inspected["vertex_count"], 177)

    def test_valid_fidelity_failure_refuses_destructive_fit(self) -> None:
        with self.assertRaises(AssetError) as raised:
            compile_asset(FAILURE, ROOT)
        self.assertEqual(raised.exception.code, "approximate_simplification_target_unreachable")
        self.assertGreater(raised.exception.details["best_valid_bytes"], 4096)

    def test_determinism_and_order_canonicalization(self) -> None:
        second = compile_asset(MANIFEST, ROOT)
        self.assertEqual(self.compiled["ir"], second["ir"])
        self.assertEqual(self.compiled["display_list"], second["display_list"])
        exact, _report = simplify_coplanar_ir(self.compiled["source_ir"])
        shuffled = copy.deepcopy(exact)
        shuffled["faces"].reverse()
        policy = self.compiled["manifest"]["simplification"]["approximate"]
        ordered, _ = simplify_approximate_ir(exact, 4096, policy)
        reordered, _ = simplify_approximate_ir(shuffled, 4096, policy)
        self.assertEqual(ordered, reordered)

    def test_outputs_materialize_both_simplification_stages(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            report = compile_asset_outputs(MANIFEST, Path(directory), ROOT)
            self.assertEqual(report["outputs"]["simplified_mesh"], "simplified-mesh.json")
            self.assertTrue((Path(directory) / "normalized-mesh.json").is_file())
            self.assertTrue((Path(directory) / "simplified-mesh.json").is_file())
            self.assertTrue((Path(directory) / "display-list.bin").is_file())

    def test_source_and_target_mutations_are_bounded_and_source_driven(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/source") as source_dir, tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as manifest_dir:
            source = Path(source_dir) / "mutated.glb"
            source.write_bytes(build_dense_shrine(roof_height=7.2))
            manifest = copy.deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
            manifest["source"] = source.relative_to(ROOT).as_posix()
            manifest_path = Path(manifest_dir) / "mutated.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            mutated = compile_asset(manifest_path, ROOT)
            manifest["geometry_storage"]["max_bytes"] = 3500
            target_path = Path(manifest_dir) / "tight.json"
            target_path.write_text(json.dumps(manifest), encoding="utf-8")
            try:
                tight = compile_asset(target_path, ROOT)
            except AssetError as error:
                self.assertEqual(error.code, "approximate_simplification_target_unreachable")
            else:
                self.assertLessEqual(tight["report"]["display_list_bytes"], 3500)
        self.assertNotEqual(self.compiled["report"]["source_sha256"], mutated["report"]["source_sha256"])
        self.assertNotEqual(self.compiled["ir"], mutated["ir"])
        self.assertNotEqual(self.compiled["display_list"], mutated["display_list"])
        self.assertEqual(self.compiled["manifest"]["id"], mutated["manifest"]["id"])
        self.assertEqual(self.compiled["collision"], mutated["collision"])
        self.assertEqual(self.compiled["textures"]["stage4d_stone"], mutated["textures"]["stage4d_stone"])

    def test_invalid_policy_and_topology_fail_stably(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as directory:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            manifest["simplification"]["approximate"]["preserve_uv_seams"] = False
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(AssetError) as raised:
                compile_asset(path, ROOT)
        self.assertEqual(raised.exception.code, "unsupported_simplification_policy")
        malformed = copy.deepcopy(self.compiled["ir"])
        malformed["faces"].append(copy.deepcopy(malformed["faces"][0]))
        with self.assertRaises(DecimationError) as topology:
            simplify_approximate_ir(malformed, 4096, self.compiled["manifest"]["simplification"]["approximate"])
        self.assertEqual(topology.exception.code, "approximate_simplification_invalid_topology")

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "requires ignored supported local ROM")
    def test_relocated_model_reopens_with_final_triangle_stream(self) -> None:
        fixture = load_fixture(FIXTURE)
        rom = NintendoDSRom.fromFile(str(ROOT / "rom.nds"))
        retail_member = NARC(rom.getFileByName("a/0/6/5")).files[0]
        member, report = build_map_member(fixture, retail_member)
        model = split_hgss_map_member(member)["nsbmd"]
        inspected = inspect_nsbmd_model(model)
        self.assertEqual(inspected["shapes"][6]["display_length"], 4024)
        self.assertEqual(inspected["shapes"][6]["commands"]["triangle_count"], 59)
        self.assertTrue(report["relocation"]["unaffected_payloads_preserved"])

    def test_stage4h_rejection_remains_immutable_and_uncataloged(self) -> None:
        catalog = json.loads((ROOT / "assets/catalog.json").read_text(encoding="utf-8"))
        ids = {entry["id"] for entry in catalog["assets"]}
        self.assertNotIn("stage4h_generated_shrine", ids)
        provenance = json.loads((ROOT / "assets/provenance/stage4h_generated_shrine.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["raw_output_sha256"], "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60")


if __name__ == "__main__":
    unittest.main()
