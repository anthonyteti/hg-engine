"""Deterministic constrained approximate decimation for validated static mesh IR.

The Stage 4J pass is intentionally bounded.  It accepts typed mesh IR schema 2,
triangulates any exact Stage 4G quads, canonicalizes corner vertices, and uses a
quadric-ranked edge-collapse sequence.  The implementation never repairs source
topology, creates UV charts, crosses material/UV seams, or exceeds declared
fidelity limits merely to satisfy a byte target.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any


ALGORITHM = "constrained_deterministic_qem"
ALGORITHM_VERSION = 1
TRIANGLE_DISPLAY_LIST_BASE_BYTES = 12
TRIANGLE_DISPLAY_LIST_BYTES_PER_FACE = 68
EPSILON = 1e-9
SILHOUETTE_GRID = 64


class DecimationError(ValueError):
    """A valid typed mesh cannot satisfy the bounded Stage 4J contract."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _hash(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _sub(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _length(value: tuple[float, ...]) -> float:
    return math.sqrt(_dot(value, value))


def _normal(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = _cross(_sub(b, a), _sub(c, a))
    length = _length(raw)
    if length <= EPSILON:
        raise DecimationError("approximate_simplification_degenerate", "triangle has zero area")
    return tuple(value / length for value in raw)  # type: ignore[return-value]


def _area(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> float:
    return _length(_cross(_sub(b, a), _sub(c, a))) / 2


def _uv_area(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2


def _bytes(face_count: int) -> int:
    return TRIANGLE_DISPLAY_LIST_BASE_BYTES + TRIANGLE_DISPLAY_LIST_BYTES_PER_FACE * face_count


def _rotated(values: tuple[int, int, int]) -> tuple[int, int, int]:
    variants = (values, (values[1], values[2], values[0]), (values[2], values[0], values[1]))
    return min(variants)


def _triangulate(ir: dict[str, Any]) -> dict[str, Any]:
    """Convert schema-2 triangle/quad IR to canonical wedge-indexed triangles."""
    if ir.get("schema_version") != 2 or not isinstance(ir.get("faces"), list) or not ir["faces"]:
        raise DecimationError("approximate_simplification_unsupported_ir", "Stage 4J requires typed mesh IR schema 2")
    wedge_keys: set[tuple[tuple[float, float, float], tuple[float, float]]] = set()
    raw_faces: list[
        tuple[list[tuple[tuple[float, float, float], tuple[float, float]]], str, str | None]
    ] = []
    for face in ir["faces"]:
        primitive = face.get("primitive")
        if primitive not in ("triangle", "quad"):
            raise DecimationError("approximate_simplification_unsupported_primitive", "only typed triangles/quads may be decimated")
        corners = [
            (
                tuple(float(value) for value in ir["vertices"][vertex]),
                tuple(float(value) for value in ir["uvs"][uv]),
            )
            for vertex, uv in zip(face["vertices"], face["uvs"], strict=True)
        ]
        triangles = (corners,) if primitive == "triangle" else ((corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3]))
        for triangle in triangles:
            wedge_keys.update(triangle)
            raw_faces.append((list(triangle), face["material_alias"], face.get("texture")))
    ordered_keys = sorted(wedge_keys)
    ids = {key: index for index, key in enumerate(ordered_keys)}
    faces: list[dict[str, Any]] = []
    for corners, material, texture in raw_faces:
        vertices = _rotated(tuple(ids[corner] for corner in corners))
        if len(set(vertices)) != 3:
            raise DecimationError("approximate_simplification_degenerate", "typed source contains a degenerate triangle")
        face = {"vertices": vertices, "material": material, "texture": texture}
        faces.append(face)
    faces.sort(key=lambda face: (face["material"], face["texture"] or "", face["vertices"]))
    if len({face["vertices"] for face in faces}) != len(faces):
        raise DecimationError("approximate_simplification_invalid_topology", "typed source contains duplicate triangles")
    return {
        "vertices": [key[0] for key in ordered_keys],
        "uvs": [key[1] for key in ordered_keys],
        "faces": faces,
    }


def _edges(faces: list[dict[str, Any]]) -> dict[tuple[int, int], list[int]]:
    result: dict[tuple[int, int], list[int]] = {}
    for face_index, face in enumerate(faces):
        a, b, c = face["vertices"]
        for edge in ((a, b), (b, c), (c, a)):
            result.setdefault(tuple(sorted(edge)), []).append(face_index)
    if any(len(owners) > 2 for owners in result.values()):
        raise DecimationError("approximate_simplification_nonmanifold", "an edge has more than two incident triangles")
    return result


def _quadric(plane: tuple[float, float, float, float]) -> list[list[float]]:
    return [[plane[row] * plane[column] for column in range(4)] for row in range(4)]


def _add_matrix(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [[left[row][column] + right[row][column] for column in range(4)] for row in range(4)]


def _quadrics(vertices: list[tuple[float, float, float]], faces: list[dict[str, Any]]) -> list[list[list[float]]]:
    result = [[[0.0] * 4 for _ in range(4)] for _ in vertices]
    for face in faces:
        a, b, c = (vertices[index] for index in face["vertices"])
        normal = _normal(a, b, c)
        plane = (*normal, -_dot(normal, a))
        matrix = _quadric(plane)
        for index in face["vertices"]:
            result[index] = _add_matrix(result[index], matrix)
    return result


def _qcost(matrix: list[list[float]], point: tuple[float, float, float]) -> float:
    vector = (*point, 1.0)
    return sum(vector[row] * matrix[row][column] * vector[column] for row in range(4) for column in range(4))


def _face_normal(vertices: list[tuple[float, float, float]], face: dict[str, Any]) -> tuple[float, float, float]:
    return _normal(*(vertices[index] for index in face["vertices"]))


def _hard_edges(
    vertices: list[tuple[float, float, float]], faces: list[dict[str, Any]], edges: dict[tuple[int, int], list[int]], threshold: float,
) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    cosine = math.cos(math.radians(threshold))
    normals = [_face_normal(vertices, face) for face in faces]
    for edge, owners in edges.items():
        if len(owners) == 2 and _dot(normals[owners[0]], normals[owners[1]]) < cosine:
            result.add(edge)
    return result


def _bounds(vertices: list[tuple[float, float, float]], faces: list[dict[str, Any]]) -> dict[str, list[float]]:
    used = sorted({index for face in faces for index in face["vertices"]})
    return {
        "min": [min(vertices[index][axis] for index in used) for axis in range(3)],
        "max": [max(vertices[index][axis] for index in used) for axis in range(3)],
    }


def _surface(vertices: list[tuple[float, float, float]], faces: list[dict[str, Any]]) -> float:
    return sum(_area(*(vertices[index] for index in face["vertices"])) for face in faces)


def _simulate(
    vertices: list[tuple[float, float, float]], uvs: list[tuple[float, float]], faces: list[dict[str, Any]],
    keep: int, drop: int, point: tuple[float, float, float], uv: tuple[float, float], policy: dict[str, Any],
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float]], list[dict[str, Any]]] | None:
    new_vertices = list(vertices); new_vertices[keep] = point
    new_uvs = list(uvs); new_uvs[keep] = uv
    output: list[dict[str, Any]] = []
    old_normals = [_face_normal(vertices, face) for face in faces]
    max_angle = float(policy["max_normal_deviation_degrees"])
    cosine = math.cos(math.radians(max_angle))
    max_uv_ratio = 1.0 + float(policy["max_uv_distortion_percent"]) / 100.0
    for face_index, face in enumerate(faces):
        replaced = tuple(keep if index == drop else index for index in face["vertices"])
        if len(set(replaced)) < 3:
            continue
        candidate = dict(face); candidate["vertices"] = _rotated(replaced)
        try:
            new_normal = _face_normal(new_vertices, candidate)
        except DecimationError:
            return None
        if keep in face["vertices"] or drop in face["vertices"]:
            if _dot(old_normals[face_index], new_normal) < cosine:
                return None
            old_uv_area = _uv_area(*(uvs[index] for index in face["vertices"]))
            new_uv_area = _uv_area(*(new_uvs[index] for index in candidate["vertices"]))
            if abs(old_uv_area) > EPSILON:
                if old_uv_area * new_uv_area <= 0:
                    return None
                ratio = abs(new_uv_area / old_uv_area)
                if ratio > max_uv_ratio or ratio < 1.0 / max_uv_ratio:
                    return None
        output.append(candidate)
    output.sort(key=lambda face: (face["material"], face["texture"] or "", face["vertices"]))
    if not output or len({face["vertices"] for face in output}) != len(output):
        return None
    try:
        _edges(output)
    except DecimationError:
        return None
    return new_vertices, new_uvs, output


def _compact(
    vertices: list[tuple[float, float, float]], uvs: list[tuple[float, float]], faces: list[dict[str, Any]], source_ir: dict[str, Any],
) -> dict[str, Any]:
    used = sorted({index for face in faces for index in face["vertices"]}, key=lambda index: (vertices[index], uvs[index]))
    remap = {old: new for new, old in enumerate(used)}
    compact_faces: list[dict[str, Any]] = []
    for face_index, face in enumerate(faces):
        indices = _rotated(tuple(remap[index] for index in face["vertices"]))
        points = [vertices[used[index]] for index in indices]
        normal = _normal(points[0], points[1], points[2])
        output = {
            "id": f"approx_triangle_{face_index:03d}", "vertices": list(indices), "uvs": list(indices),
            "normal": list(normal), "source_material": source_ir["materials"][0],
            "material_alias": face["material"], "primitive": "triangle",
        }
        if face["texture"] is not None:
            output["texture"] = face["texture"]
        compact_faces.append(output)
    compact_vertices = [list(vertices[index]) for index in used]
    compact_uvs = [list(uvs[index]) for index in used]
    bounds = {
        "min": [min(point[axis] for point in compact_vertices) for axis in range(3)],
        "max": [max(point[axis] for point in compact_vertices) for axis in range(3)],
    }
    output = copy.deepcopy(source_ir)
    output["vertices"] = compact_vertices
    output["uvs"] = compact_uvs
    output["faces"] = compact_faces
    output["bounds"] = bounds
    output["dimensions"] = [bounds["max"][axis] - bounds["min"][axis] for axis in range(3)]
    return output


def _point_triangle_distance(point: tuple[float, float, float], a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> float:
    # Ericson's closest-point regions, expressed without external numeric dependencies.
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(point, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0: return _length(ap)
    bp = _sub(point, b); d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0 and d4 <= d3: return _length(bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3); return _length(_sub(point, tuple(a[i] + v * ab[i] for i in range(3))))
    cp = _sub(point, c); d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0 and d5 <= d6: return _length(cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6); return _length(_sub(point, tuple(a[i] + w * ac[i] for i in range(3))))
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); bc = _sub(c, b)
        return _length(_sub(point, tuple(b[i] + w * bc[i] for i in range(3))))
    normal = _normal(a, b, c)
    return abs(_dot(_sub(point, a), normal))


def _mask(vertices: list[tuple[float, float, float]], faces: list[dict[str, Any]], direction: str) -> set[tuple[int, int]]:
    projections = {
        "front": lambda p: (p[0], p[1]), "rear": lambda p: (-p[0], p[1]),
        "left": lambda p: (p[2], p[1]), "right": lambda p: (-p[2], p[1]),
        "three_quarter": lambda p: ((p[0] + p[2]) / math.sqrt(2), p[1]),
    }
    projected = [projections[direction](point) for point in vertices]
    min_x, max_x = min(p[0] for p in projected), max(p[0] for p in projected)
    min_y, max_y = min(p[1] for p in projected), max(p[1] for p in projected)
    span_x, span_y = max(max_x - min_x, EPSILON), max(max_y - min_y, EPSILON)
    result: set[tuple[int, int]] = set()
    for face in faces:
        triangle = [projected[index] for index in face["vertices"]]
        pixel = [((p[0] - min_x) / span_x * (SILHOUETTE_GRID - 1), (p[1] - min_y) / span_y * (SILHOUETTE_GRID - 1)) for p in triangle]
        x0, x1 = max(0, math.floor(min(p[0] for p in pixel))), min(SILHOUETTE_GRID - 1, math.ceil(max(p[0] for p in pixel)))
        y0, y1 = max(0, math.floor(min(p[1] for p in pixel))), min(SILHOUETTE_GRID - 1, math.ceil(max(p[1] for p in pixel)))
        denominator = (pixel[1][1] - pixel[2][1]) * (pixel[0][0] - pixel[2][0]) + (pixel[2][0] - pixel[1][0]) * (pixel[0][1] - pixel[2][1])
        if abs(denominator) <= EPSILON:
            continue
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px, py = x + 0.5, y + 0.5
                w1 = ((pixel[1][1] - pixel[2][1]) * (px - pixel[2][0]) + (pixel[2][0] - pixel[1][0]) * (py - pixel[2][1])) / denominator
                w2 = ((pixel[2][1] - pixel[0][1]) * (px - pixel[2][0]) + (pixel[0][0] - pixel[2][0]) * (py - pixel[2][1])) / denominator
                w3 = 1 - w1 - w2
                if min(w1, w2, w3) >= -1e-9:
                    result.add((x, y))
    return result


def _metrics(source: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    source_vertices, source_faces = source["vertices"], source["faces"]
    final_vertices, final_faces = final["vertices"], final["faces"]
    distances = [
        min(_point_triangle_distance(point, *(source_vertices[index] for index in face["vertices"])) for face in source_faces)
        for point in final_vertices
    ]
    source_centroids = [tuple(sum(source_vertices[index][axis] for index in face["vertices"]) / 3 for axis in range(3)) for face in source_faces]
    source_normals = [_face_normal(source_vertices, face) for face in source_faces]
    normal_deviations: list[float] = []
    uv_distortions: list[float] = []
    for face in final_faces:
        centroid = tuple(sum(final_vertices[index][axis] for index in face["vertices"]) / 3 for axis in range(3))
        nearest = min(range(len(source_faces)), key=lambda index: (_length(_sub(centroid, source_centroids[index])), index))
        agreement = max(-1.0, min(1.0, _dot(_face_normal(final_vertices, face), source_normals[nearest])))
        normal_deviations.append(math.degrees(math.acos(agreement)))
        final_geo = _area(*(final_vertices[index] for index in face["vertices"]))
        final_uv = abs(_uv_area(*(final["uvs"][index] for index in face["vertices"])))
        source_geo = _area(*(source_vertices[index] for index in source_faces[nearest]["vertices"]))
        source_uv = abs(_uv_area(*(source["uvs"][index] for index in source_faces[nearest]["vertices"])))
        if min(final_geo, source_geo, final_uv, source_uv) > EPSILON:
            uv_distortions.append(abs((final_uv / final_geo) / (source_uv / source_geo) - 1.0) * 100)
    silhouettes: dict[str, float] = {}
    for direction in ("front", "rear", "left", "right", "three_quarter"):
        before, after = _mask(source_vertices, source_faces, direction), _mask(final_vertices, final_faces, direction)
        silhouettes[direction] = round(len(before & after) / max(1, len(before | after)), 6)
    source_bounds, final_bounds = _bounds(source_vertices, source_faces), _bounds(final_vertices, final_faces)
    bounds_delta = max(abs(source_bounds[kind][axis] - final_bounds[kind][axis]) for kind in ("min", "max") for axis in range(3))
    source_area, final_area = _surface(source_vertices, source_faces), _surface(final_vertices, final_faces)
    return {
        "maximum_vertex_displacement": max(distances, default=0.0),
        "mean_geometric_error": sum(distances) / max(1, len(distances)),
        "bounds_max_delta": bounds_delta,
        "source_surface_area": source_area,
        "final_surface_area": final_area,
        "surface_area_delta_percent": abs(final_area - source_area) * 100 / source_area,
        "maximum_normal_deviation_degrees": max(normal_deviations, default=0.0),
        "mean_normal_deviation_degrees": sum(normal_deviations) / max(1, len(normal_deviations)),
        "maximum_uv_distortion_percent": max(uv_distortions, default=0.0),
        "silhouette_iou": silhouettes,
        "minimum_silhouette_iou": min(silhouettes.values()),
    }


def simplify_approximate_ir(ir: dict[str, Any], target_bytes: int, policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reduce a valid typed mesh to the least-destructive <= target byte result."""
    mesh = _triangulate(ir)
    vertices, uvs, faces = list(mesh["vertices"]), list(mesh["uvs"]), list(mesh["faces"])
    source = copy.deepcopy(mesh)
    source_bytes = _bytes(len(faces))
    if source_bytes <= target_bytes:
        output = _compact(vertices, uvs, faces, ir)
        return output, {"algorithm": ALGORITHM, "algorithm_version": ALGORITHM_VERSION, "applied": False, "collapse_count": 0}
    rejected: dict[str, int] = {}
    collapses = 0
    initial_bounds = _bounds(vertices, faces)
    physical: dict[tuple[float, float, float], int] = {}
    for point in vertices: physical[point] = physical.get(point, 0) + 1
    seam_vertices = {index for index, point in enumerate(vertices) if physical[point] > 1}
    while _bytes(len(faces)) > target_bytes:
        edge_owners = _edges(faces)
        quadrics = _quadrics(vertices, faces)
        hard = _hard_edges(vertices, faces, edge_owners, float(policy["hard_normal_degrees"]))
        boundary = {index for edge, owners in edge_owners.items() if len(owners) == 1 for index in edge}
        ground_y = initial_bounds["min"][1]
        ground = {index for index, point in enumerate(vertices) if abs(point[1] - ground_y) <= 1e-8}
        candidates: list[tuple[float, int, int, tuple[float, float, float], tuple[float, float]]] = []
        for a, b in sorted(edge_owners):
            edge = (a, b)
            if a in seam_vertices or b in seam_vertices:
                rejected["uv_seam"] = rejected.get("uv_seam", 0) + 1; continue
            if (a in boundary or b in boundary) and not (a in boundary and b in boundary and len(edge_owners[edge]) == 1):
                rejected["boundary"] = rejected.get("boundary", 0) + 1; continue
            if (a in ground or b in ground) and not (a in ground and b in ground):
                rejected["ground_contact"] = rejected.get("ground_contact", 0) + 1; continue
            matrix = _add_matrix(quadrics[a], quadrics[b])
            choices = (
                (vertices[a], uvs[a], 0), (vertices[b], uvs[b], 1),
                (tuple((vertices[a][i] + vertices[b][i]) / 2 for i in range(3)), tuple((uvs[a][i] + uvs[b][i]) / 2 for i in range(2)), 2),
            )
            point, uv, choice = min(choices, key=lambda item: (_qcost(matrix, item[0]), item[2]))
            simulated = _simulate(vertices, uvs, faces, a, b, point, uv, policy)
            if simulated is None:
                rejected["invalid_collapse"] = rejected.get("invalid_collapse", 0) + 1; continue
            candidates.append((_qcost(matrix, point), a, b, point, uv))
        if not candidates:
            raise DecimationError(
                "approximate_simplification_target_unreachable",
                "no valid constrained collapse can reach the project display-list target",
                target_bytes=target_bytes, best_valid_bytes=_bytes(len(faces)), rejected=rejected,
            )
        _cost, a, b, point, uv = min(candidates, key=lambda item: (round(item[0], 12), item[1], item[2], item[3], item[4]))
        simulated = _simulate(vertices, uvs, faces, a, b, point, uv, policy)
        assert simulated is not None
        vertices, uvs, faces = simulated
        collapses += 1
    output = _compact(vertices, uvs, faces, ir)
    final_mesh = _triangulate(output)
    metrics = _metrics(source, final_mesh)
    thresholds = {
        "max_geometric_error": float(policy["max_geometric_error"]),
        "max_bounds_delta": float(policy["max_bounds_delta"]),
        "max_surface_area_delta_percent": float(policy["max_surface_area_delta_percent"]),
        "min_silhouette_iou": float(policy["min_silhouette_iou"]),
        "max_normal_deviation_degrees": float(policy["max_normal_deviation_degrees"]),
        "max_uv_distortion_percent": float(policy["max_uv_distortion_percent"]),
    }
    violations = []
    if metrics["maximum_vertex_displacement"] > thresholds["max_geometric_error"]: violations.append("geometric_error")
    if metrics["bounds_max_delta"] > thresholds["max_bounds_delta"]: violations.append("bounds")
    if metrics["surface_area_delta_percent"] > thresholds["max_surface_area_delta_percent"]: violations.append("surface_area")
    if metrics["minimum_silhouette_iou"] < thresholds["min_silhouette_iou"]: violations.append("silhouette")
    if metrics["maximum_normal_deviation_degrees"] > thresholds["max_normal_deviation_degrees"]: violations.append("normal_deviation")
    if metrics["maximum_uv_distortion_percent"] > thresholds["max_uv_distortion_percent"]: violations.append("uv_distortion")
    if violations:
        raise DecimationError(
            "approximate_simplification_target_unreachable",
            "the byte target requires geometry outside the declared fidelity envelope",
            target_bytes=target_bytes, best_valid_bytes=_bytes(len(faces)), violations=violations, metrics=metrics,
        )
    report = {
        "algorithm": ALGORITHM, "algorithm_version": ALGORITHM_VERSION, "applied": True,
        "target_bytes": target_bytes, "collapse_count": collapses,
        "rejected_collapse_reasons": dict(sorted(rejected.items())),
        "source": {"triangles": len(source["faces"]), "vertices": len(source["vertices"]), "projected_bytes": source_bytes, "semantic_sha256": _hash(source)},
        "final": {"triangles": len(faces), "vertices": len({index for face in faces for index in face["vertices"]}), "projected_bytes": _bytes(len(faces)), "semantic_sha256": _hash(output)},
        "face_reduction_percent": round((len(source["faces"]) - len(faces)) * 100 / len(source["faces"]), 3),
        "byte_reduction_percent": round((source_bytes - _bytes(len(faces))) * 100 / source_bytes, 3),
        "thresholds": thresholds, "metrics": metrics,
        "settings": {
            "deterministic_tie_break": "rounded_quadric_cost_then_canonical_edge",
            "hard_normal_degrees": policy["hard_normal_degrees"], "silhouette_grid": SILHOUETTE_GRID,
            "preserve_boundaries": True, "preserve_uv_seams": True,
            "preserve_material_boundaries": True, "preserve_hard_normals": True,
        },
    }
    return output, report
