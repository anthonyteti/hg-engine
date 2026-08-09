"""Deterministic geometry-only coarse QEM reduction for Stage 4O.

This module operates on a deliberately tiny IR: float positions plus indexed
triangles.  It derives transient face planes for geometric constraints, but it
never creates runtime normals, UVs, materials, collision, or Nintendo DS data.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from typing import Any

from .mesh_decimate import (
    EPSILON,
    _add_matrix,
    _area,
    _dot,
    _length,
    _normal,
    _point_triangle_distance,
    _qcost,
    _quadric,
    _sub,
)


ALGORITHM = "constrained_geometry_qem"
ALGORITHM_VERSION = 1
SILHOUETTE_GRID = 64
_DIRECTIONS = ("front", "rear", "left", "right", "three_quarter")


class GeometryReductionError(ValueError):
    """Geometry is invalid or cannot reach the bounded Stage 4O target."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _semantic_hash(value: object) -> str:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(data).hexdigest()


def _rotated(face: tuple[int, int, int]) -> tuple[int, int, int]:
    return min(face, (face[1], face[2], face[0]), (face[2], face[0], face[1]))


def canonical_geometry(
    positions: list[tuple[float, float, float]] | tuple[tuple[float, float, float], ...],
    faces: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
) -> dict[str, Any]:
    """Canonicalize source ordering without merging geometric identities."""
    if not positions or not faces:
        raise GeometryReductionError("geometry_predecimation_empty", "geometry requires positions and triangles")
    if len(set(positions)) != len(positions):
        raise GeometryReductionError(
            "geometry_predecimation_duplicate_position",
            "coincident source position records are unsupported; Stage 4O does not weld topology",
        )
    ordered = sorted(enumerate(positions), key=lambda item: (item[1], item[0]))
    remap = {old: new for new, (old, _point) in enumerate(ordered)}
    output_positions = [tuple(float(value) for value in point) for _old, point in ordered]
    output_faces: list[tuple[int, int, int]] = []
    for face in faces:
        if len(face) != 3 or any(isinstance(index, bool) or not isinstance(index, int) for index in face):
            raise GeometryReductionError("geometry_predecimation_invalid_indices", "faces must contain three integer indices")
        if any(index < 0 or index >= len(positions) for index in face):
            raise GeometryReductionError("geometry_predecimation_invalid_indices", "face index is outside POSITION")
        mapped = _rotated(tuple(remap[index] for index in face))
        if len(set(mapped)) != 3:
            raise GeometryReductionError("geometry_predecimation_degenerate", "triangle repeats a position")
        try:
            _normal(*(output_positions[index] for index in mapped))
        except ValueError as error:
            raise GeometryReductionError("geometry_predecimation_degenerate", "triangle has zero area") from error
        output_faces.append(mapped)
    output_faces.sort()
    if len(set(output_faces)) != len(output_faces):
        raise GeometryReductionError("geometry_predecimation_duplicate_face", "source contains duplicate oriented triangles")
    return {"schema_version": 1, "positions": output_positions, "faces": output_faces}


def _edge_data(faces: list[tuple[int, int, int]]) -> dict[tuple[int, int], list[tuple[int, int]]]:
    result: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face_index, face in enumerate(faces):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = (min(a, b), max(a, b))
            direction = 1 if (a, b) == edge else -1
            result.setdefault(edge, []).append((face_index, direction))
    return result


def _component_count(faces: list[tuple[int, int, int]], edges: dict[tuple[int, int], list[tuple[int, int]]]) -> int:
    adjacency = [set() for _ in faces]
    for owners in edges.values():
        if len(owners) == 2:
            a, b = owners[0][0], owners[1][0]
            adjacency[a].add(b); adjacency[b].add(a)
    unseen = set(range(len(faces)))
    count = 0
    while unseen:
        count += 1
        stack = [min(unseen)]
        unseen.remove(stack[0])
        while stack:
            current = stack.pop()
            for neighbor in sorted(adjacency[current]):
                if neighbor in unseen:
                    unseen.remove(neighbor); stack.append(neighbor)
    return count


