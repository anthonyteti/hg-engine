from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.pokeagent.registry import (
    DEFAULT_REGISTRY,
    RegistryError,
    allocate_resource,
    load_registry,
    resolve_symbol,
    resolve_world_source,
    validate_registry,
    verify_rom_revision,
)
from tools.pokeagent.world import STAGE3B_CELL_ORDER, load_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "stage3c_symbolic_registry_world.json"


def allocation_registry(classification: str = "KNOWN_FREE") -> dict:
    return {
        "schema_version": 1,
        "target": {"game_code": "IPKE", "rom_sha256": "0" * 64, "arm9_sha256": "1" * 64},
        "namespaces": {
            "widgets": {
                "storage": "unit_test",
                "collision_domain": "widgets",
                "allocation_policy": "persistent",
                "numeric_min": 0,
                "numeric_max": 3,
                "ranges": [{"start": 0, "end": 3, "classification": classification, "evidence": "unit test"}],
                "slot_overrides": {},
                "resources": [],
            }
        },
    }


class RegistryCanonicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(DEFAULT_REGISTRY)
        cls.source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.fixture = load_fixture(FIXTURE)

    def test_registry_models_every_world_namespace_and_conservative_provenance(self):
        required = {
            "map_headers", "map_members", "matrices", "event_banks", "local_script_banks",
            "common_scripts", "script_headers", "text_banks", "flags", "variables",
        }
        self.assertTrue(required <= self.registry["namespaces"].keys())
        classifications = {
            range_spec["classification"]
            for namespace in self.registry["namespaces"].values()
            for range_spec in namespace["ranges"]
        } | {
            override["classification"]
            for namespace in self.registry["namespaces"].values()
            for override in namespace["slot_overrides"].values()
        }
        self.assertTrue({"CONTROLLED_REPLACEMENT", "VANILLA_OWNED", "RESERVED", "UNKNOWN"} <= classifications)
        self.assertNotIn("KNOWN_FREE", classifications)

    def test_symbolic_fixture_resolves_to_existing_stage3b_serializer_ir(self):
        self.assertEqual(self.source["schema_version"], 4)
        self.assertEqual(self.fixture["schema_version"], 3)
        self.assertEqual(self.fixture["canonical_schema_version"], 4)
        self.assertEqual(self.fixture["slots"], {
            "matrix": 1, "event": 57, "script": 842, "start_script": 3,
            "script_header": 399, "text": 542,
        })
        self.assertEqual(
            [self.fixture["maps"][name]["map_header"] for name in STAGE3B_CELL_ORDER],
            [538, 9, 10, 11],
        )
        self.assertEqual(
            [self.fixture["maps"][name]["map_member"] for name in STAGE3B_CELL_ORDER],
            [633, 630, 631, 632],
        )
        self.assertGreaterEqual(len(self.fixture["registry_resolution"]["symbols"]), 15)

    def test_all_registry_owned_authoring_references_are_symbolic(self):
        self.assertIsInstance(self.source["world"]["matrix"]["id"], str)
        self.assertTrue(all(isinstance(value, str) for value in self.source["resources"].values()))
        self.assertIsInstance(self.source["model"]["template_map_member"], str)
        self.assertIsInstance(self.source["model"]["area_data"], str)
        self.assertIsInstance(self.source["header_template"], str)
        for map_spec in self.source["maps"].values():
            for key in ("matrix", "map_header", "map_member", "event_bank", "script_bank", "script_header", "text_bank"):
                self.assertIsInstance(map_spec[key], str)

    def test_resolve_reports_namespace_numeric_id_and_provenance(self):
        result = resolve_symbol(self.registry, "stage3c_proof_northwest_header", "map_headers")
        self.assertEqual(result["id"], 538)
        self.assertEqual(result["classification"], "CONTROLLED_REPLACEMENT")


