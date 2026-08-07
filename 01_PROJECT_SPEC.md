# Project Specification

## Working objective

Create an LLM-native development environment for a custom Nintendo DS Pokemon fan game using Pokemon HeartGold and HG-Engine.

The finished workflow should minimize human interaction with traditional ROM-hacking GUI applications. The user should primarily provide creative direction, approve visual results, and make game-design decisions.

## Engine

Primary:

- Pokemon HeartGold
- HG-Engine

Reference/fallback:

- `pret/pokeplatinum`

Deferred research track:

- Pokemon White 2 / Black 2
- PMC / swan / Gen 5 tooling

## Gameplay target

The first engineering phase does not require the final gameplay roster. Design the architecture so the following can be added later without restructuring the project:

- Pokemon through Legends: Arceus, National Dex #905
- relevant regional forms
- modern stats, types, moves, abilities, and evolution rules where desired
- Mega Evolution as the main battle gimmick

Do not assume that every later-generation mechanic should be ported. In particular, the initial design does not require:

- Z-Moves
- Dynamax or Gigantamax
- Terastallization
- Legends: Arceus Strong/Agile battle system
- overworld catching mechanics from Legends: Arceus

## Automation requirements

The desired long-term command surface is conceptually:

```bash
pokeagent build
pokeagent map build <map-id>
pokeagent map validate <map-id>
pokeagent asset build <asset-id>
pokeagent trainer build
pokeagent encounters build
pokeagent scripts build
pokeagent rom build
pokeagent test smoke
pokeagent test map <map-id>
```

The exact CLI name is not important. A simple Python CLI is preferred initially.

## Canonical source of truth

Game content should live in text-based, diffable files wherever practical.

Preferred formats:

- YAML for authored game content and configuration
- JSON only where another tool requires it
- PNG for 2D source images
- GLB or another common interchange format for generated 3D source assets
- C/C++/assembly only for engine features that require code

Example map source:

```yaml
id: port_azure
name: Port Azure
size: [48, 40]
theme: coastal_starting_town

exits:
  south:
    destination: route_01
  north:
    destination: route_02
    condition: FLAG_FIRST_BADGE

buildings:
  - prefab: pokemon_center
    position: [18, 15]
  - prefab: lighthouse
    position: [41, 7]

npcs:
  - id: fisherman_01
    archetype: fisherman
    position: [36, 27]
    dialogue: fisherman_port_azure_01
```

The schema will evolve after the agent learns the actual HeartGold map/event formats.

## Asset philosophy

Do not generate every world object as a unique arbitrary 3D model.

Use a layered system:

1. AI concept generation for visual exploration.
2. AI/image-to-3D for unique landmarks and selected buildings.
3. Automated DS optimization and conversion.
4. A curated modular environment kit for normal map construction.
5. Procedural or LLM-generated map layouts using those approved modules.

A region should have a coherent reusable vocabulary of terrain, cliffs, roads, vegetation, architecture, interiors, and props.

## Human role

Expected human work:

- creative direction
- choosing between visual alternatives
- approving map/gameplay results
- defining high-level story and game design
- resolving ambiguous design decisions

Work that should be automated:

- repetitive asset conversion
- map placement
- metadata entry
- encounter/trainer table generation
- script compilation
- ROM packing/building
- emulator smoke tests
- screenshot collection
- regression checks
- data validation

## Non-goals for Phase 1

- full region
- all Pokemon through #905
- final story
- final custom art style
- custom soundtrack pipeline
- online/wireless functionality
- preserving every original HeartGold side system

The first objective is proving the factory, not filling the factory with content.
