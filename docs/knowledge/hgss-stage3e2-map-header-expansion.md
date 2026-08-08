# HGSS Stage 3E2 map-header expansion

## Finding

US HeartGold map headers can be expanded sustainably with a hybrid constant-time
lookup. IDs 0--539 continue to address the untouched retail table; project IDs
start at 540 and index a build-generated resident table. The Stage 3E2 proof
generated and exercised IDs 540 and 541.

Confidence is **high for normal field gameplay and the exact two-entry tested
window**. This does not make all `u16` IDs production-safe or add project maps
to optional vanilla UI destination lists.

## Revision and retail layout

- game code: `IPKE`
- supported ROM SHA-256:
  `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`
- ARM9 SHA-256:
  `5eeaa2dcabfb66b4ff5d151687cff2c9214de9e272ba7afdae7a01d57cf319af`
- pret/pokeheartgold evidence revision:
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`
- retail RAM base: `0x020F6BE0`
- decompressed ARM9 file offset: `0xF6BE0`
- retail count: 540
- entry size: 24 bytes
- retail table SHA-256:
  `5600bae7c93612a2cb7f96fe4b8e3885657e9fa1a656a7cdb3df8ea9e786ab5a`

`pret/pokeheartgold/src/map_header.c` includes the compile-time
`data/map_headers.h` array. `MapNumberBoundsCheck` compares against
`NELEMS(sMapHeaders)`, then each direct accessor computes an address in that
array. Local ARM9 disassembly confirmed the bound 540 and table base above.

## Header record

`pret/pokeheartgold/include/map_header.h` defines the 24-byte record:

| Offset | Width | Meaning used by Stage 3E2 |
|---:|---:|---|
| 0 | 1 | wild encounter bank (`0xFF` means none) |
| 1 | 1 | area-data bank |
| 2 | 2 | move-model bank (4 bits), world X/Y (6 bits each) |
| 4 | 2 | matrix member |
| 6 | 2 | local script member |
| 8 | 2 | script-header member |
| 10 | 2 | message/text member |
| 12 | 2 | day music |
| 14 | 2 | night music |
| 16 | 2 | event member |
| 18 | 2 | map section, area icon, mom-call parameter |
| 20 | 4 | region/weather/type/camera/follow/battle BG and capability flags |

The schema-7 compiler writes complete records from canonical fields. It does
not clone or patch a retail header entry.

## Accessor architecture

Every table-reading public accessor is redirected to project-owned code in
resident HG-Engine space. The selector is:

```text
if id < 540:
    return retail_table[id]
if id - 540 < project_count:
    return project_table[id - 540]
return retail_table[MAP_NOTHING]
```

All branches are constant-time. There is no per-lookup archive I/O and no heap
lifetime dependency. The generated table contains only project-authored
records, so retail header bytes are neither copied into tracked source nor
redistributed.

The 27 hooked entry points are the accessors for area data, move model,
matrix, message, script, script header, day/night music, wild encounters,
events, map section, area icon, mom call, region, weather, camera, battle BG,
escape, fly, bike, outgoing/incoming calls, radio, map type, follow mode, and
world-map coordinates. Derived helpers call these public functions and need no
separate table hook.

HG-Engine's register-3 hook form writes an eight-byte Thumb trampoline:
`00 4B 18 47 <target|1>`. Binary inspection after the final build found all 27
trampolines at their expected addresses and targeting their matching
`ExpandedMapHeader_*` symbols.

## Generated table and registry

`world/registry.json` distinguishes:

- `VANILLA_OWNED`: retail IDs 0--539;
- `CONTROLLED_REPLACEMENT`: earlier proof-only retail slots;
- `HEADER_EXPANSION_PROVEN`: the revision-locked addressable window 540--541;
- `PROJECT_HEADER`: persistent project ownership within that window;
- `UNKNOWN`: everything beyond the tested window.

`allocate_project_header` verifies the ROM revision, selects only the next
contiguous expanded ID, persists ownership, and never renumbers existing
symbols. Pins below 540, gaps, collisions, exhaustion, or an unsupported ROM
revision fail.

The generated two-entry table is 48 bytes with SHA-256:

`0a518ef966537e7a7e503c47e57a6313dad986767a8f3ecd31838a4e79c176fd`

## Runtime evidence

The schema-7 world used matrix grid `[540, 541]`. Live `Location.mapId`
reported 540, ordinary walking crossed the native member edge, and then
reported 541. The selected project header changed events/scripts/text from
491/965/967/854 to 492/966/968/855. Runtime instrumentation counted 295
project lookups and zero invalid lookups in the final run.

The controlled-start field script performed a normal warp into header 540.
The east NPC path performed a normal save and then a script warp out of header
541 to header 540. After an emulator reset, Continue loaded the persisted
header 541 and its east resources. The field remained stable for 600 further
frames.

A test-only reset guard sees the saved east marker and suppresses re-queuing
the bootstrap warp. It does not alter the saved location or load a map; the
normal Continue path supplies the persisted header 541. No emulator savestate
is used for this assertion.

## Reproduction

```bash
.venv/bin/python -m tools.pokeagent registry validate --json
.venv/bin/python -m tools.pokeagent map determinism \
  --fixture fixtures/stage3e2_header_expansion_world.json --json
make stage3e2-header-expansion-proof -j16
.venv/bin/python -m tools.pokeagent map test \
  --fixture fixtures/stage3e2_header_expansion_world.json --timeout 360 --json
```

Ignored evidence is under `build/stage3e2/`.

## Boundaries

Confirmed by source, bytes, and runtime:

- complete header generation for 540/541;
- constant-time retail/project selection;
- native transition, field scripts/events/text, normal warp in/out, and normal
  save/reload with full project IDs;
- unchanged retail table and valid 27-accessor patching.

Confirmed by source/bytes only:

- the invalid selector branch returns retail header 0 and increments a test
  counter;
- `u16`-based serialized references can encode values through 65535.

Unknown or deliberately unsupported:

- safe allocation beyond ID 541 without extending the tested window;
- automatic Town Map/Fly destination-list authoring;
- behavior of every story/minigame-specific hardcoded map comparison;
- other ROM regions or revisions.
