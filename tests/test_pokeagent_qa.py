from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.pokeagent.qa import (
    QAError,
    _prepare_battery_config,
    deterministic_plan,
    load_scenario,
    validate_scenario_data,
)
from tools.pokeagent.qa_emulator import QAEmulatorAdapter, execute_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (
    ROOT / "qa/scenarios/stage4a_basic_world.json",
    ROOT / "qa/scenarios/stage4a_elevation.json",
    ROOT / "qa/scenarios/stage4a_world_persistence.json",
    ROOT / "qa/scenarios/stage4b_asset_ingestion.json",
    ROOT / "qa/scenarios/stage4c_project_texture.json",
    ROOT / "qa/scenarios/stage4d_scalable_textures.json",
    ROOT / "qa/scenarios/stage4e_triangle_asset.json",
)


def base_scenario() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "unit_qa",
        "fixture": "fixtures/stage2_proof_map.json",
        "build_target": "stage2-proof",
        "entry": {"mode": "new_game_controlled"},
        "steps": [{"assert": "rom_running", "value": True}],
    }


class FakeAdapter:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.frame = 0
        self.calls: list[object] = []
        self.last_movement = None
        self.screenshots: dict[str, dict[str, object]] = {}
        self.memory = {"gMarker": 42}
        self.state = {
            "frame": 0, "running": True,
            "location": {"map": 540, "warp": -1, "x": 10, "z": 10, "direction": 1},
            "map_id": 540, "position": {"x": 10, "z": 10},
            "local_position": {"x": 10, "z": 10},
            "height": {"current_height": 0, "position_y_fx32": 0},
            "event_counts": {"background": 0, "npc": 1, "warp": 0, "coordinate": 0},
            "matrix": {"width": 2, "height": 1}, "matrix_id": 288, "map_member": 676,
            "header_fields": {"matrix": 288, "event": 491, "script": 965},
            "warp_state": -1, "bdhc": {"ready": True, "stripe_counts": [6]},
            "markers": {"gMarker": 42},
        }

    def snapshot(self):
        state = copy.deepcopy(self.state)
        state["frame"] = self.frame
        return state

    def controlled_entry(self): self.calls.append("controlled_entry")
    def continue_game(self, expected_map_id=None, timeout_frames=7200):
        self.calls.append(("continue", expected_map_id, timeout_frames))
        if expected_map_id is not None:
            self.state["map_id"] = expected_map_id
            self.state["location"]["map"] = expected_map_id
    def wait(self, frames): self.frame += frames; self.calls.append(("wait", frames))
    def press(self, button, held_frames=4, after_frames=35):
        self.frame += held_frames + after_frames; self.calls.append(("press", button))
    def hold(self, button, frames): self.frame += frames; self.calls.append(("hold", button))
    def release(self, button, after_frames=0): self.frame += after_frames; self.calls.append(("release", button))
    def reset(self): self.calls.append("reset")
    def move(self, direction, tiles, max_attempts):
        delta = {"east": (1, 0), "west": (-1, 0), "north": (0, -1), "south": (0, 1)}[direction]
        start = copy.deepcopy(self.state["location"])
        self.state["location"]["x"] += delta[0] * tiles
        self.state["location"]["z"] += delta[1] * tiles
        self.state["position"] = {"x": self.state["location"]["x"], "z": self.state["location"]["z"]}
        self.state["local_position"] = {"x": self.state["location"]["x"] % 32, "z": self.state["location"]["z"] % 32}
        self.last_movement = {"start": start, "end": copy.deepcopy(self.state["location"]), "blocked": False}
        return self.last_movement
    def move_to(self, target, max_attempts):
        start = copy.deepcopy(self.state["location"])
        self.state["location"].update(target)
        self.state["position"] = {"x": self.state["location"]["x"], "z": self.state["location"]["z"]}
        self.last_movement = {"start": start, "end": copy.deepcopy(self.state["location"]), "blocked": False}
        return self.last_movement
    def assert_blocked(self, direction):
        before = self.snapshot(); after = self.snapshot()
        self.last_movement = {"direction": direction, "start": before["location"], "end": after["location"], "blocked": True}
        return before, after
    def assert_native_transition(self, direction, from_map_id, to_map_id, no_warp):
        before = self.snapshot()
        self.state["map_id"] = to_map_id; self.state["location"]["map"] = to_map_id
        after = self.snapshot()
        self.last_movement = {"direction": direction, "start": before["location"], "end": after["location"], "blocked": False}
        return before, after
    def capture(self, name):
        path = self.artifact_dir / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-png")
        value = {"path": str(path), "width": 256, "height": 384, "unique_colors": 2, "sha256": "0" * 64}
        self.screenshots[name] = value
        return value
    def read_memory(self, symbol, offset, width): return self.memory[symbol]


