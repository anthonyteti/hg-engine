from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.pokeagent.ui_audit import CORE_SURFACES, ROOT, build, validate


class Stage6BUIAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_path = ROOT / "presentation/ui/ui_reality_source.json"
        cls.source = json.loads(cls.source_path.read_text(encoding="utf-8"))
        cls.canonical = json.loads(
            (ROOT / "docs/data/hgengine_ui_reality_audit.json").read_text(encoding="utf-8")
        )

    def test_schema_and_complete_core_surface_contract(self) -> None:
        validate(self.source)
        surface_ids = {row["id"] for row in self.source["surfaces"]}
        self.assertGreaterEqual(len(surface_ids), 49)
        self.assertEqual(CORE_SURFACES - surface_ids, set())
        self.assertEqual(self.canonical["summary"]["unknown_surface_count"], 0)

    def test_inventory_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir) / "audit.json"
            second = Path(second_dir) / "audit.json"
            build(self.source_path, first)
            build(self.source_path, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first.read_bytes(), (ROOT / "docs/data/hgengine_ui_reality_audit.json").read_bytes())

    def test_every_system_has_resolved_local_and_primary_reference_evidence(self) -> None:
        self.assertEqual(self.canonical["summary"]["system_count"], 18)
        for system in self.canonical["systems"].values():
            self.assertTrue(system["local_evidence_metadata"])
            self.assertTrue(system["reference_evidence"])
            for evidence in system["local_evidence_metadata"]:
                self.assertTrue((ROOT / evidence["path"]).exists())
                if evidence["path"].startswith("base/"):
                    self.assertTrue(evidence["volatile_local_runtime_artifact"])
                    self.assertNotIn("sha256", evidence)
        reference = self.canonical["retail_reference"]
        self.assertEqual(reference["repository"], "https://github.com/pret/pokeheartgold")
        self.assertEqual(reference["revision"], "90e85d4e027f5e04800e7e015b3207094061402c")

    def test_major_overlay_ownership_is_explicit(self) -> None:
        by_id = {row["id"]: row for row in self.canonical["screens"]}
        expected = {
            "title": 60,
            "continue": 74,
            "bag": 15,
            "pc_storage": 14,
            "pokedex_entry": 18,
            "shop_buy": 3,
            "battle_commands": 12,
            "options": 54,
        }
        for surface, overlay in expected.items():
            self.assertEqual(by_id[surface]["ownership"]["overlay"], overlay)
        self.assertIsNone(by_id["party"]["ownership"]["overlay"])
        self.assertIsNone(by_id["summary_overview"]["ownership"]["overlay"])

    def test_authoring_contract_is_semantic_and_actionable(self) -> None:
        for screen in self.canonical["screens"]:
            self.assertTrue(screen["bindings"])
            self.assertTrue(screen["navigation"])
            self.assertTrue(screen["strategy"])
            self.assertTrue(screen["resource_archives"])
            self.assertNotIn("UNKNOWN", screen["classification"])
            for binding in screen["bindings"]:
                self.assertNotRegex(binding, r"^0x[0-9a-fA-F]+$")

    def test_runtime_reference_scenarios_remain_opt_in(self) -> None:
        scenarios = {
            "stage6b_bag_reference.json": "stage5bc-shared-runtime-proof",
            "stage6b_summary_reference.json": "stage5bc-shared-runtime-proof",
            "stage6b_title_reference.json": "stage5bc-shared-runtime-proof",
            "stage6b_shop_reference.json": "stage6b-ui-reference",
        }
        for filename, target in scenarios.items():
            source = json.loads((ROOT / "qa/scenarios" / filename).read_text(encoding="utf-8"))
            self.assertEqual(source["build_target"], target)
            self.assertEqual(source["entry"]["mode"], "new_game_controlled")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("STAGE6B_UI_AUDIT=Y", makefile)
        self.assertNotIn("STAGE6B_UI_AUDIT := Y", makefile)


if __name__ == "__main__":
    unittest.main()
