from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.assets import AssetError, compile_asset, compile_asset_outputs, parse_obj
from tools.pokeagent.glb import pack_glb
from tools.pokeagent.geometry import inspect_mesh_display_list
from tools.pokeagent.mesh_simplify import SimplificationError, simplify_coplanar_ir
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
LOW_MANIFEST = ROOT / "assets/manifests/stage4f_glb_faceted_tower.json"
DENSE_MANIFEST = ROOT / "assets/manifests/stage4g_dense_faceted_tower.json"
DENSE_SOURCE = ROOT / "assets/source/stage4g_dense_faceted_tower.glb"
OBJ_SOURCE = ROOT / "assets/source/stage4e_faceted_tower.obj"
FIXTURE = ROOT / "fixtures/stage4g_simplified_world.json"


def _mix(values: tuple[tuple[float, ...], ...], weights: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(sum(weights[index] * values[index][axis] for index in range(len(values))) for axis in range(len(values[0])))


def _dense_tower_glb(*, apex: float = 6.0) -> bytes:
    """Build a valid 48-triangle tower with redundant exact subdivisions."""
    mesh = parse_obj(OBJ_SOURCE.read_bytes())
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []

    def emit(corners: tuple[tuple[float, float, float], ...], texcoords: tuple[tuple[float, float], ...], normal: tuple[float, float, float]) -> None:
        positions.extend(corners)
        normals.extend((normal,) * 3)
        uvs.extend((uv[0], 1.0 - uv[1]) for uv in texcoords)

    for face in mesh.faces:
        face_positions = tuple(mesh.vertices[corner.vertex] for corner in face.corners)
        face_positions = tuple((x, apex if (x, y, z) == (0.0, 6.0, 0.0) else y, z) for x, y, z in face_positions)
        face_uvs = tuple(mesh.uvs[corner.uv] for corner in face.corners)
        normal = mesh.normals[face.corners[0].normal]
        if face.primitive == "quad":
            grid: dict[tuple[int, int], tuple[tuple[float, ...], tuple[float, ...]]] = {}
            for row in range(3):
                for column in range(3):
                    s, t = column / 2, row / 2
                    weights = ((1 - s) * (1 - t), s * (1 - t), s * t, (1 - s) * t)
                    grid[(column, row)] = (_mix(face_positions, weights), _mix(face_uvs, weights))
            for row in range(2):
                for column in range(2):
                    a, b = grid[(column, row)], grid[(column + 1, row)]
                    c, d = grid[(column + 1, row + 1)], grid[(column, row + 1)]
                    emit((a[0], b[0], c[0]), (a[1], b[1], c[1]), normal)
                    emit((a[0], c[0], d[0]), (a[1], c[1], d[1]), normal)
        else:
            a, b, c = face_positions
            ua, ub, uc = face_uvs
            ab, bc, ca = _mix((a, b), (0.5, 0.5)), _mix((b, c), (0.5, 0.5)), _mix((c, a), (0.5, 0.5))
            uab, ubc, uca = _mix((ua, ub), (0.5, 0.5)), _mix((ub, uc), (0.5, 0.5)), _mix((uc, ua), (0.5, 0.5))
            emit((a, ab, ca), (ua, uab, uca), normal)
            emit((ab, b, bc), (uab, ub, ubc), normal)
            emit((ca, bc, c), (uca, ubc, uc), normal)
            emit((ab, bc, ca), (uab, ubc, uca), normal)

    binary = bytearray()
    views: list[dict[str, int]] = []
    accessors: list[dict[str, object]] = []
    for values, components, accessor_type in ((positions, 3, "VEC3"), (normals, 3, "VEC3"), (uvs, 2, "VEC2")):
        binary.extend(b"\0" * (-len(binary) % 4))
        offset = len(binary)
        for value in values:
            binary.extend(struct.pack("<" + "f" * components, *value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset, "target": 34962})
        accessor: dict[str, object] = {
            "bufferView": len(views) - 1, "byteOffset": 0, "componentType": 5126,
            "count": len(values), "type": accessor_type,
        }
        if values is positions:
            accessor["min"] = [min(value[axis] for value in values) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in values) for axis in range(3)]
        accessors.append(accessor)
    binary.extend(b"\0" * (-len(binary) % 2))
    index_offset = len(binary)
    for index in range(len(positions)):
        binary.extend(struct.pack("<H", index))
    views.append({"buffer": 0, "byteOffset": index_offset, "byteLength": len(binary) - index_offset, "target": 34963})
    accessors.append({
        "bufferView": len(views) - 1, "byteOffset": 0, "componentType": 5123,
        "count": len(positions), "type": "SCALAR",
    })
    document = {
        "asset": {"generator": "pokeagent-stage4g-proof", "version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "stage4g_dense_faceted_tower"}],
        "meshes": [{"name": "stage4g_dense_faceted_tower", "primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
            "indices": 3, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": "faceted_shell"}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


class TemporaryDenseAsset:
    def __init__(self, source: bytes | None = None) -> None:
        self.source_context = tempfile.TemporaryDirectory(dir=ROOT / "assets/source")
        self.manifest_context = tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests")
        self.source = Path(self.source_context.name) / "probe.glb"
        self.manifest_path = Path(self.manifest_context.name) / "probe.json"
        self.source.write_bytes(source if source is not None else DENSE_SOURCE.read_bytes())
        self.manifest = json.loads(DENSE_MANIFEST.read_text(encoding="utf-8"))
        self.manifest["source"] = self.source.relative_to(ROOT).as_posix()
        self.write()

    def write(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def close(self) -> None:
        self.manifest_context.cleanup()
        self.source_context.cleanup()


def _face_geometry(ir: dict[str, object]) -> list[object]:
    result = []
    for face in ir["faces"]:
        result.append({
            "corners": sorted((
                tuple(round(value, 6) for value in ir["vertices"][vertex]),
                tuple(round(value, 6) for value in ir["uvs"][uv]),
            ) for vertex, uv in zip(face["vertices"], face["uvs"], strict=True)),
            "normal": tuple(round(value, 6) for value in face["normal"]),
            "material": face["material_alias"],
            "texture": face["texture"],
        })
    return sorted(result, key=repr)


class Stage4GSimplificationTests(unittest.TestCase):
    def test_dense_canonical_source_overflows_then_simplifies_exactly(self) -> None:
        self.assertEqual(DENSE_SOURCE.read_bytes(), _dense_tower_glb())
        compiled = compile_asset(DENSE_MANIFEST, ROOT)
        report = compiled["report"]
        self.assertEqual(report["source_normalized_counts"]["triangles"], 48)
        self.assertGreater(report["simplification"]["source_projected_display_list_bytes"], 1068)
        self.assertGreater(report["simplification"]["source_overflow_bytes"], 0)
        self.assertEqual(report["normalized_counts"]["triangles"], 4)
        self.assertEqual(report["normalized_counts"]["quads"], 4)
        self.assertLessEqual(report["display_list_bytes"], 1068)
        self.assertEqual(report["simplification"]["geometry_preservation"]["bounds_exact"], True)
        self.assertEqual(report["simplification"]["geometry_preservation"]["surface_area_delta"], 0.0)
        inspected = inspect_mesh_display_list(compiled["display_list"])
        self.assertEqual((inspected["triangle_count"], inspected["quad_count"]), (4, 4))

    def test_simplified_dense_tower_matches_low_poly_semantics(self) -> None:
        dense = compile_asset(DENSE_MANIFEST, ROOT)
        low = compile_asset(LOW_MANIFEST, ROOT)
        self.assertEqual(dense["ir"]["bounds"], low["ir"]["bounds"])
        self.assertEqual(dense["ir"]["dimensions"], low["ir"]["dimensions"])
        self.assertEqual(_face_geometry(dense["ir"]), _face_geometry(compile_asset(ROOT / "assets/manifests/stage4e_faceted_tower.json", ROOT)["ir"]))
        self.assertEqual(dense["collision"], low["collision"])
        self.assertEqual(dense["textures"]["stage4d_stone"]["texture"], low["textures"]["stage4d_stone"]["texture"])

    def test_manifest_is_opt_in_and_legacy_dense_source_still_fails(self) -> None:
        temporary = TemporaryDenseAsset()
        try:
            temporary.manifest["schema_version"] = 5
            temporary.manifest.pop("simplification")
            temporary.manifest["budget"] = "stage4b_proof"
            temporary.write()
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "faces_over_budget")
        finally:
            temporary.close()

    def test_invalid_and_unreachable_targets_fail_with_stable_codes(self) -> None:
        temporary = TemporaryDenseAsset()
        try:
            temporary.manifest["simplification"]["reserve_bytes"] = 700
            temporary.write()
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "simplification_target_unreachable")
            temporary.manifest["simplification"]["reserve_bytes"] = -1
            temporary.write()
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "invalid_target_budget")
            temporary.manifest["simplification"]["reserve_bytes"] = 0
            temporary.manifest["simplification"]["preserve_uv_seams"] = False
            temporary.write()
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "unsupported_simplification_policy")
        finally:
            temporary.close()

    def test_compile_outputs_materialize_source_and_simplified_ir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = compile_asset_outputs(DENSE_MANIFEST, Path(directory), ROOT)
            self.assertEqual(report["outputs"]["normalized_mesh"], "normalized-mesh.json")
            self.assertEqual(report["outputs"]["simplified_mesh"], "simplified-mesh.json")
            self.assertNotEqual(
                (Path(directory) / "normalized-mesh.json").read_bytes(),
                (Path(directory) / "simplified-mesh.json").read_bytes(),
            )

    def test_output_is_stable_and_unsupported_topology_fails_before_encoding(self) -> None:
        first = compile_asset(DENSE_MANIFEST, ROOT)
        second = compile_asset(DENSE_MANIFEST, ROOT)
        self.assertEqual(first["ir"], second["ir"])
        self.assertEqual(first["display_list"], second["display_list"])
        self.assertEqual(first["report"]["simplification"], second["report"]["simplification"])

        low_quad_ir = compile_asset(ROOT / "assets/manifests/stage4e_faceted_tower.json", ROOT)["ir"]
        with self.assertRaises(SimplificationError) as raised:
            simplify_coplanar_ir(low_quad_ir)
        self.assertEqual(raised.exception.code, "simplification_unsupported_primitive")

    def test_nonmanifold_triangle_input_fails_with_stable_code(self) -> None:
        source = compile_asset(DENSE_MANIFEST, ROOT)["source_ir"]
        malformed = copy.deepcopy(source)
        malformed["faces"].append(copy.deepcopy(malformed["faces"][0]))
        with self.assertRaises(SimplificationError) as raised:
            simplify_coplanar_ir(malformed)
        self.assertEqual(raised.exception.code, "simplification_nonmanifold")

    def test_source_mutation_propagates_without_touching_texture_or_collision(self) -> None:
        temporary = TemporaryDenseAsset(_dense_tower_glb())
        try:
            before = compile_asset(temporary.manifest_path, ROOT)
            temporary.source.write_bytes(_dense_tower_glb(apex=6.5))
            after = compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(before["manifest"]["id"], after["manifest"]["id"])
            self.assertNotEqual(before["report"]["source_sha256"], after["report"]["source_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["normalized_source_mesh_sha256"], after["report"]["hashes"]["normalized_source_mesh_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["normalized_mesh_sha256"], after["report"]["hashes"]["normalized_mesh_sha256"])
            self.assertNotEqual(before["display_list"], after["display_list"])
            self.assertEqual(before["report"]["hashes"]["collision_sha256"], after["report"]["hashes"]["collision_sha256"])
            self.assertEqual(before["textures"]["stage4d_stone"]["texture"], after["textures"]["stage4d_stone"]["texture"])
            self.assertEqual(before["textures"]["stage4d_stone"]["palette"], after["textures"]["stage4d_stone"]["palette"])
        finally:
            temporary.close()

    def test_stage4g_fixture_is_symbolic_and_resolved(self) -> None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIsInstance(source["model"]["area_data"], str)
        self.assertEqual(source["assets"][0]["asset"], "stage4g_dense_faceted_tower")
        resolved = load_fixture(FIXTURE)
        self.assertEqual(resolved["schema_version"], 13)
        self.assertEqual(resolved["artifact_namespace"], "stage4g")


if __name__ == "__main__":
    unittest.main()