class QASchemaTests(unittest.TestCase):
    def test_tracked_scenarios_validate_and_have_deterministic_plans(self) -> None:
        for path in SCENARIOS:
            scenario = load_scenario(path, ROOT)
            first = deterministic_plan(scenario)
            second = deterministic_plan(json.loads(json.dumps(scenario)))
            self.assertEqual(first, second)
            self.assertEqual(len(first["sha256"]), 64)

    def test_unknown_action_and_assertion_are_rejected(self) -> None:
        for key, value, code in (("action", "teleport", "unknown_action"), ("assert", "weather_magic", "unknown_assertion")):
            scenario = base_scenario(); scenario["steps"] = [{key: value}]
            with self.assertRaises(QAError) as error:
                validate_scenario_data(scenario, ROOT)
            self.assertEqual(error.exception.code, code)

    def test_invalid_direction_and_button_are_rejected(self) -> None:
        scenario = base_scenario(); scenario["steps"] = [{"action": "move", "direction": "diagonal", "tiles": 1}]
        with self.assertRaises(QAError) as direction:
            validate_scenario_data(scenario, ROOT)
        self.assertEqual(direction.exception.code, "invalid_direction")
        scenario["steps"] = [{"action": "press", "button": "power"}]
        with self.assertRaises(QAError) as button:
            validate_scenario_data(scenario, ROOT)
        self.assertEqual(button.exception.code, "invalid_button")

    def test_frame_bounds_and_unsafe_capture_are_rejected(self) -> None:
        for step, code in (
            ({"action": "wait", "frames": 3601}, "invalid_integer"),
            ({"action": "hold", "button": "a", "frames": 601}, "invalid_integer"),
            ({"action": "capture", "name": "../escape"}, "unsafe_capture_name"),
        ):
            scenario = base_scenario(); scenario["steps"] = [step]
            with self.assertRaises(QAError) as error:
                validate_scenario_data(scenario, ROOT)
            self.assertEqual(error.exception.code, code)

    def test_malformed_fixture_reference_is_rejected(self) -> None:
        scenario = base_scenario(); scenario["fixture"] = "../rom.nds"
        with self.assertRaises(QAError) as error:
            validate_scenario_data(scenario, ROOT)
        self.assertEqual(error.exception.code, "unsafe_fixture_path")

    def test_reset_continue_plan_validates(self) -> None:
        scenario = base_scenario()
        scenario["steps"] = [{"action": "reset"}, {"action": "continue", "expected_map_id": 541}]
        validated = validate_scenario_data(scenario, ROOT)
        self.assertEqual(validated["steps"], scenario["steps"])

    def test_battery_config_is_cleared_for_new_game_and_preserved_for_continue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "private-config"
            config.mkdir()
            marker = config / "desmume" / "test.dsv"
            marker.parent.mkdir()
            marker.write_bytes(b"old-save")
            _prepare_battery_config(config, "continue_existing_save")
            self.assertEqual(marker.read_bytes(), b"old-save")
            _prepare_battery_config(config, "new_game_controlled")
            self.assertTrue(config.is_dir())
            self.assertFalse(marker.exists())


