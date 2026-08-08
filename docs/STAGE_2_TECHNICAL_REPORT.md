# Stage 2: One-Map, Zero-GUI Proof

Date: 2026-08-07
Verdict: **STAGE_2_PROOF_PASSED**

## Answer

Yes. From one tracked JSON fixture, this project deterministically generates and boots one playable custom 32 x 32 HeartGold map without a human map editor. The clean proof builds through HG-Engine, reaches the map through a controlled test-only start, renders newly encoded flat geometry, enforces walkable and blocked terrain, loads one NPC, executes its dialogue script, and follows a native reciprocal warp. Headless DeSmuME captures ignored screenshots and live-memory assertions, then runs a stability window.

The solution is intentionally not a general world authoring system. It proves only the representative Stage 2 fixture.

## Architecture and canonical source

Canonical source is `fixtures/stage2_proof_map.json`, schema version 1. It defines only:

- fixed 32 x 32 dimensions and deterministic replacement slots;
- one hash-locked local NSBMD template and selected shape/material set;
- a flat height, border collision, explicit blocker `(17,16)`, and entrance backing blocker `(16,19)`;
- player start `(16,16)`, one stationary NPC at `(16,14)`, and dialogue;
- reciprocal warp records `(16,18) -> anchor 1` and `(4,4) -> anchor 0`;
- map-header, matrix, map-member, event, script, common-script, script-header, and text references.

The path is:

```text
JSON validation
  -> PER + one-plate BDHC + transformed flat NSBMD
  -> split-layout HGSS map member
  -> 1 x 1 matrix + 24-byte map-header patch + event member
  -> armips NPC/start scripts + msgenc dialogue
  -> replaced NARC members and patched extracted ARM9
  -> HG-Engine Make/armips/ndstool
  -> ignored test.nds
  -> subprocess-bounded py-desmume assertions and screenshots
```

`tools/pokeagent/world.py` owns deterministic generation. `tools/pokeagent/world_emulator.py` owns runtime assertions. `make stage2-proof` performs a clean Stage 2 ROM build. `python -m tools.pokeagent map determinism` generates into two clean directories and compares every binary component, NARC, and patched ARM9.

## Controlled IDs and cross-reference validation

The proof uses header 267, matrix 1, map member 633, event 57, local script 842, common start script 3, script header 399, and text 542. Matrix 1 and map member 633 were verified unused in the supported US ROM; header 267 is a controlled unused header. Event/script/text are controlled Stage 2 replacements and are not presented as globally free production allocations.

Validation rejects changed dimensions, incomplete/negative slot sets, different matrix/member proof slots, missing blockers, blocker overlap with NPC/warps, malformed coordinates, and non-reciprocal destination indices. Runtime reads the live event counts and warp structs back from emulated RAM.

## Implemented binary subsets

| Component | Implemented subset | Reference/evidence | Generated path |
|---|---|---|---|
| NSBMD | Hash-locked local template transform; all display lists replaced, shape 6 becomes a new flat quad | PDSMS, Apicula, EFE corroboration; Nitro headers/dictionaries; emulator render | `build/stage2/generated/components/map_member.bin` |
| HGSS member | Four length words and physically split BGS around PER/BLD | pokeheartgold runtime PER offset; PDSMS/DSPRE serializers | same map member |
| PER | 32 x 32 row-major behavior/collision pairs | pokeheartgold terrain/behavior source; emulator movement | `components/per.bin` |
| BDHC | One zero-height rectangular plate | PDSMS writer; byte-level golden test; runtime map load | `components/bdhc.bin` |
| Matrix | 1 x 1 with header and altitude grids | pokeheartgold parser; DSPRE serializer | `components/matrix.bin` |
| Header | One 24-byte US ARM9 table entry | DSPRE and pokeheartgold definitions; runtime map ID | `components/map_header.bin` |
| Event/NPC/warps | One 32-byte object and two 12-byte reciprocal warps | Uxie binary structs; pokeheartgold runtime structs; live RAM | `components/event.bin` |
| Field scripts | One local NPC entry and common start entry | HG-Engine armips macros; pokeheartgold script-bank mapping | `components/2_842`, `components/2_003` |
| Dialogue | One fixed-key encoded message bank | HG-Engine `msgenc`; visible screenshot and marker | `components/7_542` |

NARC integration replaces exactly the selected members of map `a/0/6/5`, matrix `a/0/4/1`, event `a/0/3/2`, script `a/0/1/2`, and text `a/0/2/7`. Generated archives and source-ROM-derived bytes are ignored.

## NSBMD kill-gate decision

No legally usable open-source general writer sufficient for this proof was found. PDSMS generates IMD then invokes proprietary, absent `g3dcvtr.exe`; Apicula is open/0BSD but read/export oriented; EFE has writer code but no license was found. Importing either GUI or depending silently on `g3dcvtr` was rejected.

The selected solution is the smallest sustainable proof subset: original project code transforms a hash-verified model from the user's local ROM, encodes a new flat quadrilateral display list, emits valid degenerate quads for the remaining shapes, and updates model counts. No proprietary converter is used or required. This proves new geometry and the complete surrounding pipeline, but does not authorize content scaling. Public CI still needs a lawfully supplied supported ROM and must not publish outputs.

