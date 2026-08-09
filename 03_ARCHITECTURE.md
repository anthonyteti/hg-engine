# Autonomous Architecture

## Principle

The core product is not the fan game. The core product is the **factory that can generate and revise the fan game**.

The LLM should operate on high-level, diffable source files. Deterministic tools should translate those source files into Nintendo DS resources and finally into a ROM build.

## Target pipeline

```text
Human creative direction
        |
        v
Game Director agent
        |
        +--------------------+-------------------+
        |                    |                   |
        v                    v                   v
World planner          Story/content       Systems engineer
        |                    |                   |
        v                    v                   v
Map DSL/YAML            Dialogue/events      C/C++/hooks
        |                    |                   |
        +----------+---------+-------------------+
                   |
                   v
            Deterministic compilers
                   |
     +-------------+----------------------------+
     |             |             |              |
     v             v             v              v
Map compiler   Asset compiler  Data compiler  Script compiler
     |             |             |              |
     +-------------+-------------+--------------+
                   |
                   v
              HG-Engine build
                   |
                   v
                 ROM
                   |
                   v
          Automated emulator runner
                   |
          screenshots + logs + state
                   |
                   v
                QA agent
                   |
                   +----> issues/fixes -> source files
```

## Repository layout

Proposed initial structure around the HG-Engine checkout:

```text
project/
  AGENTS.md
  docs/
  game/
    world/
      maps/
      regions/
      prefabs/
    story/
      chapters/
      dialogue/
      events/
    data/
      pokemon/
      moves/
      abilities/
      items/
      trainers/
      encounters/
    assets/
      source/
        buildings/
        terrain/
        vegetation/
        props/
        characters/
      processed/
  tools/
    pokeagent/
      cli.py
      maps/
      assets/
      scripts/
      data/
      rom/
      qa/
  tests/
    fixtures/
    smoke/
    integration/
  vendor/
    hg-engine/   # or use hg-engine as repository root and place custom directories alongside it
```

The agent should choose the least invasive layout after inspecting HG-Engine's real repository conventions.

## Map architecture

### Symbolic resource registry

Canonical world/content source must refer to HeartGold resources by stable
symbols. `world/registry.json` centrally owns numeric IDs, physical collision
domains, slot provenance, revision coupling, and persistent allocations.
Registry resolution and cross-reference validation occur before the binary
serializers run; serializers receive resolved numeric values and do not contain
allocation policy.

New automatic allocations may consume only source-backed `KNOWN_FREE` ranges.
Controlled vanilla replacements remain explicit, and unknown NARC capacity is
not treated as free. See `docs/STAGE_3C_TECHNICAL_REPORT.md`.

For the five proven world-resource NARCs, Stage 3E1 adds a second, distinct
allocation path: persistent contiguous members inside revision-locked
`APPEND_PROVEN` windows become `PROJECT_APPENDED`. Retail members remain
vanilla-owned, HG-Engine's generated text prefix remains `ENGINE_OWNED`, and
all logical script namespaces share the physical script-NARC collision
domain. No other archive or map-header capacity is implied. See
`docs/STAGE_3E1_TECHNICAL_REPORT.md`.

### Source

Maps should be authored through structured data, not mouse placement.

The Stage 3D static-terrain subset is now a tested intermediate layer:

```text
symbolic world + rectangular surfaces/transitions
  -> validated geometry IR
  -> deterministic quads in verified template shapes
  -> PER + BDHC from the same terrain features
  -> existing HGSS world serializers
```

It intentionally remains template-bound and quad-only. Unsupported topology,
new materials/textures, model relocation, and OBJ/GLB import must not be
inferred from this proof. See `docs/STAGE_3D_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage3d-static-geometry.md`.

The map source should describe:

- dimensions
- tiles/modules
- height/elevation
- terrain
- buildings and props
- collision
- doors/warps
- NPCs
- triggers
- camera hints where needed
- encounter zones
- metadata

### Modular environment system

World generation should use reusable DS-safe modules.

Example kit:

```text
terrain/
  grass_flat
  grass_slope_n
  grass_slope_s
  dirt_path_straight
  dirt_path_corner
  cliff_1
  cliff_corner
  water_edge
  stairs

vegetation/
  tree_small_a
  tree_small_b
  tree_large
  bush
  rock

architecture/
  house_small_a
  house_small_b
  pokemon_center
  gatehouse
  warehouse
```

