# HGSS Stage 4B external static-asset ingestion

## Finding

A small, project-authored OBJ can be parsed and normalized without Blender,
compiled through the Stage 3D Nitro quad encoder, placed symbolically in a map,
and made collision-active from the same manifest placement. The runtime-tested
proof merges the object into an existing shape of the hash-locked map NSBMD;
it does not use BLD, create a standalone model, or author materials/textures.

Confidence is **high for the exact bounded quad-only subset and template
revision exercised here**. Triangle meshes, arbitrary OBJ features, new
materials, new textures, BLD, and independent prop models remain unknown.

## Canonical inputs

The project-local asset catalog maps a stable asset ID to a tracked manifest:

```text
assets/catalog.json
  stage4b_test_shed -> assets/manifests/stage4b_test_shed.json
```

The schema-1 manifest records:

- stable ID, tracked source path, `obj` format, category, proof status;
- explicit project-authored provenance and redistributable license;
- source units, signed up/forward axes, and right-handed convention;
- deterministic units-to-tile scale and footprint-center/base anchor;
- source-material to approved-template-alias mapping;
- rectangular collision proxy;
- the exact conservative Stage 4B budget.

The world fixture contains only the asset symbol and placement ID, X/Z, and a
cardinal rotation. Geometry-local asset IDs never consume an HGSS resource ID.

## OBJ subset and neutral IR

`tools.pokeagent.assets` accepts UTF-8 OBJ records `v`, `vt`, `vn`, `usemtl`,
and `f`; comments and harmless object/group/smoothing records are ignored.
Faces must be planar nondegenerate quads with positive `v/vt/vn` indices,
explicit 0..1 UVs, and coherent normals/winding. Unsupported statements,
triangles, N-gons, relative indices, missing attributes, nonfinite values, or
unmapped materials fail with a stable `AssetError.code`.

Parsing produces source vertices, UVs, normals, material groups, and faces.
Normalization then derives a canonical IR with:

```text
X/Z = ground plane
Y   = vertical
origin = footprint center at terrain height
unit = one overworld tile
faces = stable source order with normalized vertices/UVs/normals
```

Signed source up/forward axes define a right-handed basis. Unit conversion,
axis conversion, anchoring, winding, normal checks, and fixed-point range checks
complete before HG-specific encoding. No filesystem iteration participates in
mesh or placement ordering.

## Proven budget and model binding

The conservative proof budget is 256 KiB source, 64 positions, 64 UVs, 32
normals, 24 quads, one material, eight tiles in X/Z, eight tiles high, and 64
blocked collision tiles. This is a Stage 4B policy, not a claim about global DS
limits.

The shed has 16 source vertices, four UVs, six normals, and 12 quads. Its bounds
are 4.5 x 3.0 x 3.5 tiles. The Nitro display list is 1,068 bytes and uses
42.788% of shape 1's verified 2,496-byte region. The encoder is the Stage 3D
quad command subset: texture coordinate, normal, and vertex commands inside a
quad primitive. Triangle commands were intentionally not added.

The source material `shed_shell` is explicitly mapped to local alias `prop`,
which binds existing template shape 1 / material 18 / `road01_r`. Ground
remains shape 5 / material 12 / `grass01`. No Nintendo texture bytes or local
NSBMD template bytes enter tracking.

## Placement and collision synchronization

Placement applies a deterministic cardinal rotation and map translation to the
normalized vertices. The same placement transforms the manifest footprint,
then blocks every covered tile center in PER. One placement at `(16,16)` blocks
12 tiles; nearby `(16,17)` remains walkable. Invalid rotations, off-map proxies,
overlaps, missing catalog assets, duplicate placement IDs, and combined shape
overflow fail before model transformation.

Stage 4B emits an empty BGS payload, preserving the normal-overworld runtime
invariant that PER begins at physical map-member offset `0x14`. Retaining the
template's logical BGS payload caused live movement to ignore the intended
footprint; the declarative QA collision assertion exposed this immediately.
The corrected layout has a permanent unit regression.

## Generated artifacts and CLI

```bash
python3 -m tools.pokeagent asset validate \
  assets/manifests/stage4b_test_shed.json --json
python3 -m tools.pokeagent asset inspect \
  assets/manifests/stage4b_test_shed.json --json
python3 -m tools.pokeagent asset compile \
  assets/manifests/stage4b_test_shed.json \
  --output build/assets/stage4b_test_shed --json
```

Ignored output contains normalized-mesh JSON, a standalone display list,
collision JSON, and a budget/hash report. Report artifact names are relative,
so the report itself remains identical across clean output roots. Schema-8 world generation also emits
placement IR, a world asset-capacity report, the placed display list, transformed
NSBMD, PER/BDHC/map member, registry snapshot, and rebuilt world NARCs.

Canonical hashes for the proof asset are:

- source: `b8f88aeae3d0c8d6e79ec1daae220449444b75be8c43acb26481899ec8602da9`;
- normalized IR: `85e40ac18e9037d4be6f62f02c23086f8e37663a9997726db6e35f834113daa6`;
- display list: `628581e2dcdd4cc0047e638c3579b30729fd86ca83e8bc5b6f441186c0d290dc`;
- transformed NSBMD: `b2d804347c07788de6247764f00424ee771d4728fc36d8084b466f9912140217`;
- map member: `de8b5c55bfdec36f2bec59908074c3ee54b6080e8d9afdab5e79cfac58c2ac4a`.

Two clean roots matched across all 24 generated world artifacts.

## Runtime and visual evidence

The Stage 4A scenario enters map 538 at `(16,20)`, approaches the shed, captures
it, proves north movement from `(16,17)` is blocked by the footprint, walks east
and north beside/behind the object, captures again, and remains stable for 600
frames. Both 256 x 384 screenshots show the shell upright, grounded, coherent,
and visible from opposite sides. The inherited road material is deliberately
plain dark green; this is geometry ingestion evidence, not final art.

## Source-driven mutation

Changing only roof-top source Y from 3.0 to 3.25 changed:

- source hash to `a88a371c039b4f821c19808d9dd586d55d2280216ae49510a0d313623282d0dd`;
- normalized hash to `dbac2ba5308adee18c77795c90782d33494da33784c26473d734868920586f2c`;
- display-list hash to `e12ed1ac29a6a218734d07a8d7eeedb2a6fc3fd329ffb9d6c18c128229b801f4`.

The symbolic asset ID and collision hash remained unchanged. The mutation was
temporary; canonical source retains the accepted 3.0-tile roof height.

## Confirmed, inferred, and unknown

Confirmed by source, binary tests, build, and runtime:

- deterministic quad OBJ parsing/normalization and template shape encoding;
- one reusable symbolic placement and manifest-derived rectangular collision;
- map-member PER placement, visible rendering, collision, nearby traversal,
  and 600-frame stability;
- source mutation propagates to generated geometry without resource renumbering.

Confirmed by validation/unit tests only:

- all signed perpendicular up/forward-axis combinations accepted by the schema;
- cardinal placement rotations other than the canonical zero-degree placement;
- duplicate placement/asset and capacity-overflow failures.

Unknown or deliberately unsupported:

- triangles/N-gons, multiple materials, new texture/palette authoring;
- independent BLD/static-prop resources, animation, skeletons, transparency;
- arbitrary transforms, nonrectangular collision, mesh simplification;
- capacity beyond the verified template shape regions or another ROM revision.
