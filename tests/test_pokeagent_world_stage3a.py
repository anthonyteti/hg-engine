import struct
import unittest
from pathlib import Path

from tools.pokeagent.world import (
    build_bdhc,
    build_event,
    build_height_display_list,
    build_per,
    load_fixture,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "stage3a_height_proof_map.json"


class Stage3AHeightFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture(FIXTURE)

    def test_fixture_is_the_single_bounded_height_profile(self):
        self.assertEqual(self.fixture["schema_version"], 2)
        self.assertEqual(self.fixture["slots"]["map_header"], 538)
        self.assertEqual(self.fixture["dimensions"], {"width": 32, "height": 32})
        self.assertEqual(self.fixture["warps"], [])
        self.assertNotIn("npc", self.fixture)
        self.assertEqual(self.fixture["terrain"]["lower"]["height"], 0)
        self.assertEqual(self.fixture["terrain"]["raised"]["height"], 2)

    def test_display_list_contains_exactly_seven_bounded_quads(self):
        display_list = build_height_display_list()
        self.assertLessEqual(len(display_list), 1068)
        self.assertEqual(display_list[:8], struct.pack("<II", 0x40, 1))
        self.assertEqual(display_list[-4:], struct.pack("<I", 0x41))
        self.assertEqual(display_list.count(bytes((0x21, 0, 0, 0))), 7)
        self.assertEqual(display_list.count(bytes((0x23, 0, 0, 0))), 28)

    def test_bdhc_encodes_lower_ramp_and_raised_plates(self):
        data = build_bdhc(self.fixture)
        self.assertEqual(data[:4], b"BDHC")
        self.assertEqual(struct.unpack_from("<6H", data, 4), (10, 2, 2, 5, 3, 10))
        offset = 16
        points = [struct.unpack_from("<4h", data, offset + i * 8) for i in range(10)]
        offset += 80
        normals = [struct.unpack_from("<3i", data, offset + i * 12) for i in range(2)]
        offset += 24
        constants = [struct.unpack_from("<i", data, offset + i * 4)[0] for i in range(2)]
        offset += 8
        plates = [struct.unpack_from("<4H", data, offset + i * 8) for i in range(5)]
        offset += 40
        stripes = [struct.unpack_from("<4H", data, offset + i * 8) for i in range(3)]
        offset += 24
        access = struct.unpack_from("<10H", data, offset)
        self.assertEqual(points, [
            (0, -16, 0, -16), (0, 0, 0, 16),
            (0, 0, 0, -2), (0, 2, 0, 2),
            (0, 0, 0, -16), (0, 16, 0, -2),
            (0, 2, 0, -2), (0, 16, 0, 2),
            (0, 0, 0, 2), (0, 16, 0, 16),
        ])
        self.assertEqual(normals, [(0, 4096, 0), (-2896, 2896, 0)])
        self.assertEqual(constants, [0, -131072])
        self.assertEqual(plates, [
            (0, 1, 0, 0), (2, 3, 1, 0), (4, 5, 0, 1),
            (6, 7, 0, 1), (8, 9, 0, 1),
        ])
        self.assertEqual(stripes, [
            (0, 0xFFFE, 4, 0), (0, 2, 4, 4), (0, 16, 2, 8),
        ])
        self.assertEqual(access, (0, 1, 2, 3, 0, 1, 3, 4, 0, 4))
        self.assertEqual(len(data), 212)

    def test_per_marks_both_elevations_walkable_and_blocks_the_perimeter(self):
        per = build_per(self.fixture)
        self.assertEqual(len(per), 32 * 32 * 2)

        def collision(x, z):
            return per[(z * 32 + x) * 2 + 1]

        self.assertEqual(collision(14, 12), 0)
        self.assertEqual(collision(18, 16), 0)
        self.assertEqual(collision(16, 12), 0)
        self.assertEqual(collision(17, 12), 0)
        self.assertEqual(collision(16, 16), 0)
        self.assertEqual(collision(17, 16), 0)
        self.assertEqual(collision(0, 16), 128)
        self.assertEqual(collision(31, 16), 128)
        self.assertEqual(collision(16, 0), 128)
        self.assertEqual(collision(16, 31), 128)

    def test_stage3a_event_file_is_empty_and_deterministic(self):
        self.assertEqual(build_event(self.fixture), bytes(16))
        self.assertEqual(
            sha256_bytes(build_bdhc(self.fixture)),
            "438f9232871173f7c686aa35d1930d0620acc7c205dd020c4d2fd68b1481193e",
        )


if __name__ == "__main__":
    unittest.main()
