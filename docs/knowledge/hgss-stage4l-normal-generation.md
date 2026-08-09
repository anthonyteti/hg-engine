# HGSS Stage 4L deterministic normal generation

## Finding

A bounded static GLB that satisfies the strict Stage 4F source contract except
for `NORMAL` can be canonicalized deterministically before Stage 4F:

```text
POSITION + TEXCOORD_0 + indices + named material, no NORMAL
  -> validate triangle surface and manifold adjacency
  -> derive winding-based face normals
  -> classify 60-degree creases and UV seams
  -> build area-weighted smoothing fans
  -> split attribute vertices at hard fan boundaries
  -> canonical GLB with float32 NORMAL
  -> unchanged Stage 4F parser
```

Stage 4F still rejects the original source with `missing_attribute`. Normal
generation is explicit manifest schema 10 preprocessing, not parser leniency.

## Supported contract and bounds

The project-owned standard-library adapter accepts GLB 2.0 with one selected
scene, one implicit-identity mesh node, one mesh, one named material, one to
four independent indexed-triangle primitives, POSITION and TEXCOORD_0, and no
NORMAL. Limits are 262,144 source/BIN bytes, 16 accessors, 16 buffer views, 256
elements per accessor, 256 faces, and 768 geometric adjacency edges.

Interior manifold edges have exactly two incident faces; open edges have one.
More than two incidents, same-direction traversal of a shared edge,
degeneracy, non-finite coordinates, invalid indices, missing UV/material,
existing NORMAL, extensions, hierarchy/transforms, animation, skins, morphs,
or other primitive modes fail with stable codes. No URI or network loading is
performed.

## Geometry and smoothing semantics

For ordered corners `(p0,p1,p2)`, the face area vector is
`cross(p1-p0,p2-p0)` and its normalized direction is the face normal. An
interior edge is smooth only when both adjacent faces share material and UV
identities and their normal dot product is at least `cos(60 degrees)`. UV seams
force a hard split even when geometry is coplanar. Open boundaries remain
boundaries.

For every `(position, UV, material)` identity, face adjacency through eligible
smooth edges creates deterministic connected smoothing fans. Each fan normal is
the normalized sum of its unnormalized face area vectors. A geometric position
is duplicated in the output only when its faces require different normal/UV
attribute identities. Positions and UV values never move; topology and winding
remain semantically unchanged.

Faces, fan traversals, semantic vertices, and canonical GLB dictionaries are
sorted by stable semantic keys. JSON/BIN serialization and float32 normals are
therefore independent of source triangle ordering. Existing Stage 4K writer
bytes remain unchanged because Stage 4L uses a separate bounded transformation.

## Canonical proof

The project-authored turret source has 24 triangles, 19 source attribute
vertices, valid UV0, one `turret_stone` material, and no normals. Source SHA-256
is `efa69d281a43f75316d589e5f671394ac5de90a5164631f7a5cd9f42774f2374`
(1,244 bytes).

At the declared policy, the result has 27 attribute vertices (8 net splits),
25 unique normal values, 27 smoothing fans, 23 smooth edges, 9 hard edges, 8
open boundary edges, and 2 UV-seam-forced hard edges. Maximum float32 normal
length error is `1.712942865328415e-08`. Canonical SHA-256 is
`b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9`
(1,852 bytes), byte-identical to the independently authored-normal reference.
Reference normal vectors are exactly equal; the angle calculation's numerical
ceiling is `8.537736462515939e-07` degrees.

The unchanged typed-IR/Nitro path produces 24 triangles, 72 emitted vertices,
and a 1,644-byte display list (65.865% of the inherited 2,496-byte prop shape),
so neither Stage 4I relocation nor Stage 4J decimation participates. Texture
identity remains `stage4d_stone`; collision remains the manifest rectangle
`[-1.9,1.9]` on X and Z.

The current Nitro encoder writes one geometric NORMAL command per face rather
than interpolating these source vertex normals. The generated smoothing fans
therefore preserve correct semantic normal boundaries for validation and future
Stage 4J processing, while runtime lighting remains deliberately faceted. This
stage does not claim a new smooth-shading renderer.

## Evidence and reproduction

Unit evidence covers planar smoothing, 90-degree/hard and below-threshold
edges, UV seams, source-order invariance, exact authored-reference equality,
threshold and roof-height mutations, non-manifold/winding/degenerate failures,
manifest opt-in, strict Stage 4F before/after behavior, and immutable Stage 4H
rejection. Two independent world roots have zero deterministic mismatches.

```bash
python3 -m tools.pokeagent asset normals assets/manifests/stage4l_missing_normals_turret.json --json
python3 -m unittest tests.test_pokeagent_stage4l_normals
python3 -m tools.pokeagent map determinism --fixture fixtures/stage4l_normal_generation_world.json --json
make stage4l-normal-generation-proof
python3 -m tools.pokeagent qa run qa/scenarios/stage4l_normal_generation.json --json
```

Confidence is confirmed by geometry math, exact reference bytes, unchanged
Stage 4F parsing, binary/world determinism, ROM build, live-memory gameplay QA,
and inspected screenshots. Remaining unknowns are arbitrary scene structures,
multi-material smoothing, non-manifold or inconsistent topology, alternate
weighting policies, authored-normal repair/replacement, and sources beyond the
declared preprocessing envelope.
