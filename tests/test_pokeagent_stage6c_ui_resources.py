from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.pokeagent.ui_resources import DEFAULT_SOURCE, ROOT, UIResourceError, compile_resources, validate


class Stage6CUIResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))

    def test_symbolic_schema_and_audited_destination(self) -> None:
        validate(self.source)
        self.assertEqual(self.source["bundle_id"], "ui.start_menu.adriatic_field_journal")
        self.assertEqual(
            [row["id"] for row in self.source["components"]],
            [
                "ui.surface.field_window",
                "ui.rail.lake_gradient",
                "ui.rail.paper_guide",
                "ui.rail.copper_shore",
            ],
        )
        self.assertEqual(self.source["target"]["archive"], "a/0/1/4")
        self.assertEqual(
            [self.source["target"][name] for name in ("character_member", "screen_member", "palette_member")],
            [12, 13, 15],
        )

    def test_compiler_is_two_root_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            first_report = compile_resources(DEFAULT_SOURCE, first)
            second_report = compile_resources(DEFAULT_SOURCE, second)
            for name in ("start_menu_chrome.png", "start_menu_chrome.tilemap.json", "start_menu_chrome.NCGR.lz", "start_menu_chrome.NSCR.lz", "start_menu_chrome.NCLR"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            for key in first_report["outputs"]:
                self.assertEqual(first_report["outputs"][key]["sha256"], second_report["outputs"][key]["sha256"])

    def test_outputs_are_native_bounded_nitro_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = compile_resources(DEFAULT_SOURCE, output)
            with Image.open(output / "start_menu_chrome.png") as image:
                self.assertEqual(image.size, (256, 32))
                self.assertEqual(image.mode, "P")
                self.assertLessEqual(len(image.getpalette() or []) // 3, 256)
            self.assertEqual((output / "start_menu_chrome.NCGR.lz").read_bytes()[0], 0x10)
            self.assertEqual((output / "start_menu_chrome.NSCR.lz").read_bytes()[0], 0x10)
            self.assertEqual((output / "start_menu_chrome.NCLR").read_bytes()[:4], b"RLCN")
            self.assertLessEqual(report["outputs"]["character"]["bytes"], 4096)
            self.assertLessEqual(report["outputs"]["screen"]["bytes"], 2048)
            self.assertLessEqual(report["outputs"]["palette"]["bytes"], 552)

    def test_invalid_palette_tile_and_member_collisions_fail_closed(self) -> None:
        duplicate_color = copy.deepcopy(self.source)
        duplicate_color["palette"][1] = duplicate_color["palette"][0]
        with self.assertRaisesRegex(UIResourceError, "palette colors"):
            validate(duplicate_color)
        duplicate_tile = copy.deepcopy(self.source)
        duplicate_tile["components"][1]["tiles"][0] = 0
        with self.assertRaisesRegex(UIResourceError, "cover 0..7"):
            validate(duplicate_tile)
        duplicate_member = copy.deepcopy(self.source)
        duplicate_member["target"]["screen_member"] = 12
        with self.assertRaisesRegex(UIResourceError, "12/13/15"):
            validate(duplicate_member)

    def test_runtime_proof_is_opt_in_and_normal_code_is_unchanged(self) -> None:
        scenario = json.loads(
            (ROOT / "qa/scenarios/stage6c_ui_resource_runtime.json").read_text(encoding="utf-8")
        )
        self.assertEqual(scenario["build_target"], "stage6c-ui-resource-proof")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("python3 -m tools.pokeagent.ui_resources --proof-rom", makefile)
        self.assertNotIn("STAGE6C_UI_RESOURCE_PROOF := Y", makefile)
        self.assertFalse(any(path.name.startswith("stage6c") for path in (ROOT / "src").glob("*.c")))

    def test_catalog_matches_current_deterministic_build(self) -> None:
        catalog = ROOT / "docs/data/stage6_ui_resources.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = compile_resources(DEFAULT_SOURCE, output)
        tracked = json.loads(catalog.read_text(encoding="utf-8"))
        self.assertEqual(tracked["bundle_id"], report["bundle_id"])
        self.assertEqual(tracked["source_sha256"], report["source_sha256"])
        for key in tracked["outputs"]:
            self.assertEqual(tracked["outputs"][key]["sha256"], report["outputs"][key]["sha256"])


if __name__ == "__main__":
    unittest.main()
