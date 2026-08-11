from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.pokeagent.qa import deterministic_plan, load_scenario


ROOT = Path(__file__).resolve().parents[1]


class Stage5DRegionalFormProofTests(unittest.TestCase):
    def test_manifest_records_existing_regional_contract(self) -> None:
        manifest = json.loads((ROOT / "fixtures/stage5d_regional_form_runtime.json").read_text())
        self.assertTrue(manifest["proof_only"])
        self.assertEqual(
            [(row["identity_id"], row["base_species"], row["form"]) for row in manifest["representative_line"]],
            [(1335, 620, 1), (1336, 621, 1)],
        )
        self.assertEqual(manifest["source_evolution"]["method"], "EVO_LEVEL")
        self.assertEqual(manifest["source_evolution"]["parameter"], 30)
        self.assertEqual(manifest["runtime_storage"]["selected_serialized_path"], "wild_encounter")

    def test_source_contract_maps_base_form_and_regional_lineage(self) -> None:
        species = (ROOT / "include/constants/species.h").read_text(encoding="utf-8")
        forms = (ROOT / "data/FormToSpeciesMapping.c").read_text(encoding="utf-8")
        evolutions = (ROOT / "data/Evolutions.c").read_text(encoding="utf-8")
        self.assertIn("#define SPECIES_ZORUA_HISUIAN", species)
        self.assertIn("#define SPECIES_ZOROARK_HISUIAN", species)
        self.assertIn("[SPECIES_ZORUA_HISUIAN - SPECIES_MEGA_START] = SPECIES_ZORUA", forms)
        self.assertIn("[SPECIES_ZOROARK_HISUIAN - SPECIES_MEGA_START] = SPECIES_ZOROARK", forms)
        self.assertIn("MON_WITH_FORM(SPECIES_ZOROARK, 1)", evolutions)

    def test_existing_form_assets_cover_icon_follower_and_battle_paths(self) -> None:
        followers = (ROOT / "src/field/overworld_table.c").read_text(encoding="utf-8")
        properties = (ROOT / "data/FollowerProperties.c").read_text(encoding="utf-8")
        for name in ("ZORUA_HISUIAN", "ZOROARK_HISUIAN"):
            self.assertIn(f"SPECIES_{name}", followers)
            self.assertIn(f"[SPECIES_{name}]", properties)
            sprite_dir = ROOT / "data" / "graphics" / "sprites" / name.lower()
            self.assertTrue(sprite_dir.is_dir())

    def test_proof_is_opt_in_and_observes_ordinary_evolution(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        runtime = (ROOT / "src/stage5d_runtime.c").read_text(encoding="utf-8")
        pokemon = (ROOT / "src/pokemon.c").read_text(encoding="utf-8")
        encounters = (ROOT / "data/Encounters.c").read_text(encoding="utf-8")
        self.assertIn("ifeq ($(STAGE5D_REGIONAL_FORM_PROOF),Y)", makefile)
        self.assertIn("#ifdef STAGE5D_REGIONAL_FORM_PROOF", runtime)
        self.assertIn("Stage5D_RecordEvolutionCheck", pokemon)
        self.assertIn("Stage5D_RecordSpeciesMutation", pokemon)
        self.assertNotIn("GetMonEvolution(", runtime)
        self.assertNotIn("PokeParaSet(&zorua, SPECIES_ZOROARK", runtime)
        self.assertNotRegex(runtime, r"SetMonData\([^;\n]*MON_DATA_SPECIES")
        self.assertIn("MON_WITH_FORM(SPECIES_ZORUA, 1)", encounters)

    def test_scenarios_are_deterministic_and_separate_wild_intake(self) -> None:
        main = load_scenario(ROOT / "qa/scenarios/stage5d_regional_form_runtime.json", ROOT)
        wild = load_scenario(ROOT / "qa/scenarios/stage5d_hisuian_wild_form.json", ROOT)
        self.assertEqual(main["build_target"], "stage5d-regional-form-proof")
        self.assertEqual(wild["build_target"], "stage5d-regional-form-proof")
        self.assertEqual(deterministic_plan(main), deterministic_plan(json.loads(json.dumps(main))))
        self.assertEqual(deterministic_plan(wild), deterministic_plan(json.loads(json.dumps(wild))))
        self.assertEqual(sum(step.get("action") == "reset" for step in main["steps"]), 3)
        self.assertEqual(sum(step.get("action") == "continue" for step in main["steps"]), 3)
        self.assertFalse(any(step.get("action") == "reset" for step in wild["steps"]))
        writes = [step for step in main["steps"] if step.get("action") == "write_memory"]
        self.assertTrue(writes)
        self.assertTrue(all(step["offset"] == 4 for step in writes))


if __name__ == "__main__":
    unittest.main()
