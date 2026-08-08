# HGSS Stage 3A BDHC Height Findings

Recorded: 2026-08-08

## Finding

HeartGold's normal overworld collision path accepts a small multi-plate BDHC and resolves a 45-degree X-axis transition at runtime. The Stage 3A proof uses five plates: one lower horizontal surface, one ramp, and three non-overlapping regions of the raised horizontal surface. Three Z stripes reduce each position query to the relevant plate IDs.

This finding does **not** generalize BDHC to arbitrary slopes, bridges, stacked floors, or production terrain. It records only the subset confirmed for the fixture in `fixtures/stage3a_height_proof_map.json`.

## Physical structure implemented

All values are little-endian. The file is:

```text
"BDHC"
u16 point_count
u16 normal_count
u16 constant_count
u16 plate_count
u16 stripe_count
u16 total_access_count

point[point_count]       // 4 * s16: zero, X, zero, Z
normal[normal_count]     // 3 * s32: X, Y, Z
constant[constant_count] // s32, Q16.16 plane constant
plate[plate_count]       // 4 * u16: point0, point1, normal, constant
stripe[stripe_count]     // 4 * u16: zero, signed Z end, count, access offset
access[total_access_count] // u16 plate IDs
```

The Stage 3A counts are `(10, 2, 2, 5, 3, 10)`, producing a 212-byte BDHC. The two normals are horizontal `(0, 4096, 0)` and the tested positive-X ramp `(-2896, 2896, 0)`. Constants are `0` and `-131072`, representing horizontal heights 0 and 2.

## Coordinates and plane evaluation

BDHC X/Z coordinates are centered map-tile units. For this 32 x 32 member, the center of tile `(x,z)` is queried as approximately `(x + 0.5 - 16, z + 0.5 - 16)`. Thus the ramp rectangle `(0,-2)` through `(2,2)` covers map tiles X 16-17 and Z 14-17.

The runtime evaluates a candidate plane as:

```text
Y = -(constant + normalX * X + normalZ * Z) / normalY
```

with the engine's fixed-point scaling. A horizontal height `h` therefore uses constant `-h * 65536`. The tested ramp normal produces `Y=X` over its local X range 0 through 2.

Live player state has two useful representations:

- `MapObject.positionVector.y` is FX32/Q16.16 world height: lower `0`, raised `131072` (2.0).
- `MapObject.hCurr` is the same elevation in half-height units (`positionY >> 15`): lower `0`, ramp samples `1` and `3`, raised `4`.

The exact runtime transition observations were:

```text
tile (15,16): hCurr 0, positionY 0
tile (16,16): hCurr 1, positionY 32768
tile (17,16): hCurr 3, positionY 98304
tile (18,16): hCurr 4, positionY 131072
```

## Plates and access lists

A plate's two point references define its inclusive X/Z bounds; its normal and constant references define the plane. The fixture partitions the world as:

1. lower: local `(-16,-16)` through `(0,16)`, height 0;
2. ramp: `(0,-2)` through `(2,2)`, rising from 0 to 2;
3. raised north: `(0,-16)` through `(16,-2)`, height 2;
4. raised corridor after the ramp: `(2,-2)` through `(16,2)`, height 2;
5. raised south: `(0,2)` through `(16,16)`, height 2.

Each stripe stores a signed Z endpoint, a candidate count, and an offset into the concatenated u16 plate-ID array. Runtime first selects the stripe for Z, then iterates that stripe's candidate IDs, checks plate bounds, evaluates eligible planes, and applies its current-height selection rules. The tested access lists are `(0,1,2,3)`, `(0,1,3,4)`, and `(0,4)` for stripe endpoints `-2`, `2`, and `16`. Candidate ordering did not affect this fixture because its tile-center regions do not overlap ambiguously.

## Critical map-load-mode finding

Stage 2 used header 267, `MAP_BATTLE_TOWER_UNUSED_1`. `sub_02052F30` classifies this header as Battle Tower, whose map-load mode sets `useSimpleTerrainCollisions=TRUE`. The corresponding loader leaves the parsed BDHC pointer at zero. This was harmless for the flat Stage 2 proof, which exercised PER collision, but it cannot prove heights.

Stage 3A therefore replaces explicit normal-overworld slot 538, `MAP_UNUSED`. Source inspection found no special load-mode case for 538, and live memory confirmed one loaded map slot with `ready=1`, three stripes, and non-null pointers for all six BDHC sections. This is why Stage 3A must not reuse header 267.

## PER synchronization

The proven HGSS map-member layout remains unchanged, including PER at physical offset `0x14`. PER blocks the perimeter and marks the lower surface, ramp tiles, and raised surface walkable. It deliberately does not mark the ledge columns impassable, because X 16-17 are valid raised-top tiles when approached from above. BDHC supplies the decisive height-aware ledge: approaching from lower terrain stops at X 15; approaching from the raised top reaches X 16 but cannot descend to X 15. The only lower-to-raised path observed is the ramp corridor.

## Evidence

- Project implementation and golden tests: `tools/pokeagent/world.py`, `tools/pokeagent/world_emulator.py`, `tests/test_pokeagent_world_stage3a.py`.
- Pokemon DS Map Studio revision `ac30b653e5b090ce116278ed6ba9758fff956673`: `BdhcWriterHGSS.java`, `BdhcLoaderHGSS.java`, `Plate.java`, and `Stripe.java`.
- `pret/pokeheartgold` revision `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`: `src/field_warp_tasks.c`, `include/constants/maps.h`, `src/data/map_headers.h`, `asm/overlay_01_021FB04C.s`, and `asm/unk_02054648.s`.
- Headless DeSmuME structured evidence: ignored `build/stage3a/emulator/report.json`.
- Golden BDHC SHA-256: `438f9232871173f7c686aa35d1930d0620acc7c205dd020c4d2fd68b1481193e`.

## Confidence

- **Confirmed by source and runtime:** section layout, five-plate parsing, stripe/access use, centered tile coordinates, horizontal constants, tested ramp equation, live height scaling, transition, ledge blocking, return traversal, and the header-267 simple-collision trap.
- **Confirmed by source only:** the runtime's broader candidate/current-height selection branches outside the non-ambiguous fixture.
- **Inferred:** the PDSMS names for some axes describe editor coordinates rather than the engine's field naming; this note uses runtime X/Y/Z semantics consistently.
- **Unknown:** stacked/overlapping floors, bridges, other slope directions/angles, discontinuous stairs, plate-count limits beyond the observed runtime scratch capacity, and behavior at deliberately ambiguous plate boundaries.

## Reproduction

```bash
.venv/bin/python -m unittest tests.test_pokeagent_world_stage3a -v
make stage3a-height-proof -j16
.venv/bin/python -m tools.pokeagent map test --fixture fixtures/stage3a_height_proof_map.json --timeout 240 --json
.venv/bin/python -m tools.pokeagent map determinism --fixture fixtures/stage3a_height_proof_map.json --json
```

ROM-derived inputs, generated binaries, the playable ROM, and screenshots remain local and ignored.
