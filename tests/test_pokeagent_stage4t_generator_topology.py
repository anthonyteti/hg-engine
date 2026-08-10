from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.assets import compile_asset
from tools.pokeagent.generator_topology import (
    GeneratorTopologyError,
    load_generator_topology_manifest,
    run_generator_topology_manifest,
    write_generator_topology_outputs,
)
from tools.pokeagent.glb_geometry_reduce import reduce_geometry_manifest
from tools.pokeagent.glb_topology import run_topology_manifest
from tools.pokeagent.glb_tinyface import run_tinyface_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4t_triposr_topology_sweep.json"
RAW64 = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"
RAW48 = ROOT / "assets/source/generated/stage4t_triposr_shrine_mc48_raw.glb"
RAW32 = ROOT / "assets/source/generated/stage4t_triposr_shrine_mc32_raw.glb"


class Stage4TGeneratorTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_generator_topology_manifest(MANIFEST, ROOT)
        cls.report = cls.result["report"]
        cls.by_resolution = {item["resolution"]: item for item in cls.report["candidates"]}

    def _mutated_manifest(self, mutation) -> Path:
        document = json.loads(MANIFEST.read_text(encoding="utf-8")); mutation(document)
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", dir=ROOT / "build", delete=False, encoding="utf-8")
        json.dump(document, handle, sort_keys=True); handle.write("\n"); handle.close()
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_exact_generator_revision_inputs_and_candidate_hashes_are_locked(self) -> None:
        manifest = load_generator_topology_manifest(MANIFEST, ROOT)
        self.assertEqual(manifest["generator"]["revision"], "f84354eb350eb07a108faf33a6bc564d455f9764")
        self.assertEqual(manifest["generator"]["foreground_ratio"], 0.85)
        self.assertEqual(manifest["generator"]["accepted_resolution_range"], [32, 320])
        self.assertEqual(hashlib.sha256(RAW64.read_bytes()).hexdigest(), "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60")
        self.assertEqual(hashlib.sha256(RAW48.read_bytes()).hexdigest(), "b797e1851c0e517190f95a981a5b9dab61fe889d9c87a6a680e9217090242d7b")
        self.assertEqual(hashlib.sha256(RAW32.read_bytes()).hexdigest(), "da389a6595a8fb59e5bff19f2a480f1683d3c8aef7b4a590af396873c125fa2e")
        bad = self._mutated_manifest(lambda value: value["candidates"][0].update(sha256="0" * 64))
        with self.assertRaises(GeneratorTopologyError) as raised:
            load_generator_topology_manifest(bad, ROOT)
        self.assertEqual(raised.exception.code, "generator_sweep_hash_mismatch")

    def test_mc48_passes_raw_fidelity_but_fails_unchanged_stage4q(self) -> None:
        candidate = self.by_resolution[48]
        self.assertEqual((candidate["raw"]["positions"], candidate["raw"]["triangles"]), (1864, 3671))
        self.assertAlmostEqual(candidate["raw_fidelity"]["minimum"], 0.895533)
        self.assertTrue(candidate["raw_fidelity"]["passed"])
        topology = candidate["raw"]["topology"]
        self.assertEqual((topology["connected_components"], topology["boundary_edges"]), (1, 107))
        self.assertEqual((topology["valid_closed_boundary_loops"], topology["branching_boundary_vertices"]), (23, 2))
        self.assertEqual(topology["branching_boundary_degrees"], {"4": 2})
        self.assertEqual(candidate["stage4q"]["error"]["code"], "topology_sanitize_branching_boundary")
        self.assertFalse(candidate["stage4q"]["success"])
        self.assertFalse(candidate["stage4r"]["attempted"])

    def test_mc32_fails_raw_fidelity_and_has_branching_boundary(self) -> None:
        candidate = self.by_resolution[32]
        self.assertEqual((candidate["raw"]["positions"], candidate["raw"]["triangles"]), (787, 1544))
        self.assertAlmostEqual(candidate["raw_fidelity"]["minimum"], 0.809144)
        self.assertFalse(candidate["raw_fidelity"]["passed"])
        topology = candidate["raw"]["topology"]
        self.assertEqual((topology["connected_components"], topology["boundary_edges"]), (1, 52))
        self.assertEqual((topology["valid_closed_boundary_loops"], topology["branching_boundary_vertices"]), (11, 1))
        self.assertEqual(candidate["blocking_gate"], "raw_fidelity_below_0_88")
        self.assertFalse(candidate["stage4q"]["attempted"])

    def test_sweep_stops_before_forbidden_later_gates(self) -> None:
        self.assertFalse(self.report["success"])
        self.assertEqual(self.report["verdict"], "STAGE_4T_GENERATOR_TOPOLOGY_BLOCKED")
        self.assertEqual(self.report["generator_classification"], "TRIPOSR_TOPOLOGY_REMAINS_TOO_COMPLEX")
        self.assertEqual(self.report["stage4_disposition"], "STAGE_4_ASSET_INFRASTRUCTURE_HAS_SPECIFIC_BLOCKER")
        self.assertEqual(self.report["semantic_sha256"], "9728dedc5e0e4cdf0d8530361e2dde6bf289daa56c44420d63932a1e039f6414")
        self.assertIsNone(self.report["selected_candidate"])
        for resolution in (48, 32):
            candidate = self.by_resolution[resolution]
            for stage in ("stage4o", "stage4p", "stage4f", "stage4j", "stage4i", "rom"):
                self.assertFalse(candidate[stage]["attempted"])
        for resolution in (24, 16):
            self.assertEqual(self.by_resolution[resolution]["status"], "unsupported")
            self.assertEqual(self.by_resolution[resolution]["reason"], "official_generate_api_minimum_resolution_32")

    def test_raw_color_and_target_null_intake_metrics_are_evidence_only(self) -> None:
        expected = {
            48: (1864, 7456, "82a75b2599972532bffcd2fc8359de09ddd2e586bdbd728a12aee982125a9e32", 1),
            32: (787, 3148, "1997e8859710bbd87ca5725c4413162fd635d078e48fdfa1e12442c16401e677", 0),
        }
        for resolution, (count, size, digest, blocking) in expected.items():
            raw = self.by_resolution[resolution]["raw"]
            color = raw["color0"]
            self.assertEqual((color["component_type"], color["type"], color["normalized"]), (5121, "VEC4", True))
            self.assertEqual((color["count"], color["payload_bytes"], color["payload_sha256"]), (count, size, digest))
            self.assertEqual(raw["exact_zero_faces"], 0)
            self.assertEqual(raw["target_face_classifications"].get("TARGET_QUANTIZED_DEGENERATE", 0), blocking)

    def test_two_clean_analysis_roots_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            one = write_generator_topology_outputs(MANIFEST, Path(first), ROOT)
            two = write_generator_topology_outputs(MANIFEST, Path(second), ROOT)
            self.assertEqual((Path(first) / "stage4t-report.json").read_bytes(), (Path(second) / "stage4t-report.json").read_bytes())
            self.assertEqual(one["semantic_sha256"], two["semantic_sha256"])
            self.assertEqual(one["outputs"]["view_sha256"], two["outputs"]["view_sha256"])
            self.assertEqual(one["outputs"]["derived_glbs"], [])
            self.assertIsNone(one["outputs"]["rom"])

    def test_prior_stage_hashes_and_outputs_remain_exact(self) -> None:
        before = {path: path.read_bytes() for path in (RAW64, RAW48, RAW32)}
        q = run_topology_manifest(ROOT / "assets/manifests/stage4q_generated_topology.json", ROOT)
        self.assertEqual(q["report"]["canonical_sha256"], "ef022994ecdd5574940284d992de237236b1ff32313695ae60e942baca77f0f7")
        r = run_tinyface_manifest(ROOT / "assets/manifests/stage4r_target_null.json", ROOT)
        self.assertEqual(r["report"]["canonical_sha256"], "69deff902150a082981a624a391a3b25629f8e6628dcbe1f6c3e21df0cfcd814")
        o = reduce_geometry_manifest(ROOT / "assets/manifests/stage4o_dense_geometry_shrine.json", ROOT)
        self.assertEqual(o["report"]["canonical_sha256"], "7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957")
        p = compile_asset(ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json", ROOT)
        self.assertEqual(hashlib.sha256(p["bootstrapped_glb"]).hexdigest(), "06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1")
        j = compile_asset(ROOT / "assets/manifests/stage4j_dense_stone_shrine.json", ROOT)["report"]
        self.assertEqual((j["display_list_bytes"], j["hashes"]["display_list_sha256"]), (4024, "e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04"))
        for path, data in before.items(): self.assertEqual(path.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
