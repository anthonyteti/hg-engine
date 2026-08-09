# Stage 4D technical report: scalable project textures and bounded camera scale

## Verdict

`STAGE_4D_SCALABLE_TEXTURES_PASSED`

Three stable project texture/palette identities (ground, wood, stone) now
coexist in one newly appended project-owned area-texture member. Two imported
props bind the wood and stone identities simultaneously, render distinctly in
one generated map, retain manifest-derived collision, and pass deterministic
binary, ROM, gameplay, and visual verification. The bounded camera side result
is `CAMERA_FIXED_ONLY`: a fixed wider/higher preset works, while source proves
that native connection transitions expect equal camera types.

## Stage 4C checkpoint

Stage 4D began only after the intentional Stage 4C compiler, PNG/OBJ, manifests,
fixture, QA, battery isolation, tests, Make integration, and documentation were
staged explicitly and checked. Commit
`cee5dc592 Add Stage 4C project texture and palette pipeline` (full
`cee5dc592bc7ab49bc546cd67191e66f635f4e4e`) was pushed to `main`; local
`HEAD`, `origin/main`, and remote main agreed, and the worktree was clean.
No ROM, generated NARC/model, build output, screenshot, battery state, retail
asset, log, credential, or other unsafe artifact entered the checkpoint.

## Architecture

Stage 4D chose preferred architecture A: one new project-owned area texture
member plus one new project-owned area-data record.

```text
project PNGs + persistent texture catalog
  -> Stage 4C PLTT16/BGR555 compiler
  -> stable project symbols and physical binding allocation
  -> hash-locked TEX0 metadata + zeroed inherited payload regions
  -> generated project BTX0 member 106 in a/0/4/4
  -> generated project area record 106 in a/0/4/2
  -> symbolic header areaDataBank=106
  -> two schema-3 OBJ manifests / two existing model materials
  -> map NSBMD + PER/BDHC
  -> HG-Engine ROM
  -> Stage 4A declarative QA and visual review
```

This avoids modifying retail members 0--105 and copies zero retail texel or
palette bytes into the project payload regions. It retains a hash-verified
local dictionary/layout template because Stage 4D deliberately does not build
general Nitro Patricia dictionaries.

## Catalog and allocation policy

`assets/texture_catalog.json` is a tracked, diff-friendly persistent record.
Project symbols are stable and source manifests never contain physical TEX0
indices. Allocations are explicit contiguous integers; adding an unrelated
allocation at the tail cannot renumber existing records. The compiler maps
each symbol to one unique verified texture slot, palette slot, and pair of
Nitro resource names. Names are 1--15 ASCII identifier bytes and collision-
checked.

The canonical entries are:

| Allocation | Symbol | Texture name/index | Palette name/index | Encoded hashes (texture / palette) |
|---:|---|---|---|---|
| 0 | `stage4d_ground` | `grass01gs` / 21 | `grass01` / 21 | `5dca0b54...` / `ad62ef5a...` |
| 1 | `stage4d_wood` | `road01_r` / 26 | `road01_r` / 26 | `d606dd69...` / `090c279b...` |
| 2 | `stage4d_stone` | `road01` / 25 | `road01` / 25 | `fed37aab...` / `744abd49...` |

These inherited physical names are internal name-binding keys inside a new
project member, not authored identities and not claims that retail slots are
free. The new registry namespaces `area_data_banks` and
`area_texture_members` preserve retail ownership for 0--105 and classify 106
as append-proven/project-appended for the supported ROM revision. World schema
10 resolves `stage4d_project_area_data` and
`stage4d_project_area_texture` symbolically.

## Container and material binding

The bounded writer parses BTX0/TEX0 header/section lengths, resource
dictionaries, 16-byte names, PLTT16 metadata, relative payload offsets,
capacities, bounds, and alignment. It preserves all 37,092 metadata bytes and
dictionary layout, zeroes the complete 32,000-byte texture and 1,520-byte
palette payload regions, writes the three project pairs, and reparses the
result. Overlap, malformed tables, invalid offsets, unsupported formats,
overflow, wrong hashes/revisions, duplicate names/slots, or retail-prefix
allocation fail before build.

