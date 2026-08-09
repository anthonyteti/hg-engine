from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.pokeagent.assets import compile_asset, compile_asset_outputs
from tools.pokeagent.cli import build_parser
from tools.pokeagent.generated_intake import inspect_generated_asset
from tools.pokeagent.glb import GLBError, GLB_LIMITS, _chunks, pack_glb, parse_glb
from tools.pokeagent.glb_bootstrap import (
    BootstrapError,
    bootstrap_geometry_glb,
    discard_color0_to_geometry,
    inspect_color0_discard_applicability,
)
from tools.pokeagent.glb_geometry_reduce import reduce_geometry_manifest
from tools.pokeagent.glb_preprocess import preprocess_static_glb
from tools.pokeagent.glb_normals import NormalGenerationError
from tools.pokeagent.glb_uvs import UVGenerationError
from tools.pokeagent.mesh_decimate import simplify_approximate_ir
from tools.pokeagent.stage4p_fixture import _pack_source, build_stage4p_fixtures
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/stage4p_geometry_only_turret.glb"
REFERENCE = ROOT / "assets/source/stage4p_complete_reference.glb"
COLOR_SOURCE = ROOT / "assets/source/stage4p_color0_geometry.glb"
COLOR_REFERENCE = ROOT / "assets/source/stage4p_color0_discard_reference.glb"
MANIFEST = ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json"
FIXTURE = ROOT / "fixtures/stage4p_attribute_bootstrap_world.json"
STAGE4H_MANIFEST = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"
STAGE4H_RAW = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"
POLICY = {
    "policy": "hard_surface_static_v1",
    "material_name": "generated_surface",
    "color0_policy": "reject",
    "patch_normal_degrees": 0.1,
    "plane_epsilon": 0.00001,
    "texture_size": 32,
    "padding_texels": 1,
    "crease_angle_degrees": 60,
    "normal_weighting": "area",
}


