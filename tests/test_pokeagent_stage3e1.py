from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from ndspy.narc import NARC

from tools.pokeagent.registry import (
    RegistryError,
    allocate_appended_resource,
    load_registry,
    resolve_symbol,
    validate_registry,
)
from tools.pokeagent.world import (
    _narc_btaf_count,
    _replace_narc_members,
    build_event,
    build_map_header,
    build_matrix,
    load_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "stage3e1_narc_append_world.json"


def append_registry() -> dict:
    append = {
        "archive": "widgets", "pristine_count": 2, "allocation_start": 2,
        "proven_max_id": 4, "policy": "contiguous_from_pristine_count",
    }
    namespace = {
        "storage": "unit_test", "collision_domain": "shared_widgets",
        "allocation_policy": "persistent_contiguous_append_after_stage3e1",
        "numeric_min": 0, "numeric_max": 8,
        "ranges": [
            {"start": 0, "end": 1, "classification": "VANILLA_OWNED", "evidence": "test retail"},
            {"start": 2, "end": 4, "classification": "APPEND_PROVEN", "evidence": "test proof"},
            {"start": 5, "end": 8, "classification": "UNKNOWN", "evidence": "untested"},
        ],
        "append": append,
        "slot_overrides": {},
        "resources": [],
    }
    return {
        "schema_version": 1,
        "target": {
            "game_code": "IPKE", "rom_sha256": "0" * 64, "arm9_sha256": "1" * 64,
            "archives": {"widgets": {"path": "x", "members": 2, "sha256": "2" * 64}},
        },
        "namespaces": {"widgets_a": copy.deepcopy(namespace), "widgets_b": copy.deepcopy(namespace)},
    }


class Stage3E1FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.fixture = load_fixture(FIXTURE)

    def test_source_is_symbolic_and_resolves_to_bounded_appended_ids(self) -> None:
        self.assertEqual(self.source["schema_version"], 6)
        self.assertIsInstance(self.source["world"]["matrix"]["id"], str)
        for map_spec in self.source["maps"].values():
            for key in ("matrix", "map_header", "map_member", "event_bank", "script_bank", "script_header", "text_bank"):
                self.assertIsInstance(map_spec[key], str)
        self.assertEqual(self.fixture["slots"], {"matrix": 288, "matrix_probe": 289, "start_script": 3})
        self.assertEqual(
            [(m["map_member"], m["event"], m["script"], m["script_header"], m["text"])
             for m in self.fixture["maps"].values()],
            [(676, 491, 965, 967, 854), (677, 492, 966, 968, 855)],
        )

    def test_matrix_and_events_encode_appended_references_without_warps(self) -> None:
        matrix = build_matrix(self.fixture)
        name_length = matrix[4]
        offset = 5 + name_length
        self.assertEqual(matrix[:4], bytes((2, 1, 1, 1)))
        self.assertEqual(struct.unpack_from("<2H", matrix, offset), (538, 9))
        self.assertEqual(matrix[offset + 4:offset + 6], b"\0\0")
        self.assertEqual(struct.unpack_from("<2H", matrix, offset + 6), (676, 677))
        for name, expected_x in (("west", 16), ("east", 36)):
            event = build_event(self.fixture, name)
            self.assertEqual(struct.unpack_from("<4I", event, 0)[0:2], (0, 1))
            npc = struct.unpack_from("<6Hh3HhhHHi", event, 8)
            self.assertEqual((npc[5], npc[12], npc[13]), (1, expected_x, 14))
            self.assertEqual(struct.unpack_from("<2I", event, 40), (0, 0))

    def test_headers_store_full_u16_appended_banks(self) -> None:
        arm9 = bytearray(0xF6BE0 + 540 * 24)
        template = self.fixture["header_template"]
        arm9[0xF6BE0 + template * 24:0xF6BE0 + (template + 1) * 24] = bytes(range(24))
        west = build_map_header(self.fixture, bytes(arm9), "west")
        east = build_map_header(self.fixture, bytes(arm9), "east")
        self.assertEqual(struct.unpack_from("<4H", west, 4), (288, 965, 967, 854))
        self.assertEqual(struct.unpack_from("<H", west, 16)[0], 491)
        self.assertEqual(struct.unpack_from("<4H", east, 4), (288, 966, 968, 855))
        self.assertEqual(struct.unpack_from("<H", east, 16)[0], 492)

    def test_narc_append_updates_btaf_and_preserves_existing_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.narc"
            output = Path(directory) / "output.narc"
            archive = NARC()
            archive.files = [b"retail-a", b"retail-b"]
            archive.saveToFile(str(source))
            report = _replace_narc_members(source, {2: b"new-c", 3: b"new-d"}, output)
            rebuilt = NARC.fromFile(str(output))
            self.assertEqual(rebuilt.files, [b"retail-a", b"retail-b", b"new-c", b"new-d"])
            self.assertEqual(report["appended_ids"], [2, 3])
            self.assertEqual(report["rebuilt_count"], 4)
            self.assertEqual(_narc_btaf_count(output.read_bytes()), 4)

    def test_narc_gap_and_malformed_btaf_are_rejected_or_detectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.narc"
            output = Path(directory) / "output.narc"
            archive = NARC()
            archive.files = [b"a"]
            archive.saveToFile(str(source))
            with self.assertRaisesRegex(ValueError, "gap"):
                _replace_narc_members(source, {2: b"c"}, output)
            corrupted = bytearray(source.read_bytes())
            offset = corrupted.find(b"BTAF")
            struct.pack_into("<H", corrupted, offset + 8, 7)
            self.assertEqual(_narc_btaf_count(bytes(corrupted)), 7)
            self.assertNotEqual(_narc_btaf_count(bytes(corrupted)), len(NARC.fromFile(str(source)).files))


class Stage3E1RegistryTests(unittest.TestCase):
    def test_real_registry_distinguishes_retail_engine_and_project_append_ownership(self) -> None:
        registry = load_registry()
        text = registry["namespaces"]["text_banks"]
        self.assertEqual(text["append"]["pristine_count"], 829)
        self.assertEqual(text["append"]["allocation_start"], 854)
        self.assertEqual(resolve_symbol(registry, "stage3e1_west_text", "text_banks")["classification"], "PROJECT_APPENDED")
        self.assertEqual(resolve_symbol(registry, "stage3e1_east_member", "map_members")["id"], 677)

    @patch("tools.pokeagent.registry.verify_rom_revision", return_value={"game_code": "IPKE"})
    def test_appended_allocations_are_persistent_stable_and_shared_domain_safe(self, _verify) -> None:
        registry = append_registry()
        registry, alpha = allocate_appended_resource(registry, "widgets_a", "alpha", Path("rom.nds"))
        registry, bravo = allocate_appended_resource(registry, "widgets_b", "bravo", Path("rom.nds"))
        before = {symbol: resolve_symbol(registry, symbol)["id"] for symbol in ("alpha", "bravo")}
        registry, charlie = allocate_appended_resource(registry, "widgets_a", "charlie", Path("rom.nds"))
        self.assertEqual((alpha["id"], bravo["id"], charlie["id"]), (2, 3, 4))
        self.assertEqual(before, {symbol: resolve_symbol(registry, symbol)["id"] for symbol in before})

    @patch("tools.pokeagent.registry.verify_rom_revision", return_value={"game_code": "IPKE"})
    def test_append_failures_cover_unproven_below_boundary_collision_gap_and_exhaustion(self, _verify) -> None:
        registry = append_registry()
        with self.assertRaises(RegistryError) as below:
            allocate_appended_resource(registry, "widgets_a", "bad", Path("rom.nds"), 1)
        self.assertEqual(below.exception.code, "append_below_pristine")
        with self.assertRaises(RegistryError) as gap:
            allocate_appended_resource(registry, "widgets_a", "bad", Path("rom.nds"), 3)
        self.assertEqual(gap.exception.code, "noncontiguous_append_pin")
        registry["namespaces"]["widgets_a"].pop("append")
        with self.assertRaises(RegistryError) as unproven:
            allocate_appended_resource(registry, "widgets_a", "bad", Path("rom.nds"))
        self.assertEqual(unproven.exception.code, "unproven_append")

        registry = append_registry()
        for symbol in ("alpha", "bravo", "charlie"):
            registry, _ = allocate_appended_resource(
                registry, "widgets_a", symbol, Path("rom.nds")
            )
        with self.assertRaises(RegistryError) as exhausted:
            allocate_appended_resource(registry, "widgets_a", "delta", Path("rom.nds"))
        self.assertEqual(exhausted.exception.code, "append_allocation_exhausted")

        registry = append_registry()
        namespace = registry["namespaces"]["widgets_b"]
        namespace["slot_overrides"]["2"] = {
            "classification": "CONTROLLED_REPLACEMENT", "evidence": "test collision",
        }
        namespace["resources"].append({
            "symbol": "controlled_tail", "id": 2, "access": "write",
        })
        with self.assertRaises(RegistryError) as collision:
            allocate_appended_resource(
                registry, "widgets_a", "append_after_controlled", Path("rom.nds")
            )
        self.assertEqual(collision.exception.code, "append_gap")

    @patch(
        "tools.pokeagent.registry.verify_rom_revision",
        side_effect=RegistryError("unsupported_rom_revision", "wrong revision"),
    )
    def test_append_allocation_refuses_wrong_rom_revision(self, _verify) -> None:
        with self.assertRaises(RegistryError) as error:
            allocate_appended_resource(
                append_registry(), "widgets_a", "alpha", Path("wrong.nds")
            )
        self.assertEqual(error.exception.code, "unsupported_rom_revision")

    def test_scanner_evidence_mismatch_duplicate_ownership_and_append_gap_fail(self) -> None:
        registry = append_registry()
        registry["namespaces"]["widgets_a"]["append"]["pristine_count"] = 1
        with self.assertRaises(RegistryError) as mismatch:
            validate_registry(registry)
        self.assertEqual(mismatch.exception.code, "append_evidence_mismatch")

        registry = append_registry()
        for namespace_name in ("widgets_a", "widgets_b"):
            ns = registry["namespaces"][namespace_name]
            ns["slot_overrides"]["2"] = {"classification": "PROJECT_APPENDED", "evidence": "test"}
            ns["resources"].append({"symbol": f"owner_{namespace_name}", "id": 2, "access": "write"})
        with self.assertRaises(RegistryError) as duplicate:
            validate_registry(registry)
        self.assertEqual(duplicate.exception.code, "duplicate_numeric_ownership")

        registry = append_registry()
        ns = registry["namespaces"]["widgets_a"]
        ns["slot_overrides"]["3"] = {"classification": "PROJECT_APPENDED", "evidence": "test"}
        ns["resources"].append({"symbol": "skipped_first", "id": 3, "access": "write"})
        with self.assertRaises(RegistryError) as gap:
            validate_registry(registry)
        self.assertEqual(gap.exception.code, "append_gap")


if __name__ == "__main__":
    unittest.main()
