from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.pokeagent.registry import (
    RegistryError,
    allocate_project_header,
    load_registry,
    resolve_symbol,
    validate_registry,
)
from tools.pokeagent.world import (
    MAP_HEADER_SIZE,
    WorldBuildError,
    build_event,
    build_map_header,
    build_matrix,
    load_fixture,
    validate_project_header_table,
    write_project_header_include,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "stage3e2_header_expansion_world.json"


class Stage3E2FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.fixture = load_fixture(FIXTURE)

    def test_symbolic_source_resolves_to_project_headers_and_appended_resources(self) -> None:
        self.assertEqual(self.source["schema_version"], 7)
        self.assertEqual(
            [entry["map_header"] for entry in self.source["maps"].values()],
            ["stage3e2_project_header_a", "stage3e2_project_header_b"],
        )
        self.assertEqual([entry["map_header"] for entry in self.fixture["maps"].values()], [540, 541])
        self.assertEqual([entry["map_member"] for entry in self.fixture["maps"].values()], [676, 677])
        self.assertEqual(self.fixture["warps"], [])

    def test_matrix_uses_full_u16_project_headers_and_native_adjacency(self) -> None:
        matrix = build_matrix(self.fixture)
        offset = 5 + matrix[4]
        self.assertEqual(matrix[:4], bytes((2, 1, 1, 1)))
        self.assertEqual(struct.unpack_from("<2H", matrix, offset), (540, 541))
        self.assertEqual(struct.unpack_from("<2H", matrix, offset + 6), (676, 677))
        for name in ("west", "east"):
            event = build_event(self.fixture, name)
            self.assertEqual(struct.unpack_from("<I", event, 40)[0], 0)

    def test_generated_headers_are_complete_deterministic_24_byte_records(self) -> None:
        west = build_map_header(self.fixture, b"", "west")
        east = build_map_header(self.fixture, b"", "east")
        self.assertEqual(len(west), MAP_HEADER_SIZE)
        self.assertEqual(len(east), MAP_HEADER_SIZE)
        self.assertEqual(west.hex(), "ff020f002001c503c7035603fb03fb03eb017f11000108f6")
        self.assertEqual(east.hex(), "ff020f002001c603c8035703fb03fb03ec017f11000108f6")
        self.assertEqual(struct.unpack_from("<4H", west, 4), (288, 965, 967, 854))
        self.assertEqual(struct.unpack_from("<H", east, 16)[0], 492)
        validate_project_header_table(self.fixture, west + east)
        with self.assertRaisesRegex(WorldBuildError, "table length"):
            validate_project_header_table(self.fixture, west + east[:-1])
        below_boundary = copy.deepcopy(self.fixture)
        below_boundary["maps"]["west"]["map_header"] = 539
        with self.assertRaisesRegex(WorldBuildError, "contiguous from the retail boundary"):
            validate_project_header_table(below_boundary, west + east)
        beyond_generated_count = copy.deepcopy(self.fixture)
        beyond_generated_count["maps"]["east"]["map_header"] = 542
        with self.assertRaisesRegex(WorldBuildError, "contiguous from the retail boundary"):
            validate_project_header_table(beyond_generated_count, west + east)

    def test_generated_c_include_locks_boundary_count_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "project_map_headers.h"
            report = write_project_header_include(FIXTURE, output)
            text = output.read_text(encoding="utf-8")
        self.assertEqual(report["project_ids"], [540, 541])
        self.assertIn("#define PROJECT_MAP_HEADER_BASE 540u", text)
        self.assertIn("#define PROJECT_MAP_HEADER_COUNT 2u", text)
        self.assertEqual(
            report["sha256"],
            "0a518ef966537e7a7e503c47e57a6313dad986767a8f3ecd31838a4e79c176fd",
        )


class Stage3E2RegistryTests(unittest.TestCase):
    def test_real_registry_protects_retail_and_owns_only_expanded_headers(self) -> None:
        registry = load_registry()
        namespace = registry["namespaces"]["map_headers"]
        self.assertEqual(namespace["header_expansion"], {
            "retail_count": 540,
            "entry_size": 24,
            "allocation_start": 540,
            "proven_max_id": 541,
            "policy": "contiguous_from_retail_boundary",
        })
        for symbol, expected in (
            ("stage3e2_project_header_a", 540),
            ("stage3e2_project_header_b", 541),
        ):
            resolved = resolve_symbol(registry, symbol, "map_headers")
            self.assertEqual((resolved["id"], resolved["classification"]), (expected, "PROJECT_HEADER"))
        self.assertEqual(resolve_symbol(registry, "stage3c_proof_northeast_header", "map_headers")["classification"], "CONTROLLED_REPLACEMENT")

    @patch("tools.pokeagent.registry.verify_rom_revision", return_value={"game_code": "IPKE"})
    def test_allocator_is_contiguous_stable_and_exhausts_proven_window(self, _verify) -> None:
        registry = load_registry()
        namespace = registry["namespaces"]["map_headers"]
        namespace["header_expansion"]["proven_max_id"] = 542
        namespace["ranges"][1]["end"] = 542
        namespace["ranges"][2]["start"] = 543
        before = {
            symbol: resolve_symbol(registry, symbol, "map_headers")["id"]
            for symbol in ("stage3e2_project_header_a", "stage3e2_project_header_b")
        }
        registry, allocated = allocate_project_header(registry, "future_project_header", Path("rom.nds"))
        self.assertEqual(allocated["id"], 542)
        self.assertEqual(
            before,
            {symbol: resolve_symbol(registry, symbol, "map_headers")["id"] for symbol in before},
        )
        with self.assertRaises(RegistryError) as exhausted:
            allocate_project_header(registry, "another_project_header", Path("rom.nds"))
        self.assertEqual(exhausted.exception.code, "header_allocation_exhausted")

    @patch("tools.pokeagent.registry.verify_rom_revision", return_value={"game_code": "IPKE"})
    def test_allocator_rejects_retail_collision_gap_duplicate_and_bad_pin(self, _verify) -> None:
        registry = load_registry()
        with self.assertRaises(RegistryError) as below:
            allocate_project_header(registry, "bad_retail_header", Path("rom.nds"), 539)
        self.assertEqual(below.exception.code, "header_below_expansion_boundary")
        with self.assertRaises(RegistryError) as exhausted:
            allocate_project_header(registry, "no_capacity", Path("rom.nds"))
        self.assertEqual(exhausted.exception.code, "header_allocation_exhausted")
        with self.assertRaises(RegistryError) as duplicate:
            allocate_project_header(registry, "stage3e2_project_header_a", Path("rom.nds"))
        self.assertEqual(duplicate.exception.code, "duplicate_symbol")

        malformed = copy.deepcopy(registry)
        malformed["namespaces"]["map_headers"]["resources"].append({
            "symbol": "duplicate_header_owner", "id": 540, "access": "write",
        })
        with self.assertRaises(RegistryError) as collision:
            validate_registry(malformed)
        self.assertEqual(collision.exception.code, "duplicate_numeric_ownership")

    @patch(
        "tools.pokeagent.registry.verify_rom_revision",
        side_effect=RegistryError("unsupported_rom_revision", "wrong revision"),
    )
    def test_allocator_refuses_wrong_rom_revision(self, _verify) -> None:
        with self.assertRaises(RegistryError) as error:
            allocate_project_header(load_registry(), "new_header", Path("wrong.nds"))
        self.assertEqual(error.exception.code, "unsupported_rom_revision")

    def test_validation_rejects_bad_expansion_boundary_gap_and_unknown_provenance(self) -> None:
        registry = load_registry()
        registry["namespaces"]["map_headers"]["header_expansion"]["allocation_start"] = 539
        with self.assertRaises(RegistryError) as boundary:
            validate_registry(registry)
        self.assertEqual(boundary.exception.code, "header_expansion_evidence_mismatch")

        registry = load_registry()
        resources = registry["namespaces"]["map_headers"]["resources"]
        resources[:] = [resource for resource in resources if resource["id"] != 540]
        with self.assertRaises(RegistryError) as gap:
            validate_registry(registry)
        self.assertEqual(gap.exception.code, "header_expansion_gap")


if __name__ == "__main__":
    unittest.main()
