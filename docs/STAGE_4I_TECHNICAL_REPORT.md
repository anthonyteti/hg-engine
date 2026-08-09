# Stage 4I technical report: project-owned model geometry capacity

## Verdict

`STAGE_4I_MODEL_CAPACITY_PASSED`

A valid project-authored 56-triangle gatehouse now compiles to a 3,820-byte
Nitro display list that demonstrably fails the inherited 1,068-byte shape-6
allocation, then succeeds through an opt-in project-owned MDL0-tail relocation.
The rebuilt model preserves all 17 other display-list offsets, lengths, and
payload hashes, builds through HG-Engine, renders correctly in HeartGold, and
passes independent binary parsing, collision/gameplay, visual, stress,
mutation, and clean-root determinism gates.

Capacity classification:

```text
FORMAT_CAPACITY = u32 relative display-list offset and u32 byte length
TESTED_PROJECT_CAPACITY = 4,096 bytes per relocated display list
UNKNOWN_HARDWARE_LIMIT = unknown beyond the bounded 4 KiB runtime proof
```

## Stage 4H checkpoint and preserved rejection

Stage 4H was committed as `3f716df08 Add Stage 4H generated asset intake
gate`, full SHA `3f716df08db608d0bfe0d36d2f1d1e0855fc1132`, and pushed before
Stage 4I began. Local `HEAD`, `origin/main`, and remote main matched and the
working tree was clean. No ROM, build output, rejected temporary candidate,
save, screenshot, credential, cache, or extracted retail resource entered the
commit.

Stage 4H remains exactly:

```text
STAGE_4H_GENERATED_ASSET_REJECTED
REJECTED_UNSUPPORTED_STRUCTURE
```

Its immutable TripoSR GLB is still outside `assets/catalog.json`; intake still
rejects its hierarchy, missing material/normals/UV0, unexpected vertex colors,
and 453,164-byte conditional projection. Stage 4I neither edits nor compiles it.

## MDL0/NSBMD architecture discovered

The hash-locked template member contains one 16,604-byte BMD0 v2 container,
one MDL0 section, one model, one node, 23 materials, 18 shapes, and no inverse
bind payload. The model header stores relative offsets for SBC, materials,
shapes, and its inverse-bind/end marker. Each 16-byte shape record contains a
relative u32 command offset and u32 command length.

The original shape command ranges are contiguous from absolute offset 3,512 to
the model/container end at 16,604. Shape 6 is:

```text
record offset        3,320
command offset      10,048
command length       1,068
command end         11,116
```

There is no unclaimed tail gap. The 1,068-byte limit is therefore inherited
layout capacity, not the width of the shape record. Local Apicula 0BSD parsing
code independently confirms the piece-record size/relative-offset/length
semantics. Local `pret/pokeheartgold` source reaches field models through
Nitro's model-set/model-index APIs rather than hardcoded template command
addresses. `ReadMModelFromNarcInternal` calls `NARC_GetMemberSize`, allocates
that exact dynamic member size on heap 4, and reads the whole member; the NARC
implementation obtains the size from BTAF start/end offsets. The final runtime
proof establishes that HeartGold accepts the lengthened bounded model.

## Relocation/rebuild and parser architecture

`tools/pokeagent/nsbmd_model.py` owns the bounded layout step:

```text
typed mesh IR
  -> existing Nitro command encoder
  -> legacy hash-locked transform with target placeholder
  -> append project list to four-byte-aligned model tail
  -> redirect target shape record
  -> update BMD0/MDL0/model/end lengths and model counters
  -> independently reopen the finished model
```

The geometry encoder knows no file offsets. `world.py` invokes relocation only
when an asset manifest declares schema 7 and
`project_relocated_display_list`; legacy schemas keep the old path. The writer
does not rebuild dictionaries, materials, nodes, SBC, or textures.

The independent parser reopens the BMD0/MDL0/model/shape dictionaries and
validates container sizes, protected metadata, shape records, alignment,
non-overlapping in-bounds ranges, the project GX command subset, primitive
termination/counts, and model counters. Corruption tests cover wrong container
size, outside ranges, misalignment, overlaps, command truncation, and invalid
counters.

## Project budget policy

Manifest schema 7 adds the explicit opt-in policy:

```json
"geometry_storage": {
  "policy": "project_relocated_display_list",
  "max_bytes": 4096
}
```

The compiler hard-caps authored values at the runtime-tested constant 4,096.
It refuses zero, negative, boolean, larger, or under-required capacities.
There is no silent truncation or fallback. This is not a claim that arbitrary
u32-sized lists, multiple 4 KiB shapes, or aggregate large maps are safe.

Generated Armips script sources were also made clean-root-stable by hashing a
canonical output token and substituting the actual path only in a deleted
invocation copy. Script binaries are unchanged; this removes output-directory
paths from deterministic semantic artifacts.

