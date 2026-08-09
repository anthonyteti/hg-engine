# Stage 4N Technical Report: Bounded Named-Material Synthesis

Date: 2026-08-09

Verdict: `STAGE_4N_MATERIAL_SYNTHESIS_PASSED`

Classification: `MATERIAL_GAP_CLOSED`

## Checkpoint and scope

Stage 4M was committed as `9c7931ee44e37786e5f1925b78b6cf038dd3ca70`
(`Add Stage 4M UV generation`) and pushed to `origin/main` before Stage 4N
work began. Local `HEAD`, the remote-tracking ref, and the remote branch agreed,
and the tree was clean.

Stage 4N creates one source-side glTF material identity. It does not create a
Nitro material, texture, palette, PBR interpretation, or any geometry
attribute. Stage 4F remains the unchanged strict acceptance boundary.

## Format evidence

The official glTF 2.0 specification defines a primitive's `material` as an
optional zero-based index into the top-level `materials` array, and a material
object's `name` as an optional string. Consequently the smallest sufficient
project object is:

```json
{"name": "generated_surface"}
```

with `primitive.material = 0`. No PBR fields are needed for the project's
source-identity mapping. Source: Khronos glTF 2.0 specification,
`https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html`, inspected
2026-08-09.

## Architecture

`tools.pokeagent.glb_materials` is a bounded, missing-only adapter:

```text
local embedded GLB without materials
  -> validate bounded structure and required attributes
  -> copy JSON semantics
  -> append one manifest-declared minimal material
  -> assign primitive.material = 0
  -> preserve the BIN chunk byte-for-byte
  -> unchanged Stage 4F parser
  -> existing material alias / project texture path
```

The module has no DS, NSBMD, map, registry, collision, or texture-container
knowledge. Manifest schema 12 opts in with
`assign_single_named_material`. Names are 1..64 lower-snake-case ASCII
characters matching `[a-z][a-z0-9_]*`. Authored materials or primitive
assignments fail with `material_already_present` and are never overwritten.

The bounded source envelope is 262,144 GLB/BIN bytes, one scene, 1..4 nodes in
the Stage 4K root-to-mesh-chain subset, one mesh, one TRIANGLES primitive, at
most 16 accessors/buffer views, and at most 256 elements per accessor. Required
attributes are exactly `POSITION`, `NORMAL`, and `TEXCOORD_0`; embedded
resources, extensions, animation, skins, morphs, and `COLOR_0` are rejected.

Stage 4N is hierarchy-neutral. It validates the bounded chain but does not
evaluate, bake, reorder, or rewrite nodes, scenes, or transforms. A controlled
two-node no-material source remained byte/semantic identical except for the
material additions, then Stage 4K flattened it and Stage 4F accepted it.

## Canonical proof

The project-authored source is
`assets/source/stage4n_missing_material_turret.glb`:

| Property | Source | Canonical |
|---|---:|---:|
| SHA-256 | `4610685f64497a323ba6adfb059f7503a11bf6d740e272a7ed514d8cf22e2a75` | `3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66` |
| Size | 2,112 bytes | 2,168 bytes |
| Materials | 0 | 1 |
| Primitive material | absent | 0 |
| Triangles | 20 | 20 |

The independently authored reference is
`assets/source/stage4n_authored_material_reference.glb`. The generated GLB is
byte-identical to that reference. Before preprocessing, unchanged Stage 4F
rejects the source with `unsupported_material`; afterward it accepts all 20
faces under source material `generated_surface`.

The embedded BIN hash is identical before and after:
`2e8a744ad00c66336423d37a78fc8cf39022581fcc324b5a26b5fec5d5e83258`.
Logical payload hashes are:

| Payload | SHA-256 |
|---|---|
| POSITION | `a431532788ca1b0242d12803d7470de6f80f522a5de6f6ae680d65379c09bbc0` |
| NORMAL | `613e27f7299ebc18fec093ae09f568d648af133e839ea20465207d7ae7ec1d2a` |
| TEXCOORD_0 | `2aa61931620b70e194f53c0f70db9be1478978ca3e3a6d86ed413cefa6b0b442` |
| indices | `f3446004937c36a1362a8af90e35b269b3896b7af5aa22dda2eb6b255f3a136f` |

