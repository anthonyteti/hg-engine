"""Reproducible no-normal turret and independently authored normal reference."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from .glb import pack_glb
from .glb_normals import _write_canonical


def _normalize(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(component * component for component in value))
    return tuple(component / length for component in value)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(a[index] - b[index] for index in range(3))


def _source_geometry(*, roof_height: float = 4.0) -> tuple[list[tuple[float, float, float]], list[tuple[float, float]], list[tuple[int, int, int]]]:
    radius = 2.0
    ring = [(radius * math.cos(math.radians(index * 45)), radius * math.sin(math.radians(index * 45))) for index in range(8)]
    positions: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    # Wall seam is represented by duplicated attributes at i=0/i=8.
    for height, v in ((0.0, 0.0), (3.0, 1.0)):
        for index in range(9):
            x, z = ring[index % 8]
            positions.append((x, height, z)); uvs.append((index / 8, v))
    # Roof reuses the upper-ring attributes. Its geometric crease therefore
    # requires true normal-driven vertex splitting. The i=0/i=8 wall wrap is a
    # separate UV identity and remains the controlled UV-seam proof.
    positions.append((0.0, roof_height, 0.0)); uvs.append((0.5, 0.5))
    triangles: list[tuple[int, int, int]] = []
    for index in range(8):
        bottom, next_bottom = index, index + 1
        top, next_top = 9 + index, 9 + index + 1
        triangles.extend(((bottom, top, next_top), (bottom, next_top, next_bottom)))
    apex = 18
    for index in range(8):
        triangles.append((9 + index, apex, 9 + ((index + 1) % 8)))
    return positions, uvs, triangles


def _pack_source(
    positions: list[tuple[float, float, float]], uvs: list[tuple[float, float]],
    triangles: list[tuple[int, int, int]], *, reverse_faces: bool = False,
) -> bytes:
    ordered = list(reversed(triangles)) if reverse_faces else triangles
    indices = [value for triangle in ordered for value in triangle]
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[object], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values:
            binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            packed = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in values]
            accessor["min"] = [min(value[axis] for value in packed) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in packed) for axis in range(3)]
        accessors.append(accessor); return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, True)
    uv = append(uvs, "<2f", "VEC2", 5126)
    ix = append(indices, "<B", "SCALAR", 5121)
    document = {
        "asset": {"generator": "pokeagent-stage4l-source-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "normal_missing_turret"}],
        "meshes": [{"name": "normal_missing_turret", "primitives": [{
            "attributes": {"POSITION": p, "TEXCOORD_0": uv}, "indices": ix, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": "turret_stone"}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def _authored_reference(
    positions: list[tuple[float, float, float]], uvs: list[tuple[float, float]], triangles: list[tuple[int, int, int]],
) -> bytes:
    area_vectors = [
        _cross(_sub(positions[triangle[1]], positions[triangle[0]]), _sub(positions[triangle[2]], positions[triangle[0]]))
        for triangle in triangles
    ]
    # The authored smoothing design has independent wall and roof fans. Upper
    # ring attributes are intentionally split at the >60-degree roof crease.
    normal_by_group: dict[tuple[str, int], tuple[float, float, float]] = {}
    for group, face_range in (("wall", range(16)), ("roof", range(16, 24))):
        for attribute in range(len(positions)):
            incident = [area_vectors[index] for index in face_range if attribute in triangles[index]]
            if incident:
                normal_by_group[(group, attribute)] = _normalize(
                    tuple(sum(value[axis] for value in incident) for axis in range(3))
                )
    semantic_vertices = sorted({
        (positions[attribute], uvs[attribute], normal_by_group[("wall" if face_index < 16 else "roof", attribute)])
        for face_index, triangle in enumerate(triangles) for attribute in triangle
    })
    lookup = {value: index for index, value in enumerate(semantic_vertices)}
    canonical_triangles = [
        tuple(lookup[(positions[index], uvs[index], normal_by_group[("wall" if original_index < 16 else "roof", index)])] for index in triangle)
        for original_index, triangle in sorted(enumerate(triangles), key=lambda item: tuple((positions[index], uvs[index]) for index in item[1]))
    ]
    return _write_canonical(semantic_vertices, canonical_triangles, "turret_stone")


def build_stage4l_fixtures(*, roof_height: float = 4.0, reverse_faces: bool = False) -> tuple[bytes, bytes]:
    positions, uvs, triangles = _source_geometry(roof_height=roof_height)
    # The direct authored reference is defined over the exact float32 values
    # that the source GLB exposes, not over Python's higher-precision builders.
    positions = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in positions]
    uvs = [struct.unpack("<2f", struct.pack("<2f", *value)) for value in uvs]
    return _pack_source(positions, uvs, triangles, reverse_faces=reverse_faces), _authored_reference(positions, uvs, triangles)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path); parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    source, reference = build_stage4l_fixtures()
    args.source.parent.mkdir(parents=True, exist_ok=True); args.reference.parent.mkdir(parents=True, exist_ok=True)
    args.source.write_bytes(source); args.reference.write_bytes(reference)


if __name__ == "__main__":
    main()
