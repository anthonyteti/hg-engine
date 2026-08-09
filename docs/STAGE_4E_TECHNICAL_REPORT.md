# Stage 4E technical report: triangle and mixed-mesh ingestion

## Verdict

`STAGE_4E_TRIANGLE_PIPELINE_PASSED`

A tracked project-authored OBJ containing four independent roof triangles and
four wall quads now compiles through one generic typed-face IR and Nitro
display-list encoder, uses the existing scalable project texture container,
retains symbolic placement and rectangular collision, builds through
HG-Engine, and passes declarative gameplay plus front/rear visual inspection.

## Stage 4D checkpoint

Stage 4E began only after the intentional Stage 4D texture-container, catalog,
area-resource, assets, fixture, QA, camera notes, tests, Make integration, and
architecture documentation were staged explicitly and checked. Commit
`dee25a1f7 Add Stage 4D scalable project textures` (full
`dee25a1f7e32b3b563ac5b4c0d59d801943981d2`) was pushed to `main`.
Local `HEAD`, `origin/main`, and remote main agreed and the worktree was clean.
No generated or retail artifact entered the checkpoint.

## Architecture and supported OBJ subset

Stage 4E extends the primitive layer without changing the asset factory:

```text
schema-4 OBJ manifest + project texture symbol
  -> explicit triangle/quad OBJ faces
  -> normalized mesh IR schema 2
  -> winding/normal/UV/range/budget validation
  -> stable consecutive primitive plan
  -> independent triangle + quad Nitro commands
  -> existing shape/material + Stage 4D project texture
  -> symbolic placement + manifest footprint
  -> map NSBMD + PER/BDHC
  -> HG-Engine ROM + Stage 4A QA
```

The parser accepts positive, explicit `v/vt/vn` faces with exactly three or
four corners. It still rejects N-gons, negative/relative indices, absent UVs
or normals, malformed indices, degenerate faces, non-planar quads, normal/
winding mismatch, unsupported materials, non-finite or fixed-point-unsafe
coordinates, and over-budget geometry. Manifest schemas 1--3 remain quad-only;
schema 4 is the explicit triangle capability boundary.

Each IR face records `primitive: triangle|quad`, ordered position/UV/normal
references, and resolved local material/texture identity. Source order is
semantic and deterministic. The compiler does not automatically triangulate,
repair, or reorder topology.

## Nitro encoding, winding, and accounting

Primary Nitro declarations establish `GX_BEGIN_TRIANGLES=0` and
`GX_BEGIN_QUADS=1`. The project encoder uses `BEGIN` opcode `0x40`, then the
unchanged proven `NORMAL` `0x21`, `TEXCOORD` `0x22`, and `VTX_16` `0x23`
commands, followed by `END` `0x41`. Independent triangles consume each three
vertices; independent quads consume each four. Strips/fans remain rejected.

Only consecutive equal face types share a block. The canonical ordered plan is
one four-quad block (364 bytes) followed by one four-triangle block (284
bytes), 648 bytes total. It emits 28 vertices and uses 60.674% of shape 6's
verified 1,068-byte capacity. A bounded independent parser confirms both
opcodes, arities, normal/UV counts, block boundaries, and the terminal `END`.
It rejects corrupted begin types and end commands.

Canonical winding is right-handed after Y-up/+Z-forward normalization. The
face cross product defines the emitted normal and must agree with every source
corner normal (`dot >= 0.5`). Cardinal X/Z rotations preserve handedness;
tests cover 0/90/180/270 degrees and verify positive cross/normal dot products.
No screenshot-driven manual winding fix is used.

The transformed MDL0 model counters are no longer quad-assumed. They are
written as 96 total vertices, 25 polygons, 4 triangles, and 21 quads for the
complete template model (including flat ground and unselected-shape safety
primitives).

## Canonical proof asset and world

`assets/source/stage4e_faceted_tower.obj` and
`assets/manifests/stage4e_faceted_tower.json` are tracked project-authored CC0
sources. The 3 x 6 x 3 tile tower has a rectangular four-quad shell and a
pyramidal four-triangle roof meeting at one apex. It uses 9 positions, 5 UVs,
8 normals, one material group, and the `stage4d_stone` project texture bound
through the previously proven `prop_secondary` shape 6/material 17 path.

`fixtures/stage4e_triangle_world.json` is symbolic schema 11 source. It places
one tower at `(16,16)` on a flat 32 x 32 project-textured map, starts the player
at `(16,22)`, reuses controlled proof header 538/member 633, and selects the
appended project area-data/texture member 106 through registry symbols. It uses
the already proven fixed camera preset 4; no camera work continued.

The manifest footprint `[-1.5,+1.5]` in X/Z produces nine blocked tiles.
Visual geometry and collision placement share the manifest anchor. No detailed
triangle-mesh collision was introduced.

Key hashes are:

| Artifact | SHA-256 |
|---|---|
| OBJ source | `0321f51f2d383f728b140f8ecaef041f60eeca50ddee6acef737658ce8b2ba32` |
| normalized semantic mesh | `b7c666fb2b2c759bf4c78546eb980139849d54d180a7ddbb39d2211a7d449bd9` |
| mixed display list | `c03249bd7999ee5dde9a1045bdb8d8f8873803f44d7fdeaa08b6cd832763167d` |
| transformed NSBMD | `746937fb1695b257f810d1b3c2edc0ad0931c972616267a62c283a934c2b9786` |
| PER | `2cfc72a045e0111ceef672a9fd6dc1fe5c6d2ef3978c23f1826e380c106b956b` |
| map member | `0fae6306b18858754ec115aa373ec84e83d0723ebed429a197125767628e1951` |

