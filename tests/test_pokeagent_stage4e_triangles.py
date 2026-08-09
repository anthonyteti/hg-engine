from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.pokeagent.assets import (
    AssetError,
    _encode_asset_primitives,
    _ir_primitives,
    compile_asset,
    compile_placements,
    parse_obj,
)
from tools.pokeagent.geometry import GeometryError, Triangle, inspect_mesh_display_list
from tools.pokeagent.world import load_fixture


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4e_faceted_tower.json"
SOURCE = ROOT / "assets/source/stage4e_faceted_tower.obj"
CATALOG = ROOT / "assets/catalog.json"
FIXTURE = ROOT / "fixtures/stage4e_triangle_world.json"


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _subtract(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, float, float]:
    return tuple(a[index] - b[index] for index in range(3))


class TemporaryTriangleAsset:
    def __init__(self) -> None:
        self.source_context = tempfile.TemporaryDirectory(dir=ROOT / "assets/source")
        self.manifest_context = tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests")
        self.source = Path(self.source_context.name) / "probe.obj"
        self.manifest_path = Path(self.manifest_context.name) / "probe.json"
        self.source.write_bytes(SOURCE.read_bytes())
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.manifest["source"] = self.source.relative_to(ROOT).as_posix()
        self.write_manifest()

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def close(self) -> None:
        self.manifest_context.cleanup()
        self.source_context.cleanup()


