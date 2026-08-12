import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.ui_qa import DEFAULT_AUDIT, DEFAULT_LAYOUT, DEFAULT_SOURCE, UIQAError, compile_ui_qa, validate


class Stage6HUIQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(DEFAULT_SOURCE.read_text())
        cls.layout = json.loads(DEFAULT_LAYOUT.read_text())
        cls.audit = json.loads(DEFAULT_AUDIT.read_text())

    def test_contract(self):
        metrics = validate(self.source, self.layout, self.audit)
        self.assertEqual(len(self.source["required_screens"]), 13)
        self.assertEqual(metrics["runtime_scenario_count"], 8)
        self.assertTrue(self.source["policy"]["semantic_primary"])

    def test_navigation_failures_are_actionable(self):
        bad = copy.deepcopy(self.layout)
        bad["navigation"]["party_button"]["right"] = "missing"
        with self.assertRaisesRegex(UIQAError, "navigation target missing"):
            validate(self.source, bad, self.audit)
        bad = copy.deepcopy(self.layout)
        del bad["navigation"]["bag_button"]["cancel"]
        with self.assertRaisesRegex(UIQAError, "requires cancel"):
            validate(self.source, bad, self.audit)

    def test_bounds_failure_is_actionable(self):
        bad = copy.deepcopy(self.layout)
        bad["components"][0]["bounds"] = [31, 23, 2, 2]
        with self.assertRaisesRegex(UIQAError, "out of native bounds"):
            validate(self.source, bad, self.audit)

    def test_determinism_and_tracked_report(self):
        with tempfile.TemporaryDirectory(dir="build") as a, tempfile.TemporaryDirectory(dir="build") as b:
            pa, pb = Path(a)/"report.json", Path(b)/"report.json"
            compile_ui_qa(DEFAULT_SOURCE, DEFAULT_LAYOUT, DEFAULT_AUDIT, pa)
            compile_ui_qa(DEFAULT_SOURCE, DEFAULT_LAYOUT, DEFAULT_AUDIT, pb)
            self.assertEqual(pa.read_bytes(), pb.read_bytes())
            self.assertEqual(pa.read_bytes(), Path("docs/data/stage6_ui_qa.json").read_bytes())


if __name__ == "__main__": unittest.main()
