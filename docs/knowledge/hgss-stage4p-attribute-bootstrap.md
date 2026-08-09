# HGSS Stage 4P: Atomic Attribute Bootstrap

## Finding

A valid bounded hard-surface GLB containing only `POSITION` and indexed
triangles can be deterministically completed with one manifest-declared source
material, connected planar-patch UV0, and UV-aware crease normals in one atomic
transaction. The result passes the unchanged strict Stage 4F parser and the
ordinary HeartGold texture, collision, model, map, and QA path.

Confidence: confirmed by exact reference equality, independent Stage 4F
reopening, binary/model validation, two-root determinism, ROM runtime,
declarative gameplay QA, screenshot inspection, mutation tests, Stage 4O
composition, and exact Stage 4K/L/M/N/J regressions.

## Reproduction

```bash
python -m tools.pokeagent asset bootstrap \
  assets/manifests/stage4p_geometry_bootstrap_turret.json --json
python -m unittest -v tests.test_pokeagent_stage4p_bootstrap
make stage4p-attribute-bootstrap-proof
python -m tools.pokeagent qa run \
  qa/scenarios/stage4p_attribute_bootstrap.json --timeout 300 --json
```

Generated `bootstrapped.glb`, bootstrap report, normalized IR, display list,
collision, model, map, ROM, and screenshots remain ignored.

## Contract

- embedded GLB 2.0, one scene/identity node/mesh/indexed TRIANGLES primitive
- `POSITION` and indices present
- material, `NORMAL`, and `TEXCOORD_0` all absent
- <=256 KiB, <=256 positions, <=80 faces, <=240 indices
- finite, nondegenerate, consistently wound, one-component manifold or open
  manifold hard-surface geometry
- no default auxiliary-attribute deletion
- no topology repair, hierarchy flattening, reduction, DS material creation,
  texture creation, or Stage 4F leniency

## Transaction

1. Validate geometry-only source.
2. Assign manifest source identity `generated_surface` using Stage 4N naming
   semantics.
3. Generate UV0 using Stage 4M's pure connected planar-patch core and
   transient geometric face normals.
4. Generate final Stage 4L area-weighted 60-degree normals after UV seams
   exist.
5. Serialize once, reopen independently, and require unchanged Stage 4F.

Any phase failure invalidates the transaction; partial intermediates are not
approved assets. Reports label every generated attribute's provenance.

The 19-position/30-face proof produces 18 UV patches, 47 UV splits, 30 seam
edges, 66 final attribute vertices, 66 smoothing fans, 30 hard edges, 12
smooth edges, and 40 unique normal vectors. UVs remain in
`[0.03125,0.96875]`; no triangle has degenerate or mirrored UV orientation.
The 2,052-byte display list fits the inherited 2,496-byte shape region.

## COLOR_0 decision

`COLOR_0` may be discarded only by explicit opt-in for generated hard-surface
geometry whose final appearance is intentionally replaced by a project-owned
texture. Accepted color data is bounded normalized unsigned VEC3/VEC4. The
operation records the logical color payload hash, removes only `COLOR_0`, and
must prove exact POSITION/index semantics against independent reopening.

It is not a general cleanup rule and is rejected for sources with material,
PBR texture/image intent, or another auxiliary attribute. It never translates
color into texture, UV, normals, or material.

## Stage 4H boundary

The immutable candidate's U8 VEC4 color accessor matches the discard data
format, but discard was not performed. Independent topology blockers remain:
one zero-area face, two components, and 25 open boundary loops. No derived
candidate or catalog entry exists; its historical rejection is unchanged.

## Remaining unknowns

- policy for bounded valid multiple-component generated geometry
- whether zero-area generated faces may ever be removed under an explicit
  non-repair intake rule
- broader hard-surface and organic UV classes
- source appearance preservation when vertex color is semantically important
- large generated input beyond Stage 4O's validated topology contract
