"""Deterministic planar-patch UV generation for bounded hard-surface GLBs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct
from typing import Any

from .glb import GLBError, _chunks, _decode_accessor, _integer, _validate_document, pack_glb, parse_glb


UV_LIMITS = {
    "max_source_bytes": 262_144,
    "max_nodes": 1,
    "max_meshes": 1,
    "max_primitives": 4,
    "max_accessors": 16,
    "max_buffer_views": 16,
    "max_accessor_elements": 256,
    "max_buffer_bytes": 262_144,
    "max_faces": 80,
    "max_patches": 64,
    "max_adjacency_edges": 256,
}
CANONICAL_PATCH_NORMAL_DEGREES = 0.1
CANONICAL_PLANE_EPSILON = 1e-5
CANONICAL_TEXTURE_SIZE = 32
CANONICAL_PADDING_TEXELS = 1


class UVGenerationError(ValueError):
    """Source geometry cannot safely acquire UV0 under the bounded policy."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class _Corner:
    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    source_attribute: tuple[int, int]


@dataclass(frozen=True)
class _Face:
    material: str
    corners: tuple[_Corner, _Corner, _Corner]
    area_vector: tuple[float, float, float]
    unit_normal: tuple[float, float, float]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(a[index] - b[index] for index in range(3))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(left * right for left, right in zip(a, b, strict=True))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(value: tuple[float, float, float], code: str = "uv_generation_invalid_basis") -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    if not math.isfinite(length) or length <= 1e-12:
        raise UVGenerationError(code, "UV projection produced a zero or non-finite vector")
    result = tuple(component / length for component in value)
    if any(not math.isfinite(component) for component in result):
        raise UVGenerationError(code, "UV projection produced NaN or infinity")
    return result


def _face_key(face: _Face) -> tuple[object, ...]:
    return (face.material, tuple((corner.position, corner.normal) for corner in face.corners))