The member retains 67 texture and 66 palette entries and has SHA-256
`8dcfd7074afbb6c5c37e03bf57b45e083292c17824cf5d0e4ef6d67e7bc02a9d`.
The new area-data record is `00006a00ffff0101`. Both area archives grow from
106 to 107 members with byte-identical retail prefixes. Their hashes are
`249cb771f4d8b629b37e1f4e2b8a6c46720a7686b578de3aad6839d5f20bec2f`
and `b70995e24989d25a2cd6dc797479eefd636fe4ac4dbf807b6b691f7673449ec2`.
The ROM-contained archives matched the generated files.

No arbitrary material state was introduced. The project ground binds shape 5
/ material 12, the wood shed binds shape 1 / material 18, and the stone
monument binds shape 6 / material 17. All retain the template's render state;
only name-selected project pixels differ. This is the minimum sustainable
multi-binding subset.

## Canonical assets and world

The proof world is `fixtures/stage4d_scalable_textures_world.json`, one flat
32 x 32 symbolic schema-10 fixture using controlled header 538/member 633 and
the two new appended area resources. It places:

- `stage4d_wood_shed` at `(10,16)`, reusing the proven quad shed geometry with
  a brown plank/red-trim project texture;
- `stage4d_stone_monument` at `(22,16)`, a project-authored six-quad tall shell
  with gray masonry and blue trim.

The ground uses its own muted green project texture. Shape utilization is
1,068/2,496 bytes for the 12-quad shed, 540/1,068 for the six-quad monument,
and 100/1,936 for the ground. Each manifest's symbolic texture binding drives
UV/material selection; its rectangular footprint drives PER collision.

The tracked PNGs are project-authored CC0 assets. The wood and stone patterns
were derived deterministically from a generated visual reference sheet and
reduced to deliberate 32 x 32, <=16-color opaque sources; the final tracked
files, not the reference image, are canonical.

## CLI, allocation stability, and mutation

The new command surface is:

```bash
python -m tools.pokeagent texture catalog --json
python -m tools.pokeagent texture catalog --compile --output build/assets/stage4d-catalog --json
```

Its report exposes project symbol, allocation, Nitro names/indices, source and
payload hashes, count, and an allocation semantic hash. A temporary fourth
unrelated catalog record retained allocations and slot/name mappings for all
three canonical entries. Duplicate identities, physical names, allocations,
slot pairs, gaps, wrong append boundary/revision, missing texture/material
bindings, overflow, malformed dictionaries, invalid offsets, and overlapping
payloads have focused failure coverage.

A temporary magenta pixel mutation to the wood PNG changed its source,
texture, and palette hashes. The asset symbolic identity, normalized mesh hash,
display-list geometry, collision hash, and world IDs remained unchanged. The
canonical PNG was never changed.

## Determinism, build, runtime, and visual evidence

Two clean roots matched all 60 Stage 4D binary artifacts with zero mismatches,
including image IRs, texels, palettes, allocation snapshot, project container,
area record, asset IR/display lists, NSBMD, PER, BDHC, map member, registry
snapshot, rebuilt NARCs, and ARM9. The map member SHA-256 is
`8bb1f5ef856494dd81a0e754c7f3b4a856c5940514cfbc14a704999e2ee599d0`.

`make stage4d-texture-scaling-proof` completed through HG-Engine and produced
the ignored `test.nds`. One initial clean parallel build encountered the
existing transient `narcpy.py` empty-output race on an unrelated `pokegra`
archive; the unchanged incremental retry completed successfully. This did not
affect generated Stage 4D artifacts or determinism.

The tracked 30-step Stage 4A scenario has plan SHA-256
`f4f40ffe8fce5558cd9e8b24fa392308ca7ac52d0dcdff5c9b8c879693155b4e`
and passed 17/17 assertions. It confirmed map 538, matrix 1, member 633,
height 0, zero warps, movement to each prop, separate blocked footprints,
valid movement around them, three captures, and stability through frame 9,575
after another 600 frames.