class QAExecutionTests(unittest.TestCase):
    def execute(self, steps):
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeAdapter(Path(directory))
            scenario = base_scenario(); scenario["steps"] = steps
            return execute_scenario(adapter, scenario), adapter

    def test_snapshot_semantics_and_assertion_success(self) -> None:
        result, _ = self.execute([
            {"assert": "map_id", "value": 540},
            {"assert": "position", "x": 10, "z": 10},
            {"assert": "height", "current_height": 0},
            {"assert": "event_counts", "npc": 1, "warp": 0},
            {"assert": "header_field", "field": "event", "value": 491},
            {"assert": "bdhc_ready", "value": True, "stripe_count": 6},
        ])
        self.assertTrue(result["success"])
        self.assertEqual(result["assertions_passed"], 6)

    def test_movement_success_and_blocked_are_structured(self) -> None:
        result, adapter = self.execute([
            {"action": "move", "direction": "east", "tiles": 2},
            {"assert": "movement_succeeded", "value": True},
            {"assert": "collision_blocked", "direction": "north"},
        ])
        self.assertTrue(result["success"])
        self.assertTrue(adapter.last_movement["blocked"])

    def test_semantic_failure_has_expected_observed_and_step(self) -> None:
        result, _ = self.execute([{"assert": "map_id", "value": 999}])
        self.assertFalse(result["success"])
        error = result["errors"][0]
        self.assertEqual(error["code"], "semantic_assertion_failed")
        self.assertEqual(error["details"]["expected"], 999)
        self.assertEqual(error["details"]["observed"], 540)
        self.assertEqual(error["step_index"], 0)
        self.assertIn("state_after", result["trace"][0])

    def test_reset_continue_executes_in_order(self) -> None:
        result, adapter = self.execute([
            {"action": "reset"},
            {"action": "continue", "expected_map_id": 541, "timeout_frames": 7200},
            {"assert": "map_id", "value": 541},
        ])
        self.assertTrue(result["success"])
        self.assertIn("reset", adapter.calls)
        self.assertIn(("continue", 541, 7200), adapter.calls)

    def test_hold_and_release_execute_with_bounded_frames(self) -> None:
        result, adapter = self.execute([
            {"action": "hold", "button": "left", "frames": 12},
            {"action": "release", "button": "left", "after_frames": 3},
        ])
        self.assertTrue(result["success"])
        self.assertIn(("hold", "left"), adapter.calls)
        self.assertIn(("release", "left"), adapter.calls)
        self.assertEqual(adapter.frame, 15)

    def test_screenshot_artifact_metadata_is_assertable(self) -> None:
        result, _ = self.execute([
            {"action": "capture", "name": "evidence"},
            {"assert": "screenshot_valid", "name": "evidence"},
        ])
        self.assertTrue(result["success"])
        self.assertEqual(result["screenshots"]["evidence"]["width"], 256)

    def test_native_transition_is_semantic_and_traceable(self) -> None:
        result, _ = self.execute([
            {"assert": "native_transition", "direction": "east", "from_map_id": 540, "to_map_id": 541, "no_warp": True},
            {"assert": "map_id", "value": 541},
        ])
        self.assertTrue(result["success"])
        self.assertEqual(result["trace"][0]["result"]["observed"]["after"]["map_id"], 541)

    def test_required_location_reports_field_not_ready(self) -> None:
        adapter = QAEmulatorAdapter.__new__(QAEmulatorAdapter)
        adapter.emu = object()
        adapter.symbols = {"gFieldSysPtr": 0x02000000}
        with patch("tools.pokeagent.qa_emulator._location", side_effect=RuntimeError("not loaded")):
            with self.assertRaises(QAError) as error:
                adapter._location_required()
        self.assertEqual(error.exception.code, "field_not_ready")


if __name__ == "__main__":
    unittest.main()
