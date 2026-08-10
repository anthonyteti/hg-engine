"""Validated declarative gameplay-QA scenarios and bounded worker orchestration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
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


QA_SCHEMA_VERSION = 1
MAX_STEPS = 256
MAX_WAIT_FRAMES = 3600
MAX_HOLD_FRAMES = 600
MAX_MOVE_TILES = 96
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SAFE_CAPTURE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SAFE_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,95}$")
BUTTONS = {"a", "b", "x", "y", "up", "down", "left", "right", "start", "select", "l", "r"}
DIRECTIONS = {"north", "east", "south", "west"}
ACTIONS = {
    "wait", "press", "hold", "release", "move", "interact", "capture", "reset", "continue",
    "write_memory",
}
ASSERTIONS = {
    "rom_running", "map_id", "matrix_id", "map_member", "position", "local_position",
    "height", "event_counts", "warp_state", "marker", "memory_value", "screenshot_valid",
    "header_field", "resource_id", "bdhc_ready", "movement_succeeded", "collision_blocked",
    "native_transition",
}
HEADER_FIELDS = {"matrix", "script", "script_header", "text", "music_day", "music_night", "event"}


class QAError(ValueError):
    """A scenario or QA run failed with a stable machine-readable code."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _require_int(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise QAError("invalid_integer", f"{name} must be an integer from {minimum} through {maximum}")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise QAError("unknown_field", f"{context} contains unsupported fields: {unknown}", fields=unknown)


def _validate_action(step: dict[str, Any], index: int) -> None:
    action = step.get("action")
    if action not in ACTIONS:
        raise QAError("unknown_action", f"step {index} has unknown action {action!r}", step=index)
    if action == "wait":
        _reject_unknown(step, {"action", "frames"}, f"step {index}")
        _require_int(step.get("frames"), "frames", 1, MAX_WAIT_FRAMES)
    elif action == "press":
        _reject_unknown(step, {"action", "button", "held_frames", "after_frames"}, f"step {index}")
        if step.get("button") not in BUTTONS:
            raise QAError("invalid_button", f"step {index} has invalid button {step.get('button')!r}")
        _require_int(step.get("held_frames", 4), "held_frames", 1, 120)
        _require_int(step.get("after_frames", 35), "after_frames", 0, MAX_HOLD_FRAMES)
    elif action == "hold":
        _reject_unknown(step, {"action", "button", "frames"}, f"step {index}")
        if step.get("button") not in BUTTONS:
            raise QAError("invalid_button", f"step {index} has invalid button {step.get('button')!r}")
        _require_int(step.get("frames"), "frames", 1, MAX_HOLD_FRAMES)
    elif action == "release":
        _reject_unknown(step, {"action", "button", "after_frames"}, f"step {index}")
        if step.get("button") not in BUTTONS:
            raise QAError("invalid_button", f"step {index} has invalid button {step.get('button')!r}")
        _require_int(step.get("after_frames", 0), "after_frames", 0, MAX_HOLD_FRAMES)
    elif action == "move":
        _reject_unknown(step, {"action", "direction", "tiles", "target", "max_attempts"}, f"step {index}")
        has_tiles = "direction" in step or "tiles" in step
        has_target = "target" in step
        if has_tiles == has_target:
            raise QAError("invalid_move", f"step {index} move requires direction+tiles or target, not both")
        if has_tiles:
            if step.get("direction") not in DIRECTIONS:
                raise QAError("invalid_direction", f"step {index} has invalid direction {step.get('direction')!r}")
            _require_int(step.get("tiles"), "tiles", 1, MAX_MOVE_TILES)
        else:
            target = step.get("target")
            if not isinstance(target, dict) or not target or not set(target) <= {"x", "z"}:
                raise QAError("invalid_move_target", f"step {index} target must contain x and/or z")
            for axis, value in target.items():
                _require_int(value, f"target.{axis}", -1024, 1024)
        _require_int(step.get("max_attempts", MAX_MOVE_TILES), "max_attempts", 1, MAX_MOVE_TILES)
    elif action == "interact":
        _reject_unknown(step, {"action", "after_frames"}, f"step {index}")
        _require_int(step.get("after_frames", 90), "after_frames", 0, MAX_HOLD_FRAMES)
    elif action == "capture":
        _reject_unknown(step, {"action", "name"}, f"step {index}")
        if not isinstance(step.get("name"), str) or not SAFE_CAPTURE.fullmatch(step["name"]):
            raise QAError("unsafe_capture_name", f"step {index} capture name is unsafe")
    elif action == "reset":
        _reject_unknown(step, {"action"}, f"step {index}")
    elif action == "continue":
        _reject_unknown(step, {"action", "expected_map_id", "timeout_frames"}, f"step {index}")
        if "expected_map_id" in step:
            _require_int(step["expected_map_id"], "expected_map_id", 0, 65535)
        _require_int(step.get("timeout_frames", 7200), "timeout_frames", 60, 12000)
    elif action == "write_memory":
        _reject_unknown(step, {"action", "symbol", "value", "offset", "width", "after_frames"}, f"step {index}")
        if not isinstance(step.get("symbol"), str) or not SAFE_SYMBOL.fullmatch(step["symbol"]):
            raise QAError("invalid_symbol", f"step {index} requires a safe linker symbol")
        _require_int(step.get("value"), "value", 0, 2**32 - 1)
        _require_int(step.get("offset", 0), "offset", 0, 4096)
        if step.get("width", 4) not in (1, 2, 4):
            raise QAError("invalid_memory_width", f"step {index} memory width must be 1, 2, or 4")
        _require_int(step.get("after_frames", 30), "after_frames", 0, MAX_HOLD_FRAMES)


