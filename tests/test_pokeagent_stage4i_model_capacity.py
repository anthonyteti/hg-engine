from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom

from tools.pokeagent.assets import AssetError, compile_asset
from tools.pokeagent.geometry import GeometryError, Triangle, encode_mesh_primitives
from tools.pokeagent.glb import BIN_CHUNK, JSON_CHUNK, pack_glb
from tools.pokeagent.nsbmd_model import (
    PROJECT_DISPLAY_LIST_TESTED_MAX,
    ModelLayoutError,
    inspect_nsbmd_model,
    relocate_display_lists,
)
from tools.pokeagent.world import (
    build_degenerate_display_list,
    build_map_member,
    load_fixture,
    split_hgss_map_member,
    transform_template_nsbmd_multi,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4i_expanded_gatehouse.json"
SOURCE = ROOT / "assets/source/stage4i_expanded_gatehouse.glb"
FIXTURE = ROOT / "fixtures/stage4i_expanded_geometry_world.json"


def _template_model() -> bytes:
    rom = NintendoDSRom.fromFile(str(ROOT / "rom.nds"))
    member = NARC(rom.getFileByName("a/0/6/5")).files[0]
    return split_hgss_map_member(member)["nsbmd"]


def _triangle_list(count: int) -> bytes:
    triangle = Triangle(
        id="stress",
        material="prop_secondary",
        vertices=((0.0, 0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 1.0, 0.0), (0.0, 1.0, 0.0, 0.0, 1.0)),
        normal=(0.0, 0.0, 1.0),
    )
    return encode_mesh_primitives([triangle] * count)


def _mutate_buttress_height(data: bytes) -> bytes:
    json_length, json_kind = struct.unpack_from("<II", data, 12)
    assert json_kind == JSON_CHUNK
    document = json.loads(data[20:20 + json_length].decode("utf-8"))
    binary_header = 20 + json_length
    binary_length, binary_kind = struct.unpack_from("<II", data, binary_header)
    assert binary_kind == BIN_CHUNK
    binary = bytearray(data[binary_header + 8:binary_header + 8 + binary_length])
    accessor = document["accessors"][0]
    view = document["bufferViews"][accessor["bufferView"]]
    base = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    changed = 0
    for index in range(accessor["count"]):
        offset = base + index * 12
        x, y, z = struct.unpack_from("<3f", binary, offset)
        if abs(y - 3.3) < 1e-5:
            struct.pack_into("<3f", binary, offset, x, 3.5, z)
            changed += 1
    assert changed
    return pack_glb(document, bytes(binary))


class Stage4IModelCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiled = compile_asset(MANIFEST, ROOT)
        cls.fixture = load_fixture(FIXTURE)

    def test_canonical_asset_is_valid_meaningful_overflow_geometry(self) -> None:
        report = self.compiled["report"]
        self.assertEqual(report["source_format"], "glb")
        self.assertEqual(report["normalized_counts"]["triangles"], 56)
        self.assertEqual(report["normalized_counts"]["quads"], 0)
        self.assertEqual(report["emitted_vertex_count"], 168)
        self.assertEqual(report["display_list_bytes"], 3820)
        self.assertEqual(report["geometry_storage"]["inherited_capacity_bytes"], 1068)
        self.assertEqual(report["geometry_storage"]["max_bytes"], 4096)
        self.assertTrue(report["geometry_storage"]["requires_relocation"])
        self.assertEqual(PROJECT_DISPLAY_LIST_TESTED_MAX, 4096)

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "requires ignored supported local ROM")
    def test_old_path_fails_and_relocated_model_passes(self) -> None:
        template = _template_model()
        with self.assertRaises(GeometryError) as raised:
            transform_template_nsbmd_multi(
                template, {6: self.compiled["display_list"]}, {6: 0}, {6: 56},
            )
        self.assertEqual(raised.exception.code, "display_list_overflow")
        self.assertEqual(raised.exception.details, {"shape": 6, "required_bytes": 3820, "capacity_bytes": 1068})

        member, report = build_map_member(self.fixture, NARC(NintendoDSRom.fromFile(str(ROOT / "rom.nds")).getFileByName("a/0/6/5")).files[0])
        model = split_hgss_map_member(member)["nsbmd"]
        inspected = inspect_nsbmd_model(model)
        relocation = report["relocation"]
        self.assertEqual((relocation["old_file_size"], relocation["new_file_size"]), (16604, 20424))
        self.assertEqual(relocation["file_size_delta"], 3820)
        self.assertEqual(len(relocation["unaffected_shapes"]), 17)
        self.assertTrue(relocation["unaffected_payloads_preserved"])
        self.assertEqual(inspected["shapes"][6]["display_offset"], 16604)
        self.assertEqual(inspected["shapes"][6]["display_length"], 3820)
        self.assertEqual(inspected["counts"], {
            "nodes": 1, "materials": 23, "shapes": 18,
            "vertices": 236, "polygons": 73, "triangles": 56, "quads": 17,
        })

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "requires ignored supported local ROM")
    def test_independent_parser_rejects_corrupt_layouts(self) -> None:
        member, _report = build_map_member(
            self.fixture, NARC(NintendoDSRom.fromFile(str(ROOT / "rom.nds")).getFileByName("a/0/6/5")).files[0],
        )
        valid = split_hgss_map_member(member)["nsbmd"]
        inspected = inspect_nsbmd_model(valid)
        record6 = inspected["shapes"][6]["record_offset"]
        record7 = inspected["shapes"][7]["record_offset"]
        target = inspected["shapes"][6]["display_offset"]

        corruptions: list[tuple[str, bytearray]] = []
        bad = bytearray(valid); bad[:4] = b"BAD0"
        corruptions.append(("unsupported_model_revision", bad))
        bad = bytearray(valid); struct.pack_into("<I", bad, 8, len(bad) - 4)
        corruptions.append(("container_size_mismatch", bad))
        bad = bytearray(valid); bad[inspected["model_base"] + inspected["model_offsets"]["shapes"] + 1] = 0
        corruptions.append(("malformed_shape_dictionary", bad))
        bad = bytearray(valid); struct.pack_into("<I", bad, record6 + 8, 0xFFFFFFF0)
        corruptions.append(("display_list_range_outside_section", bad))
        bad = bytearray(valid); struct.pack_into("<I", bad, record6 + 8, target + 2 - record6)
        corruptions.append(("misaligned_display_list", bad))
        bad = bytearray(valid); struct.pack_into("<I", bad, record7 + 8, target - record7)
        corruptions.append(("overlapping_display_list_ranges", bad))
        bad = bytearray(valid); struct.pack_into("<H", bad, inspected["model_base"] + 36, 1)
        corruptions.append(("invalid_model_counters", bad))
        for code, candidate in corruptions:
            with self.subTest(code=code), self.assertRaises(ModelLayoutError) as raised:
                inspect_nsbmd_model(bytes(candidate))
            self.assertEqual(raised.exception.code, code)

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "requires ignored supported local ROM")
    def test_capacity_stress_layouts_are_exact_and_deterministic(self) -> None:
        template = _template_model()
        for triangles, expected_bytes in ((15, 1032), (30, 2052), (45, 3072), (56, 3820)):
            with self.subTest(triangles=triangles):
                payload = _triangle_list(triangles)
                self.assertEqual(len(payload), expected_bytes)
                placeholder, _ = transform_template_nsbmd_multi(
                    template, {6: build_degenerate_display_list()}, {6: 0}, {6: triangles},
                )
                first, report = relocate_display_lists(placeholder, {6: payload}, configured_capacity=4096)
                second, _ = relocate_display_lists(placeholder, {6: payload}, configured_capacity=4096)
                self.assertEqual(first, second)
                self.assertEqual(report["validation"]["shapes"][6]["commands"]["triangle_count"], triangles)
                self.assertEqual(report["new_file_size"], 16604 + expected_bytes)

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "requires ignored supported local ROM")
    def test_capacity_mutation_fails_without_truncation(self) -> None:
        template = _template_model()
        placeholder, _ = transform_template_nsbmd_multi(
            template, {6: build_degenerate_display_list()}, {6: 0}, {6: 56},
        )
        with self.assertRaises(ModelLayoutError) as raised:
            relocate_display_lists(placeholder, {6: self.compiled["display_list"]}, configured_capacity=3816)
        self.assertEqual(raised.exception.code, "project_geometry_capacity_exceeded")
        self.assertEqual(raised.exception.details, {"shape": 6, "required_bytes": 3820, "configured_capacity": 3816})

        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as manifest_dir:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            manifest["geometry_storage"]["max_bytes"] = 3816
            path = Path(manifest_dir) / "bounded.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(AssetError) as asset_raised:
                compile_asset(path, ROOT)
        self.assertEqual(asset_raised.exception.code, "project_geometry_capacity_exceeded")
        self.assertEqual(asset_raised.exception.details["asset_id"], "stage4i_expanded_gatehouse")
        self.assertEqual(asset_raised.exception.details["required_bytes"], 3820)
        self.assertEqual(asset_raised.exception.details["target_bytes"], 3816)
        self.assertEqual(asset_raised.exception.details["shape"], 6)
        self.assertEqual(asset_raised.exception.details["tested_project_capacity_bytes"], 4096)
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as manifest_dir:
            manifest["geometry_storage"]["max_bytes"] = 4097
            path = Path(manifest_dir) / "too-large.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(AssetError) as maximum_raised:
                compile_asset(path, ROOT)
        self.assertEqual(maximum_raised.exception.code, "invalid_project_geometry_capacity")

    def test_source_mutation_propagates_but_identity_texture_and_collision_do_not(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/source") as source_dir, tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as manifest_dir:
            source = Path(source_dir) / "mutated.glb"
            source.write_bytes(_mutate_buttress_height(SOURCE.read_bytes()))
            manifest = copy.deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
            manifest["source"] = source.relative_to(ROOT).as_posix()
            manifest_path = Path(manifest_dir) / "mutated.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            mutated = compile_asset(manifest_path, ROOT)
        self.assertEqual(self.compiled["manifest"]["id"], mutated["manifest"]["id"])
        self.assertNotEqual(self.compiled["report"]["source_sha256"], mutated["report"]["source_sha256"])
        self.assertNotEqual(self.compiled["report"]["hashes"]["normalized_mesh_sha256"], mutated["report"]["hashes"]["normalized_mesh_sha256"])
        self.assertNotEqual(self.compiled["display_list"], mutated["display_list"])
        self.assertEqual(self.compiled["collision"], mutated["collision"])
        self.assertEqual(self.compiled["textures"]["stage4d_stone"], mutated["textures"]["stage4d_stone"])

    def test_fixture_is_symbolic_and_stage4h_rejection_remains_separate(self) -> None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(source["schema_version"], 14)
        self.assertEqual(source["assets"][0]["asset"], "stage4i_expanded_gatehouse")
        self.assertIsInstance(source["map"]["map_header"], str)
        self.assertEqual(self.fixture["artifact_namespace"], "stage4i")
        catalog = json.loads((ROOT / "assets/catalog.json").read_text(encoding="utf-8"))
        self.assertNotIn("stage4h_generated_shrine", catalog["assets"])


if __name__ == "__main__":
    unittest.main()
