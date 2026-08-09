from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from ndspy.narc import NARC
from PIL import Image

from tools.pokeagent.assets import AssetError, compile_asset
from tools.pokeagent.textures import (
    TextureError,
    compile_png,
    parse_btx0,
    patch_btx0,
    rgb888_to_bgr555,
)
from tools.pokeagent.world import build_per, load_fixture


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets/manifests/stage4c_textured_shed.json"
PNG = ROOT / "assets/textures/stage4c_shed_atlas.png"
OBJ = ROOT / "assets/source/stage4c_textured_shed.obj"
FIXTURE = ROOT / "fixtures/stage4c_texture_world.json"


class TemporaryTexture:
    def __init__(self) -> None:
        self.context = tempfile.TemporaryDirectory()
        self.root = Path(self.context.name)
        (self.root / "assets/textures").mkdir(parents=True)
        (self.root / "assets/source").mkdir(parents=True)
        (self.root / "assets/manifests").mkdir(parents=True)
        self.png = self.root / "assets/textures/test.png"
        self.obj = self.root / "assets/source/test.obj"
        self.manifest_path = self.root / "assets/manifests/test.json"
        self.png.write_bytes(PNG.read_bytes())
        self.obj.write_bytes(OBJ.read_bytes())
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.manifest["id"] = "test_textured_asset"
        self.manifest["source"] = "assets/source/test.obj"
        self.manifest["textures"][0]["id"] = "test_atlas"
        self.manifest["textures"][0]["source"] = "assets/textures/test.png"
        self.manifest["material_policy"]["mappings"]["shed_shell"]["texture"] = "test_atlas"
        self.write_manifest()

    @property
    def spec(self) -> dict:
        return self.manifest["textures"][0]

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n", encoding="utf-8")

    def close(self) -> None:
        self.context.cleanup()


