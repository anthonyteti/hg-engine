"""Bounded deterministic static GLB hierarchy flattening for Stage 4K."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
from typing import Any

from .asset_source import SourceMesh
from .glb import GLBError, _chunks, pack_glb, parse_glb


PREPROCESS_LIMITS = {
    "max_source_bytes": 262_144,
    "max_nodes": 4,
    "max_depth": 4,
    "max_meshes": 1,
    "max_primitives": 4,
    "max_accessors": 16,
    "max_buffer_views": 16,
    "max_accessor_elements": 256,
    "max_buffer_bytes": 262_144,
}


class GLBPreprocessError(ValueError):
    """A GLB cannot be reduced to the strict Stage 4F contract."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _finite_vector(value: object, size: int, field: str, default: tuple[float, ...]) -> tuple[float, ...]:
    if value is None:
        return default
    if (
        not isinstance(value, list) or len(value) != size
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in value)
    ):
        raise GLBPreprocessError("invalid_node_transform", f"{field} must contain {size} finite numbers")
    return tuple(float(item) for item in value)


def _identity() -> tuple[tuple[float, ...], ...]:
    return (
        (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0),
    )


def _multiply(a: tuple[tuple[float, ...], ...], b: tuple[tuple[float, ...], ...]) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(sum(a[row][k] * b[k][column] for k in range(4)) for column in range(4)) for row in range(4))


def _local_matrix(node: dict[str, Any], index: int) -> tuple[tuple[float, ...], ...]:
    if "matrix" in node:
        raise GLBPreprocessError("unsupported_matrix_transform", f"node {index} uses matrix; Stage 4K accepts TRS only")
    allowed = {"name", "children", "mesh", "translation", "rotation", "scale"}
    if set(node) - allowed:
        raise GLBPreprocessError("unsupported_node_property", f"node {index} contains unsupported properties")
    translation = _finite_vector(node.get("translation"), 3, f"node {index}.translation", (0.0, 0.0, 0.0))
    scale = _finite_vector(node.get("scale"), 3, f"node {index}.scale", (1.0, 1.0, 1.0))
    if any(value <= 0.0 for value in scale):
        code = "unsupported_reflective_transform" if any(value < 0.0 for value in scale) else "singular_transform"
        raise GLBPreprocessError(code, f"node {index} scale must be strictly positive")
    quaternion = _finite_vector(node.get("rotation"), 4, f"node {index}.rotation", (0.0, 0.0, 0.0, 1.0))
    length = math.sqrt(sum(value * value for value in quaternion))
    if abs(length - 1.0) > 1e-6:
        raise GLBPreprocessError("invalid_quaternion", f"node {index} rotation must be a unit XYZW quaternion")
    x, y, z, w = quaternion
    rotation = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0.0),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0.0),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    scaling = (
        (scale[0], 0.0, 0.0, 0.0), (0.0, scale[1], 0.0, 0.0),
        (0.0, 0.0, scale[2], 0.0), (0.0, 0.0, 0.0, 1.0),
    )
    transform = _multiply(rotation, scaling)
    return (
        (transform[0][0], transform[0][1], transform[0][2], translation[0]),
        (transform[1][0], transform[1][1], transform[1][2], translation[1]),
        (transform[2][0], transform[2][1], transform[2][2], translation[2]),
        transform[3],
    )


def _determinant3(matrix: tuple[tuple[float, ...], ...]) -> float:
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _inverse3(matrix: tuple[tuple[float, ...], ...]) -> tuple[tuple[float, ...], ...]:
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    determinant = _determinant3(matrix)
    if determinant <= 1e-9:
        code = "unsupported_reflective_transform" if determinant < 0 else "singular_transform"
        raise GLBPreprocessError(code, "combined world transform must have a positive nonsingular determinant", determinant=determinant)
    return (
        ((e * i - f * h) / determinant, (c * h - b * i) / determinant, (b * f - c * e) / determinant),
        ((f * g - d * i) / determinant, (a * i - c * g) / determinant, (c * d - a * f) / determinant),
        ((d * h - e * g) / determinant, (b * g - a * h) / determinant, (a * e - b * d) / determinant),
    )


