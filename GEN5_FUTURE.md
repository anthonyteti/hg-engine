# Gen 5 Future Track

Status: deferred, not abandoned.

## Why it is deferred

A Black 2/White 2 autonomous project appears technically plausible, but it currently needs more infrastructure than the HeartGold route.

Running both projects now would duplicate:

- reverse engineering
- build orchestration
- map tooling
- content schemas
- emulator QA
- asset conversion
- token-heavy repository exploration

The highest-value abstractions can be proven once on HeartGold and later ported.

## Relevant Gen 5 ecosystem

The research identified a useful stack around B2W2:

- PMC for compiled code injection
- swan for known functions/structures/symbols
- White2Upgrade for an early modernized/expanded B2W2 base
- Gen 5 editors and map tools as format knowledge sources
- Pokemon DS Map Studio for Gen 5-compatible map creation concepts
- newer project-based tooling for scripts/maps/trainers/encounters
- animation reconstruction tools that expose Gen 5 battle sprite structure

A Pokemon Black decompilation is also useful as reverse-engineering reference, but a B2W2 production project would likely remain a hybrid source/injection/tooling environment.

## Desired Gen 5 target

If started later:

- Pokemon White 2 base
- autonomous content compiler
- Pokemon through Legends: Arceus
- Mega Evolution
- no requirement for Z-Moves, Dynamax, Terastallization, or PLA battle styles
- machine-generated maps/assets/data
- no repetitive GUI editing

## Revisit criteria

Do not create the Gen 5 repository until:

1. HeartGold has a headless new-map pipeline.
2. HeartGold has automated ROM build and emulator QA.
3. The map/content schemas are stable enough to be engine-neutral.
4. The asset factory has at least one working DS-safe environment kit.
5. A polished HeartGold vertical slice has been generated.
6. Gen 5 visuals are still important enough to justify additional engineering.

## First Gen 5 experiments when revisited

Do not begin with a full region.

### Experiment A: new species beyond existing expansion

Add one Pokemon beyond the current expansion boundary end-to-end:

- stats
- types
- abilities
- moves
- evolution
- icon
- front/back graphics
- animation
- Pokedex
- wild encounter
- trainer use
- party/box/save/load

### Experiment B: one Mega Evolution

Implement and validate one complete Mega flow:

- eligibility
- held item/trigger
- battle command
- one-Mega restriction
- form transition
- stats
- ability
- sprite/animation
- battle completion
- save safety

### Experiment C: one generated map

Create a new playable B2W2 map entirely from machine-readable source without opening a GUI editor for normal authoring.

If A, B, and C pass, the Gen 5 project becomes a credible production option.
