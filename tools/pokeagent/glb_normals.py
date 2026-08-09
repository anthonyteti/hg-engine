"""Deterministic crease-aware normal generation for bounded static GLB geometry."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct
from typing import Any

from .glb import GLBError, _chunks, _decode_accessor, _integer, _validate_document, pack_glb, parse_glb


NORMAL_LIMITS = {
    "max_source_bytes": 262_144,
    "max_nodes": 1,
    "max_meshes": 1,
    "max_primitives": 4,
    "max_accessors": 16,
    "max_buffer_views": 16,
    "max_accessor_elements": 256,
    "max_buffer_bytes": 262_144,
    "max_faces": 256,
    "max_adjacency_edges": 768,
}
CANONICAL_CREASE_DEGREES = 60.0
CANONICAL_WEIGHTING = "area"


class NormalGenerationError(ValueError):
    """Source geometry cannot safely acquire normals under the bounded policy."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class _Corner:
    position: tuple[float, float, float]
    uv: tuple[float, float]
    source_attribute: tuple[int, int]


@dataclass(frozen=True)
class _Face:
    material: str
    corners: tuple[_Corner, _Corner, _Corner]
    area_vector: tuple[float, float, float]
    unit_normal: tuple[float, float, float]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _subtract(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(a[index] - b[index] for index in range(3))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(left * right for left, right in zip(a, b, strict=True))


def _normalize(value: tuple[float, float, float], code: str = "normal_generation_zero_length") -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    if not math.isfinite(length) or length <= 1e-12:
        raise NormalGenerationError(code, "normal derivation produced a zero or non-finite vector")
    result = tuple(component / length for component in value)
    if any(not math.isfinite(component) for component in result):
        raise NormalGenerationError("normal_generation_nonfinite", "normal derivation produced NaN or infinity")
    return result


def _face_key(face: _Face) -> tuple[object, ...]:
    return (face.material, tuple((corner.position, corner.uv) for corner in face.corners))


def _decode_missing_normal_source(data: bytes) -> tuple[list[_Face], str, int, dict[str, object]]:
    try:
        document, binary = _chunks(data, NORMAL_LIMITS)
        arrays = _validate_document(document, binary, NORMAL_LIMITS)
    except GLBError as error:
        raise NormalGenerationError(error.code, str(error), **error.details) from error
    mesh = arrays["meshes"][0]
    if not isinstance(mesh, dict) or mesh.get("weights") is not None:
        raise NormalGenerationError("unsupported_morph_targets", "normal generation rejects mesh weights and morphs")
    primitives = mesh.get("primitives")
    if not isinstance(primitives, list) or not 1 <= len(primitives) <= NORMAL_LIMITS["max_primitives"]:
        raise NormalGenerationError("unsupported_primitive_count", "normal generation accepts 1..4 triangle primitives")
    faces: list[_Face] = []
    referenced_attributes: set[tuple[int, int]] = set()
    for primitive_index, primitive in enumerate(primitives):
        if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
            raise NormalGenerationError("unsupported_primitive_mode", "normal generation accepts TRIANGLES mode 4 only")
        if primitive.get("targets") is not None:
            raise NormalGenerationError("unsupported_morph_targets", "normal generation rejects morph targets")
        attributes = primitive.get("attributes")
        if isinstance(attributes, dict) and "NORMAL" in attributes:
            raise NormalGenerationError("normal_attribute_already_present", "missing-normal policy never replaces authored normals")
        required = {"POSITION", "TEXCOORD_0"}
        if not isinstance(attributes, dict) or set(attributes) != required:
            missing = sorted(required - set(attributes or {})) if isinstance(attributes, dict) else sorted(required)
            raise NormalGenerationError("missing_attribute", f"normal source requires only POSITION/TEXCOORD_0; missing={missing}")
        try:
            positions = _decode_accessor(
                attributes["POSITION"], "VEC3", {5126}, arrays, binary, require_bounds=True,
                max_elements=NORMAL_LIMITS["max_accessor_elements"],
            )
            uvs = _decode_accessor(
                attributes["TEXCOORD_0"], "VEC2", {5126}, arrays, binary,
                max_elements=NORMAL_LIMITS["max_accessor_elements"],
            )
            indices = _decode_accessor(
                primitive.get("indices"), "SCALAR", {5121, 5123, 5125}, arrays, binary,
                indices=True, max_elements=NORMAL_LIMITS["max_accessor_elements"],
            )
        except GLBError as error:
            raise NormalGenerationError(error.code, str(error), **error.details) from error
        if len(positions) != len(uvs):
            raise NormalGenerationError("attribute_count_mismatch", "POSITION and TEXCOORD_0 counts must match")
        flat_indices = [int(value[0]) for value in indices]
        if len(flat_indices) % 3:
            raise NormalGenerationError("invalid_indices", "triangle index count must be divisible by three")
        if any(index >= len(positions) for index in flat_indices):
            raise NormalGenerationError("invalid_indices", "triangle index is out of range")
        material_index = _integer(primitive.get("material"), "unsupported_material", "primitive.material")
        if material_index >= len(arrays["materials"]):
            raise NormalGenerationError("unsupported_material", "primitive material index is out of range")
        material = arrays["materials"][material_index]["name"]
        for offset in range(0, len(flat_indices), 3):
            raw = flat_indices[offset:offset + 3]
            corners = tuple(
                _Corner(
                    tuple(float(value) for value in positions[index]),
                    tuple(float(value) for value in uvs[index]),
                    (primitive_index, index),
                )
                for index in raw
            )
            if len({corner.position for corner in corners}) != 3:
                raise NormalGenerationError("normal_generation_degenerate", "triangle repeats a geometric vertex")
            area = _cross(_subtract(corners[1].position, corners[0].position), _subtract(corners[2].position, corners[0].position))
            normal = _normalize(area, "normal_generation_degenerate")
            faces.append(_Face(material, corners, area, normal))
            referenced_attributes.update(corner.source_attribute for corner in corners)
    if not faces or len(faces) > NORMAL_LIMITS["max_faces"]:
        raise NormalGenerationError("normal_generation_face_budget", "source face count exceeds the bounded normal-generation envelope")
    faces.sort(key=_face_key)
    keys = [_face_key(face) for face in faces]
    if len(keys) != len(set(keys)):
        raise NormalGenerationError("normal_generation_duplicate_face", "duplicate oriented triangles are unsupported")
    return faces, arrays["materials"][0]["name"], len(referenced_attributes), {
        "source_primitive_count": len(primitives),
        "source_accessor_count": len(arrays["accessors"]),
        "source_buffer_view_count": len(arrays["views"]),
    }


def _edge_key(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (a, b) if a < b else (b, a)


def _generate(faces: list[_Face], crease_degrees: float) -> tuple[list[tuple[tuple[float, float, float], tuple[float, float], tuple[float, float, float]]], list[tuple[int, int, int]], dict[str, object]]:
    if not 0.0 < crease_degrees < 180.0 or not math.isfinite(crease_degrees):
        raise NormalGenerationError("invalid_crease_threshold", "crease angle must be finite and strictly between 0 and 180")
    threshold = math.cos(math.radians(crease_degrees))
    edges: dict[tuple[tuple[float, float, float], tuple[float, float, float]], list[tuple[int, int, int]]] = {}
    for face_index, face in enumerate(faces):
        for start in range(3):
            end = (start + 1) % 3
            edges.setdefault(_edge_key(face.corners[start].position, face.corners[end].position), []).append((face_index, start, end))
    if len(edges) > NORMAL_LIMITS["max_adjacency_edges"]:
        raise NormalGenerationError("normal_generation_edge_budget", "source adjacency exceeds the bounded edge envelope")
    smooth_links: list[tuple[int, int, tuple[float, float, float], tuple[float, float, float]]] = []
    smooth_edges = hard_edges = uv_seams = boundary_edges = 0
    for key in sorted(edges):
        incidents = edges[key]
        if len(incidents) > 2:
            raise NormalGenerationError("normal_generation_non_manifold", "a geometric edge has more than two incident faces", edge=key)
        if len(incidents) == 1:
            boundary_edges += 1
            continue
        first, second = incidents
        f1, s1, e1 = first; f2, s2, e2 = second
        a1, b1 = faces[f1].corners[s1], faces[f1].corners[e1]
        a2, b2 = faces[f2].corners[s2], faces[f2].corners[e2]
        if not (a1.position == b2.position and b1.position == a2.position):
            raise NormalGenerationError("normal_generation_inconsistent_winding", "adjacent faces traverse a shared edge in the same direction", edge=key)
        uv_compatible = a1.uv == b2.uv and b1.uv == a2.uv
        material_compatible = faces[f1].material == faces[f2].material
        angle_compatible = _dot(faces[f1].unit_normal, faces[f2].unit_normal) >= threshold - 1e-12
        if uv_compatible and material_compatible and angle_compatible:
            smooth_edges += 1
            smooth_links.append((f1, f2, key[0], key[1]))
        else:
            hard_edges += 1
            if not uv_compatible:
                uv_seams += 1

    incident: dict[tuple[tuple[float, float, float], tuple[float, float], str], set[int]] = {}
    for face_index, face in enumerate(faces):
        for corner in face.corners:
            incident.setdefault((corner.position, corner.uv, face.material), set()).add(face_index)
    links_by_vertex: dict[tuple[tuple[float, float, float], tuple[float, float], str], set[tuple[int, int]]] = {}
    for first, second, position_a, position_b in smooth_links:
        for position in (position_a, position_b):
            corner_first = next(corner for corner in faces[first].corners if corner.position == position)
            corner_second = next(corner for corner in faces[second].corners if corner.position == position)
            if corner_first.uv == corner_second.uv:
                key = (position, corner_first.uv, faces[first].material)
                links_by_vertex.setdefault(key, set()).add((min(first, second), max(first, second)))

    normal_by_corner: dict[tuple[int, int], tuple[float, float, float]] = {}
    fan_count = 0
    for key in sorted(incident):
        remaining = set(incident[key])
        links = links_by_vertex.get(key, set())
        while remaining:
            seed = min(remaining); component = {seed}; frontier = [seed]
            while frontier:
                current = frontier.pop(0)
                neighbors = sorted(b if a == current else a for a, b in links if a == current or b == current)
                for neighbor in neighbors:
                    if neighbor in remaining and neighbor not in component:
                        component.add(neighbor); frontier.append(neighbor)
            remaining -= component
            summed = tuple(sum(faces[index].area_vector[axis] for index in sorted(component)) for axis in range(3))
            normal = _normalize(summed)
            fan_count += 1
            for face_index in component:
                for corner_index, corner in enumerate(faces[face_index].corners):
                    if (corner.position, corner.uv, faces[face_index].material) == key:
                        normal_by_corner[(face_index, corner_index)] = normal

    semantic_vertices = {
        (corner.position, corner.uv, normal_by_corner[(face_index, corner_index)])
        for face_index, face in enumerate(faces)
        for corner_index, corner in enumerate(face.corners)
    }
    vertices = sorted(semantic_vertices)
    vertex_index = {value: index for index, value in enumerate(vertices)}
    triangles = [
        tuple(vertex_index[(corner.position, corner.uv, normal_by_corner[(face_index, corner_index)])] for corner_index, corner in enumerate(face.corners))
        for face_index, face in enumerate(faces)
    ]
    unique_normals = {vertex[2] for vertex in vertices}
    packed_normals = [struct.unpack("<3f", struct.pack("<3f", *normal)) for normal in unique_normals]
    max_length_error = max(abs(math.sqrt(_dot(normal, normal)) - 1.0) for normal in packed_normals)
    metrics = {
        "face_count": len(faces), "canonical_attribute_vertices": len(vertices),
        "generated_unique_normal_count": len(unique_normals), "smoothing_fan_count": fan_count,
        "smooth_edge_count": smooth_edges, "hard_edge_count": hard_edges,
        "boundary_edge_count": boundary_edges, "uv_seam_forced_split_count": uv_seams,
        "max_float32_normal_length_error": max_length_error,
        "minimum_smooth_edge_normal_agreement": 1.0 if smooth_edges else None,
    }
    return vertices, triangles, metrics


def _write_canonical(
    vertices: list[tuple[tuple[float, float, float], tuple[float, float], tuple[float, float, float]]],
    triangles: list[tuple[int, int, int]], material: str,
) -> bytes:
    positions = [value[0] for value in vertices]
    uvs = [value[1] for value in vertices]
    normals = [value[2] for value in vertices]
    indices = [index for triangle in triangles for index in triangle]
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[Any], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4:
            binary.append(0)
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
    component, fmt = (5121, "<B") if len(vertices) <= 256 else (5123, "<H")
    ix = append(indices, fmt, "SCALAR", component)
    document = {
        "asset": {"generator": "pokeagent-stage4l-normals-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "canonical_normal_mesh"}],
        "meshes": [{"name": "canonical_normal_mesh", "primitives": [{
            "attributes": {"POSITION": p, "NORMAL": n, "TEXCOORD_0": uv},
            "indices": ix, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": material}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def generate_missing_normals(
    data: bytes,
    *,
    crease_angle_degrees: float = CANONICAL_CREASE_DEGREES,
    weighting: str = CANONICAL_WEIGHTING,
) -> dict[str, Any]:
    """Generate area-weighted crease-aware normals and strict Stage 4F GLB bytes."""
    if weighting != CANONICAL_WEIGHTING:
        raise NormalGenerationError(
            "invalid_normal_weighting",
            f"Stage 4L supports only {CANONICAL_WEIGHTING!r} normal weighting",
            weighting=weighting,
        )
    faces, material, source_attributes, source_details = _decode_missing_normal_source(data)
    vertices, triangles, metrics = _generate(faces, crease_angle_degrees)
    canonical = _write_canonical(vertices, triangles, material)
    try:
        accepted = parse_glb(canonical)
    except GLBError as error:
        raise NormalGenerationError("normal_generation_canonical_mismatch", str(error), stage4f_code=error.code) from error
    report = {
        "schema_version": 1, "success": True, "policy": "crease_aware",
        "crease_angle_degrees": crease_angle_degrees, "weighting": weighting,
        "preserve_uv_seams": True, "preserve_boundaries": True,
        "limits": dict(NORMAL_LIMITS), "source_sha256": _sha256(data),
        "canonical_sha256": _sha256(canonical), "source_size_bytes": len(data),
        "canonical_size_bytes": len(canonical), "source_attribute_vertices": source_attributes,
        "split_vertex_count": len(vertices) - source_attributes, "material": material,
        "stage4f_accepted": True, **source_details, **metrics,
    }
    semantic = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = _sha256(semantic)
    return {"canonical_glb": canonical, "canonical_mesh": accepted, "report": report}


def inspect_normal_applicability(data: bytes) -> dict[str, Any]:
    """Read-only projection for intake; no derived GLB is returned or stored."""
    try:
        result = generate_missing_normals(data)
    except NormalGenerationError as error:
        return {"applicable": False, "error": {"code": error.code, "message": str(error), "details": error.details}}
    return {"applicable": True, "error": None, "metrics": result["report"]}
