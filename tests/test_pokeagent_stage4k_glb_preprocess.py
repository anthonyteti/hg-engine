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
from tools.pokeagent.glb_preprocess import (
    GLBPreprocessError,
    _identity,
    _local_matrix,
    _multiply,
    inspect_static_hierarchy,
    preprocess_static_glb,
    transform_normal,
    transform_position,
)
from tools.pokeagent.stage4k_fixture import build_stage4k_fixtures
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/stage4k_hierarchical_tower.glb"
REFERENCE_SOURCE = ROOT / "assets/source/stage4k_flat_reference.glb"
BASE_SOURCE = ROOT / "assets/source/stage4f_glb_faceted_tower.glb"
MANIFEST = ROOT / "assets/manifests/stage4k_hierarchical_tower.json"
REFERENCE_MANIFEST = ROOT / "assets/manifests/stage4k_flat_reference.json"
FIXTURE = ROOT / "fixtures/stage4k_static_hierarchy_world.json"
STAGE4H = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"


def _unpack(data: bytes) -> tuple[dict[str, object], bytes]:
    length, kind = struct.unpack_from("<II", data, 12)
    assert kind == JSON_CHUNK
    document = json.loads(data[20:20 + length].decode("utf-8"))
    offset = 20 + length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    assert binary_kind == BIN_CHUNK
    return document, data[offset + 8:offset + 8 + binary_length]


