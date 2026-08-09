# Stage 4P Technical Report: Atomic Attribute Bootstrap

Date: 2026-08-09

Verdict: `STAGE_4P_ATTRIBUTE_BOOTSTRAP_PASSED`

Bootstrap classification: `ATTRIBUTE_BOOTSTRAP_GAP_CLOSED`

COLOR_0 classification: `COLOR0_EXPLICIT_DISCARD_PROVEN`

## Checkpoint and scope

Stage 4O was committed and pushed before this work began as
`6fa79e9ef4595b0135773fa6dcf86bd20050fd8b`
(`Add Stage 4O geometry predecimation`). Local `HEAD`, `origin/main`, and the
remote `main` reference agreed, and the worktree was clean.

Stage 4P closes the isolated-attribute sequence with one explicit transaction:

```text
bounded POSITION + indices GLB
  -> validate geometry-only contract
  -> assign one manifest-declared source material
  -> derive connected planar-patch UV0 from geometry and winding
  -> derive final crease-aware normals with generated UV seams protected
  -> write one canonical GLB
  -> reopen through unchanged Stage 4F
```

It does not repair geometry, flatten hierarchy, reduce geometry, create a DS
material or texture, process the Stage 4H candidate, or broaden Stage 4F.

## Architecture and atomic policy

`tools.pokeagent.glb_bootstrap` owns schema-13 transaction validation, phase
ordering, generated-attribute provenance, atomic failure, canonical output,
and read-only `COLOR_0` compatibility reporting. It reuses:

- Stage 4N's public source-name validator;
- Stage 4M's extracted pure geometry-to-planar-UV core;
- Stage 4L's unchanged missing-normal generator and UV-aware smoothing fans;
- the existing bounded GLB packer and unchanged Stage 4F parser.

No second UV or normal algorithm was introduced. Standalone Stages 4L, 4M,
and 4N retain their strict isolated source contracts and their documented
canonical hashes.

The manifest policy is `hard_surface_static_v1` with:

- source material `generated_surface`;
- `COLOR_0` rejected on the runtime proof;
- 0.1-degree planar-patch normal tolerance;
- `1e-5` plane-distance tolerance;
- 32x32 texture space with one-texel padding;
- 60-degree crease threshold;
- area-weighted final normals.

The transaction emits no successful canonical file until all phases and the
independent Stage 4F reopen succeed. Stable phase errors distinguish source,
material, UV, normal, and final Stage 4F failures. Generated data is labeled
as Stage-4N-policy material identity, Stage-4M-policy planar UV0, and
Stage-4L-policy crease-aware normals; none is described as authored.

## Source contract and ordering decision

The bounded input is an embedded GLB 2.0 with one scene, one identity mesh
node, one mesh, one indexed independent-triangle primitive, `POSITION`, and
indices. It must have no `NORMAL`, `TEXCOORD_0`, material, or auxiliary
attribute. Limits are 256 KiB source/BIN, one node/mesh/primitive, four
accessors/views, 256 positions, 80 faces, and 240 indices.

UVs are generated before final normals. Stage 4M patch construction only needs
transient geometric face normals derived from valid winding; those transient
values are never serialized. Stage 4L then sees the actual generated UV seams
and prevents smoothing across them. Reversing this order would either require
inventing provisional normals to satisfy the standalone Stage 4M interface or
would smooth across seams whose existence was not yet known.

The same consequence explains the crease-policy mutation: planar-patch UVs
already split every non-coplanar edge in the canonical transaction. Changing
60 degrees to 30 degrees is therefore a deterministic semantic no-op for this
fixture. It does not bypass UV-seam protection merely to force an output
difference.

## Canonical proof and exact reference

The tracked source `assets/source/stage4p_geometry_only_turret.glb` is a
project-authored 19-position, 30-triangle open-bottom hard-surface turret with
walls, ledges, a faceted roof, and no material, UV0, or normals. Its SHA-256 is
`abe77fe5f6ce58e1ca01b26946d35bde438b12d1598d43bb044b74f6fed5216e`.

The completed canonical GLB is byte-identical to the independently constructed
complete reference `assets/source/stage4p_complete_reference.glb`:

`06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1`

Stage 4F rejects the raw source as `unsupported_material`; after the atomic
transaction the unchanged parser accepts all 30 faces and the single
`generated_surface` material.

| Metric | Result |
|---|---:|
| source positions / faces | 19 / 30 |
| planar patches | 18 |
| UV-driven splits | 47 |
| final attribute vertices | 66 |
| UV seam edges | 30 |
| UV range | 0.03125 .. 0.96875 |
| degenerate / mirrored UV triangles | 0 / 0 |
| maximum / mean aspect distortion | 0.000001129 / 0.000000342 |
| smoothing fans | 66 |
| hard / smooth edges | 30 / 12 |
| generated unique normals | 40 |
| max float32 normal-length error | 2.76e-8 |

The normalized asset is 4.30 x 4.50 x 3.72 tiles. It emits 90 triangle
vertices in a 2,052-byte Nitro display list, SHA-256
`4377c8cf4628b296273056b52d3f2710fdecbc587fa7ee5dea6181bd9f7bbb5e`,
using 82.212% of shape 1's inherited 2,496-byte region. No Stage 4J reduction
or Stage 4I relocation is needed.

