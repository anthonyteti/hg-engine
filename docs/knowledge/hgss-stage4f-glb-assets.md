# HGSS Stage 4F bounded GLB static assets

## Finding and confidence

A tracked GLB 2.0 static mesh can be decoded deterministically into the same
source-neutral mesh records and typed triangle IR used by the project OBJ
pipeline. No GLB-specific Nintendo DS path exists: shared normalization,
winding/normal validation, budgets, Nitro display-list encoding, project
texture binding, placement, footprint collision, map-member assembly, and QA
consume the result unchanged.

Confidence is **high for the exact embedded, indexed, identity-node static GLB
subset proven by official-format inspection, malformed-byte tests, semantic
OBJ equivalence, a clean ROM build, live gameplay/collision, and two visually
inspected runtime views**. It is not evidence for arbitrary GLTF scenes,
transforms, extensions, PBR materials, embedded textures, animation, or repair.

## Format and dependency evidence

The authoritative format source is the Khronos
[glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
The implemented facts are:

- glTF uses a right-handed coordinate system, meters, +Y up, and +Z forward;
- front faces use counter-clockwise winding;
- texture coordinate `(0,0)` is the upper-left corner;
- node local transforms are either a matrix or `T * R * S`;
- GLB is little-endian with a 12-byte header, JSON first, then optional BIN;
- chunks and their starts are four-byte aligned;
- buffer views bound byte regions and may declare `byteStride`;
- accessors define component type, element type, count, and byte offset;
- index accessors may use unsigned byte, unsigned short, or unsigned int;
- floating-point accessor data must not contain NaN or infinity.

`pygltflib` 1.16.5 was evaluated as the most obvious small Python option. It
is MIT licensed and supports both GLTF and GLB, but it is a broad object-model
dependency and does not replace this project's subset, path, size, bounds,
material, transform, or safety validation. Stage 4F therefore adds no package:
`tools.pokeagent.glb` is a project-owned reader built only with Python's
`json`, `struct`, and `math` modules. There is no Blender, native converter,
`g3dcvtr`, remote fetch, or copied third-party implementation.

## Supported container and scene subset

The canonical accepted form is:

```text
GLB 2.0
  JSON chunk
  BIN chunk
  scene 0
    node 0 (implicit identity; leaf)
      mesh 0
        1..4 primitives, mode 4 TRIANGLES
  material 0 (name only)
```

Hard proof limits are 256 KiB source/BIN, one scene, node, mesh, material, and
buffer, up to four primitives, 16 accessors, 16 buffer views, and 256 elements
per accessor. The parser requires exactly one JSON and one BIN chunk and zero
BIN padding. This is intentionally stricter than generic glTF.

All geometry is indexed. Each primitive requires exactly:

| Semantic | Accepted accessor |
|---|---|
| `POSITION` | float32 `VEC3`, matching declared min/max |
| `NORMAL` | float32 unit `VEC3` |
| `TEXCOORD_0` | float32 `VEC2` |
| indices | unsigned 8/16/32-bit `SCALAR` |

Attribute counts must match; index count must be divisible by three and every
index must be in range. Tightly packed views and interleaved views with a
4-byte-multiple stride in 4..252 are tested. Accessor/view offset, component
alignment, stride, declared length, range, and finite-float checks happen
before mesh construction. Sparse and normalized accessors are rejected.

The following fail with stable error codes: bad GLB magic/version/length,
malformed/missing chunks, URI-backed buffers, extensions, extra scenes/nodes/
meshes/materials, node transforms or children, animations, skins/weights,
morph targets, images/textures/samplers, PBR material fields, non-triangle
modes, missing/extra attributes, sparse/unsupported accessors, invalid stride/
alignment/bounds, bad indices, non-unit normals, degenerate/reversed faces,
unmapped material names, and DS display-list overflow.

## Source-neutral mapping

`tools.pokeagent.asset_source` defines only `MeshCorner`, `MeshFace`, and
`SourceMesh`. Both source adapters terminate there:

```text
OBJ bytes -> parse_obj --┐
                        ├-> SourceMesh -> _normalized_ir -> typed IR schema 2
GLB bytes -> parse_glb --┘
```

The GLB reader traverses source arrays by declared primitive and index order.
It stable-deduplicates position, UV, and normal tuples by first occurrence so
indexed or exporter-duplicated attributes do not create nondeterministic
downstream identity. It tags the source UV origin as upper-left; shared
normalization flips `V` exactly once into the existing OBJ lower-left semantic
IR. The existing texture encoder later performs the already-proven canonical
IR-to-Nitro texel transform.

Node transforms are deliberately not partially interpreted: any matrix, TRS,
children, or multiple root structure fails. The manifest still owns source
units/axes, asset anchoring, and world placement. This avoids a second HGSS
coordinate pipeline.

## Canonical asset and OBJ equivalence

`assets/source/stage4f_glb_faceted_tower.glb` is a 2,248-byte project-authored
CC0 file containing one static tower primitive. It has 36 source attribute
elements and 36 unsigned-16 indices. Stable deduplication produces 9 positions,
5 UVs, 8 normals, and 12 independent triangle faces. Bounds are 3 x 6 x 3
tiles. Its manifest maps GLB material `faceted_shell` to existing project
texture `stage4d_stone`, shape 6/material 17, and the existing 3 x 3 collision
footprint.

The reference Stage 4E OBJ has four wall quads plus four roof triangles.
Tests split each OBJ quad only for comparison and prove exact semantic equality
with the GLB after six-decimal float32 normalization: ordered positions,
triangle winding, UVs, normals, source material, project alias/texture, bounds,
and collision all match. Display-list bytes intentionally differ because OBJ
preserves four quad commands while GLB supplies 12 triangles.

| Metric | GLB result |
|---|---:|
| GLB SHA-256 | `89c32d0d3d29a0d57b63605cb6b195f17821296beaee97ce561db108a352df1d` |
| normalized semantic SHA-256 | `6a7f72d7b17c215efc2d7150ceee122ee568c34805e127b294afcf2dd7d40b4d` |
| triangles / emitted vertices | 12 / 36 |
| display-list bytes / capacity | 828 / 1,068 |
| utilization | 77.528% |
| display-list SHA-256 | `a2f57b278d759f105e11b073fb41b65725e44a9a8dcfc87e238fc7e7bacceae7` |
| transformed NSBMD SHA-256 | `c78e5511f731d8f920e133c72826c2ca1c3419ea09539a0fb32f0a87bcbd74d0` |
| collision SHA-256 | `a7cd86681a16abad2ad7f0796fcde753fd41fe569e817dfb3bd3f48d884d45f3` |

The existing display-list inspector independently confirms one TRIANGLES block,
12 triangles, 36 vertices, 12 normals, 36 texture coordinates, 36 vertex
commands, and terminal END. Model counters include 104 vertices, 29 polygons,
12 triangles, and 17 quads after ground and template safety shapes.

## Runtime, mutation, and determinism

The controlled fixture loads header 538, matrix 1, member 633 and places the
tower at `(16,16)` with player start `(16,22)`. The declarative scenario passed
15/15 assertions: five-tile approach, position `(16,17)`, north collision,
east/north/west walk-around to `(16,13)`, rear-side traversal to `(12,13)`, two
valid captures, and another 600 stable frames through frame 8,809. The ROM
contained the exact generated member 633. Appended area-data and area-texture
member 106 also matched generated bytes in 107-member NARCs.

Front and rear screenshots show the complete pyramidal facets and rectangular
body with consistent stone texture/lighting. No face disappears, the asset is
upright and grounded, UVs do not explode, and neighboring terrain remains
intact. Screenshot hashes are traceability only, not correctness oracles.

A temporary deterministic GLB rebuild raised the apex from 6.0 to 6.5 tiles:

| Artifact | Canonical | Mutated |
|---|---|---|
| source | `89c32d0d...` | `1ad2629836...` |
| normalized IR | `6a7f72d7...` | `896dba5b5...` |
| display list | `a2f57b27...` | `202ccb5e...` |
| transformed model | `c78e5511...` | `fa5a591c...` |

Texture and palette bytes, asset identity, world IDs, and collision hash
`a7cd8668...` did not change. Temporary files were isolated under ignored/
temporary paths and the tracked GLB remained canonical.

Two clean Stage 4F roots matched all 43 deterministic artifacts with zero
mismatches. The installed manifest reports 46 hashes including install-only
script/text outputs. All earlier fixtures also returned zero mismatches.

## Boundaries and reproduction

Confirmed through source/specification, bytes, tests, build, runtime, and
visual inspection:

- local embedded GLB triangles enter the same IR and renderer as OBJ;
- upper-left glTF UVs, winding, normals, texture binding, scale, and collision
  survive the full HeartGold pipeline;
- source mutation is independently observable without identifier churn;
- no network, GUI, converter, or new dependency is required.

Confirmed only by parser/unit tests:

- U8/U16/U32 indices and bounded interleaved vertex views decode identically;
- multiple triangle primitives up to the bounded count share stable traversal;
- malformed container/scene/accessor combinations fail before world output.

Unsupported or unknown:

- `.gltf` JSON packages, data/external/remote URIs, extra GLB chunks;
- node transforms or hierarchies, multiple scenes/nodes/meshes/materials;
- strips/fans/lines/points, non-indexed primitives, sparse/normalized accessors;
- embedded images, PBR state, secondary UVs, tangents, vertex colors;
- animation, skins, morphs, extensions, Draco/meshopt compression;
- repair, simplification, normal/UV generation, detailed mesh collision,
  display-list relocation, production assets, or generated 3D.

Reproduce with:

```bash
.venv/bin/python -m tools.pokeagent asset inspect assets/manifests/stage4f_glb_faceted_tower.json --json
.venv/bin/python -m tools.pokeagent map determinism --fixture fixtures/stage4f_glb_world.json --json
make stage4f-glb-proof
.venv/bin/python -m tools.pokeagent qa run qa/scenarios/stage4f_glb_asset.json --timeout 300 --json
```

Generated IR, models, NARCs, ROMs, screenshots, logs, and battery saves remain
ignored.
