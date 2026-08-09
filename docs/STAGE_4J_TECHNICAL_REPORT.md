# Stage 4J Technical Report: Approximate Decimation

## Verdict

`STAGE_4J_APPROX_DECIMATION_PASSED`

Fidelity: `FIDELITY_ACCEPTABLE`

Stage 4J proves deterministic constrained approximate reduction of one valid
non-coplanar GLB to the Stage 4I runtime-tested 4,096-byte project geometry
budget. It does not modify or approve the rejected Stage 4H generated asset.

## Checkpoint and scope

Stage 4I was committed as `292be70bd Add Stage 4I project model capacity` and
pushed. Local `HEAD`, `origin/main`, and remote `main` agreed before Stage 4J.

Stage 4J adds a format-independent, exact-first simplification layer. It adds
no hierarchy support, missing-attribute generation, topology repair, texture
capacity, model capacity beyond 4 KiB, or generated-asset retry.

## Architecture and algorithm

`tools.pokeagent.mesh_decimate` consumes normalized typed IR. It canonicalizes
corner vertices/faces, computes quadrics, ranks manifold edge collapses by error
plus stable canonical tie keys, and stops when actual encoded Nitro bytes first
fit the manifest target. Ordinary geometry validation and encoding then run.

No third-party dependency is used: this is project-owned Python standard-library
code under the repository license. Stage 4G exact coplanar reduction runs first.
Approximate reduction is schema-8 opt-in and requires Stage 4I
`project_relocated_display_list` storage.

## Source budget and policy

The source envelope is 524,288 GLB bytes, 512 positions, 512 UVs, 256 normals,
256 faces, and 24,000 projected Nitro bytes. Runtime target remains 4,096 bytes.

| Metric | Predeclared limit |
|---|---:|
| Maximum vertex displacement | 0.25 |
| Maximum bounds delta | 0.25 |
| Maximum surface-area delta | 12% |
| Minimum five-view silhouette IoU | 0.90 |
| Maximum normal deviation | 50 degrees |
| Maximum UV distortion | 70% |

Material, texture, UV seam, hard-normal, boundary, and ground-contact
preservation are mandatory.

## Canonical asset and budgets

`assets/source/stage4j_dense_stone_shrine.glb` is a 22,144-byte project-authored
strict Stage 4F GLB. SHA-256:
`1557161dad774a6657a4abfc934cb4743451edbed1dd27f7487e714d8c72e1c8`.
It contains one identity-node mesh, one material, independent indexed triangles,
authored POSITION/NORMAL/TEXCOORD_0, and no unsupported runtime features.

| Stage | Faces | Positions | Emitted vertices | Nitro bytes |
|---|---:|---:|---:|---:|
| Normalized source | 208 triangles | 120 | 624 | 14,156 |
| Stage 4G exact | 64 triangles + 72 quads | - | 480 | 10,928 |
| Stage 4J approximate | 59 triangles | 37 | 177 | 4,024 |

The exact pass remains 6,832 bytes over budget. Approximate reduction accepts
83 collapses, reduces faces 71.635%, reduces bytes 71.574%, and stops at 98.242%
capacity utilization.

## Fidelity result

| Metric | Observed |
|---|---:|
| Maximum displacement | 0.123495 |
| Mean geometric error | 0.006194 |
| Bounds maximum delta | 0.175000 |
| Surface-area delta | 7.439966% |
| Maximum normal deviation | 42.807662 degrees |
| Mean normal deviation | 14.258270 degrees |
| Maximum UV distortion | 65.097121% |
| Minimum silhouette IoU | 0.933789 |

All thresholds pass. Front/rear IoU is 0.953540, left/right 0.954574, and the
three-quarter view 0.933789. Silhouette and architectural form are strong, but
localized roof UV stretch makes fidelity acceptable rather than high.

Material/texture identity remains `stage4d_stone`; texture/palette bytes are
unchanged. Manifest collision remains `[-2.45, 2.45]` on both ground axes.

## Display list and model validation

The 4,024-byte final stream has 59 triangles and 177 vertex emissions. SHA-256:
`e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04`.

Stage 4I relocates shape 6 to offset 16,604. NSBMD size grows 16,604 to 20,628
bytes. The independent parser validates sizes, ranges, non-overlap, terminal
commands, material binding, and counters. All 17 unaffected shape payloads are
byte-identical.

Final counters: one node, 23 materials, 18 shapes, 245 vertices, 76 polygons,
59 triangles, and 17 terrain quads. Transformed NSBMD SHA-256:
`c05be9faf641fe1956f07f0a5cff083318deeacc5810f66c37fddd07b408b23e`.
Map-member SHA-256:
`bf33d66d8fcf839724ceedbadef0455a5184f93b67b89d3ae9da8245186e7a19`.

## World, gameplay, and visual QA

The schema-15 symbolic fixture uses project header 544 and existing appended
resources. ROM build succeeds; final ROM size is 192,188,896 bytes, SHA-256
`665d47671bd95ece14574e3b1f6bf3642c83e782f549432a483c1e0edf406b44`.

The tracked Stage 4A scenario passes 15/15 assertions through frame 9,004. It
proves entry and resource identity, approach, expected blocked footprint,
walk-around, captures, adjacent traversal, and another 600 stable frames.

Capture SHA-256 values:

- front: `11adf44bcc68c3d47ae868ca0c35e9b3563e38aba5d844c24bb311d4de5dc38c`;
- side/rear: `a931d4471160b63d6911d32946bb3871d97fdb1ff8170ee27e01bc6f63e0ffc8`.

Visual inspection confirms the recognizable faceted shrine in both views:
intact tiers/roof, correct scale and ground contact, no holes, inversions,
truncation, or exploded vertices, coherent stone mapping, aligned collision,
and intact terrain.

## Negative, mutation, and ordering proofs

The tracked strict-fidelity fixture fails with
`approximate_simplification_target_unreachable`; its best valid state is 14,020
bytes against 4,096. Quality is therefore not sacrificed to force success.

A temporary roof-height mutation changes source, normalized IR, display list,
and model while asset symbol, texture/palette, collision, and world IDs remain
stable. A temporary 3,500-byte target yields a valid 3,480-byte result. Reversed
source face order produces byte-identical canonical output.

## Determinism and regression

Two clean Stage 4J roots have zero mismatches across source/exact/approximate IR,
reports, command stream, layout, NSBMD, PER/BDHC, map member, bindings, world and
registry snapshots, NARCs, and ARM9.

Determinism checks for Stages 2, 3A, 3B, 3C, 3D, 3E1, 3E2, 4B, 4C, 4D, 4E,
4F, 4G, and 4I also have zero mismatches. Stage 4H raw hash remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`,
uncataloged and rejected. Registry validation, preflight, artifact hygiene, and
the full suite pass. Three ROM-dependent tests remain intentionally opt-in when
the ignored local ROM is absent.

Canonical simplification takes approximately 12-16 seconds on this host. The
bounded source envelope contains current implementation cost. DeepSeek was not
used; token usage and cost are zero.

## Boundary and recommendation

Confirmed: valid single-material, authored-normal, authored-UV manifold static
meshes can use constrained approximate loss to fit 4 KiB and render through
Stage 4I within declared fidelity.

Unsupported: missing attributes, hierarchy/transforms, multiple material seams
requiring collapse, topology repair, UV unwrap, arbitrary generated meshes,
high-frequency curved fidelity, and capacity beyond 4,096 bytes. Stage 4H
remains rejected.

Stage 4K may proceed only as a separately bounded infrastructure proof for one
identified preprocessing gap; it should not combine multiple gaps or begin
production/generated-asset approval.
