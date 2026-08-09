"""Deterministic exact simplification for redundant coplanar triangle patches.

This is deliberately narrower than a general edge-collapse or topology-repair
tool.  It accepts already-valid normalized triangle meshes, preserves every
material/UV/hard-normal boundary, and replaces connected coplanar subdivisions
with their minimal three- or four-corner boundary primitive.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any


ALGORITHM = "exact_coplanar_patches"
ALGORITHM_VERSION = 1
POSITION_TOLERANCE = 1e-6
NORMAL_TOLERANCE = 1e-6
UV_TOLERANCE = 1e-6


class SimplificationError(ValueError):
    """The valid input cannot be reduced by the bounded exact algorithm."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _hash(value: object) -> str:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(data).hexdigest()


def _subtract(a: list[float], b: list[float]) -> tuple[float, float, float]:
    return tuple(float(x) - float(y) for x, y in zip(a, b, strict=True))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(vector: tuple[float, ...]) -> float:
    return math.sqrt(_dot(vector, vector))


def _triangle_area(a: list[float], b: list[float], c: list[float]) -> float:
    return _length(_cross(_subtract(b, a), _subtract(c, a))) / 2


def _surface_area(ir: dict[str, Any]) -> float:
    total = 0.0
    for face in ir["faces"]:
        points = [ir["vertices"][index] for index in face["vertices"]]
        total += _triangle_area(points[0], points[1], points[2])
        if face.get("primitive") == "quad":
            total += _triangle_area(points[0], points[2], points[3])
    return total


def _referenced_vertex_count(ir: dict[str, Any]) -> int:
    return len({index for face in ir["faces"] for index in face["vertices"]})


def _computed_bounds(ir: dict[str, Any]) -> tuple[dict[str, list[float]], list[float]]:
    referenced = sorted({index for face in ir["faces"] for index in face["vertices"]})
    bounds = {
        "min": [min(float(ir["vertices"][index][axis]) for index in referenced) for axis in range(3)],
        "max": [max(float(ir["vertices"][index][axis]) for index in referenced) for axis in range(3)],
    }
    dimensions = [bounds["max"][axis] - bounds["min"][axis] for axis in range(3)]
    return bounds, dimensions


def _uv_seam_vertex_count(ir: dict[str, Any]) -> int:
    assignments: dict[int, set[tuple[float, float]]] = {}
    for face in ir["faces"]:
        for vertex, uv in zip(face["vertices"], face["uvs"], strict=True):
            assignments.setdefault(vertex, set()).add(tuple(float(value) for value in ir["uvs"][uv]))
    return sum(len(values) > 1 for values in assignments.values())


def _signature(ir: dict[str, Any], face: dict[str, Any]) -> tuple[object, ...]:
    normal = tuple(round(float(value), 6) for value in face["normal"])
    point = ir["vertices"][face["vertices"][0]]
    plane = round(sum(normal[axis] * float(point[axis]) for axis in range(3)), 6)
    return (
        face["source_material"], face["material_alias"], face.get("texture"),
        tuple(round(float(value), 6) for value in face.get("protected_normal", face["normal"])),
        normal, plane,
    )


