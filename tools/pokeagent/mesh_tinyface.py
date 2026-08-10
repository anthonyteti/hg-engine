"""Representation-aware classification of nonzero Stage 4O-blocking faces.

Stage 4Q remains the sole owner of mathematically exact zero-area sanitation.
This module may remove a nonzero face only when the unchanged Stage 4O normal
gate rejects it, the exact project VTX_16 coordinate path makes it degenerate,
and removing it preserves every source component and valid boundary topology.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .geometry import (
    GeometryError,
    MODEL_BASE_Y,
    MODEL_TILE_SCALE,
    quantize_vtx16_coordinate,
)
from .mesh_decimate import EPSILON
from .mesh_predecimate import _DIRECTIONS, _mask, _projection
from .mesh_sanitize import _cross_squared, _hash, _rotated, _topology


TINYFACE_POLICY = "target_quantized_degenerate_v1"
TINYFACE_VERSION = 1
_ROTATIONS = {0, 90, 180, 270}


class TinyFaceError(ValueError):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _semantic_hash(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _axis(value: object, field: str) -> tuple[float, float, float]:
    vectors = {
        "+x": (1.0, 0.0, 0.0), "-x": (-1.0, 0.0, 0.0),
        "+y": (0.0, 1.0, 0.0), "-y": (0.0, -1.0, 0.0),
        "+z": (0.0, 0.0, 1.0), "-z": (0.0, 0.0, -1.0),
    }
    if value not in vectors:
        raise TinyFaceError("invalid_tinyface_axis", f"{field} must be a signed canonical axis")
    return vectors[value]  # type: ignore[index]


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def validate_tinyface_policy(policy: object) -> dict[str, Any]:
    expected = {
        "policy", "candidate_scope", "coordinate_system", "normalization",
        "placement", "preserve_components", "require_valid_boundaries",
    }
    if not isinstance(policy, dict) or set(policy) != expected or policy.get("policy") != TINYFACE_POLICY:
        raise TinyFaceError("invalid_tinyface_policy", "Stage 4R target-representation policy is incomplete")
    if policy.get("candidate_scope") != "stage4o_normal_rejected_only":
        raise TinyFaceError("invalid_tinyface_policy", "Stage 4R removes only faces already rejected by Stage 4O")
    coordinates = policy.get("coordinate_system")
    if not isinstance(coordinates, dict) or set(coordinates) != {"up_axis", "forward_axis", "handedness"}:
        raise TinyFaceError("invalid_tinyface_policy", "coordinate-system policy is incomplete")
    up = _axis(coordinates.get("up_axis"), "up_axis")
    forward = _axis(coordinates.get("forward_axis"), "forward_axis")
    if coordinates.get("handedness") != "right" or abs(_dot(up, forward)) > 1e-12:
        raise TinyFaceError("invalid_tinyface_policy", "Stage 4R requires perpendicular right-handed axes")
    normalization = policy.get("normalization")
    if not isinstance(normalization, dict) or set(normalization) != {"units_to_tiles", "anchor"}:
        raise TinyFaceError("invalid_tinyface_policy", "normalization policy is incomplete")
    scale = normalization.get("units_to_tiles")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise TinyFaceError("invalid_tinyface_policy", "units_to_tiles must be finite and positive")
    if normalization.get("anchor") != "footprint_center_base":
        raise TinyFaceError("invalid_tinyface_policy", "Stage 4R requires the production footprint/base anchor")
    placement = policy.get("placement")
    if not isinstance(placement, dict) or set(placement) != {"x", "z", "rotation"}:
        raise TinyFaceError("invalid_tinyface_policy", "placement policy is incomplete")
    if any(isinstance(placement.get(key), bool) or not isinstance(placement.get(key), int) for key in ("x", "z")):
        raise TinyFaceError("invalid_tinyface_policy", "placement anchors must be integer tiles")
    if placement.get("rotation") not in _ROTATIONS:
        raise TinyFaceError("invalid_tinyface_policy", "placement rotation must be cardinal")
    if policy.get("preserve_components") is not True or policy.get("require_valid_boundaries") is not True:
        raise TinyFaceError("invalid_tinyface_policy", "topology preservation flags must be true")
    return json.loads(json.dumps(policy, sort_keys=True))


def _target_coordinates(
    positions: list[tuple[float, float, float]], policy: dict[str, Any],
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]], list[tuple[int, int, int]], dict[str, Any]]:
    policy = validate_tinyface_policy(policy)
    if not positions or any(
        len(point) != 3 or any(not math.isfinite(float(value)) for value in point)
        for point in positions
    ):
        raise TinyFaceError("tinyface_nonfinite_position", "Stage 4R requires finite POSITION triples")
    up = _axis(policy["coordinate_system"]["up_axis"], "up_axis")
    forward = _axis(policy["coordinate_system"]["forward_axis"], "forward_axis")
    right = _cross(up, forward)
    scale = float(policy["normalization"]["units_to_tiles"])
    oriented = [
        (_dot(point, right) * scale, _dot(point, up) * scale, _dot(point, forward) * scale)
        for point in positions
    ]
    minimum = [min(point[axis] for point in oriented) for axis in range(3)]
    maximum = [max(point[axis] for point in oriented) for axis in range(3)]
    center_x = (minimum[0] + maximum[0]) / 2
    center_z = (minimum[2] + maximum[2]) / 2
    base_y = minimum[1]
    normalized = [(x - center_x, y - base_y, z - center_z) for x, y, z in oriented]
    rotation = policy["placement"]["rotation"]
    anchor_x = policy["placement"]["x"]
    anchor_z = policy["placement"]["z"]
    model = []
    quantized = []
    for x, y, z in normalized:
        if rotation == 0: rx, rz = x, z
        elif rotation == 90: rx, rz = z, -x
        elif rotation == 180: rx, rz = -x, -z
        else: rx, rz = -z, x
        target = (
            (anchor_x + rx - 16) * MODEL_TILE_SCALE,
            MODEL_BASE_Y + y * MODEL_TILE_SCALE,
            (anchor_z + rz - 16) * MODEL_TILE_SCALE,
        )
        try:
            encoded = tuple(quantize_vtx16_coordinate(value) for value in target)
        except GeometryError as error:
            raise TinyFaceError("tinyface_target_quantization_overflow", str(error), point=list(target)) from error
        model.append(target)
        quantized.append(encoded)  # type: ignore[arg-type]
    transform = {
        "source_units_to_tiles": scale,
        "source_bounds_oriented_tiles": {"min": minimum, "max": maximum},
        "anchor_center_xz_base_y": [center_x, base_y, center_z],
        "placement": dict(policy["placement"]),
        "model_tile_scale": MODEL_TILE_SCALE,
        "model_base_y": MODEL_BASE_Y,
        "command": "VTX_16",
        "opcode": "0x23",
        "fixed_fraction_bits": 12,
        "model_coordinate_increment": 1 / 4096,
        "normalized_tile_increment": 1 / (4096 * MODEL_TILE_SCALE),
        "rounding": "python_round_nearest_ties_to_even",
        "signed_range": [-32768, 32767],
    }
    return normalized, model, quantized, transform


def _integer_cross_squared(points: list[tuple[int, int, int]]) -> int:
    a = tuple(points[1][axis] - points[0][axis] for axis in range(3))
    b = tuple(points[2][axis] - points[0][axis] for axis in range(3))
    cross = _cross(a, b)  # type: ignore[arg-type]
    return int(sum(value * value for value in cross))


def _face_components(faces: list[tuple[int, int, int]]) -> list[set[int]]:
    owners: dict[tuple[int, int], list[int]] = {}
    for face_id, face in enumerate(faces):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            owners.setdefault((min(a, b), max(a, b)), []).append(face_id)
    adjacency = [set() for _ in faces]
    for edge_owners in owners.values():
        if len(edge_owners) == 2:
            a, b = edge_owners
            adjacency[a].add(b); adjacency[b].add(a)
    unseen = set(range(len(faces))); result = []
    while unseen:
        seed = min(unseen); unseen.remove(seed); stack = [seed]; found = {seed}
        while stack:
            current = stack.pop()
            for neighbor in sorted(adjacency[current]):
                if neighbor in unseen:
                    unseen.remove(neighbor); found.add(neighbor); stack.append(neighbor)
        result.append(found)
    return result


def _surface_area(positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> float:
    return sum(math.sqrt(_cross_squared(*(positions[index] for index in face))) / 2 for face in faces)


def _silhouette_iou(
    positions: list[tuple[float, float, float]], source: list[tuple[int, int, int]], final: list[tuple[int, int, int]],
) -> dict[str, float]:
    result = {}
    for direction in _DIRECTIONS:
        projected = [_projection(point, direction) for point in positions]
        bounds = (
            min(point[0] for point in projected), max(point[0] for point in projected),
            min(point[1] for point in projected), max(point[1] for point in projected),
        )
        before = _mask(positions, source, direction, bounds)
        after = _mask(positions, final, direction, bounds)
        result[direction] = round(len(before & after) / max(1, len(before | after)), 6)
    return result


def classify_target_faces(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], policy: dict[str, Any],
) -> dict[str, Any]:
    """Classify every nonzero face against the exact production VTX_16 integers."""
    normalized, model, quantized, transform = _target_coordinates(positions, policy)
    minimum = [min(point[axis] for point in positions) for axis in range(3)]
    maximum = [max(point[axis] for point in positions) for axis in range(3)]
    diagonal_squared = sum((maximum[axis] - minimum[axis]) ** 2 for axis in range(3))
    records = []
    for source_face_index, face in enumerate(faces):
        points = [positions[index] for index in face]
        cross_squared = _cross_squared(*points)
        if cross_squared == 0.0:
            classification = "EXACT_ZERO_STAGE4Q_REQUIRED"
        else:
            target_cross_squared = _integer_cross_squared([quantized[index] for index in face])
            stage4o_blocking = math.sqrt(cross_squared) <= EPSILON
            if target_cross_squared == 0 and stage4o_blocking:
                classification = "TARGET_QUANTIZED_DEGENERATE"
            elif target_cross_squared == 0:
                classification = "TARGET_NULL_NONBLOCKING_PRESERVED"
            else:
                classification = "TARGET_REPRESENTABLE"
        target_cross_squared = _integer_cross_squared([quantized[index] for index in face])
        area = math.sqrt(cross_squared) / 2
        records.append({
            "canonical_source_face_id": _hash({"indices": _rotated(face), "positions": points})[:16],
            "source_face_index": source_face_index,
            "indices": list(face),
            "source_positions": [list(point) for point in points],
            "source_edge_lengths": [
                math.dist(points[a], points[b]) for a, b in ((0, 1), (1, 2), (2, 0))
            ],
            "source_cross_squared": cross_squared,
            "source_cross_length": math.sqrt(cross_squared),
            "source_area": area,
            "source_relative_area_diagonal_squared": area / diagonal_squared if diagonal_squared else None,
            "normalized_positions": [list(normalized[index]) for index in face],
            "target_model_positions": [list(model[index]) for index in face],
            "target_quantized_positions": [list(quantized[index]) for index in face],
            "target_distinct_coordinate_count": len({quantized[index] for index in face}),
            "target_cross_squared": target_cross_squared,
            "stage4o_cross_length_limit": EPSILON,
            "stage4o_blocking": cross_squared > 0.0 and math.sqrt(cross_squared) <= EPSILON,
            "classification": classification,
        })
    records.sort(key=lambda item: item["canonical_source_face_id"])
    return {
        "target_transform": transform,
        "faces": records,
        "classification_counts": {
            name: sum(item["classification"] == name for item in records)
            for name in (
                "EXACT_ZERO_STAGE4Q_REQUIRED", "TARGET_QUANTIZED_DEGENERATE",
                "TARGET_NULL_NONBLOCKING_PRESERVED", "TARGET_REPRESENTABLE",
            )
        },
    }


def remove_target_null_faces(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove only target-null Stage 4O blockers when topology remains valid."""
    policy = validate_tinyface_policy(policy)
    packed_positions = [tuple(float(value) for value in point) for point in positions]
    packed_faces = [tuple(face) for face in faces]
    try:
        source_topology = _topology(packed_positions, packed_faces)
    except Exception as error:
        if hasattr(error, "code"):
            raise TinyFaceError(error.code, str(error), **getattr(error, "details", {})) from error
        raise
    classified = classify_target_faces(packed_positions, packed_faces, policy)
    exact = [item for item in classified["faces"] if item["classification"] == "EXACT_ZERO_STAGE4Q_REQUIRED"]
    if exact:
        raise TinyFaceError(
            "tinyface_exact_zero_requires_stage4q",
            "exact-zero faces must be removed by unchanged Stage 4Q before Stage 4R",
            face_ids=[item["canonical_source_face_id"] for item in exact],
        )
    candidates = [item for item in classified["faces"] if item["classification"] == "TARGET_QUANTIZED_DEGENERATE"]
    if not candidates:
        raise TinyFaceError("tinyface_no_target_null_blocker", "source contains no removable target-null Stage 4O blocker")
    remove_indices = {int(item["source_face_index"]) for item in candidates}
    source_components = _face_components(packed_faces)
    for component in source_components:
        surviving = component - remove_indices
        if not surviving:
            raise TinyFaceError("target_null_removal_component_vanished", "target-null removal would delete a component")
        selected = [packed_faces[index] for index in sorted(surviving)]
        if len(_face_components(selected)) != 1:
            raise TinyFaceError("target_null_removal_component_split", "target-null removal would split a component")
    kept = [face for index, face in enumerate(packed_faces) if index not in remove_indices]
    used = sorted({index for face in kept for index in face}, key=lambda index: (packed_positions[index], index))
    remap = {old: new for new, old in enumerate(used)}
    compact_positions = [packed_positions[index] for index in used]
    compact_faces = sorted(_rotated(tuple(remap[index] for index in face)) for face in kept)
    if len(set(compact_faces)) != len(compact_faces):
        raise TinyFaceError("target_null_removal_duplicate_face", "removal produced duplicate surviving geometry")
    try:
        final_topology = _topology(compact_positions, compact_faces)
    except Exception as error:
        if hasattr(error, "code"):
            raise TinyFaceError("target_null_removal_topology_damage", str(error), source_code=error.code) from error
        raise
    if final_topology["connected_components"] != source_topology["connected_components"]:
        raise TinyFaceError(
            "target_null_removal_component_changed", "target-null removal changed component count",
            source=source_topology["connected_components"], final=final_topology["connected_components"],
        )
    source_area = _surface_area(packed_positions, packed_faces)
    final_area = _surface_area(compact_positions, compact_faces)
    source_bounds = {
        "min": [min(point[axis] for point in packed_positions) for axis in range(3)],
        "max": [max(point[axis] for point in packed_positions) for axis in range(3)],
    }
    final_bounds = {
        "min": [min(point[axis] for point in compact_positions) for axis in range(3)],
        "max": [max(point[axis] for point in compact_positions) for axis in range(3)],
    }
    silhouettes = _silhouette_iou(packed_positions, packed_faces, kept)
    removed_area = sum(float(item["source_area"]) for item in candidates)
    mesh = {"schema_version": 1, "positions": compact_positions, "faces": compact_faces}
    report = {
        "schema_version": 1,
        "success": True,
        "algorithm": TINYFACE_POLICY,
        "algorithm_version": TINYFACE_VERSION,
        "classification_formula": (
            "source_cross_squared>0 AND source_cross_length<=Stage4O_EPSILON "
            "AND integer_VTX16_cross_squared==0"
        ),
        "policy": policy,
        "target_representation": classified["target_transform"],
        "classification_counts": classified["classification_counts"],
        "removed_face_count": len(candidates),
        "removed_faces": candidates,
        "source_positions": len(packed_positions),
        "source_triangles": len(packed_faces),
        "final_positions": len(compact_positions),
        "final_triangles": len(compact_faces),
        "source_topology": source_topology,
        "final_topology": final_topology,
        "component_survival": True,
        "component_merge_or_split": False,
        "boundary_loops_before": source_topology["boundary_loops"],
        "boundary_loops_after": final_topology["boundary_loops"],
        "unreferenced_positions_removed": len(packed_positions) - len(used),
        "positions_moved": False,
        "winding_changed": False,
        "faces_retriangulated": False,
        "vertices_welded": False,
        "source_surface_area": source_area,
        "final_surface_area": final_area,
        "removed_source_area": removed_area,
        "removed_area_ratio": removed_area / source_area,
        "source_bounds": source_bounds,
        "final_bounds": final_bounds,
        "bounds_changed": source_bounds != final_bounds,
        "silhouette_iou": silhouettes,
        "minimum_silhouette_iou": min(silhouettes.values()),
        "old_to_new_position": (
            {str(old): new for new, old in enumerate(used)}
            if len(packed_positions) != len(used) else {}
        ),
    }
    report["semantic_sha256"] = _semantic_hash(report)
    return mesh, report
