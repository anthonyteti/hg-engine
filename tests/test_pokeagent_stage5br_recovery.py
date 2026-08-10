from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.pokeagent.battle_save import (
    BattleSaveError,
    DSV_FOOTER,
    DSV_TRAILER,
    RAW_SAVE_BYTES,
    _extract_raw_dsv,
    provision_battle_save,
)
from tools.pokeagent.qa import run_scenario
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]


class FailedCommand:
    succeeded = False

    def to_dict(self) -> dict[str, object]:
        return {"exit_code": 2, "succeeded": False, "timed_out": False}


class Stage5BRRecoveryTests(unittest.TestCase):
    def test_battle_save_dsv_extraction_is_bounded(self) -> None:
        raw = bytes((index % 251) + 1 for index in range(RAW_SAVE_BYTES))
        container = raw + DSV_FOOTER + b"metadata" + DSV_TRAILER
        self.assertEqual(_extract_raw_dsv(container), raw)
        with self.assertRaises(BattleSaveError):
            _extract_raw_dsv(b"\xff" * RAW_SAVE_BYTES + DSV_FOOTER + DSV_TRAILER)
        with self.assertRaises(BattleSaveError):
            _extract_raw_dsv(raw)

    def test_battle_save_requires_local_rom_and_ignored_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(BattleSaveError, "provisioning ROM is unavailable"):
                provision_battle_save(root / "missing.nds", root / "test.sav", root)

    def test_battle_runner_missing_save_message_is_actionable(self) -> None:
        source = (ROOT / "scripts/run_tests.py").read_text(encoding="utf-8")
        self.assertIn("missing_battle_save", source)
        self.assertIn("make battle-test-save", source)
        self.assertIn("524288 bytes", source)

    def test_stage5b_save_npc_is_opt_in_and_normal_stage4a_is_unchanged(self) -> None:
        stage5b = load_fixture(ROOT / "fixtures/stage5b_victini_world.json")
        stage4a = load_fixture(ROOT / "fixtures/stage3e2_header_expansion_world.json")
        self.assertTrue(stage5b["maps"]["west"]["npc"]["save_game"])
        self.assertFalse(stage5b["maps"]["west"]["npc"]["warp_after_save"])
        self.assertNotIn("save_game", stage4a["maps"]["west"]["npc"])

    def test_qa_build_failure_is_stable_and_stops_before_emulation(self) -> None:
        scenario = {
            "schema_version": 1,
            "id": "build_failure",
            "fixture": "fixtures/stage2_proof_map.json",
            "build_target": "stage2-proof",
            "entry": {"mode": "new_game_controlled"},
            "steps": [{"assert": "rom_running", "value": True}],
        }
        with patch("tools.pokeagent.qa.load_scenario", return_value=scenario), patch(
            "tools.pokeagent.qa.run_command", return_value=FailedCommand()
        ) as command:
            report = run_scenario(Path("ignored.json"), ROOT, build=True)
        self.assertFalse(report["success"])
        self.assertEqual(report["errors"][0]["code"], "qa_build_failed")
        command.assert_called_once()


if __name__ == "__main__":
    unittest.main()
