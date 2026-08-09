"""Reproducible material-missing turret and authored-material reference."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct

from .glb import BIN_CHUNK, JSON_CHUNK, pack_glb
from .glb_uvs import generate_missing_uvs
from .stage4m_fixture import build_stage4m_fixtures


def _document_and_binary(data: bytes) -> tuple[dict[str, object], bytes]:
    json_length, json_kind = struct.unpack_from("<II", data, 12)
    if json_kind != JSON_CHUNK:
        raise ValueError("fixture GLB must start with JSON")
    document = json.loads(data[20:20 + json_length])
    offset = 20 + json_length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    if binary_kind != BIN_CHUNK:
        raise ValueError("fixture GLB must contain BIN")
    return document, data[offset + 8:offset + 8 + binary_length]


def build_stage4n_fixtures(
    *, material_name: str = "generated_surface", roof_height: float = 4.0,
    hierarchical: bool = False,
) -> tuple[bytes, bytes]:
    no_uv, _reference = build_stage4m_fixtures(roof_height=roof_height)
    strict = generate_missing_uvs(no_uv)["canonical_glb"]
    document, binary = _document_and_binary(strict)
    source = copy.deepcopy(document)
    source["asset"] = {"generator": "pokeagent-stage4n-source-v1", "version": "2.0"}
    source["nodes"] = [{"mesh": 0, "name": "material_missing_turret"}]
    source["meshes"][0]["name"] = "material_missing_turret"
    source.pop("materials")
    source["meshes"][0]["primitives"][0].pop("material")
    if hierarchical:
        source["scenes"] = [{"nodes": [0]}]
        source["nodes"] = [
            {"name": "material_root", "translation": [1.0, 0.0, -1.0], "children": [1]},
            {"mesh": 0, "name": "material_mesh", "rotation": [0.0, 0.0, 0.0, 1.0]},
        ]
    authored = copy.deepcopy(source)
    authored["materials"] = [{"name": material_name}]
    authored["meshes"][0]["primitives"][0]["material"] = 0
    return pack_glb(source, binary), pack_glb(authored, binary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("reference", type=Path)
    args = parser.parse_args()
    source, reference = build_stage4n_fixtures()
    args.source.parent.mkdir(parents=True, exist_ok=True)
    args.source.write_bytes(source)
    args.reference.write_bytes(reference)


if __name__ == "__main__":
    main()
