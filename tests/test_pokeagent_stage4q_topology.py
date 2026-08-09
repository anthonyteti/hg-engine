from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.assets import (
    _encode_asset_primitives, _ir_primitives, _normalized_ir, compile_asset, load_manifest,
)
from tools.pokeagent.cli import build_parser
from tools.pokeagent.glb import GLBError, parse_glb
from tools.pokeagent.glb_bootstrap import bootstrap_geometry_glb
from tools.pokeagent.glb_geometry_reduce import pack_geometry_glb, parse_geometry_glb, reduce_geometry_manifest
from tools.pokeagent.glb_topology import (
    TopologyGLBError, inspect_topology_sanitation_applicability, load_topology_manifest,
    run_topology_manifest, sanitize_topology_glb, write_topology_outputs,
)
from tools.pokeagent.mesh_predecimate import GeometryReductionError, reduce_geometry_components, validate_geometry
from tools.pokeagent.mesh_sanitize import MeshSanitizeError, _topology, sanitize_mesh
from tools.pokeagent.stage4q_fixture import (
    build_boundary_loop_fixture, build_near_zero_fixture, build_stage4q_multicomponent,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4q_generated_topology.json"
SOURCE = ROOT / "assets/source/stage4q_generated_multicomponent.glb"
REFERENCE = ROOT / "assets/source/stage4q_sanitized_reference.glb"
STAGE4H = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"


class Stage4QTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, _data = load_topology_manifest(MANIFEST, ROOT)
        cls.result = run_topology_manifest(MANIFEST, ROOT)
        cls.topology_policy = cls.manifest["preprocessing"]["topology"]
        cls.reduction_policy = cls.manifest["preprocessing"]["geometry_reduction"]

    def test_source_fixture_and_exact_reference_are_reproducible(self) -> None:
        source, reference = build_stage4q_multicomponent()
        self.assertEqual(source, SOURCE.read_bytes())
        self.assertEqual(reference, REFERENCE.read_bytes())
        self.assertEqual(hashlib.sha256(source).hexdigest(), "629529520af2246825a25cfd6f779990005198d13e0adae061e910f3cb6afcec")
        sanitized = sanitize_topology_glb(source, self.topology_policy)
        self.assertEqual(sanitized["canonical_glb"], reference)
        report = sanitized["report"]["sanitation"]
        self.assertEqual(report["removed_face_count"], 1)
        self.assertEqual(report["removed_categories"]["collinear_zero_area"], 1)
        self.assertFalse(report["positions_moved"])
        self.assertFalse(report["vertices_welded"])

    def test_near_zero_nonzero_triangle_survives(self) -> None:
        positions, faces = build_near_zero_fixture()
        mesh, report = sanitize_mesh(positions, faces, remove_exact_zero_area_faces=True)
        self.assertEqual(len(mesh["faces"]), 1)
        self.assertEqual(report["near_zero_nonzero_faces_preserved"], 1)
        self.assertEqual(report["removed_categories"]["collinear_zero_area"], 1)

    def test_exact_categories_and_all_zero_failure_are_stable(self) -> None:
        positions = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (1, 1, 0)]
        mesh, report = sanitize_mesh(positions, [(0, 1, 2), (0, 3, 4)], remove_exact_zero_area_faces=True)
        self.assertEqual(len(mesh["faces"]), 1)
        self.assertEqual(report["removed_face_count"], 1)
        with self.assertRaises(MeshSanitizeError) as raised:
            sanitize_mesh(positions[:3], [(0, 1, 2)], remove_exact_zero_area_faces=True)
        self.assertEqual(raised.exception.code, "topology_sanitize_all_faces_removed")
        positions.extend(((3, 0, 0), (4, 0, 0), (5, 0, 0)))
        _mesh, report = sanitize_mesh(
            positions, [(0, 1, 2), (5, 6, 7), (0, 3, 4)], remove_exact_zero_area_faces=True,
        )
        self.assertEqual(report["removed_face_count"], 2)

    def test_multicomponent_reduction_preserves_every_component_and_loop(self) -> None:
        reduction = self.result["report"]["reduction"]
        self.assertEqual((reduction["source"]["connected_components"], reduction["final"]["connected_components"]), (2, 2))
        self.assertEqual((reduction["source"]["boundary_loops"], reduction["final"]["boundary_loops"]), (1, 1))
        self.assertTrue(reduction["component_survival"])
        self.assertFalse(reduction["component_merge_or_split"])
        self.assertEqual((reduction["final"]["positions"], reduction["final"]["triangles"]), (32, 55))
        self.assertEqual([(item["source_faces"], item["target_faces"], item["final_faces"]) for item in reduction["component_reports"]], [(1056, 39, 39), (32, 17, 16)])
        self.assertGreaterEqual(reduction["metrics"]["minimum_silhouette_iou"], 0.84)

    def test_legitimate_multiple_boundary_loops_are_preserved(self) -> None:
        fixture = build_boundary_loop_fixture()
        topology = validate_geometry(fixture)
        self.assertEqual((topology["connected_components"], topology["boundary_loops"]), (1, 2))
        detailed = _topology(fixture["positions"], fixture["faces"])
        self.assertEqual(detailed["boundary_loop_vertex_counts"], [4, 4])

    def test_qop_pipeline_reaches_unchanged_stage4f(self) -> None:
        report = self.result["report"]
        self.assertTrue(report["stage4f_accepted"])
        parsed = parse_glb(self.result["canonical_glb"])
        self.assertEqual(len(parsed.faces), 55)
        self.assertEqual(report["bootstrap"]["material"]["name"], "generated_surface")
        self.assertEqual(report["canonical_sha256"], "ef022994ecdd5574940284d992de237236b1ff32313695ae60e942baca77f0f7")
        with self.assertRaises(GLBError):
            parse_glb(self.result["sanitized_glb"])

    def test_completed_geometry_has_a_bounded_stage4i_display_list(self) -> None:
        proof_manifest, _raw = load_manifest(ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json", ROOT)
        mesh = parse_glb(self.result["canonical_glb"])
        ir = _normalized_ir(proof_manifest, mesh, ROOT)
        display_list, plan = _encode_asset_primitives(_ir_primitives(ir))
        self.assertEqual((plan["triangle_count"], plan["vertex_count"], len(display_list)), (55, 165, 3752))
        self.assertLessEqual(len(display_list), 4096)
        self.assertEqual(hashlib.sha256(display_list).hexdigest(), "144f555b4cc98cf20f0d092000463f4eb19d7c52f67f971c14cba74451ef4c11")
        self.assertEqual(proof_manifest["material_policy"]["mappings"]["generated_surface"]["texture"], "stage4d_stone")

    def test_order_component_and_degenerate_order_invariance(self) -> None:
        reversed_source, _reference = build_stage4q_multicomponent(reverse_faces=True)
        sanitized = sanitize_topology_glb(reversed_source, self.topology_policy)
        self.assertEqual(sanitized["canonical_glb"], self.result["sanitized_glb"])
        reduced, report = reduce_geometry_components(sanitized["geometry"], self.reduction_policy)
        self.assertEqual(pack_geometry_glb(reduced), self.result["reduced_glb"])
        self.assertEqual([item["component_id"] for item in report["component_reports"]], [item["component_id"] for item in self.result["report"]["reduction"]["component_reports"]])

    def test_translation_and_independent_component_mutations_are_isolated(self) -> None:
        translated_source, _ = build_stage4q_multicomponent(component_translation=1.0)
        translated = sanitize_topology_glb(translated_source, self.topology_policy)
        output, report = reduce_geometry_components(translated["geometry"], self.reduction_policy)
        canonical_faces = self.result["geometry"]["faces"]
        self.assertEqual(len(output["faces"]), len(canonical_faces))
        self.assertEqual(sorted(item["target_faces"] for item in report["component_reports"]), [17, 39])
        self.assertNotEqual(pack_geometry_glb(output), self.result["reduced_glb"])
        canonical_body = sorted(point for point in self.result["geometry"]["positions"] if point[0] < 3.0)
        translated_body = sorted(point for point in output["positions"] if point[0] < 3.0)
        self.assertEqual(translated_body, canonical_body)

    def test_whole_mesh_translation_is_semantically_invariant(self) -> None:
        canonical = sanitize_topology_glb(SOURCE.read_bytes(), self.topology_policy)["geometry"]
        delta = (100.0, -20.0, 7.0)
        translated = {
            "schema_version": 1,
            "positions": [tuple(point[axis] + delta[axis] for axis in range(3)) for point in canonical["positions"]],
            "faces": canonical["faces"],
        }
        output, report = reduce_geometry_components(translated, self.reduction_policy)
        self.assertEqual(output["faces"], self.result["geometry"]["faces"])
        for actual, expected in zip(output["positions"], self.result["geometry"]["positions"], strict=True):
            self.assertTrue(all(abs(actual[axis] - delta[axis] - expected[axis]) < 2e-5 for axis in range(3)))
        self.assertEqual(sorted(item["target_faces"] for item in report["component_reports"]), [17, 39])

    def test_component_scale_and_target_mutations_are_predictable(self) -> None:
        scaled_source, _ = build_stage4q_multicomponent(component_scale=3.0)
        scaled = sanitize_topology_glb(scaled_source, self.topology_policy)
        output, report = reduce_geometry_components(scaled["geometry"], self.reduction_policy)
        allocations = sorted(item["target_faces"] for item in report["component_reports"])
        self.assertNotEqual(allocations, [17, 39])
        self.assertEqual(len(output["faces"]), sum(item["final_faces"] for item in report["component_reports"]))
        impossible = dict(self.reduction_policy); impossible["target_faces"] = 40
        canonical = sanitize_topology_glb(SOURCE.read_bytes(), self.topology_policy)["geometry"]
        with self.assertRaises(GeometryReductionError) as raised:
            reduce_geometry_components(canonical, impossible)
        self.assertEqual(raised.exception.code, "geometry_predecimation_target_unreachable")

    def test_failures_reject_repair_and_component_deletion(self) -> None:
        with self.assertRaises(MeshSanitizeError) as raised:
            sanitize_mesh([(0,0,0),(1,0,0),(0,1,0)], [(0,1,2)], remove_exact_zero_area_faces=False)
        self.assertEqual(raised.exception.code, "topology_sanitize_policy_required")
        positions = []; faces = []
        for component in range(5):
            offset = len(positions); x = component * 3.0
            positions.extend(((x,0,0),(x+1,0,0),(x,1,0))); faces.append((offset,offset+1,offset+2))
        offset = len(positions); positions.extend(((99,0,0),(100,0,0),(101,0,0))); faces.append((offset,offset+1,offset+2))
        with self.assertRaises(MeshSanitizeError) as raised:
            sanitize_mesh(positions, faces, remove_exact_zero_area_faces=True, max_components=4)
        self.assertEqual(raised.exception.code, "topology_sanitize_component_limit")
        policy = dict(self.topology_policy); policy["color0_policy"] = "reject"
        with self.assertRaises(TopologyGLBError) as raised:
            sanitize_topology_glb(SOURCE.read_bytes(), policy)
        self.assertEqual(raised.exception.code, "topology_color0_policy_required")

    def test_nonmanifold_winding_and_branching_boundaries_reject(self) -> None:
        exact = [(9,0,0),(10,0,0),(11,0,0)]
        positions = [(0,0,0),(1,0,0),(0,1,0),(0,-1,0),(0,0,1)] + exact
        with self.assertRaises(MeshSanitizeError) as raised:
            sanitize_mesh(
                positions, [(0,1,2),(1,0,3),(0,1,4),(5,6,7)],
                remove_exact_zero_area_faces=True,
            )
        self.assertEqual(raised.exception.code, "topology_sanitize_non_manifold")
        with self.assertRaises(MeshSanitizeError) as raised:
            sanitize_mesh(
                positions, [(0,1,2),(0,1,3),(5,6,7)],
                remove_exact_zero_area_faces=True,
            )
        self.assertEqual(raised.exception.code, "topology_sanitize_inconsistent_winding")
        branching_positions = [(0,0,0),(1,0,0),(0,1,0),(-1,0,0),(0,-1,0)] + exact
        with self.assertRaises(MeshSanitizeError) as raised:
            sanitize_mesh(
                branching_positions, [(0,1,2),(0,3,4),(5,6,7)],
                remove_exact_zero_area_faces=True,
            )
        self.assertEqual(raised.exception.code, "topology_sanitize_branching_boundary")

    def test_clean_runs_and_cli_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            one = write_topology_outputs(MANIFEST, Path(first), ROOT)
            two = write_topology_outputs(MANIFEST, Path(second), ROOT)
            for name in ("sanitized-geometry.glb", "reduced-geometry.glb", "bootstrapped.glb", "generated-topology-report.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
            self.assertEqual(one["report_sha256"], two["report_sha256"])
        args = build_parser().parse_args(["asset", "topology-sanitize", str(MANIFEST), "--json"])
        self.assertEqual(args.asset_command, "topology-sanitize")

    def test_stage4h_exact_policy_projection_keeps_historical_source_immutable(self) -> None:
        before = STAGE4H.read_bytes()
        projection = inspect_topology_sanitation_applicability(before)
        self.assertFalse(projection["applicable"])
        self.assertTrue(projection["color0_discard_applicable"])
        analysis = projection["analysis"]
        self.assertEqual(analysis["exact_zero_area_faces"], 0)
        self.assertEqual(analysis["near_zero_nonzero_faces"], 1)
        self.assertAlmostEqual(analysis["minimum_cross_squared"], 2.6948343349697145e-19)
        self.assertEqual(analysis["full_topology"]["connected_components"], 2)
        self.assertEqual(analysis["full_topology"]["boundary_loops"], 24)
        self.assertEqual(hashlib.sha256(before).hexdigest(), "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60")
        self.assertEqual(STAGE4H.read_bytes(), before)

    def test_stage4o_stage4p_and_stage4j_regressions_are_exact(self) -> None:
        stage4o = reduce_geometry_manifest(ROOT / "assets/manifests/stage4o_dense_geometry_shrine.json", ROOT)
        self.assertEqual(stage4o["report"]["canonical_sha256"], "7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957")
        stage4p = compile_asset(ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json", ROOT)
        self.assertEqual(hashlib.sha256(stage4p["bootstrapped_glb"]).hexdigest(), "06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1")
        stage4j = compile_asset(ROOT / "assets/manifests/stage4j_dense_stone_shrine.json", ROOT)["report"]
        self.assertEqual(stage4j["display_list_bytes"], 4024)
        self.assertEqual(stage4j["hashes"]["display_list_sha256"], "e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04")


if __name__ == "__main__":
    unittest.main()
