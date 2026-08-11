from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.pokeagent.qa import deterministic_plan, load_scenario


ROOT = Path(__file__).resolve().parents[1]


class Stage5CEvolutionProofTests(unittest.TestCase):
    def test_manifest_records_the_unchanged_runtime_contract(self) -> None:
        manifest = json.loads((ROOT / "fixtures/stage5c_evolution_runtime.json").read_text())
        self.assertTrue(manifest["proof_only"])
        self.assertEqual(
            [entry["engine_id"] for entry in manifest["representative_line"]],
            [778, 779, 780],
        )
        self.assertEqual(
            [(entry["method"], entry["parameter"]) for entry in manifest["source_evolutions"]],
            [("EVO_LEVEL", 17), ("EVO_LEVEL", 34)],
        )
        self.assertTrue(manifest["trigger"]["ordinary_bag_path"])
        self.assertFalse(manifest["trigger"]["direct_level_write"])
        self.assertFalse(manifest["trigger"]["direct_species_write"])

    def test_source_contract_is_the_existing_level_evolution_line(self) -> None:
        species = (ROOT / "include/constants/species.h").read_text(encoding="utf-8")
        evolutions = (ROOT / "data/Evolutions.c").read_text(encoding="utf-8")
        self.assertIn("#define SPECIES_POPPLIO         778", species)
        self.assertIn("#define SPECIES_BRIONNE         779", species)
        self.assertIn("#define SPECIES_PRIMARINA       780", species)
        self.assertIn("{ EVO_LEVEL, 17, SPECIES_BRIONNE }", evolutions)
        self.assertIn("{ EVO_LEVEL, 34, SPECIES_PRIMARINA }", evolutions)

    def test_existing_identity_dependent_mappings_cover_the_line(self) -> None:
        followers = (ROOT / "src/field/overworld_table.c").read_text(encoding="utf-8")
        properties = (ROOT / "data/FollowerProperties.c").read_text(encoding="utf-8")
        learnsets = json.loads((ROOT / "data/learnsets/learnsets.json").read_text(encoding="utf-8"))
        for name in ("POPPLIO", "BRIONNE", "PRIMARINA"):
            self.assertIn(f"MON_FOLLOWER_ENTRY(SPECIES_{name}", followers)
            self.assertIn(f"[SPECIES_{name}]", properties)
            self.assertIn(f"SPECIES_{name}", learnsets)

    def test_proof_is_opt_in_and_does_not_bypass_evolution(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        runtime = (ROOT / "src/stage5c_runtime.c").read_text(encoding="utf-8")
        pokemon = (ROOT / "src/pokemon.c").read_text(encoding="utf-8")
        self.assertIn("ifeq ($(STAGE5C_EVOLUTION_PROOF),Y)", makefile)
        self.assertIn("#ifdef STAGE5C_EVOLUTION_PROOF", runtime)
        self.assertIn("Stage5C_RecordEvolutionCheck", pokemon)
        self.assertIn("Stage5C_RecordSpeciesMutation", pokemon)
        self.assertNotIn("SetMonData", runtime)
        self.assertNotIn("GetMonEvolution(", runtime)
        self.assertNotIn("SetPartyPokemonParamsForEvoCutscene", runtime)

    def test_proof_bookkeeping_uses_persistent_not_temporary_variables(self) -> None:
        runtime = (ROOT / "src/stage5c_runtime.c").read_text(encoding="utf-8")
        self.assertIn("#define STAGE5C_PHASE_VAR 0x416D", runtime)
        self.assertIn("#define STAGE5C_BOX_VAR 0x416E", runtime)
        self.assertIn("#define STAGE5C_SLOT_VAR 0x416F", runtime)
        for temporary in ("0x4010", "0x4011", "0x4012"):
            self.assertNotIn(f"#define STAGE5C_PHASE_VAR {temporary}", runtime)

    def test_scenario_is_one_deterministic_continuous_identity_proof(self) -> None:
        scenario = load_scenario(ROOT / "qa/scenarios/stage5c_evolution_runtime.json", ROOT)
        self.assertEqual(scenario["build_target"], "stage5c-evolution-proof")
        self.assertEqual(deterministic_plan(scenario), deterministic_plan(json.loads(json.dumps(scenario))))
        captures = {step["name"] for step in scenario["steps"] if step.get("action") == "capture"}
        for name in (
            "popplio_party_icon",
            "popplio_to_brionne",
            "brionne_follower",
            "brionne_after_continue",
            "brionne_party_icon",
            "brionne_to_primarina",
            "primarina_party_icon",
            "primarina_follower",
            "primarina_after_continue",
            "primarina_box_after_continue",
        ):
            self.assertIn(name, captures)
        self.assertEqual(sum(step.get("action") == "reset" for step in scenario["steps"]), 3)
        self.assertEqual(sum(step.get("action") == "continue" for step in scenario["steps"]), 3)
        writes = [step for step in scenario["steps"] if step.get("action") == "write_memory"]
        self.assertTrue(writes)
        self.assertTrue(all(step["offset"] == 4 for step in writes))


if __name__ == "__main__":
    unittest.main()
