# Stage 4K Technical Report: Static GLB Hierarchy Preprocessing

## Verdict

`STAGE_4K_STATIC_HIERARCHY_PREPROCESS_PASSED`

Structural classification: `STRUCTURAL_GAP_CLOSED`

Stage 4K proves an explicit, deterministic adapter from one bounded static GLB
node chain into the unchanged strict Stage 4F one-node identity contract.

## Checkpoint and scope

Stage 4J was committed as `f17773573 Add Stage 4J approximate mesh decimation`
and pushed. Local `HEAD`, `origin/main`, and remote `main` agreed and the tree
was clean before Stage 4K.

Stage 4K adds only hierarchy inspection, static TRS composition, transform
baking of existing positions/normals, and canonical GLB serialization. It adds
no normals, UVs, materials, topology repair, decimation, texture/model capacity,
generator retry, or production content.

## Architecture and source boundary

`tools.pokeagent.glb_preprocess` is a pre-Stage-4F structural adapter:

```text
schema-9 hierarchical GLB
  -> bounded structural canonicalizer
  -> ignored canonical one-node identity GLB
  -> unchanged Stage 4F parser
  -> existing typed IR / Nitro / world pipeline
```

It accepts one selected scene, one connected root-to-mesh chain of 1..4 static
TRS nodes, one mesh, up to four triangle primitives, existing required
attributes, and one named material. Source/BIN size is capped at 262,144 bytes;
accessors/buffer views at 16; accessor elements at 256. Remote/external content
is never loaded.

Authored matrices, branching/DAG/cyclic/disconnected graphs, multiple
scenes/meshes, animation, skinning, morphs, extensions, singular/reflected
transforms, missing attributes/material, and unsupported modes fail with stable
codes. Matrix transforms are deliberately deferred instead of partially
supported.

## Transform and writer semantics

The implementation follows the [official Khronos glTF 2.0
specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html): local
transform is `T * R * S`, quaternion order is XYZW, and parent transforms
compose before children. Positions receive the combined affine transform.
Existing normals receive the normalized inverse-transpose 3x3 transform. UV0,
material identity, indices, ordering, and winding are preserved.

The bounded writer reconstructs stable JSON/BIN chunks, 4-byte alignment,
buffer views/accessors, updated float32 POSITION bounds, and one implicit
identity mesh node. It is not a general glTF serializer.

## Controlled proof and equivalence

The project-authored source is a two-node faceted tower with composed parent and
child translation, Y rotation, and positive non-uniform scale:

```text
combined matrix
[[ 0.523923048454, 0, 0.917759341371,  2.265165042945],
 [ 0,              1.21, 0,              0.775         ],
 [-0.787461339179, 0, 0.434605808376, -1.583363094479],
 [ 0,              0, 0,              1                ]]
determinant 1.149984
```

| Artifact | Nodes | Transform | Bytes | SHA-256 |
|---|---:|---|---:|---|
| Hierarchical source | 2 | composed TRS | 2,516 | `3168b05b6b1373a2c12b6256a7df3c214dbae912664e9d06211d6a7ba8fb26d2` |
| Canonical output | 1 | implicit identity | 2,196 | `d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6` |
| Direct-flat reference | 1 | implicit identity | 2,196 | `d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6` |

The unchanged Stage 4F parser rejects the source with `unsupported_scene` and
accepts the canonical output. Canonical output is byte-identical to the direct
flat reference. Normalized semantic IR after excluding only the distinct
authored asset ID, display list, texture bytes, and collision are exact matches.

Golden tests cover identity, translation, 90-degree and arbitrary quaternion Y
rotation, uniform/non-uniform positive scale, parent/child composition,
positions, inverse-transpose normals, unchanged UVs/indices/material, and
failures around topology, transform, and required attributes.

## DS model, world, and binary evidence

The result has 9 positions, 8 normals, 5 UVs, 12 independent triangles, and 36
emitted vertices. Its 828-byte display list uses 77.528% of the inherited
1,068-byte shape region, so no Stage 4I relocation or Stage 4J decimation is
needed. Display SHA-256 is
`f0c0ee20b4188f6a91bf2406e67cc8b48f113398aff61b32adb34bb018a2867d`.

