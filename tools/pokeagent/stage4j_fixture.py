"""Reproducible project-authored Stage 4J GLB proof fixture builder."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from .glb import pack_glb


def build_dense_shrine(*, roof_height: float = 7.0, reverse_faces: bool = False) -> bytes:
    """Build a valid, non-coplanar, one-material GLB in the Stage 4F subset."""
    segments = 16
    rings = (
        (0.0, 2.50), (0.45, 2.75), (0.90, 2.50), (3.60, 2.50),
        (4.00, 2.80), (4.40, 2.35), (5.00, 2.35),
    )
    triangles: list[tuple[tuple[float, float, float], ...]] = []
    triangle_uvs: list[tuple[tuple[float, float], ...]] = []

    def point(index: int, y: float, radius: float) -> tuple[float, float, float]:
        angle = 2 * math.pi * index / segments
        return (radius * math.cos(angle), y, radius * math.sin(angle))

    for ring_index, ((lower_y, lower_radius), (upper_y, upper_radius)) in enumerate(zip(rings, rings[1:])):
        for segment in range(segments):
            a, b = segment, segment + 1
            corners = (
                point(a, lower_y, lower_radius), point(a, upper_y, upper_radius),
                point(b, upper_y, upper_radius), point(b, lower_y, lower_radius),
            )
            u0, u1 = segment / segments, (segment + 1) / segments
            v0, v1 = lower_y / roof_height, upper_y / roof_height
            uvs = ((u0, v0), (u0, v1), (u1, v1), (u1, v0))
            triangles.extend(((corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3])))
            triangle_uvs.extend(((uvs[0], uvs[1], uvs[2]), (uvs[0], uvs[2], uvs[3])))
    apex = (0.0, roof_height, 0.0)
    base_y, base_radius = rings[-1]
    for segment in range(segments):
        a, b = segment, segment + 1
        triangle = (point(a, base_y, base_radius), apex, point(b, base_y, base_radius))
        u0, u1 = segment / segments, (segment + 1) / segments
        triangles.append(triangle)
        triangle_uvs.append(((u0, base_y / roof_height), (0.5, 1.0), (u1, base_y / roof_height)))
    if reverse_faces:
        order = list(range(len(triangles))); order.reverse()
        triangles = [triangles[index] for index in order]
        triangle_uvs = [triangle_uvs[index] for index in order]

    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    indices: list[int] = []
    for triangle, texcoords in zip(triangles, triangle_uvs, strict=True):
        ab = tuple(triangle[1][axis] - triangle[0][axis] for axis in range(3))
        ac = tuple(triangle[2][axis] - triangle[0][axis] for axis in range(3))
        raw = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
        length = math.sqrt(sum(value * value for value in raw))
        normal = tuple(value / length for value in raw)
        for position, uv in zip(triangle, texcoords, strict=True):
            indices.append(len(positions)); positions.append(position); normals.append(normal); uvs.append(uv)

    binary = bytearray()
    views = []
    accessors = []

    def append(values: list[tuple[float, ...]] | list[int], fmt: str, accessor_type: str, component: int, *, bounds: bool = False) -> int:
        offset = len(binary)
        if values and isinstance(values[0], tuple):
            for value in values: binary.extend(struct.pack(fmt, *value))
            count = len(values)
        else:
            for value in values: binary.extend(struct.pack(fmt, value))
            count = len(values)
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor = {"bufferView": len(views) - 1, "componentType": component, "count": count, "type": accessor_type}
        if bounds:
            accessor["min"] = [min(value[axis] for value in values) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in values) for axis in range(3)]
        accessors.append(accessor)
        while len(binary) % 4: binary.append(0)
        return len(accessors) - 1

    position_accessor = append(positions, "<3f", "VEC3", 5126, bounds=True)
    normal_accessor = append(normals, "<3f", "VEC3", 5126)
    uv_accessor = append(uvs, "<2f", "VEC2", 5126)
    index_accessor = append(indices, "<H", "SCALAR", 5123)
    document = {
        "asset": {"version": "2.0", "generator": "pokeagent-stage4j-fixture-v1"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "stage4j_dense_shrine"}],
        "meshes": [{"name": "stage4j_dense_shrine", "primitives": [{
            "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor, "TEXCOORD_0": uv_accessor},
            "indices": index_accessor, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": "approx_shell"}], "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views, "accessors": accessors,
    }
    return pack_glb(document, bytes(binary))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_dense_shrine())


if __name__ == "__main__":
    main()
