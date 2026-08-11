from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.pokeagent.qa import deterministic_plan, load_scenario


ROOT = Path(__file__).resolve().parents[1]


class Stage5BRuntimeProofTests(unittest.TestCase):
    def test_manifest_declares_existing_victini_data(self) -> None:
        manifest = json.loads((ROOT / "fixtures/stage5b_victini_runtime.json").read_text())
        self.assertTrue(manifest["proof_only"])
        self.assertEqual(manifest["species"]["constant"], "SPECIES_VICTINI")
        self.assertEqual(manifest["species"]["engine_id"], 544)
        self.assertEqual(manifest["species"]["base_stats"], [100] * 6)
        self.assertEqual(manifest["species"]["types"], [14, 10])
        self.assertEqual(manifest["species"]["ability"], 162)
        self.assertEqual(manifest["species"]["moves"], [93, 116, 529, 513])
        self.assertEqual(manifest["evolution"], "NOT_APPLICABLE")

    def test_runtime_hook_is_opt_in_and_uses_ordinary_storage(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        source = (ROOT / "src/stage5b_runtime.c").read_text()
        bag = (ROOT / "src/bag.c").read_text()
        self.assertIn("ifeq ($(STAGE5B_RUNTIME_PROOF),Y)", makefile)
        self.assertIn("#ifdef STAGE5B_RUNTIME_PROOF", source)
        self.assertIn("#ifdef STAGE5B_RUNTIME_PROOF", bag)
        for operation in (
            "PokeParaSet", "InitBoxMonMoveset", "PokeParty_Add",
            "PCStorage_PlaceMonInBoxByIndexPair", "PCStorage_GetMonByIndexPair",
            "PCStorage_DeleteBoxMonByIndexPair", "SetPokemonSee", "SetPokemonGet",
        ):
            self.assertIn(operation, source)

    def test_scenario_has_deterministic_semantic_matrix(self) -> None:
        scenario = load_scenario(ROOT / "qa/scenarios/stage5b_victini_runtime.json", ROOT)
        first = deterministic_plan(scenario)
        second = deterministic_plan(json.loads(json.dumps(scenario)))
        self.assertEqual(first, second)
        captures = {step["name"] for step in scenario["steps"] if step.get("action") == "capture"}
        self.assertIn("victini_follower", captures)
        self.assertIn("victini_after_continue", captures)
        commands = {
            step["value"] for step in scenario["steps"]
            if step.get("action") == "write_memory" and step.get("offset") == 8
        }
        self.assertEqual(commands, {1, 2, 3, 4, 5})
        self.assertEqual(
            sum(step.get("assert") == "marker" and step.get("value") == 45 for step in scenario["steps"]),
            2,
        )
        self.assertIn("victini_party_persisted", captures)
        self.assertIn("victini_pc_box_persisted", captures)

    def test_battle_fixture_uses_victini_on_both_sides(self) -> None:
        source = (ROOT / "data/battle_tests/stage5b/victini_runtime.c").read_text()
        self.assertEqual(source.count(".species = SPECIES_VICTINI"), 2)
        self.assertEqual(source.count(".ability = ABILITY_VICTORY_STAR"), 2)
        self.assertIn("Victini used Incinerate!", source)
        self.assertIn("The opposing Victini is getting pumped!", source)
        self.assertLess(
            source.index('expectationValue.message = "Victini used Incinerate!"'),
            source.index('expectationValue.message = "The opposing Victini is getting pumped!"'),
        )


if __name__ == "__main__":
    unittest.main()