class Stage4PAttributeBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = bootstrap_geometry_glb(SOURCE.read_bytes(), POLICY)
        cls.compiled = compile_asset(MANIFEST, ROOT)

    def test_tracked_fixtures_are_reproducible_and_hash_locked(self) -> None:
        outputs = build_stage4p_fixtures()
        tracked = (SOURCE, REFERENCE, COLOR_SOURCE, COLOR_REFERENCE)
        for actual, path in zip(outputs, tracked, strict=True):
            self.assertEqual(actual, path.read_bytes())
        self.assertEqual(hashlib.sha256(outputs[0]).hexdigest(), "abe77fe5f6ce58e1ca01b26946d35bde438b12d1598d43bb044b74f6fed5216e")
        self.assertEqual(hashlib.sha256(outputs[1]).hexdigest(), "06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1")
        self.assertEqual(hashlib.sha256(outputs[2]).hexdigest(), "f341585984c093237642c26ddbdbe2f906ac7b7fb8427bdc06ce2fa7d33d33bb")
        self.assertEqual(hashlib.sha256(outputs[3]).hexdigest(), "39971cd8850b6cf4c8b41066a7ce785b3e75132f2c8a4e0218ab70cf4d649f27")

    def test_strict_stage4f_rejects_source_then_accepts_exact_reference(self) -> None:
        with self.assertRaises(GLBError) as raised:
            parse_glb(SOURCE.read_bytes())
        self.assertEqual(raised.exception.code, "unsupported_material")
        self.assertEqual(self.result["canonical_glb"], REFERENCE.read_bytes())
        mesh = parse_glb(self.result["canonical_glb"])
        self.assertEqual((len(mesh.faces), {face.material for face in mesh.faces}), (30, {"generated_surface"}))
        self.assertTrue(self.result["report"]["stage4f_accepted"])

    def test_transaction_order_provenance_metrics_and_runtime_budget(self) -> None:
        report = self.result["report"]
        self.assertTrue(report["atomic"])
        self.assertEqual(report["operation_order"], [
            "validate_geometry", "assign_material", "generate_uv0", "generate_final_normals", "stage4f_validate",
        ])
        self.assertEqual((report["source_topology"]["positions"], report["source_topology"]["triangles"]), (19, 30))
        self.assertEqual(report["material"]["provenance"], "stage4p_via_stage4n_policy")
        self.assertEqual((report["uv"]["planar_patch_count"], report["uv"]["uv_split_count"], report["uv"]["uv_seam_edge_count"]), (18, 47, 30))
        self.assertEqual((report["normals"]["smoothing_fan_count"], report["normals"]["generated_unique_normal_count"]), (66, 40))
        self.assertEqual((report["normals"]["hard_edge_count"], report["normals"]["smooth_edge_count"]), (30, 12))
        self.assertEqual(report["final_counts"]["attribute_vertices"], 66)
        self.assertEqual(self.compiled["report"]["display_list_bytes"], 2052)
        self.assertEqual(self.compiled["report"]["shape_utilization_percent"], 82.212)
        self.assertEqual(self.compiled["report"]["hashes"]["display_list_sha256"], "4377c8cf4628b296273056b52d3f2710fdecbc587fa7ee5dea6181bd9f7bbb5e")
        self.assertEqual(self.compiled["report"]["material_mappings"]["generated_surface"]["texture"], "stage4d_stone")

    def test_color0_explicit_discard_is_exact_opt_in_and_bounded(self) -> None:
        with self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(COLOR_SOURCE.read_bytes(), POLICY)
        self.assertEqual(raised.exception.code, "bootstrap_color0_policy_required")
        discarded = discard_color0_to_geometry(COLOR_SOURCE.read_bytes())
        self.assertEqual(discarded["canonical_glb"], COLOR_REFERENCE.read_bytes())
        self.assertTrue(discarded["report"]["position_index_semantics_preserved"])
        self.assertEqual(discarded["report"]["removed_attributes"], ["COLOR_0"])
        self.assertEqual(discarded["report"]["color0"]["payload_sha256"], "d6ced436249fc4c1e2729cec8acc742a10964cf6ecd3d70b4ccfcd3edb70231d")
        policy = dict(POLICY); policy["color0_policy"] = "explicit_discard"
        self.assertEqual(bootstrap_geometry_glb(COLOR_SOURCE.read_bytes(), policy)["canonical_glb"], REFERENCE.read_bytes())

    def test_source_order_and_clean_output_runs_are_byte_identical(self) -> None:
        reversed_source, _reference, _color, _discard = build_stage4p_fixtures(reverse_faces=True)
        self.assertEqual(bootstrap_geometry_glb(reversed_source, POLICY)["canonical_glb"], self.result["canonical_glb"])
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            compile_asset_outputs(MANIFEST, Path(first), ROOT)
            compile_asset_outputs(MANIFEST, Path(second), ROOT)
            for name in ("bootstrapped.glb", "bootstrap-report.json", "normalized-mesh.json", "display-list.bin", "collision.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
        parsed = build_parser().parse_args(["asset", "bootstrap", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "bootstrap"))
        self.assertEqual(load_fixture(FIXTURE)["canonical_schema_version"], 20)

    def test_geometry_material_uv_and_normal_policy_mutations_are_orthogonal(self) -> None:
        changed_source, _reference, _color, _discard = build_stage4p_fixtures(roof_height=4.8)
        changed = bootstrap_geometry_glb(changed_source, POLICY)
        self.assertNotEqual(changed["canonical_glb"], self.result["canonical_glb"])
        self.assertEqual(changed["report"]["material"]["name"], "generated_surface")
        alternate = dict(POLICY); alternate["material_name"] = "generated_surface_alt"
        alternate_result = bootstrap_geometry_glb(SOURCE.read_bytes(), alternate)
        self.assertNotEqual(alternate_result["canonical_glb"], self.result["canonical_glb"])
        self.assertEqual(alternate_result["report"]["uv"]["planar_patch_count"], self.result["report"]["uv"]["planar_patch_count"])
        padded = dict(POLICY); padded["padding_texels"] = 2
        padded_result = bootstrap_geometry_glb(SOURCE.read_bytes(), padded)
        self.assertNotEqual(padded_result["canonical_glb"], self.result["canonical_glb"])
        self.assertEqual(padded_result["report"]["normals"]["hard_edge_count"], self.result["report"]["normals"]["hard_edge_count"])
        tighter = dict(POLICY); tighter["crease_angle_degrees"] = 30
        tighter_result = bootstrap_geometry_glb(SOURCE.read_bytes(), tighter)
        # Planar-patch UV seams already protect every non-coplanar edge in this
        # transaction; changing 60 to 30 is therefore a deterministic semantic no-op.
        self.assertEqual(tighter_result["canonical_glb"], self.result["canonical_glb"])
        self.assertEqual(tighter_result["report"]["normals"]["hard_edge_count"], 30)

    def test_stage4o_reduced_geometry_composes_into_strict_stage4f(self) -> None:
        reduced = reduce_geometry_manifest(ROOT / "assets/manifests/stage4o_dense_geometry_shrine.json", ROOT)
        bootstrapped = bootstrap_geometry_glb(reduced["canonical_glb"], POLICY)
        self.assertEqual((bootstrapped["report"]["source_topology"]["positions"], bootstrapped["report"]["source_topology"]["triangles"]), (35, 64))
        self.assertEqual(bootstrapped["report"]["final_counts"]["attribute_vertices"], 192)
        self.assertEqual(len(parse_glb(bootstrapped["canonical_glb"]).faces), 64)

    def test_stage4k_output_and_stage4j_typed_ir_interfaces_are_compatible(self) -> None:
        flattened = preprocess_static_glb(
            (ROOT / "assets/source/stage4k_hierarchical_tower.glb").read_bytes(),
        )["canonical_mesh"]
        geometry_only = _pack_source(
            list(flattened.vertices),
            [tuple(corner.vertex for corner in face.corners) for face in flattened.faces],
        )
        composed = bootstrap_geometry_glb(geometry_only, POLICY)
        self.assertEqual(len(parse_glb(composed["canonical_glb"]).faces), len(flattened.faces))

        approximate_policy = json.loads(
            (ROOT / "assets/manifests/stage4j_dense_stone_shrine.json").read_text(),
        )["simplification"]["approximate"]
        eligible, report = simplify_approximate_ir(self.compiled["ir"], 4096, approximate_policy)
        self.assertFalse(report["applied"])
        self.assertEqual(len(eligible["faces"]), len(self.compiled["ir"]["faces"]))
        self.assertEqual(eligible["materials"], self.compiled["ir"]["materials"])

    def test_missing_all_topology_attribute_and_policy_failures_are_stable(self) -> None:
        source = SOURCE.read_bytes()
        complete = REFERENCE.read_bytes()
        for data, code in (
            (complete, "bootstrap_material_already_present"),
            (COLOR_SOURCE.read_bytes(), "bootstrap_color0_policy_required"),
        ):
            with self.subTest(code=code), self.assertRaises(BootstrapError) as raised:
                bootstrap_geometry_glb(data, POLICY)
            self.assertEqual(raised.exception.code, code)
        positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
        with self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(_pack_source(positions, [(0, 1, 2)]), POLICY)
        self.assertEqual(raised.exception.code, "bootstrap_source_failed")
        invalid = dict(POLICY); invalid["material_name"] = "Bad-Name"
        with self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(source, invalid)
        self.assertEqual(raised.exception.code, "bootstrap_material_failed")

        complete_document, complete_binary = _chunks(complete, GLB_LIMITS)
        complete_document.pop("materials")
        primitive = complete_document["meshes"][0]["primitives"][0]
        primitive.pop("material")
        normal_only = json.loads(json.dumps(complete_document))
        normal_only["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0")
        uv_only = json.loads(json.dumps(complete_document))
        uv_only["meshes"][0]["primitives"][0]["attributes"].pop("NORMAL")
        for data, code in (
            (pack_glb(normal_only, complete_binary), "bootstrap_normal_already_present"),
            (pack_glb(uv_only, complete_binary), "bootstrap_uv_already_present"),
        ):
            with self.subTest(code=code), self.assertRaises(BootstrapError) as raised:
                bootstrap_geometry_glb(data, POLICY)
            self.assertEqual(raised.exception.code, code)

        nonmanifold = _pack_source(
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
             (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)],
            [(0, 1, 2), (1, 0, 3), (0, 1, 4)],
        )
        with self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(nonmanifold, POLICY)
        self.assertEqual(raised.exception.code, "bootstrap_source_failed")

    def test_atomic_uv_normal_and_stage4f_phase_failures_are_stable(self) -> None:
        with mock.patch(
            "tools.pokeagent.glb_bootstrap.generate_planar_uvs_from_geometry",
            side_effect=UVGenerationError("generated_degenerate_uv", "controlled UV failure"),
        ), self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(SOURCE.read_bytes(), POLICY)
        self.assertEqual((raised.exception.code, raised.exception.phase), ("bootstrap_uv_failed", "uv"))

        with mock.patch(
            "tools.pokeagent.glb_bootstrap.generate_missing_normals",
            side_effect=NormalGenerationError("zero_length_generated_normal", "controlled normal failure"),
        ), self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(SOURCE.read_bytes(), POLICY)
        self.assertEqual((raised.exception.code, raised.exception.phase), ("bootstrap_normal_failed", "normal"))

        with mock.patch(
            "tools.pokeagent.glb_bootstrap.parse_glb",
            side_effect=GLBError("missing_attribute", "controlled final rejection"),
        ), self.assertRaises(BootstrapError) as raised:
            bootstrap_geometry_glb(SOURCE.read_bytes(), POLICY)
        self.assertEqual((raised.exception.code, raised.exception.phase), ("bootstrap_stage4f_rejected", "stage4f"))

    def test_stage4h_projection_preserves_historical_rejection_and_raw_hash(self) -> None:
        before = STAGE4H_RAW.read_bytes()
        projection = inspect_color0_discard_applicability(before)
        self.assertTrue(projection["color0_policy_match"])
        self.assertFalse(projection["post_discard_stage4o_applicable"])
        self.assertEqual(projection["topology"]["zero_area_triangles"], 1)
        self.assertEqual(projection["topology"]["connected_components"], 2)
        self.assertEqual(projection["topology"]["open_boundary_loops"], 25)
        report = inspect_generated_asset(STAGE4H_MANIFEST, ROOT)
        self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        self.assertFalse(report["stage4p"]["retroactive_approval"])
        self.assertEqual(STAGE4H_RAW.read_bytes(), before)

    def test_documented_canonical_regressions_remain_exact(self) -> None:
        expectations = {
            "stage4k_hierarchical_tower.json": ("preprocessed_glb_sha256", "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6"),
            "stage4l_missing_normals_turret.json": ("normal_generated_glb_sha256", "b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9"),
            "stage4m_missing_uv_turret.json": ("uv_generated_glb_sha256", "c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84"),
            "stage4n_missing_material_turret.json": ("material_generated_glb_sha256", "3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66"),
        }
        for manifest, (field, expected) in expectations.items():
            report = compile_asset(ROOT / "assets/manifests" / manifest, ROOT)["report"]
            self.assertEqual(report["hashes"][field], expected)
        stage4j = compile_asset(ROOT / "assets/manifests/stage4j_dense_stone_shrine.json", ROOT)["report"]
        self.assertEqual(stage4j["display_list_bytes"], 4024)
        self.assertEqual(stage4j["hashes"]["display_list_sha256"], "e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04")


if __name__ == "__main__":
    unittest.main()
