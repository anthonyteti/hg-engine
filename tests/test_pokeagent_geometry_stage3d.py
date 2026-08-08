from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import unittest

from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom

from tools.pokeagent.geometry import GeometryError, MATERIAL_BINDINGS, compile_geometry
from tools.pokeagent.registry import RegistryError, resolve_stage3d_source
from tools.pokeagent.world import (
    build_bdhc,
    build_event,
    build_map_member,
    build_matrix,
    build_per,
    load_fixture,
    sha256_bytes,
    split_hgss_map_member,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "stage3d_static_geometry_world.json"
REGISTRY = ROOT / "world" / "registry.json"


class Stage3DGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.fixture = load_fixture(FIXTURE)
        cls.compiled = compile_geometry(cls.fixture["geometry"])

    def test_symbolic_source_resolves_without_owning_numeric_ids(self):
        self.assertEqual(self.source["schema_version"], 5)
        self.assertIsInstance(self.source["map"]["map_header"], str)
        self.assertIsInstance(self.source["map"]["map_member"], str)
        self.assertIsInstance(self.source["world"]["matrix"]["id"], str)
        self.assertEqual(self.fixture["slots"]["map_header"], 538)
        self.assertEqual(self.fixture["slots"]["map_member"], 633)
        self.assertEqual(self.fixture["slots"]["matrix"], 1)

    def test_generic_ir_compiles_three_material_partitions(self):
        report = self.compiled["report"]
        self.assertEqual(report["feature_count"], 14)
        self.assertEqual(report["surface_count"], 12)
        self.assertEqual(report["transition_count"], 2)
        self.assertEqual(report["derived_wall_count"], 8)
        self.assertEqual(report["quad_count"], 22)
        self.assertEqual(report["vertex_count"], 88)
        self.assertEqual(set(self.compiled["display_lists"]), {1, 5, 6})
        for material, binding in MATERIAL_BINDINGS.items():
            detail = report["materials"][material]
            self.assertEqual(detail["shape"], binding["shape"])
            self.assertLessEqual(detail["display_list_bytes"], binding["capacity_bytes"])

    def test_display_lists_are_golden_bounded_quad_streams(self):
        expected = {
            1: (716, "3787fe59399f5efc9aaf86886cd0a70770030411222a0b1230d4ef2562e727d6"),
            5: (1068, "6dbb5a8f0ee108f4cb17b39dcd68b4c86faedf830cf096c64f6e22f3ac7e83ab"),
            6: (188, "676719a075b91fcd5582e4b6f54a611030d4b452c2d2372f382cc9bd6a71dab1"),
        }
        for shape, data in self.compiled["display_lists"].items():
            self.assertEqual(data[:8], struct.pack("<II", 0x40, 1))
            self.assertEqual(data[-4:], struct.pack("<I", 0x41))
            self.assertEqual((len(data), self.compiled["report"]["hashes"]["display_lists"][str(shape)]), expected[shape])

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "requires ignored supported local ROM")
    def test_hash_locked_template_accepts_all_three_shapes_without_relocation(self):
        rom = NintendoDSRom.fromFile(str(ROOT / "rom.nds"))
        template = NARC(rom.getFileByName("a/0/6/5")).files[0]
        self.assertEqual(sha256_bytes(template), self.fixture["model"]["template_member_sha256"])
        member, report = build_map_member(self.fixture, template)
        parts = split_hgss_map_member(member)
        self.assertEqual(sha256_bytes(parts["nsbmd"]), "92b19251e9a918da5bf889194a7007668fadf2785b30fd4a34068ea8bd84dfda")
        self.assertEqual(sha256_bytes(member), "fd1c47b0b8e931a214247e5301b5aadb1f069360d4d97ba0197104562b408f86")
        self.assertEqual(set(report["assignments"]), {"1", "5", "6"})
        self.assertEqual(member[0x14:0x14 + len(parts["per"])], parts["per"])

    def test_per_is_derived_from_shared_terrain_and_keeps_both_ramps_open(self):
        per = build_per(self.fixture)
        self.assertEqual(per, self.compiled["per"])

        def collision(x: int, z: int) -> int:
            return per[(z * 32 + x) * 2 + 1]

        self.assertEqual(collision(8, 12), 0)
        self.assertEqual([collision(x, 12) for x in (13, 14, 15, 16, 17)], [0, 0, 0, 0, 0])
        self.assertEqual([collision(26, z) for z in (23, 24, 25, 26)], [0, 0, 0, 0])
        self.assertEqual(collision(20, 15), 0)
        self.assertEqual(collision(20, 16), 0)
        self.assertEqual(collision(0, 12), 128)
        self.assertEqual(collision(31, 12), 128)

    def test_visual_and_bdhc_ir_are_derived_from_the_same_features(self):
        visual = self.compiled["ir"]["visual_features"]
        bdhc = self.compiled["ir"]["bdhc_plates"]
        self.assertEqual([entry["id"] for entry in visual], [entry["id"] for entry in bdhc])
        self.assertEqual(
            [(entry["rectangle"], entry["start_height"], entry["end_height"], entry["axis"]) for entry in visual],
            [(entry["rectangle"], entry["start_height"], entry["end_height"], entry["axis"]) for entry in bdhc],
        )

    def test_bdhc_contains_one_plate_per_declared_top_feature(self):
        bdhc = build_bdhc(self.fixture)
        self.assertEqual(bdhc, self.compiled["bdhc"])
        self.assertEqual(struct.unpack_from("<6H", bdhc, 4), (28, 3, 4, 14, 6, 26))
        normal_offset = 16 + 28 * 8
        normals = [struct.unpack_from("<3i", bdhc, normal_offset + index * 12) for index in range(3)]
        self.assertEqual(normals, [(0, 4096, 0), (-2896, 2896, 0), (0, 2896, 2896)])
        self.assertEqual(
            self.compiled["report"]["hashes"]["bdhc_sha256"],
            "67feb2e03d0f3a47869ca8073dc9599148143a3fe2d5ed9d2ec6242bab174653",
        )

    def test_bdhc_access_lists_union_lookahead_and_sort_the_complete_band_by_x(self):
        bdhc = self.compiled["bdhc"]
        point_count, normal_count, constant_count, plate_count, stripe_count, access_count = struct.unpack_from("<6H", bdhc, 4)
        stripe_offset = 16 + point_count * 8 + normal_count * 12 + constant_count * 4 + plate_count * 8
        stripes = [struct.unpack_from("<4H", bdhc, stripe_offset + index * 8) for index in range(stripe_count)]
        access_offset = stripe_offset + stripe_count * 8
        access = struct.unpack_from(f"<{access_count}H", bdhc, access_offset)
        slices = [access[offset:offset + count] for _zero, _end, count, offset in stripes]
        self.assertEqual(slices[1], (2, 4, 12, 3, 5))

    def test_single_map_world_components_remain_bounded(self):
        matrix = build_matrix(self.fixture)
        self.assertEqual(matrix[:5], bytes((1, 1, 1, 1, len("stage3d-terrain"))))
        self.assertEqual(build_event(self.fixture), bytes(16))

    def test_duplicate_geometry_id_is_rejected(self):
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["transitions"][0]["id"] = geometry["surfaces"][0]["id"]
        with self.assertRaisesRegex(GeometryError, "duplicate geometry ID") as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "duplicate_geometry_id")

    def test_gap_and_overlap_are_rejected(self):
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["surfaces"][0]["rectangle"]["max_x"] = 15
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "geometry_gap")
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["surfaces"][0]["rectangle"]["max_x"] = 17
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "overlapping_geometry")

    def test_invalid_material_axis_and_coordinate_are_rejected(self):
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["surfaces"][0]["material"] = "new_texture"
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "invalid_material")
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["transitions"][0]["axis"] = "y"
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "unsupported_transition")
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["surfaces"][0]["rectangle"]["min_x"] = -1
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "out_of_range")

    def test_unbounded_authored_primitive_is_rejected(self):
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["surfaces"][0]["primitive"] = "triangle"
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "invalid_feature")

    def test_known_shape_capacity_overflow_fails_before_nsbmd_encoding(self):
        geometry = copy.deepcopy(self.fixture["geometry"])
        geometry["surfaces"] = [
            {"id": f"strip_{x:02d}", "material": "ground", "height": (x % 2) * 2,
             "rectangle": {"min_x": x, "max_x": x + 1, "min_z": 0, "max_z": 32}}
            for x in range(30)
        ]
        geometry["transitions"] = [
            {"id": "overflow_ramp_a", "material": "transition", "axis": "x", "start_height": 0, "end_height": 2,
             "rectangle": {"min_x": 30, "max_x": 31, "min_z": 0, "max_z": 32}},
            {"id": "overflow_ramp_b", "material": "transition", "axis": "x", "start_height": 2, "end_height": 0,
             "rectangle": {"min_x": 31, "max_x": 32, "min_z": 0, "max_z": 32}},
        ]
        with self.assertRaises(GeometryError) as context:
            compile_geometry(geometry)
        self.assertEqual(context.exception.code, "display_list_overflow")
        self.assertEqual(context.exception.details["shape"], 5)

    def test_numeric_registry_reference_is_rejected(self):
        source = copy.deepcopy(self.source)
        source["map"]["map_header"] = 538
        with self.assertRaises(RegistryError) as context:
            resolve_stage3d_source(source, REGISTRY)
        self.assertEqual(context.exception.code, "numeric_reference")


if __name__ == "__main__":
    unittest.main()