Removing only the new `materials` array and primitive index from the canonical
JSON yields exact source JSON equality. The source/reference normalized IR,
display-list bytes, and collision proxy are semantically equal.

## Downstream result

The manifest maps:

```text
generated_surface -> prop -> stage4d_stone
```

No physical material or texture slot was added. The 20 triangles emit 60
vertices and a 1,372-byte display list in the existing 2,496-byte shape. Its
hash is `4b70a89f6ab34386fff4e0e55add0bfe0b875c846d42d96cfa16c740602c26dc`.
The normalized mesh hash is
`376cc892d088218023db3ce43a4a5a82a8329d9dc5266ad12b551c55391b2662`.

The existing `stage4d_stone` texture and palette remain
`fed37aab0b14b2e656f7c34f0bfc08f41129f578d7025ae7205fc8981cc078d7`
and `744abd4930f4580303c156f1f5440f9b320c7eb21b08060582a63206ba56e7d1`.
The manifest-owned collision hash remains
`e989e1b48c21ad79ae2fbf229286aa12def5573bb02b2a15be043f6739c33664`.

## Mutations and composition

Changing the declared name to `generated_surface_alt`, with a matching
temporary downstream mapping, changes only canonical material-name bytes.
Stage 4F still accepts it, accessor hashes and the display list remain
unchanged, and the same project texture resolves.

Changing the roof height to 4.2 changes the source, POSITION payload,
canonical GLB, normalized IR, display list, and model while retaining
`generated_surface`, project texture identity, collision policy, and world
IDs. Reversing triangle order does not alter the material policy or identity.

Controlled integration proves orthogonality with Stage 4K hierarchy
canonicalization and with Stage 4L/4M missing-normal and missing-UV adapters.
Stage 4N never invokes or duplicates their logic.

## Determinism, binary, and runtime QA

Two clean generation roots produced zero mismatches across the material report,
canonical GLB, normalized IR, display list, collision, map model/member,
texture container, NARCs, ARM9 inputs, and registry/world snapshots. The final
map member hash is
`84dd526ef027ec0107cc62e0594295344d866654791245744604a5147f7d3b2f`;
the transformed NSBMD hash is
`fac121d057a06ef35c89eec5373d27fb7cfd4ec82b9e3e2687e9557cc953bab8`.

The clean ROM build passed; the ROM SHA-256 was
`eab9f2f2b0c835bbd80dda16de309c3073585dadd773a8c65840c8bd6fb9a0a0`.
The Stage 4A declarative scenario passed 15/15 assertions on map 538/member
633, including collision, traversal around the asset, adjacent walkability,
and 600 additional stable frames. Battery state used its isolated per-run
directory.

Codex inspected both front and rear captures. The stone texture binds to the
synthesized identity with complete geometry, coherent normals and UVs, no
fallback or material leakage, correct grounding/collision, and intact terrain.
Screenshot hashes are
`7c98ed55fc4fccb7119f7ae22fffcc005925c27d1991877d3390b9a2b875a9f5`
and `ce11562a07f070139ab8e4b681bfae44f28248b65d1b2995eeedc31d4aab39e3`.

## Stage 4H projection

The immutable raw Stage 4H SHA remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
Its two-node chain is structurally within Stage 4N's hierarchy-neutral envelope,
but material synthesis as a complete operation is not currently applicable:
it lacks `NORMAL` and `TEXCOORD_0` and contains unexpected `COLOR_0`.
It also has 3,360 positions, 6,664 triangles, over-envelope accessors, and a
projected 453,164-byte display list. Its historical result remains
`STAGE_4H_GENERATED_ASSET_REJECTED` / `REJECTED_UNSUPPORTED_STRUCTURE`.

## Boundaries and recommendation

Stage 4N supports exactly one missing named source material on one bounded
static triangle primitive. It does not replace authored identities, assign
multiple materials, interpret PBR, convert vertex colors, create DS resources,
or preprocess large generated meshes.

The next stage should remain separately authorized. A reasonable Stage 4O
investigation would address one remaining generated-input gap—without changing
the Stage 4H verdict or combining that work with production content.

DeepSeek was not used. Tokens: 0. Cost: $0. Disposition: unnecessary.