## Canonical proof asset and geometry

The tracked CC0 source is
`assets/source/stage4i_expanded_gatehouse.glb`:

- size: 6,740 bytes;
- SHA-256:
  `e0e70a52f7308d9b994770a5ec42e2e5848311616655bb3588f317ba8d109399`;
- one GLB 2.0 scene/node/mesh/primitive/material;
- identity node, indexed independent triangles, authored POSITION/NORMAL/UV0;
- no image, transform, hierarchy, animation, skin, morph, repair, or
  simplification requirement;
- source IR: 43 positions, 12 normals, 4 UVs, 56 faces;
- emitted: 56 triangles, zero quads, 168 vertices;
- bounds: approximately `[-2.3, 0, -1.95]` to `[2.3, 6, 1.95]` tiles;
- geometry: main body, pitched/faceted roof, projecting doorway, two
  buttresses, and a triangular pediment.

These are meaningful silhouette/details rather than redundant coplanar
tessellation. Stage 4G simplification is neither enabled nor required.

Normalized semantic SHA-256 is
`0a40ce3c8c84a90b641b29f0d805e4bd20153872b4960aa894052e6a4609c858`.
The one TRIANGLES block is 3,820 bytes, SHA-256
`051edf1981f4e064732e016be0d121b48b9651c09e35d2c80fb45ceabf0b106d`.

## Negative old path and expanded binary result

The exact canonical list compiled through the old transformer fails before
mutation:

```text
shape = 6
required bytes = 3,820
inherited capacity = 1,068
error = display_list_overflow
```

The opt-in path succeeds at 93.262% of the 4,096-byte ceiling:

| Field | Before | After | Delta |
|---|---:|---:|---:|
| BMD0/NSBMD | 16,604 | 20,424 | +3,820 |
| MDL0 | 16,584 | 20,404 | +3,820 |
| model | 16,536 | 20,356 | +3,820 |
| shape-6 command offset | 10,048 | 16,604 | relocated |
| shape-6 command length | 1,068 allocation | 3,820 commands | +2,752 vs inherited |

No alignment bytes are needed. The target record alone changes. Every
non-target shape retains its absolute command offset, allocation length, and
payload hash. The final model counters independently reparse as 236 emitted
vertices, 73 polygons, 56 triangles, and 17 invisible/ground quads.

Final hashes:

| Artifact | SHA-256 |
|---|---|
| transformed NSBMD | `8105ceb9c7450b2308e6b8ef89631ba4a72ba2111ea32ef4d91b9715ac0f8cc1` |
| map member 633 | `834ed833ed80022695a68cc75d08cab28d8fb2b8d7b3f038725c42333ea0f818` |
| PER | `429374e5ea9839420d7738289a302965574437a39db115140f91c06c0cf9178a` |
| BDHC | `07584c4215ceed2216ba6928d51273b36fa3345815e076390ed5e8ca340980e1` |
| Stage 4I ROM | `99fcf8041a015688e00513aa7643c4f401fc568ae0fdd44521069fdc6a8e3061` |

The rebuilt land-data NARC member 633 is exactly the generated 22,558-byte map
member. It retains the fixed PER position at map-member offset `0x14`, empty
BLD, BGS ordering, 20,424-byte model, flat runtime-proven BDHC, and ordinary
NARC repacking.

## Texture, material, and collision preservation

The gatehouse reuses material index 17/shape 6 and project texture
`stage4d_stone` from the already-proven PLTT16/BGR555 project area-texture
member. No texture slot, format, palette, material state, area data, or embedded
GLB image is added.

The manifest owns a near-bounds rectangular footprint
`[-2.29, 2.29] x [-1.94, 1.94]`; world rasterization produces the expected
four-by-four blocked tile core while adjacent routes remain open. Collision
SHA-256 is
`4b7617d99801b608fa1f9c9fb3060fcc6c4becfa172136c8136665fb8f9a2f52`.
PER and the visual placement derive from that same symbolic asset placement.

## ROM, runtime, gameplay, and visual QA

`make stage4i-model-capacity-proof` completed from a clean HG-Engine build.
Live QA proved header 538, matrix 1, member 633, height zero, no NPC/warp
substitute, controlled start `(16,23)`, approach to `(16,18)`, a northward
footprint block, complete walk-around to `(16,13)`, open movement to `(11,13)`,
and 600 additional stable frames. All 15 assertions passed through frame 8,887;
the runner remained active, BDHC was ready, and no resource/crash state was
observed. Plan SHA-256 is
`9b30cf9d2aa5bc96f097742ff324f3af9574fbccb67b04a02e432693a838d460`.

