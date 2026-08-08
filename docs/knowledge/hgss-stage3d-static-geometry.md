# HGSS Stage 3D static-terrain geometry subset

## Finding

A hash-verified retail NSBMD template can support a reusable, deterministic
static-terrain compiler without becoming a general NSBMD writer. Canonical
rectangular surfaces and axis-aligned transitions can drive visual quads, PER,
and HGSS BDHC together. Three existing template shapes/materials are sufficient
for ground, transitions, and derived cliff faces.

Confidence is **high** for the exact template, command subset, shape capacities,
fixture topology, two tested transition directions, BDHC plate/stripe encoding,
and runtime behavior described below. Confidence is **unknown** outside this
bounded subset.

## Canonical and generated flow

```text
schema-5 symbolic world source
  -> Stage 3C registry resolution
  -> geometry validation
  -> rectangular surface/transition IR
  -> deterministic horizontal/ramp/wall quads
  -> three bounded Nitro display lists
  -> hash-locked NSBMD shape replacement
  -> PER + BDHC from the same terrain features
  -> unchanged HGSS map-member/container pipeline
```

Canonical fixture: `fixtures/stage3d_static_geometry_world.json`.
Implementation: `tools/pokeagent/geometry.py`.

Global map/header/member/script/text references remain symbolic. Geometry-local
IDs such as `west_ramp` and `raised_terrace_stem` do not consume HGSS IDs.

## Geometry IR and validation

The Stage 3D subset supports:

- integer-boundary rectangular horizontal surfaces;
- integer-boundary X or Z transitions with linear height interpolation;
- a fixed 32 x 32 tile domain and height range -8 through 8;
- `ground`, `transition`, and derived `cliff` material aliases only;
- quads only, emitted in source-stable order;
- perimeter PER blocking and interior BDHC height/ledge resolution.

Every tile center must be covered by exactly one top feature. Gaps, overlaps,
duplicate IDs, invalid coordinates/heights, unsupported axes/materials,
degenerate transitions, display-list overflow, and malformed collision policy
fail before binary encoding with a machine-readable `GeometryError.code`.

The materialized `geometry-ir.json` records both visual features and BDHC
plates. They are currently one-to-one; a regression test compares ID, bounds,
height endpoints, and axis for every entry. Walls are derived from adjacent
tile-center height discontinuities above the canonical threshold. PER and BDHC
are not separately authored.

## Nitro display-list subset

Each selected shape receives exactly:

```text
BEGIN(QUADS)
  for each quad:
    NORMAL
    four times: TEXCOORD, VTX_16
END
```

Command bytes are little-endian opcode words followed by 32-bit parameters.
`VTX_16` uses signed fx16 values. Texture coordinates use signed s16 values in
1/16 units. Normals use normalized signed 10-bit components. A non-empty list
is exactly `12 + 88 * quad_count` bytes. Golden tests independently check the
length and SHA-256 of every list.

Map coordinates are centered at tile (16, 16) and scaled by 1/4 for the local
model. The visual Y coordinate is `0.25 + terrain_height / 4`, preserving the
known template offset. Horizontal UVs are deterministic functions of local
feature bounds; no UV unwrap or new texture is generated.

## Template shape inventory and binding

Template map member 0 is required to hash to:

`f9fbf0196f416739019288f24be604fd6c096a2ec4ebf7e820e116e7ecc329cc`

All 18 shape display-list capacities were inspected:

| Shape | Capacity | Shape | Capacity | Shape | Capacity |
|---:|---:|---:|---:|---:|---:|
| 0 | 696 | 6 | 1,068 | 12 | 416 |
| 1 | 2,496 | 7 | 1,416 | 13 | 136 |
| 2 | 976 | 8 | 128 | 14 | 1,332 |
| 3 | 216 | 9 | 128 | 15 | 784 |
| 4 | 216 | 10 | 576 | 16 | 336 |
| 5 | 1,936 | 11 | 96 | 17 | 140 |

The proven bindings are:

| Alias | Shape | Material | Template name | Proof bytes / capacity | Utilization |
|---|---:|---:|---|---:|---:|
| ground | 5 | 12 | `grass01` | 1,068 / 1,936 | 55.165% |
| transition | 6 | 17 | `road01` | 188 / 1,068 | 17.603% |
| cliff | 1 | 18 | `road01_r` | 716 / 2,496 | 28.686% |

The model/material/texture dictionaries, SBC stream, texture block, offsets,
and per-shape allocated regions remain in place. Selected display-list lengths
may shrink inside the known capacity. Every unused shape is replaced with a
small valid degenerate list, matching the earlier bounded transformer. There is
no relocation or expansion. Overflow fails instead of touching unknown data.

One shape is bound to one existing material in this template's SBC stream.
Using three materials therefore also proves deterministic multi-shape output;
it is not a generic material allocator.

