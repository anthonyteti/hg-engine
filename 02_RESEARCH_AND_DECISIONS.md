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

## Stage 4D decision: appended project area-texture member

Allocate scalable project textures in a new revision-locked area-texture NARC
member and select it through a new appended area-data record. Preserve the
hash-verified TEX0 dictionary/layout metadata, zero every inherited payload,
and centrally allocate only verified 32 x 32 PLTT16 texture/palette slot pairs.
Project manifests use persistent symbols; physical Nitro names/indices remain
catalog-owned binding details. Retail members remain byte-identical.

This establishes multiple simultaneous project textures without pretending to
be a general TEX0/material writer. Capacity remains limited to explicitly
verified compatible dictionary slots. The camera side proof permits a fixed
wider preset, but native adjacent-map transitions retain equal camera types
until a separate connection-camera patch is designed.

See `docs/STAGE_4D_TECHNICAL_REPORT.md`,
`docs/knowledge/hgss-stage4d-texture-container.md`, and
`docs/knowledge/hgss-stage4d-camera-scale.md`.

## Stage 4E decision: independent triangles in the existing asset IR

Extend only asset manifest schema 4 and normalized mesh IR schema 2 with
explicit `triangle` and `quad` faces. Preserve authored face order, group only
consecutive equal primitive types, and encode independent Nitro primitives
with separate `BEGIN`/`END` runs. Winding must agree with explicit source
normals before encoding, and all four cardinal placements preserve handedness.

Keep strips, fans, N-gons, automatic triangulation, missing UV/normal repair,
negative OBJ indices, arbitrary transforms/materials, and display-list
relocation unsupported. The bounded mixed tower proves four triangles plus
four quads through bytes, ROM, collision, declarative QA, and front/rear visual
inspection without changing the Stage 4D texture container.

See `docs/STAGE_4E_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4e-triangle-assets.md`.

## Stage 4F decision: bounded project-owned GLB 2.0 reader

Add GLB as a source adapter only. A project-owned standard-library parser
accepts one embedded, static glTF 2.0 scene with one identity-transform mesh
node, one named material, and one to four indexed independent-triangle
primitives containing authored float32 positions, unit normals, and UVs. It
decodes tightly packed or bounded interleaved buffer views and unsigned
8/16/32-bit indices, then terminates at the same source-neutral records used by
OBJ. Normalization, winding checks, typed IR, budgets, Nitro encoding, project
textures, placement, and collision remain shared.

Reject external/remote resources, embedded images, extensions, transforms,
hierarchies, animation, skins, morphs, sparse/normalized accessors, other
primitive modes, missing attributes, and PBR material state. No dependency was
added: the evaluated MIT `pygltflib` 1.16.5 package was broader than the proof
and would not remove the need for project-specific security and subset
validation. This decision proves modern single-file interchange without
authorizing GLTF breadth, repair, simplification, or generated assets.

See `docs/STAGE_4F_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4f-glb-assets.md`.

## Stage 4G decision: exact coplanar budget adaptation

Simplify only after OBJ/GLB source adapters converge on normalized typed mesh
IR. Asset manifest schema 6 opts into a project-owned deterministic exact
coplanar-patch reducer targeting the assigned verified Nitro shape capacity.
It may merge redundant triangle subdivisions only when plane, material,
texture, UV boundary, authored hard normal, winding, and simple-boundary rules
all agree. Recompute and validate output bounds, surface area, normals, and
ordinary asset constraints before encoding; fail if exact fidelity and the byte
budget cannot both be satisfied.

Do not silently simplify legacy assets or treat this as QEM, arbitrary curved
decimation, topology repair, normal/UV generation, detailed collision, or
display-list expansion. The bounded result is a conservative prerequisite for
later generated assets, not permission to ingest malformed or production-scale
meshes.

See `docs/STAGE_4G_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4g-mesh-simplification.md`.

## Stage 4H decision: immutable generated-input intake before approval

Treat externally generated 3D as untrusted source, not as an approved asset.
Track a project-owned concept, an unedited generated GLB where redistribution
is permitted, exact generator provenance, and immutable hashes. Run a bounded
read-only intake analyzer before the Stage 4F parser; only candidates that meet
the existing source contract may acquire catalog/world identity or reach
normalization and compilation.

The first real TripoSR output is recognizable but rejected: it contains a
two-node hierarchy, vertex colors without normals/UV0/material, 6,664 triangles,
and a conditional 453,164-byte Nitro projection against the unchanged 1,068-byte
shape capacity. Stage 4G exact coplanar simplification is not applicable. Do not
flatten, synthesize attributes, approximately decimate, or weaken limits inside
the intake layer merely to pass generated output.

