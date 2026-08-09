from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.cli import build_parser
from tools.pokeagent.generated_intake import (
    GeneratedIntakeError,
    inspect_generated_asset,
    write_intake_report,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"
RAW = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"
CONCEPT = ROOT / "assets/concepts/stage4h_generated_shrine_concept.png"
REFERENCE_GLB = ROOT / "assets/source/stage4f_glb_faceted_tower.glb"


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TemporaryIntake:
    def __init__(self, source: bytes) -> None:
        self.source_dir = Path(tempfile.mkdtemp(dir=ROOT / "assets/source/generated"))
        self.provenance_dir = Path(tempfile.mkdtemp(dir=ROOT / "assets/provenance"))
        self.manifest_dir = Path(tempfile.mkdtemp(dir=ROOT / "assets/manifests"))
        self.source = self.source_dir / "candidate.glb"
        self.provenance = self.provenance_dir / "candidate.json"
        self.manifest_path = self.manifest_dir / "candidate.json"
        self.source.write_bytes(source)
        self.manifest = copy.deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
        self.manifest["id"] = "temporary_generated_candidate"
        self.manifest["source"] = self.source.relative_to(ROOT).as_posix()
        self.manifest["source_sha256"] = _hash(source)
        self.manifest["provenance"] = self.provenance.relative_to(ROOT).as_posix()
        self.write()

    def write(self) -> None:
        provenance = {
            "asset_id": self.manifest["id"],
            "raw_output_sha256": self.manifest["source_sha256"],
            "concept_sha256": self.manifest["concept_sha256"],
            "generator": "synthetic-test",
            "generator_model": "none",
            "generator_revision": "test",
        }
        self.provenance.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def close(self) -> None:
        for directory in (self.source_dir, self.provenance_dir, self.manifest_dir):
            for path in directory.iterdir():
                path.unlink()
            directory.rmdir()


class Stage4HGeneratedIntakeTests(unittest.TestCase):
    def test_canonical_generated_candidate_is_rejected_with_complete_evidence(self) -> None:
        before = RAW.read_bytes()
        report = inspect_generated_asset(MANIFEST, ROOT)
        self.assertTrue(report["success"])
        self.assertFalse(report["accepted"])
        self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        self.assertEqual(report["source"]["sha256"], "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60")
        self.assertEqual(report["structure"]["node_count"], 2)
        self.assertEqual(report["structure"]["mesh_count"], 1)
        self.assertEqual(report["structure"]["material_count"], 0)
        self.assertEqual(report["geometry"]["triangle_count"], 6664)
        self.assertEqual(report["geometry"]["position_count"], 3360)
        self.assertEqual(report["budget"]["projected_nitro_bytes_if_attributes_existed"], 453164)
        self.assertEqual(report["budget"]["capacity_bytes"], 1068)
        codes = [problem["code"] for problem in report["stage4f"]["problems"]]
        for code in (
            "unsupported_scene", "hierarchy_unsupported", "material_count_invalid",
            "missing_normal", "missing_texcoord_0", "unexpected_attribute",
            "accessor_element_budget_exceeded", "vertex_budget_exceeded",
            "face_budget_exceeded", "ds_display_list_overflow",
        ):
            self.assertIn(code, codes)
        self.assertFalse(report["stage4g"]["exact_simplification_applicable"])
        self.assertEqual(RAW.read_bytes(), before)

    def test_report_and_cli_plan_are_deterministic(self) -> None:
        first = inspect_generated_asset(MANIFEST, ROOT)
        second = inspect_generated_asset(MANIFEST, ROOT)
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            write_intake_report(MANIFEST, Path(first_dir), ROOT)
            write_intake_report(MANIFEST, Path(second_dir), ROOT)
            self.assertEqual(
                (Path(first_dir) / "intake-report.json").read_bytes(),
                (Path(second_dir) / "intake-report.json").read_bytes(),
            )
        parsed = build_parser().parse_args(["asset", "intake", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "intake"))

    def test_known_stage4f_subset_is_accepted_by_the_same_analyzer(self) -> None:
        temporary = TemporaryIntake(REFERENCE_GLB.read_bytes())
        try:
            report = inspect_generated_asset(temporary.manifest_path, ROOT)
            self.assertTrue(report["accepted"])
            self.assertTrue(report["stage4f"]["compliant"])
            self.assertEqual(report["quality_classification"], "ACCEPTABLE_WITHOUT_MANUAL_CLEANUP")
            self.assertLessEqual(
                report["budget"]["projected_nitro_bytes_if_attributes_existed"],
                report["budget"]["capacity_bytes"],
            )
        finally:
            temporary.close()

    def test_hash_path_and_container_failures_are_stable(self) -> None:
        temporary = TemporaryIntake(REFERENCE_GLB.read_bytes())
        try:
            temporary.manifest["source_sha256"] = "0" * 64
            temporary.write()
            with self.assertRaises(GeneratedIntakeError) as raised:
                inspect_generated_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "source_hash_mismatch")

            temporary.manifest["source"] = "assets/source/generated/../stage4f_glb_faceted_tower.glb"
            temporary.manifest["source_sha256"] = _hash(REFERENCE_GLB.read_bytes())
            temporary.write()
            with self.assertRaises(GeneratedIntakeError) as raised:
                inspect_generated_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "unsafe_path")
        finally:
            temporary.close()

        malformed = TemporaryIntake(b"not a GLB")
        try:
            with self.assertRaises(GeneratedIntakeError) as raised:
                inspect_generated_asset(malformed.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "malformed_glb_length")
        finally:
            malformed.close()

    def test_concept_and_raw_input_are_tracked_canonical_evidence(self) -> None:
        self.assertEqual(CONCEPT.stat().st_size, 1375386)
        self.assertEqual(_hash(CONCEPT.read_bytes()), "06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f")
        self.assertEqual(RAW.stat().st_size, 134740)

    def test_clean_target_cannot_delete_canonical_generated_source(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertNotIn('find . -type d -name "generated"', makefile)
        self.assertIn("armips/include/generated include/constants/generated data/generated", makefile)
        self.assertNotIn("assets/source/generated", makefile)


if __name__ == "__main__":
    unittest.main()
