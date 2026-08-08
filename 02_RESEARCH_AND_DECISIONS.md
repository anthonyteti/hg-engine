# Research and Decision Record

Research snapshot: 2026-08-07

## HeartGold + HG-Engine

HG-Engine describes itself as an overhaul for English Pokemon HeartGold focused on bringing battles closer to newer mainline mechanics.

Its documented feature set includes:

- Dex expansion, documented as almost complete through Gen 6
- ability expansion
- move and item expansion with later-generation content
- Mega Evolutions and Primal Reversions
- Fairy type
- Hidden Abilities
- modernized battle behavior
- more configurable trainers
- 30 PC boxes

Its build system supports a normal command-line `make` flow and also documents a Docker build. Various game data can be edited from project files under its source tree.

The repository also contains hooks and code for Mega behavior, form handling, battle calculations, expanded systems, and related engine features.

### Strengths for this project

- Mega Evolution already exists.
- Expansion architecture already exists.
- The engine is designed specifically for substantial HeartGold modifications.
- Reproducible command-line ROM builds already exist.
- We can spend early engineering time on autonomous world/content generation rather than first recreating the modern battle layer.

### Weaknesses

- HeartGold is not as thoroughly decompiled into readable C as Platinum.
- HG-Engine relies heavily on hooks, inserted code, armips data, and knowledge of the retail binary.
- Existing map authoring tools are primarily interactive applications.
- A fully headless map/event pipeline still has to be engineered.

## Platinum

`pret/pokeplatinum` is the strongest Nintendo DS Pokemon codebase for LLM source comprehension. It is a mature decompilation with a large C codebase and a conventional source-oriented structure.

### Strengths

- Best source readability among the DS mainline Pokemon projects.
- Easier for an LLM to trace and modify original engine behavior.
- Strong reference for understanding Gen 4 systems.
- Very attractive fallback if HeartGold's binary-oriented areas become a severe automation bottleneck.

### Weaknesses for this project's current priorities

- It does not provide an HG-Engine-equivalent mature modern gameplay layer out of the box.
- Adding a roster through Legends: Arceus plus Mega Evolution would require more engine work before content production.

## Pokemon DS Map Studio

Pokemon DS Map Studio supports Diamond/Pearl, Platinum, HeartGold/SoulSilver, Black/White, and Black 2/White 2.

It provides a tilemap-like authoring model that automatically converts a map to a 3D model. Its public README describes an interactive Java application and notes that NSBMD export requires Nintendo conversion components.

For this project, the source code is more valuable than the GUI. The first tooling task is to determine whether its conversion logic can be called headlessly, extracted into a library, or recreated in our own compiler.

Do not assume a supported official headless CLI exists until verified in code.

## Decision

Start with HeartGold + HG-Engine, but enforce an early automation kill gate.

The project remains on HeartGold only if the agent can establish a deterministic, scriptable workflow for new maps and their supporting data.

If world automation remains dependent on fragile GUI control after the feasibility phase, move the production target to Platinum.

This is preferable to building HeartGold and Gen 5 simultaneously because the most valuable work is engine-agnostic:

- map DSL design
- content schemas
- asset processing
- QA architecture
- model routing
- build orchestration

Those abstractions can later be ported to another DS engine.

## Gen 5 decision

Do not actively develop the Gen 5 implementation yet.

Current Gen 5 work shows that an LLM-native B2W2 pipeline is plausible, but it requires substantially more infrastructure and reverse engineering. The right time to revisit it is after the HeartGold vertical slice proves that the autonomous workflow itself is productive.

See `GEN5_FUTURE.md`.

## Stage 2 decision: bounded NSBMD template transformation

For the one-map zero-GUI proof, use a hash-locked transformation of a user-local HeartGold NSBMD template. Project code replaces the template display lists with deterministic valid geometry while retaining compatible local material/texture dictionaries. Do not redistribute the source member or generated binary.

This decision rejects a silent dependency on Nintendo `g3dcvtr` and does not claim to solve general NSBMD authoring. A broader open model compiler remains a later kill gate before world-content scaling. The proof is sufficient to continue with HeartGold because it generates new flat geometry, boots through the native engine, and keeps the proprietary input boundary identical to the existing ROM build.

See `docs/knowledge/nsbmd-stage2-model-path.md` and `docs/STAGE_2_TECHNICAL_REPORT.md`.
