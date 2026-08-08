"""Headless emulator adapter and trace executor for declarative QA scenarios."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import time
from typing import Any

from .qa import QAError, load_scenario
from .rom import utc_now, write_json_report
from .world import MAP_TILES, load_fixture
from .world_emulator import (
    _active_header_banks,
    _bdhc_runtime_state,
    _capture,
    _event_counts,
    _height_state,
    _location,
    _read_u8,
    _read_u16,
    _read_u32,
    _stage3b_runtime_state,
    _symbols,
)


DIRECTION_BUTTON = {"north": "up", "east": "right", "south": "down", "west": "left"}
DIRECTION_DELTA = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}


class QAExecutionError(QAError):
    """A bounded action or semantic assertion failed at runtime."""


class QAEmulatorAdapter:
    """Revision-specific semantic facade over py-desmume and HG field memory."""

    def __init__(self, root: Path, rom_path: Path, fixture_path: Path, artifact_dir: Path, deadline: float) -> None:
        from desmume.emulator import DeSmuME

        self.root = root
        self.fixture_path = fixture_path
        self.fixture = load_fixture(fixture_path)
        self.artifact_dir = artifact_dir
        self.deadline = deadline
        self.frame = 0
        self.last_movement: dict[str, object] | None = None
        self.screenshots: dict[str, dict[str, object]] = {}
        self.held: set[str] = set()
        self.symbols = _symbols(root, require_stage3e2=self.fixture["schema_version"] == 7)
        self.project_header_table = self.symbols.get("gProjectMapHeaders")
        self.emu = DeSmuME()
        self.emu.open(str(rom_path))

    def _key(self, button: str) -> int:
        from desmume.controls import Keys

        try:
            return int(getattr(Keys, f"KEY_{button.upper()}"))
        except AttributeError as error:
            raise QAExecutionError("invalid_button", f"emulator does not expose button {button}") from error

    def _mask(self, button: str) -> int:
        from desmume.controls import keymask

        return int(keymask(self._key(button)))

    def wait(self, frames: int) -> None:
        for _ in range(frames):
            if time.monotonic() >= self.deadline:
                raise QAExecutionError("worker_timeout", "QA emulator worker exceeded its deadline")
            self.emu.cycle(False)
            self.frame += 1

    def press(self, button: str, held_frames: int = 4, after_frames: int = 35) -> None:
        mask = self._mask(button)
        self.emu.input.keypad_add_key(mask)
        try:
            self.wait(held_frames)
        finally:
            self.emu.input.keypad_rm_key(mask)
        self.wait(after_frames)

    def hold(self, button: str, frames: int) -> None:
        if button not in self.held:
            self.emu.input.keypad_add_key(self._mask(button))
            self.held.add(button)
        self.wait(frames)

    def release(self, button: str, after_frames: int = 0) -> None:
        self.emu.input.keypad_rm_key(self._mask(button))
        self.held.discard(button)
        self.wait(after_frames)

    def _location_required(self) -> dict[str, int]:
        try:
            location = _location(self.emu, self.symbols["gFieldSysPtr"])
        except (RuntimeError, ValueError, TypeError) as error:
            raise QAExecutionError("field_not_ready", "field location is not available") from error
        if location is None:
            raise QAExecutionError("field_not_ready", "field location is not available")
        return location

    def controlled_entry(self) -> None:
        self.wait(3200)
        self.press("a", after_frames=800)
        self.emu.input.touch_set_pos(130, 152)
        self.wait(4)
        self.emu.input.touch_release()
        self.wait(400)
        if self.fixture["schema_version"] in (3, 6, 7):
            start_spec = self.fixture["maps"][self.fixture["player_start"]["map"]]
            target_header = start_spec["map_header"]
        else:
            target_header = self.fixture["slots"]["map_header"]
        current = None
        for _ in range(75):
            current = _location(self.emu, self.symbols["gFieldSysPtr"])
            if current is not None and current["map"] == target_header:
                break
            self.press("a", after_frames=60)
        else:
            raise QAExecutionError(
                "controlled_entry_failed", f"controlled entry did not reach map {target_header}",
                expected={"map_id": target_header}, observed=current,
            )
        self.wait(180)

    def continue_game(self, expected_map_id: int | None = None, timeout_frames: int = 7200) -> None:
        initial = min(3200, timeout_frames)
        self.wait(initial)
        remaining = timeout_frames - initial
        current = None
        while remaining > 0:
            current = _location(self.emu, self.symbols["gFieldSysPtr"])
            if current is not None and (expected_map_id is None or current["map"] == expected_map_id):
                self.wait(240)
                return
            after = min(80, max(0, remaining - 4))
            self.press("a", after_frames=after)
            remaining -= 4 + after
        raise QAExecutionError(
            "continue_failed", "Continue did not reach the expected field state",
            expected={"map_id": expected_map_id}, observed=current,
        )

    def reset(self) -> None:
        for button in list(self.held):
            self.emu.input.keypad_rm_key(self._mask(button))
        self.held.clear()
        self.emu.reset()

    def move(self, direction: str, tiles: int, max_attempts: int) -> dict[str, object]:
        start = self._location_required()
        current = start
        dx, dz = DIRECTION_DELTA[direction]
        attempts = 0
        for tile in range(tiles):
            if attempts >= max_attempts:
                raise QAExecutionError("movement_attempt_limit", "movement exceeded max_attempts")
            before = current
            self.press(DIRECTION_BUTTON[direction])
            attempts += 1
            current = self._location_required()
            expected = (before["x"] + dx, before["z"] + dz)
            observed = (current["x"], current["z"])
            if observed != expected:
                self.last_movement = {
                    "direction": direction, "requested_tiles": tiles, "completed_tiles": tile,
                    "attempts": attempts, "start": start, "end": current, "blocked": observed == (before["x"], before["z"]),
                }
                raise QAExecutionError(
                    "movement_blocked" if self.last_movement["blocked"] else "movement_unexpected",
                    f"movement {direction} did not reach the next tile",
                    expected={"x": expected[0], "z": expected[1]}, observed=current,
                )
        self.last_movement = {
            "direction": direction, "requested_tiles": tiles, "completed_tiles": tiles,
            "attempts": attempts, "start": start, "end": current, "blocked": False,
        }
        return self.last_movement

    def move_to(self, target: dict[str, int], max_attempts: int) -> dict[str, object]:
        start = self._location_required()
        attempts = 0
        segments = []
        for axis in ("x", "z"):
            if axis not in target:
                continue
            while self._location_required()[axis] != target[axis]:
                current = self._location_required()
                direction = (
                    "east" if axis == "x" and current[axis] < target[axis] else
                    "west" if axis == "x" else
                    "south" if current[axis] < target[axis] else "north"
                )
                if attempts >= max_attempts:
                    raise QAExecutionError(
                        "movement_attempt_limit", "move target exceeded max_attempts",
                        expected=target, observed=current,
                    )
                segment = self.move(direction, 1, 1)
                attempts += 1
                segments.append(segment)
        current = self._location_required()
        self.last_movement = {
            "target": target, "attempts": attempts, "start": start, "end": current,
            "segments": segments, "blocked": False,
        }
        return self.last_movement

    def assert_blocked(self, direction: str) -> tuple[dict[str, object], dict[str, object]]:
        before = self.snapshot()
        self.press(DIRECTION_BUTTON[direction], after_frames=60)
        after = self.snapshot()
        blocked = after.get("position") == before.get("position")
        self.last_movement = {
            "direction": direction, "requested_tiles": 1, "completed_tiles": 0 if blocked else 1,
            "start": before.get("location"), "end": after.get("location"), "blocked": blocked,
        }
        if not blocked:
            raise QAExecutionError(
                "collision_not_blocked", f"expected collision to block movement {direction}",
                expected={"position": before.get("position")}, observed={"position": after.get("position")},
            )
        return before, after

    def assert_native_transition(
        self, direction: str, from_map_id: int, to_map_id: int, no_warp: bool,
    ) -> tuple[dict[str, object], dict[str, object]]:
        before = self.snapshot()
        self.press(DIRECTION_BUTTON[direction], after_frames=60)
        after = self.snapshot()
        expected = {"from_map_id": from_map_id, "to_map_id": to_map_id, "no_warp": no_warp}
        success = before.get("map_id") == from_map_id and after.get("map_id") == to_map_id
        if no_warp:
            success = success and before.get("warp_state") == after.get("warp_state")
        if not success:
            raise QAExecutionError(
                "native_transition_failed", f"native transition {from_map_id}->{to_map_id} failed",
                expected=expected,
                observed={"before": before, "after": after},
            )
        self.last_movement = {
            "direction": direction, "requested_tiles": 1, "completed_tiles": 1,
            "start": before.get("location"), "end": after.get("location"), "blocked": False,
        }
        return before, after

    def capture(self, name: str) -> dict[str, object]:
        metadata = _capture(self.emu, self.artifact_dir / "screenshots" / f"{name}.png")
        metadata["frame"] = self.frame
        metadata["state"] = self.snapshot()
        self.screenshots[name] = metadata
        return metadata

    def read_memory(self, symbol: str, offset: int, width: int) -> int:
        if symbol not in self.symbols:
            raise QAExecutionError("unknown_runtime_symbol", f"runtime symbol is unavailable: {symbol}")
        address = self.symbols[symbol] + offset
        return {1: _read_u8, 2: _read_u16, 4: _read_u32}[width](self.emu, address)

    def snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "frame": self.frame,
            "running": bool(self.emu.is_running()),
            "location": None,
            "map_id": None,
            "position": None,
            "local_position": None,
            "height": None,
            "event_counts": None,
            "matrix": None,
            "matrix_id": None,
            "map_member": None,
            "header_fields": None,
            "warp_state": None,
            "bdhc": None,
            "markers": {},
        }
        try:
            location = _location(self.emu, self.symbols["gFieldSysPtr"])
        except (RuntimeError, ValueError, TypeError):
            return snapshot
        if location is None:
            return snapshot
        snapshot.update({
            "location": location,
            "map_id": location["map"],
            "position": {"x": location["x"], "z": location["z"]},
            "local_position": {"x": location["x"] % MAP_TILES, "z": location["z"] % MAP_TILES},
            "warp_state": location["warp"],
        })
        try:
            world = _stage3b_runtime_state(self.emu, self.symbols["gFieldSysPtr"])
            snapshot["matrix"] = world["matrix"]
            snapshot["map_member"] = world["load_manager"]["active_member"]
        except (RuntimeError, ValueError, TypeError):
            pass
        try:
            header = _active_header_banks(self.emu, location["map"], self.project_header_table)
            snapshot["header_fields"] = header
            snapshot["matrix_id"] = header["matrix"]
        except (RuntimeError, ValueError):
            pass
        try:
            snapshot["height"] = _height_state(self.emu, self.symbols["gFieldSysPtr"])
        except (RuntimeError, ValueError):
            pass
        try:
            snapshot["event_counts"] = _event_counts(self.emu, self.symbols["gFieldSysPtr"])
        except (RuntimeError, ValueError):
            pass
        try:
            bdhc = _bdhc_runtime_state(self.emu, self.symbols["gFieldSysPtr"])
            snapshot["bdhc"] = {
                "ready": any(entry.get("ready") == 1 for entry in bdhc),
                "stripe_counts": sorted({entry.get("stripe_count") for entry in bdhc if entry.get("ready") == 1}),
                "slots": bdhc,
            }
        except (RuntimeError, ValueError):
            pass
        snapshot["markers"] = {
            symbol: self.read_memory(symbol, 0, 4)
            for symbol in sorted(self.symbols)
            if symbol.startswith("gStage") and "HeaderLookup" not in symbol and "Lookups" not in symbol
        }
        return snapshot

    def close(self) -> None:
        for button in list(self.held):
            try:
                self.release(button)
            except Exception:
                pass
        try:
            self.emu.destroy()
        except Exception:
            pass


def _subset(observed: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(key in observed and _subset(observed[key], value) for key, value in expected.items())
    return observed == expected


def _assert_semantic(adapter: QAEmulatorAdapter, step: dict[str, Any]) -> dict[str, object]:
    kind = step["assert"]
    before = adapter.snapshot()
    if kind == "collision_blocked":
        adapter.assert_blocked(step["direction"])
        return {"expected": {"blocked": True, "direction": step["direction"]}, "observed": adapter.last_movement}
    if kind == "native_transition":
        transition = adapter.assert_native_transition(
            step["direction"], step["from_map_id"], step["to_map_id"], step.get("no_warp", True),
        )
        return {"expected": step, "observed": {"before": transition[0], "after": transition[1]}}
    if kind == "rom_running":
        expected, observed = step["value"], before["running"]
    elif kind in {"map_id", "matrix_id", "map_member", "warp_state"}:
        expected, observed = step["value"], before[kind]
    elif kind in {"position", "local_position"}:
        expected, observed = {"x": step["x"], "z": step["z"]}, before[kind]
    elif kind == "height":
        expected = {name: step[name] for name in ("current_height", "position_y_fx32") if name in step}
        observed = before["height"]
    elif kind == "event_counts":
        expected = {name: value for name, value in step.items() if name != "assert"}
        observed = before["event_counts"]
    elif kind == "marker":
        expected = step["value"]
        observed = adapter.read_memory(step["symbol"], step.get("offset", 0), step.get("width", 4))
    elif kind == "memory_value":
        expected = step["value"]
        observed = adapter.read_memory(step["symbol"], step.get("offset", 0), step.get("width", 4))
        if "mask" in step:
            observed &= step["mask"]
    elif kind == "screenshot_valid":
        expected = {"exists": True, "valid_png": True}
        capture = adapter.screenshots.get(step["name"])
        observed = {
            "exists": capture is not None and Path(str(capture["path"])).is_file(),
            "valid_png": capture is not None and capture.get("width", 0) > 0 and capture.get("height", 0) > 0 and capture.get("unique_colors", 0) > 1,
        }
    elif kind in {"header_field", "resource_id"}:
        expected = step["value"]
        fields = before.get("header_fields") or {}
        observed = fields.get(step["field"])
    elif kind == "bdhc_ready":
        expected = {"ready": step["value"]}
        if "stripe_count" in step:
            expected["stripe_count"] = step["stripe_count"]
        bdhc = before.get("bdhc") or {}
        observed = {"ready": bdhc.get("ready")}
        if "stripe_count" in step:
            observed["stripe_count"] = step["stripe_count"] if step["stripe_count"] in bdhc.get("stripe_counts", []) else None
    elif kind == "movement_succeeded":
        expected = step["value"]
        observed = bool(adapter.last_movement and not adapter.last_movement.get("blocked"))
    else:
        raise QAExecutionError("unknown_assertion", f"unsupported runtime assertion {kind}")
    if not _subset(observed, expected):
        raise QAExecutionError(
            "semantic_assertion_failed", f"assertion {kind} failed",
            assertion=kind, expected=expected, observed=observed,
        )
    return {"expected": expected, "observed": observed}


def execute_scenario(adapter: QAEmulatorAdapter, scenario: dict[str, Any]) -> dict[str, object]:
    trace: list[dict[str, object]] = []
    assertion_passes = 0
    errors: list[dict[str, object]] = []
    if scenario["entry"]["mode"] == "new_game_controlled":
        adapter.controlled_entry()
    else:
        adapter.continue_game()
    for index, step in enumerate(scenario["steps"]):
        start_frame = adapter.frame
        before = adapter.snapshot()
        entry: dict[str, object] = {
            "index": index, "step": step, "start_frame": start_frame,
            "state_before": before, "success": False,
        }
        try:
            result: object = None
            action = step.get("action")
            if action == "wait":
                adapter.wait(step["frames"])
            elif action == "press":
                adapter.press(step["button"], step.get("held_frames", 4), step.get("after_frames", 35))
            elif action == "hold":
                adapter.hold(step["button"], step["frames"])
            elif action == "release":
                adapter.release(step["button"], step.get("after_frames", 0))
            elif action == "move":
                result = (
                    adapter.move_to(step["target"], step.get("max_attempts", 96))
                    if "target" in step else
                    adapter.move(step["direction"], step["tiles"], step.get("max_attempts", 96))
                )
            elif action == "interact":
                adapter.press("a", after_frames=step.get("after_frames", 90))
            elif action == "capture":
                result = adapter.capture(step["name"])
            elif action == "reset":
                adapter.reset()
            elif action == "continue":
                adapter.continue_game(step.get("expected_map_id"), step.get("timeout_frames", 7200))
            elif action is not None:
                raise QAExecutionError("unknown_action", f"unsupported runtime action {action}")
            else:
                result = _assert_semantic(adapter, step)
                assertion_passes += 1
            entry.update({
                "success": True, "result": result, "end_frame": adapter.frame,
                "duration_frames": adapter.frame - start_frame, "state_after": adapter.snapshot(),
            })
        except QAError as error:
            diagnostic = error.as_dict()
            diagnostic["step_index"] = index
            diagnostic["step"] = step
            diagnostic["last_action"] = next(
                (previous["step"] for previous in reversed(trace) if "action" in previous["step"]), None,
            )
            entry.update({
                "end_frame": adapter.frame, "duration_frames": adapter.frame - start_frame,
                "state_after": adapter.snapshot(), "error": diagnostic,
            })
            errors.append(diagnostic)
            trace.append(entry)
            break
        trace.append(entry)
    final_state = adapter.snapshot()
    return {
        "success": not errors and len(trace) == len(scenario["steps"]),
        "trace": trace,
        "errors": errors,
        "assertions_passed": assertion_passes,
        "assertions_total": sum("assert" in step for step in scenario["steps"]),
        "screenshots": adapter.screenshots,
        "final_state": final_state,
    }


def _worker(
    root: Path, rom_path: Path, scenario_path: Path, result_path: Path,
    artifact_dir: Path, timeout_seconds: float,
) -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    started = time.monotonic()
    deadline = started + timeout_seconds
    scenario = load_scenario(scenario_path, root)
    fixture_path = root / scenario["fixture"]
    adapter = None
    execution: dict[str, object] = {
        "success": False, "trace": [], "errors": [], "screenshots": {}, "final_state": None,
        "assertions_passed": 0, "assertions_total": sum("assert" in step for step in scenario["steps"]),
    }
    try:
        adapter = QAEmulatorAdapter(root, rom_path, fixture_path, artifact_dir, deadline)
        execution = execute_scenario(adapter, scenario)
    except QAError as error:
        execution["errors"] = [error.as_dict()]
    except Exception as error:
        execution["errors"] = [{"code": "unexpected_worker_error", "message": str(error), "details": {}}]
    finally:
        if adapter is not None:
            adapter.close()
    trace_path = artifact_dir / "trace.json"
    write_json_report(trace_path, {
        "schema_version": 1, "scenario": scenario["id"], "success": execution["success"],
        "steps": execution["trace"], "errors": execution["errors"],
    })
    try:
        binding_version = version("py-desmume")
    except PackageNotFoundError:
        binding_version = "unknown"
    payload = {
        **execution,
        "schema_version": 1,
        "scenario": scenario["id"],
        "entry_strategy": scenario["entry"]["mode"],
        "emulator": {
            "implementation": "DeSmuME",
            "python_binding": "py-desmume",
            "binding_version": binding_version,
            "version_evidence": str(artifact_dir / "emulator.log"),
        },
        "duration_seconds": round(time.monotonic() - started, 6),
        "completed_at": utc_now(),
        "trace_path": str(trace_path),
    }
    write_json_report(result_path, payload)
    return 0 if payload["success"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return _worker(args.root, args.rom, args.scenario, args.result, args.artifact_dir, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