This result validates the intake architecture while rejecting this asset. It
does not invalidate the hand-authored OBJ/GLB factory and does not authorize
production generation. See `docs/STAGE_4H_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4h-generated-asset-intake.md`.

## Stage 4I decision: opt-in model-tail display-list relocation

Keep the typed geometry encoder separate from bounded NSBMD layout ownership.
For manifest schema 7 only, first apply the hash-locked legacy transformer with
an invisible placeholder, then append the actual project display list to the
end of the single-model MDL0 block and redirect only its 16-byte shape record.
Update the BMD0, MDL0, model, inverse-bind-end, and model-counter fields, and
reopen the result with an independent bounded parser before map assembly.

The current project ceiling is 4,096 bytes per relocated display list. This is
a runtime-tested project policy, not a Nintendo DS hardware limit. Legacy
manifests retain their original byte-for-byte layout path; non-target shape
offsets, lengths, and command payloads must remain unchanged. The Stage 4H
TripoSR input remains rejected and is not made viable by this bounded capacity
increase. See `docs/STAGE_4I_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4i-model-capacity.md`.

## Stage 4J decision: exact-first constrained approximate decimation

Permit approximate loss only for schema-8 assets that explicitly opt into a
fidelity policy and Stage 4I relocated storage. Run Stage 4G exact reduction
first, then use deterministic quadric-error-ranked manifold edge collapses until
the encoded Nitro stream first fits 4,096 bytes. Protect material/texture, UV
seams, hard normals, boundaries, and ground contact; validate bounds, surface,
normals, UVs, and five-view silhouette. Fail rather than exceed fidelity.

This project-owned standard-library implementation supports valid typed static
geometry only. It is not topology repair, hierarchy/transform handling,
missing-attribute generation, a larger model budget, or approval of the
rejected Stage 4H candidate. See `docs/STAGE_4J_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4j-approximate-decimation.md`.

## Stage 4K decision: explicit static-GLB structural canonicalization

Keep Stage 4F as the strict runtime asset boundary. Manifest schema 9 may
explicitly opt a GLB into a separate bounded preprocessor that accepts one
root-to-leaf chain of at most four static TRS nodes, composes transforms using
glTF `T * R * S` semantics, bakes positions and existing normals, and emits a
deterministic one-node implicit-identity GLB. UVs, indices, topology, and the
single named material are preserved; missing attributes are never synthesized.

Reject authored matrices, branching/DAG scenes, multiple meshes/scenes,
animation, skinning, morphs, singular or reflective transforms, and remote
resources. The immutable Stage 4H input is structurally preprocessable but
remains rejected for its independent missing-attribute/material and geometry
budget blockers. See `docs/STAGE_4K_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4k-static-glb-preprocess.md`.

## Stage 4L decision: explicit crease-aware normal canonicalization

Keep missing normals outside the strict Stage 4F parser. Manifest schema 10 may
explicitly route one otherwise-valid identity-node GLB through a bounded
preprocessor that derives geometric normals from existing triangle winding,
classifies shared edges at 60 degrees, preserves UV seams and open boundaries,
builds connected smoothing fans, and writes area-weighted float32 normals into
a deterministic canonical GLB. Hard creases are represented by deterministic
attribute-vertex splits; positions, UV values, triangle surfaces, material,
texture, collision, and world identity remain unchanged.

Reject non-manifold/inconsistently wound/degenerate geometry, missing UV or
material, authored-normal replacement, unsupported modes, and out-of-envelope
input. This is not topology repair, normal inference for invalid geometry, UV
generation, material synthesis, or approval of the Stage 4H candidate. See
`docs/STAGE_4L_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4l-normal-generation.md`.

## Stage 4M decision: repeat-per-planar-patch UV canonicalization

Keep missing UV0 outside the strict Stage 4F parser. Manifest schema 11 may
explicitly route one otherwise-valid identity-node hard-surface GLB through a
bounded adapter that groups connected coplanar faces, constructs deterministic
world-oriented bases, uniformly fits each patch into a one-texel-padded unit
square, and intentionally reuses that square across patches. This avoids a
general atlas packer while producing useful UVs for repeatable 32x32
environment textures.

Reject non-manifold/inconsistently wound/degenerate geometry, missing normals
or material, authored-UV replacement, non-planar patch merging, unsupported
modes, and out-of-envelope input. This decision does not approve the Stage 4H
candidate or add organic unwrapping, material synthesis, topology repair, or
production content. See `docs/STAGE_4M_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4m-uv-generation.md`.

## Stage 4N decision: missing-only source-material identity synthesis

