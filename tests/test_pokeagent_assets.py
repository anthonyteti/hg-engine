from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.assets import (
    AssetError,
    compile_asset,
    compile_asset_outputs,
    compile_placements,
    load_catalog,
    parse_obj,
)
from tools.pokeagent.world import _build_bgs, build_event, build_matrix, build_per, load_fixture


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4b_test_shed.json"
SOURCE = ROOT / "assets/source/stage4b_test_shed.obj"
CATALOG = ROOT / "assets/catalog.json"


class TemporaryAsset:
    def __init__(self) -> None:
        self.context = tempfile.TemporaryDirectory()
        self.root = Path(self.context.name)
        (self.root / "assets/source").mkdir(parents=True)
        (self.root / "assets/manifests").mkdir(parents=True)
        self.source = self.root / "assets/source/test.obj"
        self.manifest_path = self.root / "assets/manifests/test.json"
        self.source.write_bytes(SOURCE.read_bytes())
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.manifest["id"] = "test_asset"
        self.manifest["source"] = "assets/source/test.obj"
        self.write_manifest()

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def close(self) -> None:
        self.context.cleanup()


class AssetCanonicalTests(unittest.TestCase):
    def test_project_authored_shed_compiles_to_exact_bounded_quad_subset(self) -> None:
        compiled = compile_asset(MANIFEST, ROOT)
        report = compiled["report"]
        self.assertEqual(report["source_counts"], {"vertices": 16, "uvs": 4, "normals": 6, "faces": 12})
        self.assertEqual(report["normalized_counts"], {"vertices": 16, "faces": 12, "quads": 12, "triangles": 0})
        self.assertEqual(report["dimensions_tiles"], [4.5, 3.0, 3.5])
        self.assertEqual(report["display_list_bytes"], 1068)
        self.assertEqual(report["display_list_capacity_bytes"], 2496)
        self.assertEqual(report["shape"], 1)
        self.assertEqual(report["material_name"], "road01_r")
        self.assertEqual(len(compiled["display_list"]), 12 + 88 * 12)

    def test_compile_outputs_are_reproducible_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = compile_asset_outputs(MANIFEST, Path(first), ROOT)
            b = compile_asset_outputs(MANIFEST, Path(second), ROOT)
            self.assertEqual(a["hashes"], b["hashes"])
            for name in ("normalized-mesh.json", "display-list.bin", "collision.json", "asset-report.json"):
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())

    def test_world_placement_is_symbolic_and_drives_collision(self) -> None:
        fixture = load_fixture(ROOT / "fixtures/stage4b_asset_world.json")
        compiled = compile_placements(ROOT / fixture["asset_catalog"], fixture["assets"], ROOT)
        self.assertEqual(fixture["slots"]["map_header"], 538)
        self.assertEqual(fixture["slots"]["map_member"], 633)
        self.assertEqual(compiled["report"]["placement_count"], 1)
        self.assertEqual(compiled["report"]["blocked_tile_count"], 12)
        self.assertIn((16, 16), compiled["blocked_tiles"])
        self.assertNotIn((16, 17), compiled["blocked_tiles"])

    def test_world_serializers_use_asset_collision_and_controlled_slots(self) -> None:
        fixture = load_fixture(ROOT / "fixtures/stage4b_asset_world.json")
        per = build_per(fixture)
        collision = lambda x, z: per[(z * 32 + x) * 2 + 1]
        self.assertEqual(len(per), 2048)
        self.assertEqual(collision(16, 16), 128)
        self.assertEqual(collision(16, 17), 0)
        self.assertEqual(collision(0, 16), 128)
        matrix = build_matrix(fixture)
        name_length = matrix[4]
        self.assertEqual(matrix[5:5 + name_length], b"stage4b-assets")
        self.assertEqual(int.from_bytes(matrix[5 + name_length:7 + name_length], "little"), 538)
        self.assertEqual(int.from_bytes(matrix[-2:], "little"), 633)
        self.assertEqual(build_event(fixture), bytes(16))

    def test_normal_overworld_member_keeps_per_at_fixed_offset_0x14(self) -> None:
        fixture = load_fixture(ROOT / "fixtures/stage4b_asset_world.json")
        template_bgs = b"\x34\x12\x58\x00" + bytes(0x58)
        self.assertEqual(_build_bgs(fixture, template_bgs), b"\x34\x12\x00\x00")

    def test_source_mutation_changes_geometry_not_identity_or_collision(self) -> None:
        temporary = TemporaryAsset()
        try:
            before = compile_asset(temporary.manifest_path, temporary.root)
            text = temporary.source.read_text(encoding="utf-8")
            temporary.source.write_text(text.replace(" 3.0 ", " 3.25 "), encoding="utf-8")
            after = compile_asset(temporary.manifest_path, temporary.root)
            self.assertEqual(before["manifest"]["id"], after["manifest"]["id"])
            self.assertNotEqual(before["report"]["source_sha256"], after["report"]["source_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["normalized_mesh_sha256"], after["report"]["hashes"]["normalized_mesh_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["display_list_sha256"], after["report"]["hashes"]["display_list_sha256"])
            self.assertEqual(before["report"]["hashes"]["collision_sha256"], after["report"]["hashes"]["collision_sha256"])
        finally:
            temporary.close()


class AssetFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.asset = TemporaryAsset()

    def tearDown(self) -> None:
        self.asset.close()

    def assert_compile_code(self, code: str) -> None:
        self.asset.write_manifest()
        with self.assertRaises(AssetError) as error:
            compile_asset(self.asset.manifest_path, self.asset.root)
        self.assertEqual(error.exception.code, code)

    def test_missing_source_and_unsupported_extension(self) -> None:
        self.asset.manifest["source"] = "assets/source/missing.obj"
        self.assert_compile_code("missing_source")
        self.asset.manifest["source"] = "assets/source/test.glb"
        (self.asset.root / self.asset.manifest["source"]).write_bytes(b"glTF")
        self.assert_compile_code("unsupported_source_format")

    def test_malformed_nonfinite_and_missing_uv_meshes(self) -> None:
        for source, code in (
            (b"not-an-obj\n", "unsupported_obj_statement"),
            (b"v nan 0 0\n", "nonfinite_coordinate"),
            (b"v 0 0 0\nvt 0 0\nvn 0 1 0\nusemtl shed_shell\nf 1//1 1//1 1//1 1//1\n", "missing_uv_or_normal"),
        ):
            with self.subTest(code=code):
                self.asset.source.write_bytes(source)
                self.assert_compile_code(code)

    def test_degenerate_face_and_unsupported_polygon(self) -> None:
        degenerate = (
            "v 0 0 0\nv 1 0 0\nv 1 0 0\nv 0 0 1\nv 0 1 0\n"
            "vt 0 0\nvt 0 1\nvt 1 1\nvt 1 0\nvn 0 1 0\nusemtl shed_shell\n"
            "f 1/1/1 2/2/1 3/3/1 4/4/1\n"
        )
        self.asset.source.write_text(degenerate, encoding="utf-8")
        self.assert_compile_code("degenerate_face")
        self.asset.source.write_text(degenerate.replace("f 1/1/1 2/2/1 3/3/1 4/4/1", "f 1/1/1 2/2/1 4/4/1"), encoding="utf-8")
        self.assert_compile_code("unsupported_polygon")

    def test_vertex_and_face_budgets(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        extra_vertices = "".join(f"v {index}.0 0.0 0.0\n" for index in range(49))
        self.asset.source.write_text(source + extra_vertices, encoding="utf-8")
        self.assert_compile_code("vertices_over_budget")
        faces = [line for line in source.splitlines() if line.startswith("f ")]
        self.asset.source.write_text(source + "\n".join(faces[:1] * 13) + "\n", encoding="utf-8")
        self.assert_compile_code("faces_over_budget")

    def test_invalid_scale_axis_and_material(self) -> None:
        self.asset.manifest["normalization"]["units_to_tiles"] = 0
        self.assert_compile_code("invalid_scale")
        self.asset.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.asset.manifest["id"] = "test_asset"; self.asset.manifest["source"] = "assets/source/test.obj"
        self.asset.manifest["coordinate_system"]["up_axis"] = "q"
        self.assert_compile_code("invalid_axis")
        self.asset.manifest["coordinate_system"]["up_axis"] = "+y"
        self.asset.manifest["material_policy"]["mappings"] = {"shed_shell": "random"}
        self.assert_compile_code("unsupported_material")

    def test_unsafe_path_traversal_is_rejected(self) -> None:
        self.asset.manifest["source"] = "../outside.obj"
        self.assert_compile_code("unsafe_path")

    def test_duplicate_catalog_asset_id(self) -> None:
        catalog = self.asset.root / "assets/catalog.json"
        entry = {"id": "test_asset", "manifest": "assets/manifests/test.json"}
        catalog.write_text(json.dumps({"schema_version": 1, "assets": [entry, entry]}), encoding="utf-8")
        with self.assertRaises(AssetError) as error:
            load_catalog(catalog, self.asset.root)
        self.assertEqual(error.exception.code, "duplicate_asset_id")

    def _catalog(self) -> Path:
        catalog = self.asset.root / "assets/catalog.json"
        catalog.write_text(json.dumps({
            "schema_version": 1,
            "assets": [{"id": "test_asset", "manifest": "assets/manifests/test.json"}],
        }), encoding="utf-8")
        return catalog

    def test_invalid_and_out_of_bounds_placements(self) -> None:
        catalog = self._catalog()
        invalid = [{"id": "placed", "asset": "test_asset", "x": 16, "z": 16, "rotation": 45}]
        with self.assertRaises(AssetError) as error:
            compile_placements(catalog, invalid, self.asset.root)
        self.assertEqual(error.exception.code, "invalid_rotation")
        self.asset.manifest["collision"]["rectangle"] = {
            "min_x": -2.25, "max_x": 2.25, "min_z": -1.75, "max_z": 1.75,
        }
        self.asset.write_manifest()
        outside = [{"id": "placed", "asset": "test_asset", "x": 3, "z": 3, "rotation": 0}]
        with self.assertRaises(AssetError) as error:
            compile_placements(catalog, outside, self.asset.root)
        self.assertEqual(error.exception.code, "collision_out_of_bounds")

    def test_placement_display_list_overflow(self) -> None:
        catalog = self._catalog()
        placements = [
            {"id": "placed_a", "asset": "test_asset", "x": 8, "z": 8, "rotation": 0},
            {"id": "placed_b", "asset": "test_asset", "x": 16, "z": 16, "rotation": 90},
            {"id": "placed_c", "asset": "test_asset", "x": 24, "z": 24, "rotation": 180},
        ]
        with self.assertRaises(AssetError) as error:
            compile_placements(catalog, placements, self.asset.root)
        self.assertEqual(error.exception.code, "display_list_overflow")

    def test_repeated_compilation_has_stable_ordering(self) -> None:
        first = compile_asset(self.asset.manifest_path, self.asset.root)
        second = compile_asset(self.asset.manifest_path, self.asset.root)
        self.assertEqual(first["ir"], second["ir"])
        self.assertEqual(first["display_list"], second["display_list"])
        self.assertEqual(first["report"], second["report"])


if __name__ == "__main__":
    unittest.main()
