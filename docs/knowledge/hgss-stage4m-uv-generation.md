# HGSS Stage 4M: bounded planar-patch UV generation

## Finding

A strict identity-node GLB that already contains valid `POSITION`, `NORMAL`,
indices, and one named material can acquire deterministic `TEXCOORD_0` without
weakening the Stage 4F parser. The proven adapter groups connected coplanar
triangles, projects each patch through a stable world-oriented orthonormal
basis, uniformly fits the patch into the padded unit square, and intentionally
allows every patch to reuse that square.

## Confirmed contract

The source envelope is 262,144 bytes, one node/mesh/material, one to four
independent-triangle primitives, 16 accessors/views, 256 accessor elements, 80
faces, 64 patches, and 256 adjacency edges. `POSITION`, `NORMAL`, and indices
are required; `TEXCOORD_0` must be absent. Animation, skin, morph, hierarchy,
extensions, embedded/external resources, invalid normals, degeneracy,
inconsistent winding, and non-manifold edges fail before projection.

The canonical policy is:

```text
patch normal deviation <= 0.1 degrees
plane distance error <= 1e-5 source units
texture dimensions = 32 x 32
padding = 1 texel = 0.03125 UV
scale = one uniform factor fitting the longest projected dimension
shorter dimension = centered
patch overlap = intentional
output UV precision = deterministic 1e-6 canonical grid
```

## Patch and basis construction

Only edge-connected faces may share a patch. Coplanarity, material identity,
and coherent winding are all required. Disconnected coplanar surfaces remain
separate.

For vertical and moderately sloped architecture, world up is projected onto
the patch plane as bitangent and tangent is `cross(bitangent, normal)`. For
near-horizontal patches, +X (or +Z when necessary) is projected into the
plane, and bitangent is `cross(normal, tangent)`. In both cases
`cross(tangent, bitangent) == normal`, so source winding maps to positive UV
orientation. Triangle order is not an input to basis selection.

Projection is patch-local:

```text
u_raw = dot(position, tangent)
v_raw = dot(position, bitangent)
scale = usable / max(width, height)
uv = padding + centered_margin + (raw - patch_min) * scale
```

Patch-local minima make UV semantics invariant to source translation. A final
fixed decimal grid absorbs harmless float32 translation-rounding differences.

## Evidence

The project-authored square turret contains four wall directions, four sloped
roof patches, and one horizontal cap. Its 20 triangles become nine patches.
Thirteen source attribute vertices become 37 canonical vertices, with 24 UV
splits and 16 protected seam edges. UV range is exactly
`[0.03125,0.96875]`; zero triangles are degenerate or mirrored. Maximum and
mean aspect distortion are `6.112702082283761e-07` and
`2.2301723573610784e-07` after canonical UV rounding.

The 1,152-byte source hash is
`809f77f87ea9b2bb93d83aa58b4aaa54c9c48b3d4bcac6c90d22f483441f6d6e`.
Generated output is byte-identical to the independently authored 2,148-byte
reference with hash
`c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84`.
The unchanged Stage 4F parser rejects the source and accepts the result.

The final display list is 1,372 bytes for 20 triangles/60 emitted vertices,
54.968% of the inherited 2,496-byte shape. Stage 4I relocation and Stage 4J
decimation are not used. ROM QA passes collision, traversal, two captures, and
600 stable frames. The existing `stage4d_stone` texture/palette bytes are
unchanged.

## Reproduction

```bash
python -m tools.pokeagent asset uvs assets/manifests/stage4m_missing_uv_turret.json --json
python -m unittest tests.test_pokeagent_stage4m_uvs -v
python -m tools.pokeagent map determinism --fixture fixtures/stage4m_uv_generation_world.json --json
make stage4m-uv-generation-proof
python -m tools.pokeagent qa run qa/scenarios/stage4m_uv_generation.json --timeout 300 --json
```

## Confidence and limits

Confirmed by exact reference bytes, math/failure fixtures, Stage 4F parsing,
two-root generation, ROM build, live-memory QA, and screenshot inspection.
This is not organic unwrapping, unique atlas packing, material synthesis,
topology repair, or a claim that the Stage 4H generated candidate is eligible.
That candidate exceeds the 80-face/256-element envelope and retains independent
hierarchy, material, normal, color-only, and geometry-budget blockers.