## Build, binary validation, QA, and visual result

`make stage4e-triangle-proof` completed from a clean HG-Engine build and
produced the ignored `test.nds` with SHA-256
`5e3443baf385bb1c69ff5a136114b08c218b28c9ce6c51237b0a00ee0e598357`.
The ROM-contained map member 633 matched the generated map member. Appended
area-data and area-texture NARCs retained 107 members; member 106 matched the
generated eight-byte area record and project texture container respectively.
The binary display list contains `BEGIN(QUADS)` followed at offset `0x16c` by
`BEGIN(TRIANGLES)`, and ends at offset `0x284` with `END`.

The tracked 23-step Stage 4A scenario has plan SHA-256
`74ce5f3c5db3f46624aea258e2ff7d5ea11d9153d9df43a7552e7eb7da2033f9`
and passed 15/15 assertions. It confirmed header 538, matrix 1, member 633,
height 0, no NPC/warp path, five-tile approach, expected northward footprint
block, east/north/west walk-around to the rear, nearby westward movement, two
valid captures, and stability through frame 8,809 after another 600 frames.

Codex inspected both 256 x 384 captures. The front and rear views show the
four-facet pyramidal roof above the upright rectangular shell. No face is
missing from either side, the silhouette and inherited lighting are coherent,
the stone masonry/blue-trim UVs remain attached rather than exploding, the
asset is grounded, and neighboring project terrain is intact. Collision blocks
the visual footprint while the surrounding path remains walkable. Screenshot
SHA-256 values are
`e2c82b0771596e7284c072e28c62d8f910a6c02110134263385ebf445066e29f`
and `16be99a265f488a8c506c0b91dff2747fb8414be0fade6589d3e16fb2ba77de2`;
these are traceability evidence, not brittle correctness assertions.

## Source mutation and determinism

A temporary source-only mutation raised the roof apex from 6.0 to 6.5 tiles.
It changed source SHA `0321f51f...` to `58685af6...`, normalized mesh SHA
`b7c666fb...` to `d0b9ab8a...`, and display-list SHA `c03249bd...` to
`d3861423...`. Asset identity, project texture/palette bytes, world resource
IDs, and collision SHA `a7cd8668...` remained unchanged. The canonical OBJ was
restored automatically by using isolated temporary sources.

Two clean generation roots matched all 46 Stage 4E binary artifacts with zero
mismatches: normalized IR, primitive plan/report, display list, texture
bindings, collision proxy, NSBMD, map member, PER/BDHC, world/registry/catalog
snapshots, rebuilt NARCs, and ARM9.

## Tests, regressions, evidence, and limits

Focused Stage 4E tests cover the exact primitive plan, all cardinal rotations,
corrupt begin/end streams, degenerate/duplicate triangles, reversed winding,
invalid UV/normal, missing indices, N-gons, material failures, fixed-point
overflow, mixed-shape capacity overflow, deterministic compilation, symbolic
resolution, and source mutation propagation. Existing Stage 4B--4D quad and
texture tests remain unchanged in semantics.

Clean-root determinism passed with zero mismatches for Stage 2, 3A, 3B, 3C,
3D, 3E1, 3E2, 4B, 4C, 4D, and 4E. Registry validation passed 12 namespaces /
34 resources. All seven declarative QA scenarios validated. Virtual-environment
preflight passed commands, Python packages, system library, supported ROM,
git-hygiene, and Docker-context groups. The full suite ran 166 tests: 163
passed and three opt-in integration gates skipped as designed.

As a fresh immediate-predecessor runtime regression, Stage 4D was rebuilt and
its declarative scenario passed 17/17 assertions through stable frame 9,575.
Stage 4E was then restored by the normal deterministic installer/repacker and
its scenario passed a second time with the same ROM and screenshot hashes.
Earlier-stage live evidence remains preserved in its committed reports; their
serializers and complete artifact graphs were revalidated by the full suite
and the clean-root determinism battery rather than replaying every emulator
route in this bounded stage.

Evidence came from the supported `pret/pokeheartgold` revision
`008257708bd41df5b8c9037e019088ba24df0a87` and its Nitro declarations.
Apicula revision `3d4e91e14045392a49c89e86dab8cb936225588c`
(0BSD) independently corroborated command parsing and primitive grouping. No
editor code, Nintendo converter, proprietary tooling, or retail asset bytes
were added. No DeepSeek call was needed: usage was 0 tokens, estimated cost
`$0`.

The supported boundary remains independent triangles/quads, explicit positive
OBJ indices, authored UVs/normals, one material per proof asset, cardinal
rotation, inherited material state, three proven project texture slot pairs,
existing shape capacities, rectangular collision, and the locked US revision.
There is no N-gon/strip/fan support, triangulation, topology repair, negative
indices, arbitrary transforms/materials, detailed collision, display-list
relocation, GLB, simplification, image-to-3D, production landmark, kit, or game
content.

Stage 4F may proceed only as a separately bounded next asset capability. A
logical next gate is GLB/GLTF ingestion into this same typed triangle/quad IR,
without adding simplification or generative 3D in the same stage.