def _decode_no_uv_source(data: bytes) -> tuple[list[_Face], str, int, dict[str, object]]:
    try:
        document, binary = _chunks(data, UV_LIMITS)
        arrays = _validate_document(document, binary, UV_LIMITS)
    except GLBError as error:
        raise UVGenerationError(error.code, str(error), **error.details) from error
    mesh = arrays["meshes"][0]
    if not isinstance(mesh, dict) or mesh.get("weights") is not None:
        raise UVGenerationError("unsupported_morph_targets", "UV generation rejects mesh weights and morphs")
    primitives = mesh.get("primitives")
    if not isinstance(primitives, list) or not 1 <= len(primitives) <= UV_LIMITS["max_primitives"]:
        raise UVGenerationError("unsupported_primitive_count", "UV generation accepts 1..4 triangle primitives")
    faces: list[_Face] = []
    referenced_attributes: set[tuple[int, int]] = set()
    for primitive_index, primitive in enumerate(primitives):
        if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
            raise UVGenerationError("unsupported_primitive_mode", "UV generation accepts TRIANGLES mode 4 only")
        if primitive.get("targets") is not None:
            raise UVGenerationError("unsupported_morph_targets", "UV generation rejects morph targets")
        attributes = primitive.get("attributes")
        if isinstance(attributes, dict) and "TEXCOORD_0" in attributes:
            raise UVGenerationError("uv_attribute_already_present", "missing-UV policy never replaces authored UV0")
        required = {"POSITION", "NORMAL"}
        if not isinstance(attributes, dict) or set(attributes) != required:
            missing = sorted(required - set(attributes or {})) if isinstance(attributes, dict) else sorted(required)
            raise UVGenerationError("missing_attribute", f"UV source requires only POSITION/NORMAL; missing={missing}")
        try:
            positions = _decode_accessor(
                attributes["POSITION"], "VEC3", {5126}, arrays, binary, require_bounds=True,
                max_elements=UV_LIMITS["max_accessor_elements"],
            )
            normals = _decode_accessor(
                attributes["NORMAL"], "VEC3", {5126}, arrays, binary,
                max_elements=UV_LIMITS["max_accessor_elements"],
            )
            indices = _decode_accessor(
                primitive.get("indices"), "SCALAR", {5121, 5123, 5125}, arrays, binary,
                indices=True, max_elements=UV_LIMITS["max_accessor_elements"],
            )
        except GLBError as error:
            raise UVGenerationError(error.code, str(error), **error.details) from error
        if len(positions) != len(normals):
            raise UVGenerationError("attribute_count_mismatch", "POSITION and NORMAL counts must match")
        for normal in normals:
            length = math.sqrt(sum(float(component) ** 2 for component in normal))
            if not math.isfinite(length) or abs(length - 1.0) > 1e-5:
                raise UVGenerationError("invalid_normal", "source NORMAL vectors must be finite unit vectors")
        flat_indices = [int(value[0]) for value in indices]
        if len(flat_indices) % 3:
            raise UVGenerationError("invalid_indices", "triangle index count must be divisible by three")
        if any(index >= len(positions) for index in flat_indices):
            raise UVGenerationError("invalid_indices", "triangle index is out of range")
        material_index = _integer(primitive.get("material"), "unsupported_material", "primitive.material")
        if material_index >= len(arrays["materials"]):
            raise UVGenerationError("unsupported_material", "primitive material index is out of range")
        material = arrays["materials"][material_index]["name"]
        for offset in range(0, len(flat_indices), 3):
            raw = flat_indices[offset:offset + 3]
            corners = tuple(
                _Corner(
                    tuple(float(value) for value in positions[index]),
                    tuple(float(value) for value in normals[index]),
                    (primitive_index, index),
                )
                for index in raw
            )
            if len({corner.position for corner in corners}) != 3:
                raise UVGenerationError("uv_generation_degenerate", "triangle repeats a geometric vertex")
            area = _cross(_sub(corners[1].position, corners[0].position), _sub(corners[2].position, corners[0].position))
            geometric_normal = _normalize(area, "uv_generation_degenerate")
            if any(_dot(corner.normal, geometric_normal) < 0.5 for corner in corners):
                raise UVGenerationError("normal_winding_mismatch", "authored normal disagrees with triangle winding")
            faces.append(_Face(material, corners, area, geometric_normal))
            referenced_attributes.update(corner.source_attribute for corner in corners)
    if not faces or len(faces) > UV_LIMITS["max_faces"]:
        raise UVGenerationError("uv_generation_face_budget", "source face count exceeds the bounded UV envelope")
    faces.sort(key=_face_key)
    geometric_keys = [(face.material, tuple(corner.position for corner in face.corners)) for face in faces]
    if len(geometric_keys) != len(set(geometric_keys)):
        raise UVGenerationError("uv_generation_duplicate_face", "duplicate oriented triangles are unsupported")
    return faces, arrays["materials"][0]["name"], len(referenced_attributes), {
        "source_primitive_count": len(primitives),
        "source_accessor_count": len(arrays["accessors"]),
        "source_buffer_view_count": len(arrays["views"]),
    }


def _edge_key(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (a, b) if a < b else (b, a)


def _basis(normal: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float], str]:
    world_up = (0.0, 1.0, 0.0)
    if abs(_dot(normal, world_up)) < 0.7071067811865476:
        bitangent = _normalize(tuple(world_up[index] - _dot(world_up, normal) * normal[index] for index in range(3)))
        tangent = _normalize(_cross(bitangent, normal))
        return tangent, bitangent, "vertical_world_up"
    reference = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.95 else (0.0, 0.0, 1.0)
    tangent = _normalize(tuple(reference[index] - _dot(reference, normal) * normal[index] for index in range(3)))
    bitangent = _normalize(_cross(normal, tangent))
    return tangent, bitangent, "world_axis_projected"