class RegistryStabilityAndFailureTests(unittest.TestCase):
    def test_persistent_allocations_do_not_renumber_when_unrelated_resource_is_added(self):
        registry = allocation_registry()
        before = {}
        for symbol in ("alpha", "bravo", "charlie"):
            registry, result = allocate_resource(registry, "widgets", symbol)
            before[symbol] = result["id"]
        registry, delta = allocate_resource(registry, "widgets", "delta")
        after = {symbol: resolve_symbol(registry, symbol, "widgets")["id"] for symbol in before}
        self.assertEqual(before, after)
        self.assertEqual(delta["id"], 3)
        registry["namespaces"]["widgets"]["resources"] = [
            resource
            for resource in registry["namespaces"]["widgets"]["resources"]
            if resource["symbol"] != "delta"
        ]
        self.assertEqual(
            before,
            {symbol: resolve_symbol(registry, symbol, "widgets")["id"] for symbol in before},
        )
        registry, delta_readded = allocate_resource(registry, "widgets", "delta")
        self.assertEqual(delta_readded["id"], 3)
        self.assertEqual(validate_registry(copy.deepcopy(registry)), registry)

    def test_duplicate_symbol_fails(self):
        registry = copy.deepcopy(load_registry())
        registry["namespaces"]["event_banks"]["slot_overrides"]["58"] = {
            "classification": "CONTROLLED_REPLACEMENT", "evidence": "test",
        }
        registry["namespaces"]["event_banks"]["resources"].append({
            "symbol": "stage3c_proof_northwest_header", "id": 58, "access": "write",
        })
        with self.assertRaisesRegex(RegistryError, "declared more than once") as caught:
            validate_registry(registry)
        self.assertEqual(caught.exception.code, "duplicate_symbol")

    def test_duplicate_numeric_ownership_across_shared_script_domain_fails(self):
        registry = copy.deepcopy(load_registry())
        common = registry["namespaces"]["common_scripts"]
        common["slot_overrides"]["842"] = {"classification": "CONTROLLED_REPLACEMENT", "evidence": "test"}
        common["resources"].append({"symbol": "conflicting_script", "id": 842, "access": "write"})
        with self.assertRaises(RegistryError) as caught:
            validate_registry(registry)
        self.assertEqual(caught.exception.code, "duplicate_numeric_ownership")

    def test_exhausted_range_fails(self):
        registry = allocation_registry()
        for symbol in ("alpha", "bravo", "charlie", "delta"):
            registry, _ = allocate_resource(registry, "widgets", symbol)
        with self.assertRaises(RegistryError) as caught:
            allocate_resource(registry, "widgets", "echo")
        self.assertEqual(caught.exception.code, "allocation_exhausted")

    def test_unknown_and_wrong_namespace_references_fail(self):
        registry = load_registry()
        with self.assertRaises(RegistryError) as unknown:
            resolve_symbol(registry, "missing_resource")
        self.assertEqual(unknown.exception.code, "unknown_reference")
        with self.assertRaises(RegistryError) as wrong:
            resolve_symbol(registry, "stage3c_proof_matrix", "map_headers")
        self.assertEqual(wrong.exception.code, "wrong_namespace")

    def test_unsupported_rom_revision_fails_before_allocation_or_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.nds"
            path.write_bytes(b"wrong revision")
            fake_rom = type("FakeRom", (), {"idCode": bytearray(b"IPKE"), "arm9": b""})()
            with patch("tools.pokeagent.registry.NintendoDSRom", return_value=fake_rom):
                with self.assertRaises(RegistryError) as caught:
                    verify_rom_revision(load_registry(), path)
        self.assertEqual(caught.exception.code, "unsupported_rom_revision")

    def test_reserved_vanilla_unknown_and_out_of_range_manual_pins_fail(self):
        for classification in ("RESERVED", "VANILLA_OWNED", "UNKNOWN"):
            with self.subTest(classification=classification):
                with self.assertRaises(RegistryError) as caught:
                    allocate_resource(allocation_registry(classification), "widgets", "alpha", 1)
                self.assertEqual(caught.exception.code, "invalid_manual_pin")
                self.assertEqual(caught.exception.details["classification"], classification)
        with self.assertRaises(RegistryError) as caught:
            allocate_resource(allocation_registry(), "widgets", "alpha", 9)
        self.assertEqual(caught.exception.details["classification"], "OUT_OF_RANGE")

    def test_writable_records_cannot_claim_nonwritable_slot_classifications(self):
        for classification in ("RESERVED", "VANILLA_OWNED", "UNKNOWN"):
            with self.subTest(classification=classification):
                registry = allocation_registry(classification)
                registry["namespaces"]["widgets"]["resources"] = [
                    {"symbol": "alpha", "id": 1, "access": "write"}
                ]
                with self.assertRaises(RegistryError) as caught:
                    validate_registry(registry)
                self.assertEqual(caught.exception.code, f"{classification.lower()}_id")

    def _resolve_mutated_source(self, source: dict, registry: dict | None = None):
        registry = copy.deepcopy(load_registry()) if registry is None else registry
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            source = copy.deepcopy(source)
            source["registry"] = str(path)
            return resolve_world_source(source, path)

    def test_deleting_still_referenced_resource_fails(self):
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        registry = copy.deepcopy(load_registry())
        members = registry["namespaces"]["map_members"]["resources"]
        registry["namespaces"]["map_members"]["resources"] = [
            resource for resource in members if resource["symbol"] != "stage3c_proof_northwest_member"
        ]
        with self.assertRaises(RegistryError) as caught:
            self._resolve_mutated_source(source, registry)
        self.assertEqual(caught.exception.code, "unknown_reference")

    def test_numeric_reference_in_symbolic_source_fails(self):
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        source["maps"]["stage3c_proof_northwest"]["map_header"] = 538
        with self.assertRaises(RegistryError) as caught:
            self._resolve_mutated_source(source)
        self.assertEqual(caught.exception.code, "numeric_reference")

    def test_missing_map_and_wrong_matrix_relationship_fail(self):
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        del source["maps"]["stage3c_proof_southeast"]
        with self.assertRaises(RegistryError) as missing:
            self._resolve_mutated_source(source)
        self.assertEqual(missing.exception.code, "dangling_map")
        source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        source["maps"]["stage3c_proof_northwest"]["matrix"] = "stage3c_proof_northeast_header"
        with self.assertRaises(RegistryError) as wrong:
            self._resolve_mutated_source(source)
        self.assertEqual(wrong.exception.code, "wrong_matrix_reference")


if __name__ == "__main__":
    unittest.main()
