# Roadmap

## Stage 0: Repository and toolchain audit

Goal: understand reality before writing a custom framework.

Tasks:

- fork or clone HG-Engine
- prove an unmodified build from a user-supplied base ROM
- record exact host dependencies
- prefer Docker or WSL on Windows if it improves reproducibility
- inventory how HG-Engine stores trainers, Pokemon data, items, moves, encounters, scripts, maps, graphics, and text
- inspect Pokemon DS Map Studio source and export path
- inspect relevant HeartGold map/event tooling source
- identify every step that currently requires a GUI
- determine which can be invoked as a library/CLI and which need reimplementation
- select an emulator automation route

Deliverable:

`docs/AUTOMATION_AUDIT.md`

The audit must classify operations:

```text
HEADLESS_NOW
HEADLESS_WITH_WRAPPER
REQUIRES_FORMAT_IMPLEMENTATION
GUI_ONLY_TEMPORARILY
UNKNOWN
```

No game content work before this audit.

## Stage 1: Reproducible base build

Goal: one command produces a bootable modified ROM.

Acceptance:

- clean checkout + documented local prerequisites works
- base ROM is never committed
- generated ROM is ignored by Git
- `build` script returns nonzero on failure
- build log is captured
- simple harmless source/data change appears in emulator

Kill condition:

If HG-Engine cannot be built reliably in a reproducible environment, stop and reassess rather than layering automation on top.

## Stage 2: Headless map vertical slice

Goal: generate and insert one new playable map without repetitive GUI editing.

Minimum map:

- small outdoor area
- collision
- one building/door or equivalent warp
- one NPC
- one item pickup
- one trainer
- one wild encounter zone
- one conditional event/flag

Acceptance:

- map is generated from text-based source
- build is deterministic
- rerunning generator does not accumulate corruption
- map can be rebuilt after deleting generated output
- emulator reaches map
- screenshots can be captured automatically or semi-headlessly without manual map editing

### Primary kill gate

If achieving this still requires a human repeatedly operating a map editor for ordinary content changes, stop expansion work.

At that point compare the remaining work against switching the production target to Platinum.

## Stage 3: Build the world DSL

Only after Stage 2 passes.

Tasks:

- formalize map schema
- add reusable prefabs
- implement validation for bounds, overlaps, invalid warps, unreachable exits, bad NPC coordinates, and missing references
- implement deterministic IDs
- create a simple rendered/debug representation before ROM build

Acceptance:

- LLM can create a second map purely by editing structured source
- compiler reports actionable errors
- maps can reference reusable approved assets

## Stage 4: Autonomous QA loop

Tasks:

- scripted emulator boot
- savestate/test-state strategy
- deterministic test entry points where practical
- screenshots
- crash/time-out detection
- battle smoke tests
- map traversal tests
- machine-readable test report

Acceptance:

The agent can modify a test map, rebuild, launch, inspect evidence, and fix an error without human emulator interaction.

## Stage 5: Modern roster proof

Do not add hundreds of species at once.

Proof sequence:

1. confirm one already-supported expanded species path
2. add or fully normalize one later species through the canonical generator
3. add one regional form
4. verify one Mega Evolution end-to-end
5. verify save/load, box, party, battle, evolution, dex, icon, sprite, and trainer/wild usage

Only after these pass should bulk roster generation begin.

## Stage 6: Art factory

Tasks:

- define visual bible
- create one environment kit
- automate DS asset constraints
- add asset manifests
- create validation metrics
- build 5-10 approved modular assets
- prove generated landmark conversion

Acceptance:

A model can request a new building variant and the pipeline produces a DS-safe candidate plus a screenshot without manual Blender cleanup for the normal case.

Human review remains allowed for art direction.

## Stage 7: Game vertical slice

Build approximately 20-40 minutes of actual game:

- starting town
- first route
- first dungeon or landmark
- second town
- first gym/boss
- rival/story event
- encounters
- trainers
- items
- dialogue
- custom environment kit

Do not begin the full region until this slice feels like a real game.

## Stage 8: Scale production

Only after the factory is stable.

At this point LLM usage shifts from reverse engineering toward content production, which is the intended cost profile.

## Gen 5 revisit gate

Consider starting the B2W2 branch only when all are true:

- HeartGold map generation is headless
- asset pipeline is reusable
- emulator QA is automated
- content schemas have stabilized
- at least one polished vertical slice exists
- the user still considers Gen 5 presentation worth the extra engineering

Then port the abstractions, not the HeartGold binary tooling.
