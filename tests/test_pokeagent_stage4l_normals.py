from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.assets import AssetError, compile_asset, compile_asset_outputs
from tools.pokeagent.cli import build_parser
from tools.pokeagent.generated_intake import inspect_generated_asset
from tools.pokeagent.glb import BIN_CHUNK, JSON_CHUNK, GLBError, pack_glb, parse_glb
from tools.pokeagent.glb_normals import NormalGenerationError, generate_missing_normals
from tools.pokeagent.glb_preprocess import preprocess_static_glb
from tools.pokeagent.stage4l_fixture import _pack_source, build_stage4l_fixtures
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/stage4l_missing_normals_turret.glb"
REFERENCE = ROOT / "assets/source/stage4l_authored_normals_reference.glb"
MANIFEST = ROOT / "assets/manifests/stage4l_missing_normals_turret.json"
REFERENCE_MANIFEST = ROOT / "assets/manifests/stage4l_authored_normals_reference.json"
FIXTURE = ROOT / "fixtures/stage4l_normal_generation_world.json"
STAGE4H = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"


def _unpack(data: bytes) -> tuple[dict[str, object], bytes]:
    length, kind = struct.unpack_from("<II", data, 12)
    assert kind == JSON_CHUNK
    document = json.loads(data[20:20 + length].decode("utf-8"))
    offset = 20 + length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    assert binary_kind == BIN_CHUNK
    return document, data[offset + 8:offset + 8 + binary_length]


def _angle(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / denominator))
    return math.degrees(math.acos(dot))