`generated_surface` maps through alias `prop` to the unchanged
`stage4d_stone` texture. Texture SHA-256 is
`fed37aab0b14b2e656f7c34f0bfc08f41129f578d7025ae7205fc8981cc078d7`;
palette SHA-256 is
`744abd4930f4580303c156f1f5440f9b320c7eb21b08060582a63206ba56e7d1`.
Collision remains manifest-owned at `[-1.9,1.9] x [-1.65,1.65]`, with semantic
hash `404200f5a057db3926b7037e26a26f8a03fee5b6cef187d60aafc3f74c8076b7`.

## COLOR_0 decision

Three policies were evaluated. Preserving/interpolating color through Stage
4O would add an attribute-aware reduction policy and imply runtime meaning the
project does not use. Default deletion would silently discard authored
appearance. Continued rejection is safe but leaves a non-runtime generated
attribute as an unnecessary structural blocker.

The proven decision is explicit opt-in discard, limited to generated
hard-surface geometry whose appearance will intentionally be replaced by a
project texture. The source must have no source material, PBR texture/image,
or other auxiliary attribute. Only bounded normalized unsigned `COLOR_0`
VEC3/VEC4 is accepted. The source remains immutable; the report records its
accessor, count, type, byte count, and payload hash.

The controlled 19-element normalized U8 VEC4 fixture has payload SHA-256
`d6ced436249fc4c1e2729cec8acc742a10964cf6ecd3d70b4ccfcd3edb70231d`.
Explicit discard produces a geometry-only GLB byte-identical to the independent
no-color reference, preserving POSITION/index semantics exactly. Without the
policy it fails as `bootstrap_color0_policy_required`. No color value is
interpreted, interpolated, converted to a texture, material, normal, or UV.

## Composition, mutation, and determinism

- Stage 4O's canonical 35-position/64-face result bootstraps to 192 attribute
  vertices and passes unchanged Stage 4F, proving the intended boundary.
- The transaction consumes identity geometry after a supported Stage 4K
  canonicalization; hierarchy logic is not duplicated.
- Its complete typed output has material, UV, normal, manifold, and bounded
  geometry semantics required for later Stage 4J eligibility; Stage 4J is not
  invoked in this proof.
- Reversed face order yields byte-identical canonical GLB.
- Raising the roof changes geometry, UV patch data, normals, canonical GLB,
  typed IR, display list, and model while retaining material/project identity.
- Renaming the temporary source identity changes material bytes only; mapping
  it to the same alias/texture preserves project texture and Nitro geometry.
- One-to-two-texel padding changes UV/canonical outputs while preserving
  positions, topology, material, textures, and seam classification.
- The 60-to-30-degree normal mutation is a deterministic no-op because the
  generated patch seams are already the stricter boundary for all
  non-coplanar edges.
- Two clean roots produce byte-identical bootstrap report, GLB, IR, display
  list, collision, NSBMD, map member, texture resources, NARCs, and ARM9 input;
  world determinism reports zero mismatches.

## Runtime, QA, and visual evidence

`make stage4p-attribute-bootstrap-proof` builds the ROM using the ordinary
world installer. The declarative Stage 4A scenario boots map header 538 /
matrix 1 / member 633, approaches the turret, proves the collision footprint,
walks around it, captures front and rear views, traverses neighboring terrain,
and remains stable for another 600 frames. All 15/15 assertions pass through
frame 8,848. The ROM SHA-256 is
`29b642100bae82c29e2a2d7499052754bc68dce2bdb1fcc0290ffc47b4294273`;
the front/rear screenshot SHA-256 values are `40e80c5e...b55afb1` and
`af767864...6060322`.

Visual inspection confirms a complete upright faceted turret, grounded on the
project terrain, with coherent repeated stone mapping, stable wall/roof
orientation, correct hard transitions, coherent lighting, no inverted or
missing faces, no exploded attribute splits, and aligned collision. Terrain
and neighboring traversal remain intact.

## Stage 4H read-only projection

The immutable Stage 4H GLB remains SHA-256
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
Its normalized U8 VEC4 `COLOR_0` structurally matches the explicit discard
format (3,360 elements, payload SHA-256
`019534d056ff0fc4713bfdedcbf6bb6adf320eb23a64edb407edc21c9bdb910e`).
This is applicability evidence only; no attribute was discarded and no derived
candidate was created.

Removing color alone would not make the candidate eligible. It still contains
one zero-area face, two connected components, 99 boundary edges in 25 loops,
and violates Stage 4O's valid one-component source policy. It also remains a
6,664-triangle geometry requiring authorized preprocessing. The raw file,
historical `STAGE_4H_GENERATED_ASSET_REJECTED` /
`REJECTED_UNSUPPORTED_STRUCTURE` verdict, and lack of catalog identity are
unchanged.

## Regressions and remaining limits

Canonical outputs remain exact: Stage 4K `d3fba377...`, Stage 4L
`b49552f3...`, Stage 4M `c18f88f0...`, Stage 4N `3443c8fc...`, and Stage 4J's
4,024-byte display list `e01fcce1...`. Stage 4O, strict GLB, OBJ, exact and
approximate reduction, model relocation, generated intake, texture catalog,
registry, QA isolation, preflight, full unit suite, and tracked-artifact
hygiene remain green. The full suite passes 270 tests with three expected
opt-in integration skips; the focused Stage 4P suite passes 12/12.

Stage 4P remains limited to one valid identity-node, one-component,
hard-surface mesh inside the 80-face/256-position envelope. It does not handle
topology defects, multiple components, non-identity transforms, organic UVs,
source appearance preservation, PBR, arbitrary auxiliary attributes, or large
geometry. The recommended Stage 4Q direction is a separately authorized,
strictly bounded topology-intake decision for real generated evidence—not
production art and not a retroactive Stage 4H approval.

DeepSeek was not used; cost was $0.
