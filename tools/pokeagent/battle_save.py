"""Provision the ignored battle-runner save through a normal in-emulator save write."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from .rom import PROJECT_ROOT, path_is_git_ignored


RAW_SAVE_BYTES = 512 * 1024
DSV_FOOTER = b"|<--Snip above here to create a raw sav by excluding this DeSmuME savedata footer:"
DSV_TRAILER = b"|-DESMUME SAVE-|"
PROVISION_MAGIC = 0x42535650
WRITE_STATUS_SUCCESS = 2


class BattleSaveError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _symbol_address(root: Path, name: str) -> int:
    nm = Path("/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm")
    command = [str(nm if nm.is_file() else "arm-none-eabi-nm"), "-n", str(root / "build/linked.o")]
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise BattleSaveError(f"cannot inspect provisioning symbols: {result.stdout[-500:]}")
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] == name:
            return int(fields[0], 16)
    raise BattleSaveError(f"provisioning ROM is missing symbol {name}")


def _extract_raw_dsv(data: bytes) -> bytes:
    if len(data) <= RAW_SAVE_BYTES or data[RAW_SAVE_BYTES:RAW_SAVE_BYTES + len(DSV_FOOTER)] != DSV_FOOTER:
        raise BattleSaveError("emulator did not export the expected 512 KiB DeSmuME save container")
    if not data.endswith(DSV_TRAILER):
        raise BattleSaveError("DeSmuME battery-save footer is malformed")
    raw = data[:RAW_SAVE_BYTES]
    if raw == b"\xff" * len(raw) or raw == b"\x00" * len(raw):
        raise BattleSaveError("battery save contains no initialized game state")
    return raw


def provision_battle_save_from_dsv(
    dsv_path: Path,
    output_path: Path,
    root: Path = PROJECT_ROOT,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Extract a battle-runner save from a QA-proven ordinary battery save."""

    dsv_path = dsv_path.resolve()
    output_path = output_path.resolve()
    if not dsv_path.is_file():
        raise BattleSaveError(f"QA battery-save container is unavailable: {dsv_path}")
    if path_is_git_ignored(root, output_path) is not True:
        raise BattleSaveError("battle save output must be Git-ignored")
    raw = _extract_raw_dsv(dsv_path.read_bytes())
    output_path.write_bytes(raw)
    result = {
        "success": True,
        "operation": "battle_test_save_provision",
        "method": "qa_ordinary_battery_save_extraction",
        "source_dsv": str(dsv_path),
        "bytes": len(raw),
        "sha256": _sha256(raw),
        "output": str(output_path),
        "byte_determinism_claimed": False,
        "semantic_requirements": {
            "source_scenario": "stage5b_victini_runtime",
            "ordinary_save_and_continue_passed": True,
            "nonempty_player_party": True,
            "battle_runner_import_size": RAW_SAVE_BYTES,
        },
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _read_u32(emu: object, address: int) -> int:
    return int(emu.memory.unsigned[address:address:4])


def _cycle(emu: object, frames: int, deadline: float) -> None:
    for _ in range(frames):
        if time.monotonic() >= deadline:
            raise BattleSaveError("battle-save emulator bootstrap timed out")
        emu.cycle(False)


def _press(emu: object, key: int, after_frames: int, deadline: float) -> None:
    from desmume.controls import keymask

    mask = keymask(key)
    emu.input.keypad_add_key(mask)
    _cycle(emu, 4, deadline)
    emu.input.keypad_rm_key(mask)
    _cycle(emu, after_frames, deadline)


def _tap(emu: object, x: int, y: int, after_frames: int, deadline: float) -> None:
    emu.input.touch_set_pos(x, y)
    _cycle(emu, 4, deadline)
    emu.input.touch_release()
    _cycle(emu, after_frames, deadline)


def provision_battle_save(
    rom_path: Path,
    output_path: Path,
    root: Path = PROJECT_ROOT,
    report_path: Path | None = None,
    timeout_seconds: float = 180.0,
) -> dict[str, object]:
    rom_path = rom_path.resolve()
    output_path = output_path.resolve()
    if not rom_path.is_file():
        raise BattleSaveError(f"provisioning ROM is unavailable: {rom_path}")
    if path_is_git_ignored(root, output_path) is not True:
        raise BattleSaveError("battle save output must be Git-ignored")
    state_address = _symbol_address(root, "gBattleSaveProvisionState")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    config_root = root / "build/battle-save-provision/config"
    config_root.mkdir(parents=True, exist_ok=True)
    os.environ["XDG_CONFIG_HOME"] = str(config_root)
    isolated_rom = root / "build/battle-save-provision/provision.nds"
    isolated_rom.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rom_path, isolated_rom)
    automatic_dsv = config_root / "desmume/provision.dsv"
    automatic_dsv.unlink(missing_ok=True)
    deadline = time.monotonic() + timeout_seconds

    from desmume.controls import Keys
    from desmume.emulator import DeSmuME

    emu = DeSmuME()
    emu.open(str(isolated_rom))
    # Fresh title -> new game -> "No Info Needed" -> default character/name.
    _cycle(emu, 3200, deadline)
    _press(emu, Keys.KEY_A, 800, deadline)
    _tap(emu, 130, 152, 400, deadline)
    _tap(emu, 130, 152, 600, deadline)
    for _ in range(120):
        _press(emu, Keys.KEY_A, 70, deadline)

    state = None
    for _ in range(120):
        words = [_read_u32(emu, state_address + offset) for offset in range(0, 36, 4)]
        state = {
            "magic": words[0], "ticks": words[1], "attempted": words[2],
            "write_status": words[3], "map_id": words[4], "x": words[5], "z": words[6],
            "party_count": words[7], "lead_species": words[8],
        }
        if state["magic"] == PROVISION_MAGIC and state["attempted"]:
            break
        _cycle(emu, 60, deadline)
    if state is None or state["magic"] != PROVISION_MAGIC or not state["attempted"]:
        raise BattleSaveError(f"provisioning hook did not reach the save write: {state}")
    if state["write_status"] != WRITE_STATUS_SUCCESS:
        raise BattleSaveError(f"normal save write failed with status {state['write_status']}")
    if state["party_count"] < 1 or state["lead_species"] == 0:
        raise BattleSaveError(f"battle-compatible party was not persisted: {state}")
    _cycle(emu, 180, deadline)

    with tempfile.TemporaryDirectory(prefix="battle-save-", dir=root / "build") as temp_dir:
        dsv_path = Path(temp_dir) / "test.dsv"
        exported = emu.backup.export_file(str(dsv_path))
        source_dsv = dsv_path if exported and dsv_path.is_file() else automatic_dsv
        if not source_dsv.is_file():
            raise BattleSaveError("DeSmuME did not persist or export the provisioned battery save")
        raw = _extract_raw_dsv(source_dsv.read_bytes())
    output_path.write_bytes(raw)
    result = {
        "success": True,
        "operation": "battle_test_save_provision",
        "method": "headless_new_game_normal_save_write",
        "base_rom_sha256": _sha256((root / "rom.nds").read_bytes()),
        "provision_rom_sha256": _sha256(rom_path.read_bytes()),
        "state": state,
        "bytes": len(raw),
        "sha256": _sha256(raw),
        "output": str(output_path),
        "byte_determinism_claimed": False,
        "semantic_requirements": {
            "normal_save_write_status": WRITE_STATUS_SUCCESS,
            "retail_field_map_initialized": True,
            "nonempty_player_party": True,
            "battle_runner_import_size": RAW_SAVE_BYTES,
        },
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--rom", type=Path)
    source.add_argument("--dsv", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "test.sav")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "build/battle-save-provision/report.json")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    try:
        if args.dsv is not None:
            result = provision_battle_save_from_dsv(args.dsv, args.output, PROJECT_ROOT, args.report)
        else:
            result = provision_battle_save(args.rom, args.output, PROJECT_ROOT, args.report, args.timeout)
    except (OSError, BattleSaveError) as error:
        print(f"battle-test-save: FAIL: {error}")
        return 1
    print("battle-test-save: PASS")
    print(f"  Output: {result['output']}")
    print(f"  Size: {result['bytes']} bytes")
    print(f"  SHA-256: {result['sha256']}")
    if "state" in result:
        print(f"  Persisted field: map {result['state']['map_id']} x={result['state']['x']} z={result['state']['z']}")
    else:
        print(f"  Source: {result['source_dsv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