Unique landmarks may use custom generated 3D models, but ordinary world construction should prefer approved modules.

## Asset pipeline

```text
concept image
   -> generated/raw 3D asset
   -> geometry validation
   -> scale normalization
   -> polygon/vertex budget enforcement
   -> UV validation
   -> texture resizing / palette constraints
   -> collision proxy generation
   -> DS-compatible conversion
   -> visual smoke test
   -> approved prefab
```

Do not rely on an LLM to manually perform deterministic mesh cleanup every time. Write tools for it.

### Asset manifests

Every processed asset should have a manifest containing at least:

```yaml
id: lighthouse_coastal_v1
source: assets/source/buildings/lighthouse_coastal_v1.glb
category: building
bounds: [x, y, z]
collision: simple
lod: ds
texture_budget: ds_standard
status: approved
```

Exact budgets should be derived from tested DS constraints and from representative original HeartGold assets rather than guessed globally.

## Pokemon data architecture

Do not scatter new species definitions across dozens of manually edited files.

Create one canonical structured species representation and generate HG-Engine-compatible files from it where possible.

Example:

```yaml
species: WYRDEER
national_dex: 899
types: [NORMAL, PSYCHIC]
base_stats:
  hp: 103
  attack: 105
  defense: 72
  sp_attack: 105
  sp_defense: 75
  speed: 65
abilities:
  normal_1: INTIMIDATE
  normal_2: FRISK
  hidden: SAP_SIPPER
```

Do not implement the full #905 roster until one species beyond the engine's comfortable existing range can be added end-to-end through the automated pipeline.

## Build orchestration

The end state should have one top-level command that:

1. validates authored schemas
2. builds/updates generated resources
3. invokes HG-Engine's build
4. verifies ROM creation
5. runs selected smoke tests
6. writes an artifact report

Example:

```bash
python -m tools.pokeagent build --test smoke
```

## Generated file policy

Mark generated files clearly.

Agents should edit canonical source files, not generated output, unless debugging the generator itself.

A generated file should be reproducible and safe to delete.

## Emulator QA

Preferred initial strategy:

- use an emulator that exposes deterministic command-line or scripting capabilities
- investigate DeSmuME's command-line, Lua, screenshot, savestate, and GDB features
- keep melonDS as a compatibility validation target

The exact testing emulator should be selected during the feasibility audit.

Useful automated checks:

- ROM boots
- save initializes
- player can enter test map
- no immediate crash
- scripted input reaches expected coordinates
- warp reaches expected map
- battle begins with expected trainer
- wild encounter table can be sampled
- screenshots match expected coarse visual properties

Avoid brittle pixel-perfect testing for normal gameplay.

Stage 4A adds a reusable declarative layer without removing the specialized
runtime regressions:

```text
tracked qa/scenarios JSON
  -> validation + deterministic plan hash
  -> bounded headless worker
  -> semantic HeartGold state adapter
  -> actions/assertions
  -> ignored trace, report, log, and screenshots
```

`tools.pokeagent.qa` owns schema, planning, subprocess orchestration, and the
stable CLI. `tools.pokeagent.qa_emulator` owns input and runtime execution while
reusing revision-specific state readers from `world_emulator`. Canonical
scenarios use map, matrix, member, position, height, collision, resource, and
marker semantics; revision-specific addresses remain centralized. See
`docs/knowledge/hgss-stage4a-gameplay-qa.md`.

## Agent loop

For a normal map request:

1. inspect current game design constraints
2. modify map source and supporting content
3. run validation
4. compile resources
5. build ROM
6. launch automated test
7. capture screenshots/logs
8. inspect output
9. fix problems
10. summarize changed files and remaining uncertainty

The agent should not stop at "code written" when a local build/test path is available.

## Stage 2 proof implementation

The bounded proof uses `fixtures/stage2_proof_map.json` as canonical input and `tools.pokeagent.world` for validation and deterministic serialization. It produces a flat transformed NSBMD, PER, BDHC, a 1 x 1 matrix, one map-header patch, one event member, one NPC script, one common controlled-start script, and one dialogue bank. Generated members and rebuilt NARCs live under ignored `build/stage2/`; the Make integration installs them only into the already ignored extracted ROM tree immediately before packing `test.nds`.

