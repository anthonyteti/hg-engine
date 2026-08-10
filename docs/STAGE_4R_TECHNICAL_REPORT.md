# Stage 4R Technical Report: Representation-Aware Tiny Faces

Date: 2026-08-09

Verdict: `STAGE_4R_TINY_FACE_POLICY_PASSED`

Tiny-face classification: `TARGET_NULL_FACE_POLICY_PROVEN`

Stage 4H face classification: `STAGE4H_TINY_FACE_POLICY_APPLICABLE`

Real-candidate readiness: `DERIVED_GENERATED_CANDIDATE_READY_FOR_AUTHORIZED_ATTEMPT`

## Checkpoint and scope

Stage 4Q was committed and pushed before this work as
`29f0e5f3cb6f51111dfc8dc4834be75565f41c93` (`Add Stage 4Q generated
topology sanitation`). Local `HEAD`, `origin/main`, and remote `main` agreed,
and the worktree was clean.

Stage 4R does not redefine zero area and does not introduce a source-space
epsilon cleanup rule. Stage 4Q remains exactly `cross_squared == 0.0`. Stage 4R
handles only a narrower class: a mathematically nonzero face that unchanged
Stage 4O rejects for geometric-normal stability and that collapses exactly in
the actual target coordinate representation. The immutable Stage 4H GLB was
inspected only; no derived file, catalog entry, model, or ROM was created.

## Actual target representation

The existing asset path first applies manifest axes and `units_to_tiles`, then
anchors X/Z at the footprint center and Y at the source base. Cardinal world
placement is applied separately. The map-model encoder multiplies tile-space
coordinates by `MODEL_TILE_SCALE = 0.25`, adds `MODEL_BASE_Y = 0.25`, and emits
Nitro `VTX_16` (`0x23`) coordinates.

Each model coordinate is encoded as a signed 4.12 fixed-point integer:

```text
q = round(model_coordinate * 4096)
range = [-32768, 32767]
```

The project therefore has a model-coordinate increment of `1/4096` and a
pre-model normalized-tile increment of `1/1024`. Python's specified integer
rounding behavior is nearest with ties to even; Stage 4R compares integer
coordinates after that exact production quantizer. Overflow is rejected.

## Classification and safety policy

`tools.pokeagent.mesh_tinyface` classifies each face as one of:

- `EXACT_ZERO_STAGE4Q_REQUIRED`;
- `TARGET_QUANTIZED_DEGENERATE`;
- `TARGET_NULL_NONBLOCKING_PRESERVED`;
- `TARGET_REPRESENTABLE`.

A face is removable only when all three predicates hold:

```text
source_cross_squared > 0
source_cross_length <= unchanged Stage 4O EPSILON (1e-9)
integer VTX_16 target cross squared == 0
```

The Stage 4O threshold is a numerical-stability validity gate inherited from
the constrained-QEM core, not a renderer or representation tolerance. Stage
4R uses it only to restrict removal to faces that currently block Stage 4O.
A target-null face that Stage 4O can already process remains preserved.

Before removal, the tool verifies that no component disappears or splits.
After removal it independently revalidates manifold/open-manifold topology,
non-branching boundaries, component count, duplicate faces, and deterministic
position compaction. It never moves or welds positions, changes winding,
retriangulates, fills holes, bridges boundaries, or creates attributes.

## Controlled proof

`assets/source/stage4r_target_null_generated.glb` is a project-authored CC0
fixture with two meaningful components, normalized U8 `COLOR_0`, 1,095 input
faces including one exact Stage 4Q face and one nonzero target-null Stage 4R
face. It is 16,496 bytes with SHA-256:

`2912d3e0c32f64154df17b2050fd072f580ece5392c5be09b343a47c57cc66dd`

Stage 4P's proven explicit color policy discards COLOR_0. Stage 4Q removes the
exact face. Stage 4R then sees 566 positions / 1,094 faces and classifies one
Stage 4O blocker, three target-null but nonblocking faces, and 1,090
target-representable faces. The blocker has:

```text
source cross squared  = 1.9478342112530432e-19
source cross length   = 4.4134274790156495e-10
source area           = 2.2067137395078247e-10
target VTX_16 points  = (-115, 6690, 947) three times
target cross squared  = 0
```

Only that blocker is removed. The canonical output is byte-identical to the
independently generated no-face reference, 14,056 bytes, SHA-256:

`e36f56728f47667096501fd1d54c9802d225aee62ec6035a2d4be2a7ab858a5d`

Removal changes neither aggregate nor component bounds. Its source-area
contribution is `1.8843242557792575e-12` of the valid surface. Deterministic
front/rear/left/right/three-quarter silhouette IoUs are all `1.0`. Component
count remains two; removal opens a valid hole, changing valid boundary-loop
count from one to two without branching.

The critical negative fixture has a cross length below `1e-9` but maps to
three non-collinear integer target coordinates with target cross squared one.
It survives as `TARGET_REPRESENTABLE`. Rounding probes at `0.4999`, `0.5`, and
`0.5001` target increments prove below-boundary, exact ties-to-even, and
above-boundary behavior. Signed half probes encode `0.5 -> 0`, `1.5 -> 2`,
`-0.5 -> 0`, and `-1.5 -> -2` integer units.

