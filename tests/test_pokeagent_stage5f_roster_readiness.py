from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.pokeagent.qa import deterministic_plan, load_scenario
from tools.pokeagent.roster_inventory import ROOT, write_inventory
from tools.pokeagent.roster_readiness import (
    FAMILY_REQUIREMENTS,
    FORM_FAMILIES,
    READINESS_STATUSES,
    species_text_records,
    validate_generated_dex_archives,
)


def _record(inventory: dict, name: str) -> dict:
    return next(record for record in inventory["records"] if record["species"] == name)


class Stage5FRosterReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.json"
            cls.inventory = write_inventory(output, ROOT, "TEST")

    def test_production_scope_and_required_base_roster(self) -> None:
        production = self.inventory["production_readiness"]
        self.assertEqual(production["required_base_species"]["count"], 905)
        self.assertEqual(production["required_base_species"]["ready_count"], 905)
        self.assertEqual(production["required_base_species"]["functional_gap_count"], 0)
        self.assertEqual(production["required_base_species"]["content_gap_count"], 0)
        self.assertEqual(production["required_base_species"]["cry_runtime_ready_count"], 905)
        self.assertEqual(_record(self.inventory, "SPECIES_ENAMORUS")["national_dex_number"], 905)
        self.assertEqual(_record(self.inventory, "SPECIES_ENAMORUS")["production"]["scope"], "IN_SCOPE")
        self.assertEqual(_record(self.inventory, "SPECIES_SPRIGATITO")["national_dex_number"], 906)
        self.assertEqual(_record(self.inventory, "SPECIES_SPRIGATITO")["production"]["scope"], "OUT_OF_SCOPE_FOR_GAME")
        self.assertLessEqual({record["production"]["readiness"] for record in self.inventory["records"]}, READINESS_STATUSES)

    def test_actual_expanded_dex_source_is_complete(self) -> None:
        validation = self.inventory["production_readiness"]["dex_content"]
        self.assertEqual(validation["validation"], "PASS")
        self.assertEqual(validation["usable_entries"], 1025)
        self.assertEqual(validation["errors"], [])
        text = species_text_records(ROOT)
        for name in ("SPECIES_VICTINI", "SPECIES_CHESPIN", "SPECIES_ROWLET", "SPECIES_GROOKEY", "SPECIES_SPRIGATITO"):
            self.assertTrue(text[name]["classification"])
            self.assertTrue(text[name]["pokedexEntry"])
            self.assertEqual(_record(self.inventory, name)["production"]["content"]["dex"], "READY")

    def test_generated_dex_archives_match_canonical_text_when_built(self) -> None:
        generated = validate_generated_dex_archives(ROOT, self.inventory["records"])
        self.assertEqual(generated["validation"], "PASS")
        self.assertEqual(generated["implemented_base_entries_checked"], 1025)
        self.assertEqual(set(generated["identity_rows_per_member"].values()), {1476})
        self.assertEqual(generated["errors"], [])

    def test_generation_gap_table_distinguishes_authenticity(self) -> None:
        rows = {row["generation"]: row for row in self.inventory["production_readiness"]["generation_base_status"]}
        self.assertEqual(sum(rows[g]["in_scope_count"] for g in range(1, 10)), 905)
        self.assertTrue(all(rows[g]["functional_gap_count"] == 0 for g in range(1, 10)))
        self.assertTrue(all(rows[g]["dex_content_gap_count"] == 0 for g in range(1, 10)))
        self.assertEqual(rows[5]["cry_authenticity_unverified_count"], 156)
        self.assertEqual(rows[8]["in_scope_count"], 96)
        self.assertEqual(rows[9]["in_scope_count"], 0)

    def test_cry_routes_are_ready_without_false_authenticity_claim(self) -> None:
        counts = self.inventory["production_readiness"]["cry_classification_counts"]
        self.assertEqual(counts["AUTHENTIC_PROVENANCE_VERIFIED"], 493)
        self.assertEqual(counts["ROUTED_SOURCE_PRESENT_UNVERIFIED"], 532)
        self.assertEqual(_record(self.inventory, "SPECIES_VICTINI")["production"]["content"]["cry_authenticity"], "ROUTED_SOURCE_PRESENT_UNVERIFIED")

    def test_form_families_cover_every_form_once(self) -> None:
        forms = [record for record in self.inventory["records"] if record["kind"] == "form"]
        self.assertEqual(len(forms), 400)
        self.assertLessEqual({record["production"]["family"] for record in forms}, FORM_FAMILIES)
        self.assertEqual(_record(self.inventory, "SPECIES_ZORUA_HISUIAN")["production"]["family"], "REGIONAL_PERSISTENT")
        self.assertEqual(_record(self.inventory, "SPECIES_MEGA_ALTARIA")["production"]["family"], "MEGA_TEMPORARY")
        self.assertEqual(_record(self.inventory, "SPECIES_GIGANTAMAX_VENUSAUR")["production"]["family"], "GIGANTAMAX_OUT_OF_SCOPE")
        self.assertIn("ordinary_follower", FAMILY_REQUIREMENTS["MEGA_TEMPORARY"]["not_applicable"])
        self.assertIn("follower_mapping", FAMILY_REQUIREMENTS["REGIONAL_PERSISTENT"]["required"])

    def test_regional_and_current_scope_mega_static_contracts(self) -> None:
        production = self.inventory["production_readiness"]
        self.assertEqual(production["regional_static_audit"]["required_gap_count"], 0)
        self.assertEqual(production["mega_static_audit"]["required_gap_count"], 0)
        rayquaza = _record(self.inventory, "SPECIES_MEGA_RAYQUAZA")
        self.assertEqual(rayquaza["production"]["readiness"], "READY")
        self.assertIn("MEGA_MOVE_TRIGGER_MAPPING_DRAGON_ASCENT", rayquaza["production"]["reason_codes"])

    def test_exceptional_identities_are_explained_not_fabricated(self) -> None:
        exceptions = self.inventory["production_readiness"]["exceptional_identities"]
        self.assertEqual(len(exceptions), 6)
        self.assertEqual({entry["audit_status"] for entry in exceptions}, {"DATA_ONLY", "ASSET_ONLY", "UNKNOWN"})
        for entry in exceptions:
            self.assertIn(entry["readiness"], {"OUT_OF_SCOPE_FOR_GAME", "RESERVED_PLACEHOLDER"})
            self.assertTrue(entry["action"])

    def test_historical_status_is_preserved_beside_semantic_readiness(self) -> None:
        victini = _record(self.inventory, "SPECIES_VICTINI")
        mega = _record(self.inventory, "SPECIES_MEGA_ALTARIA")
        self.assertEqual(victini["status"], "PARTIAL")
        self.assertEqual(victini["production"]["readiness"], "READY")
        self.assertEqual(mega["status"], "PARTIAL")
        self.assertEqual(mega["production"]["readiness"], "READY")
        self.assertIn("ordinary_follower", mega["production"]["not_applicable"])

    def test_inventory_generation_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            write_inventory(first, ROOT, "TEST")
            write_inventory(second, ROOT, "TEST")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), hashlib.sha256(second.read_bytes()).hexdigest())
            json.loads(first.read_text(encoding="utf-8"))

    def test_proof_manifest_and_five_dex_scenarios_are_deterministic(self) -> None:
        manifest = json.loads((ROOT / "fixtures/stage5f_roster_content.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["scope"]["base_species_last_national_dex"], 905)
        self.assertEqual([row["generation"] for row in manifest["dex_representatives"]], [5, 6, 7, 8, 9])
        paths = [ROOT / "qa/scenarios/stage5f_expanded_dex_ui.json"] + [
            ROOT / f"qa/scenarios/stage5f_expanded_dex_gen{generation}.json" for generation in range(6, 10)
        ]
        for path in paths:
            scenario = load_scenario(path, ROOT)
            self.assertEqual(deterministic_plan(scenario), deterministic_plan(json.loads(json.dumps(scenario))))

    def test_stage5f_runtime_support_is_compile_time_isolated(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        bag = (ROOT / "src/bag.c").read_text(encoding="utf-8")
        runtime = (ROOT / "src/stage5f_runtime.c").read_text(encoding="utf-8")
        self.assertIn("ifeq ($(STAGE5F_DEX_PROOF),Y)", makefile)
        self.assertIn("#ifdef STAGE5F_DEX_PROOF", bag)
        self.assertIn("#ifdef STAGE5F_DEX_PROOF", runtime)


if __name__ == "__main__":
    unittest.main()