`tools.pokeagent.world_emulator` runs in the existing subprocess safety boundary. It follows the normal new-game initialization, lets a test-only hook queue the controlled warp, and asserts live location/event memory plus screenshot changes. The hook and its diagnostic symbols are compiled only with `STAGE2_MAP=Y`.

This is proof infrastructure, not the final world DSL or a general NSBMD compiler.

## Expanded map-header layer

Stage 3E2 keeps project header allocation above the retail fixed boundary in
the registry layer:

```text
symbolic schema-7 world
  -> revision-locked registry (PROJECT_HEADER)
  -> complete deterministic 24-byte header records
  -> contiguous resident project table
  -> hybrid O(1) accessor (retail below 540, project at/above 540)
  -> existing field/matrix/event/script/text runtime
```

The retail header array remains unmodified. The 27 public accessors that read
it directly are redirected at their entry points; derived helpers continue to
use those public functions. Binary serializers know only resolved field values,
while allocation/provenance stays centralized in `tools.pokeagent.registry`.

The current proven window is deliberately only IDs 540 and 541. Optional
vanilla UI/static tables do not automatically acquire project-map entries and
must be registered by later scoped systems. See
`docs/knowledge/hgss-stage3e2-map-header-expansion.md`.

## External static-asset boundary

Stage 4B establishes a deliberately bounded project-local asset path:

```text
tracked OBJ + manifest/catalog symbol
  -> bounded parser and normalized mesh IR
  -> validation + DS-oriented budget report
  -> Stage 3D quad display-list encoder
  -> symbolic cardinal map placement
  -> existing NSBMD shape + manifest-derived PER footprint
```

Source-format handling lives in `tools.pokeagent.assets`, not `world.py`.
Global HGSS resource identity remains in the Stage 3C registry; reusable asset
symbols remain in the separate asset catalog because they require no engine ID.
The accepted path reuses verified template material/texture slots and fails on
unknown topology, mappings, transforms, or shape overflow. It does not imply
triangle, BLD, new texture/material, or arbitrary model support. See
`docs/knowledge/hgss-stage4b-asset-ingestion.md`.

Stage 4C extends that same asset boundary with one bounded image path:

```text
opaque project PNG + schema-2 manifest texture symbol
  -> deterministic 32x32 PLTT16 image IR (BGR555, 16 palette slots)
  -> hash-locked replacement of one dedicated TEX0 payload pair
  -> rebuilt area texture NARC
  -> existing name-bound prop material + Stage 4B placement/collision
```

The map model remains MDL0-only; HGSS loads TEX0 separately through
`areaDataBank` and binds by Nitro resource name. The compiler preserves every
dictionary and unrelated payload and is limited to the verified `road01_r`
slot in US HeartGold area texture member 2. This is not general
NSBTX/material authoring. See `docs/STAGE_4C_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4c-texture-palette.md`.

Stage 4D adds a separate persistent project texture allocation layer:

```text
project texture symbols + PNGs
  -> stable texture catalog allocation
  -> PLTT16/BGR555 payloads
  -> hash-locked, zero-payload project BTX0 member
  -> appended area texture member + appended area-data record
  -> symbolic world header selection
  -> existing named materials and asset placements
```

The project member preserves verified dictionaries only as local binding
metadata; it contains no inherited texture/palette pixels. Authors never choose
TEX0 indices or Nitro names. The current physical pool is intentionally three
verified slot pairs and does not imply arbitrary dictionary/material creation.
See `docs/knowledge/hgss-stage4d-texture-container.md`.

Field camera scale remains orthogonal to assets. A map header may select a
fixed wider/higher retail preset, but native matrix connections require equal
camera types on both sides in the current runtime. See
`docs/knowledge/hgss-stage4d-camera-scale.md`.

Stage 4E adds typed independent primitives without changing source/catalog or
texture ownership boundaries:

```text
explicit OBJ triangle/quad faces
  -> normalized mesh IR with per-face primitive type
  -> winding, normal, UV, range, and exact-capacity validation
  -> stable consecutive triangle/quad BEGIN/END blocks
  -> existing map-model shapes/materials and project textures
  -> existing symbolic placement and footprint collision
```

Terrain continues using its proven quad compiler. Asset schemas 1--3 remain
quad-only; schema 4 is the explicit triangle capability boundary. Nitro strips,
fans, N-gons, auto-triangulation, and relocation remain outside the compiler.
See `docs/knowledge/hgss-stage4e-triangle-assets.md`.

