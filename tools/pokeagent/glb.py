"""Deterministic parser for the bounded Stage 4F static GLB 2.0 subset."""

from __future__ import annotations

import json
import math
import struct
from typing import Any

from .asset_source import MeshCorner, MeshFace, SourceMesh


GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
GLB_LIMITS = {
    "max_source_bytes": 262_144,
    "max_nodes": 1,
    "max_meshes": 1,
    "max_primitives": 4,
    "max_accessors": 16,
    "max_buffer_views": 16,
    "max_accessor_elements": 256,
    "max_buffer_bytes": 262_144,
}
_COMPONENTS = {
    5121: ("B", 1),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}


class GLBError(ValueError):
    """The GLB does not fit the exact offline static-mesh subset."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def pack_glb(document: dict[str, Any], binary: bytes) -> bytes:
    """Pack deterministic JSON/BIN chunks; used by bounded fixtures and tests."""
    json_data = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    json_data += b" " * (-len(json_data) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(json_data) + (8 + len(binary) if binary else 0)
    output = bytearray(struct.pack("<4sII", GLB_MAGIC, GLB_VERSION, total))
    output += struct.pack("<II", len(json_data), JSON_CHUNK) + json_data
    if binary:
        output += struct.pack("<II", len(binary), BIN_CHUNK) + binary
    return bytes(output)


def _integer(value: object, code: str, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GLBError(code, f"{field} must be an integer >= {minimum}")
    return value


def _array(document: dict[str, Any], key: str, code: str, *, maximum: int, exact: int | None = None) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list) or (exact is not None and len(value) != exact) or len(value) > maximum:
        expected = f"exactly {exact}" if exact is not None else f"at most {maximum}"
        raise GLBError(code, f"GLB {key} must contain {expected} entries")
    return value


def _chunks(data: bytes, limits: dict[str, int]) -> tuple[dict[str, Any], bytes]:
    if len(data) > limits["max_source_bytes"]:
        raise GLBError("source_too_large", "GLB exceeds the bounded source byte budget")
    if len(data) < 20:
        raise GLBError("malformed_glb_length", "GLB is shorter than its header and JSON chunk")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != GLB_MAGIC:
        raise GLBError("invalid_glb_magic", "GLB magic must be ASCII glTF")
    if version != GLB_VERSION:
        raise GLBError("invalid_glb_version", "only GLB container version 2 is supported")
    if declared_length != len(data):
        raise GLBError("malformed_glb_length", "GLB header length disagrees with the file length")
    chunks: list[tuple[int, bytes]] = []
    offset = 12
    while offset < len(data):
        if offset % 4 or offset + 8 > len(data):
            raise GLBError("malformed_chunk_length", "GLB chunk header is truncated or misaligned")
        length, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if length % 4 or offset + length > len(data):
            raise GLBError("malformed_chunk_length", "GLB chunk length is misaligned or out of bounds")
        chunks.append((kind, data[offset:offset + length]))
        offset += length
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise GLBError("missing_json_chunk", "GLB JSON must be the first chunk")
    if len(chunks) < 2 or chunks[1][0] != BIN_CHUNK:
        raise GLBError("missing_bin_chunk", "bounded static GLB requires one embedded BIN chunk")
    if len(chunks) != 2:
        raise GLBError("unsupported_glb_chunk", "bounded static GLB accepts only JSON and BIN chunks")
    try:
        document = json.loads(chunks[0][1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GLBError("invalid_glb_json", "GLB JSON chunk is not valid UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise GLBError("invalid_glb_json", "GLB JSON root must be an object")
    return document, chunks[1][1]


def _validate_document(document: dict[str, Any], binary: bytes, limits: dict[str, int]) -> dict[str, list[Any]]:
    asset = document.get("asset")
    if not isinstance(asset, dict) or asset.get("version") != "2.0" or asset.get("minVersion") not in (None, "2.0"):
        raise GLBError("invalid_gltf_version", "GLB JSON asset must target glTF 2.0")
    if document.get("extensionsUsed") or document.get("extensionsRequired"):
        raise GLBError("unsupported_gltf_extension", "glTF extensions are outside the Stage 4F subset")
    for key, code in (("animations", "unsupported_animation"), ("skins", "unsupported_skin")):
        if document.get(key):
            raise GLBError(code, f"GLB {key} are unsupported")
    if document.get("cameras"):
        raise GLBError("unsupported_camera", "GLB cameras are outside the static-mesh source subset")
    if any(document.get(key) for key in ("images", "textures", "samplers")):
        raise GLBError("embedded_texture", "GLB images/textures are disallowed; use the project PNG catalog")

    scenes = _array(document, "scenes", "unsupported_scene", maximum=1, exact=1)
    nodes = _array(document, "nodes", "unsupported_scene", maximum=limits["max_nodes"], exact=1)
    meshes = _array(document, "meshes", "unsupported_mesh_count", maximum=limits["max_meshes"], exact=1)
    materials = _array(document, "materials", "unsupported_material", maximum=1, exact=1)
    accessors = _array(document, "accessors", "unsupported_accessor_count", maximum=limits["max_accessors"])
    views = _array(document, "bufferViews", "unsupported_buffer_view_count", maximum=limits["max_buffer_views"])
    buffers = _array(document, "buffers", "unsupported_buffer_count", maximum=1, exact=1)

    if document.get("scene", 0) != 0 or not isinstance(scenes[0], dict) or scenes[0].get("nodes") != [0]:
        raise GLBError("unsupported_scene", "GLB must select one scene with node 0 as its only root")
    node = nodes[0]
    if not isinstance(node, dict) or node.get("mesh") != 0 or node.get("children"):
        raise GLBError("unsupported_scene", "GLB must contain one leaf mesh node")
    if any(key in node for key in ("matrix", "translation", "rotation", "scale")):
        raise GLBError("unsupported_node_transform", "Stage 4F requires an implicit identity node transform")
    if "camera" in node:
        raise GLBError("unsupported_camera", "mesh nodes may not select a GLB camera")
    if any(key in node for key in ("skin", "weights")):
        raise GLBError("unsupported_skin", "skin, weights, and morph state are unsupported")

    material = materials[0]
    if not isinstance(material, dict) or set(material) != {"name"} or not isinstance(material["name"], str):
        raise GLBError("unsupported_material", "GLB material must contain only one source name")
    buffer = buffers[0]
    if not isinstance(buffer, dict) or set(buffer) - {"byteLength", "name"}:
        raise GLBError("external_uri", "GLB buffer must be the embedded buffer without a URI")
    byte_length = _integer(buffer.get("byteLength"), "invalid_buffer", "buffer.byteLength", minimum=1)
    if byte_length > limits["max_buffer_bytes"] or len(binary) < byte_length or len(binary) > byte_length + 3:
        raise GLBError("invalid_buffer", "GLB BIN length disagrees with its declared buffer length")
    if any(binary[byte_length:]):
        raise GLBError("invalid_buffer_padding", "GLB BIN alignment padding must be zero")

    for index, view in enumerate(views):
        if not isinstance(view, dict) or view.get("buffer") != 0:
            raise GLBError("buffer_view_out_of_bounds", f"bufferView {index} must reference embedded buffer 0")
        offset = _integer(view.get("byteOffset", 0), "buffer_view_out_of_bounds", f"bufferView {index}.byteOffset")
        length = _integer(view.get("byteLength"), "buffer_view_out_of_bounds", f"bufferView {index}.byteLength", minimum=1)
        if offset + length > byte_length:
            raise GLBError("buffer_view_out_of_bounds", f"bufferView {index} exceeds the embedded buffer")
        if "byteStride" in view:
            stride = _integer(view["byteStride"], "invalid_byte_stride", f"bufferView {index}.byteStride", minimum=4)
            if stride > 252 or stride % 4:
                raise GLBError("invalid_byte_stride", f"bufferView {index} byteStride must be a 4-byte multiple in 4..252")
    return {
        "scenes": scenes, "nodes": nodes, "meshes": meshes, "materials": materials,
        "accessors": accessors, "views": views, "buffers": buffers,
    }


def _decode_accessor(
    accessor_index: object,
    expected_type: str,
    allowed_components: set[int],
    arrays: dict[str, list[Any]],
    binary: bytes,
    *,
    indices: bool = False,
    require_bounds: bool = False,
    max_elements: int = GLB_LIMITS["max_accessor_elements"],
) -> tuple[tuple[float | int, ...], ...]:
    index = _integer(accessor_index, "invalid_accessor", "accessor index")
    if index >= len(arrays["accessors"]):
        raise GLBError("invalid_accessor", f"accessor {index} does not exist")
    accessor = arrays["accessors"][index]
    if not isinstance(accessor, dict):
        raise GLBError("invalid_accessor", f"accessor {index} must be an object")
    if "sparse" in accessor:
        raise GLBError("unsupported_sparse_accessor", f"accessor {index} uses sparse storage")
    component_type = accessor.get("componentType")
    accessor_type = accessor.get("type")
    if component_type not in allowed_components or accessor_type != expected_type:
        raise GLBError(
            "unsupported_accessor_component_type",
            f"accessor {index} must use {expected_type} with one of {sorted(allowed_components)}",
        )
    if accessor.get("normalized", False) is not False:
        raise GLBError("unsupported_normalized_accessor", f"accessor {index} must not be normalized")
    count = _integer(accessor.get("count"), "invalid_accessor", f"accessor {index}.count", minimum=1)
    if count > max_elements:
        raise GLBError("accessor_over_budget", f"accessor {index} exceeds the element budget")
    view_index = _integer(accessor.get("bufferView"), "invalid_accessor", f"accessor {index}.bufferView")
    if view_index >= len(arrays["views"]):
        raise GLBError("invalid_accessor", f"accessor {index} references a missing bufferView")
    view = arrays["views"][view_index]
    format_code, component_size = _COMPONENTS[component_type]
    components = _TYPE_COMPONENTS[accessor_type]
    element_size = component_size * components
    if indices and "byteStride" in view:
        raise GLBError("invalid_byte_stride", "index accessors must be tightly packed")
    stride = view.get("byteStride", element_size)
    if not isinstance(stride, int) or stride < element_size:
        raise GLBError("invalid_byte_stride", f"accessor {index} stride is smaller than its element")
    accessor_offset = _integer(accessor.get("byteOffset", 0), "accessor_out_of_bounds", f"accessor {index}.byteOffset")
    view_offset = int(view.get("byteOffset", 0))
    view_length = int(view["byteLength"])
    if (view_offset + accessor_offset) % component_size:
        raise GLBError("invalid_accessor_alignment", f"accessor {index} is not component-aligned")
    required = accessor_offset + (count - 1) * stride + element_size
    if required > view_length:
        raise GLBError("accessor_out_of_bounds", f"accessor {index} exceeds bufferView {view_index}")
    values: list[tuple[float | int, ...]] = []
    fmt = "<" + format_code * components
    for element in range(count):
        value = struct.unpack_from(fmt, binary, view_offset + accessor_offset + element * stride)
        if any(isinstance(component, float) and not math.isfinite(component) for component in value):
            raise GLBError("nonfinite_coordinate", f"accessor {index} contains NaN or infinity")
        values.append(tuple(value))
    has_min, has_max = "min" in accessor, "max" in accessor
    if has_min != has_max or (require_bounds and not has_min):
        raise GLBError("invalid_accessor_bounds", f"accessor {index} must declare matching min/max bounds")
    if expected_type == "VEC3" and component_type == 5126 and has_min:
        observed_min = [min(float(value[axis]) for value in values) for axis in range(3)]
        observed_max = [max(float(value[axis]) for value in values) for axis in range(3)]
        for declared, observed, label in ((accessor["min"], observed_min, "min"), (accessor["max"], observed_max, "max")):
            if (
                not isinstance(declared, list) or len(declared) != 3
                or any(not isinstance(value, (int, float)) or abs(float(value) - observed[axis]) > 1e-6 for axis, value in enumerate(declared))
            ):
                raise GLBError("invalid_accessor_bounds", f"accessor {index} {label} does not match decoded data")
    return tuple(values)


def parse_glb(data: bytes, limits: dict[str, int] | None = None) -> SourceMesh:
    """Parse one static, identity-node, indexed-triangle GLB into neutral mesh records."""
    active_limits = {**GLB_LIMITS, **(limits or {})}
    document, binary = _chunks(data, active_limits)
    arrays = _validate_document(document, binary, active_limits)
    mesh = arrays["meshes"][0]
    if not isinstance(mesh, dict) or mesh.get("weights") is not None:
        raise GLBError("unsupported_morph_targets", "mesh weights and morph targets are unsupported")
    primitives = mesh.get("primitives")
    if not isinstance(primitives, list) or not primitives or len(primitives) > active_limits["max_primitives"]:
        raise GLBError("unsupported_primitive_count", "mesh must contain 1..4 triangle primitives")

    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    normals: list[tuple[float, float, float]] = []
    vertex_ids: dict[tuple[float, float, float], int] = {}
    uv_ids: dict[tuple[float, float], int] = {}
    normal_ids: dict[tuple[float, float, float], int] = {}
    faces: list[MeshFace] = []
    accessor_roles: list[dict[str, object]] = []

    def intern(value: tuple[float, ...], values: list[Any], ids: dict[Any, int]) -> int:
        if value not in ids:
            ids[value] = len(values)
            values.append(value)
        return ids[value]

    for primitive_index, primitive in enumerate(primitives):
        if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
            raise GLBError("unsupported_primitive_mode", "Stage 4F accepts independent TRIANGLES mode 4 only")
        if primitive.get("targets") is not None:
            raise GLBError("unsupported_morph_targets", "primitive morph targets are unsupported")
        attributes = primitive.get("attributes")
        required = {"POSITION", "NORMAL", "TEXCOORD_0"}
        if not isinstance(attributes, dict) or set(attributes) != required:
            missing = sorted(required - set(attributes or {})) if isinstance(attributes, dict) else sorted(required)
            raise GLBError("missing_attribute", f"primitive {primitive_index} requires only POSITION/NORMAL/TEXCOORD_0; missing={missing}")
        positions = _decode_accessor(
            attributes["POSITION"], "VEC3", {5126}, arrays, binary, require_bounds=True,
            max_elements=active_limits["max_accessor_elements"],
        )
        primitive_normals = _decode_accessor(attributes["NORMAL"], "VEC3", {5126}, arrays, binary, max_elements=active_limits["max_accessor_elements"])
        primitive_uvs = _decode_accessor(attributes["TEXCOORD_0"], "VEC2", {5126}, arrays, binary, max_elements=active_limits["max_accessor_elements"])
        primitive_indices = _decode_accessor(
            primitive.get("indices"), "SCALAR", {5121, 5123, 5125}, arrays, binary,
            indices=True, max_elements=active_limits["max_accessor_elements"],
        )
        if len(positions) != len(primitive_normals) or len(positions) != len(primitive_uvs):
            raise GLBError("attribute_count_mismatch", "POSITION/NORMAL/TEXCOORD_0 counts must match")
        for normal in primitive_normals:
            length = math.sqrt(sum(float(component) ** 2 for component in normal))
            if abs(length - 1.0) > 1e-5:
                raise GLBError("invalid_normal", "glTF NORMAL vectors must have unit length")
        flat_indices = [int(value[0]) for value in primitive_indices]
        if len(flat_indices) % 3:
            raise GLBError("invalid_indices", "triangle index count must be divisible by three")
        if any(index >= len(positions) for index in flat_indices):
            raise GLBError("invalid_indices", "triangle index references an out-of-range vertex")
        material_index = _integer(primitive.get("material"), "unsupported_material", "primitive.material")
        if material_index >= len(arrays["materials"]):
            raise GLBError("unsupported_material", "primitive material index is out of range")
        material_name = arrays["materials"][material_index]["name"]
        for corner_offset in range(0, len(flat_indices), 3):
            corners: list[MeshCorner] = []
            for raw_index in flat_indices[corner_offset:corner_offset + 3]:
                position = tuple(float(value) for value in positions[raw_index])
                normal = tuple(float(value) for value in primitive_normals[raw_index])
                uv = tuple(float(value) for value in primitive_uvs[raw_index])
                corners.append(MeshCorner(
                    intern(position, vertices, vertex_ids),
                    intern(uv, uvs, uv_ids),
                    intern(normal, normals, normal_ids),
                ))
            faces.append(MeshFace(f"face_{len(faces):03d}", material_name, tuple(corners)))
        accessor_roles.append({
            "primitive": primitive_index,
            "position": attributes["POSITION"], "normal": attributes["NORMAL"],
            "texcoord_0": attributes["TEXCOORD_0"], "indices": primitive["indices"],
            "source_vertices": len(positions), "triangles": len(flat_indices) // 3,
        })
    if not faces:
        raise GLBError("malformed_mesh", "GLB mesh contains no triangles")
    return SourceMesh(
        tuple(vertices), tuple(uvs), tuple(normals), tuple(faces),
        {
            "source_format": "glb", "uv_origin": "upper_left", "glb_version": 2,
            "scene_count": 1, "node_count": 1, "mesh_count": 1,
            "primitive_count": len(primitives), "accessor_count": len(arrays["accessors"]),
            "buffer_view_count": len(arrays["views"]), "buffer_bytes": arrays["buffers"][0]["byteLength"],
            "accessors": accessor_roles,
        },
    )
