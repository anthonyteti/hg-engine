import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.pokeagent.ui_layout import DEFAULT_SOURCE, UILayoutError, compile_layout

ROOT = Path(__file__).resolve().parents[1]


class Stage6DUILayoutTests(unittest.TestCase):
    def _compile(self, root: Path, source: Path = DEFAULT_SOURCE):
        return compile_layout(source, root / "stage6d_ui.h", root / "report.json")

    def test_schema_uses_semantic_bindings_and_symbolic_resources(self):
        source = json.loads(DEFAULT_SOURCE.read_text())
        self.assertEqual(source["screen"]["resource_bundle"], "ui.start_menu.adriatic_field_journal")
        self.assertEqual([item["source"] for item in source["bindings"]], [
            "party[0].species", "party[0].level", "party[0].hp", "party[0].max_hp"])
        self.assertNotIn("address", json.dumps(source).lower())

    def test_two_root_compilation_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            a = self._compile(Path(left))
            b = self._compile(Path(right))
            self.assertEqual(a, b)
            self.assertEqual((Path(left) / "stage6d_ui.h").read_bytes(), (Path(right) / "stage6d_ui.h").read_bytes())
            self.assertEqual((Path(left) / "report.json").read_bytes(), (Path(right) / "report.json").read_bytes())

    def test_source_revision_changes_generated_configuration(self):
        original = json.loads(DEFAULT_SOURCE.read_text())
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            baseline = self._compile(temp / "baseline")
            revised = copy.deepcopy(original)
            revised["components"][0]["text"] = "FIELD NOTES"
            revised["navigation"]["initial"] = "bag_button"
            source = temp / "revised.json"
            source.write_text(json.dumps(revised), encoding="utf-8")
            changed = self._compile(temp / "changed", source)
            generated = (temp / "changed" / "stage6d_ui.h").read_text()
        self.assertNotEqual(baseline["source_sha256"], changed["source_sha256"])
        self.assertNotEqual(baseline["header_sha256"], changed["header_sha256"])
        self.assertIn("#define STAGE6D_UI_INITIAL_SELECTION 1", generated)

    def test_layout_navigation_and_budgets_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self._compile(Path(temp))
        self.assertEqual(result["component_count"], 5)
        self.assertEqual(result["touch_region_count"], 0)
        self.assertLessEqual(result["tile_count"], result["budgets"]["tiles"])
        self.assertTrue(all(value == "PASS" for value in result["validation"].values()))

    def test_out_of_bounds_overlap_raw_binding_and_dead_navigation_fail(self):
        original = json.loads(DEFAULT_SOURCE.read_text())
        mutations = []
        bad = copy.deepcopy(original); bad["components"][0]["bounds"] = [31, 1, 3, 2]; mutations.append(bad)
        bad = copy.deepcopy(original); bad["components"][1]["bounds"] = bad["components"][0]["bounds"]; mutations.append(bad)
        bad = copy.deepcopy(original); bad["bindings"][0]["source"] = "0x02100000"; mutations.append(bad)
        bad = copy.deepcopy(original); bad["navigation"]["party_button"]["right"] = "missing"; mutations.append(bad)
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / "bad.json"
                    path.write_text(json.dumps(mutation))
                    with self.assertRaises(UILayoutError):
                        self._compile(Path(temp), path)

    def test_tracked_header_and_report_match_canonical_source(self):
        with tempfile.TemporaryDirectory() as temp:
            self._compile(Path(temp))
            self.assertEqual((Path(temp) / "stage6d_ui.h").read_bytes(), (ROOT / "include/generated/stage6d_ui.h").read_bytes())
            self.assertEqual((Path(temp) / "report.json").read_bytes(), (ROOT / "docs/data/stage6_ui_layouts.json").read_bytes())

    def test_runtime_hook_is_opt_in(self):
        make = (ROOT / "Makefile").read_text()
        bag = (ROOT / "src/bag.c").read_text()
        self.assertIn("STAGE6D_DECLARATIVE_UI_PROOF", make)
        self.assertIn("#ifdef STAGE6D_DECLARATIVE_UI_PROOF", bag)
        self.assertIn("Stage6D_RuntimeTick", bag)


if __name__ == "__main__":
    unittest.main()