Stage 4F makes source parsing explicitly pluggable while keeping one downstream
asset compiler:

```text
bounded OBJ parser ─┐
                    ├─> SourceMesh records -> shared normalization/typed IR
bounded GLB parser ─┘                        -> budgets/Nitro/textures/collision
```

`tools.pokeagent.asset_source` owns the source-neutral corner, face, and mesh
records. `tools.pokeagent.glb` owns only the strict offline GLB 2.0 container,
scene, bufferView, accessor, and triangle decoding boundary. GLB UVs are
canonicalized from the official upper-left convention before the existing
texture-coordinate path. The world compiler and Nitro encoder never inspect
GLB structures. See `docs/knowledge/hgss-stage4f-glb-assets.md`.

Stage 4G adds one optional format-independent optimization step:

```text
normalized typed triangle IR
  -> source display-list byte projection
  -> exact coplanar patch reduction (manifest schema 6 only)
  -> recomputed bounds/area/winding/normal validation
  -> existing typed triangle/quad encoder and verified shape capacity
```

`tools.pokeagent.mesh_simplify` preserves source/world separation: it knows no
OBJ, GLB, HGSS registry, texture container, placement, or collision format.
Materials, UV seams, and authored hard normals are protected adjacency
boundaries. Legacy schemas still fail on overflow. See
`docs/knowledge/hgss-stage4g-mesh-simplification.md`.

Stage 4H adds a gate in front of that approved path:

```text
project concept -> external generator -> immutable raw GLB + provenance
                                           |
                                           v
                               read-only intake analyzer
                                | structure | budget |
                                           v
                                  accept or reject
                                           |
                               accepted only: Stage 4F+
```

`tools.pokeagent.generated_intake` may inspect a larger untrusted GLB envelope
than the compiler, but it never repairs, normalizes, simplifies, or compiles it.
It centrally reports strict Stage 4F compliance and exact Stage 4G applicability.
Rejected candidates remain outside `assets/catalog.json`, world fixtures, and
numeric resource registries. The immutable raw hash is the downstream
determinism boundary; external generator reruns are not assumed deterministic.
See `docs/knowledge/hgss-stage4h-generated-asset-intake.md`.

Stage 4I makes model storage an explicit opt-in layer after command encoding:

```text
typed mesh IR -> Nitro display-list bytes
                         |
          legacy: inherited shape region
          schema 7: bounded MDL0-tail append + shape-record redirect
                         |
              independent model-layout parser
                         |
                 unchanged HGSS map assembly
```

`tools.pokeagent.nsbmd_model` owns only the hash-locked one-MDL0, one-model,
no-inverse-bind map-template subset. It does not parse assets, assign materials,
or write arbitrary model dictionaries. The compiler ceiling is the 4 KiB
runtime-tested project capacity; the u32 format fields and unknown hardware
ceiling are deliberately not exposed as authoring capacity. See
`docs/knowledge/hgss-stage4i-model-capacity.md`.

Stage 4J adds a second optional optimizer without changing source adapters or
model layout ownership:

```text
normalized typed IR
  -> Stage 4G exact coplanar reduction
  -> schema-8 constrained approximate reduction to encoded-byte target
  -> ordinary validation and Nitro encoder
  -> Stage 4I relocated display-list writer/parser
```

`tools.pokeagent.mesh_decimate` owns deterministic QEM-ranked edge selection,
collapse constraints, canonical ordering, and fidelity metrics. It knows no
GLB/OBJ container, registry, texture container, collision, or NSBMD layout. The
4,096-byte Stage 4I ceiling remains authoritative. See
`docs/knowledge/hgss-stage4j-approximate-decimation.md`.

Stage 4K adds a structural adapter before the unchanged strict GLB parser:

```text
bounded hierarchical GLB
  -> explicit schema-9 static-hierarchy preprocessing
  -> canonical one-node implicit-identity GLB
  -> unchanged Stage 4F parser and shared typed IR
  -> existing geometry/texture/collision/world pipeline
```

`tools.pokeagent.glb_preprocess` owns only bounded node-chain inspection, glTF
TRS composition, position baking, inverse-transpose transformation of existing
normals, and deterministic canonical GLB writing. It does not generate missing
attributes/materials, repair geometry, parse world data, or change DS model
capacity. The source hierarchy is part of the asset; normal symbolic world
placement remains a separate downstream transform. See
`docs/knowledge/hgss-stage4k-static-glb-preprocess.md`.

