# Stage 4B technical report: first external environment asset ingestion

## Verdict

`STAGE_4B_ASSET_PIPELINE_PASSED`

A tracked project-authored OBJ now flows through a deterministic, bounded mesh
parser and normalized IR into the existing HeartGold map-model transformer.
The manifest and symbolic placement jointly drive render geometry and PER
collision. The ROM builds through HG-Engine, the reusable Stage 4A runner proves
approach/collision/around-object movement and stability, and Codex visually
confirmed the generated shell in two emulator captures.

## Stage 4A checkpoint

Stage 4B began only after Stage 4A was deliberately staged, reviewed, committed,
pushed, and remotely verified:

- commit: `610689426 Add Stage 4A declarative gameplay QA framework`;
- full commit: `610689426803137799a902edb8feacaadf51a554`;
- branch: `main`;
- local `HEAD`, `origin/main`, and remote main agreed;
- the worktree was clean before Stage 4B implementation.

No ROM, generated NARC, screenshot, save, extracted asset, log, credential, or
ignored runtime output entered the checkpoint.

## Source, manifest, and catalog

The sole proof asset is `stage4b_test_shed`, a project-authored CC0 low-poly
outdoor shed shell. Its tracked OBJ contains a rectangular body and shallow roof
slab: 16 positions, four UVs, six normals, 12 planar quads, one source material,
and no animation/skeleton/proprietary content.

The tracked schema-1 JSON manifest declares identity/source/provenance,
coordinate convention, units-to-tile scale, base-centered anchor, approved
material mapping, rectangular collision, and explicit proof budget. A separate
catalog resolves the stable local asset symbol to that manifest. Asset identity
does not consume an HGSS global numeric registry resource.

Stage 4B intentionally supports OBJ only. GLB/GLTF, Blender, converters, and
external generation services are absent.

## Compiler architecture

```text
tracked OBJ + JSON manifest
  -> bounded OBJ parser
  -> neutral mesh (positions, UVs, normals, quads, materials, bounds)
  -> axis/unit/anchor/winding normalization
  -> validation and conservative budget
  -> Stage 3D Nitro quad display-list encoder
  -> symbolic cardinal placement
  -> existing NSBMD shape transformation + PER proxy
  -> existing world serializers and HG-Engine build
```

`tools.pokeagent.assets` owns format parsing, normalization, asset validation,
budgeting, catalog/placement resolution, display-list generation, and asset
reports. `world.py` receives compiled placement geometry and resolved world IDs;
it does not contain shed-specific emit functions or raw OBJ handling.

## Primitive, material, and model strategy

The supported primitive is an explicit planar quad with per-corner UV and
normal. Triangles and N-gons fail deterministically; Stage 4B did not expand
Nitro primitive semantics without need. Face and placement order follows tracked
source order, never directory/dictionary iteration.

The external source material `shed_shell` maps explicitly to approved alias
`prop`: existing template shape 1, material index 18, `road01_r`, 2,496-byte
verified capacity. The shed consumes 1,068 bytes (42.788%). Terrain remains
shape 5/material 12. No new material, texture, palette, NSBTX, or arbitrary
shape relocation is generated.

The proof object is merged into the map NSBMD. BLD and a standalone prop-model
loader were not introduced because the verified multi-shape map-model path is
the smaller reusable boundary for this proof.

## Normalization and budget

The canonical target is Y-up, X/Z ground plane, one tile per canonical unit,
right-handed, origin at footprint center/base. Source units, signed up/forward
axes, scale, anchor, normal direction, and winding are explicit and validated.
The accepted normalized bounds are `(-2.25,0,-1.75)` to `(2.25,3,1.75)` tiles.

The deliberately conservative policy caps source bytes, positions, UVs,
normals, quads, materials, dimensions, height, blocked tiles, and verified
display-list capacity. The generated JSON report includes counts, bounds,
material/shape assignment, display-list utilization, collision, and SHA-256s.
It is an asset-generation budget, not a global hardware-capacity claim.

## Reusable placement and collision

The schema-8 world fixture places `stage4b_test_shed` at `(16,16)` with a
cardinal rotation. Placement transforms geometry and the manifest footprint
through the same X/Z operation. Its rectangular proxy blocks 12 PER tiles,
while adjacent approach and around-object tiles remain traversable.

The object uses controlled Stage 3C proof resources (header 538, matrix 1, map
member 633, event 57, scripts 842/3 and header 399, text 542). The Stage 3E1/E2
proven append/header windows are already allocated, so Stage 4B did not silently
extend production capacity or renumber persistent resources.

Runtime initially exposed one physical-layout regression: retaining the
template BGS payload displaced effective normal-overworld collision. Schema 8
now emits an empty BGS payload, keeping PER at the permanent physical offset
`0x14`; a focused test permanently covers it.

## CLI and generated outputs

`python3 -m tools.pokeagent asset validate|inspect|compile <manifest>` is the
stable noninteractive command surface and supports `--json`. Compile output
under ignored `build/assets/<id>/` includes normalized mesh JSON, asset report,
display-list bytes, and collision JSON. World generation additionally records
placement IR and map-level shape/collision utilization.