def _validate_assertion(step: dict[str, Any], index: int) -> None:
    assertion = step.get("assert")
    if assertion not in ASSERTIONS:
        raise QAError("unknown_assertion", f"step {index} has unknown assertion {assertion!r}", step=index)
    common = {"assert"}
    if assertion in {"rom_running", "map_id", "matrix_id", "map_member", "warp_state", "movement_succeeded"}:
        _reject_unknown(step, common | {"value"}, f"step {index}")
        if assertion in {"map_id", "matrix_id", "map_member"}:
            _require_int(step.get("value"), "value", 0, 65535)
        elif assertion == "warp_state":
            _require_int(step.get("value"), "value", -1, 65535)
        elif not isinstance(step.get("value"), bool):
            raise QAError("invalid_assertion_value", f"step {index} {assertion} requires a boolean value")
    elif assertion in {"position", "local_position"}:
        _reject_unknown(step, common | {"x", "z"}, f"step {index}")
        _require_int(step.get("x"), "x", -1024, 1024)
        _require_int(step.get("z"), "z", -1024, 1024)
    elif assertion == "height":
        _reject_unknown(step, common | {"current_height", "position_y_fx32"}, f"step {index}")
        if not ({"current_height", "position_y_fx32"} & set(step)):
            raise QAError("invalid_height_assertion", f"step {index} height requires at least one field")
        for name in ("current_height", "position_y_fx32"):
            if name in step:
                _require_int(step[name], name, -(2**31), 2**31 - 1)
    elif assertion == "event_counts":
        _reject_unknown(step, common | {"background", "npc", "warp", "coordinate"}, f"step {index}")
        if len(step) == 1:
            raise QAError("invalid_event_assertion", f"step {index} event_counts requires a count")
        for name, value in step.items():
            if name != "assert":
                _require_int(value, name, 0, 4096)
    elif assertion in {"marker", "memory_value"}:
        allowed = common | {"symbol", "value", "offset", "width", "mask"}
        _reject_unknown(step, allowed, f"step {index}")
        if not isinstance(step.get("symbol"), str) or not SAFE_SYMBOL.fullmatch(step["symbol"]):
            raise QAError("invalid_symbol", f"step {index} requires a safe linker symbol")
        _require_int(step.get("value"), "value", -(2**31), 2**32 - 1)
        _require_int(step.get("offset", 0), "offset", 0, 4096)
        if step.get("width", 4) not in (1, 2, 4):
            raise QAError("invalid_memory_width", f"step {index} memory width must be 1, 2, or 4")
        if "mask" in step:
            _require_int(step["mask"], "mask", 0, 2**32 - 1)
    elif assertion == "screenshot_valid":
        _reject_unknown(step, common | {"name"}, f"step {index}")
        if not isinstance(step.get("name"), str) or not SAFE_CAPTURE.fullmatch(step["name"]):
            raise QAError("unsafe_capture_name", f"step {index} screenshot name is unsafe")
    elif assertion in {"header_field", "resource_id"}:
        _reject_unknown(step, common | {"field", "value"}, f"step {index}")
        if step.get("field") not in HEADER_FIELDS:
            raise QAError("invalid_header_field", f"step {index} has invalid header field {step.get('field')!r}")
        _require_int(step.get("value"), "value", 0, 65535)
    elif assertion == "bdhc_ready":
        _reject_unknown(step, common | {"value", "stripe_count"}, f"step {index}")
        if not isinstance(step.get("value"), bool):
            raise QAError("invalid_assertion_value", f"step {index} bdhc_ready requires a boolean value")
        if "stripe_count" in step:
            _require_int(step["stripe_count"], "stripe_count", 0, 65535)
    elif assertion == "collision_blocked":
        _reject_unknown(step, common | {"direction"}, f"step {index}")
        if step.get("direction") not in DIRECTIONS:
            raise QAError("invalid_direction", f"step {index} has invalid direction {step.get('direction')!r}")
    elif assertion == "native_transition":
        _reject_unknown(step, common | {"direction", "from_map_id", "to_map_id", "no_warp"}, f"step {index}")
        if step.get("direction") not in DIRECTIONS:
            raise QAError("invalid_direction", f"step {index} has invalid direction {step.get('direction')!r}")
        _require_int(step.get("from_map_id"), "from_map_id", 0, 65535)
        _require_int(step.get("to_map_id"), "to_map_id", 0, 65535)
        if not isinstance(step.get("no_warp", True), bool):
            raise QAError("invalid_assertion_value", f"step {index} no_warp must be boolean")


