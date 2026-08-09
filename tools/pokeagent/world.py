"""Deterministic HGSS world-proof generator for Stages 2 through 4D.

This intentionally implements only the binary subset required by the fixture.
The NSBMD writer is a hash-locked, user-local template transformer: it preserves
the template's material dictionaries while replacing every display list and
emitting only the bounded static geometry required by each fixture.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
from typing import Any

from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom

from .assets import ASSET_MATERIAL_BINDINGS, compile_asset, compile_placements, load_catalog
from .geometry import MATERIAL_BINDINGS, MATERIAL_ORDER, GeometryError, compile_geometry
from .registry import (
    load_registry,
    resolve_stage3d_source,
    resolve_stage3e1_source,
    resolve_stage4b_source,
    resolve_stage4c_source,
    resolve_stage4d_source,
    resolve_stage4e_source,
    resolve_stage4f_source,
    resolve_world_source,
    verify_rom_revision,
)
from .textures import build_project_btx0, compile_texture_catalog, parse_btx0, patch_btx0


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "fixtures" / "stage2_proof_map.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "stage2" / "generated"
HGSS_US_HEADER_OFFSET = 0xF6BE0
MAP_HEADER_SIZE = 24
MAP_TILES = 32
STAGE3B_CELL_ORDER = ("nw", "ne", "sw", "se")
STAGE3E1_CELL_ORDER = ("west", "east")
STAGE3B_CONTROLLED_HEADERS = {"nw": 538, "ne": 9, "sw": 10, "se": 11}
STAGE3B_CONTROLLED_MEMBERS = {"nw": 633, "ne": 630, "sw": 631, "se": 632}
CARDINAL_DELTAS = {
    "north": (-1, 0),
    "east": (0, 1),
    "south": (1, 0),
    "west": (0, -1),
}
OPPOSITE_EDGE = {"north": "south", "east": "west", "south": "north", "west": "east"}

NARC_PATHS = {
    "map": Path("base/root/a/0/6/5"),
    "matrix": Path("base/root/a/0/4/1"),
    "event": Path("base/root/a/0/3/2"),
    "script": Path("base/root/a/0/1/2"),
    "text": Path("base/root/a/0/2/7"),
}


class WorldBuildError(ValueError):
    """The canonical fixture or local template does not satisfy the proof contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_fixture(path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    try:
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorldBuildError(f"cannot load fixture {path}: {error}") from error
    if fixture.get("schema_version") == 4:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 3C fixture must declare a symbolic registry path")
        fixture = resolve_world_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 5:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 3D fixture must declare a symbolic registry path")
        fixture = resolve_stage3d_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 6:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 3E1 fixture must declare a symbolic registry path")
        fixture = resolve_stage3e1_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 7:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 3E2 fixture must declare a symbolic registry path")
        fixture = resolve_stage3e1_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 8:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 4B fixture must declare a symbolic registry path")
        fixture = resolve_stage4b_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 9:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 4C fixture must declare a symbolic registry path")
        fixture = resolve_stage4c_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 10:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 4D fixture must declare a symbolic registry path")
        fixture = resolve_stage4d_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 11:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 4E fixture must declare a symbolic registry path")
        fixture = resolve_stage4e_source(fixture, PROJECT_ROOT / registry_reference)
    elif fixture.get("schema_version") == 12:
        registry_reference = fixture.get("registry")
        if not isinstance(registry_reference, str):
            raise WorldBuildError("Stage 4F fixture must declare a symbolic registry path")
        fixture = resolve_stage4f_source(fixture, PROJECT_ROOT / registry_reference)
    validate_fixture(fixture)
    return fixture


def validate_fixture(fixture: dict[str, Any]) -> None:
    schema_version = fixture.get("schema_version")
    if schema_version not in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12):
        raise WorldBuildError("only resolved Stage 2 through Stage 4F schemas are supported")
    if schema_version in (8, 9, 10, 11, 12):
        _validate_stage4b_fixture(fixture)
        return
    if schema_version == 7:
        _validate_stage3e2_fixture(fixture)
        return
    if schema_version == 6:
        _validate_stage3e1_fixture(fixture)
        return
    if schema_version == 5:
        _validate_stage3d_fixture(fixture)
        return
    if schema_version == 3:
        _validate_stage3b_fixture(fixture)
        return
    dimensions = fixture.get("dimensions", {})
    if dimensions != {"width": 32, "height": 32}:
        raise WorldBuildError("Stage 2 is deliberately limited to one 32x32 map")
    slots = fixture.get("slots", {})
    required_slots = {
        "map_header", "matrix", "map_member", "event", "script",
        "start_script", "script_header", "text",
    }
    if set(slots) != required_slots or any(not isinstance(value, int) or value < 0 for value in slots.values()):
        raise WorldBuildError("slots must contain exactly the eight non-negative deterministic IDs")
    if slots["matrix"] != 1:
        raise WorldBuildError("matrix slot 1 is the verified unreferenced US HG slot")
    if slots["map_member"] != 633:
        raise WorldBuildError("map member 633 is the verified unreferenced US HG slot")
    if schema_version == 1:
        blocked = fixture.get("terrain", {}).get("blocked_tiles", [])
        if not blocked:
            raise WorldBuildError("at least one deliberately blocked tile is required")
        occupied = {(fixture["npc"]["x"], fixture["npc"]["z"])}
        occupied.update((warp["x"], warp["z"]) for warp in fixture.get("warps", []))
        for tile in blocked:
            if len(tile) != 2 or not all(isinstance(v, int) and 0 <= v < 32 for v in tile):
                raise WorldBuildError(f"invalid blocked tile {tile!r}")
            if tuple(tile) in occupied:
                raise WorldBuildError(f"blocked tile {tile!r} overlaps an NPC or warp")
        if len(fixture.get("warps", [])) != 2:
            raise WorldBuildError("the Stage 2 proof requires exactly one reciprocal warp pair")
        header = slots["map_header"]
        if any(warp["destination_header"] != header for warp in fixture["warps"]):
            raise WorldBuildError("Stage 2 warps must be reciprocal within the proof header")
        if sorted(warp["destination_warp"] for warp in fixture["warps"]) != [0, 1]:
            raise WorldBuildError("reciprocal warp destination indices must be 0 and 1")
        return

    if fixture.get("artifact_namespace") != "stage3a":
        raise WorldBuildError("Stage 3A schema 2 must use the stage3a artifact namespace")
    if slots["map_header"] != 538:
        raise WorldBuildError("Stage 3A requires the explicit non-special MAP_UNUSED header 538")
    if fixture.get("warps") != [] or "npc" in fixture:
        raise WorldBuildError("the Stage 3A height fixture must not add NPCs or warps")
    terrain = fixture.get("terrain", {})
    expected_regions = {
        "lower": {"min_x": 0, "max_x": 15, "min_z": 0, "max_z": 31, "height": 0},
        "transition": {
            "min_x": 16, "max_x": 17, "min_z": 14, "max_z": 17,
            "start_height": 0, "end_height": 2,
        },
        "raised": {"min_x": 16, "max_x": 31, "min_z": 0, "max_z": 31, "height": 2},
    }
    for name, expected in expected_regions.items():
        if terrain.get(name) != expected:
            raise WorldBuildError(f"Stage 3A {name} region must match the bounded proof profile")
    for key in ("permission_type", "walkable_collision", "blocked_collision"):
        if not isinstance(terrain.get(key), int) or not 0 <= terrain[key] <= 255:
            raise WorldBuildError(f"Stage 3A terrain {key} must be a byte")
    if terrain.get("block_border") is not True:
        raise WorldBuildError("Stage 3A requires a blocked perimeter")


def _validate_stage3d_fixture(fixture: dict[str, Any]) -> None:
    if fixture.get("artifact_namespace") != "stage3d" or fixture.get("canonical_schema_version") != 5:
        raise WorldBuildError("resolved Stage 3D source must preserve schema and artifact identity")
    if fixture.get("dimensions") != {"width": 32, "height": 32}:
        raise WorldBuildError("Stage 3D remains limited to one 32x32 map")
    required_slots = {
        "map_header", "matrix", "map_member", "event", "script", "start_script", "script_header", "text",
    }
    slots = fixture.get("slots", {})
    if set(slots) != required_slots or any(not isinstance(value, int) or value < 0 for value in slots.values()):
        raise WorldBuildError("Stage 3D must resolve exactly eight registry-owned numeric slots")
    matrix = fixture.get("world", {}).get("matrix", {})
    if matrix != {"width": 1, "height": 1, "name": "stage3d-terrain", "altitudes": [0]}:
        raise WorldBuildError("Stage 3D requires the bounded 1x1 terrain matrix")
    if fixture.get("warps") != [] or "npc" in fixture:
        raise WorldBuildError("Stage 3D geometry proof must not add NPCs or warps")
    start = fixture.get("player_start")
    if start != {"x": 8, "z": 12, "direction": 3}:
        raise WorldBuildError("Stage 3D controlled start must use the proof route origin")
    if fixture.get("model", {}).get("half_extent") != 16:
        raise WorldBuildError("Stage 3D template model must retain the 32x32 centered extent")
    compile_geometry(fixture.get("geometry"))


