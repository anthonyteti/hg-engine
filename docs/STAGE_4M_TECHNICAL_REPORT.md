# Stage 4M Technical Report: Deterministic Planar-Patch UV Generation

## Verdict

`STAGE_4M_UV_GENERATION_PASSED`

UV classification: `UV_GAP_CLOSED`

Stage 4M proves repeat-per-planar-patch UV0 generation for one bounded
hard-surface class while retaining Stage 4F as the unchanged canonical GLB
acceptance boundary.

## Checkpoint and scope

Stage 4L was committed and pushed as
`aa68f6708ea2ff4199410335fe5ac8b013236e85 Add Stage 4L normal generation`.
Local `HEAD`, `origin/main`, and remote `main` agreed, and the tree was clean
before Stage 4M began.

Stage 4M does not synthesize a material or texture, repair topology/winding,
pack a unique atlas, decimate geometry, retry a generator, expand source/model
budgets, approve Stage 4H, or create production content.

## Architecture and source contract

`tools.pokeagent.glb_uvs` is an explicit schema-11 adapter:

```text
identity GLB with POSITION/NORMAL/indices/material and no TEXCOORD_0
  -> bounded topology validation
  -> connected coplanar patches
  -> stable planar bases and patch-local projection
  -> deterministic attribute splitting/canonical GLB
  -> unchanged Stage 4F parser
  -> existing typed IR / DS geometry / texture / world pipeline
```

The source envelope is 262,144 bytes, one identity node/mesh/material, one to
four indexed independent-triangle primitives, 16 accessors/views, 256 elements,
80 faces, 64 patches, and 256 adjacency edges. Authored normals must be finite
unit vectors consistent with winding. Interior edges have two incidents, open
boundaries one, and non-manifold edges fail.

## Declared UV policy

The policy was fixed before runtime inspection:

| Setting | Value |
|---|---:|
| Patch normal tolerance | 0.1 degrees |
| Plane-distance tolerance | `1e-5` |
| Texture dimensions | 32x32 |
| Padding | one texel / `0.03125` UV |
| Scaling | uniform, fit longest dimension |
| Short dimension | centered |
| Island overlap | intentional per-patch reuse |
| Canonical UV grid | `1e-6` |

Only connected faces with the same material, coherent winding, matching plane,
and matching normal direction join. Disconnected coplanar surfaces do not.
World-up projection keeps vertical/sloped texture V coherent; horizontal faces
use a deterministic projected world axis. The bases satisfy
`cross(tangent,bitangent) == normal`, preventing accidental mirroring.

## Proof asset and reference

The project-authored turret contains four vertical wall patches, four sloped
roof patches, and one horizontal cap. It has valid authored normals and one
`turret_stone` material but no UV0.

| Artifact | TEXCOORD_0 | Bytes | SHA-256 |
|---|---|---:|---|
| Missing-UV source | absent | 1,152 | `809f77f87ea9b2bb93d83aa58b4aaa54c9c48b3d4bcac6c90d22f483441f6d6e` |
| Generated canonical | generated | 2,148 | `c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84` |
| Authored reference | authored | 2,148 | `c18f88f0aad0466d5d5897383ad4e71882193b3edb2d3f55b54a1632e9cc3a84` |

The unchanged Stage 4F parser rejects the source with `missing_attribute` and
accepts the generated result. Canonical output is byte-identical to the direct
authored-UV reference. Typed IR, display list, collision, material, texture,
positions, normals, UVs, and topology match; maximum and mean reference UV
component differences are zero.

## Quantitative UV result

| Metric | Result |
|---|---:|
| Triangles | 20 |
| Planar patches | 9 |
| Source attribute vertices | 13 |
| Canonical attribute vertices | 37 |
| UV-driven splits | 24 |
| UV seam edges | 16 |
| Open boundary edges | 4 |
| Protected-edge fraction | 0.5 |
| UV minimum | `(0.03125,0.03125)` |
| UV maximum | `(0.96875,0.96875)` |
| Degenerate UV triangles | 0 |
| Mirrored UV triangles | 0 |
| Maximum aspect distortion | `6.112702082283761e-07` |
| Mean aspect distortion | `2.2301723573610784e-07` |
| Intentionally overlapping islands | 9 |

## Binary, texture, and collision result

The existing encoder emits 60 vertices into a 1,372-byte triangle display
list, 54.968% of the inherited 2,496-byte `prop` capacity. Display-list hash is
`4b70a89f6ab34386fff4e0e55add0bfe0b875c846d42d96cfa16c740602c26dc`.
No Stage 4I relocation or Stage 4J decimation is used.