def _patch_uvs(
    patch_faces: list[int], faces: list[_Face], padding: float,
) -> tuple[dict[tuple[float, float, float], tuple[float, float]], dict[str, object]]:
    summed = tuple(sum(faces[index].area_vector[axis] for index in patch_faces) for axis in range(3))
    normal = _normalize(summed)
    tangent, bitangent, basis_policy = _basis(normal)
    positions = sorted({corner.position for index in patch_faces for corner in faces[index].corners})
    raw = {position: (_dot(position, tangent), _dot(position, bitangent)) for position in positions}
    min_u = min(value[0] for value in raw.values()); max_u = max(value[0] for value in raw.values())
    min_v = min(value[1] for value in raw.values()); max_v = max(value[1] for value in raw.values())
    width, height = max_u - min_u, max_v - min_v
    if width <= 1e-10 or height <= 1e-10:
        raise UVGenerationError("uv_generation_zero_patch_extent", "planar patch has zero projected width or height")
    usable = 1.0 - 2.0 * padding
    scale = usable / max(width, height)
    margin_u = (usable - width * scale) / 2.0
    margin_v = (usable - height * scale) / 2.0
    mapped = {
        position: (
            round(padding + margin_u + (value[0] - min_u) * scale, 6),
            round(padding + margin_v + (value[1] - min_v) * scale, 6),
        )
        for position, value in raw.items()
    }
    return mapped, {
        "normal": list(normal), "tangent": list(tangent), "bitangent": list(bitangent),
        "basis_policy": basis_policy, "projected_width": width, "projected_height": height,
        "uniform_scale": scale, "unused_margin_u": 2.0 * margin_u, "unused_margin_v": 2.0 * margin_v,
    }


