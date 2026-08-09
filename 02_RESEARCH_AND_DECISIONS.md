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

## Stage 3C decision: symbolic IDs with conservative provenance

All new world authoring must use stable symbolic resource identities resolved
through the tracked `world/registry.json`. Numeric ownership, collision domains,
revision hashes, and persistent allocations belong to the registry layer, not
to authoring agents or binary serializers.

The earlier proof IDs remain explicit `CONTROLLED_REPLACEMENT` records. Existing
vanilla members are not considered free, and structurally addressable appended
NARC IDs remain `UNKNOWN` until runtime-tested. This conservative policy removes
raw LLM-managed IDs without claiming unsupported capacity.

See `docs/STAGE_3C_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage3c-reference-registry.md`.

## Stage 3D decision: bounded declarative static terrain

Generalize the hash-locked template path only through a project-owned,
quad-based static-terrain IR. Canonical rectangular surfaces and X/Z
transitions drive visual display lists, PER, and BDHC together. Deterministic
material aliases bind to three existing template shape/material pairs; their
known capacities are hard limits, and overflow fails without relocation.

This passes the reusable geometry kill gate for moderately complex primitive
terrain, but does not authorize arbitrary topology, new materials/textures,
OBJ/GLB import, display-list relocation, or a general NSBMD writer. Those remain
separate future decisions. The tested result supports continuing on HeartGold.

See `docs/STAGE_3D_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage3d-static-geometry.md`.

## Stage 3E1 decision: provenance-aware contiguous NARC append

The five NARCs used by the world compiler may allocate only the small,
revision-locked contiguous windows proven by source inspection, binary
validation, and live gameplay. Appended members are `APPEND_PROVEN` /
`PROJECT_APPENDED`, not `KNOWN_FREE`; HG-Engine's post-retail text prefix is
separately `ENGINE_OWNED`. Local scripts, common scripts, and script headers
share one physical collision domain.

This decision establishes bounded new resource capacity without claiming the
whole `u16` space or expanding the fixed map-header table. Stage 3E2 remains a
separate kill gate.

See `docs/STAGE_3E1_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage3e1-narc-append.md`.

## Stage 3E2 decision: hybrid resident map-header expansion

Preserve the retail 540-entry map-header table byte-for-byte and route its 27
direct public accessors through a project-owned constant-time selector. IDs
0--539 retain retail behavior; revision-locked project IDs start at 540 and
index a deterministic resident table generated from symbolic registry source.
Do not perform per-lookup NARC I/O or bless retail-looking slots as free.

`HEADER_EXPANSION_PROVEN` and `PROJECT_HEADER` remain distinct from vanilla and
controlled-replacement ownership. The current emulator-tested allocation
window is 540--541; extending it requires an explicit registry/window change.
Normal loading, native adjacency, scripts/events/text, warp, and real
save/reset/Continue were verified. Optional Town Map/Fly and special-mode
registrations remain future content-system work, not a core field blocker.

See `docs/STAGE_3E2_TECHNICAL_REPORT.md`,
`docs/knowledge/hgss-stage3e2-map-header-expansion.md`, and
`docs/knowledge/hgss-stage3e2-map-id-width-audit.md`.

## Stage 4B decision: bounded quad OBJ ingestion into map geometry

Accept one deterministic project-authored OBJ subset: explicit planar quads,
UVs, normals, and manifest-mapped source materials. Normalize source axes,
units, scale, anchor, and winding into the Stage 3D tile/Y convention, then
encode the result through the already proven Nitro quad path. Reject unsupported
topology and capacity overflow before ROM build.

For the first proof, merge symbolic asset placements into verified existing map
NSBMD shapes and derive rectangular PER collision proxies from the same manifest
placement. Reuse hash-locked template materials/textures; do not introduce BLD,
new NSBTX/material authoring, Blender, triangles, or a general model importer.
This keeps the legal boundary local and proves source-driven asset ingestion
without overstating the supported asset envelope.

See `docs/STAGE_4B_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4b-asset-ingestion.md`.

## Stage 4C decision: fixed-slot project texture ingestion

Keep the Stage 4B OBJ/manifest/placement boundary and add one exact,
revision-locked image compiler: an opaque 32 x 32 PNG becomes a deterministic
Nitro PLTT16 texel stream and 16-entry BGR555 palette. HGSS loads map textures
from the area-data BTX0/TEX0 resource separately from the MDL0-only map model,
then binds resources by name. For the proof, replace only the exact-size
`road01_r` texture/palette payload pair used by the dedicated prop shape;
preserve dictionaries, offsets, every unrelated payload/member, and the
Stage 4B geometry/collision path.

Do not infer support for other texture modes, dimensions, transparency,
quantization, multiple materials/textures, dictionary extension, payload
relocation, or a general NSBTX writer. The bounded result is sufficient to
continue the asset factory without Nintendo converters or GUI tooling.

See `docs/STAGE_4C_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4c-texture-palette.md`.