def transform_position(matrix: tuple[tuple[float, ...], ...], value: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(sum(matrix[row][column] * value[column] for column in range(3)) + matrix[row][3] for row in range(3))


def transform_normal(matrix: tuple[tuple[float, ...], ...], value: tuple[float, float, float]) -> tuple[float, float, float]:
    inverse = _inverse3(matrix)
    transformed = tuple(sum(inverse[column][row] * value[column] for column in range(3)) for row in range(3))
    length = math.sqrt(sum(component * component for component in transformed))
    if length <= 1e-9:
        raise GLBPreprocessError("invalid_transformed_normal", "normal inverse-transpose produced a zero vector")
    return tuple(component / length for component in transformed)


def _hierarchy(document: dict[str, Any]) -> tuple[list[int], tuple[tuple[float, ...], ...]]:
    if document.get("extensionsUsed") or document.get("extensionsRequired"):
        raise GLBPreprocessError("unsupported_gltf_extension", "Stage 4K accepts no glTF extensions")
    for key, code in (("animations", "unsupported_animation"), ("skins", "unsupported_skin")):
        if document.get(key):
            raise GLBPreprocessError(code, f"Stage 4K rejects {key}")
    scenes = document.get("scenes")
    nodes = document.get("nodes")
    meshes = document.get("meshes")
    if not isinstance(scenes, list) or len(scenes) != 1 or document.get("scene") != 0:
        raise GLBPreprocessError("unsupported_scene", "Stage 4K requires exactly one selected scene")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= PREPROCESS_LIMITS["max_nodes"]:
        raise GLBPreprocessError("unsupported_node_count", "Stage 4K accepts 1..4 nodes")
    if not isinstance(meshes, list) or len(meshes) != 1:
        raise GLBPreprocessError("unsupported_mesh_count", "Stage 4K requires exactly one mesh")
    roots = scenes[0].get("nodes") if isinstance(scenes[0], dict) else None
    if not isinstance(roots, list) or len(roots) != 1 or not isinstance(roots[0], int):
        raise GLBPreprocessError("unsupported_scene_roots", "selected scene must have one root node")
    path: list[int] = []
    visited: set[int] = set()
    current = roots[0]
    world = _identity()
    while True:
        if current in visited:
            raise GLBPreprocessError("cyclic_node_hierarchy", "node hierarchy contains a cycle")
        if not 0 <= current < len(nodes) or not isinstance(nodes[current], dict):
            raise GLBPreprocessError("invalid_node_reference", "node hierarchy references a missing node")
        visited.add(current); path.append(current)
        node = nodes[current]
        world = _multiply(world, _local_matrix(node, current))
        children = node.get("children", [])
        if not isinstance(children, list) or any(not isinstance(child, int) for child in children):
            raise GLBPreprocessError("invalid_node_reference", f"node {current} children must be node indices")
        if len(children) > 1:
            raise GLBPreprocessError("branching_node_hierarchy", "Stage 4K accepts one unique parent chain")
        has_mesh = "mesh" in node
        if has_mesh and node.get("mesh") != 0:
            raise GLBPreprocessError("unsupported_mesh_count", "mesh-bearing leaf must reference mesh 0")
        if children:
            if has_mesh:
                raise GLBPreprocessError("branching_mesh_hierarchy", "only the leaf node may own the mesh")
            current = children[0]
            continue
        if not has_mesh:
            raise GLBPreprocessError("missing_mesh_node", "hierarchy leaf must own the mesh")
        break
    if len(path) != len(nodes):
        raise GLBPreprocessError("disconnected_node_hierarchy", "all nodes must belong to the unique root-to-mesh chain")
    determinant = _determinant3(world)
    if determinant <= 1e-9:
        code = "unsupported_reflective_transform" if determinant < 0 else "singular_transform"
        raise GLBPreprocessError(code, "combined transform must have a positive determinant", determinant=determinant)
    return path, world


def _canonical_glb(mesh: SourceMesh, world: tuple[tuple[float, ...], ...], material: str) -> bytes:
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    indices: list[int] = []
    for face in mesh.faces:
        for corner in face.corners:
            positions.append(transform_position(world, mesh.vertices[corner.vertex]))
            normals.append(transform_normal(world, mesh.normals[corner.normal]))
            uvs.append(mesh.uvs[corner.uv])
            indices.append(len(indices))
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[Any], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values:
            binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            packed = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in values]
            accessor["min"] = [min(value[axis] for value in packed) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in packed) for axis in range(3)]
        accessors.append(accessor)
        return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, True)
    n = append(normals, "<3f", "VEC3", 5126)
    uv = append(uvs, "<2f", "VEC2", 5126)
    index_component, index_fmt = (5121, "<B") if len(indices) <= 255 else (5123, "<H")
    ix = append(indices, index_fmt, "SCALAR", index_component)
    document = {
        "asset": {"generator": "pokeagent-stage4k-canonical-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "canonical_static_mesh"}],
        "meshes": [{"name": "canonical_static_mesh", "primitives": [{
            "attributes": {"POSITION": p, "NORMAL": n, "TEXCOORD_0": uv},
            "indices": ix, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": material}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def preprocess_static_glb(data: bytes) -> dict[str, Any]:
    """Flatten one supported static node chain and emit strict Stage 4F GLB."""
    try:
        document, binary = _chunks(data, PREPROCESS_LIMITS)
    except GLBError as error:
        raise GLBPreprocessError(error.code, str(error), **error.details) from error
    path, world = _hierarchy(document)
    validation_document = copy.deepcopy(document)
    validation_document["scene"] = 0
    validation_document["scenes"] = [{"nodes": [0]}]
    validation_document["nodes"] = [{"mesh": 0, "name": "stage4k_validation"}]
    try:
        source_mesh = parse_glb(pack_glb(validation_document, binary))
    except GLBError as error:
        raise GLBPreprocessError(error.code, str(error), **error.details) from error
    material_names = {face.material for face in source_mesh.faces}
    if len(material_names) != 1:
        raise GLBPreprocessError("unsupported_material", "Stage 4K requires exactly one named material")
    canonical = _canonical_glb(source_mesh, world, next(iter(material_names)))
    try:
        accepted = parse_glb(canonical)
    except GLBError as error:
        raise GLBPreprocessError("invalid_canonical_output", str(error), stage4f_code=error.code) from error
    determinant = _determinant3(world)
    report_core = {
        "schema_version": 1, "success": True,
        "preprocess_limits": dict(PREPROCESS_LIMITS),
        "source_sha256": _sha256(data), "canonical_sha256": _sha256(canonical),
        "source_size_bytes": len(data), "canonical_size_bytes": len(canonical),
        "source_node_count": len(document["nodes"]), "source_node_path": path,
        "source_mesh_count": len(document["meshes"]),
        "source_primitive_count": len(document["meshes"][0]["primitives"]),
        "combined_world_matrix": [[round(value, 12) for value in row] for row in world],
        "combined_determinant": round(determinant, 12),
        "canonical_node_count": 1, "canonical_transform": "implicit_identity",
        "position_count": len(accepted.vertices), "normal_count": len(accepted.normals),
        "uv_count": len(accepted.uvs), "face_count": len(accepted.faces),
        "uv_semantics_preserved": True, "index_topology_preserved": True,
        "material": next(iter(material_names)), "stage4f_accepted": True,
    }
    semantic = json.dumps(report_core, sort_keys=True, separators=(",", ":")).encode()
    report_core["report_sha256"] = _sha256(semantic)
    return {"canonical_glb": canonical, "source_mesh": source_mesh, "canonical_mesh": accepted, "report": report_core}


def inspect_static_hierarchy(data: bytes) -> dict[str, Any]:
    """Read-only structural applicability projection without touching attributes."""
    try:
        document, _binary = _chunks(data, PREPROCESS_LIMITS)
        path, world = _hierarchy(document)
    except (GLBError, GLBPreprocessError) as error:
        return {
            "applicable": False, "resulting_node_count": None,
            "error": {"code": error.code, "message": str(error), "details": error.details},
        }
    return {
        "applicable": True, "resulting_node_count": 1, "source_node_path": path,
        "combined_world_matrix": [[round(value, 12) for value in row] for row in world],
        "combined_determinant": round(_determinant3(world), 12), "error": None,
    }