def validate_scenario_data(data: object, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise QAError("invalid_scenario", "scenario root must be an object")
    _reject_unknown(data, {"schema_version", "id", "fixture", "build_target", "entry", "steps"}, "scenario")
    if data.get("schema_version") != QA_SCHEMA_VERSION:
        raise QAError("unsupported_schema", f"QA schema_version must be {QA_SCHEMA_VERSION}")
    scenario_id = data.get("id")
    if not isinstance(scenario_id, str) or not SAFE_ID.fullmatch(scenario_id):
        raise QAError("invalid_scenario_id", "scenario id must be lower snake_case")
    fixture_value = data.get("fixture")
    if not isinstance(fixture_value, str):
        raise QAError("invalid_fixture", "fixture must be a repository-relative path")
    fixture = Path(fixture_value)
    if fixture.is_absolute() or ".." in fixture.parts:
        raise QAError("unsafe_fixture_path", "fixture path must stay within the repository")
    resolved_fixture = (root / fixture).resolve()
    try:
        resolved_fixture.relative_to(root.resolve())
    except ValueError as error:
        raise QAError("unsafe_fixture_path", "fixture path escapes the repository") from error
    if not resolved_fixture.is_file():
        raise QAError("missing_fixture", f"scenario fixture does not exist: {fixture_value}")
    if not isinstance(data.get("build_target"), str) or not SAFE_ID.fullmatch(data["build_target"].replace("-", "_")):
        raise QAError("invalid_build_target", "build_target must be a safe Make target")
    entry = data.get("entry")
    if not isinstance(entry, dict):
        raise QAError("invalid_entry", "entry must be an object")
    _reject_unknown(entry, {"mode"}, "entry")
    if entry.get("mode") not in {"new_game_controlled", "continue_existing_save"}:
        raise QAError("invalid_entry_mode", "entry mode is not supported")
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise QAError("invalid_steps", f"steps must contain 1 through {MAX_STEPS} entries")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise QAError("invalid_step", f"step {index} must be an object", step=index)
        if ("action" in step) == ("assert" in step):
            raise QAError("invalid_step", f"step {index} must contain exactly one action or assertion", step=index)
        _validate_action(step, index) if "action" in step else _validate_assertion(step, index)
    return json.loads(json.dumps(data, sort_keys=True))


def load_scenario(path: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QAError("scenario_read_failed", f"cannot read QA scenario {path}: {error}") from error
    return validate_scenario_data(data, root)


def deterministic_plan(scenario: dict[str, Any]) -> dict[str, object]:
    semantics = {
        "schema_version": scenario["schema_version"],
        "id": scenario["id"],
        "fixture": scenario["fixture"],
        "build_target": scenario["build_target"],
        "entry": scenario["entry"],
        "steps": scenario["steps"],
    }
    encoded = json.dumps(semantics, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"semantics": semantics, "sha256": hashlib.sha256(encoded).hexdigest(), "step_count": len(scenario["steps"])}


def inspect_scenario(path: Path, root: Path = PROJECT_ROOT) -> dict[str, object]:
    scenario = load_scenario(path, root)
    plan = deterministic_plan(scenario)
    return {
        "success": True,
        "scenario": scenario["id"],
        "fixture": scenario["fixture"],
        "build_target": scenario["build_target"],
        "entry": scenario["entry"],
        "actions": sorted({step["action"] for step in scenario["steps"] if "action" in step}),
        "assertions": sorted({step["assert"] for step in scenario["steps"] if "assert" in step}),
        "plan": plan,
    }


def _prepare_battery_config(path: Path, entry_mode: str) -> None:
    """Create a private DeSmuME config root, clearing it only for fresh entry."""
    if entry_mode == "new_game_controlled":
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def run_scenario(
    path: Path,
    root: Path = PROJECT_ROOT,
    timeout_seconds: float = 300,
    *,
    build: bool = False,
    build_timeout_seconds: float = 1200,
) -> dict[str, object]:
    root = root.resolve()
    scenario = load_scenario(path, root)
    plan = deterministic_plan(scenario)
    artifact_dir = root / "build" / "qa" / scenario["id"]
    report_path = artifact_dir / "report.json"
    trace_path = artifact_dir / "trace.json"
    worker_path = artifact_dir / ".worker.json"
    log_path = artifact_dir / "emulator.log"
    screenshots = artifact_dir / "screenshots"
    battery_config = artifact_dir / "desmume-config"
    rom_path = root / GENERATED_ROM_NAME
    errors: list[object] = []
    build_result = None
    if build:
        build_result = run_command(
            ["make", scenario["build_target"]],
            cwd=root,
            timeout_seconds=build_timeout_seconds,
        )
        if not build_result.succeeded:
            return {
                "schema_version": QA_SCHEMA_VERSION,
                "operation": "qa_run",
                "scenario": scenario["id"],
                "fixture": scenario["fixture"],
                "build_target": scenario["build_target"],
                "entry_strategy": scenario["entry"]["mode"],
                "plan": plan,
                "build": build_result.to_dict(),
                "rom_sha256": sha256_file(rom_path) if rom_path.is_file() else None,
                "success": False,
                "errors": [QAError(
                    "qa_build_failed",
                    f"declared QA build target failed: {scenario['build_target']}",
                ).as_dict()],
            }
    report: dict[str, object] = {
        "schema_version": QA_SCHEMA_VERSION,
        "operation": "qa_run",
        "scenario": scenario["id"],
        "fixture": scenario["fixture"],
        "build_target": scenario["build_target"],
        "entry_strategy": scenario["entry"]["mode"],
        "plan": plan,
        "rom_sha256": sha256_file(rom_path) if rom_path.is_file() else None,
        "success": False,
        "artifacts": {
            "directory": str(artifact_dir), "report": str(report_path), "trace": str(trace_path),
            "log": str(log_path), "screenshots": str(screenshots),
            "battery_config": str(battery_config),
        },
        "errors": errors,
    }
    if build_result is not None:
        report["build"] = build_result.to_dict()
    targets = (artifact_dir, report_path, trace_path, worker_path, log_path, screenshots, battery_config)
    if any(path_is_git_ignored(root, target) is not True for target in targets):
        errors.append(QAError("unsafe_output_path", "QA artifacts must be Git-ignored").as_dict())
        return report
    if not rom_path.is_file():
        errors.append(QAError("missing_rom", f"generated ROM is missing: {rom_path}").as_dict())
        return report
    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshots.mkdir(parents=True, exist_ok=True)
    _prepare_battery_config(battery_config, scenario["entry"]["mode"])
    worker_path.unlink(missing_ok=True)
    command = [
        sys.executable, "-m", "tools.pokeagent.qa_emulator", "--worker",
        "--root", str(root), "--rom", str(rom_path), "--scenario", str(path),
        "--result", str(worker_path), "--artifact-dir", str(artifact_dir),
        "--timeout", str(max(1, timeout_seconds - 2)),
    ]
    command_result = run_command(
        command, cwd=root, timeout_seconds=timeout_seconds, log_path=log_path,
        env_overrides={
            "SDL_VIDEODRIVER": "dummy",
            "XDG_CONFIG_HOME": str(battery_config),
        },
    )
    worker: dict[str, object] | None = None
    if worker_path.is_file():
        try:
            worker = json.loads(worker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(QAError("worker_result_invalid", str(error)).as_dict())
    else:
        errors.append(QAError("worker_result_missing", "QA worker did not write a result").as_dict())
    if not command_result.succeeded:
        code = "worker_timeout" if command_result.timed_out else "worker_failed"
        errors.append(QAError(code, f"QA worker exited {command_result.exit_code}").as_dict())
    if worker is not None and not worker.get("success"):
        errors.extend(worker.get("errors", []))
    report.update({
        "command": command_result.to_dict(), "worker": worker,
        "success": not errors, "completed_at": utc_now(),
    })
    worker_path.unlink(missing_ok=True)
    write_json_report(report_path, report)
    return report
