# Stage 4G technical report: deterministic mesh simplification

## Verdict

`STAGE_4G_SIMPLIFICATION_PIPELINE_PASSED`

A valid, deliberately over-tessellated project GLB now passes through the
shared source-neutral/typed mesh path, demonstrably exceeds its verified Nitro
shape budget, and is reduced deterministically by an opt-in exact coplanar
patch simplifier. The reduced model preserves its bounds, surface area,
materials, UV boundaries, hard normals, texture, collision, and symbolic IDs;
it builds through HG-Engine and passes binary, declarative gameplay, visual,
mutation, and clean-root determinism gates.

## Stage 4F checkpoint

Stage 4G began only after the intentional Stage 4F GLB parser, source adapter,
asset, manifest, fixture, QA, tests, Make integration, and documents were
explicitly staged and checked. Commit `252d4b238 Add Stage 4F GLB asset
ingestion` (full `252d4b238ab67db662ed7787d8f55f2a12754d44`) was pushed to
`main`. Local `HEAD`, `origin/main`, and remote main matched, and the worktree
was clean. No generated, commercial, or sensitive artifact entered the
checkpoint.

## Algorithm and dependency decision

Stage 4G uses project-owned `exact_coplanar_patches` algorithm version 1. It
uses only the Python standard library and adds no package. A broad QEM/edge-
collapse dependency was rejected for this proof because it would introduce
approximation, seam/error policy, output-order, and dependency concerns that
are unnecessary for redundant coplanar tessellation. Blender, proprietary
tools, remote services, and GUI cleanup are absent.

The simplifier operates after OBJ/GLB parsing and shared normalization on typed
mesh IR schema 2. It groups connected triangles only when their material,
project texture, geometric plane, face normal, and authored protected hard
normal match. Adjacency keys include both position and UV indices, preventing
cross-seam merging. Each patch must be a consistently wound manifold disk with
one simple boundary. Only collinear boundary vertices whose UVs interpolate
exactly within a fixed `1e-6` tolerance are removed. The remaining three- or
four-corner boundary becomes one typed triangle or quad. Stable source indices,
sorted edge traversal, and deterministic tie breaks make output independent of
set/dictionary iteration order.

Every output is revalidated. Computed referenced-vertex bounds, dimensions,
surface area, winding, normal agreement, material identity, and downstream
asset validation must pass. The compiler fails rather than approximate when a
patch is non-manifold, has multiple loops, requires crossing a seam/hard edge,
does not reduce to a triangle/quad, changes bounds/area, or still exceeds the
actual shape budget.

## Manifest policy and compiler architecture

Asset manifest schema 6 adds an explicit opt-in block:

```json
{
  "simplification": {
    "policy": "exact_coplanar_patches",
    "target": "fit_shape",
    "reduction_mode": "maximal_exact",
    "reserve_bytes": 0,
    "preserve_boundaries": true,
    "preserve_uv_seams": true,
    "preserve_material_boundaries": true,
    "preserve_hard_normals": true
  }
}
```

Schemas 1--5 remain unchanged: an over-budget legacy asset still fails before
encoding. Allocation targets the assigned verified Nitro shape capacity, less
an explicit reserve; authored input never supplies a physical display-list
offset. The source budget permits the bounded dense proof to reach the
simplifier, while the final encoded budget remains the existing shape limit.

The format-independent flow is:

```text
OBJ / GLB -> SourceMesh -> normalized typed IR -> source byte projection
                                           -> opt-in exact simplifier
                                           -> ordinary typed-IR validator
                                           -> existing Nitro encoder
```

`asset inspect` reports both source and final budgets. `asset simplify` makes
the declared transformation explicit and writes ignored `normalized-mesh.json`
and `simplified-mesh.json` artifacts. `asset compile` and the world compiler use
the same function; no world- or source-format-specific simplifier exists.

## Dense canonical source and measured reduction