def _boundary_loops(edges: dict[tuple[int, int], list[tuple[int, int]]]) -> int:
    adjacency: dict[int, set[int]] = {}
    for (a, b), owners in edges.items():
        if len(owners) == 1:
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    if not adjacency:
        return 0
    if any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise GeometryReductionError(
            "geometry_predecimation_invalid_boundary",
            "open-manifold boundaries must form closed non-branching loops",
        )
    unseen = set(adjacency)
    loops = 0
    while unseen:
        loops += 1
        stack = [min(unseen)]
        unseen.remove(stack[0])
        while stack:
            vertex = stack.pop()
            for neighbor in sorted(adjacency[vertex]):
                if neighbor in unseen:
                    unseen.remove(neighbor); stack.append(neighbor)
    return loops


def validate_geometry(mesh: dict[str, Any], *, require_one_component: bool = False) -> dict[str, Any]:
    positions = [tuple(point) for point in mesh["positions"]]
    faces = [tuple(face) for face in mesh["faces"]]
    edges = _edge_data(faces)
    if any(len(owners) > 2 for owners in edges.values()):
        raise GeometryReductionError("geometry_predecimation_non_manifold", "an edge has more than two incident faces")
    if any(len(owners) == 2 and owners[0][1] == owners[1][1] for owners in edges.values()):
        raise GeometryReductionError("geometry_predecimation_inconsistent_winding", "adjacent faces traverse an edge in the same direction")
    components = _component_count(faces, edges)
    if require_one_component and components != 1:
        raise GeometryReductionError(
            "geometry_predecimation_component_count",
            "canonical Stage 4O proof requires one connected component",
            observed=components,
        )
    loops = _boundary_loops(edges)
    used = {index for face in faces for index in face}
    if len(used) != len(positions):
        raise GeometryReductionError("geometry_predecimation_unreferenced_position", "every POSITION must be referenced")
    bounds = {
        "min": [min(point[axis] for point in positions) for axis in range(3)],
        "max": [max(point[axis] for point in positions) for axis in range(3)],
    }
    return {
        "valid": True,
        "positions": len(positions),
        "triangles": len(faces),
        "edges": len(edges),
        "connected_components": components,
        "boundary_edges": sum(len(owners) == 1 for owners in edges.values()),
        "boundary_loops": loops,
        "bounds": bounds,
        "semantic_sha256": _semantic_hash(mesh),
    }


def inspect_geometry_quality(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]],
) -> dict[str, Any]:
    """Read-only tolerant topology evidence; never rewrites invalid faces."""
    repeated = 0
    zero_area = 0
    duplicate = 0
    seen: set[tuple[int, int, int]] = set()
    usable: list[tuple[int, int, int]] = []
    for face in faces:
        if len(set(face)) != 3:
            repeated += 1
            continue
        try:
            _normal(*(positions[index] for index in face))
        except ValueError:
            zero_area += 1
            continue
        canonical = _rotated(face)
        if canonical in seen:
            duplicate += 1
        seen.add(canonical)
        usable.append(canonical)
    edges = _edge_data(usable)
    nonmanifold = sum(len(owners) > 2 for owners in edges.values())
    winding = sum(len(owners) == 2 and owners[0][1] == owners[1][1] for owners in edges.values())
    components = _component_count(usable, edges) if usable else 0
    boundary_edges = sum(len(owners) == 1 for owners in edges.values())
    try:
        loops: int | None = _boundary_loops(edges)
    except GeometryReductionError:
        loops = None
    return {
        "positions": len(positions),
        "triangles": len(faces),
        "repeated_vertex_triangles": repeated,
        "zero_area_triangles": zero_area,
        "duplicate_faces": duplicate,
        "nonmanifold_edges": nonmanifold,
        "inconsistent_winding_edges": winding,
        "connected_components": components,
        "open_boundary_edges": boundary_edges,
        "open_boundary_loops": loops,
        "valid_for_predecimation": not any((repeated, zero_area, duplicate, nonmanifold, winding)) and loops is not None,
    }


