from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom
from PIL import Image

from tools.pokeagent.assets import compile_asset, compile_placements
from tools.pokeagent.registry import load_registry, resolve_stage4d_source
from tools.pokeagent.textures import (
    TextureError,
    build_project_btx0,
    compile_texture_catalog,
    load_texture_catalog,
    parse_btx0,
)
from tools.pokeagent.world import build_map_header, load_fixture


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "assets/texture_catalog.json"
FIXTURE = ROOT / "fixtures/stage4d_scalable_textures_world.json"
ROM = ROOT / "rom.nds"


class Stage4DTextureCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_data = json.loads(CATALOG.read_text(encoding="utf-8"))

    def _load_variant(self, data: dict) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_texture_catalog(path, ROOT)

    def test_catalog_allocations_and_material_bindings_are_distinct(self) -> None:
        compiled = compile_texture_catalog(CATALOG, ROOT)
        allocations = compiled["report"]["allocations"]
        self.assertEqual([item["allocation"] for item in allocations], [0, 1, 2])
        self.assertEqual([item["symbol"] for item in allocations], [
            "stage4d_ground", "stage4d_wood", "stage4d_stone",
        ])
        self.assertEqual(compiled["report"]["physical_container"], {
            "archive": "a/0/4/4", "member": 106, "provenance": "PROJECT_APPENDED",
        })
        self.assertEqual(allocations[1]["bindings"], [{
            "asset": "stage4d_wood_shed", "source_material": "shed_shell", "material_alias": "prop",
        }])
        self.assertEqual(allocations[2]["bindings"], [{
            "asset": "stage4d_stone_monument", "source_material": "monument_shell",
            "material_alias": "prop_secondary",
        }])
        placed = compile_placements(ROOT / "assets/catalog.json", [
            {"id": "a", "asset": "stage4d_wood_shed", "x": 10, "z": 16, "rotation": 0},
            {"id": "b", "asset": "stage4d_stone_monument", "x": 22, "z": 16, "rotation": 0},
        ], ROOT)
        self.assertEqual(sorted(placed["display_lists"]), [1, 6])
        self.assertNotEqual(placed["display_lists"][1], placed["display_lists"][6])

    def test_unrelated_append_keeps_existing_allocations_stable(self) -> None:
        before = self._load_variant(self.catalog_data)
        variant = copy.deepcopy(self.catalog_data)
        probe = copy.deepcopy(variant["textures"][0])
        probe.update({
            "allocation": 3, "nitro_texture": "cavekn", "nitro_palette": "cavekn_pl",
            "texture_slot": 0, "palette_slot": 0,
        })
        probe["texture"]["id"] = "stage4d_unrelated_probe"
        variant["textures"].append(probe)
        after = self._load_variant(variant)
        project = lambda data: [
            (entry["texture"]["id"], entry["allocation"], entry["texture_slot"], entry["palette_slot"])
            for entry in data["textures"][:3]
        ]
        self.assertEqual(project(before), project(after))

    def test_catalog_rejects_collisions_names_gaps_and_revision(self) -> None:
        variants = []
        duplicate_symbol = copy.deepcopy(self.catalog_data)
        duplicate_symbol["textures"][1]["texture"]["id"] = duplicate_symbol["textures"][0]["texture"]["id"]
        variants.append((duplicate_symbol, "duplicate_texture_symbol"))
        duplicate_name = copy.deepcopy(self.catalog_data)
        duplicate_name["textures"][1]["nitro_texture"] = duplicate_name["textures"][0]["nitro_texture"]
        variants.append((duplicate_name, "duplicate_physical_name"))
        gap = copy.deepcopy(self.catalog_data)
        gap["textures"][2]["allocation"] = 4
        variants.append((gap, "unstable_texture_allocation"))
        revision = copy.deepcopy(self.catalog_data)
        revision["target"]["rom_sha256"] = "0" * 64
        variants.append((revision, "unsupported_container_revision"))
        overflow = copy.deepcopy(self.catalog_data)
        overflow["textures"][0]["nitro_texture"] = "this_name_is_far_too_long"
        variants.append((overflow, "texture_name_overflow"))
        retail = copy.deepcopy(self.catalog_data)
        retail["target"]["project_member"] = 105
        variants.append((retail, "unsupported_container_revision"))
        shared_payload = copy.deepcopy(self.catalog_data)
        shared_payload["textures"][1]["texture_slot"] = shared_payload["textures"][0]["texture_slot"]
        shared_payload["textures"][1]["palette_slot"] = shared_payload["textures"][0]["palette_slot"]
        variants.append((shared_payload, "duplicate_texture_payload"))
        for data, code in variants:
            with self.subTest(code=code), self.assertRaises(TextureError) as raised:
                self._load_variant(data)
            self.assertEqual(raised.exception.code, code)

    @unittest.skipUnless(ROM.is_file(), "ignored supported ROM prerequisite is absent")
    def test_parser_rejects_malformed_dictionary_and_payload_offsets(self) -> None:
        rom = NintendoDSRom.fromFile(str(ROM))
        template = NARC(rom.getFileByName("a/0/4/4")).files[2]
        layout = parse_btx0(template)

        malformed_count = bytearray(template)
        texture_info = layout.tex0_offset + struct.unpack_from("<H", template, layout.tex0_offset + 0x0E)[0]
        malformed_count[texture_info + 1] = 0xFF
        with self.assertRaises(TextureError) as raised:
            parse_btx0(bytes(malformed_count))
        self.assertEqual(raised.exception.code, "malformed_texture_dictionary")

        malformed_offset = bytearray(template)
        texture_properties = texture_info + 4 + struct.unpack_from("<H", template, texture_info + 6)[0]
        struct.pack_into("<H", malformed_offset, texture_properties + 21 * 8, 0xFFFF)
        with self.assertRaises(TextureError) as raised:
            parse_btx0(bytes(malformed_offset))
        self.assertEqual(raised.exception.code, "invalid_texture_offset")

    @unittest.skipUnless(ROM.is_file(), "ignored supported ROM prerequisite is absent")
    def test_project_container_reopens_and_payloads_match(self) -> None:
        rom = NintendoDSRom.fromFile(str(ROM))
        template = NARC(rom.getFileByName("a/0/4/4")).files[2]
        compiled = compile_texture_catalog(CATALOG, ROOT)
        project, report = build_project_btx0(template, compiled)
        layout = parse_btx0(project)
        self.assertTrue(report["parser_reopen_succeeded"])
        self.assertEqual(report["inherited_payload_bytes_copied"], 0)
        self.assertEqual(report["project_entry_count"], 3)
        for entry in self.catalog_data["textures"]:
            texture = layout.textures[entry["texture_slot"]]
            palette = layout.palettes[entry["palette_slot"]]
            generated = compiled["textures"][entry["texture"]["id"]]
            self.assertEqual(project[texture.image_offset:texture.image_offset + 512], generated["texture"])
            self.assertEqual(project[palette.data_offset:palette.data_offset + 32], generated["palette"])

    def test_stage4d_symbolic_resolution_and_fixed_camera_header(self) -> None:
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        resolved = resolve_stage4d_source(source, ROOT / "world/registry.json")
        self.assertEqual(resolved["model"]["area_data"], 106)
        self.assertEqual(resolved["texture_container"]["area_texture_member"], 106)
        fixture = load_fixture(FIXTURE)
        arm9 = (ROOT / "base/arm9.bin").read_bytes()
        header = build_map_header(fixture, arm9)
        flags = struct.unpack_from("<I", header, 20)[0]
        self.assertEqual(header[1], 106)
        self.assertEqual((flags >> 12) & 0x3F, 4)

    def test_stage4d_manifest_rejects_missing_catalog_texture(self) -> None:
        manifest = json.loads((ROOT / "assets/manifests/stage4d_wood_shed.json").read_text())
        manifest["material_policy"]["mappings"]["shed_shell"]["texture"] = "missing"
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/manifests") as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported alias or catalog texture"):
                compile_asset(path, ROOT)

    def test_texture_source_mutation_changes_only_texture_outputs(self) -> None:
        baseline_catalog = compile_texture_catalog(CATALOG, ROOT)
        baseline_asset = compile_asset(ROOT / "assets/manifests/stage4d_wood_shed.json", ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "assets/textures") as temporary:
            texture_path = Path(temporary) / "mutated.png"
            image = Image.open(ROOT / "assets/textures/stage4d_wood.png").convert("RGB")
            image.putpixel((0, 0), (248, 0, 248))
            image.save(texture_path)
            variant = copy.deepcopy(self.catalog_data)
            relative = texture_path.relative_to(ROOT).as_posix()
            variant["textures"][1]["texture"]["source"] = relative
            catalog_path = Path(temporary) / "catalog.json"
            catalog_path.write_text(json.dumps(variant), encoding="utf-8")
            mutated = compile_texture_catalog(catalog_path, ROOT)
        base_wood = baseline_catalog["textures"]["stage4d_wood"]
        mutated_wood = mutated["textures"]["stage4d_wood"]
        self.assertNotEqual(base_wood["report"]["source_sha256"], mutated_wood["report"]["source_sha256"])
        self.assertNotEqual(base_wood["texture"], mutated_wood["texture"])
        self.assertNotEqual(base_wood["palette"], mutated_wood["palette"])
        after_asset = compile_asset(ROOT / "assets/manifests/stage4d_wood_shed.json", ROOT)
        self.assertEqual(baseline_asset["report"]["hashes"]["normalized_mesh_sha256"],
                         after_asset["report"]["hashes"]["normalized_mesh_sha256"])
        self.assertEqual(baseline_asset["report"]["hashes"]["collision_sha256"],
                         after_asset["report"]["hashes"]["collision_sha256"])


if __name__ == "__main__":
    unittest.main()
