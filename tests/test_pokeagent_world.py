from __future__ import annotations

import struct
import unittest

from tools.pokeagent.world import (
    HGSS_US_HEADER_OFFSET,
    MAP_HEADER_SIZE,
    build_bdhc,
    build_event,
    build_flat_display_list,
    build_map_header,
    build_matrix,
    build_per,
    load_fixture,
    sha256_bytes,
    split_hgss_map_member,
)


class Stage2FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture()

    def test_fixture_uses_bounded_verified_slots(self) -> None:
        self.assertEqual(self.fixture["dimensions"], {"width": 32, "height": 32})
        self.assertEqual(self.fixture["slots"]["matrix"], 1)
        self.assertEqual(self.fixture["slots"]["map_member"], 633)
        self.assertEqual(self.fixture["slots"]["start_script"], 3)
        self.assertEqual(len(self.fixture["warps"]), 2)

    def test_per_is_two_interleaved_32_by_32_layers(self) -> None:
        per = build_per(self.fixture)
        self.assertEqual(len(per), 2048)

        def tile(x: int, z: int) -> tuple[int, int]:
            offset = (z * 32 + x) * 2
            return per[offset], per[offset + 1]

        self.assertEqual(tile(16, 16), (0, 0))
        self.assertEqual(tile(17, 16), (0, 0x80))
        self.assertEqual(tile(16, 18), (101, 0))
        self.assertEqual(tile(16, 19), (0, 0x80))
        self.assertEqual(tile(0, 16), (0, 0x80))
        self.assertEqual(tile(31, 31), (0, 0x80))

    def test_map_member_physically_places_per_at_runtime_offset_0x14(self) -> None:
        per = bytes(range(16))
        bld = b"BLD"
        bgs = b"\x12\x34\x08\x00sound"
        model = b"BMD0model"
        bdhc = b"BDHCdata"
        header = struct.pack("<4I", len(per), len(bld), len(model), len(bdhc))
        member = header + bgs[:4] + per + bld + bgs[4:] + model + bdhc

        self.assertEqual(member[0x14:0x14 + len(per)], per)
        self.assertEqual(
            split_hgss_map_member(member),
            {"bgs": bgs, "per": per, "bld": bld, "nsbmd": model, "bdhc": bdhc},
        )

    def test_bdhc_is_one_flat_plate(self) -> None:
        bdhc = build_bdhc(self.fixture)
        self.assertEqual(bdhc[:4], b"BDHC")
        self.assertEqual(struct.unpack_from("<6H", bdhc, 4), (2, 1, 1, 1, 1, 1))
        self.assertEqual(struct.unpack_from("<4h", bdhc, 16), (0, -16, 0, -16))
        self.assertEqual(struct.unpack_from("<4h", bdhc, 24), (0, 16, 0, 16))
        self.assertEqual(struct.unpack_from("<3i", bdhc, 32), (0, 4096, 0))
        self.assertEqual(len(bdhc), 66)
        self.assertEqual(sha256_bytes(bdhc), "07584c4215ceed2216ba6928d51273b36fa3345815e076390ed5e8ca340980e1")

    def test_matrix_is_one_by_one_with_all_sections(self) -> None:
        matrix = build_matrix(self.fixture)
        width, height, has_headers, has_altitudes, name_length = matrix[:5]
        self.assertEqual((width, height, has_headers, has_altitudes), (1, 1, 1, 1))
        offset = 5 + name_length
        self.assertEqual(struct.unpack_from("<H", matrix, offset)[0], self.fixture["slots"]["map_header"])
        self.assertEqual(matrix[offset + 2], 0)
        self.assertEqual(struct.unpack_from("<H", matrix, offset + 3)[0], self.fixture["slots"]["map_member"])

    def test_event_contains_one_npc_and_reciprocal_warps(self) -> None:
        event = build_event(self.fixture)
        self.assertEqual(struct.unpack_from("<I", event, 0)[0], 0)
        self.assertEqual(struct.unpack_from("<I", event, 4)[0], 1)
        npc = struct.unpack_from("<6Hh3HhhHHi", event, 8)
        self.assertEqual((npc[0], npc[1], npc[5], npc[12], npc[13]), (0, 146, 1, 16, 14))
        warp_count_offset = 8 + 32
        self.assertEqual(struct.unpack_from("<I", event, warp_count_offset)[0], 2)
        warp0 = struct.unpack_from("<4HI", event, warp_count_offset + 4)
        warp1 = struct.unpack_from("<4HI", event, warp_count_offset + 16)
        self.assertEqual(warp0[:4], (16, 18, 267, 1))
        self.assertEqual(warp1[:4], (4, 4, 267, 0))
        self.assertEqual(struct.unpack_from("<I", event, len(event) - 4)[0], 0)

    def test_map_header_patches_only_the_declared_references(self) -> None:
        size = HGSS_US_HEADER_OFFSET + (268 * MAP_HEADER_SIZE)
        arm9 = bytearray(size)
        template = self.fixture["header_template"]
        source = HGSS_US_HEADER_OFFSET + template * MAP_HEADER_SIZE
        arm9[source:source + MAP_HEADER_SIZE] = bytes(range(MAP_HEADER_SIZE))
        header = build_map_header(self.fixture, bytes(arm9))
        self.assertEqual(len(header), MAP_HEADER_SIZE)
        self.assertEqual(header[:2], b"\xff\x02")
        self.assertEqual(struct.unpack_from("<4H", header, 4), (1, 842, 399, 542))
        self.assertEqual(struct.unpack_from("<H", header, 16)[0], 57)

    def test_flat_nsbmd_display_list_is_bounded_and_has_four_vertices(self) -> None:
        display_list = build_flat_display_list()
        self.assertEqual(len(display_list), 100)
        self.assertEqual(display_list[:4], b"\x40\0\0\0")
        self.assertEqual(display_list[-4:], b"\x41\0\0\0")
        self.assertEqual(display_list.count(b"\x23\0\0\0"), 4)


if __name__ == "__main__":
    unittest.main()
