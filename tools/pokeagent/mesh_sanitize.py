"""Exact, auditable topology sanitation for bounded generated geometry.

Stage 4Q removes only triangles whose float32-decoded geometric area is
mathematically zero.  It never welds, fills, flips, retriangulates, joins, or
selects components.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


MAX_COMPONENTS = 4
SANITIZER = "generated_static_exact_sanitize_v1"
SANITIZER_VERSION = 1
STAGE4O_REJECTION_CROSS_SQUARED = 1e-18


class MeshSanitizeError(ValueError):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _hash(value: object) -> str:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def _cross_squared(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]


def _rotated(face: tuple[int, int, int]) -> tuple[int, int, int]:
    return min(face, (face[1], face[2], face[0]), (face[2], face[0], face[1]))


def _topology(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]],
) -> dict[str, Any]:
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face_id, face in enumerate(faces):
        for start, end in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = min(start, end), max(start, end)
            edges.setdefault(edge, []).append((face_id, 1 if (start, end) == edge else -1))
    if any(len(owners) > 2 for owners in edges.values()):
        raise MeshSanitizeError("topology_sanitize_non_manifold", "an edge has more than two incident faces")
    if any(len(owners) == 2 and owners[0][1] == owners[1][1] for owners in edges.values()):
        raise MeshSanitizeError("topology_sanitize_inconsistent_winding", "shared-edge winding is inconsistent")
    face_adjacency = [set() for _ in faces]
    for owners in edges.values():
        if len(owners) == 2:
            left, right = owners[0][0], owners[1][0]
            face_adjacency[left].add(right); face_adjacency[right].add(left)
    remaining = set(range(len(faces))); components: list[list[int]] = []
    while remaining:
        seed = min(remaining); remaining.remove(seed); stack = [seed]; found = []
        while stack:
            current = stack.pop(); found.append(current)
            for neighbor in sorted(face_adjacency[current], reverse=True):
                if neighbor in remaining:
                    remaining.remove(neighbor); stack.append(neighbor)
        components.append(sorted(found))
    boundary_adjacency: dict[int, set[int]] = {}
    boundary_edges = []
    for edge, owners in edges.items():
        if len(owners) == 1:
            boundary_edges.append(edge)
            a, b = edge
            boundary_adjacency.setdefault(a, set()).add(b)
            boundary_adjacency.setdefault(b, set()).add(a)
    if any(len(neighbors) != 2 for neighbors in boundary_adjacency.values()):
        raise MeshSanitizeError(
            "topology_sanitize_branching_boundary",
            "open boundaries must be non-branching closed loops",
        )
    unseen = set(boundary_adjacency); loops: list[list[int]] = []
    while unseen:
        seed = min(unseen); unseen.remove(seed); stack = [seed]; vertices = []
        while stack:
            current = stack.pop(); vertices.append(current)
            for neighbor in sorted(boundary_adjacency[current], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor); stack.append(neighbor)
        loops.append(sorted(vertices))
    component_records = []
    for face_ids in components:
        used = sorted({index for face_id in face_ids for index in faces[face_id]})
        subset_faces = [faces[index] for index in face_ids]
        bounds = {
            "min": [min(positions[index][axis] for index in used) for axis in range(3)],
            "max": [max(positions[index][axis] for index in used) for axis in range(3)],
        }
        signature = {
            "positions": sorted(positions[index] for index in used),
            "faces": sorted(_rotated(face) for face in subset_faces),
        }
        component_records.append({
            "component_id": _hash(signature)[:16],
            "faces": len(face_ids),
            "positions": len(used),
            "bounds": bounds,
            "boundary_loops": sum(set(loop) <= set(used) for loop in loops),
        })
    component_records.sort(key=lambda item: item["component_id"])
    return {
        "connected_components": len(components),
        "components": component_records,
        "boundary_edges": len(boundary_edges),
        "boundary_loops": len(loops),
        "boundary_loop_vertex_counts": sorted(len(loop) for loop in loops),
    }


def sanitize_mesh(
    positions: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    *,
    remove_exact_zero_area_faces: bool,
    max_components: int = MAX_COMPONENTS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove exact-zero faces and preserve every remaining surface exactly."""
    if remove_exact_zero_area_faces is not True:
        raise MeshSanitizeError("topology_sanitize_policy_required", "exact-zero removal must be explicit")
    if not 1 <= max_components <= MAX_COMPONENTS:
        raise MeshSanitizeError("topology_sanitize_component_limit", "component limit is outside the proven bound")
    if not positions or not faces:
        raise MeshSanitizeError("topology_sanitize_empty", "source requires positions and faces")
    packed_positions = [tuple(float(value) for value in point) for point in positions]
    kept: list[tuple[int, int, int]] = []
    removed = []
    near_zero_nonzero = 0
    for source_face_id, raw_face in enumerate(faces):
        face = tuple(raw_face)
        if len(face) != 3 or any(isinstance(index, bool) or not isinstance(index, int) for index in face):
            raise MeshSanitizeError("topology_sanitize_invalid_indices", "face indices must be integer triples")
        if any(index < 0 or index >= len(packed_positions) for index in face):
            raise MeshSanitizeError("topology_sanitize_invalid_indices", "face index exceeds POSITION")
        points = [packed_positions[index] for index in face]
        squared = _cross_squared(*points)
        if squared == 0.0:
            repeated_index = len(set(face)) != 3
            repeated_position = len(set(points)) != 3
            category = (
                "repeated_index" if repeated_index else
                "repeated_position" if repeated_position else
                "collinear_zero_area"
            )
            removed.append({
                "primitive": 0,
                "canonical_source_face_id": _hash({"indices": _rotated(face), "positions": points})[:16],
                "source_face_index": source_face_id,
                "indices": list(face),
                "positions": [list(point) for point in points],
                "cross_squared": squared,
                "area": 0.0,
                "reason": category,
            })
            continue
        if squared <= STAGE4O_REJECTION_CROSS_SQUARED:
            near_zero_nonzero += 1
        kept.append(face)
    if not removed:
        raise MeshSanitizeError("topology_sanitize_no_exact_zero_area", "source contains no exact-zero face")
    if not kept:
        raise MeshSanitizeError("topology_sanitize_all_faces_removed", "all source faces have exact zero area")
    used = sorted({index for face in kept for index in face}, key=lambda index: (packed_positions[index], index))
    remap = {old: new for new, old in enumerate(used)}
    compact_positions = [packed_positions[index] for index in used]
    compact_faces = sorted(_rotated(tuple(remap[index] for index in face)) for face in kept)
    if len(set(compact_faces)) != len(compact_faces):
        raise MeshSanitizeError("topology_sanitize_duplicate_face", "surviving source contains duplicate faces")
    topology = _topology(compact_positions, compact_faces)
    if topology["connected_components"] > max_components:
        raise MeshSanitizeError(
            "topology_sanitize_component_limit",
            "surviving component count exceeds the declared maximum",
            observed=topology["connected_components"], maximum=max_components,
        )
    mesh = {"schema_version": 1, "positions": compact_positions, "faces": compact_faces}
    report = {
        "schema_version": 1,
        "success": True,
        "algorithm": SANITIZER,
        "algorithm_version": SANITIZER_VERSION,
        "zero_area_definition": "float32_decoded_cross_squared_exactly_zero",
        "source_positions": len(positions),
        "source_triangles": len(faces),
        "final_positions": len(compact_positions),
        "final_triangles": len(compact_faces),
        "removed_face_count": len(removed),
        "removed_faces": sorted(removed, key=lambda item: item["canonical_source_face_id"]),
        "removed_categories": {
            category: sum(item["reason"] == category for item in removed)
            for category in ("repeated_index", "repeated_position", "collinear_zero_area")
        },
        "near_zero_nonzero_faces_preserved": near_zero_nonzero,
        "old_to_new_position": {str(old): new for new, old in enumerate(used)},
        "unreferenced_positions_removed": len(positions) - len(used),
        "positions_moved": False,
        "winding_changed": False,
        "faces_retriangulated": False,
        "vertices_welded": False,
        "components_merged_or_deleted": False,
        "topology": topology,
    }
    report["semantic_sha256"] = _hash(report)
    return mesh, report


def analyze_topology(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]],
) -> dict[str, Any]:
    """Read-only exact sanitation projection for generated intake evidence."""
    squared = [_cross_squared(*(positions[index] for index in face)) for face in faces]
    exact = sum(value == 0.0 for value in squared)
    near_nonzero = sum(0.0 < value <= STAGE4O_REJECTION_CROSS_SQUARED for value in squared)
    try:
        mesh, report = sanitize_mesh(
            positions, faces, remove_exact_zero_area_faces=True, max_components=MAX_COMPONENTS,
        )
    except MeshSanitizeError as error:
        topology = None
        try:
            topology = _topology(positions, faces)
        except MeshSanitizeError:
            pass
        return {
            "applicable": False,
            "exact_zero_area_faces": exact,
            "near_zero_nonzero_faces": near_nonzero,
            "minimum_cross_squared": min(squared, default=None),
            "full_topology": topology,
            "error": error.as_dict(),
        }
    return {"applicable": True, "hypothetical_mesh": mesh, "report": report}