class Stage4LNormalGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated = generate_missing_normals(SOURCE.read_bytes())
        cls.compiled = compile_asset(MANIFEST, ROOT)
        cls.reference = compile_asset(REFERENCE_MANIFEST, ROOT)

    def test_tracked_fixtures_are_reproducible_and_hash_locked(self) -> None:
        source, reference = build_stage4l_fixtures()
        self.assertEqual(source, SOURCE.read_bytes())
        self.assertEqual(reference, REFERENCE.read_bytes())
        self.assertEqual(hashlib.sha256(source).hexdigest(), "efa69d281a43f75316d589e5f671394ac5de90a5164631f7a5cd9f42774f2374")
        self.assertEqual(hashlib.sha256(reference).hexdigest(), "b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9")

    def test_strict_stage4f_rejects_source_and_accepts_generated_reference(self) -> None:
        with self.assertRaises(GLBError) as raised:
            parse_glb(SOURCE.read_bytes())
        self.assertEqual(raised.exception.code, "missing_attribute")
        canonical = parse_glb(self.generated["canonical_glb"])
        self.assertEqual(len(canonical.faces), 24)
        self.assertEqual(self.generated["canonical_glb"], REFERENCE.read_bytes())
        self.assertTrue(self.generated["report"]["stage4f_accepted"])

    def test_generated_and_authored_reference_match_semantically_and_binary(self) -> None:
        actual_ir, expected_ir = copy.deepcopy(self.compiled["ir"]), copy.deepcopy(self.reference["ir"])
        actual_ir.pop("asset_id"); expected_ir.pop("asset_id")
        self.assertEqual(actual_ir, expected_ir)
        self.assertEqual(self.compiled["display_list"], self.reference["display_list"])
        self.assertEqual(self.compiled["collision"], self.reference["collision"])
        self.assertEqual(self.compiled["textures"]["stage4d_stone"]["texture"], self.reference["textures"]["stage4d_stone"]["texture"])
        generated_normals = self.generated["canonical_mesh"].normals
        reference_normals = parse_glb(REFERENCE.read_bytes()).normals
        self.assertEqual(generated_normals, reference_normals)
        errors = [_angle(left, right) for left, right in zip(generated_normals, reference_normals, strict=True)]
        self.assertLess(max(errors), 1e-5)
        self.assertLess(sum(errors) / len(errors), 1e-6)

    def test_declared_crease_policy_smooths_walls_splits_roof_and_preserves_uv_seam(self) -> None:
        report = self.generated["report"]
        self.assertEqual(report["crease_angle_degrees"], 60.0)
        self.assertEqual(report["weighting"], "area")
        self.assertEqual(report["source_attribute_vertices"], 19)
        self.assertEqual(report["canonical_attribute_vertices"], 27)
        self.assertEqual(report["split_vertex_count"], 8)
        self.assertEqual(report["generated_unique_normal_count"], 25)
        self.assertEqual(report["smooth_edge_count"], 23)
        self.assertEqual(report["hard_edge_count"], 9)
        self.assertEqual(report["boundary_edge_count"], 8)
        self.assertEqual(report["uv_seam_forced_split_count"], 2)
        self.assertLess(report["max_float32_normal_length_error"], 2e-7)

    def test_flat_hard_smooth_and_uv_cases_are_order_invariant(self) -> None:
        forward, _ = build_stage4l_fixtures()
        reversed_faces, _ = build_stage4l_fixtures(reverse_faces=True)
        self.assertEqual(generate_missing_normals(forward)["canonical_glb"], generate_missing_normals(reversed_faces)["canonical_glb"])
        planar_positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
        planar_uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        planar = generate_missing_normals(_pack_source(planar_positions, planar_uvs, [(0, 2, 1), (0, 3, 2)]))
        self.assertEqual(planar["report"]["generated_unique_normal_count"], 1)
        self.assertEqual(planar["report"]["smooth_edge_count"], 1)

    def test_crease_threshold_and_geometry_mutations_propagate_predictably(self) -> None:
        thirty = generate_missing_normals(SOURCE.read_bytes(), crease_angle_degrees=30)
        sixty = self.generated
        self.assertNotEqual(thirty["canonical_glb"], sixty["canonical_glb"])
        self.assertLess(thirty["report"]["smooth_edge_count"], sixty["report"]["smooth_edge_count"])
        self.assertGreater(thirty["report"]["canonical_attribute_vertices"], sixty["report"]["canonical_attribute_vertices"])
        mutated, _ = build_stage4l_fixtures(roof_height=4.2)
        changed = generate_missing_normals(mutated)
        self.assertNotEqual(changed["report"]["source_sha256"], sixty["report"]["source_sha256"])
        self.assertNotEqual(changed["canonical_glb"], sixty["canonical_glb"])
        self.assertEqual(self.compiled["manifest"]["id"], "stage4l_missing_normals_turret")
        self.assertEqual(self.compiled["collision"], self.reference["collision"])

    def test_nonmanifold_winding_degenerate_and_policy_failures_are_stable(self) -> None:
        positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)]
        uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.5, 1.0), (1.0, 1.0)]
        cases = (
            (_pack_source(positions, uvs, [(0, 1, 2), (1, 0, 3), (0, 1, 4)]), "normal_generation_non_manifold"),
            (_pack_source(positions[:4], uvs[:4], [(0, 1, 2), (0, 1, 3)]), "normal_generation_inconsistent_winding"),
            (_pack_source(positions[:3], uvs[:3], [(0, 1, 1)]), "normal_generation_degenerate"),
        )
        for source, code in cases:
            with self.subTest(code=code), self.assertRaises(NormalGenerationError) as raised:
                generate_missing_normals(source)
            self.assertEqual(raised.exception.code, code)
        for kwargs, code in (({"crease_angle_degrees": 0}, "invalid_crease_threshold"), ({"crease_angle_degrees": 180}, "invalid_crease_threshold"), ({"weighting": "angle"}, "invalid_normal_weighting")):
            with self.subTest(code=code), self.assertRaises(NormalGenerationError) as raised:
                generate_missing_normals(SOURCE.read_bytes(), **kwargs)
            self.assertEqual(raised.exception.code, code)
        with self.assertRaises(NormalGenerationError) as raised:
            generate_missing_normals(REFERENCE.read_bytes())
        self.assertEqual(raised.exception.code, "normal_attribute_already_present")

    def test_missing_attributes_material_and_mode_remain_rejected(self) -> None:
        document, binary = _unpack(SOURCE.read_bytes())
        mutations = (
            (lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("POSITION"), "missing_attribute"),
            (lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0"), "missing_attribute"),
            (lambda d: d.update({"materials": []}), "unsupported_material"),
            (lambda d: d["meshes"][0]["primitives"][0].update({"mode": 5}), "unsupported_primitive_mode"),
        )
        for mutate, code in mutations:
            with self.subTest(code=code):
                changed = copy.deepcopy(document); mutate(changed)
                with self.assertRaises(NormalGenerationError) as raised:
                    generate_missing_normals(pack_glb(changed, binary))
                self.assertEqual(raised.exception.code, code)

    def test_outputs_cli_fixture_and_manifest_policy_are_deterministic(self) -> None:
        self.assertEqual(self.generated, generate_missing_normals(SOURCE.read_bytes()))
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            compile_asset_outputs(MANIFEST, Path(first), ROOT)
            compile_asset_outputs(MANIFEST, Path(second), ROOT)
            self.assertEqual((Path(first) / "normal-generated.glb").read_bytes(), (Path(second) / "normal-generated.glb").read_bytes())
            self.assertEqual((Path(first) / "normal-generation-report.json").read_bytes(), (Path(second) / "normal-generation-report.json").read_bytes())
        parsed = build_parser().parse_args(["asset", "normals", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "normals"))
        fixture = load_fixture(FIXTURE)
        self.assertEqual((fixture["schema_version"], fixture["artifact_namespace"]), (17, "stage4l"))
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as directory:
            data = json.loads(MANIFEST.read_text(encoding="utf-8")); data.pop("preprocessing")
            path = Path(directory) / "missing-policy.json"; path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(AssetError) as raised:
                compile_asset(path, ROOT)
            self.assertEqual(raised.exception.code, "invalid_manifest")

    def test_stage4k_bytes_and_stage4h_rejection_remain_invariant(self) -> None:
        stage4k = preprocess_static_glb((ROOT / "assets/source/stage4k_hierarchical_tower.glb").read_bytes())
        self.assertEqual(hashlib.sha256(stage4k["canonical_glb"]).hexdigest(), "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6")
        raw = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"
        before = raw.read_bytes(); report = inspect_generated_asset(STAGE4H, ROOT)
        self.assertFalse(report["accepted"])
        self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        self.assertFalse(report["stage4l"]["normal_generation"]["applicable"])
        self.assertFalse(report["stage4l"]["topology_subset"]["applicable"])
        self.assertEqual(
            {item["code"] for item in report["stage4l"]["topology_subset"]["reasons"]},
            {"normal_generation_face_budget", "normal_generation_accessor_budget"},
        )
        self.assertFalse(report["stage4l"]["retroactive_approval"])
        self.assertEqual(raw.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