## BDHC subset

For each source top feature, the compiler emits:

- two centered X/Z rectangle points as `(0, x, 0, z)` signed shorts;
- one deduplicated Q12 normal;
- one deduplicated Q16.16 plane constant;
- one plate containing point, normal, and constant indices.

Confirmed normals in this fixture:

- horizontal: `(0, 4096, 0)`;
- X ascent: `(-2896, 2896, 0)`;
- Z descent: `(0, 2896, 2896)`.

For a plane normal `(Nx, Ny, Nz)` through source point `(x0, h0, z0)`, the
serialized constant is:

```text
D = -16 * (Nx*x0 + Ny*h0 + Nz*z0)
```

The proof contains 28 points, 3 normals, 4 constants, 14 plates, 6 stripes, and
26 access indices. Stripes are made from sorted Z maxima. Each stripe contains
its overlapping plates plus the immediately following stripe's look-ahead
plates, then the complete candidate set is stably sorted by minimum X and plate
index. This agrees with PDSMS `BdhcWriterHGSS.calculateStripes()` intent and is
runtime-proven for the final banded fixture. PDSMS `Stripe.sortPlateIndices()`
appears to associate candidate IDs with `plates.get(i)` rather than the
candidate's plate; that apparent implementation defect was not copied.

An early fixture placed an X ramp across an entire Z band and could ascend but
could not establish normal raised-surface movement beyond its endpoint. That
layout was rejected. The passing fixture isolates the ramp in its own Z band,
as the Stage 3A golden does, and provides compatible neighboring plate bands.
No general claim is made for arbitrary overlapping plate-selection ambiguity.

## Runtime-proven fixture

The final source has 12 horizontal surfaces, two transitions, and eight derived
wall quads: 22 quads / 88 vertices total. Its raised area changes from a broad
northeastern terrace to a narrow stem, so it is not a half-map split.

Runtime evidence confirms:

- lower start `(8,12)`, height state 0 / Y `0`;
- X transition at Z 12: X 14/15/16/17 with heights 1/3/4/4;
- cliff attempt from `(16,9)` remains `(16,9)` at height 4;
- irregular raised traversal reaches `(18,23)` at height 4 / Y `131072`;
- Z transition at X 18: Z 24/25/26/27 with heights 3/1/0/0;
- lower movement reaches `(14,27)` at height 0;
- the ROM remains running there for another 600 frames.

The two transition axes and opposite height direction are proven only in those
arrangements. The active map state identifies matrix 1, member 633, and normal
overworld header 538. The Stage 2 test-only start hook queues at counter 300 so
the new-game field script has released input ownership before the controlled
warp; the old counter-30 timing loaded the map but intermittently left D-pad
input owned by the bootstrap script.

## Reproduction

```bash
python -m tools.pokeagent map geometry inspect \
  --fixture fixtures/stage3d_static_geometry_world.json --json
python -m tools.pokeagent map determinism \
  --fixture fixtures/stage3d_static_geometry_world.json --json
make stage3d-geometry-proof
python -m tools.pokeagent map test \
  --fixture fixtures/stage3d_static_geometry_world.json --json
```

Ignored reports/evidence:

- `build/stage3d/generated/components/geometry-ir.json`
- `build/stage3d/generated/components/geometry-report.json`
- `build/stage3d/emulator/report.json`
- `build/stage3d/emulator/{lower-start,transition-a,cliff-blocked,raised-terrace,transition-b}.png`

## Evidence and revisions

- Pokemon DS Map Studio revision
  `ac30b653e5b090ce116278ed6ba9758fff956673`, especially
  `BdhcWriterHGSS.java`, `Stripe.java`, and `Plate.java`.
- pret/pokeheartgold revision
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`, used for runtime structure and
  field-collision source inspection.
- Stage 2/3A known model and BDHC goldens.
- Generated bytes, unit goldens, HG-Engine build, and DeSmuME live memory.

Neither inspected external checkout contained a top-level redistribution
license file at the inspected revision. They were used as format/source
evidence only; no editor framework or source implementation was copied. The
compiler transforms a user-local, hash-verified retail template and does not
track or redistribute it.

## Unknown / unsupported

- triangles, arbitrary polygons, arbitrary normals, or unrestricted topology;
- more transition directions/arrangements than the two tested here;
- arbitrary plate overlap, bridges, stacked floors, or ambiguous floors;
- display-list relocation, shape expansion, or arbitrary shape/material/SBC
  rebinding;
- new materials, textures, palettes, NSBTX, animation, or node hierarchies;
- OBJ/GLB import or a from-scratch NSBMD writer;
- maximum practical BDHC plate/stripe/access counts beyond this fixture.

These are explicit boundaries, not presumed future capabilities.