def _generate(
    faces: list[_Face], *, normal_degrees: float, plane_epsilon: float, padding: float,
) -> tuple[list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float]]], list[tuple[int, int, int]], dict[str, object]]:
    if not math.isfinite(normal_degrees) or not 0.0 < normal_degrees <= 5.0:
        raise UVGenerationError("invalid_planarity_threshold", "patch normal threshold must be in (0,5] degrees")
    if not math.isfinite(plane_epsilon) or not 0.0 < plane_epsilon <= 1e-3:
        raise UVGenerationError("invalid_planarity_threshold", "plane epsilon must be in (0,1e-3]")
    if not math.isfinite(padding) or not 0.0 < padding < 0.25:
        raise UVGenerationError("invalid_uv_padding", "UV padding must be finite and in (0,0.25)")
    threshold = math.cos(math.radians(normal_degrees))
    edges: dict[tuple[tuple[float, float, float], tuple[float, float, float]], list[tuple[int, int, int]]] = {}
    for face_index, face in enumerate(faces):
        for start in range(3):
            end = (start + 1) % 3
            edges.setdefault(_edge_key(face.corners[start].position, face.corners[end].position), []).append((face_index, start, end))
    if len(edges) > UV_LIMITS["max_adjacency_edges"]:
        raise UVGenerationError("uv_generation_edge_budget", "source adjacency exceeds the bounded edge envelope")
    links: set[tuple[int, int]] = set()
    boundary_edges = seam_edges = 0
    for key in sorted(edges):
        incidents = edges[key]
        if len(incidents) > 2:
            raise UVGenerationError("uv_generation_non_manifold", "a geometric edge has more than two incident faces", edge=key)
        if len(incidents) == 1:
            boundary_edges += 1
            continue
        first, second = incidents
        f1, s1, e1 = first; f2, s2, e2 = second
        a1, b1 = faces[f1].corners[s1], faces[f1].corners[e1]
        a2, b2 = faces[f2].corners[s2], faces[f2].corners[e2]
        if not (a1.position == b2.position and b1.position == a2.position):
            raise UVGenerationError("uv_generation_inconsistent_winding", "adjacent faces traverse an edge in the same direction", edge=key)
        first_face, second_face = faces[f1], faces[f2]
        normal_ok = _dot(first_face.unit_normal, second_face.unit_normal) >= threshold - 1e-12
        origin = first_face.corners[0].position
        plane_ok = all(abs(_dot(_sub(corner.position, origin), first_face.unit_normal)) <= plane_epsilon for corner in second_face.corners)
        if first_face.material == second_face.material and normal_ok and plane_ok:
            links.add((min(f1, f2), max(f1, f2)))
        else:
            seam_edges += 1

    remaining = set(range(len(faces))); patches: list[list[int]] = []
    while remaining:
        seed = min(remaining); component = {seed}; frontier = [seed]
        while frontier:
            current = frontier.pop(0)
            neighbors = sorted(b if a == current else a for a, b in links if a == current or b == current)
            for neighbor in neighbors:
                if neighbor in remaining and neighbor not in component:
                    component.add(neighbor); frontier.append(neighbor)
        remaining -= component
        patches.append(sorted(component))
    patches.sort(key=lambda patch: tuple(_face_key(faces[index]) for index in patch))
    if len(patches) > UV_LIMITS["max_patches"]:
        raise UVGenerationError("uv_generation_patch_budget", "planar patch count exceeds the bounded envelope")

    uv_by_corner: dict[tuple[int, int], tuple[float, float]] = {}
    patch_reports: list[dict[str, object]] = []
    distortion_values: list[float] = []
    mirrored = degenerate_uv = 0
    for patch_index, patch in enumerate(patches):
        mapped, patch_report = _patch_uvs(patch, faces, padding)
        patch_report.update({"patch": patch_index, "faces": len(patch)})
        patch_reports.append(patch_report)
        scale = float(patch_report["uniform_scale"])
        for face_index in patch:
            face = faces[face_index]
            uvs = [mapped[corner.position] for corner in face.corners]
            for corner_index, uv in enumerate(uvs):
                if any(not math.isfinite(value) or value < -1e-7 or value > 1.0 + 1e-7 for value in uv):
                    raise UVGenerationError("uv_generation_out_of_range", "generated UV lies outside 0..1")
                uv_by_corner[(face_index, corner_index)] = uv
            signed = (uvs[1][0] - uvs[0][0]) * (uvs[2][1] - uvs[0][1]) - (uvs[1][1] - uvs[0][1]) * (uvs[2][0] - uvs[0][0])
            if abs(signed) <= 1e-12:
                degenerate_uv += 1
            elif signed < 0.0:
                mirrored += 1
            for first, second in ((0, 1), (1, 2), (2, 0)):
                geometry_length = math.sqrt(_dot(_sub(face.corners[first].position, face.corners[second].position), _sub(face.corners[first].position, face.corners[second].position)))
                uv_delta = (uvs[first][0] - uvs[second][0], uvs[first][1] - uvs[second][1])
                uv_length = math.sqrt(_dot(uv_delta, uv_delta))
                distortion_values.append(abs(uv_length / (geometry_length * scale) - 1.0))
    if degenerate_uv:
        raise UVGenerationError("uv_generation_degenerate_uv", "generated UV contains a zero-area triangle", count=degenerate_uv)
    if mirrored:
        raise UVGenerationError("uv_generation_mirrored", "generated UV orientation disagrees with source winding", count=mirrored)

    semantic_vertices = {
        (corner.position, corner.normal, uv_by_corner[(face_index, corner_index)])
        for face_index, face in enumerate(faces)
        for corner_index, corner in enumerate(face.corners)
    }
    vertices = sorted(semantic_vertices)
    if len(vertices) > UV_LIMITS["max_accessor_elements"]:
        raise UVGenerationError("uv_generation_vertex_budget", "UV seams exceed the canonical attribute-vertex budget")
    vertex_index = {value: index for index, value in enumerate(vertices)}
    triangles = [
        tuple(vertex_index[(corner.position, corner.normal, uv_by_corner[(face_index, corner_index)])] for corner_index, corner in enumerate(face.corners))
        for face_index, face in enumerate(faces)
    ]
    uv_values = [vertex[2] for vertex in vertices]
    metrics = {
        "face_count": len(faces), "planar_patch_count": len(patches),
        "canonical_attribute_vertices": len(vertices), "uv_seam_edge_count": seam_edges,
        "boundary_edge_count": boundary_edges,
        "decimation_protected_edge_fraction": seam_edges / len(edges) if edges else 0.0,
        "uv_min": [min(value[axis] for value in uv_values) for axis in range(2)],
        "uv_max": [max(value[axis] for value in uv_values) for axis in range(2)],
        "degenerate_uv_triangle_count": degenerate_uv, "mirrored_uv_triangle_count": mirrored,
        "maximum_patch_aspect_distortion": max(distortion_values, default=0.0),
        "mean_patch_aspect_distortion": sum(distortion_values) / len(distortion_values) if distortion_values else 0.0,
        "intentionally_overlapping_patch_islands": len(patches), "patches": patch_reports,
    }
    return vertices, triangles, metrics


