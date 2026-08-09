# HGSS Stage 4N: Bounded glTF Source-Material Synthesis

## Finding

A local embedded GLB with valid `POSITION`, `NORMAL`, `TEXCOORD_0`, indices,
and one bounded TRIANGLES primitive can acquire exactly one deterministic
manifest-declared source material without changing any geometry or attribute
payload. The resulting GLB passes the unchanged Stage 4F parser and binds
through the existing project material/texture catalog.

Confidence: confirmed by official format specification, independent GLB
parsing, exact authored-reference equality, unit/integration tests, two-root
generation, full ROM build, declarative emulator QA, and visual inspection.

## Format semantics

In glTF 2.0, `mesh.primitive.material` is an optional zero-based index into the
top-level `materials` array. A material object's `name` is optional. The project
therefore emits only:

```json
"materials": [{"name": "generated_surface"}]
```

and assigns `primitive.material = 0`. It deliberately emits no PBR fields.

Primary source: Khronos glTF 2.0 specification,
`https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html`.

## Reproduction

```bash
python -m tools.pokeagent asset materials \
  assets/manifests/stage4n_missing_material_turret.json --json

python -m tools.pokeagent asset validate \
  assets/manifests/stage4n_missing_material_turret.json --json

python -m tools.pokeagent map determinism \
  --fixture fixtures/stage4n_material_synthesis_world.json --json

make stage4n-material-synthesis-proof

python -m tools.pokeagent qa run \
  qa/scenarios/stage4n_material_synthesis.json --timeout 300 --json
```

The ignored asset output includes `material-generated.glb` and
`material-synthesis-report.json`.

## Contract

- explicit manifest schema 12 policy: `assign_single_named_material`
- name: 1..64 lower-snake-case ASCII characters
- material table absent/empty and primitive assignment absent
- one scene, a bounded 1..4-node Stage 4K-compatible root-to-mesh chain
- one mesh and one indexed independent-TRIANGLES primitive
- exact `POSITION`, `NORMAL`, and `TEXCOORD_0` attributes
- embedded BIN only; no URI, extensions, images, textures, animations, skins,
  or morphs
- max source/BIN 262,144 bytes, 16 accessors/views, 256 elements/accessor

The adapter rejects any existing material instead of overwriting it. It accepts
the bounded hierarchy only to preserve it byte-semantically; it does not flatten
or transform it.

## Preservation evidence

Canonical source SHA:
`4610685f64497a323ba6adfb059f7503a11bf6d740e272a7ed514d8cf22e2a75`.

Canonical output/reference SHA:
`3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66`.

The source and output BIN are byte-identical with SHA:
`2e8a744ad00c66336423d37a78fc8cf39022581fcc324b5a26b5fec5d5e83258`.
The JSON documents are equal after removing exactly the added material object
and primitive index. Logical accessor payloads are independently hashed and
compared after reopening.

The generated output equals the independently authored material reference
byte-for-byte. Its display list equals the reference at 1,372 bytes and SHA
`4b70a89f6ab34386fff4e0e55add0bfe0b875c846d42d96cfa16c740602c26dc`.

## Source/project distinction

`generated_surface` is source identity only:

```text
generated_surface -> prop -> stage4d_stone -> existing HGSS-bound material
```

The adapter has no Nitro/NSBMD/TEX0 knowledge. It creates no DS material,
texture, palette, or renderer state.

## Stage 4H boundary

The Stage 4H two-node structure is inspectably within the neutral hierarchy
shape, but the complete Stage 4N operation rejects its missing `NORMAL` and
`TEXCOORD_0` plus unexpected `COLOR_0`. Its scale is also far outside the
preprocessing and runtime geometry envelopes. Material preprocessability is
not asset acceptance; the immutable Stage 4H rejection remains authoritative.

## Unknowns and unsupported cases

- multiple meshes, primitives, or material identities
- replacement/renaming of authored materials
- glTF PBR semantics and embedded images/textures
- `COLOR_0` conversion
- remote/external buffers and extensions
- general scene graphs or arbitrary hierarchy mutation
- large generated-mesh preprocessing
- mapping source material state beyond a stable manifest identity