class Stage4KStaticHierarchyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preprocessed = preprocess_static_glb(SOURCE.read_bytes())
        cls.compiled = compile_asset(MANIFEST, ROOT)

    def test_tracked_hierarchy_and_reference_are_reproducible(self) -> None:
        hierarchical, flat = build_stage4k_fixtures(BASE_SOURCE.read_bytes())
        self.assertEqual(SOURCE.read_bytes(), hierarchical)
        self.assertEqual(REFERENCE_SOURCE.read_bytes(), flat)
        self.assertEqual(flat, self.preprocessed["canonical_glb"])
        self.assertEqual(hashlib.sha256(hierarchical).hexdigest(), "3168b05b6b1373a2c12b6256a7df3c214dbae912664e9d06211d6a7ba8fb26d2")
        self.assertEqual(hashlib.sha256(flat).hexdigest(), "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6")

    def test_strict_stage4f_rejects_source_then_accepts_canonical_output(self) -> None:
        with self.assertRaises(GLBError) as raised:
            parse_glb(SOURCE.read_bytes())
        self.assertEqual(raised.exception.code, "unsupported_scene")
        canonical = parse_glb(self.preprocessed["canonical_glb"])
        self.assertEqual(len(canonical.faces), 12)
        report = self.preprocessed["report"]
        self.assertEqual(report["source_node_path"], [0, 1])
        self.assertEqual(report["canonical_node_count"], 1)
        self.assertEqual(report["canonical_transform"], "implicit_identity")
        self.assertTrue(report["stage4f_accepted"])

    def test_flat_reference_has_identical_semantic_ir_and_display_list(self) -> None:
        reference = compile_asset(REFERENCE_MANIFEST, ROOT)
        actual_ir, reference_ir = copy.deepcopy(self.compiled["ir"]), copy.deepcopy(reference["ir"])
        actual_ir.pop("asset_id"); reference_ir.pop("asset_id")
        self.assertEqual(actual_ir, reference_ir)
        self.assertEqual(self.compiled["display_list"], reference["display_list"])
        self.assertEqual(self.compiled["collision"], reference["collision"])
        self.assertEqual(self.compiled["textures"]["stage4d_stone"]["texture"], reference["textures"]["stage4d_stone"]["texture"])

    def test_golden_trs_position_normal_and_composition_math(self) -> None:
        identity = _identity()
        self.assertEqual(transform_position(identity, (1.0, 2.0, 3.0)), (1.0, 2.0, 3.0))
        self.assertEqual(transform_normal(identity, (0.0, 1.0, 0.0)), (0.0, 1.0, 0.0))
        q = math.sqrt(0.5)
        node = {"translation": [1.0, 2.0, 3.0], "rotation": [0.0, q, 0.0, q], "scale": [2.0, 3.0, 4.0]}
        matrix = _local_matrix(node, 0)
        position = transform_position(matrix, (1.0, 0.0, 0.0))
        normal = transform_normal(matrix, (1.0, 0.0, 0.0))
        for observed, expected in zip(position, (1.0, 2.0, 1.0), strict=True):
            self.assertAlmostEqual(observed, expected, places=6)
        for observed, expected in zip(normal, (0.0, 0.0, -1.0), strict=True):
            self.assertAlmostEqual(observed, expected, places=6)
        parent = _local_matrix({"translation": [2.0, 0.0, 0.0]}, 0)
        child = _local_matrix({"translation": [0.0, 3.0, 0.0]}, 1)
        self.assertEqual(transform_position(_multiply(parent, child), (0.0, 0.0, 0.0)), (2.0, 3.0, 0.0))

    def test_uv_material_indices_and_nonuniform_normal_transform_are_preserved(self) -> None:
        source = self.preprocessed["source_mesh"]
        canonical = self.preprocessed["canonical_mesh"]
        self.assertEqual([face.material for face in source.faces], [face.material for face in canonical.faces])
        self.assertEqual([len(face.corners) for face in source.faces], [len(face.corners) for face in canonical.faces])
        source_uv_faces = [[source.uvs[corner.uv] for corner in face.corners] for face in source.faces]
        canonical_uv_faces = [[canonical.uvs[corner.uv] for corner in face.corners] for face in canonical.faces]
        self.assertEqual(source_uv_faces, canonical_uv_faces)
        self.assertTrue(all(abs(math.sqrt(sum(value * value for value in normal)) - 1.0) < 1e-5 for normal in canonical.normals))

    def test_serialization_outputs_and_equivalent_identity_chain_are_deterministic(self) -> None:
        self.assertEqual(self.preprocessed, preprocess_static_glb(SOURCE.read_bytes()))
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            compile_asset_outputs(MANIFEST, Path(first), ROOT)
            compile_asset_outputs(MANIFEST, Path(second), ROOT)
            self.assertEqual((Path(first) / "preprocessed.glb").read_bytes(), (Path(second) / "preprocessed.glb").read_bytes())
            self.assertEqual((Path(first) / "preprocess-report.json").read_bytes(), (Path(second) / "preprocess-report.json").read_bytes())
        document, binary = _unpack(SOURCE.read_bytes())
        document["nodes"] = [document["nodes"][0], {"name": "identity", "children": [2]}, document["nodes"][1]]
        document["nodes"][0]["children"] = [1]
        equivalent = preprocess_static_glb(pack_glb(document, binary))
        self.assertEqual(equivalent["canonical_glb"], self.preprocessed["canonical_glb"])

    def test_transform_mutation_propagates_without_changing_owned_identity(self) -> None:
        document, binary = _unpack(SOURCE.read_bytes())
        document["nodes"][0]["scale"] = [1.3, 1.2, 1.0]
        hierarchical = pack_glb(document, binary)
        changed = preprocess_static_glb(hierarchical)
        self.assertNotEqual(changed["report"]["source_sha256"], self.preprocessed["report"]["source_sha256"])
        self.assertNotEqual(changed["canonical_glb"], self.preprocessed["canonical_glb"])
        document, _ = _unpack(hierarchical)
        self.assertEqual(document["meshes"][0]["primitives"][0]["material"], 0)
        self.assertEqual(self.compiled["manifest"]["id"], "stage4k_hierarchical_tower")
        self.assertEqual(self.compiled["collision"], {"min_x": -2.16, "max_x": 2.16, "min_z": -1.83, "max_z": 1.83})

    def test_bounded_scene_transform_and_attribute_failures_have_stable_codes(self) -> None:
        base_document, binary = _unpack(SOURCE.read_bytes())
        mutations = (
            (lambda d: d["scenes"].append({"nodes": [0]}), "unsupported_scene"),
            (lambda d: d.pop("scene"), "unsupported_scene"),
            (lambda d: d["nodes"][0].update({"children": [1, 1]}), "branching_node_hierarchy"),
            (lambda d: d["nodes"].append({"name": "disconnected"}), "disconnected_node_hierarchy"),
            (lambda d: d["nodes"][0].update({"matrix": [1, 0, 0, 0] * 4}), "unsupported_matrix_transform"),
            (lambda d: d["nodes"][0].update({"scale": [-1, 1, 1]}), "unsupported_reflective_transform"),
            (lambda d: d["nodes"][0].update({"scale": [0, 1, 1]}), "singular_transform"),
            (lambda d: d["nodes"][0].update({"translation": [float("inf"), 0, 0]}), "invalid_node_transform"),
            (lambda d: d["nodes"][0].update({"rotation": [0, 0, 0, 2]}), "invalid_quaternion"),
            (lambda d: d.update({"animations": [{}]}), "unsupported_animation"),
            (lambda d: d.update({"skins": [{}]}), "unsupported_skin"),
            (lambda d: d["meshes"][0]["primitives"][0].update({"targets": [{}]}), "unsupported_morph_targets"),
            (lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("NORMAL"), "missing_attribute"),
            (lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0"), "missing_attribute"),
            (lambda d: d.update({"materials": []}), "unsupported_material"),
            (lambda d: d["meshes"][0]["primitives"][0].update({"mode": 5}), "unsupported_primitive_mode"),
        )
        for mutate, code in mutations:
            with self.subTest(code=code):
                document = copy.deepcopy(base_document); mutate(document)
                with self.assertRaises(GLBPreprocessError) as raised:
                    preprocess_static_glb(pack_glb(document, binary))
                self.assertEqual(raised.exception.code, code)

    def test_stage4h_projection_closes_only_the_identity_hierarchy_gap(self) -> None:
        report = inspect_generated_asset(STAGE4H, ROOT)
        projection = report["stage4k"]["structure_preprocess"]
        self.assertTrue(projection["applicable"])
        self.assertEqual(projection["source_node_path"], [0, 1])
        self.assertEqual(projection["combined_determinant"], 1.0)
        self.assertFalse(report["accepted"])
        self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        remaining = set(report["stage4k"]["remaining_blockers"])
        self.assertTrue({"material_count_invalid", "missing_normal", "missing_texcoord_0", "ds_display_list_overflow"} <= remaining)

    def test_cli_fixture_and_manifest_policy_are_explicit(self) -> None:
        parsed = build_parser().parse_args(["asset", "preprocess", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "preprocess"))
        fixture = load_fixture(FIXTURE)
        self.assertEqual(fixture["schema_version"], 16)
        self.assertEqual(fixture["artifact_namespace"], "stage4k")
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as directory:
            data = json.loads(MANIFEST.read_text(encoding="utf-8"))
            data.pop("preprocessing")
            path = Path(directory) / "missing-policy.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(AssetError) as raised:
                compile_asset(path, ROOT)
        self.assertEqual(raised.exception.code, "invalid_manifest")


if __name__ == "__main__":
    unittest.main()
