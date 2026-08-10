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
    provision_battle_save_from_dsv,
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

    def test_qa_battery_save_provisions_bounded_raw_fixture(self) -> None:
        raw = bytes((index % 251) + 1 for index in range(RAW_SAVE_BYTES))
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            dsv = Path(directory) / "source.dsv"
            output = Path(directory) / "test.sav"
            dsv.write_bytes(raw + DSV_FOOTER + b"metadata" + DSV_TRAILER)
            result = provision_battle_save_from_dsv(dsv, output, ROOT)
            self.assertEqual(output.read_bytes(), raw)
            self.assertEqual(result["method"], "qa_ordinary_battery_save_extraction")

    def test_make_target_uses_ordinary_qa_save_path(self) -> None:
        source = (ROOT / "Makefile").read_text(encoding="utf-8")
        target = source[source.index("battle-test-save:"):source.index(".PHONY: stage4b-asset-proof")]
        self.assertIn("stage5b_victini_runtime.json --build", target)
        self.assertIn("--dsv build/qa/stage5b_victini_runtime", target)

    def test_clean_auto_test_includes_battle_save_world(self) -> None:
        source = (ROOT / "Makefile").read_text(encoding="utf-8")
        auto = source[source.index("ifeq ($(AUTO_TEST),Y)"):source.index("ifeq ($(STAGE2_MAP),Y)")]
        self.assertIn("STAGE3E2_HEADER := Y", auto)
        self.assertIn("STAGE5B_RUNTIME_PROOF := Y", auto)
        self.assertIn("STAGE5BC_RUNTIME_PROOF := Y", auto)
        self.assertIn("$(filter Y,$(STAGE2_MAP) $(AUTO_TEST))", source)

    def test_battle_queue_waits_for_host_range(self) -> None:
        source = (ROOT / "src/bag.c").read_text(encoding="utf-8")
        self.assertIn("ReadValueThroughCommunicationSendHole() != TEST_BATTLE_READY", source)

    def test_battle_runner_clears_title_input_dialog_before_queue(self) -> None:
        source = (ROOT / "scripts/run_tests.py").read_text(encoding="utf-8")
        self.assertIn("b_mask = keymask(Keys.KEY_B)", source)
        self.assertLess(source.index("b_mask = keymask(Keys.KEY_B)"), source.index("write_communication_hole_value(TEST_START_INDEX"))

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
