import json
from pathlib import Path
import unittest

from tools.pokeagent.stage6l_showcase import FIXTURE, REPORT, compile_showcase


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "qa/scenarios/stage6l_integrated_showcase.json"


class Stage6LShowcaseTests(unittest.TestCase):
    def test_static_showcase_compilation_is_deterministic(self) -> None:
        first = compile_showcase(write=False)
        second = compile_showcase(write=False)
        self.assertEqual(first, second)
        self.assertEqual(first["asset_count"], 2)
        self.assertEqual(first["triangle_count"], 60)
        self.assertEqual(first["quad_count"], 24)
        self.assertEqual([item["shape"] for item in first["display_lists"]], [1, 6])
        self.assertTrue(all(item["display_list_bytes"] <= item["capacity_bytes"] for item in first["display_lists"]))

    def test_fixture_keeps_integrated_world_bounded(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["schema_version"], 14)
        self.assertEqual(fixture["dimensions"], {"width": 32, "height": 32})
        self.assertEqual([item["asset"] for item in fixture["assets"]], [
            "stage6k_hunyuan_lighthouse",
            "stage6i_rural_kit",
        ])
        self.assertEqual(fixture["player_start"]["map"], "stage4i_capacity_map")
        self.assertEqual(fixture["terrain"]["permission_regions"][0]["permission_type"], 3)

    def test_integrated_qa_plan_covers_required_evidence(self) -> None:
        scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
        self.assertEqual(scenario["build_target"], "stage6l-presentation-showcase")
        captures = {
            step["name"]
            for step in scenario["steps"]
            if step.get("action") == "capture"
        }
        self.assertTrue({
            "showcase_start_menu",
            "showcase_party",
            "showcase_summary",
            "showcase_bag",
            "showcase_rural_environment",
            "showcase_generated_landmark",
            "showcase_battle_commands",
            "showcase_mega_active",
            "showcase_return_to_field",
        } <= captures)
        memory_offsets = {
            step.get("offset")
            for step in scenario["steps"]
            if step.get("symbol") == "gStage5ERuntimeState"
        }
        self.assertTrue({20, 132, 196, 208, 316, 332, 336} <= memory_offsets)
        self.assertIn({"action": "wait", "frames": 600}, scenario["steps"])

    def test_tracked_runtime_report_records_integrated_pack(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["id"], "stage6l_integrated_presentation_showcase")
        self.assertEqual(report["ui_pack"]["archive_count"], 15)
        self.assertEqual(report["ui_pack"]["resource_count"], 134)
        self.assertTrue(report["ui_pack"]["archives_restored"])
        self.assertEqual(len(report["rom_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
