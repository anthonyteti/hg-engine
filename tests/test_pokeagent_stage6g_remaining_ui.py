import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.qa import load_scenario
from tools.pokeagent.remaining_ui import DEFAULT_AUDIT, DEFAULT_SOURCE, RemainingUIError, compile_remaining_ui, validate


class Stage6GRemainingUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))
        cls.audit = json.loads(DEFAULT_AUDIT.read_text(encoding="utf-8"))

    def test_source_contract_and_complete_audit_alignment(self):
        validate(self.source, self.audit)
        expected = [screen["id"] for screen in self.audit["screens"] if screen["target_stage"] == "6G"]
        self.assertEqual([screen["id"] for screen in self.source["coverage"]], expected)
        self.assertEqual(len(expected), 25)
        self.assertNotIn("ENGINE_FIXED", {screen["control"] for screen in self.source["coverage"]})

    def test_native_resource_budget_and_unique_targets(self):
        self.assertEqual(self.source["budgets"]["resource_owner_count"], 9)
        self.assertEqual(self.source["budgets"]["palette_member_count"], 76)
        pairs = [(owner["archive"], member) for owner in self.source["resource_owners"] for member in owner["palette_members"]]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_collision_and_missing_surface_fail_actionably(self):
        bad = copy.deepcopy(self.source)
        bad["resource_owners"][0]["palette_members"].append(7)
        with self.assertRaisesRegex(RemainingUIError, "palette target collision"):
            validate(bad, self.audit)
        bad = copy.deepcopy(self.source)
        bad["coverage"].pop()
        with self.assertRaisesRegex(RemainingUIError, "coverage must exactly follow"):
            validate(bad, self.audit)

    def test_two_root_determinism_and_tracked_report(self):
        with tempfile.TemporaryDirectory(dir=Path("build")) as first, tempfile.TemporaryDirectory(dir=Path("build")) as second:
            first, second = Path(first), Path(second)
            compile_remaining_ui(DEFAULT_SOURCE, DEFAULT_AUDIT, first / "out", first / "report.json")
            compile_remaining_ui(DEFAULT_SOURCE, DEFAULT_AUDIT, second / "out", second / "report.json")
            self.assertEqual((first / "report.json").read_bytes(), (second / "report.json").read_bytes())
            self.assertEqual((first / "report.json").read_bytes(), Path("docs/data/stage6_remaining_ui.json").read_bytes())

    def test_runtime_matrix_owns_title_dex_pc_shop_and_dialogue(self):
        paths = [
            Path("qa/scenarios/stage6g_title_continue.json"),
            Path("qa/scenarios/stage6g_pokedex_1025.json"),
            Path("qa/scenarios/stage6g_pc_storage.json"),
            Path("qa/scenarios/stage6g_shop_dialogue.json"),
        ]
        scenarios = [load_scenario(path) for path in paths]
        targets = {scenario["build_target"] for scenario in scenarios}
        self.assertEqual(targets, {"stage6g-title-proof", "stage6g-dex-proof", "stage6g-pc-proof", "stage6g-shop-proof"})
        captures = {step.get("name") for scenario in scenarios for step in scenario["steps"] if step.get("action") == "capture"}
        self.assertTrue({"stage6g_title", "stage6g_continue", "stage6g_dex_1025", "stage6g_pc", "stage6g_shop", "stage6g_dialogue"} <= captures)


if __name__ == "__main__":
    unittest.main()
