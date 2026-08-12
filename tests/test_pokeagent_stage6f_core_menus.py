import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.core_menu_ui import (
    DEFAULT_SOURCE,
    CoreMenuUIError,
    compile_core_menus,
    transform_nclr,
    validate,
)
from tools.pokeagent.qa import load_scenario


class Stage6FCoreMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))

    def test_source_contract(self):
        validate(self.source)
        self.assertEqual([item["id"] for item in self.source["screens"]], ["start_menu", "party", "summary", "bag"])
        self.assertEqual(self.source["budgets"], {
            "screen_count": 4,
            "archive_count": 5,
            "palette_member_count": 48,
            "max_palette_bytes": 552,
        })
        self.assertIn("party[index].species", self.source["screens"][1]["bindings"])
        self.assertIn("change_pocket", self.source["screens"][3]["navigation"])

    def test_collision_and_budget_fail_actionably(self):
        bad = copy.deepcopy(self.source)
        bad["screens"][1]["palette_members"].append(4)
        with self.assertRaisesRegex(CoreMenuUIError, "palette target collision"):
            validate(bad)
        bad = copy.deepcopy(self.source)
        bad["budgets"]["palette_member_count"] = 45
        with self.assertRaisesRegex(CoreMenuUIError, "budgets do not match"):
            validate(bad)

    def test_palette_transform_is_deterministic_and_preserves_semantics(self):
        raw = bytearray(0x28 + 32)
        raw[:4] = b"RLCN"
        raw[0x10:0x14] = b"TTLP"
        struct.pack_into("<I", raw, 0x20, 32)
        colors = [0, 0x4210, 0x7FFF, 0x03E0, 0x001F] + [0] * 11
        for index, color in enumerate(colors):
            struct.pack_into("<H", raw, 0x28 + index * 2, color)
        transform = self.source["palette_transform"]
        first = transform_nclr(bytes(raw), transform)
        second = transform_nclr(bytes(raw), transform)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(raw))
        self.assertEqual(first[0x28:0x2A], raw[0x28:0x2A])
        self.assertNotEqual(first[0x2A:0x2E], raw[0x2A:0x2E])
        self.assertEqual(first[0x2E:0x30], raw[0x2E:0x30])
        self.assertEqual(first[0x30:0x32], raw[0x30:0x32])

    def test_start_and_bag_chrome_do_not_preserve_stock_saturation(self):
        raw = bytearray(0x28 + 32)
        raw[:4] = b"RLCN"
        raw[0x10:0x14] = b"TTLP"
        struct.pack_into("<I", raw, 0x20, 32)
        struct.pack_into("<H", raw, 0x2A, 0x03E0)
        struct.pack_into("<H", raw, 0x2C, 0x401F)
        for screen in ("start_menu", "bag"):
            themed = transform_nclr(bytes(raw), self.source["palette_transform"], screen)
            self.assertNotEqual(themed[0x28:0x2E], raw[0x28:0x2E])

    def test_two_root_determinism_and_tracked_report(self):
        with tempfile.TemporaryDirectory(dir=Path("build")) as first, tempfile.TemporaryDirectory(dir=Path("build")) as second:
            first, second = Path(first), Path(second)
            a = compile_core_menus(DEFAULT_SOURCE, first / "out", first / "report.json")
            b = compile_core_menus(DEFAULT_SOURCE, second / "out", second / "report.json")
            self.assertEqual((first / "report.json").read_bytes(), (second / "report.json").read_bytes())
            self.assertEqual(a["source_sha256"], b["source_sha256"])
            self.assertEqual((first / "report.json").read_bytes(), Path("docs/data/stage6_core_menus.json").read_bytes())

    def test_runtime_scenarios_cover_four_owners_and_navigation(self):
        core = load_scenario(Path("qa/scenarios/stage6f_core_menus.json"))
        bag = load_scenario(Path("qa/scenarios/stage6f_bag.json"))
        captures = {step.get("name") for step in core["steps"] + bag["steps"] if step.get("action") == "capture"}
        self.assertTrue({"stage6f_start_menu", "stage6f_party", "stage6f_summary", "stage6f_bag", "stage6f_bag_pocket"} <= captures)
        self.assertEqual(core["build_target"], "stage6f-core-menu-proof")
        self.assertEqual(bag["build_target"], "stage6f-core-menu-proof")


if __name__ == "__main__":
    unittest.main()