class TextureCanonicalTests(unittest.TestCase):
    def test_canonical_png_compiles_to_exact_pltt16_budget(self) -> None:
        compiled_asset = compile_asset(MANIFEST, ROOT)
        texture = compiled_asset["textures"]["stage4c_shed_atlas"]
        report = texture["report"]
        self.assertEqual(report["dimensions"], [32, 32])
        self.assertEqual(report["source_mode"], "RGB")
        self.assertEqual(report["encoded_color_count"], 9)
        self.assertEqual(report["texture_bytes"], 512)
        self.assertEqual(report["palette_bytes"], 32)
        self.assertFalse(report["transparency_used"])
        self.assertEqual(report["hashes"]["texture_sha256"], "f05679df7e820caf2b0047b3853fb0c9df496029a8af9c7a9e5c50edfc7fa3e6")
        self.assertEqual(report["hashes"]["palette_sha256"], "c8c051bb3ab1b6191f7f5f2160c1bfca417b31afaa50cca293b1e2c7ab9d594e")

    def test_png_palette_and_texel_order_are_reproducible(self) -> None:
        first = compile_asset(MANIFEST, ROOT)["textures"]["stage4c_shed_atlas"]
        second = compile_asset(MANIFEST, ROOT)["textures"]["stage4c_shed_atlas"]
        self.assertEqual(first["ir"], second["ir"])
        self.assertEqual(first["texture"], second["texture"])
        self.assertEqual(first["palette"], second["palette"])

    def test_bgr555_primary_color_golden_values(self) -> None:
        self.assertEqual(rgb888_to_bgr555(255, 0, 0), 0x001F)
        self.assertEqual(rgb888_to_bgr555(0, 255, 0), 0x03E0)
        self.assertEqual(rgb888_to_bgr555(0, 0, 255), 0x7C00)
        self.assertEqual(rgb888_to_bgr555(255, 255, 255), 0x7FFF)

    def test_schema2_uvs_are_converted_from_obj_to_nitro_texels(self) -> None:
        compiled = compile_asset(MANIFEST, ROOT)
        wall = compiled["quads"][0].vertices
        roof = compiled["quads"][6].vertices
        self.assertEqual([(v[3], v[4]) for v in wall], [(0.0, 32.0), (0.0, 16.0), (32.0, 16.0), (32.0, 32.0)])
        self.assertEqual([(v[3], v[4]) for v in roof], [(0.0, 16.0), (0.0, 0.0), (32.0, 0.0), (32.0, 16.0)])

    def test_texture_mutation_changes_texture_not_geometry_collision_or_identity(self) -> None:
        temporary = TemporaryTexture()
        try:
            before = compile_asset(temporary.manifest_path, temporary.root)
            with Image.open(temporary.png) as image:
                mutated = image.copy()
            mutated.putpixel((1, 1), mutated.getpixel((0, 3)))
            mutated.save(temporary.png, format="PNG", optimize=False, compress_level=9)
            after = compile_asset(temporary.manifest_path, temporary.root)
            before_texture = before["textures"]["test_atlas"]["report"]
            after_texture = after["textures"]["test_atlas"]["report"]
            self.assertEqual(before["manifest"]["id"], after["manifest"]["id"])
            self.assertNotEqual(before_texture["source_sha256"], after_texture["source_sha256"])
            self.assertNotEqual(before_texture["hashes"]["image_ir_sha256"], after_texture["hashes"]["image_ir_sha256"])
            self.assertNotEqual(before_texture["hashes"]["texture_sha256"], after_texture["hashes"]["texture_sha256"])
            self.assertEqual(before["report"]["hashes"]["display_list_sha256"], after["report"]["hashes"]["display_list_sha256"])
            self.assertEqual(before["report"]["hashes"]["collision_sha256"], after["report"]["hashes"]["collision_sha256"])
        finally:
            temporary.close()

    def test_world_collision_remains_stage4b_equivalent(self) -> None:
        fixture = load_fixture(FIXTURE)
        per = build_per(fixture)
        self.assertEqual(per[(16 * 32 + 16) * 2 + 1], 128)
        self.assertEqual(per[(17 * 32 + 16) * 2 + 1], 0)

    @unittest.skipUnless((ROOT / "rom.nds").is_file(), "user-local supported ROM is required")
    def test_hash_locked_container_patch_preserves_dictionaries_and_other_members(self) -> None:
        rom_archive = NARC((ROOT / "base/root/a/0/4/4").read_bytes())
        # The extracted tree may already contain the deterministic proof patch;
        # take the pristine source from the ignored supported ROM instead.
        from ndspy.rom import NintendoDSRom
        pristine_narc_bytes = NintendoDSRom.fromFile(str(ROOT / "rom.nds")).getFileByName("a/0/4/4")
        pristine = NARC(pristine_narc_bytes)
        texture = compile_asset(MANIFEST, ROOT)["textures"]["stage4c_shed_atlas"]
        patched, report = patch_btx0(pristine.files[2], texture)
        before_layout = parse_btx0(pristine.files[2])
        after_layout = parse_btx0(patched)
        self.assertEqual(before_layout.textures, after_layout.textures)
        self.assertEqual(before_layout.palettes, after_layout.palettes)
        self.assertEqual(report["texture_entry"]["name"], "road01_r")
        self.assertEqual(report["palette_entry"]["name"], "road01_r")
        self.assertTrue(report["dictionary_layout_unchanged"])
        self.assertTrue(report["unrelated_bytes_unchanged"])
        # Later project stages may append new area-texture members. The Stage
        # 4C invariant is that the retail prefix is never truncated and only
        # its explicitly controlled member 2 may differ in that prefix.
        self.assertGreaterEqual(len(rom_archive.files), len(pristine.files))
        self.assertTrue(all(
            rom_archive.files[index] == pristine.files[index]
            for index in range(len(pristine.files)) if index != 2
        ))
        malformed = dict(texture)
        malformed["texture"] = texture["texture"][:-1]
        with self.assertRaises(TextureError) as error:
            patch_btx0(pristine.files[2], malformed)
        self.assertEqual(error.exception.code, "encoded_byte_length_mismatch")


class TextureFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.texture = TemporaryTexture()

    def tearDown(self) -> None:
        self.texture.close()

    def assert_code(self, code: str) -> None:
        with self.assertRaises((TextureError, AssetError)) as error:
            compile_png(self.texture.spec, self.texture.root)
        self.assertEqual(error.exception.code, code)

    def test_missing_unsafe_extension_and_invalid_png(self) -> None:
        self.texture.spec["source"] = "assets/textures/missing.png"
        self.assert_code("missing_png")
        self.texture.spec["source"] = "../escape.png"
        self.assert_code("unsafe_texture_path")
        self.texture.spec["source"] = "assets/textures/test.jpg"
        (self.texture.root / self.texture.spec["source"]).write_bytes(b"not-jpeg")
        self.assert_code("unsupported_image_extension")
        self.texture.spec["source"] = "assets/textures/test.png"
        self.texture.png.write_bytes(b"not-png")
        self.assert_code("invalid_png")

    def test_dimensions_mode_transparency_and_palette_overflow(self) -> None:
        Image.new("RGB", (16, 16), (0, 0, 0)).save(self.texture.png)
        self.assert_code("dimension_mismatch")
        Image.new("L", (32, 32), 0).save(self.texture.png)
        self.assert_code("unsupported_color_mode")
        Image.new("RGBA", (32, 32), (0, 0, 0, 127)).save(self.texture.png)
        self.assert_code("invalid_transparency")
        image = Image.new("RGB", (32, 32))
        image.putdata([((index % 32) * 8, ((index // 32) % 32) * 8, 0) for index in range(1024)])
        image.save(self.texture.png)
        self.assert_code("palette_overflow")

    def test_format_dimension_declaration_and_mapping_failures(self) -> None:
        self.texture.spec["format"] = "direct_color"
        self.assert_code("unsupported_texture_format")
        self.texture.spec["format"] = "nitro_pltt16_4bpp"
        self.texture.spec["dimensions"] = [64, 64]
        self.assert_code("unsupported_texture_dimensions")
        self.texture.spec["dimensions"] = [32, 32]
        self.texture.manifest["material_policy"]["mappings"]["shed_shell"]["texture"] = "missing_texture"
        self.texture.write_manifest()
        with self.assertRaises(AssetError) as error:
            compile_asset(self.texture.manifest_path, self.texture.root)
        self.assertEqual(error.exception.code, "invalid_material_texture_mapping")

    def test_duplicate_texture_and_slot_hash_or_payload_mismatch(self) -> None:
        duplicate = copy.deepcopy(self.texture.spec)
        self.texture.manifest["textures"].append(duplicate)
        self.texture.write_manifest()
        with self.assertRaises(AssetError) as error:
            compile_asset(self.texture.manifest_path, self.texture.root)
        self.assertEqual(error.exception.code, "duplicate_texture_id")
        second = copy.deepcopy(self.texture.spec)
        second["id"] = "other_atlas"
        self.texture.manifest["textures"] = [self.texture.spec, second]
        self.texture.write_manifest()
        with self.assertRaises(AssetError) as error:
            compile_asset(self.texture.manifest_path, self.texture.root)
        self.assertEqual(error.exception.code, "texture_slot_conflict")
        self.texture.manifest["textures"] = [self.texture.spec]
        self.texture.spec["container"]["member_sha256"] = "0" * 64
        compiled = compile_png(self.texture.spec, self.texture.root)
        with self.assertRaises(TextureError) as error:
            patch_btx0(b"BTX0" + bytes(128), compiled)
        self.assertEqual(error.exception.code, "texture_container_hash_mismatch")

    def test_material_slot_conflict_is_rejected(self) -> None:
        self.texture.manifest["material_policy"]["mappings"]["second_shell"] = {
            "alias": "prop", "texture": "test_atlas",
        }
        self.texture.write_manifest()
        with self.assertRaises(AssetError) as error:
            compile_asset(self.texture.manifest_path, self.texture.root)
        self.assertEqual(error.exception.code, "material_slot_conflict")

    def test_malformed_container_metadata_is_rejected(self) -> None:
        with self.assertRaises(TextureError) as error:
            parse_btx0(b"BTX0" + bytes(128))
        self.assertEqual(error.exception.code, "malformed_texture_container")


if __name__ == "__main__":
    unittest.main()
