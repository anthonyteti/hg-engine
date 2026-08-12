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

### Completed infrastructure checkpoint: Stage 4F

A tracked project-authored GLB now decodes through a strict offline glTF 2.0
subset into the same neutral records, normalized typed triangle IR, Nitro
encoder, project texture, symbolic placement, footprint collision, and QA path
as OBJ. The GLB and reference OBJ towers are semantically equivalent after
normalization; the GLB build renders correctly and passes binary, gameplay,
visual, mutation, and clean-root determinism gates.

The checkpoint deliberately excludes external resources, embedded textures,
node transforms/hierarchies, non-triangle modes, sparse accessors, animation,
skins, morphs, PBR material translation, repair, simplification, image-to-3D,
and production assets. See `docs/STAGE_4F_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4f-glb-assets.md`.

### Completed infrastructure checkpoint: Stage 4G

An opt-in project-owned exact coplanar simplifier now reduces a valid 48-
triangle GLB from a genuinely overflowing 3,276-byte display-list projection
to an exact four-quad/four-triangle 648-byte model inside the unchanged 1,068-
byte shape capacity. Bounds, area, hard normals, UV/material identity, texture,
collision, symbolic IDs, runtime behavior, and visual appearance remain
preserved; unreachable tighter targets fail clearly.

The checkpoint is deliberately limited to redundant planar triangle patches
with simple three/four-corner boundaries. It excludes approximate/QEM curved
decimation, malformed-mesh repair, normal/UV generation, display-list
expansion, image-to-3D, generated services, production kits, and content. See
`docs/STAGE_4G_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4g-mesh-simplification.md`.

### Stage 4H generated-input finding

A genuine anonymous TripoSR image-to-3D run now has an immutable project-owned
concept/provenance/raw-GLB chain and a reusable read-only intake analyzer. The
first candidate was correctly rejected before compilation: it lacks normals,
UV0, and a source material; contains a hierarchy and 6,664 triangles; and would
project to 453,164 Nitro bytes against a 1,068-byte shape capacity. The exact
Stage 4G simplifier cannot apply.

This is not a completed generated-asset runtime checkpoint. It establishes the
honest rejection boundary and identifies future preprocessing gaps without
weakening GLB, geometry, or budget validation. See
`docs/STAGE_4H_TECHNICAL_REPORT.md`.

### Completed infrastructure checkpoint: Stage 4I

Project assets may now opt into a bounded relocated map-model display list
instead of inheriting the selected retail shape's byte allocation. A valid
56-triangle gatehouse that fails the old 1,068-byte region at 3,820 bytes is
appended to a rebuilt MDL0 model tail under a 4,096-byte tested ceiling, while
all 17 other shape payloads remain unchanged. The independent parser, ROM
build, collision walk-around, visual QA, mutation, stress, and determinism
gates define the supported boundary.

This checkpoint does not approve the Stage 4H generated candidate or add
approximate decimation, attribute generation, hierarchy handling, arbitrary
materials, display-list regions beyond 4 KiB, or a general NSBMD writer. See
`docs/STAGE_4I_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4i-model-capacity.md`.

### Completed infrastructure checkpoint: Stage 4J

Valid single-material non-coplanar static meshes may now opt into an exact-first
deterministic approximate reduction policy. The dense shrine falls from 14,156
projected Nitro bytes (10,928 after the exact pass) to a validated 4,024-byte
relocated stream while preserving declared bounds, surface, silhouette,
normals, UVs, texture, collision, and identity.

This checkpoint does not repair malformed meshes, generate normals/UVs, flatten
hierarchies, increase the 4 KiB ceiling, approve the Stage 4H candidate, or
begin production art. See `docs/STAGE_4J_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4j-approximate-decimation.md`.

### Completed infrastructure checkpoint: Stage 4K

A valid two-node static GLB rejected by the unchanged Stage 4F boundary can now
opt into deterministic structural preprocessing. Parent/child translation,
quaternion rotation, and positive scale are composed and baked into existing
positions/normals; the output is a canonical one-node identity GLB whose bytes,
typed IR, display list, collision, and texture binding exactly match a direct
flat reference. Runtime build, collision walk-around, visual QA, and two-root
determinism pass.

This checkpoint does not synthesize materials, normals, or UVs; support
arbitrary scenes/matrices/reflections; change the 4 KiB model ceiling; retry the
Stage 4H candidate; or begin production assets. See
`docs/STAGE_4K_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4k-static-glb-preprocess.md`.

