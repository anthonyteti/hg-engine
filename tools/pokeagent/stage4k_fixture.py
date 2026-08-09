"""Reproducible Stage 4K hierarchical and direct-flat GLB fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import struct

from .glb import BIN_CHUNK, JSON_CHUNK, pack_glb, parse_glb


EXPECTED_WORLD_MATRIX = (
    (0.523923048454, 0.0, 0.917759341371, 2.265165042945),
    (0.0, 1.21, 0.0, 0.775),
    (-0.787461339179, 0.0, 0.434605808376, -1.583363094479),
    (0.0, 0.0, 0.0, 1.0),
)


def _unpack(data: bytes) -> tuple[dict[str, object], bytes]:
    json_length, json_kind = struct.unpack_from("<II", data, 12)
    if json_kind != JSON_CHUNK:
        raise ValueError("fixture source is missing JSON chunk")
    document = json.loads(data[20:20 + json_length].decode("utf-8"))
    offset = 20 + json_length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    if binary_kind != BIN_CHUNK:
        raise ValueError("fixture source is missing BIN chunk")
    return document, data[offset + 8:offset + 8 + binary_length]


def _direct_flat_reference(reference_source: bytes) -> bytes:
    """Build the expected flat GLB independently from the Stage 4K adapter."""
    mesh = parse_glb(reference_source)
    matrix = EXPECTED_WORLD_MATRIX
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    inverse = (
        ((e * i - f * h) / determinant, (c * h - b * i) / determinant, (b * f - c * e) / determinant),
        ((f * g - d * i) / determinant, (a * i - c * g) / determinant, (c * d - a * f) / determinant),
        ((d * h - e * g) / determinant, (b * g - a * h) / determinant, (a * e - b * d) / determinant),
    )
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    indices: list[int] = []
    for face in mesh.faces:
        for corner in face.corners:
            position = mesh.vertices[corner.vertex]
            positions.append(tuple(
                sum(matrix[row][column] * position[column] for column in range(3)) + matrix[row][3]
                for row in range(3)
            ))
            normal = mesh.normals[corner.normal]
            transformed = tuple(
                sum(inverse[column][row] * normal[column] for column in range(3)) for row in range(3)
            )
            length = math.sqrt(sum(value * value for value in transformed))
            normals.append(tuple(value / length for value in transformed))
            uvs.append(mesh.uvs[corner.uv])
            indices.append(len(indices))

    binary = bytearray()
    views: list[dict[str, int]] = []
    accessors: list[dict[str, object]] = []

    def append(values: list[object], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        for value in values:
            binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {
            "bufferView": len(views) - 1, "componentType": component,
            "count": len(values), "type": kind,
        }
        if bounds:
            packed = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in values]
            accessor["min"] = [min(value[axis] for value in packed) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in packed) for axis in range(3)]
        accessors.append(accessor)
        return len(accessors) - 1

    position_accessor = append(positions, "<3f", "VEC3", 5126, True)
    normal_accessor = append(normals, "<3f", "VEC3", 5126)
    uv_accessor = append(uvs, "<2f", "VEC2", 5126)
    index_accessor = append(indices, "<B", "SCALAR", 5121)
    material = next(iter({face.material for face in mesh.faces}))
    document = {
        "asset": {"generator": "pokeagent-stage4k-canonical-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "canonical_static_mesh"}],
        "meshes": [{"name": "canonical_static_mesh", "primitives": [{
            "attributes": {
                "POSITION": position_accessor, "NORMAL": normal_accessor, "TEXCOORD_0": uv_accessor,
            },
            "indices": index_accessor, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": material}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def build_stage4k_fixtures(reference_source: bytes, *, parent_y_degrees: float = 45.0) -> tuple[bytes, bytes]:
    """Wrap the proven tower in a non-trivial two-node TRS chain and flatten it."""
    document, binary = _unpack(reference_source)
    document = copy.deepcopy(document)
    radians = math.radians(parent_y_degrees) / 2
    child_radians = math.radians(15.0) / 2
    document["asset"] = {"generator": "pokeagent-stage4k-hierarchy-v1", "version": "2.0"}
    document["scene"] = 0
    document["scenes"] = [{"nodes": [0]}]
    document["nodes"] = [
        {
            "name": "stage4k_parent", "children": [1],
            "translation": [2.0, 0.5, -1.0],
            "rotation": [0.0, math.sin(radians), 0.0, math.cos(radians)],
            "scale": [1.2, 1.1, 0.9],
        },
        {
            "name": "stage4k_mesh", "mesh": 0,
            "translation": [0.5, 0.25, -0.25],
            "rotation": [0.0, math.sin(child_radians), 0.0, math.cos(child_radians)],
            "scale": [0.8, 1.1, 1.1],
        },
    ]
    hierarchical = pack_glb(document, binary)
    flattened = _direct_flat_reference(reference_source)
    return hierarchical, flattened


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("hierarchical", type=Path)
    parser.add_argument("flat", type=Path)
    args = parser.parse_args()
    hierarchical, flat = build_stage4k_fixtures(args.reference.read_bytes())
    args.hierarchical.parent.mkdir(parents=True, exist_ok=True)
    args.flat.parent.mkdir(parents=True, exist_ok=True)
    args.hierarchical.write_bytes(hierarchical)
    args.flat.write_bytes(flat)


if __name__ == "__main__":
    main()