`assets/source/stage4g_dense_faceted_tower.glb` is a 5,952-byte project-
authored CC0 GLB in the Stage 4F subset. It represents the same 3 x 6 x 3-tile
tower as Stage 4F, but subdivides each wall into eight redundant coplanar
triangles and each roof facet into four. It contains one static mesh/material,
indexed triangles, authored positions/normals/UV0, and no image, animation,
skin, morph, transform, or repair requirement.

| Metric | Source | Simplified |
|---|---:|---:|
| triangles | 48 | 4 |
| quads | 0 | 4 |
| referenced vertices | 29 | 9 |
| emitted vertices | 144 | 28 |
| display-list bytes | 3,276 | 648 |
| shape-6 capacity | 1,068 | 1,068 |
| overflow/utilization | +2,208 bytes | 60.674% |
| surface area | 63.0 | 63.0 |

Face count falls 83.333%; encoded bytes fall 80.220%. The simplifier produces
eight exact patches: four wall quads and four roof triangles. Bounds and ground
contact are exact, surface-area delta is zero, maximum retained-boundary vertex
displacement is zero, and maximum normal deviation is zero degrees. The
reported UV seam-vertex count falls from 20 to 8 because redundant collinear
segments disappear; seam boundaries themselves are protected by position+UV
edge identity and exact UV interpolation.

Canonical hashes are:

| Artifact | SHA-256 |
|---|---|
| dense GLB | `b401e833f9bc87fc275b69c6737e52b17a64990267dca2e0b6603f9db99c1960` |
| normalized source IR semantic | `e44f16a644efddb307bf166d298da3c48ed350fa4c1da6f22996a9965a532e3d` |
| simplified IR semantic | `f665868fda527215983bfe330a7129017f42335f664b0a0271b8258acf5495ba` |
| display list | `7c8b0d34bc6861e9f5aa799b115ddbcf1245faad96177de52b51a9e69e68f579` |
| transformed NSBMD | `d13f1b49cf9ac839b17ac24ac2fb84a4a0ae41bcc4531dfc0eaa27f8af9c5e0e` |
| map member | `b87aa224d9fee958e49925d2021e0ae1c788ec1603b4cfda0d4e742ea6f4a928` |
| collision | `a7cd86681a16abad2ad7f0796fcde753fd41fe569e817dfb3bd3f48d884d45f3` |

The Stage 4F semantic comparison proves identical bounds, dimensions,
triangulated surface geometry, UVs, normals, project material/texture identity,
and collision footprint. Stage 4G's display bytes differ beneficially because
the exact reducer recovers four native quads instead of emitting all twelve
low-poly faces as triangles.

## Binary, texture, collision, build, and runtime proof

The independent display-list inspector confirms a 364-byte QUADS block with
four faces and a 284-byte TRIANGLES block with four faces, 28 emitted vertices,
valid terminal END, and 648 total bytes. The ROM-contained land-data member 633
matches the generated 18,738-byte member. Appended area-data member 106 and
project area-texture member 106 exactly match the generated eight-byte record
and 37,092-byte container. No shape relocation or capacity increase occurred.

The existing `stage4d_stone` PLTT16/BGR555 payload and material 17/shape 6
binding are unchanged. The manifest-derived 3 x 3 rectangular collision proxy
is unchanged from Stage 4F and has the same SHA-256 above; simplification never
generates collision.

`make stage4g-simplification-proof` completed from a clean HG-Engine build.
The final ignored ROM SHA-256 was
`a249ca932bb31a4c7dd3c1824017987976e7d0db7c2a0a836e34a48eac377224`.

The tracked 23-step Stage 4A scenario has plan SHA-256
`5a135b532e17a12af094659bde63701de8ca637ac8519f56f10dc6a105db1423`
and passed 15/15 assertions. Live state proved header 538, matrix 1, member 633,
height 0, no event/warp substitute, controlled start `(16,22)`, approach to
`(16,17)`, northward footprint block, complete east/north/west walk-around to
`(16,13)`, west movement to `(12,13)`, and another 600 stable frames through
frame 8,809. Per-run isolated battery state remained active.