### Completed infrastructure checkpoint: Stage 4L

An otherwise-valid identity-node GLB lacking `NORMAL` may now opt into bounded,
deterministic crease-aware normal generation. The canonical proof derives
area-weighted smoothing fans at a predeclared 60-degree threshold, preserves UV
seams and open boundaries, splits only attribute vertices, and produces bytes
identical to an independently authored-normal reference accepted unchanged by
Stage 4F.

This checkpoint does not generate UVs/materials, repair topology/winding,
simplify geometry, process or approve the Stage 4H candidate, expand model or
texture capacity, or begin production art. See
`docs/STAGE_4L_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4l-normal-generation.md`.

### Completed infrastructure checkpoint: Stage 4M

An otherwise-valid bounded identity-node hard-surface GLB lacking
`TEXCOORD_0` may now opt into deterministic connected planar-patch UV
generation. The canonical proof preserves aspect ratio, uses stable
world-oriented bases and one texel of 32x32 padding, permits intentional island
overlap, exactly matches an authored reference, and renders coherently through
the unchanged Stage 4F and HeartGold pipeline.

This checkpoint does not synthesize materials/textures, repair topology,
perform organic unwrap or atlas packing, process/approve Stage 4H, expand
budgets, or begin production art. See `docs/STAGE_4M_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4m-uv-generation.md`.

### Completed infrastructure checkpoint: Stage 4N

An otherwise-valid bounded GLB with one material-less triangle primitive may
now explicitly acquire one manifest-declared source material identity. The
adapter preserves every geometry/attribute/index BIN byte, matches an
independently authored reference, passes the unchanged Stage 4F parser, binds
through the existing project stone texture, and passes deterministic ROM and
visual gameplay QA.

This checkpoint does not create DS material state, textures, PBR mappings,
vertex-color conversion, topology repair, generated-mesh processing, or
production content. The Stage 4H candidate remains rejected. See
`docs/STAGE_4N_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4n-material-synthesis.md`.

### Completed infrastructure checkpoint: Stage 4O

A project-authored 1,056-triangle geometry-only reconstruction fixture now
deterministically reduces to 64 triangles and 35 positions under a schema-13
opt-in policy. The result stays within predeclared geometric and five-view
silhouette fidelity limits, retains valid one-component open-manifold topology,
and lies safely inside the later attribute-bootstrap envelope.

This checkpoint does not emit normals, UVs, material, textures, or a runtime
asset; Stage 4J remains the final 4 KiB decimator. Stage 4H is unchanged and
rejected. The next stage should prove a bounded explicit attribute-bootstrap
composition and decide `COLOR_0` policy rather than add another isolated
adapter. See `docs/STAGE_4O_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4o-geometry-predecimation.md`.

### Completed infrastructure checkpoint: Stage 4P

One bounded geometry-only hard-surface GLB now deterministically acquires a
manifest source identity, repeat-per-planar-patch UV0, and final UV-aware
crease normals in one atomic transaction, passes unchanged Stage 4F, and
renders through the existing HeartGold runtime/QA path. Stage 4O output is
proven compatible with this boundary. Explicit discard of bounded non-runtime
`COLOR_0` is proven only for project-textured generated geometry.

Stage 4H remains rejected: its color format is structurally eligible for the
policy, but one zero-area face, two components, and 25 boundary loops remain
outside the valid-source contract. The next engineering decision should be a
separately scoped generated-topology intake policy, not production art. See
`docs/STAGE_4P_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4p-attribute-bootstrap.md`.

### Completed infrastructure checkpoint: Stage 4Q

One generated-style 1,073-face project fixture with `COLOR_0`, one exact
collinear face, two meaningful components, and an open boundary is now
deterministically sanitized, independently reduced to the Stage 4P envelope,
bootstrapped, and accepted by unchanged Stage 4F. Exact-zero provenance,
near-zero preservation, stable component budgets, boundary-loop invariants,
and order/mutation determinism are machine-tested. No face is welded, filled,
flipped, joined, heuristically discarded, or repaired.

The real Stage 4H candidate remains rejected and is not ready for a derived
attempt. Its smallest triangle is nonzero under the exact Stage 4Q definition,
so removing it would require a separately justified tiny-face policy rather
than exact sanitation. Stage 4R, if authorized, should decide that narrow
numeric-validity boundary; it must not start production art or general repair.
See `docs/STAGE_4Q_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4q-generated-topology.md`.

