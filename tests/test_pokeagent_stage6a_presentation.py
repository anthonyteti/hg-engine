from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.pokeagent.stage6a_visuals import ROOT, build, validate, weighted_score


class Stage6APresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_path = ROOT / "presentation/stage6/directions.json"
        cls.source = json.loads(cls.source_path.read_text(encoding="utf-8"))

    def test_direction_schema_and_native_target(self) -> None:
        validate(self.source)
        self.assertEqual(self.source["native_screen"], [256, 192])
        self.assertGreaterEqual(len(self.source["candidates"]), 3)
        self.assertEqual(len(self.source["criteria"]), 17)

    def test_selected_direction_is_unique_matrix_leader(self) -> None:
        ranking = sorted(
            ((weighted_score(self.source, candidate), candidate["id"]) for candidate in self.source["candidates"]),
            reverse=True,
        )
        self.assertEqual(ranking[0][1], self.source["selected"]["id"])
        self.assertGreater(ranking[0][0], ranking[1][0])
        self.assertEqual(self.source["selected"]["primary_parent"], "adriatic_field_journal")

    def test_high_priority_criteria_are_weighted(self) -> None:
        weights = {row["id"]: row["weight"] for row in self.source["criteria"]}
        for criterion in (
            "pokemon_authenticity",
            "native_readability",
            "technical_feasibility",
            "ui_scalability",
            "environment_scalability",
            "long_term_suitability",
        ):
            self.assertEqual(weights[criterion], 3)

    def test_boards_are_byte_deterministic_and_native_studies_are_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            first_manifest = build(self.source_path, first)
            second_manifest = build(self.source_path, second)
            normalized_first = [
                (row["candidate"], row["weighted_score"], row["sha256"]) for row in first_manifest["boards"]
            ]
            normalized_second = [
                (row["candidate"], row["weighted_score"], row["sha256"]) for row in second_manifest["boards"]
            ]
            self.assertEqual(normalized_first, normalized_second)
            for candidate in (row["candidate"] for row in first_manifest["boards"]):
                left = first / f"{candidate}.png"
                right = second / f"{candidate}.png"
                self.assertEqual(left.read_bytes(), right.read_bytes())
                self.assertEqual(hashlib.sha256(left.read_bytes()).hexdigest(), hashlib.sha256(right.read_bytes()).hexdigest())
                with Image.open(left) as image:
                    self.assertEqual(image.size, (1600, 1120))
                    self.assertEqual(image.mode, "RGB")

    def test_presentation_bible_covers_required_contract(self) -> None:
        bible = (ROOT / "docs/stage6/PRESENTATION_BIBLE.md").read_text(encoding="utf-8")
        for heading in (
            "## UI geometry",
            "## Battle UI philosophy",
            "## World language",
            "## Environment families",
            "## Technical visual rules",
            "### Upper Valleys",
            "### Lake Country",
            "### Karst Interior",
            "### Great Gulf",
            "### Islands",
            "### High Country",
            "### Metropolitan Corridor",
            "### Championship Island",
        ):
            self.assertIn(heading, bible)
        self.assertIn("4,096 bytes", bible)

    def test_orchestrator_contract_is_restart_safe(self) -> None:
        state = json.loads((ROOT / "docs/stage6/STATE.yaml").read_text(encoding="utf-8"))
        plan = json.loads((ROOT / "docs/stage6/PLAN.yaml").read_text(encoding="utf-8"))
        self.assertEqual(state["stage"], 6)
        self.assertEqual(state["creative_direction"]["selection_mode"], "autonomous")
        self.assertEqual(plan["substage_order"], [f"6{letter}" for letter in "ABCDEFGHIJKL"])
        self.assertEqual({row["id"] for row in plan["substages"]}, set(plan["substage_order"]))
        for row in plan["substages"]:
            for field in (
                "objective",
                "dependencies",
                "required_evidence",
                "pass_conditions",
                "fail_conditions",
                "commit_rule",
                "next_stage_rule",
                "human_review_rule",
            ):
                self.assertIn(field, row)


if __name__ == "__main__":
    unittest.main()