## Q -> R -> O -> P -> F integration

After Stage 4R, unchanged multi-component Stage 4O reduces the controlled
geometry from 566 positions / 1,093 faces to 34 positions / 58 faces. Both
components survive; target/final face allocations are 42/42 for the body and
17/16 for the detached cap. Aggregate bounds error is zero, maximum geometric
error ratio is `0.056222`, surface-area delta is `0.947238%`, and minimum
five-view silhouette IoU is `0.924189`, all within the existing Stage 4O
policy. It accepts 532 collapses and records 22,044 rejected evaluations.

Stage 4P then assigns `generated_surface`, creates connected planar-patch UVs,
and creates UV-aware crease normals. Unchanged Stage 4F accepts the resulting
58-face GLB. The canonical hash is
`69deff902150a082981a624a391a3b25629f8e6628dcbe1f6c3e21df0cfcd814`.
The unchanged geometry encoder emits 58 triangles / 174 vertices in 3,956
bytes, SHA-256
`a5dc85ac62b050145945808a7011d09a452aea69b3cc91d65b1d0e95fc9cc571`,
inside Stage 4I's 4,096-byte tested capacity. This structural integration does
not add a new runtime world; Stage 4P already proved that same strict output,
material, texture, collision, and model route in HeartGold.

## Invariance, scale, and performance

Face/source ordering and whole-mesh translation produce the same semantic
classification and output. Integer placement translation and cardinal
rotation preserve the classification. Uniform scaling may legitimately
change representability: the controlled blocker is removable at `0.5x` and
`1x`; at `2x` it remains target-null but becomes Stage 4O-valid and is therefore
preserved. Manifest normalization scale is part of the classification, so the
production check occurs at actual encoded scale. Overflow is deterministic.

Two clean output roots match the Q/R/O/P reports and every GLB byte. A full
controlled CLI transaction takes about 4.24 seconds and 37,160 KiB maximum
resident memory on the development host.

## Stage 4H read-only analysis

For a conservative intended size of 4 x 6 x 4 tiles, the immutable Stage 4H
bounds imply `units_to_tiles = 5.047734581094872`. Its Stage 4O-blocking face
is source face 6404, indices `[3262, 3263, 3264]`, with vertices:

```text
(-0.12427455186843872, 0.15190482139587402, -0.3452380895614624)
(-0.12428575754165650, 0.15188658237457275, -0.3452380895614624)
(-0.12428575754165650, 0.15190482139587402, -0.3452157974243164)
```

Edge lengths are `2.1406284364449815e-05`,
`2.8802799804256227e-05`, and `2.4950079975812177e-05`. Source cross squared
is `2.6948343349697145e-19`, cross length is
`5.191179379456767e-10`, and area is `2.5955896897283833e-10`. Its area is
`1.388182280619436e-10` of total surface and
`1.391171464303393e-10` of its component surface.

After production normalization its points are approximately:

```text
(-0.4954692224, 2.6472895365, -1.5977942734)
(-0.4955257856, 2.6471974708, -1.5977942734)
(-0.4955257856, 2.6472895365, -1.5976817486)
```

All three encode to VTX_16 `(-507, 3735, -1636)`. Target cross squared is
zero. Hypothetical removal preserves both components, creates no isolated
position, retains valid non-branching open-manifold topology, changes loops
from 24 to 25 and boundary edges from 96 to 99, changes no bounds, and has
five-view silhouette IoU `1.0`.

The Stage 4H geometry also contains 23 target-null faces that are not Stage 4O
blockers; Stage 4R correctly preserves them. Its eligible COLOR_0 remains only
a hypothetical explicit-discard input. With the one Stage 4R face
hypothetically filtered, its two components and 25 valid loops fit Stage 4Q,
its geometry fits the Stage 4O source envelope, and bounded Stage 4O output can
feed Stage 4P. Therefore the next stage is authorized to attempt a derived
copy, but no such copy exists and no runtime or visual acceptance is implied.

The raw SHA-256 remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
The historical verdict remains `STAGE_4H_GENERATED_ASSET_REJECTED` /
`REJECTED_UNSUPPORTED_STRUCTURE`.

## Tests and recommendation

Focused Stage 4R tests cover reference equality, target-representable tiny
geometry, rounding boundaries, exact-zero ownership, policy-disabled Stage 4O
rejection, topology damage, component disappearance, COLOR_0 authorization,
unsupported attributes, overflow/non-finite input, source/translation/scale
behavior, two-root determinism, Q -> R -> O -> P -> F integration, and exact
Stage 4Q/O/P/J/K/L/M/N regressions. The focused suite passes 15/15. The full
suite passes 301 tests with three expected opt-in integration skips. The Make
proof, Python compilation, preflight (58/58), diff checks, and tracked-artifact
hygiene pass. DeepSeek was not used; token and monetary cost are zero.

Stage 4S, if authorized, may make one explicit derived-copy attempt from the
immutable Stage 4H source using only already-proven Q/R/O/P/F/J/I stages. It
must preserve the raw source and prior rejection, retain provenance for every
filter, and may still reject for fidelity, final 4 KiB budget, or visual QA.
