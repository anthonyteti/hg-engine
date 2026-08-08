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

### Source

Maps should be authored through structured data, not mouse placement.

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
