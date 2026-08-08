# HGSS Stage 2 World Format Findings

Recorded: 2026-08-07

## Finding

The Stage 2 proof can generate the required HGSS world records without an editor. The project-owned implementation is deliberately limited to the proof fixture and replaces existing NARC members rather than expanding global tables.

The US HeartGold map member physical order is:

```text
u32 PER length, BLD length, NSBMD length, BDHC length
BGS four-byte header
PER
BLD
remaining BGS payload
NSBMD
BDHC
```

This is easy to misread as `header + complete BGS + PER + BLD + NSBMD + BDHC`. That logical presentation round-trips unchanged files in some editors, but it writes edited PER bytes to the wrong runtime location. HeartGold reads the 2,048-byte terrain attribute table at fixed member offset `0x14`.

For a 32 x 32 member, PER is 1,024 row-major `(Z, then X)` records. Each record is `(u8 metatile_behavior, u8 collision)`. Collision `0` is walkable and `0x80` blocks ordinary walking in the tested fixture. A south entrance warp uses behavior `101`; the tile immediately beyond it must be blocked so the held south input is classified as an entrance transition. Arrival at the reciprocal south entrance anchor `(4,4)` places the player outside it at `(4,5)`.

Other implemented subsets:

- BDHC: one horizontal plate, two points, one normal, one constant, one plate, and one access-list entry; 66 bytes.
- Matrix: width, height, header-grid flag, altitude-grid flag, length-prefixed name, one `u16` header, one `u8` altitude, and one `u16` map member.
- Map header: a 24-byte US table entry at ARM9 offset `0xF6BE0 + id * 24`; Stage 2 patches only controlled header 267.
- Event: counted arrays of 20-byte background, 32-byte object, 12-byte warp, and 16-byte coordinate records. The proof emits one object and two warps.
- Script/text: HG-Engine armips script macros and `msgenc`; local object script IDs are one-based, so the first local script is ID 1. A fixed `msgenc` key is required because its default derives from the output path.
- Common start script: global script 2000 resolves to common script NARC member 3, entry 0 in HGSS. The test-only hook queues this script after normal new-game initialization.

## Evidence

- `tools/pokeagent/world.py` and `tests/test_pokeagent_world.py`.
- `pret/pokeheartgold` revision `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`: `src/terrain_attributes.c`, `src/map_events.c`, `src/field/field_control.c`, `include/map_events_internal.h`, matrix parser, and metatile behavior constants.
- Pokemon DS Map Studio revision `ac30b653e5b090ce116278ed6ba9758fff956673`: map container, PER, and BDHC serialization.
- DSPRE revision `d86737dfccaec7a603a6f27474180a49945158a6`: matrix, map header, event, and map serializers.
- Uxie revision `8cc3bc57e2663a87bb5e2bbdbb699311adb4cbd2`: HGSS event binary structs and JSON mappings.
- Headless DeSmuME evidence in ignored `build/stage2/emulator/report.json`: the engine loaded event counts `(0,1,2,0)`, live warp structs matched the fixture, collision blocked `(17,16)`, and the warp reached header 267/anchor 1 at `(4,5)`.

## Confidence

- Physical map-member ordering, PER offset, collision, object/event layout, script ID, and warp semantics: **confirmed by source inspection and emulator behavior**.
- Matrix, header, BDHC subset, and generated archive placement: **confirmed by source inspection, byte-level tests, successful ROM build, and map load**.
- Applicability beyond the single fixed Stage 2 map: **not established**.

## Reproduction

```bash
.venv/bin/python -m unittest tests.test_pokeagent_world -v
make stage2-proof
.venv/bin/python -m tools.pokeagent map test --json
.venv/bin/python -m tools.pokeagent map determinism --json
```

All ROM-derived inputs and generated binaries remain local/ignored.

## Remaining unknowns

- Multi-map matrices, varied heights, multiple BDHC plates, BLD/buildings, sound plates, and other warp types are outside this proof.
- Header-table offsets and the selected template/member hashes are coupled to the supported US HeartGold revision.
- The test slots for event/script/text are controlled replacements during the Stage 2 build, but are not a production allocation scheme.