class Stage4ETriangleTests(unittest.TestCase):
    def test_canonical_mixed_asset_has_exact_primitive_plan(self) -> None:
        compiled = compile_asset(MANIFEST, ROOT)
        report = compiled["report"]
        self.assertEqual(report["normalized_counts"], {
            "vertices": 9, "faces": 8, "quads": 4, "triangles": 4,
        })
        self.assertEqual(report["emitted_vertex_count"], 28)
        self.assertEqual(report["primitive_bytes"], {"quad": 364, "triangle": 284})
        self.assertEqual(report["display_list_bytes"], 648)
        self.assertEqual(report["display_list_capacity_bytes"], 1068)
        self.assertEqual([block["primitive"] for block in report["primitive_blocks"]], ["quad", "triangle"])
        self.assertEqual(compiled["ir"]["schema_version"], 2)
        self.assertEqual([face["primitive"] for face in compiled["ir"]["faces"]], ["quad"] * 4 + ["triangle"] * 4)
        self.assertEqual(inspect_mesh_display_list(compiled["display_list"])["triangle_count"], 4)

    def test_all_cardinal_rotations_preserve_winding_and_normals(self) -> None:
        ir = compile_asset(MANIFEST, ROOT)["ir"]
        hashes = set()
        for rotation in (0, 90, 180, 270):
            primitives = _ir_primitives(ir, {
                "id": f"rotation_{rotation}", "asset": "stage4e_faceted_tower",
                "x": 16, "z": 16, "rotation": rotation,
            })
            for primitive in primitives:
                cross = _cross(
                    _subtract(primitive.vertices[1], primitive.vertices[0]),
                    _subtract(primitive.vertices[2], primitive.vertices[0]),
                )
                self.assertGreater(sum(a * b for a, b in zip(cross, primitive.normal, strict=True)), 0)
            display_list, report = _encode_asset_primitives(primitives)
            self.assertEqual((report["triangle_count"], report["quad_count"]), (4, 4))
            hashes.add(display_list)
        self.assertEqual(len(hashes), 4)

    def test_binary_inspector_rejects_corrupt_begin_and_end(self) -> None:
        display_list = compile_asset(MANIFEST, ROOT)["display_list"]
        bad_begin = bytearray(display_list)
        bad_begin[4:8] = (2).to_bytes(4, "little")
        with self.assertRaises(GeometryError) as raised:
            inspect_mesh_display_list(bytes(bad_begin))
        self.assertEqual(raised.exception.code, "unsupported_primitive")
        bad_end = bytearray(display_list)
        bad_end[-4:] = b"\0\0\0\0"
        with self.assertRaises(GeometryError) as raised:
            inspect_mesh_display_list(bytes(bad_end))
        self.assertEqual(raised.exception.code, "corrupt_display_list")

    def test_triangle_validation_failures_are_stable(self) -> None:
        temporary = TemporaryTriangleAsset()
        canonical = temporary.source.read_text(encoding="utf-8")
        variants = (
            (canonical.replace("f 6/4/5 5/1/5 9/5/5", "f 6/4/5 6/1/5 9/5/5"), "degenerate_face"),
            (canonical.replace("f 6/4/5 5/1/5 9/5/5", "f 5/1/5 6/4/5 9/5/5"), "normal_winding_mismatch"),
            (canonical.replace("vt 0.5 1.0", "vt 0.5 1.2"), "invalid_uv"),
            (canonical.replace("vn 0.0 0.6 -0.8", "vn 0.0 0.0 0.0"), "invalid_normal"),
            (canonical.replace("f 6/4/5 5/1/5 9/5/5", "f 6/4/5 5/1/5 9//5"), "missing_uv_or_normal"),
            (canonical.replace("f 6/4/5 5/1/5 9/5/5", "f 6/4/5 5/1/5 9/5/5 7/3/5 8/2/5"), "unsupported_polygon"),
        )
        try:
            for source, code in variants:
                with self.subTest(code=code):
                    temporary.source.write_text(source, encoding="utf-8")
                    with self.assertRaises(AssetError) as raised:
                        compile_asset(temporary.manifest_path, ROOT)
                    self.assertEqual(raised.exception.code, code)
            temporary.source.write_text(canonical, encoding="utf-8")
            temporary.manifest["material_policy"]["mappings"] = {
                "wrong_shell": {"alias": "prop_secondary", "texture": "stage4d_stone"},
            }
            temporary.write_manifest()
            with self.assertRaises(AssetError) as raised:
                compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(raised.exception.code, "unsupported_material")
        finally:
            temporary.close()

    def test_fixed_point_overflow_and_mixed_shape_capacity_fail_early(self) -> None:
        oversized = Triangle(
            "oversized", "prop_secondary",
            ((9.0, 0.0, 0.0, 0.0, 0.0), (9.5, 0.0, 0.0, 1.0, 0.0), (9.0, 1.0, 0.0, 0.0, 1.0)),
            (0.0, 0.0, 1.0),
        )
        with self.assertRaises(AssetError) as raised:
            _encode_asset_primitives([oversized])
        self.assertEqual(raised.exception.code, "vertex_overflow")

        placements = [
            {"id": "tower_west", "asset": "stage4e_faceted_tower", "x": 8, "z": 16, "rotation": 0},
            {"id": "tower_east", "asset": "stage4e_faceted_tower", "x": 24, "z": 16, "rotation": 90},
        ]
        with self.assertRaises(AssetError) as raised:
            compile_placements(CATALOG, placements, ROOT)
        self.assertEqual(raised.exception.code, "display_list_overflow")

    def test_apex_mutation_changes_triangle_geometry_only(self) -> None:
        temporary = TemporaryTriangleAsset()
        try:
            before = compile_asset(temporary.manifest_path, ROOT)
            source = temporary.source.read_text(encoding="utf-8")
            temporary.source.write_text(source.replace("v 0.0 6.0 0.0", "v 0.0 6.5 0.0"), encoding="utf-8")
            after = compile_asset(temporary.manifest_path, ROOT)
            self.assertEqual(before["manifest"]["id"], after["manifest"]["id"])
            self.assertNotEqual(before["report"]["source_sha256"], after["report"]["source_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["normalized_mesh_sha256"], after["report"]["hashes"]["normalized_mesh_sha256"])
            self.assertNotEqual(before["report"]["hashes"]["display_list_sha256"], after["report"]["hashes"]["display_list_sha256"])
            self.assertEqual(before["report"]["hashes"]["collision_sha256"], after["report"]["hashes"]["collision_sha256"])
            for texture_id in before["textures"]:
                self.assertEqual(before["textures"][texture_id]["texture"], after["textures"][texture_id]["texture"])
                self.assertEqual(before["textures"][texture_id]["palette"], after["textures"][texture_id]["palette"])
        finally:
            temporary.close()

    def test_fixture_is_symbolic_and_compilation_order_is_deterministic(self) -> None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIsInstance(source["model"]["area_data"], str)
        self.assertIsInstance(source["texture_container"]["area_texture_member"], str)
        first = compile_asset(MANIFEST, ROOT)
        second = compile_asset(MANIFEST, ROOT)
        self.assertEqual(first["ir"], second["ir"])
        self.assertEqual(first["display_list"], second["display_list"])
        resolved = load_fixture(FIXTURE)
        self.assertEqual(resolved["schema_version"], 11)
        self.assertEqual(resolved["model"]["area_data"], 106)


if __name__ == "__main__":
    unittest.main()
