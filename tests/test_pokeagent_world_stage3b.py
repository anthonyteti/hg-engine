from __future__ import annotations

import copy
import struct
import unittest
from pathlib import Path

from tools.pokeagent.world import (
    HGSS_US_HEADER_OFFSET,
    MAP_HEADER_SIZE,
    STAGE3B_CELL_ORDER,
    WorldBuildError,
    _build_bgs,
    build_bdhc,
    build_event,
    build_map_header,
    build_matrix,
    build_per,
    load_fixture,
    sha256_bytes,
    validate_fixture,
    validate_stage3b_cross_references,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "stage3b_multimap_proof_world.json"


class Stage3BMultiMapFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture(FIXTURE)

    def test_fixture_is_exactly_four_unique_controlled_cells(self):
        self.assertEqual(self.fixture["schema_version"], 3)
        self.assertEqual(self.fixture["world"]["matrix"]["cells"], list(STAGE3B_CELL_ORDER))
        self.assertEqual(
            [self.fixture["maps"][name]["map_header"] for name in STAGE3B_CELL_ORDER],
            [538, 9, 10, 11],
        )
        self.assertEqual(
            [self.fixture["maps"][name]["map_member"] for name in STAGE3B_CELL_ORDER],
            [633, 630, 631, 632],
        )
        self.assertEqual(self.fixture["warps"], [])

    def test_matrix_has_exact_runtime_field_order_and_row_major_grids(self):
        matrix = build_matrix(self.fixture)
        expected = bytes.fromhex(
            "02 02 01 01 0b 73 74 61 67 65 33 62 2d 32 78 32 "
            "1a 02 09 00 0a 00 0b 00 "
            "00 00 00 00 "
            "79 02 76 02 77 02 78 02"
        )
        self.assertEqual(matrix, expected)
        self.assertEqual(sha256_bytes(matrix), "9b1440975e4e5a9515524075351516c2ab5249bfbd1c6bac398b6aceec4968aa")

    def test_internal_edges_are_reciprocal_and_every_exterior_edge_is_blocked(self):
        pers = {name: build_per(self.fixture, name) for name in STAGE3B_CELL_ORDER}

        def collision(name: str, x: int, z: int) -> int:
            return pers[name][(z * 32 + x) * 2 + 1]

        self.assertEqual(collision("nw", 31, 16), 0)
        self.assertEqual(collision("ne", 0, 16), 0)
        self.assertEqual(collision("ne", 16, 31), 0)
        self.assertEqual(collision("se", 16, 0), 0)
        self.assertEqual(collision("se", 0, 16), 0)
        self.assertEqual(collision("sw", 31, 16), 0)
        self.assertEqual(collision("sw", 16, 0), 0)
        self.assertEqual(collision("nw", 16, 31), 0)

        for x in range(32):
            self.assertEqual(collision("nw", x, 0), 128)
            self.assertEqual(collision("sw", x, 31), 128)
            self.assertEqual(collision("ne", x, 0), 128)
            self.assertEqual(collision("se", x, 31), 128)
        for z in range(32):
            self.assertEqual(collision("nw", 0, z), 128)
            self.assertEqual(collision("sw", 0, z), 128)
            self.assertEqual(collision("ne", 31, z), 128)
            self.assertEqual(collision("se", 31, z), 128)

    def test_each_member_has_a_unique_interior_collision_signature(self):
        per_hashes = {name: sha256_bytes(build_per(self.fixture, name)) for name in STAGE3B_CELL_ORDER}
        self.assertEqual(len(set(per_hashes.values())), 4)
        for name in STAGE3B_CELL_ORDER:
            x, z = self.fixture["maps"][name]["identity_blocked_tile"]
            per = build_per(self.fixture, name)
            self.assertEqual(per[(z * 32 + x) * 2 + 1], 128)

    def test_flat_bdhc_and_empty_events_are_shared_without_explicit_warps(self):
        self.assertEqual(build_event(self.fixture), bytes(16))
        self.assertEqual(build_bdhc(self.fixture), build_bdhc(load_fixture()))

    def test_bgs_header_declares_no_payload_before_fixed_per_offset(self):
        template = bytes.fromhex("34 12 58 00") + bytes(88)
        self.assertEqual(_build_bgs(self.fixture, template), bytes.fromhex("34 12 00 00"))

    def test_all_generated_headers_point_to_the_controlled_matrix(self):
        size = HGSS_US_HEADER_OFFSET + 540 * MAP_HEADER_SIZE
        arm9 = bytearray(size)
        source = HGSS_US_HEADER_OFFSET + self.fixture["header_template"] * MAP_HEADER_SIZE
        arm9[source:source + MAP_HEADER_SIZE] = bytes(range(MAP_HEADER_SIZE))
        headers = {
            name: build_map_header(self.fixture, bytes(arm9), name)
            for name in STAGE3B_CELL_ORDER
        }
        validate_stage3b_cross_references(self.fixture, build_matrix(self.fixture), headers)
        self.assertTrue(all(struct.unpack_from("<H", header, 4)[0] == 1 for header in headers.values()))

        corrupted = dict(headers)
        bad = bytearray(corrupted["se"])
        struct.pack_into("<H", bad, 4, 2)
        corrupted["se"] = bytes(bad)
        with self.assertRaisesRegex(WorldBuildError, "wrong matrix"):
            validate_stage3b_cross_references(self.fixture, build_matrix(self.fixture), corrupted)

    def test_validation_rejects_inconsistent_multimap_relationships(self):
        mutations = []

        wrong_dimensions = copy.deepcopy(self.fixture)
        wrong_dimensions["world"]["matrix"]["width"] = 3
        mutations.append(wrong_dimensions)

        non_ascii_name = copy.deepcopy(self.fixture)
        non_ascii_name["world"]["matrix"]["name"] = "stage3b-é"
        mutations.append(non_ascii_name)

        duplicate_member = copy.deepcopy(self.fixture)
        duplicate_member["maps"]["ne"]["map_member"] = 633
        mutations.append(duplicate_member)

        invalid_header = copy.deepcopy(self.fixture)
        invalid_header["maps"]["ne"]["map_header"] = 267
        mutations.append(invalid_header)

        missing_map = copy.deepcopy(self.fixture)
        del missing_map["maps"]["se"]
        mutations.append(missing_map)

        wrong_cell = copy.deepcopy(self.fixture)
        wrong_cell["maps"]["sw"]["cell"] = {"row": 0, "column": 1}
        mutations.append(wrong_cell)

        exterior_opening = copy.deepcopy(self.fixture)
        exterior_opening["maps"]["nw"]["edge_openings"]["north"] = [16]
        mutations.append(exterior_opening)

        nonreciprocal = copy.deepcopy(self.fixture)
        nonreciprocal["maps"]["ne"]["edge_openings"]["west"] = [15]
        mutations.append(nonreciprocal)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(WorldBuildError):
                    validate_fixture(mutation)


if __name__ == "__main__":
    unittest.main()