def _validate_stage4b_fixture(fixture: dict[str, Any]) -> None:
    schema = fixture.get("schema_version")
    expected = {
        8: ("stage4b", "stage4b-assets"),
        9: ("stage4c", "stage4c-texture"),
        10: ("stage4d", "stage4d-scalable-textures"),
        11: ("stage4e", "stage4e-triangles"),
        12: ("stage4f", "stage4f-glb"),
    }
    if schema not in expected:
        raise WorldBuildError("asset fixture must use a resolved Stage 4B through Stage 4F schema")
    namespace, matrix_name = expected[schema]
    if fixture.get("artifact_namespace") != namespace or fixture.get("canonical_schema_version") != schema:
        raise WorldBuildError(f"resolved {namespace} source must preserve schema and artifact identity")
    if fixture.get("dimensions") != {"width": 32, "height": 32}:
        raise WorldBuildError("Stage 4B remains limited to one 32x32 map")
    required_slots = {
        "map_header", "matrix", "map_member", "event", "script", "start_script", "script_header", "text",
    }
    slots = fixture.get("slots", {})
    if set(slots) != required_slots or any(not isinstance(value, int) or value < 0 for value in slots.values()):
        raise WorldBuildError("Stage 4B must resolve exactly eight registry-owned numeric slots")
    matrix = fixture.get("world", {}).get("matrix", {})
    if matrix != {"width": 1, "height": 1, "name": matrix_name, "altitudes": [0]}:
        raise WorldBuildError(f"{namespace} requires the bounded 1x1 asset matrix")
    if fixture.get("warps") != [] or "npc" in fixture:
        raise WorldBuildError("Stage 4B asset proof must not add NPCs or warps")
    expected_start = (
        {"x": 16, "z": 24, "direction": 0} if schema == 10
        else {"x": 16, "z": 22, "direction": 0} if schema in (11, 12)
        else {"x": 16, "z": 20, "direction": 0}
    )
    if fixture.get("player_start") != expected_start:
        raise WorldBuildError("asset controlled start does not match its bounded proof route")
    if fixture.get("model", {}).get("half_extent") != 16:
        raise WorldBuildError("Stage 4B template model must retain the centered 32x32 extent")
    terrain = fixture.get("terrain")
    if terrain != {
        "height": 0, "block_border": True, "permission_type": 0,
        "walkable_collision": 0, "blocked_collision": 128,
    }:
        raise WorldBuildError("Stage 4B requires the exact flat normal-overworld terrain profile")
    catalog = fixture.get("asset_catalog")
    if not isinstance(catalog, str):
        raise WorldBuildError("Stage 4B must declare its project-local asset catalog")
    compiled = compile_placements(PROJECT_ROOT / catalog, fixture.get("assets"), PROJECT_ROOT)
    expected_placements = 2 if schema == 10 else 1
    if compiled["report"]["placement_count"] != expected_placements:
        raise WorldBuildError(f"asset proof requires exactly {expected_placements} external asset placement(s)")
    if schema == 9:
        catalog_entries = load_catalog(PROJECT_ROOT / catalog, PROJECT_ROOT)
        asset = compile_asset(catalog_entries[fixture["assets"][0]["asset"]], PROJECT_ROOT)
        if len(asset["textures"]) != 1:
            raise WorldBuildError("Stage 4C proof asset must compile exactly one project texture")
    if schema == 10:
        container = fixture.get("texture_container", {})
        if container.get("area_data_bank") != 106 or container.get("area_texture_member") != 106:
            raise WorldBuildError("Stage 4D must use the first registry-owned appended area records")
        catalog = compile_texture_catalog(PROJECT_ROOT / container.get("catalog", ""), PROJECT_ROOT)
        bound = {
            mapping["texture"]
            for placement in fixture["assets"]
            for mapping in compile_asset(
                load_catalog(PROJECT_ROOT / fixture["asset_catalog"], PROJECT_ROOT)[placement["asset"]],
                PROJECT_ROOT,
            )["manifest"]["material_policy"]["mappings"].values()
        }
        if bound != {"stage4d_wood", "stage4d_stone"} or len(catalog["textures"]) < 3:
            raise WorldBuildError("Stage 4D must bind two distinct asset textures plus project ground")
    if schema == 11:
        container = fixture.get("texture_container", {})
        if container.get("area_data_bank") != 106 or container.get("area_texture_member") != 106:
            raise WorldBuildError("Stage 4E must preserve the Stage 4D project texture container")
        asset_path = load_catalog(PROJECT_ROOT / catalog, PROJECT_ROOT)[fixture["assets"][0]["asset"]]
        asset = compile_asset(asset_path, PROJECT_ROOT)
        counts = asset["report"]["normalized_counts"]
        if asset["manifest"]["schema_version"] != 4 or counts["triangles"] < 1 or counts["quads"] < 1:
            raise WorldBuildError("Stage 4E proof asset must contain both triangles and quads")
    if schema == 12:
        container = fixture.get("texture_container", {})
        if container.get("area_data_bank") != 106 or container.get("area_texture_member") != 106:
            raise WorldBuildError("Stage 4F must preserve the Stage 4D project texture container")
        asset_path = load_catalog(PROJECT_ROOT / catalog, PROJECT_ROOT)[fixture["assets"][0]["asset"]]
        asset = compile_asset(asset_path, PROJECT_ROOT)
        counts = asset["report"]["normalized_counts"]
        if (
            asset["manifest"]["schema_version"] != 5
            or asset["report"]["source_format"] != "glb"
            or counts["triangles"] < 1
            or counts["quads"] != 0
        ):
            raise WorldBuildError("Stage 4F proof asset must be an all-triangle schema-5 GLB")


def _validate_stage3e1_fixture(fixture: dict[str, Any]) -> None:
    if fixture.get("artifact_namespace") != "stage3e1" or fixture.get("canonical_schema_version") != 6:
        raise WorldBuildError("resolved Stage 3E1 source must preserve schema and artifact identity")
    if fixture.get("dimensions") != {"width": 32, "height": 32}:
        raise WorldBuildError("Stage 3E1 members remain limited to 32x32")
    matrix = fixture.get("world", {}).get("matrix", {})
    if matrix != {
        "width": 2, "height": 1, "name": "stage3e1-append",
        "cells": ["west", "east"], "altitudes": [0, 0], "external_boundaries": "blocked",
    }:
        raise WorldBuildError("Stage 3E1 requires the bounded west/east 2x1 matrix")
    slots = fixture.get("slots", {})
    if set(slots) != {"matrix", "matrix_probe", "start_script"}:
        raise WorldBuildError("Stage 3E1 slots must contain active/probe matrices and controlled start")
    if slots["matrix"] != 288 or slots["matrix_probe"] != 289 or slots["start_script"] != 3:
        raise WorldBuildError("Stage 3E1 append IDs must match the persistent registry proof window")
    maps = fixture.get("maps")
    if not isinstance(maps, dict) or tuple(maps) != STAGE3E1_CELL_ORDER:
        raise WorldBuildError("Stage 3E1 maps must resolve in deterministic west/east order")
    expected = {
        "west": {"cell": {"row": 0, "column": 0}, "header": 538, "member": 676,
                 "event": 491, "script": 965, "script_header": 967, "text": 854, "edge": {"east": [16]}},
        "east": {"cell": {"row": 0, "column": 1}, "header": 9, "member": 677,
                 "event": 492, "script": 966, "script_header": 968, "text": 855, "edge": {"west": [16]}},
    }
    for name in STAGE3E1_CELL_ORDER:
        spec = maps[name]
        profile = expected[name]
        for key in ("cell", "map_header", "map_member", "event", "script", "script_header", "text"):
            expected_value = profile[{"map_header": "header", "map_member": "member"}.get(key, key)]
            if spec.get(key) != expected_value:
                raise WorldBuildError(f"Stage 3E1 {name} {key} disagrees with the registry proof profile")
        if spec.get("edge_openings") != profile["edge"]:
            raise WorldBuildError(f"Stage 3E1 {name} must expose only the reciprocal native edge")
        npc = spec.get("npc", {})
        required_npc = {
            "local_id", "graphics_id", "movement_type", "direction", "local_x", "local_z",
            "script_index", "marker_value", "dialogue", "marker_var",
        }
        if set(npc) != required_npc or npc["marker_var"] != 0x4000 or npc["script_index"] != 1:
            raise WorldBuildError(f"Stage 3E1 {name} NPC/script proof is malformed")
    if fixture.get("player_start") != {"map": "west", "local_x": 16, "local_z": 16, "direction": 3}:
        raise WorldBuildError("Stage 3E1 controlled start must begin in the west member")
    if fixture.get("warps") != []:
        raise WorldBuildError("Stage 3E1 native adjacency must not use event warps")


def _validate_stage3e2_fixture(fixture: dict[str, Any]) -> None:
    if fixture.get("artifact_namespace") != "stage3e2" or fixture.get("canonical_schema_version") != 7:
        raise WorldBuildError("resolved Stage 3E2 source must preserve schema and artifact identity")
    if fixture.get("dimensions") != {"width": 32, "height": 32}:
        raise WorldBuildError("Stage 3E2 members remain limited to 32x32")
    matrix = fixture.get("world", {}).get("matrix", {})
    if matrix != {
        "width": 2, "height": 1, "name": "stage3e2-headers",
        "cells": ["west", "east"], "altitudes": [0, 0], "external_boundaries": "blocked",
    }:
        raise WorldBuildError("Stage 3E2 requires the bounded west/east 2x1 matrix")
    if fixture.get("slots") != {"matrix": 288, "matrix_probe": 289, "start_script": 3}:
        raise WorldBuildError("Stage 3E2 must reuse the append-proven resource window")
    maps = fixture.get("maps")
    if not isinstance(maps, dict) or tuple(maps) != STAGE3E1_CELL_ORDER:
        raise WorldBuildError("Stage 3E2 maps must resolve in deterministic west/east order")
    expected_headers = {"west": 540, "east": 541}
    for name in STAGE3E1_CELL_ORDER:
        spec = maps[name]
        if spec.get("map_header") != expected_headers[name]:
            raise WorldBuildError(f"Stage 3E2 {name} must use its contiguous project header")
        if spec.get("map_member") not in (676, 677) or spec.get("event") not in (491, 492):
            raise WorldBuildError(f"Stage 3E2 {name} must use append-proven map/event resources")
    if fixture.get("player_start") != {"map": "west", "local_x": 16, "local_z": 16, "direction": 3}:
        raise WorldBuildError("Stage 3E2 controlled start must begin in project header 540")
    if fixture.get("warps") != []:
        raise WorldBuildError("Stage 3E2 reserves A-to-B movement for native adjacency")
    _encode_header_flags(fixture.get("header_profile"))


