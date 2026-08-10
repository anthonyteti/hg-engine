"""Reproducible Stage 4R target-representation fixtures."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from .glb_geometry_reduce import pack_geometry_glb, parse_geometry_glb
from .mesh_sanitize import _cross_squared
from .stage4q_fixture import _pack, build_stage4q_multicomponent


def _point(
    center: tuple[float, float, float], corner: tuple[float, float, float], factor: float,
) -> tuple[float, float, float]:
    return tuple(center[axis] + (corner[axis] - center[axis]) * factor for axis in range(3))  # type: ignore[return-value]


def build_stage4r_target_null(
    *, reverse_faces: bool = False, micro_factor: float = 0.00002,
) -> tuple[bytes, bytes, dict[str, object]]:
    """Add exact-zero and nonzero target-null evidence to the Stage 4Q surface."""
    base, _reference = build_stage4q_multicomponent(color0=False, include_degenerate=False)
    geometry = parse_geometry_glb(base)["geometry"]
    positions = [tuple(point) for point in geometry["positions"]]
    faces = [tuple(face) for face in geometry["faces"]]

    # Select the largest body face deterministically.  Replacing it with a
    # center triangle and a six-triangle annulus preserves its outer edges.
    body = [
        (math.sqrt(_cross_squared(*(positions[index] for index in face))), face_index, face)
        for face_index, face in enumerate(faces)
        if max(positions[index][0] for index in face) < 3.0
    ]
    _cross_length, selected_index, (a, b, c) = max(body, key=lambda item: (item[0], tuple(item[2])))
    pa, pb, pc = positions[a], positions[b], positions[c]
    center = tuple((pa[axis] + pb[axis] + pc[axis]) / 3 for axis in range(3))
    p, q, r = (_point(center, corner, micro_factor) for corner in (pa, pb, pc))
    p_index = len(positions); positions.extend((p, q, r))
    p_id, q_id, r_id = p_index, p_index + 1, p_index + 2
    annulus = [
        (a, b, q_id), (a, q_id, p_id),
        (b, c, r_id), (b, r_id, q_id),
        (c, a, p_id), (c, p_id, r_id),
    ]
    tiny = (p_id, q_id, r_id)
    faces[selected_index:selected_index + 1] = annulus + [tiny]
    reference_faces = list(faces)
    reference_faces.remove(tiny)

    # Stage 4Q owns this separate exact collinear face.  Its removal is the
    # first step in the canonical Q -> R -> O -> P -> F proof.
    exact = len(positions)
    positions.extend(((8.0, 0.0, 0.0), (8.5, 0.0, 0.0), (9.0, 0.0, 0.0)))
    faces.append((exact, exact + 1, exact + 2))
    if reverse_faces:
        faces.reverse()
    source = _pack(positions, faces, color0=True)
    reference = pack_geometry_glb({
        "schema_version": 1,
        "positions": positions[:exact],
        "faces": reference_faces,
    })
    metadata = {
        "selected_source_face": [a, b, c],
        "tiny_face": list(tiny),
        "micro_factor": micro_factor,
    }
    return source, reference, metadata


def build_rounding_probe(step_numerator: float, *, units_to_tiles: float = 1.0) -> dict[str, object]:
    """Return one face whose edges straddle a VTX_16 half-step boundary."""
    step = step_numerator / (units_to_tiles * 1024)
    positions = [
        (-0.01, -0.01, -0.01), (0.01, 0.01, 0.01),
        (0.0, 0.0, 0.0), (step, 0.0, 0.0), (0.0, step, 0.0),
    ]
    return {"positions": positions, "faces": [(2, 3, 4)]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    source, reference, _metadata = build_stage4r_target_null()
    args.source.parent.mkdir(parents=True, exist_ok=True)
    args.source.write_bytes(source)
    args.reference.write_bytes(reference)


if __name__ == "__main__":
    main()
