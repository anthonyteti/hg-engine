# Stage 4L Technical Report: Deterministic Missing-Normal Generation

## Verdict

`STAGE_4L_NORMAL_GENERATION_PASSED`

Normal classification: `NORMAL_GAP_CLOSED`

Stage 4L proves an explicit bounded adapter that converts one otherwise-valid
static GLB lacking `NORMAL` into the unchanged strict Stage 4F contract with
deterministic, crease-aware float32 normals.

## Checkpoint and scope

Stage 4K was committed as
`a8f399571871fac90cf1458af9d40366b5842762 Add Stage 4K static GLB preprocessing`
and pushed. Local `HEAD`, `origin/main`, and remote `main` agreed, and the tree
was clean before Stage 4L began.

Stage 4L adds no UV/material generation, topology/winding repair, decimation,
generator retry, texture/model capacity, or production content. The immutable
Stage 4H candidate remains rejected and untouched.

## Architecture and source contract

`tools.pokeagent.glb_normals` is a pre-Stage-4F adapter:

```text
schema-10 identity GLB without NORMAL
  -> bounded triangle/manifold validation
  -> crease-aware normal generation
  -> deterministic canonical GLB with NORMAL
  -> unchanged Stage 4F parser
  -> existing typed IR / Nitro / world pipeline
```

The accepted source has one selected scene, one implicit-identity mesh node,
one mesh, one named material, one to four independent indexed-triangle
primitives, POSITION and TEXCOORD_0, and no NORMAL. Source/BIN size is capped at
262,144 bytes; accessors and buffer views at 16; elements at 256; faces at 256;
and adjacency edges at 768. Stage 4K can precede this adapter in a future
composed policy, but the controlled proof starts directly from identity
geometry.

Missing position/UV/material, authored normals, hierarchy/transforms,
animation/skin/morph, unsupported modes, invalid indices, degeneracy,
inconsistent winding, and non-manifold edges fail with stable codes. The
missing-normal policy never overwrites authored normals.

## Normal convention and policy

For ordered triangle `(p0,p1,p2)`, the implementation uses
`normalize(cross(p1-p0,p2-p0))`, preserving existing Stage 4F winding. The
canonical policy was declared before runtime review:

```text
crease angle: 60 degrees
weighting: area
preserve UV seams: true
preserve open boundaries: true
```

Interior edges with two incidents are eligible for smoothing only when
material and endpoint UV identities match and face-normal agreement is at least
`cos(60 degrees)`. More than two incidents fail as non-manifold; same-direction
edge traversal fails as inconsistent winding. Open edges are not bridged.

For each `(position, UV, material)`, deterministic adjacency through eligible
edges creates connected smoothing fans. The normalized sum of unnormalized
face area vectors becomes the fan normal. Hard fan boundaries create sorted
attribute-vertex duplicates; geometric positions, UV values, surfaces,
material, and winding remain unchanged.

## Controlled proof and reference equivalence

The project-authored faceted stone turret has planar vertical walls, 45-degree
wall corners, a sloped roof, a hard wall/roof transition, and a controlled UV
wrap seam. It contains 24 triangles and 19 source attribute vertices.

| Artifact | NORMAL | Bytes | SHA-256 |
|---|---|---:|---|
| Missing-normal source | absent | 1,244 | `efa69d281a43f75316d589e5f671394ac5de90a5164631f7a5cd9f42774f2374` |
| Generated canonical | generated | 1,852 | `b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9` |
| Authored reference | authored | 1,852 | `b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9` |

The unchanged Stage 4F parser rejects the source with `missing_attribute` and
accepts the generated output. Generated output is byte-identical to the
independently authored-normal reference; normalized typed IR (apart from asset
ID), display list, texture bytes, and collision are also exact matches.

Quantitative normal evidence:

| Metric | Result |
|---|---:|
| Canonical attribute vertices | 27 |
| Net split vertices | 8 |
| Unique generated normals | 25 |
| Smoothing fans | 27 |
| Smooth edges | 23 |
| Hard edges | 9 |
| Open boundary edges | 8 |
| UV-seam-forced hard edges | 2 |
| Maximum float32 length error | `1.712942865328415e-08` |
| Maximum reference angular error | `8.537736462515939e-07` degrees |
| Mean reference angular error | below `1e-6` degrees |

The vectors themselves are float32 tuple-equal; the tiny reported angular
value is the numerical ceiling of the independent acos calculation.

## DS binary, texture, and collision evidence

The typed IR has 17 normalized position records and 24 triangles. The Nitro
encoder emits 72 vertices into a 1,644-byte independent-triangle display list,
65.865% of the inherited 2,496-byte `prop` shape. Display-list SHA-256 is
`1654e35a4ffedde14bfdbea85eefa0a96ae176802e5576ca9fbaa66e9cdd4aa6`.
Neither Stage 4I relocation nor Stage 4J decimation is used.

