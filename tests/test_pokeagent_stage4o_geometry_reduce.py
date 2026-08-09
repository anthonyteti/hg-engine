from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.assets import compile_asset
from tools.pokeagent.cli import build_parser
from tools.pokeagent.generated_intake import inspect_generated_asset
from tools.pokeagent.glb import BIN_CHUNK, GLBError, JSON_CHUNK, pack_glb, parse_glb
from tools.pokeagent.glb_geometry_reduce import (
    BOOTSTRAP_ENVELOPE,
    GeometryGLBError,
    inspect_geometry_applicability,
    load_geometry_manifest,
    pack_geometry_glb,
    parse_geometry_glb,
    reduce_geometry_manifest,
    write_geometry_outputs,
)
from tools.pokeagent.mesh_predecimate import GeometryReductionError, canonical_geometry, reduce_geometry, validate_geometry
from tools.pokeagent.stage4o_fixture import build_dense_geometry_shrine


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/stage4o_dense_geometry_shrine.glb"
MANIFEST = ROOT / "assets/manifests/stage4o_dense_geometry_shrine.json"
FAILURE = ROOT / "assets/manifests/stage4o_fidelity_failure.json"
STAGE4H_MANIFEST = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"
STAGE4H_RAW = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"


def _document_binary(data: bytes) -> tuple[dict[str, object], bytes]:
    length, kind = struct.unpack_from("<II", data, 12)
    if kind != JSON_CHUNK: raise AssertionError("JSON chunk missing")
    document = json.loads(data[20:20 + length])
    offset = 20 + length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    if binary_kind != BIN_CHUNK: raise AssertionError("BIN chunk missing")
    return document, data[offset + 8:offset + 8 + binary_length]