The schema-16 world builds with map-member SHA-256
`ec7fa33d7dce7b04fc159c1492d6c5a9ce9679f1ec66f0869ecf7de6e282dbc9`
and NSBMD SHA-256
`a47221a7f93b969e397b57ff3a49efef5c8220514059a42eb0ad1a2459f5bfc4`.
The ROM is 192,185,312 bytes with SHA-256
`7d5208e2b13a61e987f5224df73c4a3ae62fb32986802511ea03ff36926f9812`.
Map member/PER/BDHC ordering and sizes validate through the unchanged assembly
path.

Material `faceted_shell` maps to the proven `prop_secondary` shape/material and
`stage4d_stone`; texture/palette bytes remain unchanged. Collision is the
manifest-owned, bounds-aligned `[-2.16,2.16]` X by `[-1.83,1.83]` Z
rectangular footprint; its artifact SHA-256 is
`f04b585b1a5466a841c0ef350081af4735c8bbd00ed81adf1a98fbc305a55fc9`.

## Gameplay and visual QA

The declarative Stage 4A scenario passes 15/15 assertions through frame 8,848:
ROM/map/matrix/member identity, approach, front capture, blocked northward step,
walk-around, rear capture, adjacent movement, and 600 further stable frames.
The final state is map 538, member 633, position `(12,13)`, height zero, no warp,
and live BDHC collision evidence.

Capture SHA-256 values:

- front: `0683243861680162d2afc7449f409a42d795ca20fb1cc90c702a212daa66b6a0`;
- rear: `10e8d0915b1e279ea7bc7e7e814220d84a75aaeb127d97e71a04012e6275cac8`.

Visual inspection confirms the transform is baked once: the tower is upright,
correctly oriented/scaled, grounded, fully faced, and coherently stone-textured.
Normals/lighting and UVs are stable; there is no mirroring, double translation,
double scale, exploded geometry, or neighboring-terrain corruption. Collision
aligns with the visible footprint.

## Mutation, determinism, and Stage 4H projection

Changing the parent scale from `[1.2,1.1,0.9]` to `[1.3,1.2,1.0]` changes
source SHA to
`d18e74b9b4b5752af52f7a68a3b782ea565bf34c6811d91a4633e254b5a00359`
and canonical SHA to
`51968c8a99a41236cd10fe177fa4975517beb4dd5949c6d84ef7db16ef6f4151`;
typed geometry, display list, and model change while asset ID, texture/palette,
collision, and world resource IDs stay fixed. Mutated display-list and NSBMD
hashes are respectively
`9797a2bca32060b3c0ec50448715105fed30122aeeca1a4191e912de5f249bba`
and `8f668528ae2bca8ff049fa96b71971632195313e6f3fe8005c47870b3f82812d`.
Adding an identity node to an equivalent hierarchy produces byte-identical
canonical output.

Two clean roots have zero mismatches across 45 Stage 4K artifacts, including
preprocessed GLB/report, IR, display list, NSBMD, PER/BDHC/map member, texture,
collision, world, registry, and ROM inputs.

Read-only inspection of immutable Stage 4H confirms `world -> geometry_0`, two
identity nodes, one mesh, combined determinant +1, and structural applicability.
Its raw hash remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
It remains `STAGE_4H_GENERATED_ASSET_REJECTED` /
`REJECTED_UNSUPPORTED_STRUCTURE`: no material, NORMAL, or TEXCOORD_0; COLOR_0;
accessor/vertex/face overflow; and display-list overflow. It is not cataloged,
altered, simplified, or approved.

## Regression, confidence, and recommendation

Stage 4J, Stage 4I, Stage 4H intake, prior deterministic fixtures, strict GLB,
OBJ, exact/approximate simplification, relocation, texture catalog, registry,
preflight, QA isolation, artifact hygiene, and the full unit suite pass. Legacy
assets without preprocessing retain their existing path and deterministic
outputs. DeepSeek was not used; usage and cost are zero.

Confirmed by official format semantics, source/tests, exact reference
equivalence, unchanged Stage 4F parsing, ROM build, live-memory QA, screenshots,
and determinism: `STRUCTURAL_GAP_CLOSED` for the bounded subset.

Remaining limitations are authored matrices, reflection/negative scale,
branches/DAGs, multiple meshes/scenes, arbitrary hierarchies, external buffers,
extensions, animation/skin/morph, missing material/normals/UV0, preprocessing
beyond the declared source envelope, and the unchanged 4 KiB runtime ceiling.

Stage 4L may proceed only as a separately authorized proof of one remaining
intake gap. It should not combine missing-normal, UV, material, repair, or
production/generated-asset approval work.