Codex inspected both 256 x 384 emulator captures. The front view shows the
project stone gatehouse façade, doorway projection, buttresses, roof tiers, and
player approach. The opposite view shows the complete roof/body silhouette.
The structure is upright, grounded, visibly more detailed than the Stage 4F
tower, and plausibly scaled for the fixed wide camera. No triangle truncation,
holes, missing/inverted faces, exploded vertices, UV corruption, wrong material,
cross-shape geometry, or terrain corruption is visible. The front view touches
the upper screen edge due to its close approach, while the opposite capture
shows the full structure. Screenshot hashes are
`2cd3ebfc89f9595e65e92a9baa0ee0640becfbcecd2df52bad668cc60cae5420`
and
`0ec76c065f98158b66f2b8246c6dd090867192684b03fcf5fd7ff140d6ee109b`;
they are traceability evidence, not brittle correctness oracles.

## Capacity stress and mutation gates

Deterministic independent-triangle layouts were built, relocated, and reopened
at these bounded points:

| Triangles | Bytes | 4 KiB utilization | Result |
|---:|---:|---:|---|
| 15 | 1,032 | 25.195% | parser/model pass |
| 30 | 2,052 | 50.098% | parser/model pass |
| 45 | 3,072 | 75.000% | parser/model pass |
| 56 canonical | 3,820 | 93.262% | parser, ROM, runtime, visual pass |

The canonical artistic proof is also the required near-upper-bound runtime
case. No list above the declared ceiling was attempted.

A temporary source mutation raises the buttress height without changing its
footprint. Source hash changes `e0e70a52...` -> `2aa77f26...`, normalized IR
`0a40ce3c...` -> `109bd510...`, and display list `051edf19...` ->
`63595d01...`. Asset ID, `stage4d_stone` texture/palette, collision hash, and
world IDs remain stable. The canonical GLB is restored/unchanged.

A temporary 3,816-byte project capacity deterministically rejects the
canonical 3,820-byte stream with `project_geometry_capacity_exceeded`, including
asset/shape, required bytes, and configured capacity. It never truncates the
stream.

## Determinism, tests, and regressions

Two explicit independent Stage 4I roots matched all 48 materialized files,
including canonical script-source intermediates, with zero mismatches. The
standard determinism command reports 44 project binary/semantic hashes and
zero mismatches. All 14 Stage 2 through Stage 4I fixtures passed two-root
determinism. The clean-root Stage 4I generation manifest SHA-256 is
`8eb590dc180a47db7e531119a293390caa0fe0d8d2466881bcaeee767eab208c`;
the final installed build manifest, which additionally records installation
hashes, is
`464f54db67a2575ce13d3dc583b32a4d18e21d2ddc95b35325b2c259438cd171`.

The full suite ran 197 tests: 194 passed and three opt-in live/network
integrations skipped as designed. Focused Stage 4I tests cover old overflow,
expanded success, independent parser corruption, 25/50/75/93% layouts,
under-capacity failure, source mutation, symbolic fixture resolution, and the
unchanged Stage 4H rejection. Registry validation passed 12 namespaces and 34
resources. Preflight, QA schema validation, artifact hygiene, and all prior
fixture determinism passed.

Stages 2 through 4G retain their original binary behavior where relocation is
absent; all their unit and deterministic fixture regressions pass. In
particular, Stage 4G still exact-simplifies its 48-triangle dense tower into
the inherited 648-byte list, and Stage 4H's canonical generated candidate still
fails the same immutable intake gate. Historical specialized emulator tests
were not weakened or removed.

DeepSeek was not used. The work was direct inspection of local licensed source,
template bytes, generated layouts, and runtime behavior. Tokens and cost are
zero.

## Evidence classification and limitations

Confirmed by source plus generated bytes/build/runtime/visual QA:

- the bounded shape record and model-tail relocation semantics;
- a 3,820-byte target list under a 4 KiB project ceiling;
- exact non-target shape preservation;
- model counter, map-member, NARC, collision, renderer, and runtime behavior.

Confirmed by source plus parser/unit tests only:

- deterministic layouts at 1,032, 2,052, and 3,072 bytes;
- stable rejection of corrupted layouts and under-required configured limits;
- likely applicability of the same bounded record semantics to other shapes.

Unknown/unsupported:

- the hardware/render-time ceiling beyond 4 KiB;
- aggregate budgets for several relocated shapes or several simultaneous large
  map models;
- relocation in multi-model, inverse-bind, skeletal, animated, or arbitrary
  dictionary/material models;
- display-list relocation beyond the model tail, arbitrary NSBMD generation,
  new materials/textures, QEM/approximate reduction, topology repair,
  hierarchy flattening, normal/UV generation, and production assets.

Stage 4J may proceed only as a separately scoped preprocessing/capacity step.
The most useful next question is likely bounded generated-asset preprocessing
or approximate fidelity-aware reduction, while retaining the strict 4 KiB
runtime capacity and Stage 4H intake gate. Stage 4I does not authorize another
generator attempt or production landmark work.