def _write_canonical(
    vertices: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float]]],
    triangles: list[tuple[int, int, int]], material: str,
) -> bytes:
    positions = [value[0] for value in vertices]; normals = [value[1] for value in vertices]; uvs = [value[2] for value in vertices]
    indices = [index for triangle in triangles for index in triangle]
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[Any], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values: binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            packed = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in values]
            accessor["min"] = [min(value[axis] for value in packed) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in packed) for axis in range(3)]
        accessors.append(accessor); return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, True)
    n = append(normals, "<3f", "VEC3", 5126)
    uv = append(uvs, "<2f", "VEC2", 5126)
    component, fmt = (5121, "<B") if len(vertices) <= 256 else (5123, "<H")
    ix = append(indices, fmt, "SCALAR", component)
    document = {
        "asset": {"generator": "pokeagent-stage4m-uvs-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "canonical_uv_mesh"}],
        "meshes": [{"name": "canonical_uv_mesh", "primitives": [{
            "attributes": {"POSITION": p, "NORMAL": n, "TEXCOORD_0": uv},
            "indices": ix, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": material}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def generate_missing_uvs(
    data: bytes, *,
    patch_normal_degrees: float = CANONICAL_PATCH_NORMAL_DEGREES,
    plane_epsilon: float = CANONICAL_PLANE_EPSILON,
    texture_size: int = CANONICAL_TEXTURE_SIZE,
    padding_texels: int = CANONICAL_PADDING_TEXELS,
) -> dict[str, Any]:
    """Generate repeat-per-planar-patch UV0 and strict Stage 4F GLB bytes."""
    if texture_size != CANONICAL_TEXTURE_SIZE or isinstance(padding_texels, bool) or not isinstance(padding_texels, int):
        raise UVGenerationError("invalid_uv_padding", "Stage 4M uses integer texel padding on one 32x32 texture")
    padding = padding_texels / texture_size
    faces, material, source_attributes, source_details = _decode_no_uv_source(data)
    vertices, triangles, metrics = _generate(
        faces, normal_degrees=patch_normal_degrees, plane_epsilon=plane_epsilon, padding=padding,
    )
    canonical = _write_canonical(vertices, triangles, material)
    try:
        accepted = parse_glb(canonical)
    except GLBError as error:
        raise UVGenerationError("uv_generation_canonical_mismatch", str(error), stage4f_code=error.code) from error
    report = {
        "schema_version": 1, "success": True, "policy": "repeat_per_planar_patch",
        "patch_normal_degrees": patch_normal_degrees, "plane_epsilon": plane_epsilon,
        "texture_size": texture_size, "padding_texels": padding_texels, "padding_uv": padding,
        "aspect_policy": "uniform_fit_longest_center_shorter", "overlap_policy": "intentional_per_patch_reuse",
        "limits": dict(UV_LIMITS), "source_sha256": _sha256(data), "canonical_sha256": _sha256(canonical),
        "source_size_bytes": len(data), "canonical_size_bytes": len(canonical),
        "source_attribute_vertices": source_attributes,
        "uv_split_count": len(vertices) - source_attributes,
        "material": material, "stage4f_accepted": True, **source_details, **metrics,
    }
    semantic = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = _sha256(semantic)
    return {"canonical_glb": canonical, "canonical_mesh": accepted, "report": report}


def inspect_uv_applicability(data: bytes) -> dict[str, Any]:
    """Read-only projection for generated intake; no derived GLB is retained."""
    try:
        result = generate_missing_uvs(data)
    except UVGenerationError as error:
        return {"applicable": False, "error": {"code": error.code, "message": str(error), "details": error.details}}
    return {"applicable": True, "error": None, "metrics": result["report"]}