`turret_stone` maps to the existing `prop` material and `stage4d_stone`
project texture. Texture/palette bytes are unchanged. Collision remains the
manifest-owned `[-1.9,1.9]` X by `[-1.9,1.9]` Z rectangle; its semantic hash is
`47b3be634009edff0ee494dfde01024b44f48c737ed3a1ad5200adf049181250`.

The generated world has zero two-root mismatches across normal GLB/report,
typed IR, display list, NSBMD, PER/BDHC/map member, texture, collision,
world/registry, NARCs, and ARM9. Deterministic NSBMD and map-member hashes are
`c321d10bc7c08a71a48b7c25c8f8987d84474236e39865846d53d77581b79cad`
and `cd57c2f34fafc681f880acdccf18c1154a2a4f204682833ba62ed0f1e8060293`.

## Gameplay and visual QA

The Stage 4A scenario validates map 538 / matrix 1 / member 633, approaches the
turret, captures front and rear views, proves the northward footprint block,
walks around onto adjacent terrain, and remains live for another 600 frames.
It passes 15/15 assertions through frame 8,848 in 71.55 seconds. Final state is
map 538, member 633, position `(12,13)`, height zero, no warp, and live BDHC
collision evidence. ROM SHA-256 is
`c319afdf173475c79389281535578e6adc793e612cd54f6ad2ff9295fff10c3a`.
Front/rear capture SHA-256 values are respectively
`955c98dc6945a3c606f36d9e8bc671b01717cc4f452915bfd4b3738be825a0ee`
and `517973379cbf2743f92affd14940e63d5461d475a868d629469c79706aa7bc39`.

Visual inspection confirms coherent faceted wall and roof lighting, a sharp
wall/roof transition, correct stone UVs, complete outward-facing geometry,
upright scale, ground contact, aligned collision, and intact terrain. No
inverted lighting, missing/mirrored faces, or smoothing across the hard roof
crease is visible. The typed IR preserves smoothing-fan semantics for Stage 4J
boundary decisions; the current Nitro encoder still emits one geometric NORMAL
per face, so Stage 4L does not claim interpolated per-vertex DS shading.

## Mutation and order evidence

Changing the declared crease threshold from 60 to 30 degrees leaves the source
unchanged but deterministically reduces smooth-edge classification and
increases split vertices; positions, UVs, topology, material, texture, and
collision do not change. Raising the temporary roof apex from 4.0 to 4.2
changes source, generated normals, canonical GLB, typed IR, display list, and
model while asset/texture/collision/world identities remain fixed. Canonical
source is restored.

Reversing source triangle order produces byte-identical canonical GLB. Planar,
90-degree hard-edge, below-threshold smooth-edge, UV-seam, non-manifold,
inconsistent-winding, and degeneracy fixtures independently cover the policy.

## Stage 4H projection

The immutable Stage 4H TripoSR hash remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60` and
the result remains `STAGE_4H_GENERATED_ASSET_REJECTED` /
`REJECTED_UNSUPPORTED_STRUCTURE`. Its normal-generation topology envelope is
not applicable or fully evaluated: 6,664 faces exceed the Stage 4L 256-face
limit and 3,360 positions exceed the 256-element accessor limit. Independent
remaining blockers include hierarchy at the raw boundary, no named material,
no TEXCOORD_0, COLOR_0-only attributes, and enormous geometry/display-list
cost. No derived Stage 4H file was created or compiled.

## Regression, confidence, and recommendation

All 226 unit tests pass (three opt-in integrations skipped), including Stage
4K canonical byte invariance, Stage 4J/4I/4H/4G, strict GLB, OBJ, exact and
approximate simplification, model relocation, texture catalog, registry, QA
isolation, and artifact hygiene. Preflight passes in the project virtual
environment. DeepSeek was not used; tokens and cost are zero.

Confirmed by math tests, exact authored-reference equality, unchanged Stage 4F
parsing, deterministic binary/world generation, ROM build, live-memory QA, and
screenshots: `NORMAL_GAP_CLOSED` for the bounded subset.

Remaining limitations include topology beyond a small manifold triangle mesh,
inconsistent winding, multiple materials, alternate weighting policies,
authored-normal repair/replacement, UV/material generation, preprocessing above
the declared source envelope, and the unchanged 4 KiB project model ceiling.

Stage 4M should proceed only as a separately scoped proof of the next observed
intake gap, likely bounded UV generation. It must not combine material
synthesis, topology repair, Stage 4H approval, another generator attempt, or
production art.
