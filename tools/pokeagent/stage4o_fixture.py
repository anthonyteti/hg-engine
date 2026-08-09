"""Reproducible project-authored dense geometry-only Stage 4O fixture."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from .glb import pack_glb


def _square_radius(angle: float, radius: float) -> float:
    denominator = (abs(math.cos(angle)) ** 6 + abs(math.sin(angle)) ** 6) ** (1 / 6)
    return radius / denominator


def build_dense_geometry_shrine(
    *,
    roof_height: float = 6.4,
    reverse_faces: bool = False,
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    uniform_scale: float = 1.0,
) -> bytes:
    """Build one connected open-bottom reconstruction-style hard surface."""
    segments = 32
    rings = (
        (0.00, 2.40), (0.25, 2.48), (0.55, 2.38), (0.90, 2.43),
        (1.25, 2.39), (1.60, 2.46), (1.95, 2.38), (2.30, 2.44),
        (2.65, 2.39), (3.00, 2.45), (3.35, 2.40), (3.70, 2.43),
        (3.95, 2.65), (4.20, 2.25), (4.55, 2.20), (4.85, 2.02),
        (5.10, 1.78),
    )
    positions: list[tuple[float, float, float]] = []

    def transform(point: tuple[float, float, float]) -> tuple[float, float, float]:
        return tuple(point[axis] * uniform_scale + translation[axis] for axis in range(3))

    for ring_index, (y, radius) in enumerate(rings):
        for segment in range(segments):
            angle = 2 * math.pi * segment / segments
            shaped = _square_radius(angle, radius)
            noise = 0.028 * math.sin(5 * angle + ring_index * 0.71) + 0.012 * math.sin(11 * angle - ring_index * 0.37)
            front_distance = min(abs(segment - 8), segments - abs(segment - 8))
            doorway = 0.20 * max(0.0, 1.0 - front_distance / 3.0) if 2 <= ring_index <= 8 else 0.0
            adjusted = shaped + noise - doorway
            positions.append(transform((adjusted * math.cos(angle), y, adjusted * math.sin(angle))))
    apex = len(positions)
    positions.append(transform((0.0, roof_height, 0.0)))
    faces: list[tuple[int, int, int]] = []
    for ring in range(len(rings) - 1):
        for segment in range(segments):
            next_segment = (segment + 1) % segments
            lower_a = ring * segments + segment
            lower_b = ring * segments + next_segment
            upper_a = (ring + 1) * segments + segment
            upper_b = (ring + 1) * segments + next_segment
            faces.extend(((lower_a, upper_a, upper_b), (lower_a, upper_b, lower_b)))
    last = (len(rings) - 1) * segments
    for segment in range(segments):
        faces.append((last + segment, apex, last + (segment + 1) % segments))
    if reverse_faces:
        faces.reverse()

    binary = bytearray()
    for point in positions: binary.extend(struct.pack("<3f", *point))
    position_length = len(binary)
    while len(binary) % 4: binary.append(0)
    index_offset = len(binary)
    for face in faces:
        for index in face: binary.extend(struct.pack("<H", index))
    index_length = len(binary) - index_offset
    packed_positions = [struct.unpack("<3f", struct.pack("<3f", *point)) for point in positions]
    document = {
        "asset": {"generator": "pokeagent-stage4o-fixture-v1", "version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "stage4o_dense_geometry_shrine"}],
        "meshes": [{"name": "stage4o_dense_geometry_shrine", "primitives": [{
            "attributes": {"POSITION": 0}, "indices": 1, "mode": 4,
        }]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": position_length},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": index_length},
        ],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3",
                "min": [min(point[axis] for point in packed_positions) for axis in range(3)],
                "max": [max(point[axis] for point in packed_positions) for axis in range(3)],
            },
            {"bufferView": 1, "componentType": 5123, "count": len(faces) * 3, "type": "SCALAR"},
        ],
    }
    return pack_glb(document, bytes(binary))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_dense_geometry_shrine())


if __name__ == "__main__":
    main()
