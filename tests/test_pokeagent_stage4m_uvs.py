from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.assets import AssetError, compile_asset, compile_asset_outputs
from tools.pokeagent.cli import build_parser
from tools.pokeagent.generated_intake import inspect_generated_asset
from tools.pokeagent.glb import GLBError, parse_glb
from tools.pokeagent.glb_normals import generate_missing_normals
from tools.pokeagent.glb_preprocess import preprocess_static_glb
from tools.pokeagent.glb_uvs import UVGenerationError, _basis, generate_missing_uvs
from tools.pokeagent.stage4l_fixture import build_stage4l_fixtures
from tools.pokeagent.stage4m_fixture import _pack_no_uv, build_stage4m_fixtures
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/stage4m_missing_uv_turret.glb"
REFERENCE = ROOT / "assets/source/stage4m_authored_uv_reference.glb"
MANIFEST = ROOT / "assets/manifests/stage4m_missing_uv_turret.json"
REFERENCE_MANIFEST = ROOT / "assets/manifests/stage4m_authored_uv_reference.json"
FIXTURE = ROOT / "fixtures/stage4m_uv_generation_world.json"
STAGE4H = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"


def _unit(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(component * component for component in value))
    return tuple(component / length for component in value)


def _semantic_without_uv(mesh: object) -> bytes:
    vertices = sorted({
        (mesh.vertices[corner.vertex], mesh.normals[corner.normal])
        for face in mesh.faces for corner in face.corners
    })
    lookup = {value: index for index, value in enumerate(vertices)}
    triangles = [
        tuple(lookup[(mesh.vertices[corner.vertex], mesh.normals[corner.normal])] for corner in face.corners)
        for face in mesh.faces
    ]
    return _pack_no_uv([value[0] for value in vertices], [value[1] for value in vertices], triangles)


