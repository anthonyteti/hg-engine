from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.assets import AssetError, compile_asset, compile_placements, parse_obj
from tools.pokeagent.glb import BIN_CHUNK, JSON_CHUNK, GLBError, pack_glb, parse_glb
from tools.pokeagent.geometry import inspect_mesh_display_list
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
OBJ_MANIFEST = ROOT / "assets/manifests/stage4e_faceted_tower.json"
OBJ_SOURCE = ROOT / "assets/source/stage4e_faceted_tower.obj"
GLB_MANIFEST = ROOT / "assets/manifests/stage4f_glb_faceted_tower.json"
GLB_SOURCE = ROOT / "assets/source/stage4f_glb_faceted_tower.glb"
CATALOG = ROOT / "assets/catalog.json"
FIXTURE = ROOT / "fixtures/stage4f_glb_world.json"


def _unpack_glb(data: bytes) -> tuple[dict[str, object], bytes]:
    offset = 12
    json_length, json_kind = struct.unpack_from("<II", data, offset)
    assert json_kind == JSON_CHUNK
    offset += 8
    document = json.loads(data[offset:offset + json_length].decode("utf-8"))
    offset += json_length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    assert binary_kind == BIN_CHUNK
    offset += 8
    return document, data[offset:offset + binary_length]


def _align(buffer: bytearray, alignment: int = 4) -> None:
    buffer.extend(b"\0" * (-len(buffer) % alignment))