Codex inspected the final 256 x 384 captures. The shed is intact, upright,
grounded, and unmistakably brown/red; the monument is intact, upright,
grounded, and unmistakably gray-blue. UV scale/orientation are coherent,
colors do not cross-bind, the custom ground remains intact, neighboring
terrain is not corrupted, and the fixed wide camera frames the tall monument.
Screenshot SHA-256 values are
`3a075ee5fe2dd9d3b9aed4d9b943238b765a2da8e454778b74b95e9563a41e1c`,
`29924c9ff51d599248850c460792a9a9ba160eb578e2950f0ccea24548ba5f7f`,
and `b188defca97a82a14cad1a7221827230d403758685c3059fec1b1f60d683213d`;
exact screenshot hashes are traceability evidence, not pass criteria. The final
ignored ROM SHA-256 was
`da2902bc98c91bb3c1b40a1c850704cf0077af1d0e439e34a791c3e717daadc7`.

## Camera side proof

HGSS has 17 fixed 36-byte camera presets selected by the six-bit header field.
Preset 4 is materially farther/higher than ordinary preset 0 and successfully
framed the proof world. It required no camera-table patch and remained stable
under movement/collision. The internal result is **`CAMERA_FIXED_ONLY`**.

Source inspection found a hard boundary: the native connection handler in
`field_warp_tasks.c` asserts that current and destination headers have equal
camera types. Therefore no normal-to-wide native adjacency was attempted.
Likewise, no clean existing field-script interpolation path was established;
a smooth pullback would be a separate engine/runtime feature and was deferred.
This bounded result does not claim Gen 5 camera semantics.

## Evidence, licensing, regressions, and limits

Primary/source evidence came from `pret/pokeheartgold` revision
`008257708bd41df5b8c9037e019088ba24df0a87`. Apicula revision
`3d4e91e14045392a49c89e86dab8cb936225588c` is 0BSD and corroborated Nitro
resource structures. DSPRE revision
`d86737dfccaec7a603a6f27474180a49945158a6` supplied behavioral/format evidence
only; no code was copied. Pillow remains MIT-CMU. No proprietary converter,
GUI, or redistributed retail bytes are required.

No DeepSeek call was necessary: local primary source, binary parsers, golden
tests, runtime memory, and visual evidence answered the bounded questions.
Usage was 0 tokens and estimated cost `$0`.

The final full suite ran 138 tests: 136 passed and two opt-in integration gates
skipped as designed. Registry validation passed 12 namespaces / 34 resources;
the virtual-environment preflight passed all command, Python, system, ROM,
git-hygiene, and Docker-context groups. All six tracked declarative QA
scenarios validated with deterministic plans. Clean-root deterministic
regressions passed with zero mismatches for Stage 2 (16 artifacts), Stage 3A
(16), Stage 3B (31), Stage 3C (32), Stage 3D (22), Stage 3E1 (30), Stage 3E2
(32), Stage 4B (24), and Stage 4C (31). Stage 4D itself matched 60 artifacts
and passed its 17/17 live emulator assertions. The existing Stage 2--4C
runtime evidence remains preserved; the new work did not weaken those
specialized assertions.

The proof remains limited to opaque 32 x 32 PLTT16, exact <=16-color
palettes, three verified physical slot pairs, inherited render state and names,
one appended area member/record, quad geometry, rectangular collision, and the
supported US revision. No general dictionary/material writer, other texture
formats/sizes, transparency, arbitrary capacity, triangles, GLB, simplifier,
BLD, image-to-3D, asset kit, landmark art, or production content is claimed.

Stage 4E may proceed only as another bounded asset capability. The highest-
value next gate is triangle ingestion/encoding while preserving this catalog,
container, collision, determinism, and visual-QA boundary. Camera interpolation
should remain a separate later runtime task.
