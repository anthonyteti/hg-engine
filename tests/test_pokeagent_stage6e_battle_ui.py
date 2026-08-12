import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.battle_ui import (
    DEFAULT_SOURCE,
    BattleUIError,
    compile_battle_ui,
    validate,
)
from tools.pokeagent.qa import load_scenario


class Stage6EBattleUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))

    def test_source_contract_and_semantics(self):
        validate(self.source)
        self.assertEqual(self.source["target"]["archive"], "a/0/0/7")
        self.assertEqual(self.source["target"]["hud_archive"], "a/0/0/8")
        self.assertEqual(self.source["target"]["hud_palette_member"], 71)
        self.assertEqual(len(self.source["hud_palette"]), 16)
        self.assertEqual(len(self.source["screens"]), 8)
        self.assertIn("battle.mega.eligible", self.source["semantic_bindings"])
        self.assertEqual(self.source["animation"]["mega"], "native_mega_sequence")

    def test_bounds_overlap_and_touch_fail_actionably(self):
        bad = copy.deepcopy(self.source)
        bad["screens"]["main"]["panels"][1]["bounds"] = [0, 10, 10, 10]
        with self.assertRaisesRegex(BattleUIError, "illegal panel overlap"):
            validate(bad)
        bad = copy.deepcopy(self.source)
        bad["screens"]["fight_mega"]["touch"]["mega"] = [176, 152, 300, 192]
        with self.assertRaisesRegex(BattleUIError, "invalid semantic touch"):
            validate(bad)

    def test_two_root_determinism_and_budgets(self):
        with tempfile.TemporaryDirectory(dir=Path("build")) as first, tempfile.TemporaryDirectory(dir=Path("build")) as second:
            first = Path(first)
            second = Path(second)
            a = compile_battle_ui(DEFAULT_SOURCE, first / "out", first / "ui.h", first / "report.json")
            b = compile_battle_ui(DEFAULT_SOURCE, second / "out", second / "ui.h", second / "report.json")
            self.assertEqual((first / "ui.h").read_bytes(), (second / "ui.h").read_bytes())
            self.assertEqual((first / "report.json").read_bytes(), (second / "report.json").read_bytes())
            self.assertEqual(a["source_sha256"], b["source_sha256"])
            for key in a["outputs"]:
                self.assertEqual(a["outputs"][key]["sha256"], b["outputs"][key]["sha256"])
            self.assertEqual(set(a["validation"].values()), {"PASS"})

    def test_tracked_generated_outputs_are_current(self):
        with tempfile.TemporaryDirectory(dir=Path("build")) as directory:
            directory = Path(directory)
            compile_battle_ui(DEFAULT_SOURCE, directory / "out", directory / "ui.h", directory / "report.json")
            self.assertEqual((directory / "ui.h").read_bytes(), Path("include/generated/stage6e_battle_ui.h").read_bytes())
            self.assertEqual((directory / "report.json").read_bytes(), Path("docs/data/stage6_battle_ui.json").read_bytes())

    def test_normal_build_isolation_is_explicit(self):
        source = Path("src/battle/battle_input.c").read_text(encoding="utf-8")
        makefile = Path("Makefile").read_text(encoding="utf-8")
        self.assertIn("#ifdef STAGE6E_BATTLE_UI_PROOF", source)
        self.assertIn("STAGE6E_BATTLE_UI_PROOF=Y", makefile)

    def test_runtime_scenario_reuses_proven_mega_prefix(self):
        scenario = load_scenario(Path("qa/scenarios/stage6e_battle_ui.json"))
        self.assertEqual(scenario["id"], "stage6e_battle_ui")
        self.assertEqual(scenario["build_target"], "stage6e-battle-ui-proof")
        self.assertEqual(len(scenario["steps"]), 71)
        self.assertEqual(scenario["steps"][-1], {"assert": "rom_running", "value": True})
        self.assertTrue(any(step.get("assert") == "memory_value" and step.get("value") == 1108 for step in scenario["steps"]))

    def test_command_scenario_covers_bag_switch_and_run(self):
        scenario = load_scenario(Path("qa/scenarios/stage6e_battle_commands.json"))
        captures = {step.get("name") for step in scenario["steps"] if step.get("action") == "capture"}
        self.assertIn("stage6e_battle_bag", captures)
        self.assertIn("stage6e_battle_switch", captures)
        self.assertIn("stage6e_battle_switched", captures)
        self.assertIn("stage6e_battle_run_denied", captures)
        runtime = Path("src/stage5e_runtime.c").read_text(encoding="utf-8")
        self.assertIn("#ifdef STAGE6E_BATTLE_UI_PROOF", runtime)


if __name__ == "__main__":
    unittest.main()
