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

### Completed infrastructure checkpoint: Stage 4A

A tracked JSON scenario can now drive bounded deterministic field actions and
semantic assertions through one headless DeSmuME runner. Representative Stage
2 movement/collision, Stage 3D height/terrain, and Stage 3E2 native
transition/save/reset/Continue flows pass through the reusable engine. Each run
writes an ignored machine-readable trace/report, captures named screenshots,
and reports actionable expected/observed failure context.

This checkpoint does not add pathfinding, OCR, battle automation, assets, or an
autonomous Game Director. Historical specialized regressions remain in place
for format- and proof-specific instrumentation. See
`docs/STAGE_4A_TECHNICAL_REPORT.md`.

### Completed infrastructure checkpoint: Stage 4B

One tracked project-authored quad OBJ now compiles deterministically through a
manifest/catalog, neutral normalized mesh IR, conservative budget, existing
Nitro display-list encoder, symbolic placement, and manifest-derived PER
collision. It renders as a grounded static shed shell and passes declarative
Stage 4A approach, collision, around-object movement, screenshot, and stability
QA without Blender or GUI cleanup.

This checkpoint deliberately reuses one verified template material and merges
the prop into an existing map-model shape. It does not add triangles, new
textures/materials, BLD, independent prop resources, asset kits, image-to-3D,
or production content. See `docs/STAGE_4B_TECHNICAL_REPORT.md`.

### Completed infrastructure checkpoint: Stage 4C

One tracked project-authored 32 x 32 opaque PNG now compiles deterministically
to Nitro PLTT16 texels and a BGR555 palette, replaces one hash-verified
texture/palette payload pair in the HGSS area texture resource, and binds to
the Stage 4B imported shed. Binary parsing proves dictionary and unrelated-NARC
preservation; a clean HG-Engine ROM build plus declarative collision/stability
QA and Codex visual inspection prove the atlas in game.

This checkpoint does not add triangle/N-gon support, other texture formats or
dimensions, transparency, lossy quantization, multiple/new materials,
dictionary expansion, general NSBTX generation, GLB, simplification,
image-to-3D, environment kits, or production content. See
`docs/STAGE_4C_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4c-texture-palette.md`.

### Completed infrastructure checkpoint: Stage 4D

Multiple persistent project texture identities now compile into one newly
appended, project-owned area texture member selected by an appended area-data
record. Two differently textured quad assets render together with independent
symbolic bindings and collision while the retail NARC prefixes remain
byte-identical. The fixed wider camera preset is proven; native camera-type
changes across matrix connections and smooth pullback remain deferred.

The checkpoint remains bounded to three verified 32 x 32 opaque PLTT16 slot
pairs, inherited material state/dictionary metadata, the supported US revision,
and quad assets. It does not start triangle/GLB/simplification/image-to-3D,
production kits, or content. See `docs/STAGE_4D_TECHNICAL_REPORT.md`.

### Completed infrastructure checkpoint: Stage 4E

Explicit triangle and quad OBJ faces now flow through a typed deterministic
mesh IR and independent Nitro primitive encoder. One project-authored faceted
tower combines a four-quad shell with a four-triangle roof, retains the Stage
4D project texture and manifest collision, builds through HG-Engine, and passes
binary parsing, declarative walk-around QA, and front/rear visual inspection.

The checkpoint deliberately excludes N-gons, strips/fans, automatic
triangulation/repair, negative indices, display-list relocation, GLB,
simplification, image-to-3D, production landmarks/kits, and content. See
`docs/STAGE_4E_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4e-triangle-assets.md`.

## Completed infrastructure checkpoint: Stage 3E2

The revision-locked hybrid map-header layer has been proven for project IDs
540 and 541. It preserves all retail headers, resolves symbolic project
records into a resident generated table, and passes native traversal, warp,
normal save/reset/Continue, determinism, and prior-stage regressions. This is
the final header-capacity proof; it does not begin content production or add
optional Town Map/Fly registrations.

See `docs/STAGE_3E2_TECHNICAL_REPORT.md`.

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