### Completed infrastructure checkpoint: Stage 4R

The production coordinate path is now explicit: normalized tile coordinates
enter the model at scale 0.25 and encode as signed 4.12 `VTX_16` values using
nearest/ties-to-even rounding. One nonzero face may be filtered only when it
blocks unchanged Stage 4O, becomes exactly degenerate in those integer target
coordinates, and passes component/boundary safety checks. Exact Stage 4Q and
representable tiny geometry remain untouched.

The controlled Q -> R -> O -> P -> strict Stage 4F proof passes. Read-only
Stage 4H evidence shows its blocking face is target-null at intended scale and
hypothetical removal leaves two valid components and 25 valid loops. A derived
candidate is ready for a separately authorized attempt, but none was created
or approved. Stage 4S, if authorized, should be that bounded derived-copy
attempt and must retain all fidelity, 4 KiB, runtime, provenance, and visual
rejection gates. See `docs/STAGE_4R_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4r-tiny-face-policy.md`.

### Completed kill-gate checkpoint: Stage 4S

The first authorized derived attempt from the immutable real TripoSR asset
passes its COLOR_0, exact sanitation, and target-null gates, then correctly
stops at unchanged Stage 4O. The main component cannot reach its allocated
56-face/58-position target; valid constrained collapses end at 177 faces/103
positions. No Stage 4P/F/J/model/ROM/QA artifact is produced, and no fidelity,
topology, or 4 KiB limit is weakened.

Stage 4 infrastructure therefore has one specific blocker rather than a proven
real pipeline. Do not automatically add another Stage 4 substage or begin Stage
5. The next decision should explicitly choose between a narrowly justified
pre-bootstrap reduction architecture and a generator/export path that produces
simpler topology. See `docs/STAGE_4S_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4s-real-generated-asset.md`.

### Completed blocked checkpoint: Stage 4T

The fixed TripoSR extraction-resolution experiment did not provide a natural
path into the existing factory. MC48 preserves the MC64 raw silhouette but has
branching open-boundary topology rejected by Stage 4Q. MC32 has the same
structural problem and fails raw fidelity. MC24/MC16 are below the official
API's supported minimum.

No compiler threshold or algorithm changed, and no candidate reached Stage 4O,
Stage 4P, a model, ROM, or QA. Stage 4 asset infrastructure still has the
specific generator-topology blocker. Do not automatically start another
generator experiment or Stage 5. See `docs/STAGE_4T_TECHNICAL_REPORT.md`.

### Completed access-blocked checkpoint: Stage 4U

The authorized official SPAR3D experiment stopped before generation. Official
source inspection confirms the requested triangle-remesh/target-count sweep is
supported approximately, but the official hosted Space is in `BUILD_ERROR`,
the official model is gated, and no already-authorized local credential or
weights are available. No unofficial service, alternate generator, license
acceptance, or topology change was used.

This does not establish SPAR3D topology or fidelity. Stage 4S/T/U remain
failed or blocked exactly as reported. The project now closes Stage 4 research
sequencing without declaring those experiments passed: controlled static
asset/compiler infrastructure is proven, while real external image-to-3D
generation is deferred to Stage 6 Art Factory. Do not resume Stage 4 generator
tuning. See `docs/STAGE_4U_TECHNICAL_REPORT.md`.

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

### Stage 5B complete: Victini shared runtime matrix

The original opt-in proof established personal data, generated moves, party,
Dex APIs, follower lookup/rendering/movement, and ordinary PC deposit. Stage
5B-R recovered its generic blockers: QA now builds the declared target, the
unchanged Stage 4A persistence control passes, and an ignored battle save can
be provisioned through normal game save behavior. The rerun additionally
proves two-sided battle-test front/back rendering and ordinary party and box
battery persistence through hard reset/Continue.

Stage 5B-C closes the remaining ordinary shared paths: trainer NARC, wild
encounter, native capture, encounter/capture Dex causality, party/PC icon UIs,
expanded cry routing, and native follower transition all execute for Victini.
The shared expanded base-species architecture is representative-proven while
Victini retains its historical audit-level `PARTIAL` label. Stage 5F later
confirmed that this label was caused by a conservative Stage 5A heuristic:
the expanded Dex text already exists in the canonical source/generator path.