def _complete_reference(mesh: dict[str, object]) -> bytes:
    """Attach independent test attributes; this is not a production preprocessor."""
    positions = []
    normals = []
    uvs = []
    indices = []
    source_positions = mesh["positions"]
    for face in mesh["faces"]:
        triangle = [source_positions[index] for index in face]
        ab = tuple(triangle[1][axis] - triangle[0][axis] for axis in range(3))
        ac = tuple(triangle[2][axis] - triangle[0][axis] for axis in range(3))
        raw = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
        length = math.sqrt(sum(value * value for value in raw)); normal = tuple(value / length for value in raw)
        for point, uv in zip(triangle, ((0.0, 0.0), (0.0, 1.0), (1.0, 0.0)), strict=True):
            indices.append(len(positions)); positions.append(tuple(point)); normals.append(normal); uvs.append(uv)
    binary = bytearray(); views = []; accessors = []
    def append(values, fmt, kind, component, bounds=False):
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values: binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            accessor["min"] = [min(value[axis] for value in values) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in values) for axis in range(3)]
        accessors.append(accessor); return len(accessors) - 1
    p = append(positions, "<3f", "VEC3", 5126, True)
    n = append(normals, "<3f", "VEC3", 5126)
    uv = append(uvs, "<2f", "VEC2", 5126)
    ix = append(indices, "<H", "SCALAR", 5123)
    document = {
        "asset": {"generator": "stage4o-test-only-completion", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": p, "NORMAL": n, "TEXCOORD_0": uv}, "indices": ix, "material": 0, "mode": 4}]}],
        "materials": [{"name": "geometry_reference"}], "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views, "accessors": accessors,
    }
    return pack_glb(document, bytes(binary))


class Stage4OGeometryReductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = reduce_geometry_manifest(MANIFEST, ROOT)
        cls.policy = load_geometry_manifest(MANIFEST, ROOT)["preprocessing"]["geometry_reduction"]

    def test_fixture_is_reproducible_large_and_hash_locked(self) -> None:
        data = build_dense_geometry_shrine()
        self.assertEqual(data, SOURCE.read_bytes())
        self.assertEqual(hashlib.sha256(data).hexdigest(), "c37fac771cff1f5c77fd71bab27ea02631442f9260176ac0a0ef12aedcd6bcfc")
        parsed = parse_geometry_glb(data)
        self.assertEqual((parsed["topology"]["positions"], parsed["topology"]["triangles"]), (545, 1056))
        self.assertEqual((parsed["topology"]["connected_components"], parsed["topology"]["boundary_loops"]), (1, 1))

    def test_canonical_reduction_meets_predeclared_envelope_and_fidelity(self) -> None:
        report = self.result["report"]
        reduction = report["reduction"]
        self.assertEqual((reduction["final"]["positions"], reduction["final"]["triangles"]), (35, 64))
        self.assertEqual(reduction["accepted_collapses"], 510)
        self.assertEqual(report["canonical_sha256"], "7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957")
        metrics = reduction["metrics"]
        self.assertLessEqual(metrics["bounds_max_delta_ratio"], 0.04)
        self.assertLessEqual(metrics["maximum_geometric_error_ratio"], 0.08)
        self.assertLessEqual(metrics["surface_area_delta_percent"], 22.0)
        self.assertGreaterEqual(metrics["minimum_silhouette_iou"], 0.84)
        self.assertEqual((reduction["final"]["connected_components"], reduction["final"]["boundary_loops"]), (1, 1))

    def test_output_remains_geometry_only_and_stage4f_correctly_rejects_it(self) -> None:
        document, _binary = _document_binary(self.result["canonical_glb"])
        primitive = document["meshes"][0]["primitives"][0]
        self.assertEqual(set(primitive["attributes"]), {"POSITION"})
        self.assertNotIn("materials", document)
        self.assertNotIn("material", primitive)
        with self.assertRaises(GLBError) as raised:
            parse_glb(self.result["canonical_glb"])
        self.assertEqual(raised.exception.code, "unsupported_material")

    def test_controlled_independent_attributes_fit_strict_stage4f(self) -> None:
        completed = _complete_reference(self.result["geometry"])
        parsed = parse_glb(completed, {"max_accessor_elements": 256})
        self.assertEqual(len(parsed.faces), 64)
        self.assertLessEqual(len(self.result["geometry"]["positions"]), BOOTSTRAP_ENVELOPE["max_positions"])
        self.assertLessEqual(len(self.result["geometry"]["faces"]) * 3, BOOTSTRAP_ENVELOPE["max_accessor_elements"])

    def test_source_order_translation_and_uniform_scale_are_invariant(self) -> None:
        reversed_mesh = parse_geometry_glb(build_dense_geometry_shrine(reverse_faces=True))["geometry"]
        reversed_output, reversed_report = reduce_geometry(reversed_mesh, self.policy)
        self.assertEqual(pack_geometry_glb(reversed_output), self.result["canonical_glb"])
        self.assertEqual(reversed_report["semantic_sha256"], self.result["report"]["reduction"]["semantic_sha256"])
        translated = parse_geometry_glb(build_dense_geometry_shrine(translation=(100.0, -20.0, 7.0)))["geometry"]
        translated_output, _ = reduce_geometry(translated, self.policy)
        self.assertEqual(translated_output["faces"], self.result["geometry"]["faces"])
        for actual, expected in zip(translated_output["positions"], self.result["geometry"]["positions"], strict=True):
            self.assertTrue(all(abs((actual[axis] - (100.0, -20.0, 7.0)[axis]) - expected[axis]) < 2e-5 for axis in range(3)))
        scaled = parse_geometry_glb(build_dense_geometry_shrine(uniform_scale=3.0))["geometry"]
        scaled_output, _ = reduce_geometry(scaled, self.policy)
        self.assertEqual(scaled_output["faces"], self.result["geometry"]["faces"])
        for actual, expected in zip(scaled_output["positions"], self.result["geometry"]["positions"], strict=True):
            self.assertTrue(all(abs(actual[axis] / 3.0 - expected[axis]) < 2e-5 for axis in range(3)))

    def test_geometry_and_target_mutations_propagate_predictably(self) -> None:
        mutated = parse_geometry_glb(build_dense_geometry_shrine(roof_height=6.8))["geometry"]
        mutated_output, _ = reduce_geometry(mutated, self.policy)
        self.assertNotEqual(pack_geometry_glb(mutated_output), self.result["canonical_glb"])
        tighter = copy.deepcopy(self.policy); tighter.update({"target_faces": 48, "target_positions": 48})
        tighter_output, tighter_report = reduce_geometry(parse_geometry_glb(SOURCE.read_bytes())["geometry"], tighter)
        self.assertEqual((len(tighter_output["faces"]), len(tighter_output["positions"])), (48, 27))
        self.assertGreaterEqual(tighter_report["metrics"]["minimum_silhouette_iou"], tighter["min_silhouette_iou"])

    def test_fidelity_failure_refuses_destructive_target(self) -> None:
        with self.assertRaises(GeometryGLBError) as raised:
            reduce_geometry_manifest(FAILURE, ROOT)
        self.assertEqual(raised.exception.code, "geometry_predecimation_target_unreachable")
        self.assertIn("silhouette", raised.exception.details["violations"])
        self.assertGreater(raised.exception.details["best_valid_faces"], 12)

    def test_invalid_topology_auxiliary_transform_and_manifest_fail_stably(self) -> None:
        with self.assertRaises(GeometryReductionError) as raised:
            canonical_geometry([(0, 0, 0), (1, 0, 0), (2, 0, 0)], [(0, 1, 2)])
        self.assertEqual(raised.exception.code, "geometry_predecimation_degenerate")
        with self.assertRaises(GeometryReductionError) as raised:
            canonical_geometry([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2), (0, 1, 2)])
        self.assertEqual(raised.exception.code, "geometry_predecimation_duplicate_face")
        with self.assertRaises(GeometryReductionError) as raised:
            validate_geometry(canonical_geometry(
                [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0)],
                [(0, 1, 2), (0, 1, 3)],
            ))
        self.assertEqual(raised.exception.code, "geometry_predecimation_inconsistent_winding")
        with self.assertRaises(GeometryReductionError) as raised:
            validate_geometry(canonical_geometry(
                [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)],
                [(0, 1, 2), (1, 0, 3), (0, 1, 4)],
            ))
        self.assertEqual(raised.exception.code, "geometry_predecimation_non_manifold")
        document, binary = _document_binary(SOURCE.read_bytes())
        auxiliary = copy.deepcopy(document); auxiliary["meshes"][0]["primitives"][0]["attributes"]["COLOR_0"] = 0
        with self.assertRaises(GeometryGLBError) as raised:
            parse_geometry_glb(pack_glb(auxiliary, binary))
        self.assertEqual(raised.exception.code, "unsupported_geometry_aux_attribute")
        material = copy.deepcopy(document); material["materials"] = [{"name": "source_surface"}]
        material["meshes"][0]["primitives"][0]["material"] = 0
        with self.assertRaises(GeometryGLBError) as raised:
            parse_geometry_glb(pack_glb(material, binary))
        self.assertEqual(raised.exception.code, "unsupported_geometry_resource")
        transformed = copy.deepcopy(document); transformed["nodes"][0]["translation"] = [1, 0, 0]
        with self.assertRaises(GeometryGLBError) as raised:
            parse_geometry_glb(pack_glb(transformed, binary))
        self.assertEqual(raised.exception.code, "predecimation_requires_transform_bake")
        external = copy.deepcopy(document); external["buffers"][0]["uri"] = "file:///tmp/no"
        with self.assertRaises(GeometryGLBError) as raised:
            parse_geometry_glb(pack_glb(external, binary))
        self.assertEqual(raised.exception.code, "external_uri")
        with self.assertRaises(GeometryGLBError):
            parse_geometry_glb(b"bad")

    def test_outputs_cli_and_clean_runs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            one = write_geometry_outputs(MANIFEST, Path(first), ROOT)
            two = write_geometry_outputs(MANIFEST, Path(second), ROOT)
            for name in ("reduced-geometry.glb", "geometry-only-ir.json", "geometry-predecimation-report.json", "geometry-collapse-plan.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
            self.assertEqual(one["report_sha256"], two["report_sha256"])
        parsed = build_parser().parse_args(["asset", "geometry-reduce", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "geometry-reduce"))

    def test_stage4h_read_only_geometry_evidence_preserves_rejection(self) -> None:
        before = STAGE4H_RAW.read_bytes()
        projection = inspect_geometry_applicability(before)
        self.assertFalse(projection["topology_applicable"])
        self.assertFalse(projection["transformation_applicable"])
        self.assertTrue(projection["source_envelope_fit"])
        self.assertEqual(projection["auxiliary_attribute_blockers"], ["COLOR_0"])
        self.assertEqual(projection["topology"]["zero_area_triangles"], 1)
        self.assertEqual(projection["topology"]["connected_components"], 2)
        report = inspect_generated_asset(STAGE4H_MANIFEST, ROOT)
        self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        self.assertFalse(report["stage4o"]["retroactive_approval"])
        self.assertEqual(STAGE4H_RAW.read_bytes(), before)

    def test_stage4j_and_stage4n_regressions_are_exact(self) -> None:
        stage4j = compile_asset(ROOT / "assets/manifests/stage4j_dense_stone_shrine.json", ROOT)["report"]
        self.assertEqual(stage4j["display_list_bytes"], 4024)
        self.assertEqual(stage4j["hashes"]["display_list_sha256"], "e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04")
        stage4n = compile_asset(ROOT / "assets/manifests/stage4n_missing_material_turret.json", ROOT)["report"]
        self.assertEqual(stage4n["hashes"]["material_generated_glb_sha256"], "3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66")


if __name__ == "__main__":
    unittest.main()
