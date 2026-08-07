# Autonomous Pokemon DS Project

Research snapshot: 2026-08-07

## Decision

Start with **Pokemon HeartGold + HG-Engine** as the only active engine.

Do not build the Gen 5 project in parallel yet. Preserve the Gen 5 research as a future branch, but spend engineering effort on proving one autonomous Nintendo DS content pipeline first.

This decision is conditional on an early automation gate:

> The project must be able to create, insert, build, launch, and test a new map without repetitive human GUI editing.

If a clean headless HeartGold world pipeline cannot be established after the initial tooling milestones, pivot the production project to `pret/pokeplatinum` rather than sinking large amounts of time into GUI automation or fragile binary patching.

## Why HeartGold first

HG-Engine already solves several expensive gameplay-engine problems that would otherwise become prerequisites:

- expanded species infrastructure
- expanded moves, abilities, and items
- Fairy type
- Hidden Abilities
- Mega Evolution and Primal Reversion
- modern battle sequencing and effects
- more configurable trainers
- normal command-line ROM builds

This makes HeartGold the best first target when the desired final game may include a large modern Pokemon roster and Mega Evolution.

Platinum remains an important reference because `pret/pokeplatinum` is substantially more readable as source code. If HeartGold automation becomes the bottleneck, Platinum is the fallback.

## Project philosophy

The human is the director, not the map editor.

A normal content request should eventually look like:

```text
Create a coastal starting town with six houses, a Pokemon Center,
a lighthouse, a fishing pier, a southern Route 1 exit, and a northern
path that unlocks after Gym 1.
```

The system should generate or modify structured project files, build the ROM, launch an emulator test, collect screenshots/logs, validate the result, and iterate.

Repeated manual placement in GUI tools is considered technical debt.

## First milestone

Do not start building the full game.

Build a vertical-slice factory that produces:

```text
Town A
  -> Route 1
  -> Small Cave
  -> Town B
  -> Gym
```

Acceptance criteria:

- build is reproducible from the command line
- one new custom map is generated from machine-readable source
- collision works
- warps work
- NPC placement works
- dialogue works
- flags and variables work
- trainer battle works
- wild encounter table works
- item pickup works
- screenshots can be captured for QA
- no repetitive GUI editing is required
- the pipeline can rebuild the same result from a clean checkout

## Files in this pack

- `01_PROJECT_SPEC.md`: canonical project goals and constraints
- `02_RESEARCH_AND_DECISIONS.md`: engine research and decision record
- `03_ARCHITECTURE.md`: target autonomous toolchain
- `04_ROADMAP.md`: staged implementation plan with kill gates
- `05_LOCAL_SETUP.md`: Windows/WSL and coding-harness setup
- `AGENTS.md`: operating rules for coding agents
- `MODEL_STRATEGY.md`: cost-conscious model and harness routing
- `INITIAL_AGENT_PROMPT.md`: first prompt to give Codex, Claude Code, or another coding harness
- `GEN5_FUTURE.md`: preserved Gen 5 plan and criteria for revisiting it
- `SOURCES.md`: primary sources used for the research

## Legal and project hygiene

- Do not commit or distribute commercial Pokemon ROMs.
- The user supplies a legally obtained base ROM locally.
- Keep generated builds, extracted proprietary assets, and local ROM material out of Git.
- Keep the project noncommercial. HG-Engine explicitly states that creations using it should be freely accessible and not monetized.
- Preserve upstream credits and licenses.

## Immediate next action

Give `INITIAL_AGENT_PROMPT.md` plus this repository to the coding harness.

The first agent session should perform a repository and toolchain audit. It should not begin designing the fan game itself.