Codex inspected the 256 x 384 front/rear screenshots. They show the same
straight tower shell and four-facet pyramidal roof as the Stage 4F reference,
with a sharp wall/roof boundary, coherent stone/blue texture, stable inherited
lighting, and a grounded base. There are no holes, inverted/missing faces,
collapsed corners, mirrored/exploded UVs, or neighboring terrain corruption.
Collision agrees with the visible footprint. Capture SHA-256 values are
`e2c82b0771596e7284c072e28c62d8f910a6c02110134263385ebf445066e29f`
and `16be99a265f488a8c506c0b91dff2747fb8414be0fade6589d3e16fb2ba77de2`;
these are supporting traceability, not correctness oracles.

## Mutation and determinism gates

A temporary deterministic source builder raised only the roof apex from 6.0
to 6.5 tiles. Source hash changed `b401e833...` -> `6a1cc098...`, normalized
source IR `e44f16a6...` -> `af391e29...`, simplified IR `f665868f...` ->
`233d9e84...`, and display list `7c8b0d34...` -> `a507deec...`.
Asset symbol, world IDs, texture and palette bytes, and collision hash stayed
unchanged. The tracked source was never mutated.

A temporary target reserved 700 of 1,068 shape bytes, leaving 368. The exact
648-byte output could not satisfy it without violating geometry constraints,
so compilation deterministically failed with
`simplification_target_unreachable` and reported required/target/capacity/
shape values. It did not corrupt or further degrade geometry.

Two independent clean Stage 4G roots matched all 44 generation artifacts
with zero mismatches, including source and simplified IR, reports, display
lists, textures, collision, NSBMD, map member, PER/BDHC, world/catalog/registry
snapshots, NARCs, and ARM9. The installed manifest contains 47 hashes after its
three deterministic generated script/text artifacts are added. Clean-root
determinism also passed for every Stage 2 through Stage 4F fixture.

## Tests, regressions, and evidence classification

Focused Stage 4E/4F/4G tests passed. The full suite ran 184 tests: 181 passed
and three opt-in integration gates skipped as designed. Coverage includes
canonical dense GLB packing, opt-in/legacy behavior, exact reduction and Stage
4F equivalence,
repeated deterministic output, source/simplified artifact materialization,
source and target-budget mutations, invalid policy/target, unsupported quads,
non-manifold input, unreachable capacity, display-list inspection, and symbolic
schema-13 fixture resolution. The full repository suite, registry validation,
preflight, QA-schema validation, and tracked-artifact hygiene passed. Stage 4F
was reinstalled/repacked as an immediate runtime regression and passed 15/15
assertions through frame 8,809; Stage 4G was then restored. Earlier stages were
covered by their full tests and all-fixture determinism without replaying every
historical emulator route.

No DeepSeek call was needed: 0 tokens, estimated cost `$0`.

Confirmed by source/algorithm inspection plus tests, bytes, build, runtime, and
visual evidence: exact reduction of the canonical redundant coplanar GLB,
format-independent IR placement, actual capacity targeting, identity
preservation, collision/gameplay, and deterministic output.

Confirmed only by unit tests: stable rejection of non-manifold/unsupported
topology and tighter unreachable targets.

Unsupported/unknown: approximate edge collapse or QEM, curved/non-coplanar
decimation, arbitrary quad input to the simplifier, patches with holes or more
than four irreducible corners, cross-UV/material/hard-normal merging, topology
repair, hole filling, self-intersection cleanup, disconnected-garbage cleanup,
normal/UV generation, detailed collision, display-list relocation, image-to-3D,
generated services, production kits, or production content.

Stage 4H may proceed only as a separately scoped gate. The simplifier is ready
as a conservative preprocessing stage for exact redundant tessellation; later
generated assets must still fail when fidelity and budget constraints cannot
both be satisfied.
