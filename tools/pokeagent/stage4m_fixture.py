"""Reproducible no-UV turret and independently authored UV reference."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import struct

from .glb import pack_glb
from .glb_uvs import _write_canonical


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(a[index] - b[index] for index in range(3))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(left * right for left, right in zip(a, b, strict=True))


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normalize(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    return tuple(component / length for component in value)


def _geometry(
    *, roof_height: float = 4.0, translation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[str]]:
    sides = 4
    rings = []
    for radius, height in ((2.0, 0.0), (2.0, 3.0), (1.2, roof_height)):
        rings.extend((radius * math.cos(math.radians(index * 90)), height, radius * math.sin(math.radians(index * 90))) for index in range(sides))
    positions = list(rings) + [(0.0, roof_height, 0.0)]
    positions = [tuple(value[index] + translation[index] for index in range(3)) for value in positions]
    triangles: list[tuple[int, int, int]] = []
    patches: list[str] = []
    for index in range(sides):
        next_index = (index + 1) % sides
        triangles.extend(((index, sides + index, sides + next_index), (index, sides + next_index, next_index)))
        patches.extend((f"wall_{index}", f"wall_{index}"))
    for index in range(sides):
        next_index = (index + 1) % sides
        triangles.extend(((sides + index, 2 * sides + index, 2 * sides + next_index), (sides + index, 2 * sides + next_index, sides + next_index)))
        patches.extend((f"roof_{index}", f"roof_{index}"))
    for index in range(sides):
        triangles.append((2 * sides + index, 3 * sides, 2 * sides + ((index + 1) % sides)))
        patches.append("top")
    return positions, triangles, patches


def _authored_normals(
    positions: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]],
) -> list[tuple[float, float, float]]:
    del triangles
    sides = (len(positions) - 1) // 3
    center_x, center_z = positions[-1][0], positions[-1][2]
    normals = []
    for ring in range(3):
        vertical = (0.0, 0.4, 1.0)[ring]
        for index in range(sides):
            position = positions[ring * sides + index]
            radial = _normalize((position[0] - center_x, 0.0, position[2] - center_z))
            normals.append(_normalize((radial[0], vertical, radial[2])))
    normals.append((0.0, 1.0, 0.0))
    return normals


def _pack_no_uv(
    positions: list[tuple[float, float, float]], normals: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]], *, reverse_faces: bool = False,
) -> bytes:
    ordered = list(reversed(triangles)) if reverse_faces else triangles
    indices = [value for triangle in ordered for value in triangle]
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[object], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values: binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            packed = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in values]
            accessor["min"] = [min(value[axis] for value in packed) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in packed) for axis in range(3)]
        accessors.append(accessor); return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, True); n = append(normals, "<3f", "VEC3", 5126)
    ix = append(indices, "<B", "SCALAR", 5121)
    document = {
        "asset": {"generator": "pokeagent-stage4m-source-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "uv_missing_turret"}],
        "meshes": [{"name": "uv_missing_turret", "primitives": [{
            "attributes": {"POSITION": p, "NORMAL": n}, "indices": ix, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": "turret_stone"}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def _basis(normal: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    up = (0.0, 1.0, 0.0)
    if abs(_dot(normal, up)) < 0.7071067811865476:
        bitangent = _normalize(tuple(up[index] - _dot(up, normal) * normal[index] for index in range(3)))
        return _normalize(_cross(bitangent, normal)), bitangent
    reference = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.95 else (0.0, 0.0, 1.0)
    tangent = _normalize(tuple(reference[index] - _dot(reference, normal) * normal[index] for index in range(3)))
    return tangent, _normalize(_cross(normal, tangent))


def _authored_reference(
    positions: list[tuple[float, float, float]], normals: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]], patches: list[str], *, padding: float = 1.0 / 32.0,
) -> bytes:
    face_records = sorted(
        zip(triangles, patches, strict=True),
        key=lambda record: ("turret_stone", tuple((positions[index], normals[index]) for index in record[0])),
    )
    grouped: dict[str, list[tuple[int, int, int]]] = {}
    for triangle, patch in face_records: grouped.setdefault(patch, []).append(triangle)
    uv_by_patch_position: dict[tuple[str, tuple[float, float, float]], tuple[float, float]] = {}
    for patch in sorted(grouped, key=lambda key: tuple(tuple((positions[index], normals[index]) for index in triangle) for triangle in grouped[key])):
        patch_triangles = grouped[patch]
        summed = [0.0, 0.0, 0.0]
        for a, b, c in patch_triangles:
            area = _cross(_sub(positions[b], positions[a]), _sub(positions[c], positions[a]))
            for axis in range(3): summed[axis] += area[axis]
        tangent, bitangent = _basis(_normalize(tuple(summed)))
        unique = sorted({positions[index] for triangle in patch_triangles for index in triangle})
        raw = {position: (_dot(position, tangent), _dot(position, bitangent)) for position in unique}
        min_u = min(value[0] for value in raw.values()); max_u = max(value[0] for value in raw.values())
        min_v = min(value[1] for value in raw.values()); max_v = max(value[1] for value in raw.values())
        width, height = max_u - min_u, max_v - min_v; usable = 1.0 - 2.0 * padding
        scale = usable / max(width, height); margin_u = (usable - width * scale) / 2.0; margin_v = (usable - height * scale) / 2.0
        for position, value in raw.items():
            uv_by_patch_position[(patch, position)] = (
                round(padding + margin_u + (value[0] - min_u) * scale, 6),
                round(padding + margin_v + (value[1] - min_v) * scale, 6),
            )
    semantic_vertices = sorted({
        (positions[index], normals[index], uv_by_patch_position[(patch, positions[index])])
        for triangle, patch in face_records for index in triangle
    })
    lookup = {value: index for index, value in enumerate(semantic_vertices)}
    canonical_triangles = [
        tuple(lookup[(positions[index], normals[index], uv_by_patch_position[(patch, positions[index])])] for index in triangle)
        for triangle, patch in face_records
    ]
    return _write_canonical(semantic_vertices, canonical_triangles, "turret_stone")


def build_stage4m_fixtures(
    *, roof_height: float = 4.0, reverse_faces: bool = False,
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0), padding_texels: int = 1,
) -> tuple[bytes, bytes]:
    positions, triangles, patches = _geometry(roof_height=roof_height, translation=translation)
    positions = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in positions]
    normals = _authored_normals(positions, triangles)
    normals = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in normals]
    return (
        _pack_no_uv(positions, normals, triangles, reverse_faces=reverse_faces),
        _authored_reference(positions, normals, triangles, patches, padding=padding_texels / 32.0),
    )


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("source", type=Path); parser.add_argument("reference", type=Path)
    args = parser.parse_args(); source, reference = build_stage4m_fixtures()
    args.source.parent.mkdir(parents=True, exist_ok=True); args.reference.parent.mkdir(parents=True, exist_ok=True)
    args.source.write_bytes(source); args.reference.write_bytes(reference)


if __name__ == "__main__":
    main()