Malformed/unsafe inputs fail with stable machine-readable codes for missing or
escaping source paths, extension/schema/provenance errors, nonfinite values,
unsupported topology/indexing/materials, absent UV/normals, degeneracy,
budgets, transforms, duplicate IDs, invalid/off-map placement, overlap, and
display-list overflow.

## Determinism and mutation

Two clean generation roots matched byte-for-byte across all 24 generated
Stage 4B artifacts. Key hashes:

| Artifact | SHA-256 |
|---|---|
| source OBJ | `b8f88aeae3d0c8d6e79ec1daae220449444b75be8c43acb26481899ec8602da9` |
| normalized IR semantic hash | `85e40ac18e9037d4be6f62f02c23086f8e37663a9997726db6e35f834113daa6` |
| display list | `628581e2dcdd4cc0047e638c3579b30729fd86ca83e8bc5b6f441186c0d290dc` |
| transformed NSBMD | `b2d804347c07788de6247764f00424ee771d4728fc36d8084b466f9912140217` |
| PER | `b2adea8887e2b12949e040caec8843e06fb58c186bb770c321ae93dbe2e572b5` |
| map member | `de8b5c55bfdec36f2bec59908074c3ee54b6080e8d9afdab5e79cfac58c2ac4a` |

A temporary roof-height mutation changed the source, normalized IR, and encoded
display-list hashes while preserving asset identity and collision. The accepted
source was restored; exact before/after hashes are in the knowledge note and
unit test.

## Emulator and visual QA

The tracked Stage 4A scenario has 21 declarative steps and plan hash
`f581c06af8804dd3dc449eaa58f69c220d9041af70a5ee14363f801991452022`.
It boots through the controlled entry, asserts header/member identity, approaches
the shed, captures it, proves the footprint blocks north movement, walks beside
and behind it, captures again, and remains stable for another 600 frames.

The accepted run passed 14/14 assertions and ended running at `(18,13)`. Codex
inspected both 256 x 384 captures. The object is visible, upright, centered on
its footprint, seated on terrain, non-exploded, and consistently faced from
front and rear. Its inherited material is a coherent but deliberately plain
dark-green shell. Collision corresponds to the visible footprint and nearby
terrain remains walkable. The final clean ROM SHA-256 is
`c26156ec27350e6749d82c0887ce9eb6c879682cc3a9b2ef965927c5e24f9c6c`;
the final approach/rear PNG hashes are
`a76fc4debb7ecdc0c0d919d7f2ff5aa6c5a6ae1d66043b1d3bc33d33d679f05e`
and `1159e69c49d95aee020eb60acb83188fbc2e5ab17a40cc3540ba366fc0358965`.

## Tests and regressions

Stage 4B adds 16 focused asset tests. The complete clean-build/runtime matrix
passed:

- Stage 2: clean build and specialized runtime passed; Stage 4A Scenario A
  passed 9/9 assertions.
- Stage 3A: clean build and specialized multi-height runtime passed.
- Stage 3B: clean build and specialized four-cell native-transition loop passed.
- Stage 3C: clean build and symbolic-registry runtime passed.
- Stage 3D: clean build and specialized runtime passed; Stage 4A Scenario B
  passed 13/13 assertions.
- Stage 3E1: clean build and appended-resource runtime passed.
- Stage 3E2: clean build and specialized header/warp/save runtime passed; after
  isolating the specialized worker's generated shared DeSmuME battery save,
  Stage 4A Scenario C passed 19/19 assertions and real reset/Continue.
- Stage 4B: final clean build and Scenario 4B passed 14/14 assertions.
- Full suite: 137 tests ran; 134 passed and three opt-in integration tests were
  skipped as designed.
- Registry validation: 11 namespaces / 32 resources passed.
- Preflight: every command, Python, ROM, Git-hygiene, system, and Docker-context
  check passed.

The initially ordered Stage 3E2 Scenario C rerun correctly reported blocked
movement because the immediately preceding specialized worker had created
`~/.config/desmume/test.dsv`. Moving that generated save to ignored scratch
restored the intended clean `new_game_controlled` precondition and the unchanged
scenario passed. This documents a shared emulator-state limitation; it is not a
game/compiler regression and no assertion was weakened.

## DeepSeek

No DeepSeek call was needed. The implementation reused project-owned Stage 3D
encoding and Stage 4A runtime abstractions; Codex verified parsing, bytes, build,
runtime collision, and visuals directly. Token usage: 0. Estimated cost: `$0`.

## Constraints and recommendation

The result does not support triangles, N-gons, multiple/new materials, texture
or palette authoring, BLD, independent prop resources, animation, skeletons,
arbitrary transforms, simplification, nonrectangular 3D collision, or another
ROM/template revision. It proves one small external reusable static asset, not
an environment kit.

The next separately scoped asset stage may investigate one bounded missing
capability—most usefully project-authored texture/palette handling or a carefully
verified triangle subset—while retaining this parser, manifest, budget, catalog,
placement, collision, and QA boundary. Stage 4C and image-to-3D have not begun.
