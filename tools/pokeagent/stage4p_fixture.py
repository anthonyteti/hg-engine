"""Reproducible Stage 4P geometry-only, reference, and COLOR_0 fixtures."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from .glb import pack_glb
from .glb_bootstrap import pack_uv_material_without_normals
from .glb_geometry_reduce import pack_geometry_glb
from .glb_normals import generate_missing_normals
from .glb_uvs import generate_planar_uvs_from_geometry
from .mesh_predecimate import canonical_geometry


def _geometry(
    *, roof_height: float = 4.5, reverse_faces: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    sides = 6
    positions: list[tuple[float, float, float]] = []
    for radius, height in ((2.0, 0.0), (2.15, 0.4), (2.0, 3.0)):
        positions.extend(
            (radius * math.cos(math.radians(index * 60)), height, radius * math.sin(math.radians(index * 60)))
            for index in range(sides)
        )
    apex = len(positions); positions.append((0.0, roof_height, 0.0))
    triangles: list[tuple[int, int, int]] = []
    for lower, upper in ((0, sides), (sides, 2 * sides)):
        for index in range(sides):
            next_index = (index + 1) % sides
            triangles.extend((
                (lower + index, upper + index, upper + next_index),
                (lower + index, upper + next_index, lower + next_index),
            ))
    for index in range(sides):
        triangles.append((2 * sides + index, apex, 2 * sides + ((index + 1) % sides)))
    packed_positions = [struct.unpack("<3f", struct.pack("<3f", *position)) for position in positions]
    return packed_positions, list(reversed(triangles)) if reverse_faces else triangles


def _pack_source(
    positions: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]],
    *, colors: list[tuple[int, int, int, int]] | None = None,
) -> bytes:
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[object], fmt: str, kind: str, component: int, bounds: bool = False, normalized: bool = False) -> int:
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values: binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            accessor["min"] = [min(value[axis] for value in values) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in values) for axis in range(3)]
        if normalized: accessor["normalized"] = True
        accessors.append(accessor); return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, True)
    attributes = {"POSITION": p}
    if colors is not None:
        attributes["COLOR_0"] = append(colors, "<4B", "VEC4", 5121, normalized=True)
    indices = [index for triangle in triangles for index in triangle]
    ix = append(indices, "<B", "SCALAR", 5121)
    document = {
        "asset": {"generator": "pokeagent-stage4p-source-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "bootstrap_geometry"}],
        "meshes": [{"name": "bootstrap_geometry", "primitives": [{
            "attributes": attributes, "indices": ix, "mode": 4,
        }]}],
        "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def _reference(positions: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]]) -> bytes:
    geometry = canonical_geometry(positions, triangles)
    uv = generate_planar_uvs_from_geometry(
        geometry["positions"], geometry["faces"], "generated_surface",
        patch_normal_degrees=0.1, plane_epsilon=1e-5, texture_size=32, padding_texels=1,
    )
    # This direct reference path constructs the complete expected semantics
    # independently of the Stage 4P transaction/orchestrator.
    no_normal = pack_uv_material_without_normals(uv["vertices"], uv["triangles"], "generated_surface")
    return generate_missing_normals(no_normal, crease_angle_degrees=60, weighting="area")["canonical_glb"]


def build_stage4p_fixtures(
    *, roof_height: float = 4.5, reverse_faces: bool = False,
) -> tuple[bytes, bytes, bytes, bytes]:
    positions, triangles = _geometry(roof_height=roof_height, reverse_faces=reverse_faces)
    source = _pack_source(positions, triangles)
    reference = _reference(positions, triangles)
    colors = [
        ((index * 37) % 256, (255 - index * 23) % 256, (index * 71) % 256, 255)
        for index in range(len(positions))
    ]
    color_source = _pack_source(positions, triangles, colors=colors)
    color_reference = pack_geometry_glb(canonical_geometry(positions, triangles))
    return source, reference, color_source, color_reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path); parser.add_argument("reference", type=Path)
    parser.add_argument("color_source", type=Path); parser.add_argument("color_reference", type=Path)
    args = parser.parse_args(); outputs = build_stage4p_fixtures()
    for path, data in zip((args.source, args.reference, args.color_source, args.color_reference), outputs, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)


if __name__ == "__main__":
    main()