Keep missing material identity outside the strict Stage 4F parser. Manifest
schema 12 may explicitly assign one bounded static triangle primitive a single
lower-snake-case source identity. Emit only one minimal glTF material name and
`primitive.material = 0`; preserve the source BIN, geometry attributes,
indices, hierarchy, transforms, and all other semantics exactly.

Reject authored-material replacement, multiple material/mesh/primitive cases,
missing required geometry attributes, `COLOR_0`, PBR/image processing,
extensions, and out-of-envelope input. The source name maps through the
existing project alias/texture path and creates no DS material resource. The
Stage 4H hierarchy is structurally inspectable, but the immutable candidate
remains rejected for independent attribute, vertex-color, and geometry-budget
blockers. See `docs/STAGE_4N_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4n-material-synthesis.md`.

## Stage 4O decision: bounded geometry-only predecimation

Add an explicit schema-13 pre-attribute adapter for one valid embedded GLB
triangle surface containing `POSITION` and indices only. Canonicalize a
minimal geometry IR, validate manifold/open-boundary topology, then use
deterministic QEM edge collapse to reach a conservative face/position bootstrap
envelope while enforcing bounds, surface, geometric-error, silhouette,
boundary, ground-contact, and crease constraints.

This is not the final DS decimator. It writes no normals, UVs, or material,
rejects auxiliary attributes such as `COLOR_0`, and leaves Stage 4J unchanged
as the complete-attribute, 4,096-byte final reducer. Invalid geometry is not
repaired. The Stage 4H candidate fits the numeric envelope but remains
ineligible due to `COLOR_0`, a zero-area face, and multiple components. See
`docs/STAGE_4O_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4o-geometry-predecimation.md`.

## Stage 4P decision: atomic missing-attribute bootstrap

Keep Stage 4F strict and replace the unproven manual chaining of isolated
Stages 4L/M/N with one schema-13 transaction for bounded geometry-only
hard-surface GLBs. Assign the manifest source identity, derive planar-patch UVs
from winding, then derive final UV-aware crease normals. Fail atomically and
record generated-attribute provenance.

Permit `COLOR_0` discard only by explicit opt-in when generated geometry will
intentionally receive a project texture and no authored/PBR appearance
resource exists. Record and remove only the color accessor; preserve geometry
semantics exactly. This does not approve Stage 4H or repair its zero-area face,
two components, or boundary topology. See `docs/STAGE_4P_TECHNICAL_REPORT.md`
and `docs/knowledge/hgss-stage4p-attribute-bootstrap.md`.

## Stage 4Q decision: exact sanitation, preserved components

Generated-topology sanitation is limited to float32-decoded triangles whose
cross-product squared magnitude is exactly zero. Near-zero nonzero triangles
remain geometry and must not be erased by a cleanup tolerance. Preserve up to
four valid disconnected components and every non-branching boundary loop;
reduce components independently with stable semantic IDs, a sixteen-face minimum,
and deterministic surface-area allocation. Never weld, fill, join, flip,
retriangulate, or select a largest component.

The controlled two-component Q -> O -> P proof passes. The immutable Stage 4H
candidate is not ready for a derived attempt: its smallest face was previously
reported as zero by Stage 4O's normal-length tolerance, but exact float32
inspection proves cross-product squared `2.6948343349697145e-19`, not zero.
The exact sanitation policy therefore correctly preserves it, after which the
Stage 4O validity gate still rejects it. See `docs/STAGE_4Q_TECHNICAL_REPORT.md`
and `docs/knowledge/hgss-stage4q-generated-topology.md`.

## Stage 4R decision: remove only target-representation-null Stage 4O blockers

Do not add a relative-area or generic tiny-triangle epsilon. A mathematically
nonzero face may be removed only when unchanged Stage 4O rejects its geometric
normal, the exact production normalization and signed 4.12 `VTX_16` quantizer
make its integer target triangle degenerate, and removal preserves component
and boundary topology. Exact-zero classification remains exclusively Stage 4Q;
target-null faces that do not block Stage 4O remain preserved.

The controlled Q -> R -> O -> P -> unchanged Stage 4F proof passes and rejects
a tiny but target-representable negative fixture. Read-only evidence shows the
Stage 4H blocking face meets this target-null rule at its intended 4 x 6 x 4
tile scale. This makes a separately authorized derived attempt ready; it does
not create or approve one. See `docs/STAGE_4R_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4r-tiny-face-policy.md`.

## Stage 4S decision: real candidate stops at the unchanged Stage 4O envelope

