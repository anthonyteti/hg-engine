from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.generated_pipeline import (
    GeneratedPipelineError, load_generated_pipeline_manifest,
    run_generated_pipeline_manifest, write_generated_pipeline_outputs,
)
from tools.pokeagent.glb_tinyface import run_tinyface_manifest
from tools.pokeagent.glb_topology import run_topology_manifest
from tools.pokeagent.glb_geometry_reduce import reduce_geometry_manifest
from tools.pokeagent.assets import compile_asset


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4s_real_generated_shrine.json"
RAW = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"


class Stage4SRealGeneratedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_generated_pipeline_manifest(MANIFEST, ROOT)
        cls.report = cls.result["report"]

    def _mutated_manifest(self, mutation) -> Path:
        document = json.loads(MANIFEST.read_text(encoding="utf-8")); mutation(document)
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", dir=ROOT / "build", delete=False, encoding="utf-8")
        json.dump(document, handle, sort_keys=True); handle.write("\n"); handle.close()
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_immutable_source_and_provenance_are_hash_locked(self) -> None:
        manifest, source = load_generated_pipeline_manifest(MANIFEST, ROOT)
        self.assertEqual(hashlib.sha256(source).hexdigest(), "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60")
        self.assertEqual(manifest["_source_path"], str(RAW.resolve()))
        wrong = self._mutated_manifest(lambda value: value.update(source_sha256="0" * 64))
        with self.assertRaises(GeneratedPipelineError) as raised:
            load_generated_pipeline_manifest(wrong, ROOT)
        self.assertEqual(raised.exception.code, "SOURCE_PROVENANCE_MISMATCH")

    def test_real_pipeline_fails_closed_at_unchanged_stage4o(self) -> None:
        report = self.report
        self.assertFalse(report["success"])
        self.assertEqual(report["failure"]["phase"], "stage4o")
        self.assertEqual(report["failure"]["code"], "geometry_predecimation_target_unreachable")
        self.assertEqual(report["failure"]["details"]["best_valid_faces"], 177)
        self.assertEqual(report["failure"]["details"]["best_valid_positions"], 103)
        self.assertEqual(report["failure"]["details"]["accepted_collapses_before_stall"], 3251)
        self.assertEqual((report["failure"]["details"]["target_faces"], report["failure"]["details"]["target_positions"]), (56, 58))
        for stage in ("stage4p", "stage4f", "stage4j", "stage4i", "rom", "qa"):
            self.assertFalse(report[stage]["attempted"])
        self.assertIsNone(self.result["reduced_glb"]); self.assertIsNone(self.result["canonical_glb"])

    def test_color_q_r_and_post_topology_match_read_only_projection(self) -> None:
        color = self.report["color0"]["evidence"]
        self.assertEqual((color["accessor"], color["component_type"], color["type"], color["normalized"], color["count"], color["payload_bytes"]), (2, 5121, "VEC4", True, 3360, 13440))
        self.assertEqual(color["payload_sha256"], "019534d056ff0fc4713bfdedcbf6bb6adf320eb23a64edb407edc21c9bdb910e")
        self.assertEqual(self.report["stage4q"]["removed_face_count"], 0)
        tiny = self.report["stage4r"]
        self.assertEqual(tiny["removed_face_count"], 1)
        self.assertEqual(tiny["removed_faces"][0]["canonical_source_face_id"], "4ce5eedec161d4af")
        self.assertEqual(tiny["removed_faces"][0]["target_quantized_positions"], [[-507, 3735, -1636]] * 3)
        topology = tiny["final_topology"]
        self.assertEqual((tiny["final_positions"], tiny["final_triangles"]), (3360, 6663))
        self.assertEqual((topology["connected_components"], topology["boundary_edges"], topology["boundary_loops"]), (2, 99, 25))
        self.assertEqual(sorted((part["positions"], part["faces"]) for part in topology["components"]), [(6, 8), (3354, 6655)])

    def test_stage4o_uses_untuned_canonical_policy_and_stable_allocation(self) -> None:
        stage = self.report["stage4o"]
        self.assertEqual((stage["policy"]["target_faces"], stage["policy"]["target_positions"]), (64, 64))
        allocations = sorted((part["source_faces"], part["source_positions"], part["target_faces"], part["target_positions"]) for part in stage["component_plan"])
        self.assertEqual(allocations, [(8, 6, 8, 6), (6655, 3354, 56, 58)])
        self.assertEqual(stage["error"]["details"]["rejected_collapse_reasons"], {
            "batch_conflict": 105982, "boundary": 12452, "degenerate": 61,
            "face_rotation": 23443, "ground_contact": 270, "topology_link": 10421,
        })

    def test_two_clean_derived_roots_are_byte_identical_and_contain_no_later_artifact(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            one = write_generated_pipeline_outputs(MANIFEST, Path(first), ROOT)
            two = write_generated_pipeline_outputs(MANIFEST, Path(second), ROOT)
            for name in ("derived-post-qr.glb", "stage4s-report.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
            for name in one["outputs"]["post_qr_views"]:
                self.assertEqual((Path(first) / "views" / name).read_bytes(), (Path(second) / "views" / name).read_bytes())
            self.assertEqual(one["outputs"]["view_sha256"], two["outputs"]["view_sha256"])
            self.assertFalse((Path(first) / "reduced.glb").exists())
            self.assertEqual(one["outputs"]["screenshots"], [])

    def test_intended_size_and_texture_mutations_are_deterministic_and_orthogonal(self) -> None:
        size_path = self._mutated_manifest(lambda value: value.update(intended_size_tiles=[4.5, 6.75, 4.5]))
        sized = run_generated_pipeline_manifest(size_path, ROOT)["report"]
        self.assertEqual(sized["stage4r"]["removed_face_count"], 1)
        self.assertAlmostEqual(sized["stage4r"]["policy"]["normalization"]["units_to_tiles"], 5.678701403731731)
        self.assertEqual(sized["failure"], self.report["failure"])
        texture_path = self._mutated_manifest(lambda value: value["appearance"].update(project_texture="stage4d_wood"))
        textured = run_generated_pipeline_manifest(texture_path, ROOT)["report"]
        self.assertEqual(textured["stage4q"], self.report["stage4q"])
        self.assertEqual(textured["stage4r"], self.report["stage4r"])
        self.assertEqual(textured["stage4o"], self.report["stage4o"])
        self.assertEqual(textured["appearance"]["project_texture"], "stage4d_wood")

    def test_stage4h_history_and_raw_bytes_remain_immutable(self) -> None:
        before = RAW.read_bytes(); run_generated_pipeline_manifest(MANIFEST, ROOT)
        self.assertEqual(RAW.read_bytes(), before)
        self.assertEqual(self.report["historical_stage4h"]["verdict"], ["STAGE_4H_GENERATED_ASSET_REJECTED", "REJECTED_UNSUPPORTED_STRUCTURE"])

    def test_stage4r_q_p_o_j_and_writer_regressions_remain_exact(self) -> None:
        r = run_tinyface_manifest(ROOT / "assets/manifests/stage4r_target_null.json", ROOT)
        self.assertEqual(r["report"]["canonical_sha256"], "69deff902150a082981a624a391a3b25629f8e6628dcbe1f6c3e21df0cfcd814")
        q = run_topology_manifest(ROOT / "assets/manifests/stage4q_generated_topology.json", ROOT)
        self.assertEqual(q["report"]["canonical_sha256"], "ef022994ecdd5574940284d992de237236b1ff32313695ae60e942baca77f0f7")
        o = reduce_geometry_manifest(ROOT / "assets/manifests/stage4o_dense_geometry_shrine.json", ROOT)
        self.assertEqual(o["report"]["canonical_sha256"], "7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957")
        p = compile_asset(ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json", ROOT)
        self.assertEqual(hashlib.sha256(p["bootstrapped_glb"]).hexdigest(), "06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1")
        j = compile_asset(ROOT / "assets/manifests/stage4j_dense_stone_shrine.json", ROOT)["report"]
        self.assertEqual((j["display_list_bytes"], j["hashes"]["display_list_sha256"]), (4024, "e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04"))
        expected = {
            "stage4k_flat_reference.glb": "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6",
            "stage4l_authored_normals_reference.glb": "b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9",
            "stage4m_authored_uv_reference.glb": "c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84",
            "stage4n_authored_material_reference.glb": "3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66",
        }
        for name, digest in expected.items(): self.assertEqual(hashlib.sha256((ROOT / "assets/source" / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
