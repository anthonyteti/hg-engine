from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.pokeagent.qa import deterministic_plan, load_scenario


ROOT = Path(__file__).resolve().parents[1]


class Stage5EMegaRuntimeProofTests(unittest.TestCase):
    def test_manifest_records_existing_mega_contract(self) -> None:
        manifest = json.loads((ROOT / "fixtures/stage5e_mega_runtime.json").read_text())
        self.assertEqual(manifest["base"]["id"], 334)
        self.assertEqual(manifest["mega"]["id"], 1108)
        self.assertEqual(manifest["mega"]["battle_form"], 1)
        self.assertEqual(manifest["eligibility"]["held_item_id"], 755)
        self.assertEqual(manifest["base"]["types"], [16, 2])
        self.assertEqual(manifest["mega"]["types"], [16, 9])
        self.assertEqual(manifest["mega"]["ability"], 182)

    def test_source_contract_maps_altaria_to_mega_form(self) -> None:
        species = (ROOT / "include/constants/species.h").read_text(encoding="utf-8")
        forms = (ROOT / "data/FormToSpeciesMapping.c").read_text(encoding="utf-8")
        mega = (ROOT / "src/battle/mega.c").read_text(encoding="utf-8")
        self.assertIn("#define SPECIES_ALTARIA    334", species)
        self.assertIn("#define SPECIES_MEGA_ALTARIA", species)
        self.assertIn("[SPECIES_MEGA_ALTARIA - SPECIES_MEGA_START] = SPECIES_ALTARIA", forms)
        self.assertIn(".monindex = SPECIES_ALTARIA", mega)
        self.assertIn(".itemindex = ITEM_ALTARIANITE", mega)

    def test_proof_is_opt_in_and_never_seeds_mega_identity(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        runtime = (ROOT / "src/stage5e_runtime.c").read_text(encoding="utf-8")
        encounters = (ROOT / "data/Encounters.c").read_text(encoding="utf-8")
        self.assertIn("ifeq ($(STAGE5E_MEGA_PROOF),Y)", makefile)
        self.assertIn("#ifdef STAGE5E_MEGA_PROOF", runtime)
        self.assertIn("PokeParaSet(&altaria, SPECIES_ALTARIA", runtime)
        self.assertNotIn("PokeParaSet(&altaria, SPECIES_MEGA_ALTARIA", runtime)
        self.assertNotRegex(runtime, r"SetMonData\([^;\n]*MON_DATA_FORM")
        self.assertIn("#elif defined(STAGE5E_MEGA_PROOF)", encounters)

    def test_observations_cover_native_activation_move_and_reversion(self) -> None:
        mega = (ROOT / "src/battle/mega.c").read_text(encoding="utf-8")
        before = (ROOT / "src/individual/ServerBeforeAct.c").read_text(encoding="utf-8")
        move_end = (ROOT / "src/battle/other_battle_calculators.c").read_text(encoding="utf-8")
        battle_end = (ROOT / "src/battle/battle_pokemon.c").read_text(encoding="utf-8")
        self.assertIn("Stage5E_RecordEligibility", mega)
        self.assertIn("Stage5E_RecordMegaCommandReturn", mega)
        self.assertIn("Stage5E_RecordMegaQueue", before)
        self.assertIn("Stage5E_RecordMegaActive", before)
        self.assertIn("Stage5E_RecordMove", move_end)
        self.assertIn("Stage5E_RecordBattleEndBefore", battle_end)
        self.assertIn("Stage5E_RecordBattleEndAfter", battle_end)

    def test_scenario_is_deterministic_and_uses_native_ui(self) -> None:
        scenario = load_scenario(ROOT / "qa/scenarios/stage5e_mega_runtime.json", ROOT)
        self.assertEqual(scenario["build_target"], "stage5e-mega-proof")
        self.assertEqual(deterministic_plan(scenario), deterministic_plan(json.loads(json.dumps(scenario))))
        self.assertEqual(sum(step.get("action") == "reset" for step in scenario["steps"]), 1)
        self.assertEqual(sum(step.get("action") == "continue" for step in scenario["steps"]), 1)
        self.assertTrue(any(step.get("action") == "touch" and step.get("x") == 220 for step in scenario["steps"]))
        writes = [step for step in scenario["steps"] if step.get("action") == "write_memory"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["offset"], 4)


if __name__ == "__main__":
    unittest.main()