`turret_stone` maps to `prop` / `stage4d_stone`. Texture and palette hashes
remain `fed37aab0b14b2e656f7c34f0bfc08f41129f578d7025ae7205fc8981cc078d7`
and `744abd4930f4580303c156f1f5440f9b320c7eb21b08060582a63206ba56e7d1`.
The manifest-owned collision rectangle is X `[-1.9,1.9]`, Z `[-1.7,1.7]`;
semantic hash is
`e989e1b48c21ad79ae2fbf229286aa12def5573bb02b2a15be043f6739c33664`.

Two-root generation reports zero mismatches. Deterministic NSBMD and map-member
hashes are `fac121d057a06ef35c89eec5373d27fb7cfd4ec82b9e3e2687e9557cc953bab8`
and `84dd526ef027ec0107cc62e0594295344d866654791245744604a5147f7d3b2f`.

## Gameplay and visual QA

The fresh ROM hash is
`59a79bf11a1a6d771af2e6079f441f82b73d29dfc590fd67977837471824a9ad`.
The Stage 4A scenario passes 15/15 assertions in 60.92 seconds through frame
8,848: map 538, matrix 1, member 633, collision block, walk-around, adjacent
terrain, two captures, and 600 stable frames. Final position is `(12,13)` with
live BDHC state and no warp.

Front/rear screenshot hashes are
`7c98ed55fc4fccb7119f7ae22fffcc005925c27d1991877d3390b9a2b875a9f5`
and `ce11562a07f070139ab8e4b681bfae44f28248b65d1b2995eeedc31d4aab39e3`.
Inspection confirms coherent repeated stone on every wall direction, stable
sloped-roof and horizontal-cap projection, controlled seams, correct lighting,
complete faces, grounding, aligned collision, and intact terrain. No texture
crawling, catastrophic stretch, or accidental mirror is visible.

## Invariance and mutations

Reversing face order changes the source hash but produces byte-identical
canonical output. Translating the source by `(7,2,-5)` changes geometry bytes
but leaves canonical UV semantics exactly equal. The output normalizes every
patch independently rather than preserving world texel density.

Changing padding from one to two texels changes only UV/canonical output; the
temporary output hash is
`bd639f2e75041a38c945e330d877b862c25b92ccfa3b63bad2fec2ce982c0c39`.
Positions, normals, topology, material, texture, and collision remain fixed.
Raising the roof to 4.2 changes source, UVs, canonical GLB, typed IR, display
list, and model while preserving stable project identities and unaffected
resources. Canonical source was restored.

A controlled Stage 4L-generated normal mesh can be semantically rebuilt
without its placeholder UV accessor and then accepted by Stage 4M/Stage 4F;
generated normals and geometry survive. This proves adapter compatibility, not
an automatic jointly-missing-attribute workflow.

## Stage 4H projection

The immutable Stage 4H hash and rejection remain unchanged. Raw Stage 4M
application fails at `unsupported_scene`; topology applicability is also false
because 6,664 faces exceed 80 and 3,360 positions exceed 256. Independent
blockers remain hierarchy, no material, no normal, no UV0, COLOR_0-only data,
accessor/source budgets, geometry reduction, and display-list overflow. No
derived Stage 4H asset was produced or compiled.

## Regression, confidence, and recommendation

The full suite passes 237 tests with three opt-in integrations skipped. Stage
4K canonical hash remains
`d3fba37773e289566356a4dbadff37fad8e2c4786b5c6db09e959ed0c35dfbb6`;
Stage 4L canonical hash remains
`b49552f3b890740614fb2f085ac51b7d12d86294f1df2441c69ea65468598eb9`.
Registry validation, compileall, preflight (58 checks), full ROM build, QA,
artifact hygiene, and earlier regressions pass. DeepSeek was not used; tokens
and cost are zero.

Confirmed boundary: `UV_GAP_CLOSED` only for bounded connected planar
hard-surface meshes. Unsupported classes include organic/curved surfaces,
unique atlases, authored-UV replacement, multiple materials, topology repair,
large generated inputs, and production unwraps.

Stage 4N should proceed only as a separately authorized proof of the next
independent intake gap. It must not retroactively approve Stage 4H, combine
material synthesis with generated-asset conversion, expand envelopes, retry a
generator, or begin production art.
