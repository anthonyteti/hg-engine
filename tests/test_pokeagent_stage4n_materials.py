from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.assets import AssetError, compile_asset, compile_asset_outputs
from tools.pokeagent.cli import build_parser
from tools.pokeagent.generated_intake import inspect_generated_asset
from tools.pokeagent.glb import BIN_CHUNK, JSON_CHUNK, GLBError, pack_glb, parse_glb
from tools.pokeagent.glb_materials import MaterialSynthesisError, synthesize_named_material
from tools.pokeagent.glb_normals import generate_missing_normals
from tools.pokeagent.glb_preprocess import preprocess_static_glb
from tools.pokeagent.glb_uvs import generate_missing_uvs
from tools.pokeagent.stage4n_fixture import build_stage4n_fixtures
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/stage4n_missing_material_turret.glb"
REFERENCE = ROOT / "assets/source/stage4n_authored_material_reference.glb"
MANIFEST = ROOT / "assets/manifests/stage4n_missing_material_turret.json"
REFERENCE_MANIFEST = ROOT / "assets/manifests/stage4n_authored_material_reference.json"
FIXTURE = ROOT / "fixtures/stage4n_material_synthesis_world.json"
STAGE4H = ROOT / "assets/manifests/stage4h_generated_shrine_intake.json"


def _document_binary(data: bytes) -> tuple[dict[str, object], bytes]:
    length, kind = struct.unpack_from("<II", data, 12)
    if kind != JSON_CHUNK:
        raise AssertionError("JSON chunk missing")
    document = json.loads(data[20:20 + length])
    offset = 20 + length
    binary_length, binary_kind = struct.unpack_from("<II", data, offset)
    if binary_kind != BIN_CHUNK:
        raise AssertionError("BIN chunk missing")
    return document, data[offset + 8:offset + 8 + binary_length]


def _pack_mutation(data: bytes, mutate: object) -> bytes:
    document, binary = _document_binary(data)
    changed = copy.deepcopy(document)
    mutate(changed)
    return pack_glb(changed, binary)


def _reverse_triangle_order(data: bytes) -> bytes:
    document, binary = _document_binary(data)
    primitive = document["meshes"][0]["primitives"][0]
    accessor = document["accessors"][primitive["indices"]]
    view = document["bufferViews"][accessor["bufferView"]]
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor["count"]
    indices = list(binary[start:start + count])
    triangles = [indices[offset:offset + 3] for offset in range(0, count, 3)]
    changed = bytearray(binary)
    changed[start:start + count] = bytes(value for triangle in reversed(triangles) for value in triangle)
    return pack_glb(document, bytes(changed))