def _edge_key(start: tuple[int, int], end: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(sorted((start, end)))  # type: ignore[return-value]


def _face_edges(face: dict[str, Any]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    corners = list(zip(face["vertices"], face["uvs"], strict=True))
    return [(corners[index], corners[(index + 1) % len(corners)]) for index in range(len(corners))]


def _components(ir: dict[str, Any]) -> list[list[int]]:
    faces = ir["faces"]
    if any(face.get("primitive") != "triangle" for face in faces):
        raise SimplificationError(
            "simplification_unsupported_primitive",
            "exact coplanar simplification currently accepts triangle-only input",
        )
    signatures = [_signature(ir, face) for face in faces]
    edges: dict[tuple[tuple[int, int], tuple[int, int]], list[int]] = {}
    for index, face in enumerate(faces):
        for start, end in _face_edges(face):
            edges.setdefault(_edge_key(start, end), []).append(index)
    if any(len(owners) > 2 for owners in edges.values()):
        raise SimplificationError("simplification_nonmanifold", "an input edge has more than two incident faces")
    adjacency: list[set[int]] = [set() for _face in faces]
    for owners in edges.values():
        if len(owners) == 2 and signatures[owners[0]] == signatures[owners[1]]:
            adjacency[owners[0]].add(owners[1])
            adjacency[owners[1]].add(owners[0])
    result: list[list[int]] = []
    unseen = set(range(len(faces)))
    while unseen:
        first = min(unseen)
        pending = [first]
        unseen.remove(first)
        component: list[int] = []
        while pending:
            current = pending.pop(0)
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    pending.append(neighbor)
        result.append(sorted(component))
    return result


def _boundary(ir: dict[str, Any], component: list[int]) -> list[tuple[int, int]]:
    occurrences: dict[
        tuple[tuple[int, int], tuple[int, int]],
        list[tuple[tuple[int, int], tuple[int, int]]],
    ] = {}
    for face_index in component:
        for start, end in _face_edges(ir["faces"][face_index]):
            occurrences.setdefault(_edge_key(start, end), []).append((start, end))
    boundary_edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for directed in occurrences.values():
        if len(directed) == 1:
            boundary_edges.append(directed[0])
        elif len(directed) == 2:
            first, second = directed
            if first != (second[1], second[0]):
                raise SimplificationError(
                    "simplification_winding_violation",
                    "two coplanar input faces traverse a shared edge in the same direction",
                )
        else:
            raise SimplificationError("simplification_nonmanifold", "coplanar patch has a non-manifold edge")
    outgoing: dict[tuple[int, int], tuple[int, int]] = {}
    incoming: dict[tuple[int, int], tuple[int, int]] = {}
    for start, end in boundary_edges:
        if start in outgoing or end in incoming:
            raise SimplificationError(
                "simplification_boundary_violation", "coplanar patch does not have one simple boundary loop",
            )
        outgoing[start] = end
        incoming[end] = start
    if set(outgoing) != set(incoming) or not outgoing:
        raise SimplificationError(
            "simplification_boundary_violation", "coplanar patch boundary is open or disconnected",
        )
    start = min(
        outgoing,
        key=lambda corner: (
            tuple(round(float(value), 8) for value in ir["vertices"][corner[0]]),
            tuple(round(float(value), 8) for value in ir["uvs"][corner[1]]),
            corner,
        ),
    )
    loop = [start]
    current = outgoing[start]
    while current != start:
        if current in loop or len(loop) > len(boundary_edges):
            raise SimplificationError("simplification_boundary_violation", "coplanar boundary does not close once")
        loop.append(current)
        current = outgoing[current]
    if len(loop) != len(boundary_edges):
        raise SimplificationError("simplification_boundary_violation", "coplanar patch contains multiple loops")
    return loop


def _removable(ir: dict[str, Any], previous: tuple[int, int], current: tuple[int, int], following: tuple[int, int]) -> bool:
    a, b, c = (ir["vertices"][corner[0]] for corner in (previous, current, following))
    ac = _subtract(c, a)
    length_squared = _dot(ac, ac)
    if length_squared <= POSITION_TOLERANCE ** 2:
        return False
    ab = _subtract(b, a)
    t = _dot(ab, ac) / length_squared
    if not POSITION_TOLERANCE < t < 1.0 - POSITION_TOLERANCE:
        return False
    nearest = tuple(float(a[axis]) + t * ac[axis] for axis in range(3))
    if _length(tuple(float(b[axis]) - nearest[axis] for axis in range(3))) > POSITION_TOLERANCE:
        return False
    uv_a, uv_b, uv_c = (ir["uvs"][corner[1]] for corner in (previous, current, following))
    expected = tuple(float(uv_a[axis]) + t * (float(uv_c[axis]) - float(uv_a[axis])) for axis in range(2))
    return max(abs(float(uv_b[axis]) - expected[axis]) for axis in range(2)) <= UV_TOLERANCE


def _collapse_collinear_boundary(ir: dict[str, Any], boundary: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result = list(boundary)
    changed = True
    while changed and len(result) > 3:
        changed = False
        for index in range(len(result)):
            if _removable(ir, result[index - 1], result[index], result[(index + 1) % len(result)]):
                del result[index]
                changed = True
                break
    return result


def _compact(ir: dict[str, Any], faces: list[dict[str, Any]]) -> dict[str, Any]:
    vertex_map: dict[int, int] = {}
    uv_map: dict[int, int] = {}
    vertices: list[list[float]] = []
    uvs: list[list[float]] = []
    compact_faces: list[dict[str, Any]] = []
    for face in faces:
        compact_face = copy.deepcopy(face)
        compact_face["vertices"] = []
        compact_face["uvs"] = []
        for source_vertex, source_uv in zip(face["vertices"], face["uvs"], strict=True):
            if source_vertex not in vertex_map:
                vertex_map[source_vertex] = len(vertices)
                vertices.append(copy.deepcopy(ir["vertices"][source_vertex]))
            if source_uv not in uv_map:
                uv_map[source_uv] = len(uvs)
                uvs.append(copy.deepcopy(ir["uvs"][source_uv]))
            compact_face["vertices"].append(vertex_map[source_vertex])
            compact_face["uvs"].append(uv_map[source_uv])
        compact_faces.append(compact_face)
    output = copy.deepcopy(ir)
    output["vertices"] = vertices
    output["uvs"] = uvs
    output["faces"] = compact_faces
    return output


def simplify_coplanar_ir(ir: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a maximally exact coplanar reduction and deterministic metrics."""
    if ir.get("schema_version") != 2 or not ir.get("faces"):
        raise SimplificationError("simplification_unsupported_ir", "simplification requires typed mesh IR schema 2")
    simplified_faces: list[dict[str, Any]] = []
    source_faces = ir["faces"]
    components = _components(ir)
    maximum_normal_deviation = 0.0
    for patch_index, component in enumerate(components):
        boundary = _collapse_collinear_boundary(ir, _boundary(ir, component))
        if len(boundary) not in (3, 4):
            raise SimplificationError(
                "simplification_unsupported_boundary",
                "exact coplanar patch must reduce to a triangle or quad boundary",
                patch=patch_index, boundary_vertices=len(boundary),
            )
        template = source_faces[component[0]]
        face = {
            "id": f"simplified_patch_{patch_index:03d}",
            "vertices": [corner[0] for corner in boundary],
            "uvs": [corner[1] for corner in boundary],
            "normal": copy.deepcopy(template["normal"]),
            "source_material": template["source_material"],
            "material_alias": template["material_alias"],
            "primitive": "triangle" if len(boundary) == 3 else "quad",
        }
        if "texture" in template:
            face["texture"] = template["texture"]
        if "protected_normal" in template:
            face["protected_normal"] = copy.deepcopy(template["protected_normal"])
        points = [ir["vertices"][index] for index in face["vertices"]]
        geometric = _cross(_subtract(points[1], points[0]), _subtract(points[2], points[0]))
        geometric_length = _length(geometric)
        if geometric_length <= POSITION_TOLERANCE:
            raise SimplificationError("simplification_degenerate_output", "simplified face is degenerate")
        geometric_normal = tuple(value / geometric_length for value in geometric)
        agreement = max(-1.0, min(1.0, _dot(geometric_normal, tuple(face["normal"]))))
        if agreement < 1.0 - NORMAL_TOLERANCE:
            raise SimplificationError("simplification_winding_violation", "simplified face changes winding or normal")
        maximum_normal_deviation = max(maximum_normal_deviation, math.degrees(math.acos(agreement)))
        simplified_faces.append(face)
    simplified = _compact(ir, simplified_faces)
    before_area = _surface_area(ir)
    after_area = _surface_area(simplified)
    if abs(before_area - after_area) > POSITION_TOLERANCE:
        raise SimplificationError(
            "simplification_surface_change", "exact coplanar reduction changed surface area",
            before=before_area, after=after_area,
        )
    source_bounds, source_dimensions = _computed_bounds(ir)
    simplified_bounds, simplified_dimensions = _computed_bounds(simplified)
    if source_bounds != ir["bounds"] or source_dimensions != ir["dimensions"]:
        raise SimplificationError(
            "simplification_invalid_source_bounds", "source mesh bounds disagree with referenced geometry",
        )
    if simplified_bounds != source_bounds or simplified_dimensions != source_dimensions:
        raise SimplificationError(
            "simplification_boundary_violation", "simplification changed the computed geometry bounds",
            before=source_bounds, after=simplified_bounds,
        )
    report = {
        "algorithm": ALGORITHM,
        "algorithm_version": ALGORITHM_VERSION,
        "settings": {
            "position_tolerance": POSITION_TOLERANCE,
            "normal_tolerance": NORMAL_TOLERANCE,
            "uv_tolerance": UV_TOLERANCE,
            "reduction_mode": "maximal_exact",
        },
        "patch_count": len(components),
        "source": {
            "triangles": sum(face.get("primitive") == "triangle" for face in ir["faces"]),
            "quads": sum(face.get("primitive") == "quad" for face in ir["faces"]),
            "vertices": _referenced_vertex_count(ir),
            "faces": len(ir["faces"]),
            "surface_area": before_area,
            "uv_seam_vertices": _uv_seam_vertex_count(ir),
            "material_count": len({face["material_alias"] for face in ir["faces"]}),
            "semantic_sha256": _hash(ir),
        },
        "simplified": {
            "triangles": sum(face.get("primitive") == "triangle" for face in simplified["faces"]),
            "quads": sum(face.get("primitive") == "quad" for face in simplified["faces"]),
            "vertices": _referenced_vertex_count(simplified),
            "faces": len(simplified["faces"]),
            "surface_area": after_area,
            "uv_seam_vertices": _uv_seam_vertex_count(simplified),
            "material_count": len({face["material_alias"] for face in simplified["faces"]}),
            "semantic_sha256": _hash(simplified),
        },
        "geometry_preservation": {
            "bounds_exact": True,
            "surface_area_delta": after_area - before_area,
            "maximum_vertex_displacement": 0.0,
            "maximum_normal_deviation_degrees": maximum_normal_deviation,
            "material_identity_preserved": True,
            "uv_boundary_interpolation_exact": True,
        },
    }
    return simplified, report
