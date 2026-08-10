from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.assets import (
    _encode_asset_primitives,
    _ir_primitives,
    _normalized_ir,
    compile_asset,
    load_manifest,
)
from tools.pokeagent.cli import build_parser
from tools.pokeagent.geometry import quantize_vtx16_coordinate
from tools.pokeagent.glb import _chunks, pack_glb, parse_glb
from tools.pokeagent.glb_geometry_reduce import pack_geometry_glb, reduce_geometry_manifest
from tools.pokeagent.glb_tinyface import (
    TinyFaceGLBError,
    _exact_stage4q_in_memory,
    inspect_stage4h_tiny_face,
    load_tinyface_manifest,
    run_tinyface_manifest,
    run_tinyface_pipeline,
    write_tinyface_outputs,
)
from tools.pokeagent.glb_topology import run_topology_manifest
from tools.pokeagent.mesh_predecimate import GeometryReductionError, canonical_geometry
from tools.pokeagent.mesh_sanitize import sanitize_mesh
from tools.pokeagent.mesh_tinyface import (
    TinyFaceError,
    classify_target_faces,
    remove_target_null_faces,
)
from tools.pokeagent.stage4r_fixture import build_rounding_probe, build_stage4r_target_null


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4r_target_null.json"
SOURCE = ROOT / "assets/source/stage4r_target_null_generated.glb"
REFERENCE = ROOT / "assets/source/stage4r_target_null_reference.glb"
STAGE4H = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"