class Stage4NMaterialSynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated = synthesize_named_material(SOURCE.read_bytes(), "generated_surface")
        cls.compiled = compile_asset(MANIFEST, ROOT)
        cls.reference = compile_asset(REFERENCE_MANIFEST, ROOT)

    def test_tracked_fixtures_are_reproducible_and_hash_locked(self) -> None:
        source, reference = build_stage4n_fixtures()
        self.assertEqual(source, SOURCE.read_bytes())
        self.assertEqual(reference, REFERENCE.read_bytes())
        self.assertEqual(hashlib.sha256(source).hexdigest(), "4610685f64497a323ba6adfb059f7503a11bf6d740e272a7ed514d8cf22e2a75")
        self.assertEqual(hashlib.sha256(reference).hexdigest(), "3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66")

    def test_strict_stage4f_rejects_source_then_accepts_exact_reference(self) -> None:
        with self.assertRaises(GLBError) as raised:
            parse_glb(SOURCE.read_bytes())
        self.assertEqual(raised.exception.code, "unsupported_material")
        self.assertEqual(self.generated["canonical_glb"], REFERENCE.read_bytes())
        accepted = parse_glb(self.generated["canonical_glb"])
        self.assertEqual((len(accepted.faces), {face.material for face in accepted.faces}), (20, {"generated_surface"}))
        self.assertTrue(self.generated["report"]["stage4f_accepted"])

    def test_bin_accessors_geometry_display_and_collision_are_exactly_preserved(self) -> None:
        source_document, source_binary = _document_binary(SOURCE.read_bytes())
        canonical_document, canonical_binary = _document_binary(self.generated["canonical_glb"])
        source_semantic = copy.deepcopy(source_document)
        canonical_semantic = copy.deepcopy(canonical_document)
        canonical_semantic.pop("materials")
        canonical_semantic["meshes"][0]["primitives"][0].pop("material")
        self.assertEqual(source_semantic, canonical_semantic)
        self.assertEqual(source_binary, canonical_binary)
        expected_hashes = {
            "position": "a431532788ca1b0242d12803d7470de6f80f522a5de6f6ae680d65379c09bbc0",
            "normal": "613e27f7299ebc18fec093ae09f568d648af133e839ea20465207d7ae7ec1d2a",
            "texcoord_0": "2aa61931620b70e194f53c0f70db9be1478978ca3e3a6d86ed413cefa6b0b442",
            "indices": "f3446004937c36a1362a8af90e35b269b3896b7af5aa22dda2eb6b255f3a136f",
        }
        self.assertEqual(self.generated["report"]["accessor_payload_sha256"], expected_hashes)
        actual_ir, expected_ir = copy.deepcopy(self.compiled["ir"]), copy.deepcopy(self.reference["ir"])
        actual_ir.pop("asset_id"); expected_ir.pop("asset_id")
        self.assertEqual(actual_ir, expected_ir)
        self.assertEqual(self.compiled["display_list"], self.reference["display_list"])
        self.assertEqual(self.compiled["collision"], self.reference["collision"])

    def test_declared_policy_counts_mapping_and_budget_are_bounded(self) -> None:
        report = self.generated["report"]
        self.assertEqual(report["policy"], "assign_single_named_material")
        self.assertEqual((report["source_material_count"], report["source_material_index"]), (0, None))
        self.assertEqual((report["canonical_material_count"], report["canonical_material_index"]), (1, 0))
        self.assertEqual(report["material_name"], "generated_surface")
        self.assertTrue(report["geometry_attributes_preserved"])
        self.assertEqual(self.compiled["report"]["material_mappings"], {
            "generated_surface": {"alias": "prop", "texture": "stage4d_stone"},
        })
        self.assertEqual(self.compiled["report"]["display_list_bytes"], 1372)
        self.assertEqual(self.compiled["report"]["hashes"]["display_list_sha256"], "4b70a89f6ab34386fff4e0e55add0bfe0b875c846d42d96cfa16c740602c26dc")

    def test_material_name_and_geometry_mutations_are_orthogonal(self) -> None:
        alternate = synthesize_named_material(SOURCE.read_bytes(), "generated_surface_alt")
        self.assertNotEqual(alternate["canonical_glb"], self.generated["canonical_glb"])
        self.assertEqual(alternate["report"]["accessor_payload_sha256"], self.generated["report"]["accessor_payload_sha256"])
        self.assertEqual(parse_glb(alternate["canonical_glb"]).faces[0].material, "generated_surface_alt")
        mutated_source, _ = build_stage4n_fixtures(roof_height=4.2)
        geometry = synthesize_named_material(mutated_source, "generated_surface")
        self.assertNotEqual(geometry["canonical_glb"], self.generated["canonical_glb"])
        self.assertEqual(geometry["report"]["material_name"], "generated_surface")
        self.assertNotEqual(geometry["report"]["accessor_payload_sha256"]["position"], self.generated["report"]["accessor_payload_sha256"]["position"])
        self.assertEqual(self.compiled["collision"], self.reference["collision"])
        reordered = synthesize_named_material(_reverse_triangle_order(SOURCE.read_bytes()), "generated_surface")
        self.assertEqual(reordered["report"]["material_name"], self.generated["report"]["material_name"])
        self.assertEqual(reordered["report"]["policy"], self.generated["report"]["policy"])

    def test_hierarchy_is_byte_neutral_and_composes_with_stage4k(self) -> None:
        source, reference = build_stage4n_fixtures(hierarchical=True)
        generated = synthesize_named_material(source, "generated_surface")
        self.assertEqual(generated["canonical_glb"], reference)
        before_document, before_binary = _document_binary(source)
        after_document, after_binary = _document_binary(generated["canonical_glb"])
        self.assertEqual(before_document["nodes"], after_document["nodes"])
        self.assertEqual(before_document["scenes"], after_document["scenes"])
        self.assertEqual(before_binary, after_binary)
        self.assertFalse(generated["report"]["stage4f_accepted"])
        self.assertEqual(generated["report"]["stage4f_deferred_reason"], "unsupported_scene")
        flattened = preprocess_static_glb(generated["canonical_glb"])
        self.assertTrue(flattened["report"]["stage4f_accepted"])
        self.assertEqual(flattened["report"]["material"], "generated_surface")

    def test_material_identity_survives_normal_and_uv_preprocessors(self) -> None:
        document, binary = _document_binary(self.generated["canonical_glb"])
        no_normal = copy.deepcopy(document)
        no_normal["meshes"][0]["primitives"][0]["attributes"].pop("NORMAL")
        normal = generate_missing_normals(pack_glb(no_normal, binary))
        self.assertEqual({face.material for face in normal["canonical_mesh"].faces}, {"generated_surface"})
        no_uv = copy.deepcopy(document)
        no_uv["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0")
        uv = generate_missing_uvs(pack_glb(no_uv, binary))
        self.assertEqual({face.material for face in uv["canonical_mesh"].faces}, {"generated_surface"})

    def test_missing_only_name_attribute_resource_and_structure_failures_are_stable(self) -> None:
        source = SOURCE.read_bytes()
        cases = (
            (_pack_mutation(source, lambda d: d.update({"materials": [{"name": "authored"}]})), "material_already_present"),
            (_pack_mutation(source, lambda d: d.update({"materials": [{"name": "one"}, {"name": "two"}]})), "material_already_present"),
            (_pack_mutation(source, lambda d: d["meshes"][0]["primitives"][0].update({"material": 0})), "material_already_present"),
            (_pack_mutation(source, lambda d: d["meshes"][0]["primitives"][0].update({"material": 99})), "material_already_present"),
            (_pack_mutation(source, lambda d: d.update({"meshes": d["meshes"] * 2})), "unsupported_mesh_count"),
            (_pack_mutation(source, lambda d: d["meshes"][0].update({"primitives": d["meshes"][0]["primitives"] * 2})), "unsupported_primitive_count"),
            (_pack_mutation(source, lambda d: d.update({"nodes": [{"children": [1, 2]}, {"mesh": 0}, {"mesh": 0}]})), "branching_node_hierarchy"),
            (_pack_mutation(source, lambda d: d["meshes"][0]["primitives"][0].update({"mode": 5})), "unsupported_primitive_mode"),
            (_pack_mutation(source, lambda d: d["meshes"][0]["primitives"][0]["attributes"].update({"COLOR_0": 0})), "unexpected_attribute"),
            (_pack_mutation(source, lambda d: d["meshes"][0]["primitives"][0]["attributes"].pop("NORMAL")), "missing_attribute"),
            (_pack_mutation(source, lambda d: d["buffers"][0].update({"uri": "file:///tmp/no"})), "external_uri"),
            (_pack_mutation(source, lambda d: d.update({"extensionsUsed": ["KHR_unknown"]})), "unsupported_gltf_extension"),
        )
        for changed, code in cases:
            with self.subTest(code=code), self.assertRaises(MaterialSynthesisError) as raised:
                synthesize_named_material(changed, "generated_surface")
            self.assertEqual(raised.exception.code, code)
        for name in ("", "A", "bad-name", "a" * 65, "bad\nname", "café"):
            with self.subTest(name=name), self.assertRaises(MaterialSynthesisError) as raised:
                synthesize_named_material(source, name)
            self.assertEqual(raised.exception.code, "invalid_material_name")
        with self.assertRaises(MaterialSynthesisError) as raised:
            synthesize_named_material(b"bad", "generated_surface")
        self.assertEqual(raised.exception.code, "malformed_glb_length")

    def test_outputs_cli_world_manifest_and_two_roots_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as first, tempfile.TemporaryDirectory(dir=ROOT / "build") as second:
            compile_asset_outputs(MANIFEST, Path(first), ROOT)
            compile_asset_outputs(MANIFEST, Path(second), ROOT)
            for name in ("material-generated.glb", "material-synthesis-report.json", "display-list.bin", "collision.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())
        parsed = build_parser().parse_args(["asset", "materials", str(MANIFEST), "--json"])
        self.assertEqual((parsed.command, parsed.asset_command), ("asset", "materials"))
        fixture = load_fixture(FIXTURE)
        self.assertEqual((fixture["schema_version"], fixture["artifact_namespace"]), (19, "stage4n"))
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as directory:
            manifest = json.loads(MANIFEST.read_text())
            manifest["preprocessing"]["material"]["name"] = "generated_surface_alt"
            manifest["material_policy"]["mappings"] = {
                "generated_surface_alt": {"alias": "prop", "texture": "stage4d_stone"},
            }
            path = Path(directory) / "alternate.json"
            path.write_text(json.dumps(manifest))
            alternate = compile_asset(path, ROOT)
            self.assertEqual(alternate["report"]["material_synthesis"]["material_name"], "generated_surface_alt")
            self.assertEqual(alternate["display_list"], self.compiled["display_list"])

    def test_stage4h_projection_and_prior_canonical_hashes_remain_invariant(self) -> None:
        raw = ROOT / "assets/source/generated/stage4h_generated_shrine_raw.glb"
        before = raw.read_bytes()
        report = inspect_generated_asset(STAGE4H, ROOT)
        projection = report["stage4n"]["material_synthesis"]
        self.assertFalse(projection["applicable"])
        self.assertTrue(projection["structure_applicable"])
        self.assertIn(projection["error"]["code"], {"missing_attribute", "unexpected_attribute", "accessor_over_budget"})
        self.assertFalse(report["stage4n"]["retroactive_approval"])
        self.assertFalse(report["accepted"])
        self.assertEqual(report["quality_classification"], "REJECTED_UNSUPPORTED_STRUCTURE")
        self.assertEqual(raw.read_bytes(), before)
        stage4k = preprocess_static_glb((ROOT / "assets/source/stage4k_hierarchical_tower.glb").read_bytes())
        stage4l = generate_missing_normals((ROOT / "assets/source/stage4l_missing_normals_turret.glb").read_bytes())
        stage4m = generate_missing_uvs((ROOT / "assets/source/stage4m_missing_uv_turret.glb").read_bytes())
        self.assertEqual(hashlib.sha256(stage4k["canonical_glb"]).hexdigest(), "d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6")
        self.assertEqual(hashlib.sha256(stage4l["canonical_glb"]).hexdigest(), "b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9")
        self.assertEqual(hashlib.sha256(stage4m["canonical_glb"]).hexdigest(), "c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84")


if __name__ == "__main__":
    unittest.main()
