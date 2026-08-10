from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.pokeagent.roster_inventory import ROOT, STATUSES, build_inventory, write_inventory


def _record(inventory: dict, name: str) -> dict:
    return next(record for record in inventory["records"] if record["species"] == name)


class Stage5ARosterInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = build_inventory(ROOT, "TEST")

    def test_inventory_schema_and_identity_ranges(self) -> None:
        inventory = self.inventory
        self.assertEqual(inventory["schema_version"], 1)
        self.assertEqual(inventory["summary"]["identity_count"], 1475)
        self.assertEqual(inventory["summary"]["implemented_species_count"], 1025)
        self.assertEqual(inventory["summary"]["form_identity_count"], 400)
        self.assertEqual(inventory["summary"]["reserved_placeholder_count"], 50)
        self.assertEqual(inventory["limits"]["highest_base_species_id"], 1075)
        self.assertEqual(inventory["limits"]["highest_identity_id"], 1475)
        self.assertLessEqual({record["status"] for record in inventory["records"]}, STATUSES)
        self.assertEqual(len({record["id"] for record in inventory["records"]}), 1475)
        self.assertEqual(len({record["species"] for record in inventory["records"]}), 1475)

    def test_generation_and_expanded_overworld_counts(self) -> None:
        rows = {row["generation"]: row for row in self.inventory["generation_coverage"]}
        self.assertEqual([rows[g]["expected_in_engine"] for g in range(1, 10)], [151, 100, 135, 107, 156, 72, 88, 96, 120])
        self.assertEqual([rows[g]["overworld_runtime"] for g in range(5, 10)], [156, 72, 88, 96, 120])

    def test_source_assets_do_not_substitute_for_runtime_follower_mapping(self) -> None:
        source_count = self.inventory["summary"]["overworld_source_count"]
        runtime_count = self.inventory["summary"]["overworld_runtime_count"]
        self.assertEqual(source_count, 1475)
        self.assertEqual(runtime_count, 1236)
        self.assertGreater(source_count, runtime_count)

    def test_victini_selected_proof_evidence(self) -> None:
        victini = _record(self.inventory, "SPECIES_VICTINI")
        self.assertEqual(victini["id"], 544)
        self.assertEqual(victini["generation"], 5)
        self.assertEqual(victini["status"], "PARTIAL")
        for capability in (
            "species_data", "learnset", "evolution", "battle_front", "battle_back", "icon", "cry",
            "follower_mapping", "follower_properties", "pokedex_number", "pokedex_name", "pokedex_sprite",
            "pokedex_seen_caught", "trainer_storage", "wild_storage",
            "party_storage", "box_storage", "save_storage",
        ):
            self.assertTrue(victini["capabilities"][capability], capability)
        self.assertFalse(victini["capabilities"]["pokedex_category"])
        self.assertFalse(victini["capabilities"]["pokedex_description"])
        self.assertFalse(victini["capabilities"]["pokedex_complete"])
        proof = self.inventory["selected_expanded_species_proof"]
        self.assertEqual(proof["runtime_status"], "COMPLETE_EXECUTED")
        self.assertEqual(proof["shared_runtime_architecture"], "REPRESENTATIVE_PROVEN")
        self.assertEqual(len(proof["runtime_evidence"]), 11)
        self.assertIn("expanded Dex category/description", proof["runtime_blocker"])

    def test_storage_widths_cover_base_species_and_bound_forms(self) -> None:
        limits = self.inventory["limits"]
        self.assertLess(limits["highest_base_species_id"], 2 ** limits["wild_runtime_species_bits"])
        self.assertLess(limits["highest_base_species_id"], 2 ** limits["box_party_species_bits"])
        self.assertGreater(limits["highest_identity_id"], limits["highest_base_species_id"])
        self.assertEqual(limits["alternate_form_bits"], 5)

    def test_asset_references_and_form_mappings_are_auditable(self) -> None:
        for record in self.inventory["records"]:
            asset_dir = ROOT / record["evidence"]["battle_assets"]
            self.assertTrue(asset_dir.is_dir(), record["species"])
            if record["kind"] == "form" and record["capabilities"]["form_mapping"]:
                self.assertIsNotNone(record["base_species"], record["species"])

    def test_mega_mappings_and_highest_form_are_explicit(self) -> None:
        summary = self.inventory["summary"]
        self.assertEqual(summary["mega_form_identity_count"], 97)
        self.assertEqual(summary["mega_runtime_mapped_base_species_count"], 84)
        highest = _record(self.inventory, "SPECIES_MEGA_BAXCALIBUR")
        self.assertEqual(highest["id"], 1475)
        self.assertEqual(highest["kind"], "form")

    def test_machine_report_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            write_inventory(first, ROOT, "TEST")
            write_inventory(second, ROOT, "TEST")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            parsed = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(parsed["source_revision"], "TEST")


if __name__ == "__main__":
    unittest.main()
