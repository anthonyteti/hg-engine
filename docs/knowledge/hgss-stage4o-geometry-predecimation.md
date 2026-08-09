# HGSS Stage 4O: Geometry-Only Predecimation

## Finding

A bounded valid GLB containing only `POSITION` and indexed independent
triangles can be deterministically reduced before normals, UVs, or source
material identity exist. The reducer takes a 1,056-triangle
reconstruction-style shrine to 64 triangles and 35 positions while preserving
manifold/open-boundary validity and passing predeclared bounds, surface,
geometric-error, and five-view silhouette gates.

Confidence: confirmed by independent binary reopening, topology validation,
quantitative fidelity tests, two-root byte equality, mutation/invariance tests,
and exact Stage 4J/4N regressions. This is not a ROM-renderable asset stage.

## Reproduction

```bash
python -m tools.pokeagent asset geometry-reduce \
  assets/manifests/stage4o_dense_geometry_shrine.json --json
make stage4o-geometry-predecimation-proof
python -m unittest tests.test_pokeagent_stage4o_geometry_reduce -v
```

Ignored outputs are `reduced-geometry.glb`, `geometry-only-ir.json`,
`geometry-collapse-plan.json`, and `geometry-predecimation-report.json`.

## Contract

- embedded GLB 2.0; no URI, extensions, compression, or sparse accessors
- one mesh, one indexed `TRIANGLES` primitive, `POSITION` only
- one identity mesh node or an identity-only root-to-mesh chain up to 4 nodes
- <= 8 MiB GLB/BIN, 8,192 positions, 16,384 faces, 49,152 indices
- finite nondegenerate, nonduplicate, consistently wound manifold or
  open-manifold geometry
- one connected component for the canonical policy
- no `NORMAL`, `TEXCOORD_0`, material, or auxiliary attribute is invented
- transformation rejects `COLOR_0` and all other auxiliary attributes

The schema-13 policy targets 64 faces and 64 positions, leaving margin under
the 80-face/256-element attribute-bootstrap envelope.

## Algorithm and fidelity

`mesh_predecimate` canonicalizes semantic positions/faces, normalizes by the
source bounds diagonal, and uses deterministic QEM-ranked manifold edge
collapse. Link-condition, boundary, ground-contact, crease, degeneracy,
inversion, duplicate-face, and face-rotation constraints protect the surface.
Stable edge identities break ties; no random state exists.

Canonical thresholds are bounds delta <= 0.04 of the diagonal, maximum
geometric error <= 0.08, surface-area delta <= 22%, and minimum 64x64
front/rear/left/right/three-quarter silhouette IoU >= 0.84.

The proof result is 64 faces/35 positions, 3.285732% surface delta, 0.047417
maximum normalized geometric error, 0 bounds delta, and 0.945570 minimum
silhouette IoU. A 12-face target fails rather than violating fidelity.

## Relationship to other stages

Stage 4O shares only pure geometry math with Stage 4J. Stage 4J remains the
attribute-aware final decimator and the only reducer targeting the tested
4,096-byte Nitro budget. Stage 4O output intentionally fails Stage 4F because
material, normals, and UV0 are still missing.

Stages 4L, 4M, and 4N proved isolated adapters, not their automatic combined
application to one raw source. A test-only fully attributed copy proves only
that reduced topology is acceptable once independently supplied attributes
exist.

## Stage 4H evidence

The immutable candidate's counts (3,360 positions, 6,664 faces) and identity
two-node chain fit the Stage 4O numeric/structural envelope. It is nevertheless
ineligible: read-only inspection finds one zero-area triangle and two connected
components, while `COLOR_0` is an explicit transformation blocker. No derived
file was created and the historical rejection remains unchanged.

## Remaining unknowns

- the correct explicit multi-adapter bootstrap transaction
- whether and when non-runtime `COLOR_0` may be discarded
- behavior on multiple valid components and broader generated topology
- quality on organic or very thin geometry
- scaling beyond the conservative source envelope