def _tower_glb(
    *, apex: float = 6.0, interleaved: bool = False, index_component: int = 5123,
) -> bytes:
    """Build the tracked semantic tower using only deterministic struct packing."""
    mesh = parse_obj(OBJ_SOURCE.read_bytes())
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    for face in mesh.faces:
        corner_groups = (
            (face.corners[0], face.corners[1], face.corners[2]),
            (face.corners[0], face.corners[2], face.corners[3]),
        ) if face.primitive == "quad" else (face.corners,)
        for group in corner_groups:
            for corner in group:
                position = mesh.vertices[corner.vertex]
                if position == (0.0, 6.0, 0.0):
                    position = (0.0, apex, 0.0)
                positions.append(position)
                normals.append(mesh.normals[corner.normal])
                u, v = mesh.uvs[corner.uv]
                uvs.append((u, 1.0 - v))  # glTF's upper-left UV convention.

    component = {5121: ("B", 1), 5123: ("H", 2), 5125: ("I", 4)}[index_component]
    binary = bytearray()
    views: list[dict[str, int]] = []
    accessors: list[dict[str, object]] = []

    if interleaved:
        offset = len(binary)
        for position, normal, uv in zip(positions, normals, uvs, strict=True):
            binary.extend(struct.pack("<3f3f2f", *position, *normal, *uv))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset, "byteStride": 32})
        accessors.extend((
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": len(positions), "type": "VEC3",
             "min": [min(value[axis] for value in positions) for axis in range(3)],
             "max": [max(value[axis] for value in positions) for axis in range(3)]},
            {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "count": len(normals), "type": "VEC3"},
            {"bufferView": 0, "byteOffset": 24, "componentType": 5126, "count": len(uvs), "type": "VEC2"},
        ))
    else:
        for values, components, accessor_type in ((positions, 3, "VEC3"), (normals, 3, "VEC3"), (uvs, 2, "VEC2")):
            _align(binary)
            offset = len(binary)
            for value in values:
                binary.extend(struct.pack("<" + "f" * components, *value))
            views.append({
                "buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset,
                "target": 34962,
            })
            accessor: dict[str, object] = {
                "bufferView": len(views) - 1, "byteOffset": 0, "componentType": 5126,
                "count": len(values), "type": accessor_type,
            }
            if accessor_type == "VEC3" and values is positions:
                accessor["min"] = [min(value[axis] for value in positions) for axis in range(3)]
                accessor["max"] = [max(value[axis] for value in positions) for axis in range(3)]
            accessors.append(accessor)

    _align(binary, component[1])
    index_offset = len(binary)
    for index in range(len(positions)):
        binary.extend(struct.pack("<" + component[0], index))
    views.append({
        "buffer": 0, "byteOffset": index_offset, "byteLength": len(binary) - index_offset,
        "target": 34963,
    })
    accessors.append({
        "bufferView": len(views) - 1, "byteOffset": 0, "componentType": index_component,
        "count": len(positions), "type": "SCALAR",
    })
    document = {
        "asset": {"generator": "pokeagent-stage4f-proof", "version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "stage4f_glb_tower"}],
        "meshes": [{"name": "stage4f_glb_tower", "primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
            "indices": 3, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": "faceted_shell"}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def _semantic_triangles(ir: dict[str, object]) -> list[object]:
    vertices = ir["vertices"]
    uvs = ir["uvs"]
    result = []
    for face in ir["faces"]:
        corners = list(zip(face["vertices"], face["uvs"], strict=True))
        groups = (corners[:3], [corners[0], corners[2], corners[3]]) if face["primitive"] == "quad" else (corners,)
        for group in groups:
            result.append({
                "corners": [
                    ([round(value, 6) for value in vertices[position]], [round(value, 6) for value in uvs[uv]])
                    for position, uv in group
                ],
                "normal": [round(value, 6) for value in face["normal"]],
                "source_material": face["source_material"],
                "material_alias": face["material_alias"],
                "texture": face["texture"],
            })
    return result


class TemporaryGLBAsset:
    def __init__(self, source: bytes | None = None) -> None:
        self.source_context = tempfile.TemporaryDirectory(dir=ROOT / "assets/source")
        self.manifest_context = tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests")
        self.source = Path(self.source_context.name) / "probe.glb"
        self.manifest_path = Path(self.manifest_context.name) / "probe.json"
        self.source.write_bytes(source if source is not None else GLB_SOURCE.read_bytes())
        self.manifest = json.loads(GLB_MANIFEST.read_text(encoding="utf-8"))
        self.manifest["source"] = self.source.relative_to(ROOT).as_posix()
        self.write_manifest()

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def close(self) -> None:
        self.manifest_context.cleanup()
        self.source_context.cleanup()


class Stage4FGLBTests(unittest.TestCase):
    def test_canonical_glb_is_deterministic_and_uses_existing_triangle_path(self) -> None:
        self.assertEqual(GLB_SOURCE.read_bytes(), _tower_glb())
        compiled = compile_asset(GLB_MANIFEST, ROOT)
        report = compiled["report"]
        self.assertEqual(report["source_format"], "glb")
        self.assertEqual(report["source_details"]["scene_count"], 1)
        self.assertEqual(report["source_details"]["primitive_count"], 1)
        self.assertEqual(report["source_details"]["accessor_count"], 4)
        self.assertEqual(report["source_counts"], {"vertices": 9, "uvs": 5, "normals": 8, "faces": 12})
        self.assertEqual(report["normalized_counts"], {"vertices": 9, "faces": 12, "quads": 0, "triangles": 12})
        self.assertEqual(report["emitted_vertex_count"], 36)
        self.assertEqual(report["display_list_bytes"], 828)
        self.assertEqual(report["shape"], 6)
        inspected = inspect_mesh_display_list(compiled["display_list"])
        self.assertEqual((inspected["triangle_count"], inspected["quad_count"]), (12, 0))
        self.assertEqual(compiled["ir"], compile_asset(GLB_MANIFEST, ROOT)["ir"])

    def test_obj_and_glb_normalize_to_semantically_equivalent_towers(self) -> None:
        obj = compile_asset(OBJ_MANIFEST, ROOT)
        glb = compile_asset(GLB_MANIFEST, ROOT)
        self.assertEqual(_semantic_triangles(obj["ir"]), _semantic_triangles(glb["ir"]))
        self.assertEqual(obj["ir"]["bounds"], glb["ir"]["bounds"])
        self.assertEqual(obj["ir"]["dimensions"], glb["ir"]["dimensions"])
        self.assertEqual(obj["collision"], glb["collision"])
        self.assertEqual(obj["textures"]["stage4d_stone"]["texture"], glb["textures"]["stage4d_stone"]["texture"])
        self.assertNotEqual(obj["display_list"], glb["display_list"])

    def test_tightly_packed_interleaved_and_unsigned_index_accessors(self) -> None:
        baseline = parse_glb(_tower_glb())
        for index_component in (5121, 5123, 5125):
            with self.subTest(index_component=index_component):
                candidate = parse_glb(_tower_glb(index_component=index_component))
                self.assertEqual(candidate.vertices, baseline.vertices)
                self.assertEqual(candidate.uvs, baseline.uvs)
                self.assertEqual(candidate.normals, baseline.normals)
                self.assertEqual(candidate.faces, baseline.faces)
        interleaved = parse_glb(_tower_glb(interleaved=True))
        self.assertEqual(interleaved.vertices, baseline.vertices)
        self.assertEqual(interleaved.uvs, baseline.uvs)
        self.assertEqual(interleaved.normals, baseline.normals)
        self.assertEqual(interleaved.faces, baseline.faces)

        document, binary = _unpack_glb(_tower_glb())
        document["meshes"][0]["primitives"].append(
            copy.deepcopy(document["meshes"][0]["primitives"][0]),
        )
        repeated = parse_glb(pack_glb(document, binary))
        self.assertEqual(len(repeated.faces), 24)
        self.assertEqual(
            [(face.material, face.corners) for face in repeated.faces[:12]],
            [(face.material, face.corners) for face in repeated.faces[12:]],
        )

    def test_header_chunk_and_uri_failures_have_stable_codes(self) -> None:
        canonical = GLB_SOURCE.read_bytes()
        document, binary = _unpack_glb(canonical)
        variants = []
        variants.append((b"BAD!" + canonical[4:], "invalid_glb_magic"))
        wrong_version = bytearray(canonical)
        struct.pack_into("<I", wrong_version, 4, 1)
        variants.append((bytes(wrong_version), "invalid_glb_version"))
        wrong_length = bytearray(canonical)
        struct.pack_into("<I", wrong_length, 8, len(canonical) - 4)
        variants.append((bytes(wrong_length), "malformed_glb_length"))
        variants.append((pack_glb(document, b""), "missing_bin_chunk"))
        external = copy.deepcopy(document)
        external["buffers"][0]["uri"] = "https://example.invalid/mesh.bin"
        variants.append((pack_glb(external, binary), "external_uri"))
        for payload, code in variants:
            with self.subTest(code=code):
                with self.assertRaises(GLBError) as raised:
                    parse_glb(payload)
                self.assertEqual(raised.exception.code, code)

    def test_scene_feature_and_primitive_rejections_are_bounded(self) -> None:
        document, binary = _unpack_glb(GLB_SOURCE.read_bytes())
        mutations = (
            (lambda data: data["nodes"][0].update({"translation": [0, 0, 0]}), "unsupported_node_transform"),
            (lambda data: data["scenes"].append({"nodes": [0]}), "unsupported_scene"),
            (lambda data: data["meshes"].append(copy.deepcopy(data["meshes"][0])), "unsupported_mesh_count"),
            (lambda data: data.update({"animations": [{}]}), "unsupported_animation"),
            (lambda data: data.update({"skins": [{}]}), "unsupported_skin"),
            (lambda data: data.update({"cameras": [{"type": "perspective"}]}), "unsupported_camera"),
            (lambda data: data.update({"images": [{}]}), "embedded_texture"),
            (lambda data: data["meshes"][0]["primitives"][0].update({"mode": 5}), "unsupported_primitive_mode"),
            (lambda data: data["meshes"][0]["primitives"][0]["attributes"].pop("NORMAL"), "missing_attribute"),
            (lambda data: data["meshes"][0]["primitives"][0].update({"targets": [{}]}), "unsupported_morph_targets"),
            (lambda data: data["materials"][0].update({"pbrMetallicRoughness": {}}), "unsupported_material"),
        )
        for mutation, code in mutations:
            with self.subTest(code=code):
                changed = copy.deepcopy(document)
                mutation(changed)
                with self.assertRaises(GLBError) as raised:
                    parse_glb(pack_glb(changed, binary))
                self.assertEqual(raised.exception.code, code)

    def test_accessor_bounds_stride_sparse_and_indices_are_validated(self) -> None:
        document, binary = _unpack_glb(GLB_SOURCE.read_bytes())
        mutations = (
            (lambda data: data["accessors"][0].pop("min"), "invalid_accessor_bounds"),
            (lambda data: data["accessors"][0].update({"componentType": 5123}), "unsupported_accessor_component_type"),
            (lambda data: data["accessors"][0].update({"sparse": {}}), "unsupported_sparse_accessor"),
            (lambda data: data["accessors"][0].update({"count": 257}), "accessor_over_budget"),
            (lambda data: data["bufferViews"][0].update({"byteStride": 6}), "invalid_byte_stride"),
            (lambda data: data["bufferViews"][0].update({"byteOffset": len(binary)}), "buffer_view_out_of_bounds"),
            (lambda data: data["accessors"][3].update({"count": 35}), "invalid_indices"),
        )
        for mutation, code in mutations:
            with self.subTest(code=code):
                changed = copy.deepcopy(document)
                mutation(changed)
                with self.assertRaises(GLBError) as raised:
                    parse_glb(pack_glb(changed, binary))
                self.assertEqual(raised.exception.code, code)

    def test_shared_validation_rejects_winding_degeneracy_material_and_capacity(self) -> None:
        document, binary = _unpack_glb(GLB_SOURCE.read_bytes())
        index_view = document["bufferViews"][3]
        index_offset = index_view["byteOffset"]
        reversed_binary = bytearray(binary)
        first, second = struct.unpack_from("<HH", reversed_binary, index_offset)
        struct.pack_into("<HH", reversed_binary, index_offset, second, first)
        temporary = TemporaryGLBAsset(pack_glb(document, bytes(reversed_binary)))
        try:
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "normal_winding_mismatch")
        finally:
            temporary.close()

        degenerate_binary = bytearray(binary)
        position_view = document["bufferViews"][0]
        first_position = bytes(degenerate_binary[position_view["byteOffset"]:position_view["byteOffset"] + 12])
        second_position = position_view["byteOffset"] + 12
        degenerate_binary[second_position:second_position + 12] = first_position
        temporary = TemporaryGLBAsset(pack_glb(document, bytes(degenerate_binary)))
        try:
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "degenerate_face")
        finally:
            temporary.close()

        wrong_material = copy.deepcopy(document)
        wrong_material["materials"][0]["name"] = "unmapped"
        temporary = TemporaryGLBAsset(pack_glb(wrong_material, binary))
        try:
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "unsupported_material")
        finally:
            temporary.close()

        placements = [
            {"id": "tower_west", "asset": "stage4f_glb_faceted_tower", "x": 8, "z": 16, "rotation": 0},
            {"id": "tower_east", "asset": "stage4f_glb_faceted_tower", "x": 24, "z": 16, "rotation": 90},
        ]
        with self.assertRaises(AssetError) as raised:
            compile_placements(CATALOG, placements, ROOT)
        self.assertEqual(raised.exception.code, "display_list_overflow")

    def test_glb_apex_mutation_propagates_only_through_geometry(self) -> None:
        temporary = TemporaryGLBAsset(_tower_glb())
        try:
            before = compile_asset(temporary.manifest_path, ROOT)
            temporary.source.write_bytes(_tower_glb(apex=6.5))
            after = compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(before["manifest"]["id"], after["manifest"]["id"])
            self.assertNotEqual(before["report"]["source_sha256"], after["report"]["source_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["normalized_mesh_sha256"], after["report"]["hashes"]["normalized_mesh_sha256"])
            self.assertNotEqual(before["display_list"], after["display_list"])
            self.assertEqual(before["report"]["hashes"]["collision_sha256"], after["report"]["hashes"]["collision_sha256"])
            for texture_id in before["textures"]:
                self.assertEqual(before["textures"][texture_id]["texture"], after["textures"][texture_id]["texture"])
                self.assertEqual(before["textures"][texture_id]["palette"], after["textures"][texture_id]["palette"])
        finally:
            temporary.close()

    def test_stage4f_fixture_remains_symbolic_and_registry_resolved(self) -> None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIsInstance(source["model"]["area_data"], str)
        self.assertEqual(source["assets"][0]["asset"], "stage4f_glb_faceted_tower")
        resolved = load_fixture(FIXTURE)
        self.assertEqual(resolved["schema_version"], 12)
        self.assertEqual(resolved["artifact_namespace"], "stage4f")
        self.assertEqual(resolved["model"]["area_data"], 106)


if __name__ == "__main__":
    unittest.main()