Next prove one expanded evolution line end to end, including ordinary
evolution and persistence. Do not infer regional-form or Mega support from
Victini, and do not begin bulk roster normalization.

### Stage 5C complete: representative expanded level evolution

One unchanged Popplio individual executes the existing level-17 Brionne and
level-34 Primarina evolutions through normal Rare Candy use. PID/form/party
identity, recalculated data, icon/follower refresh, Brionne and Primarina party
persistence, and boxed Primarina persistence all survive ordinary battery
save, hard reset, and Continue. This proves one expanded plain-level evolution
line only. Do not enumerate the other generic evolution methods as independent
proof stages: test them only when a production species or a discovered
compatibility gap requires one. The next distinct architectural risk is
regional-form runtime representation, lineage, presentation, and persistence,
beginning with Hisuian Zorua -> Hisuian Zoroark in Stage 5D.

### Stage 5D complete: representative regional-form runtime

The existing base-species-plus-form representation resolves Hisuian personal
data and icon/follower/battle assets, survives party and box battery saves, and
preserves form 1 and PID through ordinary Zorua -> Zoroark evolution. The wild
`u16` form-bit path also decodes identity 1335 correctly. This is one
representative line, not proof of all regional identities or form-Dex content.
The next distinct representative mechanic is one existing Mega Evolution
end-to-end (Stage 5E).

### Stage 5E complete: representative Mega runtime

The existing Altaria + Altarianite path activates through the native battle
UI, resolves Mega Altaria identity 1108 with its types, ability, calculated
stats, and back sprite, executes a move, and retains the one-use state for the
battle. Ordinary battle completion restores species 334/form 0 before field
and battery-save persistence; PID/item remain stable, and eligibility returns
in a later battle.

Do not add another representative mechanic proof automatically. Stage 5F is
roster/content gap closure planning and implementation driven by the Stage 5A
inventory and Stage 5B-E evidence. It must separate missing functionality,
missing data/content, incomplete identities/forms, cosmetic/authenticity gaps,
and unexecuted cases already covered by shared architecture.

### Stage 5F complete: semantic roster/content closure

Stage 5F preserves the historical flat audit statuses and adds production
scope, form-family requirements, readiness, reason codes, truthful cry
provenance classes, and the Stage 5B-E representative evidence. The #1-1025
production roster contains all 1,025 implemented base species, resolved by
National Dex order rather than the engine's reserved-ID-shifted constants; all
1,025 have the required static
data/assets and safe shared runtime paths. All 1,025 implemented base records
already carry nonempty category/description content through `Species.c` and
speciesdatagen; five ordinary expanded-generation Dex views confirm the live
archive/UI path. Gen 5+ cry routing is complete but source authenticity remains
explicitly unverified nonblocking debt.

Persistent regional forms and scoped temporary Megas have no required static
gaps. Gigantamax is out of game scope, filler identities are reserved, and
other special forms are classified by semantic family instead of being
mislabelled for intentionally absent follower/Dex behavior. Stage 5 foundation
work is complete with nonblocking content/provenance debt. Do not add another
representative Pokémon-mechanic stage.

### Stage 5F-S final scope correction

The supported production roster is Bulbasaur through Pecharunt, National Dex
#1-1025. The main journey will later curate approximately 300-350 species;
whole-game/postgame completion must eventually make all 1,025 obtainable.
Gigantamax remains excluded. All current-fork Mega identities are classified
under temporary-form requirements, and Pecharunt provides the bounded upper-Dex
UI regression. Stage 5 is closed after this correction; the next activity is
the unchanged Stage 6 Presentation Factory.


## Stage 6: Presentation Factory

Purpose: give the LLM high-level deterministic control over essentially the
complete game UI and the reusable environment-art system before the real game
vertical slice.

Stage 6 is intended to execute under one autonomous master prompt. It will
maintain a persistent state file, automatically checkpoint successful
technical substages, define recovery behavior, and interrupt the user mainly
for the final integrated presentation approval or a genuine external-access,
legal/license, or destructive irreversible high-risk blocker. Stage 6A visual
direction uses `AUTONOMOUS_CODEX_SELECTION`; aesthetic uncertainty does not
pause the program. Each substage must declare `OBJECTIVE`, `REQUIRED_EVIDENCE`,
`PASS_CONDITIONS`, `FAIL_CONDITIONS`, `COMMIT_RULE`, `NEXT_STAGE_RULE`, and
`HUMAN_REVIEW_RULE`.

