# HGSS Stage 4G deterministic mesh simplification

## Finding and confidence

A valid over-budget OBJ/GLB asset can be reduced after shared normalization and
before Nitro encoding with no source-format- or world-specific code. The proven
subset reconstructs minimal triangle/quad boundaries from redundant connected
coplanar triangle patches while preserving material, texture, UV, hard-normal,
silhouette, bounds, area, and collision identity.

Confidence is **high for exact redundant planar subdivisions matching the
Stage 4G constraints**. Evidence includes deterministic algorithm inspection,
malformed/failure tests, exact Stage 4F semantic equivalence, independent
display-list parsing, clean HG-Engine build, live collision/walk-around QA,
front/rear visual inspection, mutation propagation, and two-root determinism.
It is not evidence for approximate general-purpose decimation or mesh repair.

## Algorithm and ordering

`tools.pokeagent.mesh_simplify` implements `exact_coplanar_patches`, version 1,
with Python standard-library code only. No external library/license is added.

For normalized typed IR schema 2:

1. reject non-triangle input and non-manifold edges;
2. signature faces by material alias, texture, authored protected normal,
   geometric normal, and plane constant;
3. connect equal-signature faces only across identical position+UV edges;
4. visit components and neighbors in stable numeric order;
5. require consistently reversed shared-edge winding and one simple boundary;
6. choose a stable geometric/UV minimum as the boundary start;
7. remove only collinear boundary points with exact linear UV interpolation
   inside fixed `1e-6` position/UV/normal tolerances;
8. require the remaining boundary to have three or four corners;
9. emit one typed triangle/quad and compact referenced vertices/UVs by stable
   first occurrence;
10. recompute bounds from referenced output vertices and verify exact source
    bounds/dimensions, surface area, winding, normal, and downstream validity.

Set membership never determines emitted order. There is no random state or
floating priority queue. Semantic hashes exclude absolute paths.

## Protected structure and error boundary

The reducer never crosses:

- material or project-texture boundaries;
- distinct authored hard normals;
- different geometric planes/normals;
- UV seams, because adjacency includes each corner's UV index;
- open exterior boundaries.

It rejects non-manifold edges, same-direction shared winding, open/disconnected
or multi-loop patches, irreducible boundaries other than triangles/quads,
degenerate output, bounds or surface changes, normal disagreement, invalid
targets, and any result still over budget. The ordinary asset validator always
runs after simplification. This is simplification of valid data, never repair.

## Manifest and byte-budget behavior

Schema 6 is opt-in. Required policy is:

```text
policy = exact_coplanar_patches
target = fit_shape
reduction_mode = maximal_exact
preserve_boundaries/UV seams/material boundaries/hard normals = true
reserve_bytes = explicit nonnegative integer
```

The final target is `verified shape capacity - reserve_bytes`. Legacy schemas
retain fail-on-overflow behavior. The reducer simplifies maximally under exact
constraints, then the normal encoder measures exact bytes. If the result does
not fit, `simplification_target_unreachable` reports required bytes, target,
capacity, and shape. It never silently degrades geometry.

`asset inspect` exposes source projection and predicted final plan. `asset
simplify` and `asset compile` both honor the manifest. Ignored outputs include
`normalized-mesh.json`, `simplified-mesh.json`, the report, display list,
texture artifacts, and collision proxy.

## Canonical proof

The project-authored CC0 dense tower is one static embedded GLB with 48 indexed
triangles, authored normals and UV0, and existing stone material mapping. It
subdivides the exact Stage 4F tower surfaces:

| Metric | Dense source | Exact output |
|---|---:|---:|
| triangles / quads | 48 / 0 | 4 / 4 |
| referenced vertices | 29 | 9 |
| emitted vertices | 144 | 28 |
| Nitro bytes | 3,276 | 648 |
| capacity/overflow | 1,068 / +2,208 | 1,068 / none |
| area | 63.0 | 63.0 |

The face and byte reductions are 83.333% and 80.220%. Bounds are exactly
3 x 6 x 3 tiles; maximum retained-boundary displacement and normal deviation
are zero. The display inspector finds four quads, four triangles, two valid
primitive blocks, 28 vertices, and terminal END. The collision hash exactly
matches Stage 4F because collision remains manifest-owned.

## Reproduction

```bash
.venv/bin/python -m tools.pokeagent asset inspect assets/manifests/stage4g_dense_faceted_tower.json --json
.venv/bin/python -m tools.pokeagent asset simplify assets/manifests/stage4g_dense_faceted_tower.json --json
.venv/bin/python -m tools.pokeagent map determinism --fixture fixtures/stage4g_simplified_world.json --json
make stage4g-simplification-proof
.venv/bin/python -m tools.pokeagent qa run qa/scenarios/stage4g_simplified_asset.json --timeout 300 --json
```

Generated meshes, reports, display lists, NARCs, ROMs, screenshots, logs, and
battery saves remain ignored.

## Remaining unknowns

Not proven: approximate/non-coplanar edge collapse, QEM, curved surfaces,
arbitrary quad-source simplification, holes/multiple boundary loops, more than
four final boundary corners, cross-seam reduction, automatic repair, normal/UV
generation, detailed collision, display-list relocation, generated 3D, or
production asset fidelity thresholds.