def _quadrics(positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> list[list[list[float]]]:
    result = [[[0.0] * 4 for _ in range(4)] for _ in positions]
    for face in faces:
        a, b, c = (positions[index] for index in face)
        normal = _normal(a, b, c)
        matrix = _quadric((*normal, -_dot(normal, a)))
        for index in face:
            result[index] = _add_matrix(result[index], matrix)
    return result


def _hard_edges(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    edges: dict[tuple[int, int], list[tuple[int, int]]],
    threshold_degrees: float,
) -> set[tuple[int, int]]:
    normals = [_normal(*(positions[index] for index in face)) for face in faces]
    cosine = math.cos(math.radians(threshold_degrees))
    return {
        edge for edge, owners in edges.items()
        if len(owners) == 2 and _dot(normals[owners[0][0]], normals[owners[1][0]]) < cosine
    }


def _collapse_candidate(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    edges: dict[tuple[int, int], list[tuple[int, int]]],
    incident: list[set[int]],
    neighbors: list[set[int]],
    quadrics: list[list[list[float]]],
    edge: tuple[int, int],
    boundary_vertices: set[int],
    ground_vertices: set[int],
    hard_edges: set[tuple[int, int]],
    extrema: list[set[int]],
    face_index: dict[tuple[int, int, int], int],
    policy: dict[str, Any],
) -> tuple[float, tuple[float, float, float], tuple[tuple[int, ...], tuple[tuple[int, int, int], ...]]] | tuple[None, str, None]:
    a, b = edge
    owners = edges[edge]
    common = neighbors[a] & neighbors[b]
    opposite = {next(index for index in faces[owner[0]] if index not in edge) for owner in owners}
    if common != opposite:
        return None, "topology_link", None
    a_boundary, b_boundary = a in boundary_vertices, b in boundary_vertices
    if a_boundary != b_boundary or (a_boundary and len(owners) != 1):
        return None, "boundary", None
    a_ground, b_ground = a in ground_vertices, b in ground_vertices
    if a_ground != b_ground:
        return None, "ground_contact", None
    matrix = _add_matrix(quadrics[a], quadrics[b])
    midpoint = tuple((positions[a][axis] + positions[b][axis]) / 2 for axis in range(3))
    choices = [(positions[a], 0), (positions[b], 1), (midpoint, 2)]
    memberships_a = tuple(a in group for group in extrema)
    memberships_b = tuple(b in group for group in extrema)
    if memberships_a != memberships_b:
        if sum(memberships_a) > sum(memberships_b):
            choices = [(positions[a], 0)]
        elif sum(memberships_b) > sum(memberships_a):
            choices = [(positions[b], 1)]
    point, _choice = min(choices, key=lambda item: (round(_qcost(matrix, item[0]), 15), item[1]))
    impacted = incident[a] | incident[b]
    changed: list[tuple[int, int, int]] = []
    cosine = math.cos(math.radians(float(policy["max_face_rotation_degrees"])))
    for impacted_index in sorted(impacted):
        face = faces[impacted_index]
        replaced = tuple(a if index == b else index for index in face)
        if len(set(replaced)) < 3:
            continue
        old_normal = _normal(*(positions[index] for index in face))
        points = [point if index == a else positions[index] for index in replaced]
        try:
            new_normal = _normal(points[0], points[1], points[2])
        except ValueError:
            return None, "degenerate", None
        if _dot(old_normal, new_normal) <= 0 or _dot(old_normal, new_normal) < cosine:
            return None, "face_rotation", None
        canonical = _rotated(replaced)
        existing = face_index.get(canonical)
        if (existing is not None and existing not in impacted) or canonical in changed:
            return None, "duplicate_face", None
        changed.append(canonical)
    if not changed and len(impacted) == len(faces):
        return None, "empty_mesh", None
    base_cost = _qcost(matrix, point)
    diagonal_penalty = float(policy["crease_penalty"])
    if edge in hard_edges:
        base_cost += diagonal_penalty
    return base_cost, point, (tuple(sorted(impacted)), tuple(changed))


def _compact(positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> dict[str, Any]:
    used = sorted({index for face in faces for index in face}, key=lambda index: positions[index])
    remap = {old: new for new, old in enumerate(used)}
    output_positions = [positions[index] for index in used]
    output_faces = sorted(_rotated(tuple(remap[index] for index in face)) for face in faces)
    return canonical_geometry(output_positions, output_faces)


def _surface(positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> float:
    return sum(_area(*(positions[index] for index in face)) for face in faces)


def _projection(point: tuple[float, float, float], direction: str) -> tuple[float, float]:
    if direction == "front": return point[0], point[1]
    if direction == "rear": return -point[0], point[1]
    if direction == "left": return point[2], point[1]
    if direction == "right": return -point[2], point[1]
    return (point[0] + point[2]) / math.sqrt(2), point[1]


def _mask(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    direction: str,
    projection_bounds: tuple[float, float, float, float],
) -> set[tuple[int, int]]:
    projected = [_projection(point, direction) for point in positions]
    min_x, max_x, min_y, max_y = projection_bounds
    span_x, span_y = max(max_x - min_x, EPSILON), max(max_y - min_y, EPSILON)
    result: set[tuple[int, int]] = set()
    for face in faces:
        triangle = [projected[index] for index in face]
        pixels = [((p[0] - min_x) / span_x * 63, (p[1] - min_y) / span_y * 63) for p in triangle]
        x0 = max(0, math.floor(min(p[0] for p in pixels))); x1 = min(63, math.ceil(max(p[0] for p in pixels)))
        y0 = max(0, math.floor(min(p[1] for p in pixels))); y1 = min(63, math.ceil(max(p[1] for p in pixels)))
        denominator = (pixels[1][1] - pixels[2][1]) * (pixels[0][0] - pixels[2][0]) + (pixels[2][0] - pixels[1][0]) * (pixels[0][1] - pixels[2][1])
        if abs(denominator) <= EPSILON:
            continue
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px, py = x + 0.5, y + 0.5
                w1 = ((pixels[1][1] - pixels[2][1]) * (px - pixels[2][0]) + (pixels[2][0] - pixels[1][0]) * (py - pixels[2][1])) / denominator
                w2 = ((pixels[2][1] - pixels[0][1]) * (px - pixels[2][0]) + (pixels[0][0] - pixels[2][0]) * (py - pixels[2][1])) / denominator
                if min(w1, w2, 1 - w1 - w2) >= -1e-9:
                    result.add((x, y))
    return result


def fidelity_metrics(source: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    source_positions = [tuple(point) for point in source["positions"]]
    source_faces = [tuple(face) for face in source["faces"]]
    final_positions = [tuple(point) for point in final["positions"]]
    final_faces = [tuple(face) for face in final["faces"]]
    minimum = [min(point[axis] for point in source_positions) for axis in range(3)]
    maximum = [max(point[axis] for point in source_positions) for axis in range(3)]
    diagonal = max(_length(tuple(maximum[axis] - minimum[axis] for axis in range(3))), EPSILON)
    final_min = [min(point[axis] for point in final_positions) for axis in range(3)]
    final_max = [max(point[axis] for point in final_positions) for axis in range(3)]
    bounds_delta = max(abs(value - reference) for values, references in ((final_min, minimum), (final_max, maximum)) for value, reference in zip(values, references, strict=True))
    source_to_final = [
        min(_point_triangle_distance(point, *(final_positions[index] for index in face)) for face in final_faces)
        for point in source_positions
    ]
    final_to_source = [
        min(_point_triangle_distance(point, *(source_positions[index] for index in face)) for face in source_faces)
        for point in final_positions
    ]
    distances = source_to_final + final_to_source
    silhouettes: dict[str, float] = {}
    for direction in _DIRECTIONS:
        projected = [_projection(point, direction) for point in source_positions]
        bounds = (min(p[0] for p in projected), max(p[0] for p in projected), min(p[1] for p in projected), max(p[1] for p in projected))
        before = _mask(source_positions, source_faces, direction, bounds)
        after = _mask(final_positions, final_faces, direction, bounds)
        silhouettes[direction] = round(len(before & after) / max(1, len(before | after)), 6)
    source_area, final_area = _surface(source_positions, source_faces), _surface(final_positions, final_faces)
    return {
        "bounds_max_delta": bounds_delta,
        "bounds_max_delta_ratio": bounds_delta / diagonal,
        "maximum_geometric_error": max(distances, default=0.0),
        "maximum_geometric_error_ratio": max(distances, default=0.0) / diagonal,
        "mean_geometric_error": sum(distances) / max(1, len(distances)),
        "mean_geometric_error_ratio": sum(distances) / max(1, len(distances)) / diagonal,
        "source_surface_area": source_area,
        "final_surface_area": final_area,
        "surface_area_delta_percent": abs(final_area - source_area) * 100 / source_area,
        "silhouette_iou": silhouettes,
        "minimum_silhouette_iou": min(silhouettes.values()),
        "source_diagonal": diagonal,
    }


def _violations(metrics: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    result = []
    if metrics["bounds_max_delta_ratio"] > policy["max_bounds_delta_ratio"]: result.append("bounds")
    if metrics["maximum_geometric_error_ratio"] > policy["max_geometric_error_ratio"]: result.append("geometric_error")
    if metrics["surface_area_delta_percent"] > policy["max_surface_area_delta_percent"]: result.append("surface_area")
    if metrics["minimum_silhouette_iou"] < policy["min_silhouette_iou"]: result.append("silhouette")
    return result


def reduce_geometry(mesh: dict[str, Any], policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Progressively reduce to the least-destructive target state."""
    source = canonical_geometry(mesh["positions"], mesh["faces"])
    source_topology = validate_geometry(source, require_one_component=bool(policy["require_one_component"]))
    target_faces = int(policy["target_faces"]); target_positions = int(policy["target_positions"])
    positions_original = [tuple(point) for point in source["positions"]]
    faces = [tuple(face) for face in source["faces"]]
    minimum = [min(point[axis] for point in positions_original) for axis in range(3)]
    maximum = [max(point[axis] for point in positions_original) for axis in range(3)]
    center = tuple((minimum[axis] + maximum[axis]) / 2 for axis in range(3))
    scale = max(_length(tuple(maximum[axis] - minimum[axis] for axis in range(3))), EPSILON)
    positions = [tuple((point[axis] - center[axis]) / scale for axis in range(3)) for point in positions_original]
    accepted = 0
    rejected: dict[str, int] = {}
    collapse_plan: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    while len(faces) > target_faces or len({index for face in faces for index in face}) > target_positions:
        edge_records = _edge_data(faces)
        if any(len(owners) > 2 for owners in edge_records.values()):
            raise GeometryReductionError("geometry_predecimation_non_manifold", "reduction produced a non-manifold edge")
        edges = {edge: owners for edge, owners in edge_records.items()}
        incident = [set() for _ in positions]
        neighbors = [set() for _ in positions]
        for face_index, face in enumerate(faces):
            for index in face: incident[index].add(face_index)
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                neighbors[a].add(b); neighbors[b].add(a)
        quadrics = _quadrics(positions, faces)
        hard = _hard_edges(positions, faces, edges, float(policy["crease_angle_degrees"]))
        face_index = {face: index for index, face in enumerate(faces)}
        boundary_vertices = {index for edge, owners in edges.items() if len(owners) == 1 for index in edge}
        current_min_y = min(positions[index][1] for face in faces for index in face)
        ground_vertices = {
            index for face in faces for index in face
            if abs(positions[index][1] - current_min_y) <= float(policy["ground_tolerance_ratio"])
        } if policy["preserve_ground_contact"] else set()
        used = {index for face in faces for index in face}
        extrema: list[set[int]] = []
        for axis in range(3):
            low = min(positions[index][axis] for index in used); high = max(positions[index][axis] for index in used)
            extrema.extend((
                {index for index in used if abs(positions[index][axis] - low) <= 1e-10},
                {index for index in used if abs(positions[index][axis] - high) <= 1e-10},
            ))
        candidates = []
        for edge in sorted(edges):
            result = _collapse_candidate(
                positions, faces, edges, incident, neighbors, quadrics, edge,
                boundary_vertices, ground_vertices, hard, extrema, face_index, policy,
            )
            if result[0] is None:
                reason = str(result[1]); rejected[reason] = rejected.get(reason, 0) + 1
                continue
            cost, point, change = result
            candidates.append((round(float(cost), 15), edge[0], edge[1], point, change))
        if not candidates:
            raise GeometryReductionError(
                "geometry_predecimation_target_unreachable",
                "no valid constrained collapse can reach the preprocessing envelope",
                target_faces=target_faces,
                target_positions=target_positions,
                best_valid_faces=len(faces),
                best_valid_positions=len({index for face in faces for index in face}),
                rejected_collapse_reasons=dict(sorted(rejected.items())),
            )
        ordered_candidates = sorted(candidates, key=lambda item: (item[0], item[1], item[2], item[3]))
        selected = []
        protected_neighborhood: set[int] = set()
        predicted_faces = len(faces)
        predicted_positions = len({index for face in faces for index in face})
        for candidate in ordered_candidates:
            cost, keep, drop, point, change = candidate
            impacted, changed = change
            neighborhood = {keep, drop} | neighbors[keep] | neighbors[drop]
            if neighborhood & protected_neighborhood:
                rejected["batch_conflict"] = rejected.get("batch_conflict", 0) + 1
                continue
            face_delta = len(impacted) - len(changed)
            if predicted_faces - face_delta < target_faces and predicted_positions - 1 <= target_positions:
                continue
            selected.append(candidate)
            protected_neighborhood.update(neighborhood)
            predicted_faces -= face_delta
            predicted_positions -= 1
            if predicted_faces <= target_faces and predicted_positions <= target_positions:
                break
        if not selected:
            selected = [ordered_candidates[0]]
        all_impacted: set[int] = set()
        all_changed: list[tuple[int, int, int]] = []
        for cost, keep, drop, point, change in selected:
            impacted, changed = change
            positions[keep] = point
            all_impacted.update(impacted)
            all_changed.extend(changed)
            accepted += 1
        faces = sorted([face for index, face in enumerate(faces) if index not in all_impacted] + all_changed)
        for cost, keep, drop, _point, _change in selected:
            collapse_plan.append({"keep": keep, "drop": drop, "cost": cost, "faces_after_batch": len(faces)})
        snapshots.append(_compact(positions, faces))
    normalized_final = _compact(positions, faces)
    final_positions = [
        struct.unpack("<3f", struct.pack("<3f", *(point[axis] * scale + center[axis] for axis in range(3))))
        for point in normalized_final["positions"]
    ]
    final = canonical_geometry(final_positions, normalized_final["faces"])
    final_topology = validate_geometry(final, require_one_component=bool(policy["require_one_component"]))
    if final_topology["connected_components"] != source_topology["connected_components"] or final_topology["boundary_loops"] != source_topology["boundary_loops"]:
        raise GeometryReductionError("geometry_predecimation_topology_changed", "component or boundary-loop identity changed")
    metrics = fidelity_metrics(source, final)
    violations = _violations(metrics, policy)
    if violations:
        best = source
        best_metrics = fidelity_metrics(source, source)
        for snapshot in reversed(snapshots[:-1]):
            snapshot_positions = [
                struct.unpack("<3f", struct.pack("<3f", *(point[axis] * scale + center[axis] for axis in range(3))))
                for point in snapshot["positions"]
            ]
            candidate = canonical_geometry(snapshot_positions, snapshot["faces"])
            candidate_metrics = fidelity_metrics(source, candidate)
            if not _violations(candidate_metrics, policy):
                best, best_metrics = candidate, candidate_metrics
                break
        raise GeometryReductionError(
            "geometry_predecimation_target_unreachable",
            "the requested envelope exceeds the declared geometry fidelity limits",
            target_faces=target_faces,
            target_positions=target_positions,
            best_valid_faces=len(best["faces"]),
            best_valid_positions=len(best["positions"]),
            best_valid_metrics=best_metrics,
            attempted_faces=final_topology["triangles"],
            attempted_positions=final_topology["positions"],
            violations=violations,
            metrics=metrics,
        )
    report = {
        "schema_version": 1,
        "success": True,
        "algorithm": ALGORITHM,
        "algorithm_version": ALGORITHM_VERSION,
        "normalization": "bounds_center_and_diagonal",
        "policy": policy,
        "source": source_topology,
        "final": final_topology,
        "accepted_collapses": accepted,
        "rejected_collapse_reasons": dict(sorted(rejected.items())),
        "rejected_collapse_evaluations": sum(rejected.values()),
        "face_reduction_percent": round((source_topology["triangles"] - final_topology["triangles"]) * 100 / source_topology["triangles"], 3),
        "position_reduction_percent": round((source_topology["positions"] - final_topology["positions"]) * 100 / source_topology["positions"], 3),
        "metrics": metrics,
        "collapse_plan_sha256": _semantic_hash(collapse_plan),
        "collapse_plan": collapse_plan,
    }
    report["semantic_sha256"] = _semantic_hash(report)
    return final, report


def _component_meshes(mesh: dict[str, Any]) -> list[dict[str, Any]]:
    """Split canonical geometry into stable, source-order-independent components."""
    source = canonical_geometry(mesh["positions"], mesh["faces"])
    positions = [tuple(point) for point in source["positions"]]
    faces = [tuple(face) for face in source["faces"]]
    edges = _edge_data(faces)
    adjacency = [set() for _ in faces]
    for owners in edges.values():
        if len(owners) == 2:
            left, right = owners[0][0], owners[1][0]
            adjacency[left].add(right); adjacency[right].add(left)
    unseen = set(range(len(faces))); result = []
    while unseen:
        seed = min(unseen); unseen.remove(seed); stack = [seed]; face_ids = []
        while stack:
            current = stack.pop(); face_ids.append(current)
            for neighbor in sorted(adjacency[current], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor); stack.append(neighbor)
        selected = [faces[index] for index in sorted(face_ids)]
        used = sorted({index for face in selected for index in face}, key=lambda index: positions[index])
        remap = {old: new for new, old in enumerate(used)}
        component = canonical_geometry(
            [positions[index] for index in used],
            [tuple(remap[index] for index in face) for face in selected],
        )
        component["component_id"] = _semantic_hash(component)[:16]
        component["surface_area"] = _surface(component["positions"], component["faces"])
        result.append(component)
    return sorted(result, key=lambda item: item["component_id"])


def _allocate_component_budget(
    components: list[dict[str, Any]], total: int, source_key: str, *, minimum: int,
) -> list[int]:
    if total < minimum * len(components):
        raise GeometryReductionError(
            "geometry_predecimation_target_unreachable",
            "target cannot preserve the minimum allowance for every component",
            target=total, components=len(components), minimum_per_component=minimum,
        )
    capacities = [len(component[source_key]) for component in components]
    allocations = [min(minimum, capacity) for capacity in capacities]
    remaining = total - sum(allocations)
    weights = [float(component["surface_area"]) for component in components]
    while remaining > 0 and any(allocations[index] < capacities[index] for index in range(len(components))):
        eligible = [index for index in range(len(components)) if allocations[index] < capacities[index]]
        total_weight = sum(weights[index] for index in eligible) or float(len(eligible))
        ranked = sorted(
            eligible,
            key=lambda index: (
                -((weights[index] / total_weight * remaining) - math.floor(weights[index] / total_weight * remaining)),
                components[index]["component_id"],
            ),
        )
        progress = False
        for index in ranked:
            if remaining == 0:
                break
            share = max(1, math.floor(weights[index] / total_weight * remaining))
            granted = min(share, capacities[index] - allocations[index], remaining)
            if granted:
                allocations[index] += granted; remaining -= granted; progress = True
        if not progress:
            break
    return allocations


def reduce_geometry_components(
    mesh: dict[str, Any], policy: dict[str, Any], *, max_components: int = 4,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reduce bounded disconnected components independently and preserve all."""
    source = canonical_geometry(mesh["positions"], mesh["faces"])
    source_topology = validate_geometry(source)
    components = _component_meshes(source)
    if not 1 <= len(components) <= max_components:
        raise GeometryReductionError(
            "geometry_predecimation_component_count",
            "component count exceeds the bounded multi-component policy",
            observed=len(components), maximum=max_components,
        )
    if len(components) == 1:
        # The legacy path is intentionally exact and remains byte-identical.
        return reduce_geometry(source, policy)
    face_budgets = _allocate_component_budget(
        components, int(policy["target_faces"]), "faces", minimum=16,
    )
    position_budgets = _allocate_component_budget(
        components, int(policy["target_positions"]), "positions", minimum=10,
    )
    outputs = []
    component_reports = []
    for component, face_target, position_target in zip(components, face_budgets, position_budgets, strict=True):
        child_policy = dict(policy)
        child_policy.update({
            "target_faces": face_target,
            "target_positions": position_target,
            "require_one_component": True,
        })
        reduced, report = reduce_geometry(component, child_policy)
        outputs.append(reduced)
        component_reports.append({
            "component_id": component["component_id"],
            "source_faces": len(component["faces"]),
            "source_positions": len(component["positions"]),
            "source_area": component["surface_area"],
            "target_faces": face_target,
            "target_positions": position_target,
            "final_faces": len(reduced["faces"]),
            "final_positions": len(reduced["positions"]),
            "final_area": _surface(reduced["positions"], reduced["faces"]),
            "boundary_loops": report["final"]["boundary_loops"],
            "accepted_collapses": report["accepted_collapses"],
            "rejected_collapse_evaluations": report["rejected_collapse_evaluations"],
            "rejected_collapse_reasons": report["rejected_collapse_reasons"],
            "metrics": report["metrics"],
            "semantic_sha256": report["semantic_sha256"],
        })
    combined_positions: list[tuple[float, float, float]] = []
    combined_faces: list[tuple[int, int, int]] = []
    for reduced in outputs:
        offset = len(combined_positions)
        combined_positions.extend(tuple(point) for point in reduced["positions"])
        combined_faces.extend(tuple(index + offset for index in face) for face in reduced["faces"])
    final = canonical_geometry(combined_positions, combined_faces)
    final_topology = validate_geometry(final)
    if final_topology["connected_components"] != source_topology["connected_components"]:
        raise GeometryReductionError(
            "geometry_predecimation_topology_changed", "component split/merge occurred during independent reduction",
        )
    if final_topology["boundary_loops"] != source_topology["boundary_loops"]:
        raise GeometryReductionError(
            "geometry_predecimation_topology_changed", "boundary-loop count changed during independent reduction",
        )
    metrics = fidelity_metrics(source, final)
    violations = _violations(metrics, policy)
    if violations:
        raise GeometryReductionError(
            "geometry_predecimation_target_unreachable",
            "multi-component aggregate exceeds declared fidelity limits",
            violations=violations, metrics=metrics,
        )
    report = {
        "schema_version": 2,
        "success": True,
        "algorithm": ALGORITHM,
        "algorithm_version": ALGORITHM_VERSION,
        "component_policy": "stable_id_area_weighted_minimum_allowance",
        "component_count": len(components),
        "component_survival": True,
        "component_merge_or_split": False,
        "source": source_topology,
        "final": final_topology,
        "component_reports": component_reports,
        "accepted_collapses": sum(item["accepted_collapses"] for item in component_reports),
        "rejected_collapse_evaluations": sum(item["rejected_collapse_evaluations"] for item in component_reports),
        "face_reduction_percent": round((len(source["faces"]) - len(final["faces"])) * 100 / len(source["faces"]), 3),
        "position_reduction_percent": round((len(source["positions"]) - len(final["positions"])) * 100 / len(source["positions"]), 3),
        "metrics": metrics,
        "policy": policy,
    }
    report["semantic_sha256"] = _semantic_hash(report)
    return final, report
