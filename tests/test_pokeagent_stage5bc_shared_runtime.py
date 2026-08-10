from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.pokeagent.qa import deterministic_plan, load_scenario
from tools.pokeagent.registry import RegistryError, resolve_stage3e1_source
from tools.pokeagent.world import (
    _preserve_common_bank_controlled_start,
    build_event,
    load_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "fixtures/stage5bc_victini_shared_world.json"
SCENARIOS = (
    "stage5bc_victini_trainer_runtime.json",
    "stage5bc_victini_wild_seen.json",
    "stage5bc_victini_wild_capture.json",
    "stage5bc_victini_icon_ui.json",
    "stage5bc_victini_pc_icon_ui.json",
    "stage5bc_victini_follower_transition.json",
)


class Stage5BCSharedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        cls.fixture = load_fixture(SOURCE_PATH)

    def test_world_reuses_proven_headers_and_native_connection(self) -> None:
        self.assertEqual(
            [self.fixture["maps"][name]["map_header"] for name in ("west", "east")],
            [540, 541],
        )
        self.assertEqual(self.fixture["world"]["matrix"]["cells"], ["west", "east"])
        self.assertEqual(self.fixture["maps"]["west"]["npc"]["trainer_id"], 737)
        self.assertEqual(self.fixture["header_profile"]["wild_encounter_bank"], 142)
        self.assertEqual(
            self.fixture["terrain"]["permission_regions"][0],
            {"map": "east", "x0": 8, "z0": 8, "x1": 24, "z1": 24, "permission_type": 3},
        )

    def test_pc_route_is_a_bounded_access_npc_warp_to_retail_pc(self) -> None:
        access_npc = self.fixture["maps"]["west"]["access_npc"]
        self.assertEqual(
            access_npc,
            {
                "kind": "pokecenter_access_warp",
                "local_id": 1,
                "graphics_id": 146,
                "movement_type": 0,
                "local_x": 15,
                "local_z": 16,
                "direction": 3,
                "script_index": 1,
                "destination_header": 69,
                "destination_x": 11,
                "destination_z": 13,
                "destination_direction": 0,
            },
        )
        event = build_event(self.fixture, "west")
        self.assertEqual(struct.unpack_from("<I", event, 0)[0], 0)
        self.assertEqual(struct.unpack_from("<I", event, 4)[0], 2)
        self.assertEqual(struct.unpack_from("<6Hh3HhhHHi", event, 40)[0:7], (1, 146, 0, 0, 0, 1, 3))
        self.assertEqual(struct.unpack_from("<6Hh3HhhHHi", event, 40)[12:14], (15, 16))

    def test_common_script_preservation_is_explicit_and_bounded(self) -> None:
        self.assertTrue(self.fixture["resources"]["preserve_common_script_bank"])
        self.assertEqual(self.fixture["resources"]["battle_test_message_count"], 121)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "build/a012/2_003"
            template.parent.mkdir(parents=True)
            original = bytearray(range(128))
            struct.pack_into("<I", original, 0, 4)  # Script 0 starts at byte 8.
            template.write_bytes(original)
            output = root / "controlled.bin"
            _preserve_common_bank_controlled_start(self.fixture, output, root)
            generated = output.read_bytes()
        self.assertEqual(len(generated), len(original))
        self.assertEqual(generated[:8], original[:8])
        self.assertEqual(generated[22:], original[22:])
        self.assertEqual(
            generated[8:22],
            struct.pack("<7H", 176, 540, 0xFFFF, 16, 16, 3, 2),
        )

    def test_normal_stage4a_does_not_enable_common_bank_preservation(self) -> None:
        stage4a = load_fixture(ROOT / "fixtures/stage3e2_header_expansion_world.json")
        self.assertFalse(stage4a["resources"]["preserve_common_script_bank"])
        self.assertFalse(any("access_npc" in spec for spec in stage4a["maps"].values()))

    def test_symbolic_policy_validation_fails_closed(self) -> None:
        malformed = copy.deepcopy(self.source)
        malformed["resources"]["preserve_common_script_bank"] = "yes"
        with self.assertRaisesRegex(RegistryError, "preserve_common_script_bank must be boolean"):
            resolve_stage3e1_source(malformed, ROOT / "world/registry.json")
        malformed = copy.deepcopy(self.source)
        del malformed["maps"]["stage3e2_west"]["access_npc"]["destination_header"]
        with self.assertRaisesRegex(RegistryError, "malformed Pokecenter access NPC"):
            resolve_stage3e1_source(malformed, ROOT / "world/registry.json")

    def test_proof_tables_are_opt_in_and_encode_victini(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        trainers = (ROOT / "data/Trainers.c").read_text(encoding="utf-8")
        encounters = (ROOT / "data/Encounters.c").read_text(encoding="utf-8")
        self.assertIn("ifeq ($(STAGE5BC_RUNTIME_PROOF),Y)", makefile)
        self.assertIn("#ifdef STAGE5BC_RUNTIME_PROOF", encounters)
        self.assertIn("#ifndef STAGE5BC_RUNTIME_PROOF", trainers)
        self.assertIn("[737]", trainers)
        self.assertIn(".species = SPECIES_VICTINI", trainers)
        self.assertIn("[ENCDATA_UNUSED_142]", encounters)
        self.assertGreaterEqual(encounters.count("SPECIES_VICTINI"), 36)

    def test_battle_message_padding_policy_is_bounded(self) -> None:
        malformed = copy.deepcopy(self.source)
        malformed["resources"]["battle_test_message_count"] = 257
        with self.assertRaisesRegex(RegistryError, "battle_test_message_count"):
            resolve_stage3e1_source(malformed, ROOT / "world/registry.json")

    def test_shared_runtime_scenarios_have_stable_semantic_plans(self) -> None:
        plans: dict[str, str] = {}
        captures: set[str] = set()
        for name in SCENARIOS:
            scenario = load_scenario(ROOT / "qa/scenarios" / name, ROOT)
            first = deterministic_plan(scenario)
            second = deterministic_plan(json.loads(json.dumps(scenario)))
            self.assertEqual(first, second)
            plans[scenario["id"]] = first["sha256"]
            captures.update(
                step["name"] for step in scenario["steps"] if step.get("action") == "capture"
            )
        self.assertEqual(len(plans), len(SCENARIOS))
        for required in (
            "victini_party_icon",
            "victini_pc_icon",
            "victini_trainer_front",
            "victini_wild_front",
            "victini_follower_before_transition",
            "victini_follower_after_transition",
            "victini_follower_after_transition_movement",
        ):
            self.assertIn(required, captures)

    def test_qa_extensions_are_generic_and_bounded(self) -> None:
        source = (ROOT / "tools/pokeagent/qa.py").read_text(encoding="utf-8")
        adapter = (ROOT / "tools/pokeagent/qa_emulator.py").read_text(encoding="utf-8")
        for name in ("wait_memory", "memory_nonzero", "touch"):
            self.assertIn(name, source)
            self.assertIn(name, adapter)


if __name__ == "__main__":
    unittest.main()
