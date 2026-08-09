"""Reproducible Stage 4Q sanitation and multi-component fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
import math
import struct

from .glb import pack_glb
from .glb_geometry_reduce import pack_geometry_glb, parse_geometry_glb
from .stage4o_fixture import build_dense_geometry_shrine


def _pack(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], *, color0: bool,
) -> bytes:
    binary = bytearray(); views = []; accessors = []

    def append(values, fmt, kind, component, *, bounds=False, normalized=False):
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values:
            binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            accessor["min"] = [min(value[axis] for value in values) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in values) for axis in range(3)]
        if normalized: accessor["normalized"] = True
        accessors.append(accessor); return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, bounds=True)
    attributes = {"POSITION": p}
    if color0:
        colors = [((index * 29) % 256, (index * 53 + 17) % 256, (255 - index * 31) % 256, 255) for index in range(len(positions))]
        attributes["COLOR_0"] = append(colors, "<4B", "VEC4", 5121, normalized=True)
    component, fmt = (5121, "<B") if len(positions) <= 255 else (5123, "<H")
    indices = [index for face in faces for index in face]
    ix = append(indices, fmt, "SCALAR", component)
    document = {
        "asset": {"generator": "pokeagent-stage4q-fixture-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "generated_topology"}],
        "meshes": [{"name": "generated_topology", "primitives": [{
            "attributes": attributes, "indices": ix, "mode": 4,
        }]}],
        "buffers": [{"byteLength": len(binary)}], "bufferViews": views, "accessors": accessors,
    }
    return pack_glb(document, bytes(binary))


def build_stage4q_multicomponent(
    *, reverse_faces: bool = False, component_translation: float = 0.0,
    component_scale: float = 1.0, color0: bool = True, include_degenerate: bool = True,
) -> tuple[bytes, bytes]:
    main = parse_geometry_glb(build_dense_geometry_shrine())["geometry"]
    positions = [tuple(point) for point in main["positions"]]
    faces = [tuple(face) for face in main["faces"]]
    center = (4.5 + component_translation, 4.9, 0.0)
    cap_segments = 16
    local = tuple(
        (0.65 * math.cos(2 * math.pi * index / cap_segments), 0.0, 0.65 * math.sin(2 * math.pi * index / cap_segments))
        for index in range(cap_segments)
    ) + ((0.0, 0.85, 0.0), (0.0, -0.85, 0.0))
    offset = len(positions)
    positions.extend(tuple(center[axis] + point[axis] * component_scale for axis in range(3)) for point in local)
    faces.extend(
        tuple(offset + index for index in face)
        for segment in range(cap_segments)
        for face in (
            (segment, (segment + 1) % cap_segments, cap_segments),
            ((segment + 1) % cap_segments, segment, cap_segments + 1),
        )
    )
    clean_positions = list(positions); clean_faces = list(faces)
    if include_degenerate:
        degenerate = len(positions)
        positions.extend(((8.0, 0.0, 0.0), (8.5, 0.0, 0.0), (9.0, 0.0, 0.0)))
        faces.append((degenerate, degenerate + 1, degenerate + 2))
    if reverse_faces:
        faces.reverse()
    source = _pack(positions, faces, color0=color0)
    reference = pack_geometry_glb({"schema_version": 1, "positions": clean_positions, "faces": clean_faces})
    return source, reference


def build_near_zero_fixture() -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    positions = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1e-13, 0.0),
        (2.0, 0.0, 0.0), (2.5, 0.0, 0.0), (3.0, 0.0, 0.0),
    ]
    return positions, [(0, 1, 2), (3, 4, 5)]


def build_boundary_loop_fixture() -> dict[str, object]:
    # A planar square frame: one connected component, outer and inner loops.
    positions = [
        (-2.0, 0.0, -2.0), (2.0, 0.0, -2.0), (2.0, 0.0, 2.0), (-2.0, 0.0, 2.0),
        (-0.8, 0.0, -0.8), (0.8, 0.0, -0.8), (0.8, 0.0, 0.8), (-0.8, 0.0, 0.8),
    ]
    faces = [
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    return {"schema_version": 1, "positions": positions, "faces": faces}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path); parser.add_argument("reference", type=Path)
    args = parser.parse_args(); source, reference = build_stage4q_multicomponent()
    args.source.parent.mkdir(parents=True, exist_ok=True)
    args.source.write_bytes(source); args.reference.write_bytes(reference)


if __name__ == "__main__":
    main()