Conceptual orchestration state:

```yaml
stage: 6
status: in_progress
current:
  id: 6F
completed: [6A, 6B, 6C, 6D, 6E]
blocked: []
human_review:
  final_presentation: pending
```

### Stage 6A — Visual Direction & Presentation Bible

Define visual language, HGSS/DS readability rules, regional environment
language, palette and typography principles, UI aesthetics, spacing,
iconography, sprite/image hierarchy, texture density, asset budgets, and
biome/environment principles. Codex develops at least three meaningful
directions, scores and adversarially reviews them, then autonomously selects one
direction or controlled hybrid. This is not a human gate.

### Stage 6B — Complete UI Reality Audit

Inventory title/Continue, dialogue, start menu, party, summary, Bag, PC,
Pokédex, profile, Town Map, shops, save/options, naming, battle HUD,
HP/status, move and target selection, Mega control, capture/evolution, touch
regions, fonts, and transitions. Classify each as `RESOURCE_ONLY`,
`LAYOUT_DATA`, `CODE_DRIVEN`, `OVERLAY_CODE`, `ENGINE_PATCH_REQUIRED`, or
`UNKNOWN`.

### Stage 6C — UI Resource Factory

Compile project-owned deterministic source assets into DS graphics, palettes,
tilemaps, sprites, fonts, icons, and UI manifests without repetitive GUI work.

### Stage 6D — Declarative UI Engine

Create high-level primitives such as `Window`, `Panel`, `Text`, `Sprite`,
`PokemonSprite`, `PokemonIcon`, `ItemIcon`, bars/meters, `Cursor`, `Button`,
`TouchButton`, lists/grids/tabs, scrolling, modals, portraits, and animation.
Bind them to semantic values such as `player.name`, `party[0].species`,
`battle.player.active.hp`, `bag.current_pocket`, and `pokedex.seen_count`, with
declarative navigation/touch behavior rather than arbitrary DS addresses.

### Stage 6E — Battle UI Proof

**Status: passed.** Declarative source materially redesigns battle command/move
surfaces and the neutral HUD palette while preserving native text, Bag, switch,
Run, targeting and Mega controllers. Focused live QA proves Fight/Mega and
Bag/switch/Run branches; target selection remains bound to the unchanged native
controller and audited target-screen resource.

### Stage 6F — Core Menu UI

Prove party, Pokémon summary, Bag, and player/start-menu surfaces.

### Stage 6G — Remaining Game UI

Expand to PC, Pokédex, shops, save/options, Town Map, title/Continue,
dialogue, naming, capture/evolution, and remaining important screens. The end
state is full high-level LLM authorship, not a global reskin.

### Stage 6H — UI Automated QA

Validate opening/exiting, navigation reachability, touch targets, selection,
semantic bindings, text overflow, bounds/overlap, sprite/icon identity,
VRAM/OAM budgets, animation stability, and screenshot review. Pixel-perfect
comparison is supporting evidence, not the primary signal.

### Stage 6I — Environment Art Kit

Build DS-safe terrain, slopes, paths, cliffs, water edges, stairs, bridges,
vegetation, rocks, architecture, props, fences, lamps, signs, market pieces,
and utility modules.

### Stage 6J — Procedural Variants & Asset Catalog

Provide controlled variants and catalog every approved asset by identity,
source, category, biome tags, footprint, bounds, rotations, collision,
textures, DS budget, status, and visual metadata. World planning requests
catalog identities rather than Nitro internals.

### Stage 6K — Unique Landmark / Real Generated 3D Kill Gate

Run art direction -> concept -> authorized real generator/exporter -> immutable
raw output -> Stage 4 preprocessing -> DS compilation -> ROM -> visual QA.
At least one real generated landmark must pass. Stage 4H/S/T/U remain negative
and access evidence, never retroactive success.

### Stage 6L — Integrated Presentation QA

Combine the new UI, environment kit, representative custom world, and generated
landmark in one ROM. Run automated QA first and a final human presentation
review second. Stage 6 passes only when Stage 7 no longer needs ordinary manual
UI or environment editing.

Do not begin Stage 6 implementation during Stage 5F.

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