The explicitly authorized real TripoSR derived attempt passes immutable source
verification, explicit COLOR_0 discard, Stage 4Q exact inspection, and Stage
4R's one target-null removal. Preserve that proven prefix. Do not describe the
full generated-asset pipeline as proven: unchanged Stage 4O allocates the main
component 56 faces / 58 positions but exhausts valid constrained collapses at
177 faces / 103 positions. Stage 4P accepts at most 80 faces, and Stage 4J
requires complete attributes after Stage 4P.

Do not weaken thresholds, delete the detached component, invent provisional
attributes, or expand the model budget to force this asset through. This is a
specific reusable preprocessing blocker, not evidence that the raw source or
prior stages changed. See `docs/STAGE_4S_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4s-real-generated-asset.md`.

## Stage 4T decision: extraction resolution alone does not close the blocker

The authorized fixed TripoSR sweep reused the Stage 4H concept, foreground
policy, and exact model revision. MC48 retains the required MC64 raw silhouette
but emits two degree-4 branching open-boundary vertices and is rejected by
unchanged Stage 4Q. MC32 has one such vertex and also fails the `0.88` raw
silhouette floor. The official extraction API rejects values below 32, so MC24
and MC16 are unavailable.

Keep Stage 4Q strict and do not add boundary repair as an incidental response.
Extraction resolution is not a proven TripoSR path into the factory. Any next
generator experiment must be separately authorized and should prefer an
exporter that emits valid bounded topology. See
`docs/knowledge/hgss-stage4t-generator-topology.md`.

## Stage 4U decision: SPAR3D remains untested because official execution is unavailable

Official-source inspection confirms that the current Stability AI SPAR3D code
exposes triangle remeshing and approximate face-count targeting, so the
authorized 1000/500/250/125 experiment remains mechanically well-formed. It
could not be executed: the official hosted Space is in `BUILD_ERROR`, the
official model is gated, and this environment has neither an existing accepted
credential nor cached authorized weights. Do not use an unofficial mirror,
accept a license on the user's behalf, or substitute another generator.

This result is an access blocker, not evidence that SPAR3D topology is
compatible or incompatible. Preserve every Q/R/O/P/F/J/I contract unchanged.
The project-level sequencing decision after Stage 4U is to stop generator
research in Stage 4. Core asset/compiler infrastructure is proven for
project-authored and controlled static assets; a real external image-to-3D
landmark is not proven. TripoSR topology was unsuitable and SPAR3D had no
authorized executable route. Preserve the Stage 4H rejection, Stage 4S/4T
failures, and Stage 4U access blocker as historical results. Defer generator
selection and the mandatory real generated-landmark proof to Stage 6 Art
Factory; this deferral is not a technical pass for any of those stages. See
`docs/STAGE_4U_TECHNICAL_REPORT.md` and
`docs/knowledge/hgss-stage4u-spar3d-generator.md`.

## Stage 5B decision: runtime evidence must remain capability-specific

Keep the Victini proof opt-in and use ordinary party, Dex, follower, PC, and
battle-test APIs. Live field evidence confirms Victini data, Dex operations,
follower resolution/rendering/movement, and PC deposit; it does not justify
promoting trainer, wild, battle presentation, icon UI, cry playback, or
battery-save paths that did not execute. A representative species can increase
confidence in shared paths, but cannot promote every expanded identity.

Stage 5B-R traced the shared controlled-entry failure to stale-ROM reuse: the
QA runner did not build the scenario's declared target. An explicit build gate
restores unchanged Stage 4A basic and persistence controls. A local ignored
battle save is now created through normal new-game and `SaveGameNormal`
behavior; missing saves fail with the exact provisioning command. This is a
generic harness recovery, not a Victini patch.

The rerun proves two-sided Victini battle-test rendering and ordinary party and
box persistence through hard reset/Continue. Storage may therefore be called
representatively proven. Keep expanded base-species and follower runtime
partial because wild/capture, trainer-NARC loading, icon UI, cry routing, and a
native follower map transition remain unexecuted. Source or compiled-table
evidence still cannot replace those live paths.

## Stage 5B-C decision: one representative closes shared base-species runtime

Live Victini evidence now covers ordinary trainer-NARC loading, wild encounter,
native capture construction, encounter/capture Dex causality, party and retail
PC icon UIs, expanded cry routing, and native follower map transition in
addition to the previously proven battle/storage paths. The shared expanded
base-species runtime architecture may therefore be called representative-proven.

Do not translate this architectural proof into per-species completeness.
Victini remains content-level partial because expanded Dex category/description
text is absent, and evolution, regional-form, Mega, cry-authenticity, and
per-species correctness require their own bounded proofs. Next prove one
expanded evolution line; do not begin forms or Megas yet.