Stage 4L adds a second explicit attribute adapter while retaining that strict
boundary:

```text
bounded identity GLB without NORMAL
  -> explicit schema-10 crease-aware normal preprocessing
  -> canonical identity GLB with float32 NORMAL
  -> unchanged Stage 4F parser and shared typed IR
  -> existing geometry/texture/collision/world pipeline
```

`tools.pokeagent.glb_normals` owns geometric face normals, manifold edge
adjacency, 60-degree crease classification, UV-aware smoothing fans,
area-weighted averaging, deterministic attribute-vertex splitting, and bounded
canonical GLB writing. It does not create UVs or materials, repair topology or
winding, simplify geometry, or change DS storage. Stage 4K may run before this
adapter; Stage 4F remains the acceptance gate after all preprocessing. See
`docs/knowledge/hgss-stage4l-normal-generation.md`.

Stage 4M adds a third explicit pre-Stage-4F adapter:

```text
bounded identity GLB with POSITION/NORMAL but no TEXCOORD_0
  -> explicit schema-11 connected planar-patch projection
  -> canonical identity GLB with padded repeat-per-patch UV0
  -> unchanged Stage 4F parser and shared typed IR
  -> existing geometry/texture/collision/world pipeline
```

`tools.pokeagent.glb_uvs` owns manifold adjacency, strict coplanar patch
construction, stable world-oriented bases, patch-local aspect-preserving
projection, deterministic UV splits, and bounded canonical GLB writing. It
does not synthesize materials/textures, pack a unique atlas, repair topology,
or change DS storage. See
`docs/knowledge/hgss-stage4m-uv-generation.md`.

Stage 4N adds a fourth orthogonal pre-Stage-4F adapter:

```text
bounded GLB with complete geometry attributes but no material identity
  -> explicit schema-12 missing-only material assignment
  -> same GLB semantics/BIN plus one named material and primitive index
  -> unchanged Stage 4F parser and shared typed IR
  -> existing source alias / project texture / world pipeline
```

`tools.pokeagent.glb_materials` owns only material presence validation,
manifest name validation, minimal glTF material creation, primitive assignment,
and preservation reporting. It does not create Nitro materials or textures,
interpret PBR, convert vertex colors, mutate geometry, flatten hierarchy, or
change DS storage. Its bounded Stage 4K-compatible hierarchy acceptance is
neutral: nodes, scenes, transforms, mesh ownership, and BIN bytes are copied
unchanged. See `docs/knowledge/hgss-stage4n-material-synthesis.md`.

Stage 4O adds a geometry-only reduction boundary before attribute adapters:

```text
bounded embedded GLB with POSITION + indices
  -> tools.pokeagent.glb_geometry_reduce (format/safety/schema 13)
  -> tools.pokeagent.mesh_predecimate (minimal IR/QEM/fidelity)
  -> canonical small POSITION + indices GLB
  -> future explicit attribute-bootstrap composition
  -> unchanged Stage 4F and later Stage 4J/4I path
```

The GLB adapter owns container bounds, identity-only node-chain validation,
manifest policy, and deterministic geometry-only serialization. The mesh core
owns topology, connectivity, stable edge identities, collapse constraints, and
fidelity metrics. Neither module knows about Nitro commands, NSBMD, textures,
collision, registry, or world layout. Stage 4O output is intentionally not a
strict Stage 4F asset. See
`docs/knowledge/hgss-stage4o-geometry-predecimation.md`.

Stage 4P adds the explicit composition boundary Stage 4O was designed to feed:

```text
bounded POSITION + indices GLB
  -> tools.pokeagent.glb_bootstrap atomic transaction
  -> source identity + connected planar-patch UV0
  -> final UV-aware crease normals
  -> unchanged strict Stage 4F
  -> existing typed IR / texture / collision / model / world path
```

The orchestrator reuses pure Stage 4M projection, Stage 4L final normal
generation, and Stage 4N name semantics. It owns policy, ordering, provenance,
atomic validation, and reporting—not the geometry algorithms. Optional
`COLOR_0` discard is a separate explicit, hash-reported pre-geometry policy;
it is never a default or a color conversion. See
`docs/knowledge/hgss-stage4p-attribute-bootstrap.md`.