Full evidence and constraints are in `docs/knowledge/nsbmd-stage2-model-path.md`.

## External sources and revisions

- Pokemon DS Map Studio `ac30b653e5b090ce116278ed6ba9758fff956673`.
- DSPRE `d86737dfccaec7a603a6f27474180a49945158a6`.
- pret/pokeheartgold `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`.
- Uxie `8cc3bc57e2663a87bb5e2bbdbb699311adb4cbd2`.
- Apicula `3d4e91e14045392a49c89e86dab8cb936225588c` (0BSD).
- Every File Explorer `f9f00d193c9608d71c9a23d9f3ab7e752f4ada2a` (format corroboration only; no license found).

No code from an unlicensed repository, proprietary converter, ROM member, generated NARC, screenshot, save/state, or playable ROM is tracked.

## DeepSeek use and verification

A broad high-effort request exhausted its completion allowance and returned `empty_response`; it contributed no conclusion. One narrow `deepseek-ai/DeepSeek-V4-Flash-0731` review used 336 prompt and 2,408 completion tokens with provider-estimated cost `$0.00046368`. It concluded that unchanged NSBMD recombination would prove only the surrounding pipeline, whereas a byte-transforming implementation could honestly prove the model step.

Codex treated this as advisory, verified the distinction in source and generated bytes, and required transformed display lists plus emulator rendering. Broader cautions were accepted only where separately supported by source/tests.

## Runtime test procedure and evidence

The worker starts with no save-state dependency, advances the title/new-game flow, selects the no-information path and defaults, then waits for the Stage 2-only hook to queue common script 2000. That generated script uses the game's normal warp command to enter header 267 at `(16,16)`.

Assertions cover:

1. header 267 and controlled start coordinates load;
2. live event counts are zero backgrounds, one NPC, two warps, zero coordinate events;
3. live warp structs match both canonical records;
4. right movement into `(17,16)` is blocked;
5. left/right movement across ordinary terrain changes coordinates as expected;
6. the NPC is approached and interacted with;
7. NPC script sets save variable `0x4000` to 42, observed through a test-only marker, and the dialogue screenshot differs from the map screenshot;
8. the engine observes south-entrance behavior 101 and native warp anchor 1;
9. arrival is header 267, warp 1, `(4,5)`, one tile outside destination anchor `(4,4)` per HGSS convention;
10. the ROM remains running on the map for another 600 frames.

Screenshots `map-loaded.png`, `dialogue.png`, and `warp-destination.png`, along with the structured report and log, are written only to ignored `build/stage2/emulator/`.

## Verification record

Final verification commands:

```bash
make stage2-proof -j16
.venv/bin/python -m tools.pokeagent map test --timeout 180 --json
.venv/bin/python -m tools.pokeagent map determinism --json
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m tools.pokeagent preflight --json
git diff --check
```

Final clean build: **PASS**.
Headless emulator assertions: **PASS**.
Unit/integration tests: **PASS**.
Preflight and artifact-safety checks: **PASS**.
Determinism: **PASS**, with no mismatched binary artifacts.

Representative final SHA-256 values (recorded from the ignored determinism report):

- canonical fixture: `aa234a136795cf7da24487f2241bc362554fef744b4072a80ad04550bd4abe22`
- map member: `b8854e62a71ffab395fa66d74c071c20fa18839e41be7cc8efd5c8c816e30fb9`
- PER: `bbebc8dd635dfedb56e532539204d6b245ed71342d60f9a7ea476f92314a3ef6`
- BDHC: `07584c4215ceed2216ba6928d51273b36fa3345815e076390ed5e8ca340980e1`
- matrix: `b214c12162f232c91085099f58a15fb48d0a65739bdcf5ee09f1186ac21c58a6`
- event: `0348aeeba169707589e15574367e0d78fd574592dcffa20e55312bac55922ae5`
- map header: `0c751170f67faf1a55f2936f93c92fe9d4bc5c7eea409a7a94e6cd80758c781a`
- NPC script: `557cd04df92cdb738d6882fdd61baaadb315c3959400ebd3e7d040a4a238ba3b`
- start script: `bde274b515413ad85c21783038ab5b35f0d2f7778ae25335311407b9900d6afc`
- dialogue: `aa3ff507a8308671b60307b71a42f4ccb79339ed782744d3a70b5f3654d4b7cc`

## Constraints and remaining risks

- The NSBMD transformer is template- and shape-capacity-specific. A general open model compiler remains unresolved before content scaling.
- The proof reuses a user-local HeartGold material/texture/area-data set and therefore cannot publish generated artifacts.
- Only flat geometry, one BDHC plate, one matrix cell, and the listed event/script subsets are proven.
- Test header/member allocation is bounded; a production allocator and non-conflicting script/event/text allocation still need design.
- The ARM9 header table offset and template hash are revision-specific.
- Visual evidence is coarse and intentionally not pixel-perfect; correctness relies primarily on live memory plus engine behavior.

These are bounded Stage 2 limitations, not failures of the one-map architecture.

## Foundation recommendation

HeartGold + HG-Engine remains the recommended foundation. The original automation kill gate—headless deterministic map generation and gameplay verification—has passed without a GUI or proprietary converter. Platinum remains a contingency if later requirements exceed the bounded NSBMD path, but current evidence does not justify a pivot.
