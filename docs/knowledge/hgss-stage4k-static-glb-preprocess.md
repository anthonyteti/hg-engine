# HGSS Stage 4K static GLB preprocessing

## Finding

A bounded static GLB node chain can be reduced deterministically to the strict
single-node identity contract already enforced by Stage 4F:

```text
one selected scene, one 1..4-node root-to-mesh chain
  -> compose parent/child TRS
  -> bake existing POSITION and NORMAL
  -> preserve TEXCOORD_0, indices, topology, and named material
  -> canonical one-node implicit-identity GLB
  -> unchanged Stage 4F parser
```

Preprocessing is explicit schema-9 policy. Strict Stage 4F still rejects the
hierarchical source when preprocessing is disabled.

## glTF transform semantics

The implementation follows the official Khronos glTF 2.0 specification:
local TRS is `T * R * S`, rotations are unit quaternions in `(x,y,z,w)` order,
defaults are identity, and child world transforms are composed parent-first.
Internally the adapter uses row-major matrices acting on column vectors; this
is an implementation representation of the same glTF transform, not a change
to glTF semantics.

Positions use the composed affine transform. Existing normals use the
normalized inverse-transpose of the combined linear 3x3 transform. UV0 and
triangle indices are copied unchanged. POSITION accessor min/max values are
recomputed from canonical float32 output.

Primary format source: [Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).

## Accepted subset and limits

The project-owned standard-library adapter accepts:

- one selected scene;
- one mesh and one mesh-bearing leaf;
- one unique, connected root-to-leaf chain of 1..4 nodes and depth at most 4;
- static TRS with finite translation, unit XYZW quaternion, and strictly
  positive scale;
- at most four independent-triangle primitives, 16 accessors, 16 buffer views,
  and 256 elements per accessor;
- source and BIN payloads no larger than 262,144 bytes;
- authored POSITION, NORMAL, TEXCOORD_0, indices, and one named material.

It rejects authored matrices, branching/DAG/cyclic/disconnected graphs,
multiple scenes/meshes, singular/reflected transforms, animation, skinning,
morphs, extensions, missing attributes/material, unsupported primitive modes,
and external resources. It never performs network or URI loading.

## Canonical writer

`tools/pokeagent/glb_preprocess.py` decodes only supported semantic content and
constructs a clean bounded GLB rather than patching source JSON. It writes a
12-byte GLB header, stable sorted JSON, aligned JSON/BIN chunks, deterministic
buffer-view/accessor ordering, and one implicit-identity node. The ignored
artifacts are `preprocessed.glb` and `preprocess-report.json`.

The project-authored source has two nodes and a nontrivial combined transform:

```text
[[ 0.523923048454, 0, 0.917759341371,  2.265165042945],
 [ 0,              1.21, 0,              0.775         ],
 [-0.787461339179, 0, 0.434605808376, -1.583363094479],
 [ 0,              0, 0,              1                ]]
determinant = 1.149984
```

Source SHA-256 is
`3168b05b6b1373a2c12b6256a7df3c214dbae912664e9d06211d6a7ba8fb26d2`
(2,516 bytes). Canonical SHA-256 is
`d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6`
(2,196 bytes).

## Equivalence and runtime evidence

The canonical GLB is byte-identical to the independently derived direct-flat
reference. Their normalized typed IR (aside from authored asset ID), 828-byte
12-triangle display list, bounds-aligned rectangular collision, and
`stage4d_stone` texture
bytes are identical. Stage 4F rejects the source with `unsupported_scene` and
accepts the canonical output unchanged.

The display list uses 828/1,068 inherited bytes (77.528%), so Stage 4K needs no
decimation or relocated model capacity. The ROM QA passes 15/15 assertions
through frame 8,848: map identity, approach, collision, walk-around, two
captures, adjacent traversal, and 600 stable frames. Visual inspection confirms
one upright, grounded, correctly transformed tower with coherent normals/UVs
and no mirroring or double transform.

Two independent world roots match across 45 deterministic artifacts. An
equivalent hierarchy with an inserted identity node produces byte-identical
canonical output. A temporary parent-scale mutation changes source,
canonical geometry, display list, and downstream model while preserving asset,
texture, collision, and world identities. The collision rectangle is
`[-2.16,2.16]` X by `[-1.83,1.83]` Z, conservatively tracking the normalized
ground bounds from inside the validator boundary.

## Stage 4H projection and confidence

The immutable Stage 4H GLB is `world -> geometry_0`, with two identity nodes,
one mesh, and determinant +1. Its hierarchy is therefore structurally
preprocessable. Its SHA remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.

It remains rejected and uncataloged because it has no named material, NORMAL,
or TEXCOORD_0; exposes COLOR_0; exceeds accessor/vertex/face budgets; and
projects far beyond the 4 KiB model budget. Stage 4K closes only the structural
gap and does not retroactively approve that candidate.

Confidence is confirmed by official format semantics, golden math tests,
independent Stage 4F parsing, exact flat-reference equivalence, ROM build,
live-memory QA, screenshots, and two-root determinism. Unknown/unproven areas
include arbitrary matrices, reflective transforms, branches, multiple meshes,
external resources, and animated or skinned scenes.

## Reproduction

```bash
python -m tools.pokeagent asset preprocess assets/manifests/stage4k_hierarchical_tower.json --json
python -m tools.pokeagent asset inspect assets/manifests/stage4k_hierarchical_tower.json --json
python -m unittest tests.test_pokeagent_stage4k_glb_preprocess
python -m tools.pokeagent map determinism --fixture fixtures/stage4k_static_hierarchy_world.json --json
make stage4k-static-hierarchy-proof
python -m tools.pokeagent qa run qa/scenarios/stage4k_static_hierarchy.json --json
```

Evidence remains coupled to the supported US HeartGold revision and the
hash-locked local templates established by prior stages.
