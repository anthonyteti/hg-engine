# Stage 4F technical report: GLB static-mesh ingestion

## Verdict

`STAGE_4F_GLB_PIPELINE_PASSED`

A tracked project-authored GLB now deterministically parses into the same
source-neutral records and typed triangle IR as OBJ, then passes unchanged
through the proven DS display-list encoder, project texture catalog, symbolic
placement, footprint collision, HG-Engine build, declarative emulator QA, and
front/rear visual inspection.

## Stage 4E checkpoint

Stage 4F began only after the intentional Stage 4E parser, typed IR, Nitro
encoder, source/manifest, fixture, QA, tests, Make integration, and documents
were staged explicitly and checked. Commit
`774e08b2b Add Stage 4E triangle asset pipeline` (full
`774e08b2b09957731d7cfb2c00a69541c12f2601`) was pushed to `main`.
Local `HEAD`, `origin/main`, and remote main matched and the worktree was clean.
No generated, retail, or sensitive artifact entered the checkpoint.

## Parser/library decision and source evidence

The official Khronos
[glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
is authoritative for the container, coordinate, UV, scene, bufferView, and
accessor rules. `pygltflib` 1.16.5 (MIT) was evaluated: it is maintained and
supports GLTF/GLB, but its broad object model would not replace the strict
offline/safety/subset validation this compiler needs. No dependency was added.
The project-owned `tools.pokeagent.glb` uses only Python standard-library
`json`, `struct`, and `math`.

This is legally redistributable project code and a project-authored CC0 proof
asset. There is no copied converter/parser, Blender, `g3dcvtr`, network access,
proprietary tool, or retail model/texture source.

## Architecture and supported source subset

Stage 4F creates an actual source adapter boundary:

```text
OBJ parser ─┐
            ├-> SourceMesh -> shared normalization -> typed mesh IR schema 2
GLB parser ─┘                    -> budgets -> Nitro -> texture/collision/world
```

`tools.pokeagent.asset_source` owns frozen source-neutral corner, face, and
mesh records. `assets.py` dispatches schema-5 manifests to `parse_glb`; no GLB
structure passes beyond that call. OBJ behavior stays on schemas 1--4.

The accepted GLB is version 2, little-endian, JSON+BIN only, one selected scene,
one leaf identity-transform node, one mesh, one name-only material, and one to
four indexed mode-4 triangle primitives. Each primitive requires float32
`POSITION`, unit float32 `NORMAL`, float32 `TEXCOORD_0`, and unsigned
8/16/32-bit scalar indices. Position bounds are required and verified. Tight
and bounded interleaved views are supported with complete offset, stride,
alignment, count, finite-value, and range checking.

GLB's right-handed meter/+Y-up/+Z-forward convention matches the proof
manifest's declared source convention. The parser records glTF's upper-left UV
origin; shared normalization flips V once into the canonical OBJ-compatible IR.
Node transforms are rejected rather than partially applied. Source order is
stable; exporter-duplicated attribute tuples are stable-deduplicated by first
occurrence. The downstream encoder cannot tell whether OBJ or GLB authored the
mesh.

The bounded budget is 256 KiB source/BIN, one scene/node/mesh/material/buffer,
four primitives, 16 accessors, 16 views, and 256 accessor elements. It rejects
URIs, remote/external resources, images/textures, extensions, PBR fields,
transforms/hierarchies, animation, skins, morph targets, sparse/normalized
accessors, missing attributes, non-triangle modes, and every malformed bounds,
stride, alignment, index, winding, normal, material, or capacity case tested.

## Proof asset and semantic equivalence

`assets/source/stage4f_glb_faceted_tower.glb` is a 2,248-byte tracked CC0
single-file asset. It is semantically the Stage 4E tower with the four wall
quads represented as eight triangles and the same four roof facets: 36 source
attribute elements, U16 indices, one `faceted_shell` material, and no image,
animation, skin, morph, extension, or node transform.

The parser stable-deduplicates it to 9 positions, 5 UVs, 8 normals, and 12
triangles. The 3 x 6 x 3 tile bounds, ordered triangulated geometry, winding,
UVs, normals, material identity, `stage4d_stone` binding, and 3 x 3 footprint
match the Stage 4E OBJ after normalization. Their display lists appropriately
differ: OBJ preserves four quads plus four triangles; GLB contains 12 triangles.

The schema-5 manifest retains the existing project texture catalog, maps
`faceted_shell` to `prop_secondary`/`stage4d_stone`, uses shape 6/material 17,
and owns no physical Nitro ID. Schema-12
`fixtures/stage4f_glb_world.json` symbolically places it at `(16,16)` on the
same simple project-textured ground, starts at `(16,22)`, and uses controlled
proof header 538/member 633 plus appended project area resources 106. There is
no explicit warp or new gameplay feature.

## Geometry, binary, texture, and collision results

The GLB produces one existing Nitro TRIANGLES block:

| Metric | Result |
|---|---:|
| triangles / quads | 12 / 0 |
| emitted vertices | 36 |
| display-list bytes / capacity | 828 / 1,068 |
| shape utilization | 77.528% |
| source SHA-256 | `89c32d0d3d29a0d57b63605cb6b195f17821296beaee97ce561db108a352df1d` |
| semantic IR SHA-256 | `6a7f72d7b17c215efc2d7150ceee122ee568c34805e127b294afcf2dd7d40b4d` |
| display-list SHA-256 | `a2f57b278d759f105e11b073fb41b65725e44a9a8dcfc87e238fc7e7bacceae7` |
| NSBMD SHA-256 | `c78e5511f731d8f920e133c72826c2ca1c3419ea09539a0fb32f0a87bcbd74d0` |
| PER SHA-256 | `2cfc72a045e0111ceef672a9fd6dc1fe5c6d2ef3978c23f1826e380c106b956b` |
| map-member SHA-256 | `887185da919c5616b216e8ca59e690233d746952ba63a62a7cba1eddb6e4b450` |

The independent display-list inspector confirms TRIANGLES mode, 12 complete
faces, 36 UV/vertex commands, 12 normals, and terminal END. Updated model
counters are 104 vertices, 29 polygons, 12 triangles, and 17 quads including
ground and template safety primitives. No GLB-specific rendering command or
texture route exists.

The ROM-contained land-data NARC has 676 members; member 633 exactly matches
the generated map member. Appended area-data and area-texture NARCs each have
107 members; member 106 matches the generated eight-byte area record and
project texture container. The existing `stage4d_stone` PLTT16/BGR555 payload,
Nitro binding, and rectangular collision proxy are unchanged. Nine tiles block
under the visible footprint while adjacent terrain remains walkable.

## Build, gameplay QA, and visual result

`make stage4f-glb-proof` completed from a clean HG-Engine build. The ignored
`test.nds` SHA-256 is
`e0a7b2263cfb1c60fd910fe3c417f6c292638b402b5a9b8dc639fb94b68302b3`.

The tracked 23-step Stage 4A scenario has plan SHA-256
`4c419a76ceafa5e3da9b26278700aa49b08fb4e056c44e476a8ede25592ec45a`
and passed 15/15 assertions. Live state proved header 538, matrix 1, member 633,
height 0, no event/warp substitute, controlled start `(16,22)`, approach to
`(16,17)`, northward footprint block, east/north/west traversal behind the
tower at `(16,13)`, west movement to `(12,13)`, and another 600 stable frames
through frame 8,809. Per-run isolated battery configuration remained active.

Codex inspected both 256 x 384 captures. Front and rear views show the complete
four-facet roof and tower shell, consistent inherited lighting, intact stone/
blue-trim mapping, correct orientation/scale, and a grounded base. No facet is
missing from either side; there is no mirrored/exploded UV mapping, neighboring
terrain corruption, or geometry/collision disagreement. Screenshot SHA-256
values are `e7a2bbc12b7ccf83935decf00c5f4d9090ffb49b09d45e17db6ab2562a512e56`
and `4a40ac85fabf6069995b438e172f67d99c8188f24fbcc1e2c8c62a43ea5d0814`;
they are supporting evidence, not brittle assertions.

## Mutation and deterministic rebuild

A temporary deterministic GLB build raised only the roof apex from 6.0 to 6.5
tiles. Source SHA changed `89c32d0...` to `1ad26298...`, normalized IR
`6a7f72d7...` to `896dba5b...`, display list `a2f57b27...` to `202ccb5e...`,
and transformed NSBMD `c78e5511...` to `fa5a591c...`. Asset identity, world
IDs, texture/palette bytes, and collision SHA `a7cd8668...` stayed unchanged.
The tracked source was never mutated.

Two clean Stage 4F generation roots matched all 43 deterministic artifacts
with zero mismatches: source-derived IR/report, display list, texture bindings,
collision proxy, NSBMD, map member, PER/BDHC, world/catalog/registry snapshots,
NARCs, and ARM9. The installed output adds three deterministic generated
script/text artifacts for 46 manifest hashes. Clean-root determinism also
returned zero mismatches for every Stage 2 through Stage 4E fixture.

## Tests, regressions, and remaining limits

The focused suite covers canonical byte packing, semantic OBJ equivalence,
tightly packed and interleaved accessors, U8/U16/U32 indices, invalid header/
version/chunk/URI, scene/transform/animation/skin/morph/image/PBR rejection,
missing attributes, bad primitive modes, accessor bounds/types/sparse/count/
stride/view failures, reversed winding, degeneracy, unmapped materials,
capacity overflow, mutation propagation, symbolic fixture resolution, and
deterministic repeats.

Registry validation passed 12 namespaces / 34 resources. Preflight passed all
command, Python, system, ROM, git-hygiene, and Docker-context checks. The full
suite ran 175 tests: 172 passed and three opt-in integration gates skipped as
designed. All eight tracked QA scenarios validate deterministically.

Stage 4E was reinstalled/repacked as the immediate runtime regression and its
scenario passed 15/15 assertions through frame 8,809. Stage 4F was then
restored; its ROM returned to the exact SHA above. Earlier proofs were covered
by their full serializer/registry/QA-schema tests and all-fixture clean-root
determinism rather than replaying every historical emulator route.

No DeepSeek call was needed. Usage was 0 tokens and estimated cost `$0`.

The supported boundary remains `.glb` only, embedded BIN, one static identity
scene/node/mesh/material/buffer, indexed independent triangles, authored
float32 positions/unit normals/UV0, U8/U16/U32 indices, bounded tight or
interleaved views, existing shape/material capacity, existing project PNG
textures, cardinal placement, and rectangular collision on the locked US
revision. Unsupported features include `.gltf`, every URI, extra hierarchy or
transform, non-triangle modes, non-indexed geometry, sparse/normalized data,
embedded images/PBR, tangents/secondary UVs/colors, animation/skin/morph,
extensions/compression, repair, simplification, generated assets, detailed
collision, and production content.

Stage 4G may proceed only as a new bounded gate. The logical next proof is
deterministic mesh simplification/budget reduction around this now-proven
modern interchange boundary; it must not be conflated with topology repair,
image-to-3D, generative services, or production kits.
