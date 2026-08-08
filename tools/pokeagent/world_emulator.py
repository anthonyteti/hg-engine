"""Headless runtime assertions for the bounded Stage 2 through 3D proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from typing import Any

from .command import run_command
from .rom import (
    GENERATED_ROM_NAME,
    PROJECT_ROOT,
    path_is_git_ignored,
    sha256_file,
    utc_now,
    write_json_report,
)
from .world import DEFAULT_FIXTURE, MAP_TILES, STAGE3B_CELL_ORDER, load_fixture


FIELD_SYSTEM_POINTER_OFFSET = 0x14
FIELD_LOCATION_POINTER_OFFSET = 0x20
FIELD_PLAYER_AVATAR_OFFSET = 0x40
PLAYER_MAP_OBJECT_OFFSET = 0x30
MAP_OBJECT_CURRENT_HEIGHT_OFFSET = 0x68
MAP_OBJECT_POSITION_Y_OFFSET = 0x74
MAP_MATRIX_POINTER_OFFSET = 0x30
MAP_LOAD_MANAGER_POINTER_OFFSET = 0x2C
MAP_LOAD_ACTIVE_INDEX_OFFSET = 0xA4
MAP_LOAD_ACTIVE_QUADRANT_OFFSET = 0xAC
MAP_LOAD_WIDTH_OFFSET = 0xC4
MAP_LOAD_HEIGHT_OFFSET = 0xC8
MAP_LOAD_SLOT_POINTER_OFFSET = 0x90
LOADED_MAP_MATRIX_INDEX_OFFSET = 0x860
LOADED_MAP_READY_OFFSET = 0x864
MAP_MATRIX_HEADERS_OFFSET = 6
MAP_MATRIX_ALTITUDES_OFFSET = 1604
MAP_MATRIX_MEMBERS_OFFSET = 2404


def _symbols(root: Path) -> dict[str, int]:
    candidates = (
        Path("/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm"),
        Path("arm-none-eabi-nm"),
    )
    nm = next((candidate for candidate in candidates if candidate.is_file()), candidates[-1])
    result = subprocess.run(
        [str(nm), "-n", str(root / "build/linked.o")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot inspect linked symbols: {result.stdout[-500:]}")
    wanted = {
        "gFieldSysPtr", "gStage2ProofDialogueSeen", "gStage2ProofMetatileBehavior",
        "gStage2ProofWarpBehaviorSeen",
    }
    found: dict[str, int] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in wanted:
            found[fields[2]] = int(fields[0], 16)
    missing = wanted - found.keys()
    if missing:
        raise RuntimeError(f"Stage 2 symbols missing from build/linked.o: {sorted(missing)}")
    return found


def _cycle(emu: Any, frames: int, deadline: float) -> None:
    for _ in range(frames):
        if time.monotonic() >= deadline:
            raise TimeoutError("world emulator worker exceeded its deadline")
        emu.cycle(False)


def _press(emu: Any, key: int, deadline: float, held: int = 4, after: int = 35) -> None:
    from desmume.controls import keymask

    mask = keymask(key)
    emu.input.keypad_add_key(mask)
    try:
        _cycle(emu, held, deadline)
    finally:
        emu.input.keypad_rm_key(mask)
    _cycle(emu, after, deadline)


def _move_to_coordinate(
    emu: Any,
    key: int,
    field_pointer_symbol: int,
    axis: str,
    target: int,
    deadline: float,
    max_attempts: int = 96,
) -> dict[str, int]:
    """Repeat bounded normal input until one global coordinate reaches target."""
    if axis not in ("x", "z"):
        raise ValueError(f"unsupported movement axis {axis}")
    for _ in range(max_attempts):
        location = _location(emu, field_pointer_symbol)
        if location is not None and location[axis] == target:
            return location
        _press(emu, key, deadline)
    location = _location(emu, field_pointer_symbol)
    raise AssertionError(f"movement did not reach {axis}={target}: {location}")


def _read_u32(emu: Any, address: int) -> int:
    return int(emu.memory.unsigned[address:address:4])


def _read_i32(emu: Any, address: int) -> int:
    return int(emu.memory.signed[address:address:4])


def _read_u8(emu: Any, address: int) -> int:
    return int(emu.memory.unsigned[address:address:1])


def _read_u16(emu: Any, address: int) -> int:
    return int(emu.memory.unsigned[address:address:2])


def _location(emu: Any, field_pointer_symbol: int) -> dict[str, int] | None:
    field_system = _read_u32(emu, field_pointer_symbol)
    if field_system == 0:
        return None
    location = _read_u32(emu, field_system + FIELD_LOCATION_POINTER_OFFSET)
    if location == 0:
        return None
    names = ("map", "warp", "x", "z", "direction")
    return {name: _read_i32(emu, location + index * 4) for index, name in enumerate(names)}


def _event_counts(emu: Any, field_pointer_symbol: int) -> dict[str, int]:
    field_system = _read_u32(emu, field_pointer_symbol)
    event_data = _read_u32(emu, field_system + FIELD_SYSTEM_POINTER_OFFSET)
    if event_data == 0:
        raise RuntimeError("field event pointer is null")
    names = ("background", "npc", "warp", "coordinate")
    return {name: _read_u32(emu, event_data + index * 4) for index, name in enumerate(names)}


def _height_state(emu: Any, field_pointer_symbol: int) -> dict[str, int]:
    field_system = _read_u32(emu, field_pointer_symbol)
    player_avatar = _read_u32(emu, field_system + FIELD_PLAYER_AVATAR_OFFSET)
    map_object = _read_u32(emu, player_avatar + PLAYER_MAP_OBJECT_OFFSET)
    if not field_system or not player_avatar or not map_object:
        raise RuntimeError("player height state contains a null pointer")
    return {
        "current_height": _read_i32(emu, map_object + MAP_OBJECT_CURRENT_HEIGHT_OFFSET),
        "position_y_fx32": _read_i32(emu, map_object + MAP_OBJECT_POSITION_Y_OFFSET),
    }


def _bdhc_runtime_state(emu: Any, field_pointer_symbol: int) -> list[dict[str, object]]:
    """Inspect the four loaded-map slots and their parsed 0x20-byte BDHC views."""
    field_system = _read_u32(emu, field_pointer_symbol)
    map_load_manager = _read_u32(emu, field_system + 0x2C)
    slots = []
    for index in range(4):
        loaded_map = _read_u32(emu, map_load_manager + 0x90 + index * 4)
        if not loaded_map:
            continue
        bdhc = _read_u32(emu, loaded_map + 0x85C)
        entry: dict[str, object] = {
            "slot": index,
            "loaded_map": f"0x{loaded_map:08x}",
            "bdhc": f"0x{bdhc:08x}" if bdhc else None,
        }
        if bdhc:
            entry["ready"] = _read_u32(emu, bdhc + 0x18)
            entry["stripe_count"] = _read_u32(emu, bdhc + 0x1C)
            entry["pointers"] = [
                f"0x{_read_u32(emu, bdhc + offset):08x}"
                for offset in (0, 4, 8, 12, 16, 20)
            ]
        slots.append(entry)
    return slots


def _stage3b_runtime_state(emu: Any, field_pointer_symbol: int) -> dict[str, object]:
    field_system = _read_u32(emu, field_pointer_symbol)
    if not field_system:
        raise RuntimeError("Stage 3B field-system pointer is null")
    location = _location(emu, field_pointer_symbol)
    map_matrix = _read_u32(emu, field_system + MAP_MATRIX_POINTER_OFFSET)
    manager = _read_u32(emu, field_system + MAP_LOAD_MANAGER_POINTER_OFFSET)
    if location is None or not map_matrix or not manager:
        raise RuntimeError("Stage 3B runtime state contains a null world pointer")
    active_quadrant = _read_u8(emu, manager + MAP_LOAD_ACTIVE_QUADRANT_OFFSET)
    loaded_slots = []
    for slot in range(4):
        loaded_map = _read_u32(emu, manager + MAP_LOAD_SLOT_POINTER_OFFSET + slot * 4)
        loaded_slots.append({
            "slot": slot,
            "pointer": f"0x{loaded_map:08x}" if loaded_map else None,
            "matrix_index": _read_i32(emu, loaded_map + LOADED_MAP_MATRIX_INDEX_OFFSET) if loaded_map else None,
            "ready": _read_u32(emu, loaded_map + LOADED_MAP_READY_OFFSET) if loaded_map else None,
        })
    active_slot = loaded_slots[active_quadrant] if active_quadrant < len(loaded_slots) else None
    matrix_state = {
        "id": _read_u8(emu, map_matrix + 2),
        "width": _read_u8(emu, map_matrix),
        "height": _read_u8(emu, map_matrix + 1),
        "headers": [_read_u16(emu, map_matrix + MAP_MATRIX_HEADERS_OFFSET + index * 2) for index in range(4)],
        "altitudes": [_read_u8(emu, map_matrix + MAP_MATRIX_ALTITUDES_OFFSET + index) for index in range(4)],
        "members": [_read_u16(emu, map_matrix + MAP_MATRIX_MEMBERS_OFFSET + index * 2) for index in range(4)],
    }
    active_index = _read_i32(emu, manager + MAP_LOAD_ACTIVE_INDEX_OFFSET)
    active_pointer = (
        int(active_slot["pointer"], 16)
        if active_slot and active_slot["pointer"] is not None
        else 0
    )
    local_z = location["z"] % MAP_TILES
    loaded_per_hashes = []
    for slot in loaded_slots:
        pointer = int(slot["pointer"], 16) if slot["pointer"] is not None else 0
        values = [
            _read_u16(emu, pointer + index * 2)
            for index in range(MAP_TILES * MAP_TILES)
        ] if pointer and slot["ready"] == 1 else []
        data = b"".join(struct.pack("<H", value) for value in values)
        loaded_per_hashes.append(hashlib.sha256(data).hexdigest() if data else None)
    return {
        "location": location,
        "local": {"x": location["x"] % MAP_TILES, "z": location["z"] % MAP_TILES},
        "cell": {"column": location["x"] // MAP_TILES, "row": location["z"] // MAP_TILES},
        "matrix": matrix_state,
        "load_manager": {
            "active_index": active_index,
            "active_quadrant": active_quadrant,
            "width": _read_i32(emu, manager + MAP_LOAD_WIDTH_OFFSET),
            "height": _read_i32(emu, manager + MAP_LOAD_HEIGHT_OFFSET),
            "active_loaded_index": active_slot["matrix_index"] if active_slot else None,
            "active_member": matrix_state["members"][active_index] if 0 <= active_index < 4 else None,
            "active_ready": active_slot["ready"] if active_slot else None,
            # ov01_021F65E4 returns this allocation directly and the runtime
            # indexes it as 32x32 u16 PER records. Retain a compact row sample
            # in reports so a failed traversal distinguishes input, generated
            # collision, and map-selection failures without guesswork.
            "active_per_row_sample": [
                _read_u16(emu, active_pointer + 2 * (local_z * MAP_TILES + x))
                for x in range(14, 23)
            ] if active_pointer else [],
            "loaded_per_sha256": loaded_per_hashes,
            "loaded_slots": loaded_slots,
        },
    }


def _stage3b_state_matches(
    state: dict[str, object],
    fixture: dict[str, Any],
    map_name: str,
    x: int,
    z: int,
) -> bool:
    spec = fixture["maps"][map_name]
    index = spec["cell"]["row"] * 2 + spec["cell"]["column"]
    location = state["location"]
    matrix = state["matrix"]
    manager = state["load_manager"]
    return (
        location["map"] == spec["map_header"]
        and (location["x"], location["z"]) == (x, z)
        and state["cell"] == spec["cell"]
        and state["local"] == {"x": x % MAP_TILES, "z": z % MAP_TILES}
        and matrix == {
            "id": fixture["slots"]["matrix"],
            "width": 2,
            "height": 2,
            "headers": [fixture["maps"][name]["map_header"] for name in STAGE3B_CELL_ORDER],
            "altitudes": fixture["world"]["matrix"]["altitudes"],
            "members": [fixture["maps"][name]["map_member"] for name in STAGE3B_CELL_ORDER],
        }
        and manager["active_index"] == index
        and manager["width"] == 2
        and manager["height"] == 2
        and manager["active_loaded_index"] == index
        and manager["active_member"] == spec["map_member"]
        and manager["active_ready"] == 1
    )


def _warp_events(emu: Any, field_pointer_symbol: int, count: int) -> list[dict[str, int]]:
    field_system = _read_u32(emu, field_pointer_symbol)
    event_data = _read_u32(emu, field_system + FIELD_SYSTEM_POINTER_OFFSET)
    warp_pointer = _read_u32(emu, event_data + 24)
    events = []
    for index in range(count):
        values = struct.unpack(
            "<4HI",
            bytes(
                emu.memory.unsigned[
                    warp_pointer + index * 12:warp_pointer + (index + 1) * 12
                ]
            ),
        )
        events.append(dict(zip(("x", "z", "header", "anchor", "height"), values)))
    return events


def _capture(emu: Any, path: Path) -> dict[str, object]:
    image = emu.screenshot().convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    pixels = image.tobytes()
    return {
        "path": str(path),
        "width": image.width,
        "height": image.height,
        "sha256": sha256_file(path),
        "pixel_sha256": hashlib.sha256(pixels).hexdigest(),
        "unique_colors": len(set(pixels[index:index + 3] for index in range(0, len(pixels), 3))),
    }


def _worker(
    root: Path,
    rom_path: Path,
    fixture_path: Path,
    result_path: Path,
    artifact_dir: Path,
    timeout_seconds: float,
) -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    started = time.monotonic()
    deadline = started + timeout_seconds
    fixture = load_fixture(fixture_path)
    symbols = _symbols(root)
    checks: dict[str, bool] = {}
    observations: dict[str, object] = {}
    screenshots: dict[str, object] = {}
    emu = None
    payload: dict[str, object] = {
        "schema_version": fixture["schema_version"],
        "operation": "stage3c_registry_emulator_worker" if fixture.get("artifact_namespace") == "stage3c" else {
            1: "stage2_map_emulator_worker",
            2: "stage3a_height_emulator_worker",
            3: "stage3b_multimap_emulator_worker",
            5: "stage3d_geometry_emulator_worker",
        }[fixture["schema_version"]],
        "success": False,
        "rom": str(rom_path),
        "symbols": {name: f"0x{address:08x}" for name, address in symbols.items()},
        "checks": checks,
        "observations": observations,
        "screenshots": screenshots,
    }
    try:
        from desmume.controls import Keys
        from desmume.emulator import DeSmuME

        emu = DeSmuME()
        emu.open(str(rom_path))

        # Deterministic new-game bootstrap: title -> new game -> no tutorial
        # info -> accept the default player/name prompts. The test-only engine
        # hook then queues common script 2000, replaced by the generated warp.
        _cycle(emu, 3200, deadline)
        _press(emu, Keys.KEY_A, deadline, after=800)
        emu.input.touch_set_pos(130, 152)
        _cycle(emu, 4, deadline)
        emu.input.touch_release()
        _cycle(emu, 400, deadline)
        if fixture["schema_version"] == 3:
            start_spec = fixture["maps"][fixture["player_start"]["map"]]
            target_header = start_spec["map_header"]
        else:
            target_header = fixture["slots"]["map_header"]
        for _ in range(75):
            current = _location(emu, symbols["gFieldSysPtr"])
            if current is not None and current["map"] == target_header:
                break
            _press(emu, Keys.KEY_A, deadline, after=60)
        else:
            raise AssertionError(f"controlled start did not reach map {target_header}: {current}")
        # A field warp can finish loading before its script/task teardown has
        # released movement input.  Keep the bootstrap deterministic but wait
        # through that teardown before the first D-pad assertion.
        _cycle(emu, 180, deadline)

        start = _location(emu, symbols["gFieldSysPtr"])
        expected_start = fixture["player_start"]
        if fixture["schema_version"] == 3:
            expected_start_x = start_spec["cell"]["column"] * MAP_TILES + expected_start["local_x"]
            expected_start_z = start_spec["cell"]["row"] * MAP_TILES + expected_start["local_z"]
        else:
            expected_start_x, expected_start_z = expected_start["x"], expected_start["z"]
        observations["start"] = start
        checks["map_loaded"] = start is not None and start["map"] == target_header
        checks["controlled_start"] = start is not None and (start["x"], start["z"]) == (
            expected_start_x, expected_start_z
        )
        counts = _event_counts(emu, symbols["gFieldSysPtr"])
        observations["event_counts"] = counts
        if fixture["schema_version"] == 3:
            start_state = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["start_state"] = start_state
            checks["matrix_runtime_layout"] = start_state["matrix"] == {
                "id": 1,
                "width": 2,
                "height": 2,
                "headers": [538, 9, 10, 11],
                "altitudes": [0, 0, 0, 0],
                "members": [633, 630, 631, 632],
            }
            checks["start_identifies_nw"] = _stage3b_state_matches(
                start_state, fixture, "nw", 16, 16
            )
            checks["four_distinct_members_loaded"] = {
                entry["matrix_index"] for entry in start_state["load_manager"]["loaded_slots"]
                if entry["ready"] == 1
            } == {0, 1, 2, 3} and set(start_state["matrix"]["members"]) == {630, 631, 632, 633}
            checks["no_explicit_warp_events"] = counts == {
                "background": 0, "npc": 0, "warp": 0, "coordinate": 0,
            }
            screenshots["nw_start"] = _capture(emu, artifact_dir / "nw-start.png")

            _move_to_coordinate(emu, Keys.KEY_RIGHT, symbols["gFieldSysPtr"], "x", 31, deadline)
            nw_east_approach = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_RIGHT, symbols["gFieldSysPtr"], "x", 32, deadline)
            ne_entered = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_RIGHT, symbols["gFieldSysPtr"], "x", 33, deadline)
            ne_continued = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["nw_to_ne"] = {
                "approach": nw_east_approach, "entered": ne_entered, "continued": ne_continued,
            }
            checks["nw_east_edge_approached"] = _stage3b_state_matches(
                nw_east_approach, fixture, "nw", 31, 16
            )
            checks["nw_to_ne_native_transition"] = (
                _stage3b_state_matches(ne_entered, fixture, "ne", 32, 16)
                and ne_entered["local"] == {"x": 0, "z": 16}
                and ne_entered["location"]["warp"] == nw_east_approach["location"]["warp"]
            )
            checks["movement_continues_in_ne"] = _stage3b_state_matches(
                ne_continued, fixture, "ne", 33, 16
            )
            screenshots["ne_entered"] = _capture(emu, artifact_dir / "ne-entered.png")

            _move_to_coordinate(emu, Keys.KEY_RIGHT, symbols["gFieldSysPtr"], "x", 48, deadline)
            _move_to_coordinate(emu, Keys.KEY_DOWN, symbols["gFieldSysPtr"], "z", 31, deadline)
            ne_south_approach = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_DOWN, symbols["gFieldSysPtr"], "z", 32, deadline)
            se_entered = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_DOWN, symbols["gFieldSysPtr"], "z", 33, deadline)
            se_continued = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["ne_to_se"] = {
                "approach": ne_south_approach, "entered": se_entered, "continued": se_continued,
            }
            checks["ne_south_edge_approached"] = _stage3b_state_matches(
                ne_south_approach, fixture, "ne", 48, 31
            )
            checks["ne_to_se_native_transition"] = (
                _stage3b_state_matches(se_entered, fixture, "se", 48, 32)
                and se_entered["local"] == {"x": 16, "z": 0}
                and se_entered["location"]["warp"] == ne_south_approach["location"]["warp"]
            )
            checks["movement_continues_in_se"] = _stage3b_state_matches(
                se_continued, fixture, "se", 48, 33
            )
            screenshots["se_entered"] = _capture(emu, artifact_dir / "se-entered.png")

            _move_to_coordinate(emu, Keys.KEY_DOWN, symbols["gFieldSysPtr"], "z", 48, deadline)
            _move_to_coordinate(emu, Keys.KEY_LEFT, symbols["gFieldSysPtr"], "x", 32, deadline)
            se_west_approach = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_LEFT, symbols["gFieldSysPtr"], "x", 31, deadline)
            sw_entered = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_LEFT, symbols["gFieldSysPtr"], "x", 30, deadline)
            sw_continued = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["se_to_sw"] = {
                "approach": se_west_approach, "entered": sw_entered, "continued": sw_continued,
            }
            checks["se_west_edge_approached"] = _stage3b_state_matches(
                se_west_approach, fixture, "se", 32, 48
            )
            checks["se_to_sw_native_transition"] = (
                _stage3b_state_matches(sw_entered, fixture, "sw", 31, 48)
                and sw_entered["local"] == {"x": 31, "z": 16}
                and sw_entered["location"]["warp"] == se_west_approach["location"]["warp"]
            )
            checks["movement_continues_in_sw"] = _stage3b_state_matches(
                sw_continued, fixture, "sw", 30, 48
            )
            screenshots["sw_entered"] = _capture(emu, artifact_dir / "sw-entered.png")

            _move_to_coordinate(emu, Keys.KEY_LEFT, symbols["gFieldSysPtr"], "x", 16, deadline)
            _move_to_coordinate(emu, Keys.KEY_UP, symbols["gFieldSysPtr"], "z", 32, deadline)
            sw_north_approach = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_UP, symbols["gFieldSysPtr"], "z", 31, deadline)
            nw_returned = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _move_to_coordinate(emu, Keys.KEY_UP, symbols["gFieldSysPtr"], "z", 30, deadline)
            nw_continued = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["sw_to_nw"] = {
                "approach": sw_north_approach, "entered": nw_returned, "continued": nw_continued,
            }
            checks["sw_north_edge_approached"] = _stage3b_state_matches(
                sw_north_approach, fixture, "sw", 16, 32
            )
            checks["sw_to_nw_native_transition"] = (
                _stage3b_state_matches(nw_returned, fixture, "nw", 16, 31)
                and nw_returned["local"] == {"x": 16, "z": 31}
                and nw_returned["location"]["warp"] == sw_north_approach["location"]["warp"]
            )
            checks["movement_continues_after_loop"] = _stage3b_state_matches(
                nw_continued, fixture, "nw", 16, 30
            )
            screenshots["nw_returned"] = _capture(emu, artifact_dir / "nw-returned.png")

            _move_to_coordinate(emu, Keys.KEY_UP, symbols["gFieldSysPtr"], "z", 1, deadline)
            exterior_approach = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_UP, deadline, after=60)
            exterior_blocked = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["exterior_north_boundary"] = {
                "approach": exterior_approach, "blocked": exterior_blocked,
            }
            checks["nw_exterior_boundary_blocked"] = (
                _stage3b_state_matches(exterior_approach, fixture, "nw", 16, 1)
                and _stage3b_state_matches(exterior_blocked, fixture, "nw", 16, 1)
            )
            screenshots["exterior_blocked"] = _capture(emu, artifact_dir / "exterior-blocked.png")

            event_counts_after_transitions = _event_counts(emu, symbols["gFieldSysPtr"])
            observations["event_counts_after_transitions"] = event_counts_after_transitions
            checks["edge_loop_never_loaded_warp_records"] = event_counts_after_transitions == counts
            _cycle(emu, 600, deadline)
            stable = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["after_stability_window"] = stable
            checks["rom_stable_600_frames"] = (
                bool(emu.is_running()) and _stage3b_state_matches(stable, fixture, "nw", 16, 1)
            )
            payload["success"] = all(checks.values())
            if not payload["success"]:
                payload["error"] = "one or more Stage 3B runtime assertions failed"
            return 0 if payload["success"] else 1
        if fixture["schema_version"] == 5:
            observations["map_runtime"] = _stage3b_runtime_state(emu, symbols["gFieldSysPtr"])
            observations["bdhc_runtime"] = _bdhc_runtime_state(emu, symbols["gFieldSysPtr"])
            checks["parsed_bdhc_loaded"] = any(
                entry.get("ready") == 1 and entry.get("stripe_count") == 6
                for entry in observations["bdhc_runtime"]
            )
            checks["event_fixture_is_empty"] = counts == {
                "background": 0, "npc": 0, "warp": 0, "coordinate": 0,
            }
            lower_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["lower_start"] = {"location": start, "height": lower_height}
            checks["initial_lower_height"] = (
                lower_height["current_height"] == 0 and lower_height["position_y_fx32"] == 0
            )
            screenshots["lower_start"] = _capture(emu, artifact_dir / "lower-start.png")

            _press(emu, Keys.KEY_LEFT, deadline, after=60)
            lower_left = _location(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_RIGHT, deadline, after=60)
            lower_back = _location(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_UP, deadline, after=60)
            lower_up = _location(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_DOWN, deadline, after=60)
            lower_returned = _location(emu, symbols["gFieldSysPtr"])
            observations["initial_lower_movement"] = [lower_left, lower_back, lower_up, lower_returned]
            checks["lower_terrain_movement"] = (
                [(state["x"], state["z"]) for state in (lower_left, lower_back, lower_up, lower_returned)]
                == [(7, 12), (8, 12), (8, 11), (8, 12)]
            )

            for _ in range(5):
                _press(emu, Keys.KEY_RIGHT, deadline)
            ramp_a_states = []
            for target_x in (14, 15, 16, 17):
                _press(emu, Keys.KEY_RIGHT, deadline, after=60)
                ramp_a_states.append({
                    "location": _location(emu, symbols["gFieldSysPtr"]),
                    "height": _height_state(emu, symbols["gFieldSysPtr"]),
                })
            observations["transition_a"] = ramp_a_states
            checks["transition_a_traversed"] = (
                [(state["location"]["x"], state["location"]["z"]) for state in ramp_a_states]
                == [(14, 12), (15, 12), (16, 12), (17, 12)]
            )
            checks["transition_a_height_progression"] = (
                [state["height"]["current_height"] for state in ramp_a_states] == [1, 3, 4, 4]
                and ramp_a_states[-1]["height"]["position_y_fx32"] == 2 * 65536
            )
            screenshots["transition_a"] = _capture(emu, artifact_dir / "transition-a.png")

            raised_route_states = []
            _press(emu, Keys.KEY_RIGHT, deadline, after=60)
            raised_route_states.append(_location(emu, symbols["gFieldSysPtr"]))
            for _ in range(3):
                _press(emu, Keys.KEY_UP, deadline, after=60)
                raised_route_states.append(_location(emu, symbols["gFieldSysPtr"]))
            for _ in range(2):
                _press(emu, Keys.KEY_LEFT, deadline, after=60)
                raised_route_states.append(_location(emu, symbols["gFieldSysPtr"]))
            cliff_approach = _location(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_LEFT, deadline, after=60)
            cliff_blocked = _location(emu, symbols["gFieldSysPtr"])
            cliff_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["direct_cliff"] = {"approach": cliff_approach, "blocked": cliff_blocked, "height": cliff_height}
            checks["direct_cliff_blocks_shortcut"] = (
                cliff_approach is not None and (cliff_approach["x"], cliff_approach["z"]) == (16, 9)
                and cliff_blocked is not None and (cliff_blocked["x"], cliff_blocked["z"]) == (16, 9)
                and cliff_height["current_height"] == 4
            )
            screenshots["cliff_blocked"] = _capture(emu, artifact_dir / "cliff-blocked.png")

            for _ in range(2):
                _press(emu, Keys.KEY_RIGHT, deadline, after=60)
            for _ in range(14):
                _press(emu, Keys.KEY_DOWN, deadline, after=60)
                raised_route_states.append(_location(emu, symbols["gFieldSysPtr"]))
            observations["raised_route_steps"] = raised_route_states
            terrace = _location(emu, symbols["gFieldSysPtr"])
            terrace_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["irregular_terrace"] = {"location": terrace, "height": terrace_height}
            checks["irregular_raised_path_traversed"] = (
                terrace is not None and (terrace["x"], terrace["z"]) == (18, 23)
                and terrace_height["current_height"] == 4
                and terrace_height["position_y_fx32"] == 2 * 65536
            )
            screenshots["raised_terrace"] = _capture(emu, artifact_dir / "raised-terrace.png")

            ramp_b_states = []
            for target_z in (24, 25, 26, 27):
                _press(emu, Keys.KEY_DOWN, deadline, after=60)
                ramp_b_states.append({
                    "location": _location(emu, symbols["gFieldSysPtr"]),
                    "height": _height_state(emu, symbols["gFieldSysPtr"]),
                })
            observations["transition_b"] = ramp_b_states
            checks["transition_b_traversed"] = (
                [(state["location"]["x"], state["location"]["z"]) for state in ramp_b_states]
                == [(18, 24), (18, 25), (18, 26), (18, 27)]
            )
            checks["transition_b_height_progression"] = (
                [state["height"]["current_height"] for state in ramp_b_states] == [3, 1, 0, 0]
                and ramp_b_states[-1]["height"]["position_y_fx32"] == 0
            )
            screenshots["transition_b"] = _capture(emu, artifact_dir / "transition-b.png")

            for _ in range(4):
                _press(emu, Keys.KEY_LEFT, deadline, after=60)
            lower_after = _location(emu, symbols["gFieldSysPtr"])
            lower_after_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["lower_after_route"] = {"location": lower_after, "height": lower_after_height}
            checks["lower_movement_after_second_transition"] = (
                lower_after is not None and (lower_after["x"], lower_after["z"]) == (14, 27)
                and lower_after_height["current_height"] == 0
            )
            _cycle(emu, 600, deadline)
            stable = _location(emu, symbols["gFieldSysPtr"])
            stable_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["after_stability_window"] = {"location": stable, "height": stable_height}
            checks["rom_stable_600_frames"] = (
                bool(emu.is_running()) and stable is not None
                and (stable["map"], stable["x"], stable["z"]) == (target_header, 14, 27)
                and stable_height["current_height"] == 0
            )
            payload["success"] = all(checks.values())
            if not payload["success"]:
                payload["error"] = "one or more Stage 3D runtime assertions failed"
            return 0 if payload["success"] else 1
        if fixture["schema_version"] == 2:
            observations["bdhc_runtime"] = _bdhc_runtime_state(emu, symbols["gFieldSysPtr"])
            checks["parsed_bdhc_loaded"] = any(
                entry.get("ready") == 1 and entry.get("stripe_count") == 3
                for entry in observations["bdhc_runtime"]
            )
            checks["event_fixture_is_empty"] = counts == {
                "background": 0, "npc": 0, "warp": 0, "coordinate": 0,
            }
            lower_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["lower_height"] = lower_height
            checks["initial_height_is_lower"] = lower_height["current_height"] == 0
            screenshots["lower_terrain"] = _capture(emu, artifact_dir / "lower-terrain.png")

            _press(emu, Keys.KEY_LEFT, deadline)
            lower_left = _location(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_RIGHT, deadline)
            lower_back = _location(emu, symbols["gFieldSysPtr"])
            observations["lower_movement"] = [lower_left, lower_back]
            checks["lower_terrain_movement"] = (
                lower_left is not None and lower_back is not None
                and (lower_left["x"], lower_left["z"]) == (13, 12)
                and (lower_back["x"], lower_back["z"]) == (14, 12)
            )

            _press(emu, Keys.KEY_RIGHT, deadline)
            lower_edge = _location(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_RIGHT, deadline)
            lower_blocked = _location(emu, symbols["gFieldSysPtr"])
            observations["lower_boundary"] = [lower_edge, lower_blocked]
            checks["direct_lower_boundary_blocked"] = (
                lower_edge is not None and lower_blocked is not None
                and (lower_edge["x"], lower_edge["z"]) == (15, 12)
                and (lower_blocked["x"], lower_blocked["z"]) == (15, 12)
            )
            screenshots["lower_boundary"] = _capture(emu, artifact_dir / "lower-boundary.png")
            _press(emu, Keys.KEY_LEFT, deadline)
            for _ in range(4):
                _press(emu, Keys.KEY_DOWN, deadline)

            transition_states = []
            for _ in range(4):
                _press(emu, Keys.KEY_RIGHT, deadline, after=60)
                transition_states.append({
                    "location": _location(emu, symbols["gFieldSysPtr"]),
                    "height": _height_state(emu, symbols["gFieldSysPtr"]),
                })
            raised = transition_states[-1]["location"]
            raised_height = transition_states[-1]["height"]
            observations["transition_states"] = transition_states
            checks["intended_transition_traversed"] = (
                raised is not None and (raised["x"], raised["z"]) == (18, 16)
            )
            checks["raised_height_confirmed"] = (
                raised_height["current_height"] == 4
                and raised_height["position_y_fx32"] == 2 * 65536
                and raised_height["position_y_fx32"] > lower_height["position_y_fx32"]
            )
            screenshots["raised_terrain"] = _capture(emu, artifact_dir / "raised-terrain.png")

            _press(emu, Keys.KEY_UP, deadline, after=60)
            raised_right = _location(emu, symbols["gFieldSysPtr"])
            raised_right_height = _height_state(emu, symbols["gFieldSysPtr"])
            _press(emu, Keys.KEY_DOWN, deadline, after=60)
            raised_back = _location(emu, symbols["gFieldSysPtr"])
            observations["raised_movement"] = [raised_right, raised_back, raised_right_height]
            checks["raised_terrain_movement"] = (
                raised_right is not None and raised_back is not None
                and (raised_right["x"], raised_right["z"]) == (18, 15)
                and (raised_back["x"], raised_back["z"]) == (18, 16)
                and raised_right_height["current_height"] == 4
            )

            for _ in range(4):
                _press(emu, Keys.KEY_UP, deadline)
            raised_edge = _location(emu, symbols["gFieldSysPtr"])
            raised_boundary_steps = []
            for _ in range(3):
                _press(emu, Keys.KEY_LEFT, deadline, after=60)
                raised_boundary_steps.append(_location(emu, symbols["gFieldSysPtr"]))
            raised_blocked = raised_boundary_steps[-1]
            blocked_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["raised_boundary"] = [
                raised_edge, *raised_boundary_steps, blocked_height,
            ]
            checks["raised_boundary_blocked"] = (
                raised_edge is not None and raised_blocked is not None
                and (raised_edge["x"], raised_edge["z"]) == (18, 12)
                and (raised_boundary_steps[0]["x"], raised_boundary_steps[0]["z"]) == (17, 12)
                and (raised_boundary_steps[1]["x"], raised_boundary_steps[1]["z"]) == (16, 12)
                and (raised_blocked["x"], raised_blocked["z"]) == (16, 12)
            )
            checks["raised_boundary_preserves_height"] = blocked_height["current_height"] == 4
            screenshots["raised_boundary"] = _capture(emu, artifact_dir / "raised-boundary.png")

            for _ in range(2):
                _press(emu, Keys.KEY_RIGHT, deadline, after=60)
            for _ in range(4):
                _press(emu, Keys.KEY_DOWN, deadline)
            for _ in range(4):
                _press(emu, Keys.KEY_LEFT, deadline, after=60)
            returned = _location(emu, symbols["gFieldSysPtr"])
            returned_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["returned_lower"] = {"location": returned, "height": returned_height}
            checks["returned_to_lower_terrain"] = (
                returned is not None and (returned["x"], returned["z"]) == (14, 16)
                and returned_height["current_height"] == 0
                and returned_height["position_y_fx32"] == lower_height["position_y_fx32"]
            )
            screenshots["returned_lower"] = _capture(emu, artifact_dir / "returned-lower.png")

            _cycle(emu, 600, deadline)
            stable = _location(emu, symbols["gFieldSysPtr"])
            stable_height = _height_state(emu, symbols["gFieldSysPtr"])
            observations["after_stability_window"] = {"location": stable, "height": stable_height}
            checks["rom_stable_600_frames"] = (
                bool(emu.is_running()) and stable is not None and stable["map"] == target_header
                and stable_height["current_height"] == 0
            )
            payload["success"] = all(checks.values())
            if not payload["success"]:
                payload["error"] = "one or more Stage 3A runtime assertions failed"
            return 0 if payload["success"] else 1

        observations["warp_events"] = _warp_events(emu, symbols["gFieldSysPtr"], counts["warp"])
        checks["npc_loaded"] = counts == {"background": 0, "npc": 1, "warp": 2, "coordinate": 0}
        screenshots["map_loaded"] = _capture(emu, artifact_dir / "map-loaded.png")

        _press(emu, Keys.KEY_RIGHT, deadline)
        blocked = _location(emu, symbols["gFieldSysPtr"])
        observations["after_blocked_right"] = blocked
        checks["blocked_tile_prevents_movement"] = blocked is not None and (blocked["x"], blocked["z"]) == (16, 16)

        _press(emu, Keys.KEY_LEFT, deadline)
        walked_left = _location(emu, symbols["gFieldSysPtr"])
        _press(emu, Keys.KEY_RIGHT, deadline)
        walked_back = _location(emu, symbols["gFieldSysPtr"])
        observations["walkable_path"] = [walked_left, walked_back]
        checks["walkable_terrain_traversed"] = (
            walked_left is not None and walked_back is not None
            and (walked_left["x"], walked_left["z"]) == (15, 16)
            and (walked_back["x"], walked_back["z"]) == (16, 16)
        )

        _press(emu, Keys.KEY_UP, deadline)
        _press(emu, Keys.KEY_A, deadline, after=90)
        dialogue_marker = _read_u32(emu, symbols["gStage2ProofDialogueSeen"])
        observations["dialogue_marker"] = dialogue_marker
        checks["npc_interaction_and_dialogue"] = dialogue_marker == 1
        screenshots["dialogue"] = _capture(emu, artifact_dir / "dialogue.png")
        checks["dialogue_frame_changed"] = (
            screenshots["dialogue"]["pixel_sha256"] != screenshots["map_loaded"]["pixel_sha256"]
        )
        _press(emu, Keys.KEY_A, deadline, after=60)

        _press(emu, Keys.KEY_DOWN, deadline)
        _press(emu, Keys.KEY_DOWN, deadline)
        _press(emu, Keys.KEY_DOWN, deadline, held=30, after=35)
        expected_warp_index = fixture["warps"][0]["destination_warp"]
        expected_warp = fixture["warps"][expected_warp_index]
        expected_exit = (expected_warp["x"], expected_warp["z"] + 1)
        warp_result = None
        for _ in range(20):
            _cycle(emu, 30, deadline)
            warp_result = _location(emu, symbols["gFieldSysPtr"])
            if warp_result is not None and (warp_result["x"], warp_result["z"]) == expected_exit:
                break
        observations["warp_destination"] = warp_result
        observations["warp_tile_behavior"] = _read_u32(emu, symbols["gStage2ProofMetatileBehavior"])
        observations["warp_behavior_seen"] = _read_u32(emu, symbols["gStage2ProofWarpBehaviorSeen"])
        checks["warp_permission_seen"] = observations["warp_behavior_seen"] == 1
        checks["warp_events_loaded"] = observations["warp_events"] == [
            {
                "x": warp["x"], "z": warp["z"], "header": warp["destination_header"],
                "anchor": warp["destination_warp"], "height": 0,
            }
            for warp in fixture["warps"]
        ]
        checks["warp_reached_reciprocal_destination"] = (
            warp_result is not None
            and warp_result["map"] == target_header
            and warp_result["warp"] == expected_warp_index
            # A south entrance places the player one tile outside its anchor.
            and (warp_result["x"], warp_result["z"]) == expected_exit
        )
        screenshots["warp_destination"] = _capture(emu, artifact_dir / "warp-destination.png")

        _cycle(emu, 600, deadline)
        stable = _location(emu, symbols["gFieldSysPtr"])
        observations["after_stability_window"] = stable
        checks["rom_stable"] = bool(emu.is_running()) and stable is not None and stable["map"] == target_header
        payload["success"] = all(checks.values())
        if not payload["success"]:
            payload["error"] = "one or more Stage 2 runtime assertions failed"
    except Exception as error:
        payload.update({"success": False, "error_type": type(error).__name__, "error": str(error)})
    finally:
        if emu is not None:
            try:
                emu.destroy()
            except Exception as error:
                payload["cleanup_error"] = str(error)
        payload["duration_seconds"] = round(time.monotonic() - started, 6)
        payload["completed_at"] = utc_now()
        write_json_report(result_path, payload)
    return 0 if payload["success"] else 1


def run_world_test(
    root: Path = PROJECT_ROOT,
    fixture_path: Path = DEFAULT_FIXTURE,
    timeout_seconds: float = 180,
) -> dict[str, object]:
    root = root.resolve()
    fixture = load_fixture(fixture_path)
    namespace = fixture.get("artifact_namespace", "stage2")
    artifact_dir = root / "build" / namespace / "emulator"
    report_path = artifact_dir / "report.json"
    worker_path = artifact_dir / ".worker.json"
    log_path = artifact_dir / "worker.log"
    rom_path = root / GENERATED_ROM_NAME
    errors: list[str] = []
    report: dict[str, object] = {
        "schema_version": fixture["schema_version"],
        "operation": "stage3c_registry_emulator" if namespace == "stage3c" else {
            1: "stage2_map_emulator",
            2: "stage3a_height_emulator",
            3: "stage3b_multimap_emulator",
            5: "stage3d_geometry_emulator",
        }[fixture["schema_version"]],
        "success": False,
        "rom_sha256": sha256_file(rom_path) if rom_path.is_file() else None,
        "artifacts": {"directory": str(artifact_dir), "report": str(report_path), "log": str(log_path)},
        "errors": errors,
    }
    targets = (artifact_dir, report_path, worker_path, log_path)
    if any(path_is_git_ignored(root, path) is not True for path in targets):
        errors.append("refusing to write world emulator evidence outside ignored paths")
        return report
    if not rom_path.is_file():
        errors.append(f"generated ROM is missing: {rom_path}")
        return report
    artifact_dir.mkdir(parents=True, exist_ok=True)
    worker_path.unlink(missing_ok=True)
    command = [
        sys.executable, "-m", "tools.pokeagent.world_emulator", "--worker",
        "--root", str(root), "--rom", str(rom_path), "--fixture", str(fixture_path),
        "--result", str(worker_path), "--artifact-dir", str(artifact_dir),
        "--timeout", str(max(1, timeout_seconds - 2)),
    ]
    command_result = run_command(
        command,
        cwd=root,
        timeout_seconds=timeout_seconds,
        log_path=log_path,
        env_overrides={"SDL_VIDEODRIVER": "dummy"},
    )
    worker: dict[str, object] | None = None
    if worker_path.is_file():
        try:
            worker = json.loads(worker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"worker result is unreadable: {error}")
    else:
        errors.append("emulator worker did not produce a structured result")
    if not command_result.succeeded:
        errors.append("emulator worker timed out" if command_result.timed_out else f"emulator worker exited {command_result.exit_code}")
    if worker is not None and not worker.get("success"):
        errors.append(str(worker.get("error", "world emulator worker failed")))
    report.update({
        "command": command_result.to_dict(),
        "worker": worker,
        "success": not errors,
        "completed_at": utc_now(),
    })
    worker_path.unlink(missing_ok=True)
    write_json_report(report_path, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return _worker(args.root, args.rom, args.fixture, args.result, args.artifact_dir, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