def _validate_stage3b_fixture(fixture: dict[str, Any]) -> None:
    namespace = fixture.get("artifact_namespace")
    is_stage3c = namespace == "stage3c" and fixture.get("canonical_schema_version") == 4
    if namespace != "stage3b" and not is_stage3c:
        raise WorldBuildError("resolved multi-map schema must use the stage3b or stage3c artifact namespace")
    if fixture.get("dimensions") != {"width": MAP_TILES, "height": MAP_TILES}:
        raise WorldBuildError("Stage 3B map members must each be 32x32")
    slots = fixture.get("slots", {})
    required_slots = {"matrix", "event", "script", "start_script", "script_header", "text"}
    if set(slots) != required_slots or any(not isinstance(value, int) or value < 0 for value in slots.values()):
        raise WorldBuildError("Stage 3B slots must contain exactly the six shared deterministic IDs")
    if slots["matrix"] != 1:
        raise WorldBuildError("Stage 3B matrix slot must remain verified controlled slot 1")

    matrix = fixture.get("world", {}).get("matrix", {})
    if matrix.get("width") != 2 or matrix.get("height") != 2:
        raise WorldBuildError("Stage 3B requires exactly one 2x2 matrix")
    try:
        matrix_name = matrix.get("name", "").encode("ascii")
    except UnicodeEncodeError as exc:
        raise WorldBuildError("Stage 3B matrix name must be ASCII") from exc
    expected_name = "stage3c-2x2" if is_stage3c else "stage3b-2x2"
    if matrix.get("name") != expected_name or len(matrix_name) > 16:
        raise WorldBuildError(f"multi-map matrix name must be the bounded ASCII identifier {expected_name}")
    cells = matrix.get("cells")
    if cells != list(STAGE3B_CELL_ORDER):
        raise WorldBuildError("Stage 3B cells must be the row-major order nw, ne, sw, se")
    if len(cells) != matrix["width"] * matrix["height"]:
        raise WorldBuildError("Stage 3B matrix dimensions disagree with its cell count")
    if matrix.get("altitudes") != [0, 0, 0, 0]:
        raise WorldBuildError("Stage 3B uses an explicit flat, row-major four-byte altitude grid")
    if matrix.get("external_boundaries") != "blocked":
        raise WorldBuildError("Stage 3B exterior matrix boundaries must use valid blocked collision")

    maps = fixture.get("maps")
    if not isinstance(maps, dict) or set(maps) != set(STAGE3B_CELL_ORDER):
        raise WorldBuildError("Stage 3B maps must define exactly nw, ne, sw, and se")
    header_ids: list[int] = []
    member_ids: list[int] = []
    identity_tiles: set[tuple[int, int]] = set()
    for index, name in enumerate(STAGE3B_CELL_ORDER):
        map_spec = maps[name]
        if set(map_spec) != {"cell", "map_header", "map_member", "edge_openings", "identity_blocked_tile"}:
            raise WorldBuildError(f"Stage 3B map {name} has unsupported or missing fields")
        expected_cell = {"row": index // 2, "column": index % 2}
        if map_spec["cell"] != expected_cell:
            raise WorldBuildError(f"Stage 3B map {name} has an inconsistent matrix cell")
        if map_spec["map_header"] != STAGE3B_CONTROLLED_HEADERS[name]:
            raise WorldBuildError(f"Stage 3B map {name} must use its verified controlled header")
        if map_spec["map_member"] != STAGE3B_CONTROLLED_MEMBERS[name]:
            raise WorldBuildError(f"Stage 3B map {name} must use its verified unreferenced member")
        header_ids.append(map_spec["map_header"])
        member_ids.append(map_spec["map_member"])
        tile = map_spec["identity_blocked_tile"]
        if not (
            isinstance(tile, list) and len(tile) == 2
            and all(isinstance(value, int) and 1 <= value < MAP_TILES - 1 for value in tile)
        ):
            raise WorldBuildError(f"Stage 3B map {name} identity tile must be an interior coordinate")
        if tuple(tile) in identity_tiles:
            raise WorldBuildError("Stage 3B map identity tiles must be distinct")
        identity_tiles.add(tuple(tile))
        openings = map_spec["edge_openings"]
        if not isinstance(openings, dict) or any(edge not in CARDINAL_DELTAS for edge in openings):
            raise WorldBuildError(f"Stage 3B map {name} contains an invalid edge opening")
        for edge, coordinates in openings.items():
            if not (
                isinstance(coordinates, list) and coordinates
                and len(set(coordinates)) == len(coordinates)
                and all(isinstance(value, int) and 1 <= value < MAP_TILES - 1 for value in coordinates)
            ):
                raise WorldBuildError(f"Stage 3B map {name} edge {edge} has malformed openings")
            row = expected_cell["row"] + CARDINAL_DELTAS[edge][0]
            column = expected_cell["column"] + CARDINAL_DELTAS[edge][1]
            if not (0 <= row < 2 and 0 <= column < 2):
                raise WorldBuildError(f"Stage 3B map {name} cannot open exterior edge {edge}")
            neighbor = STAGE3B_CELL_ORDER[row * 2 + column]
            reciprocal = maps[neighbor].get("edge_openings", {}).get(OPPOSITE_EDGE[edge])
            if reciprocal != coordinates:
                raise WorldBuildError(f"Stage 3B edge {name}:{edge} is not reciprocal with {neighbor}")

    if len(set(header_ids)) != 4 or len(set(member_ids)) != 4:
        raise WorldBuildError("Stage 3B headers and map-member assignments must each be unique")
    expected_start = {"map": "nw", "local_x": 16, "local_z": 16, "direction": 3}
    if fixture.get("player_start") != expected_start:
        raise WorldBuildError("Stage 3B controlled start must use the bounded NW profile")
    if fixture.get("warps") != [] or "npc" in fixture:
        raise WorldBuildError("Stage 3B native transitions forbid event warps and NPC content")
    terrain = fixture.get("terrain", {})
    for key in ("permission_type", "walkable_collision", "blocked_collision"):
        if not isinstance(terrain.get(key), int) or not 0 <= terrain[key] <= 255:
            raise WorldBuildError(f"Stage 3B terrain {key} must be a byte")


def _dict_offsets(data: bytes, base: int, entry_size: int = 4) -> list[int]:
    if base + 8 > len(data):
        raise WorldBuildError("truncated Nitro dictionary")
    revision, count, size, _padding, entry_offset = struct.unpack_from("<BBHHH", data, base)
    if revision not in (0, 1) or count == 0 or base + size > len(data):
        raise WorldBuildError("unsupported Nitro dictionary header")
    values_base = base + entry_offset + 4
    if values_base + count * entry_size > base + size:
        raise WorldBuildError("Nitro dictionary entries exceed dictionary size")
    return [struct.unpack_from("<I", data, values_base + i * entry_size)[0] for i in range(count)]


def _gx_command(opcode: int, *params: int) -> bytes:
    return bytes((opcode, 0, 0, 0)) + b"".join(struct.pack("<I", value & 0xFFFFFFFF) for value in params)


def _fx16(value: float) -> int:
    raw = round(value * 4096)
    if not -0x8000 <= raw <= 0x7FFF:
        raise WorldBuildError(f"vertex coordinate {value} does not fit fx16")
    return raw & 0xFFFF


def _texcoord(s: int, t: int) -> int:
    return ((t * 16) & 0xFFFF) << 16 | ((s * 16) & 0xFFFF)


def _vtx16(x: float, y: float, z: float) -> tuple[int, int]:
    return _fx16(x) | (_fx16(y) << 16), _fx16(z)


def build_flat_display_list() -> bytes:
    normal_up = 0x1FF << 10
    vertices = [
        (-4.0, 0.25, -4.0, 0, 0),
        (-4.0, 0.25, 4.0, 0, 16),
        (4.0, 0.25, 4.0, 16, 16),
        (4.0, 0.25, -4.0, 16, 0),
    ]
    output = bytearray()
    output += _gx_command(0x40, 1)  # BEGIN, quadrilaterals
    output += _gx_command(0x21, normal_up)
    for x, y, z, s, t in vertices:
        output += _gx_command(0x22, _texcoord(s, t))
        output += _gx_command(0x23, *_vtx16(x, y, z))
    output += _gx_command(0x41)  # END
    return bytes(output)


def _append_quad(
    output: bytearray,
    vertices: list[tuple[float, float, float, int, int]],
    normal: int,
) -> None:
    output += _gx_command(0x21, normal)
    for x, y, z, s, t in vertices:
        output += _gx_command(0x22, _texcoord(s, t))
        output += _gx_command(0x23, *_vtx16(x, y, z))


def build_height_display_list() -> bytes:
    """Emit the seven static quads used by the bounded Stage 3A fixture."""
    normal_up = 0x1FF << 10
    normal_side = 0x201
    quads = [
        # Lower surface and two-tile-wide rising connection.
        ([(-4.0, 0.25, -4.0, 0, 0), (-4.0, 0.25, 4.0, 0, 16),
          (0.0, 0.25, 4.0, 8, 16), (0.0, 0.25, -4.0, 8, 0)], normal_up),
        ([(0.0, 0.25, -0.5, 0, 0), (0.0, 0.25, 0.5, 0, 2),
          (0.5, 0.75, 0.5, 2, 2), (0.5, 0.75, -0.5, 2, 0)], normal_up),
        # The raised surface begins at X=16 outside the ramp corridor. Inside
        # the corridor it begins at X=18, where the ramp reaches height 2.
        ([(0.0, 0.75, -4.0, 0, 0), (0.0, 0.75, -0.5, 0, 7),
          (4.0, 0.75, -0.5, 8, 7), (4.0, 0.75, -4.0, 8, 0)], normal_up),
        ([(0.5, 0.75, -0.5, 0, 0), (0.5, 0.75, 0.5, 0, 2),
          (4.0, 0.75, 0.5, 7, 2), (4.0, 0.75, -0.5, 7, 0)], normal_up),
        ([(0.0, 0.75, 0.5, 0, 0), (0.0, 0.75, 4.0, 0, 7),
          (4.0, 0.75, 4.0, 8, 7), (4.0, 0.75, 0.5, 8, 0)], normal_up),
        # The two wall spans make the impassable raised edge visible while
        # leaving only the transition corridor open.
        ([(0.0, 0.25, -4.0, 0, 0), (0.0, 0.75, -4.0, 0, 2),
          (0.0, 0.75, -0.5, 7, 2), (0.0, 0.25, -0.5, 7, 0)], normal_side),
        ([(0.0, 0.25, 0.5, 0, 0), (0.0, 0.75, 0.5, 0, 2),
          (0.0, 0.75, 4.0, 7, 2), (0.0, 0.25, 4.0, 7, 0)], normal_side),
    ]
    output = bytearray(_gx_command(0x40, 1))
    for vertices, normal in quads:
        _append_quad(output, vertices, normal)
    output += _gx_command(0x41)
    return bytes(output)


def build_degenerate_display_list() -> bytes:
    """Return a structurally complete but invisible quad for unused shapes."""
    output = bytearray(_gx_command(0x40, 1))
    for _ in range(4):
        output += _gx_command(0x23, *_vtx16(0, 0, 0))
    output += _gx_command(0x41)
    return bytes(output)


def transform_template_nsbmd(
    nsbmd: bytes,
    target_shape: int,
    display_list: bytes | None = None,
    target_quads: int = 1,
) -> tuple[bytes, dict[str, Any]]:
    replacement = build_flat_display_list() if display_list is None else display_list
    model, report = transform_template_nsbmd_multi(
        nsbmd, {target_shape: replacement}, {target_shape: target_quads},
    )
    report.update({
        "target_shape": target_shape,
        "display_list_bytes": len(replacement),
        "target_quads": target_quads,
    })
    return model, report


def transform_template_nsbmd_multi(
    nsbmd: bytes,
    display_lists: dict[int, bytes],
    quad_counts: dict[int, int],
    triangle_counts: dict[int, int] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Replace several hash-locked template shapes without relocating data."""
    data = bytearray(nsbmd)
    if data[:4] != b"BMD0" or len(data) < 20:
        raise WorldBuildError("template model is not a BMD0 file")
    byte_order, version, file_size, header_size, section_count = struct.unpack_from("<HHIHH", data, 4)
    if byte_order != 0xFEFF or version != 2 or file_size != len(data) or section_count < 1:
        raise WorldBuildError("unsupported BMD0 header")
    mdl_base = struct.unpack_from("<I", data, header_size)[0]
    if data[mdl_base:mdl_base + 4] != b"MDL0":
        raise WorldBuildError("BMD0 does not contain MDL0 as its first section")
    model_offsets = _dict_offsets(data, mdl_base + 8)
    if len(model_offsets) != 1:
        raise WorldBuildError("Stage 2 template must contain exactly one model")
    model_base = mdl_base + model_offsets[0]
    model_size, _ofs_sbc, _ofs_mat, ofs_shape, _ofs_evp = struct.unpack_from("<5I", data, model_base)
    if model_base + model_size > len(data):
        raise WorldBuildError("model extends past BMD0 end")
    num_nodes, num_materials, num_shapes = struct.unpack_from("<xxxBBB", data, model_base + 20)
    if num_nodes != 1 or num_shapes < 1:
        raise WorldBuildError("Stage 2 template requires one node and at least one shape")
    shape_set = model_base + ofs_shape
    shape_offsets = _dict_offsets(data, shape_set)
    if len(shape_offsets) != num_shapes:
        raise WorldBuildError("shape dictionary count disagrees with model info")
    triangle_counts = triangle_counts or {shape: 0 for shape in display_lists}
    if set(display_lists) != set(quad_counts) or set(display_lists) != set(triangle_counts) or not display_lists:
        raise WorldBuildError("NSBMD replacement display-list and primitive assignments disagree")
    if any(not 0 <= shape < num_shapes for shape in display_lists):
        raise WorldBuildError("one or more replacement shapes are outside the template model")
    capacities: list[int] = []
    regions: list[tuple[int, int]] = []
    for relative in shape_offsets:
        shape_base = shape_set + relative
        item_tag, header_len, flags, dl_offset, dl_size = struct.unpack_from("<HHIII", data, shape_base)
        if item_tag != 0 or header_len != 16 or flags & ~0xF:
            raise WorldBuildError("unsupported template shape record")
        dl_start = shape_base + dl_offset
        if dl_start + dl_size > model_base + model_size:
            raise WorldBuildError("shape display list extends past model")
        capacities.append(dl_size)
        regions.append((dl_start, dl_size))
    for shape, display_list in sorted(display_lists.items()):
        if len(display_list) > capacities[shape]:
            raise GeometryError(
                "display_list_overflow",
                f"shape {shape} needs {len(display_list)} bytes but capacity is {capacities[shape]}",
                shape=shape, required_bytes=len(display_list), capacity_bytes=capacities[shape],
            )

    degenerate = build_degenerate_display_list()
    for index, (dl_start, dl_size) in enumerate(regions):
        replacement = display_lists.get(index, degenerate)
        if len(replacement) > dl_size:
            raise WorldBuildError(f"template shape {index} is too small for a valid replacement")
        data[dl_start:dl_start + dl_size] = replacement + bytes(dl_size - len(replacement))
    total_triangles = sum(triangle_counts.values())
    total_quads = num_shapes - len(display_lists) + sum(quad_counts.values())
    total_vertices = 3 * total_triangles + 4 * total_quads
    total_polygons = total_triangles + total_quads
    struct.pack_into(
        "<4H", data, model_base + 36,
        total_vertices, total_polygons, total_triangles, total_quads,
    )
    assignments = {
        str(shape): {
            "display_list_bytes": len(display_lists[shape]),
            "capacity_bytes": capacities[shape],
            "utilization_percent": round(len(display_lists[shape]) * 100 / capacities[shape], 3),
            "triangle_count": triangle_counts[shape],
            "quad_count": quad_counts[shape],
        }
        for shape in sorted(display_lists)
    }
    return bytes(data), {
        "models": 1,
        "nodes": num_nodes,
        "materials": num_materials,
        "shapes": num_shapes,
        "shape_capacities": capacities,
        "shape_regions": [
            {"shape": index, "offset": start, "capacity_bytes": size}
            for index, (start, size) in enumerate(regions)
        ],
        "model_primitive_counts": {
            "vertices": total_vertices, "polygons": total_polygons,
            "triangles": total_triangles, "quads": total_quads,
        },
        "assignments": assignments,
    }


def split_hgss_map_member(member: bytes) -> dict[str, bytes]:
    if len(member) < 16:
        raise WorldBuildError("truncated HGSS map member")
    per_len, bld_len, model_len, bdhc_len = struct.unpack_from("<4I", member)
    bgs_len = len(member) - 16 - per_len - bld_len - model_len - bdhc_len
    if bgs_len < 0:
        raise WorldBuildError("HGSS map section lengths exceed member size")
    if bgs_len < 4:
        raise WorldBuildError("HGSS map member is missing its four-byte BGS header")
    # Runtime source reads PER at fixed member offset 0x14. HGSS stores the
    # BGS signature/length at 0x10, PER and BLD next, then the BGS sound-plate
    # payload immediately before NSBMD. GUI editors commonly present BGS as a
    # contiguous logical file, which hides this on-ROM split.
    offset = 16
    bgs_header = member[offset:offset + 4]
    offset += 4
    per = member[offset:offset + per_len]
    offset += per_len
    bld = member[offset:offset + bld_len]
    offset += bld_len
    bgs_payload = member[offset:offset + bgs_len - 4]
    offset += bgs_len - 4
    nsbmd = member[offset:offset + model_len]
    offset += model_len
    bdhc = member[offset:offset + bdhc_len]
    return {"bgs": bgs_header + bgs_payload, "per": per, "bld": bld, "nsbmd": nsbmd, "bdhc": bdhc}


def _build_bgs(fixture: dict[str, Any], template_bgs: bytes) -> bytes:
    if len(template_bgs) < 4:
        raise WorldBuildError("template BGS section is missing its four-byte header")
    if fixture["schema_version"] not in (3, 6, 7, 8, 9, 10, 11, 12):
        return template_bgs
    # The BGS header's second u16 is its payload length.  The Stage 2
    # physical invariant places PER immediately after this four-byte header
    # at member offset 0x14, so Stage 3B declares an empty BGS payload.
    return template_bgs[:2] + b"\0\0"


def _stage3b_open_tiles(map_spec: dict[str, Any]) -> set[tuple[int, int]]:
    tiles: set[tuple[int, int]] = set()
    for edge, coordinates in map_spec["edge_openings"].items():
        for coordinate in coordinates:
            if edge == "north":
                tiles.add((coordinate, 0))
            elif edge == "east":
                tiles.add((31, coordinate))
            elif edge == "south":
                tiles.add((coordinate, 31))
            else:
                tiles.add((0, coordinate))
    return tiles


def build_per(fixture: dict[str, Any], map_name: str | None = None) -> bytes:
    if fixture["schema_version"] == 5:
        return compile_geometry(fixture["geometry"])["per"]
    terrain = fixture["terrain"]
    output = bytearray()
    if fixture["schema_version"] in (3, 6, 7):
        if map_name not in fixture["maps"]:
            raise WorldBuildError("multi-map PER generation requires a declared map name")
        map_spec = fixture["maps"][map_name]
        blocked = {tuple(map_spec["identity_blocked_tile"])}
        open_border = _stage3b_open_tiles(map_spec)
    else:
        blocked = {tuple(tile) for tile in terrain.get("blocked_tiles", [])}
        open_border = set()
    if fixture["schema_version"] in (8, 9, 10, 11, 12):
        compiled_assets = compile_placements(
            PROJECT_ROOT / fixture["asset_catalog"], fixture["assets"], PROJECT_ROOT,
        )
        blocked.update(compiled_assets["blocked_tiles"])
    if fixture["schema_version"] == 7:
        warps = {
            (warp["local_x"], warp["local_z"])
            for warp in fixture.get("warps", []) if warp["map"] == map_name
        }
    else:
        warps = {(warp["x"], warp["z"]) for warp in fixture.get("warps", [])}
    # HGSS PER is row-major (Z, then X), with the permission byte immediately
    # followed by the walkability byte. PDSMS names these row/column loops
    # j/k; DSPRE stores them in its first/second rectangular-array indices.
    for z in range(32):
        for x in range(32):
            is_border = (x in (0, 31) or z in (0, 31)) and (x, z) not in open_border
            if fixture["schema_version"] not in (3, 6, 7):
                is_border = terrain["block_border"] and is_border
            collision = terrain["blocked_collision"] if is_border or (x, z) in blocked else terrain["walkable_collision"]
            permission = terrain.get("warp_permission_type", terrain["permission_type"]) if (x, z) in warps else terrain["permission_type"]
            output.extend((permission, collision))
    return bytes(output)


def build_bdhc(fixture: dict[str, Any]) -> bytes:
    if fixture["schema_version"] == 5:
        return compile_geometry(fixture["geometry"])["bdhc"]
    if fixture["schema_version"] == 2:
        # Coordinates are centered map tiles. Heights/constants are Q16.16;
        # PDSMS' HGSS loader negates the serialized plane constant. The access
        # lists describe the plates which overlap each Z stripe.
        points = [
            (-16, -16), (0, 16),  # lower
            (0, -2), (2, 2),      # ramp corridor
            (0, -16), (16, -2),   # raised north of corridor
            (2, -2), (16, 2),     # raised in corridor, after ramp
            (0, 2), (16, 16),     # raised south of corridor
        ]
        normals = [(0, 4096, 0), (-2896, 2896, 0)]
        constants = [0, -2 * 65536]
        plates = [
            (0, 1, 0, 0), (2, 3, 1, 0),
            (4, 5, 0, 1), (6, 7, 0, 1), (8, 9, 0, 1),
        ]
        stripes = [
            (-2, (0, 1, 2, 3)),
            (2, (0, 1, 3, 4)),
            (16, (0, 4)),
        ]
        output = bytearray(b"BDHC")
        output += struct.pack(
            "<6H", len(points), len(normals), len(constants), len(plates),
            len(stripes), sum(len(indices) for _, indices in stripes),
        )
        for x, z in points:
            output += struct.pack("<4h", 0, x, 0, z)
        for normal in normals:
            output += struct.pack("<3i", *normal)
        for constant in constants:
            output += struct.pack("<i", constant)
        for plate in plates:
            output += struct.pack("<4H", *plate)
        access_offset = 0
        for stripe_end, indices in stripes:
            output += struct.pack("<4H", 0, stripe_end & 0xFFFF, len(indices), access_offset)
            access_offset += len(indices)
        for _, indices in stripes:
            output += struct.pack(f"<{len(indices)}H", *indices)
        return bytes(output)

    extent = fixture["model"]["half_extent"]
    height = fixture["terrain"].get("height", 0)
    if height != 0:
        raise WorldBuildError("Stage 2 BDHC subset supports only a zero-height plane")
    output = bytearray(b"BDHC")
    output += struct.pack("<6H", 2, 1, 1, 1, 1, 1)
    output += struct.pack("<4h", 0, -extent, 0, -extent)
    output += struct.pack("<4h", 0, extent, 0, extent)
    output += struct.pack("<3i", 0, 4096, 0)
    output += struct.pack("<i", 0)
    output += struct.pack("<4H", 0, 1, 0, 0)
    output += struct.pack("<4H", 0, extent, 1, 0)
    output += struct.pack("<H", 0)
    return bytes(output)


def build_map_member(
    fixture: dict[str, Any],
    template_member: bytes,
    map_name: str | None = None,
) -> tuple[bytes, dict[str, Any]]:
    template = split_hgss_map_member(template_member)
    if fixture["schema_version"] == 5:
        geometry = compile_geometry(fixture["geometry"])
        quad_counts = {
            MATERIAL_BINDINGS[material]["shape"]: geometry["report"]["materials"][material]["quad_count"]
            for material in MATERIAL_ORDER
        }
        model, model_info = transform_template_nsbmd_multi(
            template["nsbmd"], geometry["display_lists"], quad_counts,
        )
        model_info["geometry"] = geometry["report"]
        model_info["material_bindings"] = MATERIAL_BINDINGS
    elif fixture["schema_version"] in (8, 9, 10, 11, 12):
        assets = compile_placements(
            PROJECT_ROOT / fixture["asset_catalog"], fixture["assets"], PROJECT_ROOT,
        )
        display_lists = {5: build_flat_display_list(), **assets["display_lists"]}
        quad_counts = {5: 1, **assets["quad_counts"]}
        triangle_counts = {5: 0, **assets["triangle_counts"]}
        model, model_info = transform_template_nsbmd_multi(
            template["nsbmd"], display_lists, quad_counts, triangle_counts,
        )
        model_info["asset_geometry"] = assets["report"]
        model_info["material_bindings"] = {
            "ground": MATERIAL_BINDINGS["ground"],
            **ASSET_MATERIAL_BINDINGS,
        }
    elif fixture["schema_version"] == 2:
        model, model_info = transform_template_nsbmd(
            template["nsbmd"], fixture["model"]["template_shape"],
            build_height_display_list(), target_quads=7,
        )
    else:
        model, model_info = transform_template_nsbmd(
            template["nsbmd"], fixture["model"]["template_shape"]
        )
        model_info["flat_display_list_bytes"] = model_info["display_list_bytes"]
    per = build_per(fixture, map_name)
    bld = b""
    bdhc = build_bdhc(fixture)
    bgs = _build_bgs(fixture, template["bgs"])
    header = struct.pack("<4I", len(per), len(bld), len(model), len(bdhc))
    member = header + bgs[:4] + per + bld + bgs[4:] + model + bdhc
    return member, {"bgs_bytes_reused": len(bgs), **model_info}


def build_matrix(fixture: dict[str, Any]) -> bytes:
    if fixture["schema_version"] in (3, 6, 7):
        matrix = fixture["world"]["matrix"]
        name = matrix["name"].encode("ascii")
        cells = [fixture["maps"][cell] for cell in matrix["cells"]]
        headers = [cell["map_header"] for cell in cells]
        members = [cell["map_member"] for cell in cells]
        output = bytearray((matrix["width"], matrix["height"], 1, 1, len(name)))
        output += name
        output += struct.pack(f"<{len(headers)}H", *headers)
        output += bytes(matrix["altitudes"])
        output += struct.pack(f"<{len(members)}H", *members)
        return bytes(output)
    if fixture["schema_version"] in (5, 8, 9, 10, 11, 12):
        name = fixture["world"]["matrix"]["name"].encode("ascii")
    else:
        name = b"stage2-proof" if fixture["schema_version"] == 1 else b"stage3a-height"
    slots = fixture["slots"]
    return bytes((1, 1, 1, 1, len(name))) + name + struct.pack("<H", slots["map_header"]) + b"\0" + struct.pack("<H", slots["map_member"])


def build_event(fixture: dict[str, Any], map_name: str | None = None) -> bytes:
    if fixture["schema_version"] in (6, 7):
        if map_name not in fixture["maps"]:
            raise WorldBuildError("Stage 3E1 event generation requires a declared map name")
        spec = fixture["maps"][map_name]
        npc = spec["npc"]
        x = spec["cell"]["column"] * MAP_TILES + npc["local_x"]
        z = spec["cell"]["row"] * MAP_TILES + npc["local_z"]
        output = bytearray(struct.pack("<I", 0))
        output += struct.pack("<I", 1)
        output += struct.pack(
            "<6Hh3HhhHHi",
            npc["local_id"], npc["graphics_id"], npc["movement_type"], 0, 0,
            npc["script_index"], npc["direction"], 0, 0, 0, 0, 0, x, z, 0,
        )
        map_warps = [warp for warp in fixture.get("warps", []) if warp["map"] == map_name]
        output += struct.pack("<I", len(map_warps))
        for warp in map_warps:
            x = spec["cell"]["column"] * MAP_TILES + warp["local_x"]
            z = spec["cell"]["row"] * MAP_TILES + warp["local_z"]
            output += struct.pack("<4HI", x, z, warp["destination_header"], warp["destination_warp"], 0)
        output += struct.pack("<I", 0)
        return bytes(output)
    if fixture["schema_version"] in (2, 3, 5, 8, 9, 10, 11, 12):
        return struct.pack("<4I", 0, 0, 0, 0)
    npc = fixture["npc"]
    output = bytearray(struct.pack("<I", 0))
    output += struct.pack("<I", 1)
    output += struct.pack(
        "<6Hh3HhhHHi",
        npc["local_id"], npc["graphics_id"], npc["movement_type"], 0, 0,
        npc["script_index"], npc["direction"], 0, 0, 0, 0, 0, npc["x"], npc["z"], 0,
    )
    output += struct.pack("<I", len(fixture["warps"]))
    for warp in fixture["warps"]:
        output += struct.pack("<4HI", warp["x"], warp["z"], warp["destination_header"], warp["destination_warp"], 0)
    output += struct.pack("<I", 0)
    return bytes(output)


def _map_header_id(fixture: dict[str, Any], map_name: str | None) -> int:
    if fixture["schema_version"] in (3, 6, 7):
        if map_name not in fixture["maps"]:
            raise WorldBuildError("Stage 3B map-header generation requires a declared map name")
        return fixture["maps"][map_name]["map_header"]
    return fixture["slots"]["map_header"]


def build_map_header(
    fixture: dict[str, Any],
    arm9: bytes,
    map_name: str | None = None,
) -> bytes:
    slots = fixture["slots"]
    if fixture["schema_version"] == 7:
        if map_name not in fixture["maps"]:
            raise WorldBuildError("Stage 3E2 header generation requires a declared map name")
        banks = fixture["maps"][map_name]
        profile = fixture["header_profile"]
        output = bytearray(MAP_HEADER_SIZE)
        output[0] = profile["wild_encounter_bank"]
        output[1] = fixture["model"]["area_data"]
        struct.pack_into("<H", output, 2, profile["move_model_bank"] | (profile["world_map_x"] << 4) | (profile["world_map_y"] << 10))
        struct.pack_into("<7H", output, 4, fixture["slots"]["matrix"], banks["script"], banks["script_header"], banks["text"], profile["day_music"], profile["night_music"], banks["event"])
        struct.pack_into("<H", output, 18, profile["map_section"] | (profile["area_icon"] << 8) | (profile["mom_call_intro"] << 12))
        struct.pack_into("<I", output, 20, _encode_header_flags(profile))
        return bytes(output)
    template_id = fixture["header_template"]
    template_offset = HGSS_US_HEADER_OFFSET + template_id * MAP_HEADER_SIZE
    if template_offset + MAP_HEADER_SIZE > len(arm9):
        raise WorldBuildError("US HG map-header table is outside arm9.bin")
    output = bytearray(arm9[template_offset:template_offset + MAP_HEADER_SIZE])
    output[0] = 0xFF
    output[1] = fixture["model"]["area_data"]
    if fixture["schema_version"] == 6:
        if map_name not in fixture["maps"]:
            raise WorldBuildError("Stage 3E1 header generation requires a declared map name")
        banks = fixture["maps"][map_name]
        matrix_id = slots["matrix"]
    else:
        banks = slots
        matrix_id = slots["matrix"]
    struct.pack_into(
        "<7H", output, 4, matrix_id, banks["script"], banks["script_header"], banks["text"],
        struct.unpack_from("<H", output, 12)[0], struct.unpack_from("<H", output, 14)[0], banks["event"],
    )
    if fixture["schema_version"] in (10, 11, 12):
        flags = struct.unpack_from("<I", output, 20)[0]
        flags = (flags & ~(0x3F << 12)) | (4 << 12)
        struct.pack_into("<I", output, 20, flags)
    return bytes(output)


def _encode_header_flags(profile: object) -> int:
    required = {
        "wild_encounter_bank", "move_model_bank", "world_map_x", "world_map_y", "day_music", "night_music",
        "map_section", "area_icon", "mom_call_intro", "region", "weather", "map_type", "camera",
        "follow_mode", "battle_bg", "bike_allowed", "running_allowed", "escape_rope_allowed",
        "fly_allowed", "outgoing_calls", "incoming_calls", "radio_signal",
    }
    if not isinstance(profile, dict) or set(profile) != required:
        raise WorldBuildError("Stage 3E2 header profile has unsupported or missing fields")
    widths = {
        "wild_encounter_bank": 8, "move_model_bank": 4, "world_map_x": 6, "world_map_y": 6,
        "day_music": 16, "night_music": 16, "map_section": 8, "area_icon": 4, "mom_call_intro": 4,
        "region": 1, "weather": 7, "map_type": 4, "camera": 6, "follow_mode": 2, "battle_bg": 5,
    }
    for field, width in widths.items():
        value = profile[field]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < (1 << width):
            raise WorldBuildError(f"Stage 3E2 header field {field} exceeds its {width}-bit width")
    boolean_fields = (
        "bike_allowed", "running_allowed", "escape_rope_allowed", "fly_allowed",
        "outgoing_calls", "incoming_calls", "radio_signal",
    )
    if any(not isinstance(profile[field], bool) for field in boolean_fields):
        raise WorldBuildError("Stage 3E2 header capability fields must be booleans")
    value = profile["region"] | (profile["weather"] << 1) | (profile["map_type"] << 8)
    value |= profile["camera"] << 12 | profile["follow_mode"] << 18 | profile["battle_bg"] << 20
    for bit, field in enumerate(boolean_fields, 25):
        value |= int(profile[field]) << bit
    return value


def _write_script_source(
    fixture: dict[str, Any], source: Path, output: Path, map_name: str | None = None,
) -> None:
    if fixture["schema_version"] in (6, 7):
        if map_name not in fixture["maps"]:
            raise WorldBuildError("Stage 3E1 script generation requires a declared map name")
        npc = fixture["maps"][map_name]["npc"]
        save_command = (
            "    save_game_normal 0x800C\n"
            if fixture["schema_version"] == 7 and map_name == "east"
            else ""
        )
        warp_command = (
            f"    warp {fixture['maps']['west']['map_header']}, 0xFFFF, 16, 16, 3\n"
            if fixture["schema_version"] == 7 and map_name == "east"
            else ""
        )
        source.write_text(
            ".nds\n.thumb\n\n"
            '.include "armips/include/scriptmacros.s"\n'
            '.include "armips/include/soundeffects.s"\n\n'
            f'.create "{output.as_posix()}", 0\n\n'
            f"scrdef {fixture['artifact_namespace']}_{map_name}_npc\n"
            "scrdef_end\n\n"
            f"{fixture['artifact_namespace']}_{map_name}_npc:\n"
            "    play_se SEQ_SE_DP_SELECT\n"
            "    lockall\n"
            "    faceplayer\n"
            f"    setvar {npc['marker_var']}, {npc['marker_value']}\n"
            "    npc_msg 0\n"
            "    wait_button_or_walk_away\n"
            "    closemsg\n"
            f"{save_command}"
            "    releaseall\n"
            f"{warp_command}"
            "    end\n\n.close\n",
            encoding="utf-8",
        )
        return
    if fixture["schema_version"] in (2, 3, 5, 8, 9, 10, 11, 12):
        if fixture["schema_version"] == 5:
            label = "stage3d_geometry_noop"
        elif fixture["schema_version"] in (8, 9, 10, 11, 12):
            label = f"{fixture['artifact_namespace']}_asset_noop"
        elif fixture["schema_version"] == 2:
            label = "stage3a_height_noop"
        elif fixture.get("artifact_namespace") == "stage3c":
            label = "stage3c_registry_noop"
        else:
            label = "stage3b_multimap_noop"
        source.write_text(
            ".nds\n.thumb\n\n"
            '.include "armips/include/scriptmacros.s"\n\n'
            f'.create "{output.as_posix()}", 0\n\n'
            f"scrdef {label}\n"
            "scrdef_end\n\n"
            f"{label}:\n"
            "    end\n\n.close\n",
            encoding="utf-8",
        )
        return
    marker_var = fixture["test_marker_var"]
    marker_value = fixture["test_marker_value"]
    source.write_text(
        ".nds\n.thumb\n\n"
        ".include \"armips/include/scriptmacros.s\"\n"
        ".include \"armips/include/soundeffects.s\"\n\n"
        f'.create "{output.as_posix()}", 0\n\n'
        "scrdef stage2_proof_npc\n"
        "scrdef_end\n\n"
        "stage2_proof_npc:\n"
        "    play_se SEQ_SE_DP_SELECT\n"
        "    lockall\n"
        "    faceplayer\n"
        f"    setvar {marker_var}, {marker_value}\n"
        "    npc_msg 0\n"
        "    wait_button_or_walk_away\n"
        "    closemsg\n"
        "    releaseall\n"
        "    end\n\n.close\n",
        encoding="utf-8",
    )


def _write_start_script_source(fixture: dict[str, Any], source: Path, output: Path) -> None:
    start = fixture["player_start"]
    header = _map_header_id(fixture, start.get("map"))
    if fixture["schema_version"] in (3, 6, 7):
        map_spec = fixture["maps"][start["map"]]
        x = map_spec["cell"]["column"] * MAP_TILES + start["local_x"]
        z = map_spec["cell"]["row"] * MAP_TILES + start["local_z"]
    else:
        x, z = start["x"], start["z"]
    source.write_text(
        ".nds\n.thumb\n\n"
        '.include "armips/include/scriptmacros.s"\n\n'
        f'.create "{output.as_posix()}", 0\n\n'
        "scrdef stage2_start\n"
        "scrdef_end\n\n"
        "stage2_start:\n"
        f"    warp {header}, 0xFFFF, {x}, {z}, {start['direction']}\n"
        "    end\n\n.close\n",
        encoding="utf-8",
    )


def _run_checked(command: list[str], root: Path) -> None:
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise WorldBuildError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout[-2000:]}")


def _narc_btaf_count(data: bytes) -> int:
    offset = data.find(b"BTAF")
    if offset < 0 or offset + 10 > len(data):
        raise WorldBuildError("rebuilt archive is missing a complete BTAF section")
    return struct.unpack_from("<H", data, offset + 8)[0]


def _replace_narc(source: Path, member_id: int, member: bytes, destination: Path) -> dict[str, Any]:
    return _replace_narc_members(source, {member_id: member}, destination)


def _replace_narc_members(
    source: Path, replacements: dict[int, bytes], destination: Path,
) -> dict[str, Any]:
    archive = NARC.fromFile(str(source))
    pristine_files = list(archive.files)
    for member_id, member in sorted(replacements.items()):
        if member_id < len(archive.files):
            archive.files[member_id] = member
        elif member_id == len(archive.files):
            archive.files.append(member)
        else:
            raise WorldBuildError(
                f"member {member_id} would create an unsupported NARC gap after {len(archive.files) - 1}"
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive.saveToFile(str(destination))
    rebuilt = NARC.fromFile(str(destination))
    btaf_count = _narc_btaf_count(destination.read_bytes())
    if len(rebuilt.files) != len(archive.files) or btaf_count != len(rebuilt.files):
        raise WorldBuildError("rebuilt NARC member count disagrees with its BTAF header")
    changed_retail = [
        index for index, (before, after) in enumerate(zip(pristine_files, rebuilt.files))
        if before != after
    ]
    expected_changed_retail = sorted(
        index for index, member in replacements.items()
        if index < len(pristine_files) and pristine_files[index] != member
    )
    if changed_retail != expected_changed_retail:
        raise WorldBuildError("rebuilt NARC changed an undeclared pristine member")
    for member_id, expected in replacements.items():
        if rebuilt.files[member_id] != expected:
            raise WorldBuildError(f"rebuilt NARC member {member_id} does not match generated bytes")
    return {
        "pristine_count": len(pristine_files),
        "rebuilt_count": len(rebuilt.files),
        "btaf_count": btaf_count,
        "replacement_ids": sorted(expected_changed_retail),
        "appended_ids": sorted(index for index in replacements if index >= len(pristine_files)),
        "members": {
            str(member_id): {"bytes": len(member), "sha256": sha256_bytes(member)}
            for member_id, member in sorted(replacements.items())
        },
    }


def validate_stage3b_cross_references(
    fixture: dict[str, Any],
    matrix: bytes,
    map_headers: dict[str, bytes],
) -> None:
    """Reject generated Stage 3B artifacts whose derived references disagree."""
    if fixture["schema_version"] != 3:
        raise WorldBuildError("Stage 3B cross-reference validation requires schema 3")
    width, height, has_headers, has_altitudes, name_length = matrix[:5]
    expected_matrix = fixture["world"]["matrix"]
    if (width, height, has_headers, has_altitudes) != (2, 2, 1, 1):
        raise WorldBuildError("generated Stage 3B matrix header is inconsistent")
    offset = 5 + name_length
    header_grid = list(struct.unpack_from("<4H", matrix, offset))
    altitude_grid = list(matrix[offset + 8:offset + 12])
    member_grid = list(struct.unpack_from("<4H", matrix, offset + 12))
    expected_cells = [fixture["maps"][name] for name in expected_matrix["cells"]]
    if header_grid != [cell["map_header"] for cell in expected_cells]:
        raise WorldBuildError("generated Stage 3B header grid disagrees with its cells")
    if altitude_grid != expected_matrix["altitudes"]:
        raise WorldBuildError("generated Stage 3B altitude grid disagrees with its cells")
    if member_grid != [cell["map_member"] for cell in expected_cells]:
        raise WorldBuildError("generated Stage 3B member grid disagrees with its cells")
    if set(map_headers) != set(STAGE3B_CELL_ORDER):
        raise WorldBuildError("generated Stage 3B map-header set is incomplete")
    for name, header in map_headers.items():
        if len(header) != MAP_HEADER_SIZE:
            raise WorldBuildError(f"generated Stage 3B header {name} has the wrong size")
        if struct.unpack_from("<H", header, 4)[0] != fixture["slots"]["matrix"]:
            raise WorldBuildError(f"generated Stage 3B header {name} points at the wrong matrix")


def generate_world(
    fixture_path: Path = DEFAULT_FIXTURE,
    output_dir: Path = DEFAULT_OUTPUT,
    root: Path = PROJECT_ROOT,
    install: bool = False,
) -> dict[str, Any]:
    fixture = load_fixture(fixture_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    components = output_dir / "components"
    generated_root = output_dir / "root"
    components.mkdir(parents=True, exist_ok=True)
    slots = fixture["slots"]
    stage4c_texture_narc: bytes | None = None
    stage4c_texture_narc_report: dict[str, Any] | None = None
    stage4d_texture_narc: bytes | None = None
    stage4d_area_data_narc: bytes | None = None
    stage4d_texture_narc_report: dict[str, Any] | None = None
    stage4d_area_data_narc_report: dict[str, Any] | None = None

    for name, relative in NARC_PATHS.items():
        if not (root / relative).is_file():
            raise WorldBuildError(f"missing extracted prerequisite for {name}: {relative}")
    arm9_path = root / "base/arm9.bin"
    arm9 = arm9_path.read_bytes()

    rom_path = root / "rom.nds"
    if not rom_path.is_file():
        raise WorldBuildError("missing ignored user-supplied rom.nds template source")
    if fixture.get("artifact_namespace") in (
        "stage3c", "stage3d", "stage3e1", "stage3e2", "stage4b", "stage4c", "stage4d", "stage4e", "stage4f",
    ):
        registry_reference = fixture["registry_resolution"]["registry"]
        registry = load_registry(root / registry_reference)
        verify_rom_revision(registry, rom_path)
    rom = NintendoDSRom.fromFile(str(rom_path))
    template_archive = NARC(rom.getFileByName("a/0/6/5"))
    template = template_archive.files[fixture["model"]["template_map_member"]]
    actual_template_hash = sha256_bytes(template)
    if actual_template_hash != fixture["model"]["template_member_sha256"]:
        raise WorldBuildError(
            "map template hash mismatch; expected US HG member 0 "
            f"{fixture['model']['template_member_sha256']}, got {actual_template_hash}"
        )

    matrix = build_matrix(fixture)
    if fixture["schema_version"] in (6, 7):
        events = {name: build_event(fixture, name) for name in STAGE3E1_CELL_ORDER}
        map_members = {}
        model_info = {}
        map_headers = {}
        raw_components = {
            "matrix.bin": matrix,
            "matrix-probe.bin": matrix,
            "resolved-registry.json": (
                json.dumps(fixture["registry_resolution"], indent=2, sort_keys=True) + "\n"
            ).encode("utf-8"),
            "append-allocation-snapshot.json": (
                json.dumps({
                    symbol: value
                    for symbol, value in fixture["registry_resolution"]["symbols"].items()
                    if value["classification"] == "PROJECT_APPENDED"
                }, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8"),
        }
        for name in STAGE3E1_CELL_ORDER:
            member, info = build_map_member(fixture, template, name)
            split_member = split_hgss_map_member(member)
            map_members[name] = member
            model_info[name] = info
            map_headers[name] = build_map_header(fixture, arm9, name)
            raw_components.update({
                f"maps/{name}/map_member.bin": member,
                f"maps/{name}/nsbmd.bin": split_member["nsbmd"],
                f"maps/{name}/per.bin": split_member["per"],
                f"maps/{name}/bdhc.bin": split_member["bdhc"],
                f"events/{name}.bin": events[name],
                f"headers/{name}.bin": map_headers[name],
            })
        if fixture["schema_version"] == 7:
            project_table = b"".join(map_headers[name] for name in STAGE3E1_CELL_ORDER)
            validate_project_header_table(fixture, project_table)
            raw_components["project-header-table.bin"] = project_table
            raw_components["project-header-report.json"] = (
                json.dumps({
                    "retail_count": 540,
                    "entry_size": MAP_HEADER_SIZE,
                    "project_count": len(STAGE3E1_CELL_ORDER),
                    "project_ids": [fixture["maps"][name]["map_header"] for name in STAGE3E1_CELL_ORDER],
                    "sha256": sha256_bytes(project_table),
                }, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
    else:
        event = build_event(fixture)
    if fixture["schema_version"] == 3:
        map_members: dict[str, bytes] = {}
        model_info: dict[str, Any] = {}
        map_headers = {}
        raw_components = {"matrix.bin": matrix, "event.bin": event}
        if fixture.get("artifact_namespace") == "stage3c":
            raw_components["resolved-registry.json"] = (
                json.dumps(fixture["registry_resolution"], indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
        for name in STAGE3B_CELL_ORDER:
            member, info = build_map_member(fixture, template, name)
            split_member = split_hgss_map_member(member)
            map_members[name] = member
            model_info[name] = info
            map_headers[name] = build_map_header(fixture, arm9, name)
            raw_components.update({
                f"maps/{name}/map_member.bin": member,
                f"maps/{name}/nsbmd.bin": split_member["nsbmd"],
                f"maps/{name}/per.bin": split_member["per"],
                f"maps/{name}/bdhc.bin": split_member["bdhc"],
                f"headers/{name}.bin": map_headers[name],
            })
        validate_stage3b_cross_references(fixture, matrix, map_headers)
    elif fixture["schema_version"] not in (6, 7):
        map_member, model_info = build_map_member(fixture, template)
        map_members = {"map": map_member}
        map_header = build_map_header(fixture, arm9)
        map_headers = {"map": map_header}
        split_member = split_hgss_map_member(map_member)
        raw_components = {
            "map_member.bin": map_member,
            "nsbmd.bin": split_member["nsbmd"],
            "per.bin": split_member["per"],
            "bdhc.bin": split_member["bdhc"],
            "matrix.bin": matrix,
            "event.bin": event,
            "map_header.bin": map_header,
        }
        if fixture["schema_version"] == 5:
            geometry = compile_geometry(fixture["geometry"])
            raw_components["resolved-registry.json"] = (
                json.dumps(fixture["registry_resolution"], indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            raw_components["geometry-ir.json"] = (
                json.dumps(geometry["ir"], indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            report = dict(geometry["report"])
            capacities = model_info["shape_capacities"]
            report["shape_capacities"] = [
                {"shape": index, "capacity_bytes": capacity}
                for index, capacity in enumerate(capacities)
            ]
            report["shape_assignments"] = model_info["assignments"]
            raw_components["geometry-report.json"] = (
                json.dumps(report, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            for shape, display_list in sorted(geometry["display_lists"].items()):
                raw_components[f"display-lists/shape-{shape}.bin"] = display_list
        elif fixture["schema_version"] in (8, 9, 10, 11, 12):
            assets = compile_placements(
                root / fixture["asset_catalog"], fixture["assets"], root,
            )
            catalog = load_catalog(root / fixture["asset_catalog"], root)
            raw_components["resolved-registry.json"] = (
                json.dumps(fixture["registry_resolution"], indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            raw_components["asset-placement-ir.json"] = (
                json.dumps(assets["ir"], indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            report = dict(assets["report"])
            report["shape_capacities"] = [
                {"shape": index, "capacity_bytes": capacity}
                for index, capacity in enumerate(model_info["shape_capacities"])
            ]
            report["shape_assignments"] = model_info["assignments"]
            raw_components["asset-world-report.json"] = (
                json.dumps(report, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            for shape, display_list in sorted(assets["display_lists"].items()):
                raw_components[f"display-lists/asset-shape-{shape}.bin"] = display_list
            for asset_id in sorted({placement["asset"] for placement in fixture["assets"]}):
                compiled_asset = compile_asset(catalog[asset_id], root)
                raw_components[f"assets/{asset_id}/normalized-mesh.json"] = (
                    json.dumps(compiled_asset["ir"], indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
                raw_components[f"assets/{asset_id}/asset-report.json"] = (
                    json.dumps(compiled_asset["report"], indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
                raw_components[f"assets/{asset_id}/display-list.bin"] = compiled_asset["display_list"]
                raw_components[f"assets/{asset_id}/collision.json"] = (
                    json.dumps({
                        "schema_version": 1, "asset_id": asset_id,
                        "policy": "footprint_rect", "rectangle": compiled_asset["collision"],
                    }, indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
                for texture_id, texture in sorted(compiled_asset["textures"].items()):
                    raw_components[f"assets/{asset_id}/textures/{texture_id}/texture-ir.json"] = (
                        json.dumps(texture["ir"], indent=2, sort_keys=True) + "\n"
                    ).encode("utf-8")
                    raw_components[f"assets/{asset_id}/textures/{texture_id}/texture-report.json"] = (
                        json.dumps(texture["report"], indent=2, sort_keys=True) + "\n"
                    ).encode("utf-8")
                    raw_components[f"assets/{asset_id}/textures/{texture_id}/texture.bin"] = texture["texture"]
                    raw_components[f"assets/{asset_id}/textures/{texture_id}/palette.bin"] = texture["palette"]
                    if fixture["schema_version"] == 9:
                        source_narc = rom.getFileByName("a/0/4/4")
                        container = texture["spec"]["container"]
                        if sha256_bytes(source_narc) != container["archive_sha256"]:
                            raise WorldBuildError("Stage 4C area texture archive hash does not match supported US HG")
                        archive = NARC(source_narc)
                        pristine_members = list(archive.files)
                        if container["member"] >= len(pristine_members):
                            raise WorldBuildError("Stage 4C texture member is outside the pristine area archive")
                        patched_member, container_report = patch_btx0(
                            pristine_members[container["member"]], texture,
                        )
                        archive.files[container["member"]] = patched_member
                        stage4c_texture_narc = archive.save()
                        rebuilt = NARC(stage4c_texture_narc)
                        if len(rebuilt.files) != len(pristine_members):
                            raise WorldBuildError("Stage 4C texture NARC member count changed")
                        changed_members = [
                            index for index, (before, after) in enumerate(zip(pristine_members, rebuilt.files, strict=True))
                            if before != after
                        ]
                        if changed_members != [container["member"]] or rebuilt.files[container["member"]] != patched_member:
                            raise WorldBuildError("Stage 4C texture NARC changed an undeclared member")
                        stage4c_texture_narc_report = {
                            "schema_version": 1,
                            "archive": container["archive"],
                            "pristine_archive_sha256": sha256_bytes(source_narc),
                            "rebuilt_archive_sha256": sha256_bytes(stage4c_texture_narc),
                            "member_count": len(rebuilt.files),
                            "changed_members": changed_members,
                            "member_hashes": {
                                "before": sha256_bytes(pristine_members[container["member"]]),
                                "after": sha256_bytes(patched_member),
                            },
                            "all_unrelated_members_byte_identical": True,
                            "container_validation": container_report,
                        }
                        raw_components["texture-container.bin"] = patched_member
                        raw_components["texture-container-report.json"] = (
                            json.dumps(stage4c_texture_narc_report, indent=2, sort_keys=True) + "\n"
                        ).encode("utf-8")
            if fixture["schema_version"] in (10, 11, 12):
                container = fixture["texture_container"]
                compiled_catalog = compile_texture_catalog(root / container["catalog"], root)
                source_texture_narc = rom.getFileByName("a/0/4/4")
                source_area_data_narc = rom.getFileByName("a/0/4/2")
                if sha256_bytes(source_texture_narc) != registry["target"]["archives"]["area_textures"]["sha256"]:
                    raise WorldBuildError("Stage 4D pristine area-texture NARC hash disagrees with registry evidence")
                if sha256_bytes(source_area_data_narc) != registry["target"]["archives"]["area_data_banks"]["sha256"]:
                    raise WorldBuildError("Stage 4D pristine area-data NARC hash disagrees with registry evidence")
                texture_archive = NARC(source_texture_narc)
                area_archive = NARC(source_area_data_narc)
                if len(texture_archive.files) != 106 or len(area_archive.files) != 106:
                    raise WorldBuildError("Stage 4D append boundary is not the verified pristine member count")
                project_member, container_report = build_project_btx0(
                    texture_archive.files[2], compiled_catalog,
                )
                if container["area_texture_member"] != len(texture_archive.files):
                    raise WorldBuildError("Stage 4D area-texture allocation is not contiguous at the append boundary")
                texture_archive.files.append(project_member)
                # HGSS area data: building tileset, map texture member,
                # dynamic texture type, area type, light type.
                area_record = struct.pack("<3H2B", 0, container["area_texture_member"], 0xFFFF, 1, 1)
                if container["area_data_bank"] != len(area_archive.files):
                    raise WorldBuildError("Stage 4D area-data allocation is not contiguous at the append boundary")
                area_archive.files.append(area_record)
                stage4d_texture_narc = texture_archive.save()
                stage4d_area_data_narc = area_archive.save()
                rebuilt_texture = NARC(stage4d_texture_narc)
                rebuilt_area = NARC(stage4d_area_data_narc)
                if len(rebuilt_texture.files) != 107 or rebuilt_texture.files[106] != project_member:
                    raise WorldBuildError("Stage 4D rebuilt area-texture NARC does not contain project member 106")
                if len(rebuilt_area.files) != 107 or rebuilt_area.files[106] != area_record:
                    raise WorldBuildError("Stage 4D rebuilt area-data NARC does not contain project record 106")
                if rebuilt_texture.files[:106] != texture_archive.files[:106] or rebuilt_area.files[:106] != area_archive.files[:106]:
                    raise WorldBuildError("Stage 4D changed a protected retail archive prefix")
                if parse_btx0(rebuilt_texture.files[106]) != parse_btx0(project_member):
                    raise WorldBuildError("Stage 4D ROM archive cannot reopen its project TEX0 member")
                stage4d_texture_narc_report = {
                    "schema_version": 1, "archive": "a/0/4/4",
                    "pristine_count": 106, "rebuilt_count": 107, "appended_ids": [106],
                    "pristine_archive_sha256": sha256_bytes(source_texture_narc),
                    "rebuilt_archive_sha256": sha256_bytes(stage4d_texture_narc),
                    "appended_member_sha256": sha256_bytes(project_member),
                    "retail_prefix_byte_identical": True, "container_validation": container_report,
                }
                stage4d_area_data_narc_report = {
                    "schema_version": 1, "archive": "a/0/4/2",
                    "pristine_count": 106, "rebuilt_count": 107, "appended_ids": [106],
                    "pristine_archive_sha256": sha256_bytes(source_area_data_narc),
                    "rebuilt_archive_sha256": sha256_bytes(stage4d_area_data_narc),
                    "appended_member_sha256": sha256_bytes(area_record),
                    "appended_record_hex": area_record.hex(), "retail_prefix_byte_identical": True,
                }
                raw_components["project-texture-container.bin"] = project_member
                raw_components["project-area-data.bin"] = area_record
                raw_components["texture-catalog-report.json"] = (
                    json.dumps(compiled_catalog["report"], indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
                raw_components["texture-container-report.json"] = (
                    json.dumps(stage4d_texture_narc_report, indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
                raw_components["area-data-report.json"] = (
                    json.dumps(stage4d_area_data_narc_report, indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
    for name, data in raw_components.items():
        path = components / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    stage_name = fixture.get("artifact_namespace") or {1: "stage2", 2: "stage3a", 3: "stage3b"}[fixture["schema_version"]]
    if fixture["schema_version"] in (6, 7):
        script_outputs: dict[str, bytes] = {}
        script_header_outputs: dict[str, bytes] = {}
        text_outputs: dict[str, bytes] = {}
        for index, name in enumerate(STAGE3E1_CELL_ORDER):
            spec = fixture["maps"][name]
            script_path = components / f"2_{spec['script']:03d}"
            script_source = components / f"{stage_name}_{name}_script.s"
            _write_script_source(fixture, script_source, script_path, name)
            _run_checked([str(root / "tools/armips"), str(script_source)], root)
            script_outputs[name] = script_path.read_bytes()
            header = bytes((0, 0xA1 + index, 0xE1, 0))
            script_header_outputs[name] = header
            (components / f"2_{spec['script_header']:03d}").write_bytes(header)
            text_source = components / f"{stage_name}_{name}_dialogue.txt"
            text_path = components / f"7_{spec['text']:03d}"
            text_source.write_text(spec["npc"]["dialogue"] + "\n", encoding="utf-8")
            _run_checked(
                [str(root / "tools/msgenc"), "-e", "-k", "0x2A2A", "-c", "charmap.txt",
                 str(text_source), str(text_path)],
                root,
            )
            text_outputs[name] = text_path.read_bytes()
    else:
        script_output = components / f"2_{slots['script']:03d}"
        script_source = components / f"{stage_name}_script.s"
        _write_script_source(fixture, script_source, script_output)
        _run_checked([str(root / "tools/armips"), str(script_source)], root)

    start_script_output = components / f"2_{slots['start_script']:03d}"
    start_script_source = components / f"{stage_name}_start_script.s"
    _write_start_script_source(fixture, start_script_source, start_script_output)
    _run_checked([str(root / "tools/armips"), str(start_script_source)], root)

    if fixture["schema_version"] not in (6, 7):
        text_source = components / f"{stage_name}_dialogue.txt"
        text_output = components / f"7_{slots['text']:03d}"
        text = fixture["npc"]["dialogue"] if fixture["schema_version"] == 1 else fixture["text"]
        text_source.write_text(text + "\n", encoding="utf-8")
        # msgenc derives its default key from the entire output path, which makes
        # two clean output directories byte-different. The key is stored in the
        # bank header, so a fixed explicit Stage 2 key is both valid and stable.
        _run_checked(
            [str(root / "tools/msgenc"), "-e", "-k", "0x2A2A", "-c", "charmap.txt", str(text_source), str(text_output)],
            root,
        )

    installed_paths: dict[str, str] = {}
    narc_reports: dict[str, dict[str, Any]] = {}
    if fixture["schema_version"] == 9:
        if stage4c_texture_narc is None or stage4c_texture_narc_report is None:
            raise WorldBuildError("Stage 4C texture NARC was not generated")
        texture_destination = generated_root / "a/0/4/4"
        texture_destination.parent.mkdir(parents=True, exist_ok=True)
        texture_destination.write_bytes(stage4c_texture_narc)
        narc_reports["area_texture"] = stage4c_texture_narc_report
        if install:
            texture_target = root / "base/root/a/0/4/4"
            shutil.copyfile(texture_destination, texture_target)
            installed_paths["area_texture"] = str(texture_target)
    if fixture["schema_version"] in (10, 11, 12):
        if any(value is None for value in (
            stage4d_texture_narc, stage4d_area_data_narc,
            stage4d_texture_narc_report, stage4d_area_data_narc_report,
        )):
            raise WorldBuildError("Stage 4D project area archives were not generated")
        stage4d_archives = {
            "area_texture": ("a/0/4/4", stage4d_texture_narc, stage4d_texture_narc_report),
            "area_data": ("a/0/4/2", stage4d_area_data_narc, stage4d_area_data_narc_report),
        }
        for name, (relative, data, report) in stage4d_archives.items():
            assert isinstance(data, bytes) and isinstance(report, dict)
            destination = generated_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            narc_reports[name] = report
            if install:
                target = root / "base/root" / relative
                shutil.copyfile(destination, target)
                installed_paths[name] = str(target)
    if fixture["schema_version"] in (6, 7):
        archive_replacements: dict[str, dict[int, bytes]] = {
            "map": {
                fixture["maps"][name]["map_member"]: map_members[name]
                for name in STAGE3E1_CELL_ORDER
            },
            "matrix": {slots["matrix"]: matrix, slots["matrix_probe"]: matrix},
            "event": {
                fixture["maps"][name]["event"]: events[name]
                for name in STAGE3E1_CELL_ORDER
            },
            "text": {
                fixture["maps"][name]["text"]: text_outputs[name]
                for name in STAGE3E1_CELL_ORDER
            },
            "script": {slots["start_script"]: start_script_output.read_bytes()},
        }
        for name in STAGE3E1_CELL_ORDER:
            spec = fixture["maps"][name]
            archive_replacements["script"][spec["script"]] = script_outputs[name]
            archive_replacements["script"][spec["script_header"]] = script_header_outputs[name]
        for archive_name in ("map", "matrix", "event", "script", "text"):
            destination = generated_root / NARC_PATHS[archive_name].relative_to("base/root")
            narc_reports[archive_name] = _replace_narc_members(
                root / NARC_PATHS[archive_name], archive_replacements[archive_name], destination,
            )
        expected_source_counts = {"map": 676, "matrix": 288, "event": 491, "script": 965, "text": 854}
        expected_counts = {"map": 678, "matrix": 290, "event": 493, "script": 969, "text": 856}
        source_counts = {name: report["pristine_count"] for name, report in narc_reports.items()}
        if any(
            source_counts[name] not in (expected_source_counts[name], expected_counts[name])
            for name in expected_source_counts
        ):
            raise WorldBuildError("append-proof source NARC counts disagree with scanner/build evidence")
        if {name: report["rebuilt_count"] for name, report in narc_reports.items()} != expected_counts:
            raise WorldBuildError("append-proof rebuilt NARC counts disagree with the bounded proof")
        retail_keys = {
            "map": "map_members", "matrix": "matrices", "event": "event_banks",
            "script": "scripts", "text": "text_banks",
        }
        for name, report in narc_reports.items():
            report["retail_count"] = registry["target"]["archives"][retail_keys[name]]["members"]
            if source_counts[name] == expected_counts[name]:
                report["source_count_kind"] = "previously_installed_proof_archive"
            else:
                report["source_count_kind"] = "hg_engine_owned_prefix" if name == "text" else "pristine_retail"
        if install:
            for archive_name in ("map", "matrix", "event", "script", "text"):
                destination = generated_root / NARC_PATHS[archive_name].relative_to("base/root")
                target = root / NARC_PATHS[archive_name]
                shutil.copyfile(destination, target)
                installed_paths[archive_name] = str(target)
        narc_report_path = components / "narc-append-report.json"
        narc_report_path.write_text(json.dumps(narc_reports, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif fixture["schema_version"] == 3:
        map_replacements = {
            fixture["maps"][name]["map_member"]: map_members[name]
            for name in STAGE3B_CELL_ORDER
        }
        map_destination = generated_root / NARC_PATHS["map"].relative_to("base/root")
        _replace_narc_members(root / NARC_PATHS["map"], map_replacements, map_destination)
        if install:
            shutil.copyfile(map_destination, root / NARC_PATHS["map"])
            installed_paths["map"] = str(root / NARC_PATHS["map"])
    else:
        map_destination = generated_root / NARC_PATHS["map"].relative_to("base/root")
        _replace_narc(root / NARC_PATHS["map"], slots["map_member"], map_members["map"], map_destination)
        if install:
            shutil.copyfile(map_destination, root / NARC_PATHS["map"])
            installed_paths["map"] = str(root / NARC_PATHS["map"])
    if fixture["schema_version"] not in (6, 7):
        replacements = {
            "matrix": (slots["matrix"], matrix),
            "event": (slots["event"], event),
            "text": (slots["text"], text_output.read_bytes()),
        }
        for name, (member_id, member) in replacements.items():
            destination = generated_root / NARC_PATHS[name].relative_to("base/root")
            _replace_narc(root / NARC_PATHS[name], member_id, member, destination)
            if install:
                target = root / NARC_PATHS[name]
                shutil.copyfile(destination, target)
                installed_paths[name] = str(target)

        script_destination = generated_root / NARC_PATHS["script"].relative_to("base/root")
        _replace_narc_members(root / NARC_PATHS["script"], {
            slots["script"]: script_output.read_bytes(),
            slots["start_script"]: start_script_output.read_bytes(),
        }, script_destination)
        if install:
            shutil.copyfile(script_destination, root / NARC_PATHS["script"])
            installed_paths["script"] = str(root / NARC_PATHS["script"])

    patched_arm9 = bytearray(arm9)
    if fixture["schema_version"] != 7:
        for name, map_header in map_headers.items():
            header_id = _map_header_id(fixture, name if fixture["schema_version"] in (3, 6) else None)
            header_offset = HGSS_US_HEADER_OFFSET + header_id * MAP_HEADER_SIZE
            if header_offset + MAP_HEADER_SIZE > len(patched_arm9):
                raise WorldBuildError(f"map header {header_id} is outside arm9.bin")
            patched_arm9[header_offset:header_offset + MAP_HEADER_SIZE] = map_header
    generated_arm9 = output_dir / "arm9.bin"
    generated_arm9.write_bytes(patched_arm9)
    if install:
        shutil.copyfile(generated_arm9, arm9_path)
        installed_paths["arm9"] = str(arm9_path)

    artifacts = sorted(
        path for path in output_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    hashes = {str(path.relative_to(output_dir)): sha256_bytes(path.read_bytes()) for path in artifacts}
    manifest = {
        "schema_version": fixture["schema_version"],
        "canonical_schema_version": fixture.get("canonical_schema_version", fixture["schema_version"]),
        "fixture": str(fixture_path),
        "fixture_sha256": sha256_bytes(fixture_path.read_bytes()),
        "template_member_sha256": actual_template_hash,
        "model": model_info,
        "slots": slots,
        "installed": install,
        "installed_paths": installed_paths,
        "hashes": hashes,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_determinism(fixture_path: Path = DEFAULT_FIXTURE, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    fixture = load_fixture(fixture_path)
    namespace = fixture.get("artifact_namespace", "stage2")
    first = root / "build" / namespace / "determinism-a"
    second = root / "build" / namespace / "determinism-b"
    shutil.rmtree(first, ignore_errors=True)
    shutil.rmtree(second, ignore_errors=True)
    a = generate_world(fixture_path, first, root, install=False)
    b = generate_world(fixture_path, second, root, install=False)
    # Assembly/plaintext paths necessarily embed the selected output directory;
    # determinism is asserted over every binary member, patched NARC, and ARM9.
    a_hashes = {k: v for k, v in a["hashes"].items() if not k.endswith((".s", ".txt"))}
    b_hashes = {k: v for k, v in b["hashes"].items() if not k.endswith((".s", ".txt"))}
    mismatches = sorted(key for key in set(a_hashes) | set(b_hashes) if a_hashes.get(key) != b_hashes.get(key))
    result = {"success": not mismatches, "mismatches": mismatches, "hashes": a_hashes}
    report = root / "build" / namespace / "determinism-report.json"
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def validate_project_header_table(fixture: dict[str, Any], table: bytes) -> None:
    """Validate the exact contiguous Stage 3E2 table consumed by the hook."""
    if fixture.get("schema_version") != 7:
        raise WorldBuildError("project-header table validation requires schema 7")
    project_ids = [fixture["maps"][name]["map_header"] for name in STAGE3E1_CELL_ORDER]
    if project_ids != list(range(540, 540 + len(project_ids))):
        raise WorldBuildError("project headers must be contiguous from the retail boundary")
    expected_size = len(project_ids) * MAP_HEADER_SIZE
    if len(table) != expected_size:
        raise WorldBuildError(
            f"project-header table length {len(table)} does not match {expected_size}"
        )


def write_project_header_include(fixture_path: Path, output: Path) -> dict[str, Any]:
    """Generate the compile-time Stage 3E2 project table from symbolic source."""
    fixture = load_fixture(fixture_path)
    if fixture["schema_version"] != 7:
        raise WorldBuildError("project-header include generation requires a Stage 3E2 schema-7 fixture")
    headers = [build_map_header(fixture, b"", name) for name in STAGE3E1_CELL_ORDER]
    project_ids = [fixture["maps"][name]["map_header"] for name in STAGE3E1_CELL_ORDER]
    table = b"".join(headers)
    validate_project_header_table(fixture, table)
    rows = []
    for header in headers:
        rows.append("    { " + ", ".join(f"0x{byte:02X}" for byte in header) + " },")
    text = (
        "/* Generated from fixtures/stage3e2_header_expansion_world.json; do not edit. */\n"
        "#ifndef GENERATED_PROJECT_MAP_HEADERS_H\n#define GENERATED_PROJECT_MAP_HEADERS_H\n\n"
        "#define PROJECT_MAP_HEADER_BASE 540u\n"
        f"#define PROJECT_MAP_HEADER_COUNT {len(headers)}u\n"
        f"#define PROJECT_MAP_HEADER_TABLE_SHA256 \"{sha256_bytes(table)}\"\n"
        "static const u8 gProjectMapHeaders[PROJECT_MAP_HEADER_COUNT][24] = {\n"
        + "\n".join(rows)
        + "\n};\n\n#endif\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return {
        "success": True,
        "output": str(output),
        "retail_count": 540,
        "entry_size": MAP_HEADER_SIZE,
        "project_ids": project_ids,
        "sha256": sha256_bytes(table),
    }


def inspect_geometry(fixture_path: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Return the bounded geometry/capacity plan without writing generated artifacts."""
    fixture = load_fixture(fixture_path)
    if fixture["schema_version"] != 5:
        raise WorldBuildError("geometry inspection requires a Stage 3D schema-5 fixture")
    rom_path = root / "rom.nds"
    registry = load_registry(root / fixture["registry_resolution"]["registry"])
    verify_rom_revision(registry, rom_path)
    rom = NintendoDSRom.fromFile(str(rom_path))
    template_member = NARC(rom.getFileByName("a/0/6/5")).files[fixture["model"]["template_map_member"]]
    if sha256_bytes(template_member) != fixture["model"]["template_member_sha256"]:
        raise WorldBuildError("Stage 3D template member hash does not match its canonical lock")
    geometry = compile_geometry(fixture["geometry"])
    quad_counts = {
        MATERIAL_BINDINGS[material]["shape"]: geometry["report"]["materials"][material]["quad_count"]
        for material in MATERIAL_ORDER
    }
    _model, model = transform_template_nsbmd_multi(
        split_hgss_map_member(template_member)["nsbmd"], geometry["display_lists"], quad_counts,
    )
    report = dict(geometry["report"])
    report.update({
        "success": True,
        "fixture": str(fixture_path),
        "template_member_sha256": sha256_bytes(template_member),
        "shape_capacities": [
            {"shape": index, "capacity_bytes": capacity}
            for index, capacity in enumerate(model["shape_capacities"])
        ],
        "shape_assignments": model["assignments"],
        "material_bindings": MATERIAL_BINDINGS,
    })
    return report