class Stage4MUVGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated = generate_missing_uvs(SOURCE.read_bytes())
        cls.compiled = compile_asset(MANIFEST, ROOT)
        cls.reference = compile_asset(REFERENCE_MANIFEST, ROOT)

    def test_tracked_fixtures_are_reproducible_and_hash_locked(self) -> None:
        source, reference = build_stage4m_fixtures()
        self.assertEqual(source, SOURCE.read_bytes())
        self.assertEqual(reference, REFERENCE.read_bytes())
        self.assertEqual(hashlib.sha256(source).hexdigest(), "809f77f87ea9b2bb93d83aa58b4aaa54c9c48b3d4bcac6c90d22f483441f6d6e")
        self.assertEqual(hashlib.sha256(reference).hexdigest(), "c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84")

    def test_strict_stage4f_rejects_source_and_accepts_generated_reference(self) -> None:
        with self.assertRaises(GLBError) as raised:
            parse_glb(SOURCE.read_bytes())
        self.assertEqual(raised.exception.code, "missing_attribute")
        canonical = parse_glb(self.generated["canonical_glb"])
        self.assertEqual(len(canonical.faces), 20)
        self.assertEqual(self.generated["canonical_glb"], REFERENCE.read_bytes())
        self.assertTrue(self.generated["report"]["stage4f_accepted"])

    def test_generated_and_authored_reference_match_semantically_and_binary(self) -> None:
        actual_ir, expected_ir = copy.deepcopy(self.compiled["ir"]), copy.deepcopy(self.reference["ir"])
        actual_ir.pop("asset_id"); expected_ir.pop("asset_id")
        self.assertEqual(actual_ir, expected_ir)
        self.assertEqual(self.compiled["display_list"], self.reference["display_list"])
        self.assertEqual(self.compiled["collision"], self.reference["collision"])
        generated_mesh = parse_glb(self.generated["canonical_glb"])
        reference_mesh = parse_glb(REFERENCE.read_bytes())
        self.assertEqual(generated_mesh.uvs, reference_mesh.uvs)
        differences = [abs(a - b) for left, right in zip(generated_mesh.uvs, reference_mesh.uvs, strict=True) for a, b in zip(left, right, strict=True)]
        self.assertEqual(max(differences), 0.0)
        self.assertEqual(sum(differences) / len(differences), 0.0)

    def test_declared_patch_policy_metrics_are_bounded_and_coherent(self) -> None:
        report = self.generated["report"]
        self.assertEqual(report["patch_normal_degrees"], 0.1)
        self.assertEqual(report["plane_epsilon"], 1e-5)
        self.assertEqual((report["texture_size"], report["padding_texels"], report["padding_uv"]), (32, 1, 1 / 32))
        self.assertEqual(report["source_attribute_vertices"], 13)
        self.assertEqual(report["canonical_attribute_vertices"], 37)
        self.assertEqual(report["uv_split_count"], 24)
        self.assertEqual(report["planar_patch_count"], 9)
        self.assertEqual(report["uv_seam_edge_count"], 16)
        self.assertEqual(report["boundary_edge_count"], 4)
        self.assertEqual(report["decimation_protected_edge_fraction"], 0.5)
        self.assertEqual(report["uv_min"], [0.03125, 0.03125])
        self.assertEqual(report["uv_max"], [0.96875, 0.96875])
        self.assertEqual(report["degenerate_uv_triangle_count"], 0)
        self.assertEqual(report["mirrored_uv_triangle_count"], 0)
        self.assertLess(report["maximum_patch_aspect_distortion"], 1e-6)
        self.assertLess(report["mean_patch_aspect_distortion"], 1e-6)

    def test_basis_orientation_flat_box_and_sloped_surfaces(self) -> None:
        expected = {
            (1.0, 0.0, 0.0): ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
            (-1.0, 0.0, 0.0): ((0.0, -0.0, 1.0), (0.0, 1.0, 0.0)),
            (0.0, 0.0, 1.0): ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            (0.0, 0.0, -1.0): ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            (0.0, 1.0, 0.0): ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        }
        for normal, pair in expected.items():
            tangent, bitangent, _ = _basis(normal)
            for actual, wanted in zip(tangent + bitangent, pair[0] + pair[1], strict=True):
                self.assertAlmostEqual(actual, wanted, places=12)
        positions = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        normal = [(0.0, 0.0, 1.0)] * 4
        flat = generate_missing_uvs(_pack_no_uv(positions, normal, [(0, 1, 2), (0, 2, 3)]))
        self.assertEqual(flat["report"]["planar_patch_count"], 1)
        self.assertEqual(flat["report"]["uv_split_count"], 0)
        self.assertEqual(flat["report"]["mirrored_uv_triangle_count"], 0)
        cube_positions = [
            (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
        ]
        cube_normals = [_unit(value) for value in cube_positions]
        cube_triangles = [
            (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
            (0, 4, 7), (0, 7, 3), (1, 2, 6), (1, 6, 5),
            (0, 1, 5), (0, 5, 4), (3, 7, 6), (3, 6, 2),
        ]
        cube = generate_missing_uvs(_pack_no_uv(cube_positions, cube_normals, cube_triangles))
        self.assertEqual(cube["report"]["planar_patch_count"], 6)
        self.assertEqual(cube["report"]["degenerate_uv_triangle_count"], 0)
        self.assertEqual(cube["report"]["mirrored_uv_triangle_count"], 0)
        self.assertTrue(any(0.0 < patch["normal"][1] < 1.0 for patch in self.generated["report"]["patches"]))

    def test_source_order_and_translation_invariance(self) -> None:
        reversed_source, _ = build_stage4m_fixtures(reverse_faces=True)
        self.assertEqual(self.generated["canonical_glb"], generate_missing_uvs(reversed_source)["canonical_glb"])
        translated, _ = build_stage4m_fixtures(translation=(7.0, 2.0, -5.0))
        translated_result = generate_missing_uvs(translated)
        self.assertNotEqual(self.generated["canonical_glb"], translated_result["canonical_glb"])
        self.assertEqual(self.generated["canonical_mesh"].uvs, translated_result["canonical_mesh"].uvs)

    def test_padding_and_geometry_mutations_propagate_predictably(self) -> None:
        padded = generate_missing_uvs(SOURCE.read_bytes(), padding_texels=2)
        self.assertNotEqual(padded["canonical_glb"], self.generated["canonical_glb"])
        self.assertEqual(padded["canonical_mesh"].vertices, self.generated["canonical_mesh"].vertices)
        self.assertEqual(padded["canonical_mesh"].normals, self.generated["canonical_mesh"].normals)
        self.assertNotEqual(padded["canonical_mesh"].uvs, self.generated["canonical_mesh"].uvs)
        mutated, _ = build_stage4m_fixtures(roof_height=4.2)
        changed = generate_missing_uvs(mutated)
        self.assertNotEqual(changed["report"]["source_sha256"], self.generated["report"]["source_sha256"])
        self.assertNotEqual(changed["canonical_glb"], self.generated["canonical_glb"])
        self.assertEqual(self.compiled["manifest"]["id"], "stage4m_missing_uv_turret")
        self.assertEqual(self.compiled["collision"], self.reference["collision"])

    def test_topology_attribute_and_policy_failures_are_stable(self) -> None:
        positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 2.0, 0.0)]
        normals = [(0.0, 0.0, 1.0)] * 5
        winding_positions = positions[:3] + [(0.0, 2.0, 0.0)]
        cases = (
            (_pack_no_uv(positions, normals, [(0, 1, 2), (1, 0, 3), (0, 1, 4)]), "uv_generation_non_manifold"),
            (_pack_no_uv(winding_positions, normals[:4], [(0, 1, 2), (0, 1, 3)]), "uv_generation_inconsistent_winding"),
            (_pack_no_uv(positions[:3], normals[:3], [(0, 1, 1)]), "uv_generation_degenerate"),
            (_pack_no_uv(positions[:3], normals[:3], [(0, 1, 9)]), "invalid_indices"),
        )
        for source, code in cases:
            with self.subTest(code=code), self.assertRaises(UVGenerationError) as raised:
                generate_missing_uvs(source)
            self.assertEqual(raised.exception.code, code)
        for kwargs, code in (
            ({"padding_texels": 0}, "invalid_uv_padding"),
            ({"padding_texels": 9}, "invalid_uv_padding"),
            ({"patch_normal_degrees": 0}, "invalid_planarity_threshold"),
            ({"plane_epsilon": 0}, "invalid_planarity_threshold"),
        ):
            with self.subTest(code=code), self.assertRaises(UVGenerationError) as raised:
                generate_missing_uvs(SOURCE.read_bytes(), **kwargs)
            self.assertEqual(raised.exception.code, code)
        with self.assertRaises(UVGenerationError) as raised:
            generate_missing_uvs(REFERENCE.read_bytes())
        self.assertEqual(raised.exception.code, "uv_attribute_already_present")

    def test_missing_attributes_material_and_mode_remain_rejected(self) -> None:
        import struct
        from tools.pokeagent.glb import BIN_CHUNK, JSON_CHUNK, pack_glb
        data = SOURCE.read_bytes(); length, kind = struct.unpack_from("<II", data, 12); self.assertEqual(kind, JSON_CHUNK)
        document = json.loads(data[20:20 + length]); offset = 20 + length
        binary_length, binary_kind = struct.unpack_from("<II", data, offset); self.assertEqual(binary_kind, BIN_CHUNK)
        binary = data[offset + 8:offset + 8 + binary_length]
        mutations = (
            (lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("POSITION"), "missing_attribute"),
            (lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("NORMAL"), "missing_attribute"),
            (lambda d: d.update({"materials": []}), "unsupported_material"),
            (lambda d: d["meshes"][0]["primitives"][0].update({"mode": 5}), "unsupported_primitive_mode"),
        )
        for mutate, code in mutations:
            changed = copy.deepcopy(document); mutate(changed)
            with self.subTest(code=code), self.assertRaises(UVGenerationError) as raised:
                generate_missing_uvs(pack_glb(changed, binary))
            self.assertEqual(raised.exception.code, code)

    def test_stage4l_composition_outputs_cli_world_and_manifest_are_deterministic(self) -> None:
        no_normal, _ = build_stage4l_fixtures()
        stage4l_mesh = generate_missing_normals(no_normal)["canonical_mesh"]
        composition_source = _semantic_without_uv(stage4l_mesh)
        composition = generate_missing_uvs(composition_source)
        self.assertTrue(composition["report"]["stage4f_accepted"])
        self.assertEqual(set(stage4l_mesh.vertices), set(composition["canonical_mesh"].vertices))
        self.assertEqual(set(stage4l_mesh.normals), set(composition["canonical_mesh"].normals))
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            compile_asset_outputs(MANIFEST, Path(first), ROOT); compile_asset_outputs(MANIFEST, Path(second), ROOT)
            self.assertEqual((Path(first) / "uv-generated.glb").read_bytes(), (Path(second) / "uv-generated.glb").read_bytes())
            self.assertEqual((Path(first) / "uv-generation-report.json").read_bytes(), (Path(second) / "uv-generation-report.json").read_bytes())
        parsed = build_parser().parse_args(["asset", "uvs", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "uvs"))
        fixture = load_fixture(FIXTURE)
        self.assertEqual((fixture["schema_version"], fixture["artifact_namespace"]), (18, "stage4m"))
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as directory:
            manifest = json.loads(MANIFEST.read_text()); manifest.pop("preprocessing")
            path = Path(directory) / "missing-policy.json"; path.write_text(json.dumps(manifest))
            with self.assertRaises(AssetError) as raised: compile_asset(path, ROOT)
            self.assertEqual(raised.exception.code, "invalid_manifest")

    def test_stage4k_stage4l_hashes_and_stage4h_rejection_remain_invariant(self) -> None:
        stage4k = preprocess_static_glb((ROOT / "assets/source/stage4k_hierarchical_tower.glb").read_bytes())
        self.assertEqual(hashlib.sha256(stage4k["canonical_glb"]).hexdigest(), "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6")
        stage4l = generate_missing_normals((ROOT / "assets/source/stage4l_missing_normals_turret.glb").read_bytes())
        self.assertEqual(hashlib.sha256(stage4l["canonical_glb"]).hexdigest(), "b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9")
        raw = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"; before = raw.read_bytes()
        report = inspect_generated_asset(STAGE4H, ROOT)
        self.assertFalse(report["accepted"]); self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        self.assertFalse(report["stage4m"]["uv_generation"]["applicable"])
        self.assertFalse(report["stage4m"]["topology_subset"]["applicable"])
        self.assertEqual({item["code"] for item in report["stage4m"]["topology_subset"]["reasons"]}, {"uv_generation_face_budget", "uv_generation_accessor_budget"})
        self.assertFalse(report["stage4m"]["retroactive_approval"]); self.assertEqual(raw.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
