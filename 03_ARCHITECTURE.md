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
