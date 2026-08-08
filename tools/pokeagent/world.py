"""Deterministic HGSS world-proof generator for Stages 2 through 3C.

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

from .registry import load_registry, resolve_world_source, verify_rom_revision


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "fixtures" / "stage2_proof_map.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "stage2" / "generated"
HGSS_US_HEADER_OFFSET = 0xF6BE0
MAP_HEADER_SIZE = 24
MAP_TILES = 32
STAGE3B_CELL_ORDER = ("nw", "ne", "sw", "se")
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
    validate_fixture(fixture)
    return fixture


def validate_fixture(fixture: dict[str, Any]) -> None:
    schema_version = fixture.get("schema_version")
    if schema_version not in (1, 2, 3):
        raise WorldBuildError("only resolved Stage 2, Stage 3A, and Stage 3B/3C schemas are supported")
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
    if not 0 <= target_shape < num_shapes:
        raise WorldBuildError(f"template shape {target_shape} is outside the model")

    display_list = build_flat_display_list() if display_list is None else display_list
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
    if len(display_list) > capacities[target_shape]:
        raise WorldBuildError(f"template shape {target_shape} is too small for the proof display list")

    degenerate = build_degenerate_display_list()
    for index, (dl_start, dl_size) in enumerate(regions):
        replacement = display_list if index == target_shape else degenerate
        if len(replacement) > dl_size:
            raise WorldBuildError(f"template shape {index} is too small for a valid replacement")
        data[dl_start:dl_start + dl_size] = replacement + bytes(dl_size - len(replacement))
    total_quads = num_shapes - 1 + target_quads
    struct.pack_into("<4H", data, model_base + 36, 4 * total_quads, total_quads, 0, total_quads)
    return bytes(data), {
        "models": 1,
        "nodes": num_nodes,
        "materials": num_materials,
        "shapes": num_shapes,
        "shape_capacities": capacities,
        "target_shape": target_shape,
        "display_list_bytes": len(display_list),
        "target_quads": target_quads,
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
    if fixture["schema_version"] != 3:
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
    terrain = fixture["terrain"]
    output = bytearray()
    if fixture["schema_version"] == 3:
        if map_name not in fixture["maps"]:
            raise WorldBuildError("Stage 3B PER generation requires a declared map name")
        map_spec = fixture["maps"][map_name]
        blocked = {tuple(map_spec["identity_blocked_tile"])}
        open_border = _stage3b_open_tiles(map_spec)
    else:
        blocked = {tuple(tile) for tile in terrain.get("blocked_tiles", [])}
        open_border = set()
    warps = {(warp["x"], warp["z"]) for warp in fixture.get("warps", [])}
    # HGSS PER is row-major (Z, then X), with the permission byte immediately
    # followed by the walkability byte. PDSMS names these row/column loops
    # j/k; DSPRE stores them in its first/second rectangular-array indices.
    for z in range(32):
        for x in range(32):
            is_border = (x in (0, 31) or z in (0, 31)) and (x, z) not in open_border
            if fixture["schema_version"] != 3:
                is_border = terrain["block_border"] and is_border
            collision = terrain["blocked_collision"] if is_border or (x, z) in blocked else terrain["walkable_collision"]
            permission = terrain.get("warp_permission_type", terrain["permission_type"]) if (x, z) in warps else terrain["permission_type"]
            output.extend((permission, collision))
    return bytes(output)


def build_bdhc(fixture: dict[str, Any]) -> bytes:
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
    if fixture["schema_version"] == 2:
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
    if fixture["schema_version"] == 3:
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
    name = b"stage2-proof" if fixture["schema_version"] == 1 else b"stage3a-height"
    slots = fixture["slots"]
    return bytes((1, 1, 1, 1, len(name))) + name + struct.pack("<H", slots["map_header"]) + b"\0" + struct.pack("<H", slots["map_member"])


def build_event(fixture: dict[str, Any]) -> bytes:
    if fixture["schema_version"] in (2, 3):
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
    if fixture["schema_version"] == 3:
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
    template_id = fixture["header_template"]
    template_offset = HGSS_US_HEADER_OFFSET + template_id * MAP_HEADER_SIZE
    if template_offset + MAP_HEADER_SIZE > len(arm9):
        raise WorldBuildError("US HG map-header table is outside arm9.bin")
    output = bytearray(arm9[template_offset:template_offset + MAP_HEADER_SIZE])
    output[0] = 0xFF
    output[1] = fixture["model"]["area_data"]
    struct.pack_into("<7H", output, 4, slots["matrix"], slots["script"], slots["script_header"], slots["text"],
                     struct.unpack_from("<H", output, 12)[0], struct.unpack_from("<H", output, 14)[0], slots["event"])
    return bytes(output)


def _write_script_source(fixture: dict[str, Any], source: Path, output: Path) -> None:
    if fixture["schema_version"] in (2, 3):
        if fixture["schema_version"] == 2:
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
    if fixture["schema_version"] == 3:
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


def _replace_narc(source: Path, member_id: int, member: bytes, destination: Path) -> None:
    archive = NARC.fromFile(str(source))
    if member_id >= len(archive.files):
        raise WorldBuildError(f"member {member_id} is outside {source} ({len(archive.files)} files)")
    archive.files[member_id] = member
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive.saveToFile(str(destination))


def _replace_narc_members(source: Path, replacements: dict[int, bytes], destination: Path) -> None:
    archive = NARC.fromFile(str(source))
    for member_id, member in sorted(replacements.items()):
        if member_id >= len(archive.files):
            raise WorldBuildError(f"member {member_id} is outside {source} ({len(archive.files)} files)")
        archive.files[member_id] = member
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive.saveToFile(str(destination))


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

    for name, relative in NARC_PATHS.items():
        if not (root / relative).is_file():
            raise WorldBuildError(f"missing extracted prerequisite for {name}: {relative}")
    arm9_path = root / "base/arm9.bin"
    arm9 = arm9_path.read_bytes()

    rom_path = root / "rom.nds"
    if not rom_path.is_file():
        raise WorldBuildError("missing ignored user-supplied rom.nds template source")
    if fixture.get("artifact_namespace") == "stage3c":
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
    else:
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
    for name, data in raw_components.items():
        path = components / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    script_output = components / f"2_{slots['script']:03d}"
    stage_name = fixture.get("artifact_namespace", {1: "stage2", 2: "stage3a", 3: "stage3b"}[fixture["schema_version"]])
    script_source = components / f"{stage_name}_script.s"
    _write_script_source(fixture, script_source, script_output)
    _run_checked([str(root / "tools/armips"), str(script_source)], root)

    start_script_output = components / f"2_{slots['start_script']:03d}"
    start_script_source = components / f"{stage_name}_start_script.s"
    _write_start_script_source(fixture, start_script_source, start_script_output)
    _run_checked([str(root / "tools/armips"), str(start_script_source)], root)

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
    if fixture["schema_version"] == 3:
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

    script_archive = NARC.fromFile(str(root / NARC_PATHS["script"]))
    for member_id, member in (
        (slots["script"], script_output.read_bytes()),
        (slots["start_script"], start_script_output.read_bytes()),
    ):
        if member_id >= len(script_archive.files):
            raise WorldBuildError(f"script member {member_id} is outside the script NARC")
        script_archive.files[member_id] = member
    script_destination = generated_root / NARC_PATHS["script"].relative_to("base/root")
    script_destination.parent.mkdir(parents=True, exist_ok=True)
    script_archive.saveToFile(str(script_destination))
    if install:
        shutil.copyfile(script_destination, root / NARC_PATHS["script"])
        installed_paths["script"] = str(root / NARC_PATHS["script"])

    patched_arm9 = bytearray(arm9)
    for name, map_header in map_headers.items():
        header_id = _map_header_id(fixture, name if fixture["schema_version"] == 3 else None)
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