class Stage4RTinyFaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, _source = load_tinyface_manifest(MANIFEST, ROOT)
        cls.result = run_tinyface_manifest(MANIFEST, ROOT)
        cls.q_policy = cls.manifest["preprocessing"]["topology"]
        cls.r_policy = cls.manifest["preprocessing"]["tiny_faces"]

    def test_fixture_hashes_and_independent_reference_are_reproducible(self) -> None:
        source, reference, metadata = build_stage4r_target_null()
        self.assertEqual(source, SOURCE.read_bytes())
        self.assertEqual(reference, REFERENCE.read_bytes())
        self.assertEqual(hashlib.sha256(source).hexdigest(), "2912d3e0c32f64154df17b2050fd072f580ece5392c5be09b343a47c57cc66dd")
        self.assertEqual(hashlib.sha256(reference).hexdigest(), "e36f56728f47667096501fd1d54c9802d225aee62ec6035a2d4be2a7ab858a5d")
        self.assertEqual(metadata["micro_factor"], 0.00002)
        self.assertEqual(self.result["target_filtered_glb"], reference)

    def test_q_r_o_p_f_pipeline_is_complete_and_bounded(self) -> None:
        report = self.result["report"]
        self.assertEqual(report["stage4q"]["sanitation"]["removed_face_count"], 1)
        tiny = report["stage4r"]
        self.assertEqual(tiny["removed_face_count"], 1)
        self.assertEqual(tiny["classification_counts"]["TARGET_QUANTIZED_DEGENERATE"], 1)
        self.assertEqual((tiny["boundary_loops_before"], tiny["boundary_loops_after"]), (1, 2))
        self.assertTrue(tiny["component_survival"])
        self.assertEqual(tiny["silhouette_iou"], {name: 1.0 for name in ("front", "rear", "left", "right", "three_quarter")})
        self.assertFalse(tiny["bounds_changed"])
        self.assertTrue(report["stage4f_accepted"])
        self.assertEqual((report["stage4o"]["final"]["positions"], report["stage4o"]["final"]["triangles"]), (34, 58))
        self.assertEqual(report["canonical_sha256"], "69deff902150a082981a624a391a3b25629f8e6628dcbe1f6c3e21df0cfcd814")
        self.assertEqual(len(parse_glb(self.result["canonical_glb"]).faces), 58)

    def test_target_representation_matches_the_actual_encoder(self) -> None:
        report = self.result["report"]["stage4r"]
        representation = report["target_representation"]
        self.assertEqual((representation["command"], representation["opcode"]), ("VTX_16", "0x23"))
        self.assertEqual(representation["fixed_fraction_bits"], 12)
        self.assertEqual(representation["model_coordinate_increment"], 1 / 4096)
        self.assertEqual(representation["normalized_tile_increment"], 1 / 1024)
        removed = report["removed_faces"][0]
        self.assertGreater(removed["source_cross_squared"], 0.0)
        self.assertLessEqual(removed["source_cross_length"], 1e-9)
        self.assertEqual(removed["target_cross_squared"], 0)
        self.assertEqual(removed["target_distinct_coordinate_count"], 1)

    def test_display_list_uses_unchanged_stage4f_and_stage4i_capacity(self) -> None:
        proof_manifest, _raw = load_manifest(ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json", ROOT)
        mesh = parse_glb(self.result["canonical_glb"])
        ir = _normalized_ir(proof_manifest, mesh, ROOT)
        display_list, plan = _encode_asset_primitives(_ir_primitives(ir))
        self.assertEqual((plan["triangle_count"], plan["vertex_count"], len(display_list)), (58, 174, 3956))
        self.assertLessEqual(len(display_list), 4096)
        self.assertEqual(hashlib.sha256(display_list).hexdigest(), "a5dc85ac62b050145945808a7011d09a452aea69b3cc91d65b1d0e95fc9cc571")

    def test_tiny_but_target_representable_face_survives(self) -> None:
        policy = copy.deepcopy(self.r_policy)
        policy["normalization"]["units_to_tiles"] = 1024.0
        probe = build_rounding_probe(0.75, units_to_tiles=1024.0)
        face = classify_target_faces(probe["positions"], probe["faces"], policy)["faces"][0]
        self.assertLess(face["source_cross_length"], 1e-9)
        self.assertEqual(face["target_cross_squared"], 1)
        self.assertEqual(face["classification"], "TARGET_REPRESENTABLE")
        with self.assertRaises(TinyFaceError) as raised:
            remove_target_null_faces(probe["positions"], probe["faces"], policy)
        self.assertEqual(raised.exception.code, "tinyface_no_target_null_blocker")

    def test_quantization_boundary_and_ties_to_even_are_exact(self) -> None:
        expected = ((0.4999, "TARGET_NULL_NONBLOCKING_PRESERVED"), (0.5, "TARGET_NULL_NONBLOCKING_PRESERVED"), (0.5001, "TARGET_REPRESENTABLE"))
        for numerator, classification in expected:
            probe = build_rounding_probe(numerator)
            face = classify_target_faces(probe["positions"], probe["faces"], self.r_policy)["faces"][0]
            self.assertEqual(face["classification"], classification)
        self.assertEqual(quantize_vtx16_coordinate(0.5 / 4096), 0)
        self.assertEqual(quantize_vtx16_coordinate(1.5 / 4096), 2)
        self.assertEqual(quantize_vtx16_coordinate(-0.5 / 4096), 0)
        self.assertEqual(quantize_vtx16_coordinate(-1.5 / 4096), -2)

    def test_exact_zero_remains_exclusively_stage4q_territory(self) -> None:
        positions = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        with self.assertRaises(TinyFaceError) as raised:
            remove_target_null_faces(positions, [(0, 1, 2), (0, 3, 1)], self.r_policy)
        self.assertEqual(raised.exception.code, "tinyface_exact_zero_requires_stage4q")
        mesh, report = sanitize_mesh(positions, [(0, 1, 2), (0, 3, 1)], remove_exact_zero_area_faces=True)
        self.assertEqual((report["removed_face_count"], len(mesh["faces"])), (1, 1))

    def test_policy_disabled_leaves_stage4o_rejection_unchanged(self) -> None:
        exact = _exact_stage4q_in_memory(SOURCE.read_bytes(), self.q_policy)["geometry"]
        with self.assertRaises(GeometryReductionError) as raised:
            canonical_geometry(exact["positions"], exact["faces"])
        self.assertEqual(raised.exception.code, "geometry_predecimation_degenerate")
        policy = copy.deepcopy(self.r_policy); policy["candidate_scope"] = "disabled"
        with self.assertRaises(TinyFaceError) as raised:
            remove_target_null_faces(exact["positions"], exact["faces"], policy)
        self.assertEqual(raised.exception.code, "invalid_tinyface_policy")

    def test_component_deletion_and_split_are_rejected(self) -> None:
        sole_positions = [
            (0.0, 0.0, 0.0), (1e-5, 0.0, 0.0), (0.0, 1e-5, 0.0),
            (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0),
        ]
        with self.assertRaises(TinyFaceError) as raised:
            remove_target_null_faces(sole_positions, [(0, 1, 2), (3, 4, 5)], self.r_policy)
        self.assertEqual(raised.exception.code, "target_null_removal_component_vanished")
        split_positions = [
            (0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (1e-5, 0.0, 0.0),
            (0.0, 1e-5, 0.0), (0.0, 1.0, 0.0),
        ]
        split_faces = [(0, 2, 1), (1, 2, 3), (4, 3, 2)]
        with self.assertRaises(TinyFaceError) as raised:
            remove_target_null_faces(split_positions, split_faces, self.r_policy)
        self.assertEqual(raised.exception.code, "target_null_removal_component_split")

    def test_source_order_translation_and_component_semantics_are_invariant(self) -> None:
        reversed_source, _reference, _metadata = build_stage4r_target_null(reverse_faces=True)
        exact = _exact_stage4q_in_memory(reversed_source, self.q_policy)["geometry"]
        filtered, report = remove_target_null_faces(exact["positions"], exact["faces"], self.r_policy)
        self.assertEqual(pack_geometry_glb(filtered), self.result["target_filtered_glb"])
        self.assertEqual(report["removed_faces"][0]["canonical_source_face_id"], self.result["report"]["stage4r"]["removed_faces"][0]["canonical_source_face_id"])
        canonical = _exact_stage4q_in_memory(SOURCE.read_bytes(), self.q_policy)["geometry"]
        delta = (100.0, -20.0, 7.0)
        translated = [tuple(point[axis] + delta[axis] for axis in range(3)) for point in canonical["positions"]]
        translated_output, translated_report = remove_target_null_faces(translated, canonical["faces"], self.r_policy)
        def semantic(mesh, offset):
            return sorted(
                tuple(sorted(
                    tuple(round(mesh["positions"][index][axis] - offset[axis], 5) for axis in range(3))
                    for index in face
                ))
                for face in mesh["faces"]
            )
        self.assertEqual(semantic(translated_output, delta), semantic(filtered, (0.0, 0.0, 0.0)))
        self.assertEqual(translated_report["classification_counts"], report["classification_counts"])

    def test_scale_and_placement_behavior_match_target_semantics(self) -> None:
        canonical = _exact_stage4q_in_memory(SOURCE.read_bytes(), self.q_policy)["geometry"]
        expected = {0.5: (1, 3), 1.0: (1, 3), 2.0: (0, 4)}
        for factor, counts in expected.items():
            scaled = [tuple(value * factor for value in point) for point in canonical["positions"]]
            classified = classify_target_faces(scaled, canonical["faces"], self.r_policy)
            self.assertEqual(
                (classified["classification_counts"]["TARGET_QUANTIZED_DEGENERATE"], classified["classification_counts"]["TARGET_NULL_NONBLOCKING_PRESERVED"]),
                counts,
            )
        placed = copy.deepcopy(self.r_policy)
        placed["placement"] = {"x": 17, "z": 12, "rotation": 90}
        classified = classify_target_faces(canonical["positions"], canonical["faces"], placed)
        self.assertEqual(classified["classification_counts"]["TARGET_QUANTIZED_DEGENERATE"], 1)

    def test_security_failures_are_stable(self) -> None:
        policy = copy.deepcopy(self.q_policy); policy["color0_policy"] = "reject"
        with self.assertRaises(TinyFaceGLBError) as raised:
            _exact_stage4q_in_memory(SOURCE.read_bytes(), policy)
        self.assertEqual(raised.exception.code, "tinyface_color0_policy_required")
        document, binary = _chunks(SOURCE.read_bytes(), {"max_source_bytes": 8*1024*1024, "max_buffer_bytes": 8*1024*1024})
        attributes = document["meshes"][0]["primitives"][0]["attributes"]
        attributes["NORMAL"] = attributes["COLOR_0"]
        unsupported = pack_glb(document, binary[:document["buffers"][0]["byteLength"]])
        with self.assertRaises(TinyFaceGLBError) as raised:
            _exact_stage4q_in_memory(unsupported, self.q_policy)
        self.assertEqual(raised.exception.code, "unsupported_tinyface_aux_attribute")
        overflow = copy.deepcopy(self.r_policy); overflow["normalization"]["units_to_tiles"] = 8.0
        exact = _exact_stage4q_in_memory(SOURCE.read_bytes(), self.q_policy)["geometry"]
        with self.assertRaises(TinyFaceError) as raised:
            classify_target_faces(exact["positions"], exact["faces"], overflow)
        self.assertEqual(raised.exception.code, "tinyface_target_quantization_overflow")
        with self.assertRaises(TinyFaceError) as raised:
            classify_target_faces([(math.nan, 0.0, 0.0)], [(0, 0, 0)], self.r_policy)
        self.assertEqual(raised.exception.code, "tinyface_nonfinite_position")

    def test_clean_outputs_cli_and_report_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            one = write_tinyface_outputs(MANIFEST, Path(first), ROOT)
            two = write_tinyface_outputs(MANIFEST, Path(second), ROOT)
            for name in ("target-null-sanitized.glb", "reduced-geometry.glb", "bootstrapped.glb", "tiny-face-report.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
            self.assertEqual(one["report_sha256"], two["report_sha256"])
        args = build_parser().parse_args(["asset", "tinyface-sanitize", str(MANIFEST), "--json"])
        self.assertEqual(args.asset_command, "tinyface-sanitize")

    def test_stage4h_read_only_face_is_target_null_and_candidate_is_ready(self) -> None:
        before = STAGE4H.read_bytes()
        projection = inspect_stage4h_tiny_face(before, (4.0, 6.0, 4.0))
        self.assertEqual(projection["raw_source_sha256"], "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60")
        self.assertTrue(projection["tinyface_policy_applicable"])
        self.assertTrue(projection["stage4o_structurally_applicable_after_hypothetical_removal"])
        face = projection["stage4o_blocking_target_null_faces"][0]
        self.assertAlmostEqual(face["source_cross_squared"], 2.6948343349697145e-19)
        self.assertEqual(face["target_quantized_positions"], [[-507, 3735, -1636]] * 3)
        self.assertEqual(face["edge_incident_face_counts"], [2, 2, 2])
        self.assertFalse(face["boundary_participation"])
        self.assertEqual((projection["hypothetical_removal"]["boundary_loops_before"], projection["hypothetical_removal"]["boundary_loops_after"]), (24, 25))
        self.assertEqual(projection["hypothetical_stage4o_topology"]["connected_components"], 2)
        self.assertTrue(projection["color0_discard_applicable"])
        self.assertFalse(projection["derived_candidate_created"])
        self.assertEqual(STAGE4H.read_bytes(), before)

    def test_stage4q_o_p_j_and_canonical_writer_regressions_are_exact(self) -> None:
        stage4q = run_topology_manifest(ROOT / "assets/manifests/stage4q_generated_topology.json", ROOT)
        self.assertEqual(stage4q["report"]["canonical_sha256"], "ef022994ecdd5574940284d992de237236b1ff32313695ae60e942baca77f0f7")
        stage4o = reduce_geometry_manifest(ROOT / "assets/manifests/stage4o_dense_geometry_shrine.json", ROOT)
        self.assertEqual(stage4o["report"]["canonical_sha256"], "7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957")
        stage4p = compile_asset(ROOT / "assets/manifests/stage4p_geometry_bootstrap_turret.json", ROOT)
        self.assertEqual(hashlib.sha256(stage4p["bootstrapped_glb"]).hexdigest(), "06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1")
        stage4j = compile_asset(ROOT / "assets/manifests/stage4j_dense_stone_shrine.json", ROOT)["report"]
        self.assertEqual((stage4j["display_list_bytes"], stage4j["hashes"]["display_list_sha256"]), (4024, "e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04"))
        expected = {
            "stage4k_flat_reference.glb": "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6",
            "stage4l_authored_normals_reference.glb": "b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9",
            "stage4m_authored_uv_reference.glb": "c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84",
            "stage4n_authored_material_reference.glb": "3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66",
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / "assets/source" / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
