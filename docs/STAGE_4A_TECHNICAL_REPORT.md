# Stage 4A technical report: reusable autonomous gameplay QA

## Verdict

`STAGE_4A_QA_FRAMEWORK_PASSED`

Representative world movement, collision, multi-height terrain, native map
transition, resource/script interaction, real save, reset, Continue, screenshot
capture, and post-action stability are now expressed by tracked JSON scenarios
and executed through one bounded headless QA engine. Failures produce semantic
expected/observed diagnostics rather than bare assertions.

## Stage 3E2 checkpoint

Stage 4A began only after the intentional Stage 3E2 tree was staged, reviewed,
committed, pushed, and remotely verified:

- commit: `c1c42130f Add Stage 3E2 expandable map header system`;
- full commit: `c1c42130f451a47f39c67b75c160f3c7dbc0b061`;
- branch: `main`;
- local `HEAD`, `origin/main`, and `git ls-remote origin main` agreed;
- the worktree was clean before Stage 4A implementation.

No ROM, generated archive, screenshot, save, extracted asset, log, credential,
or ignored build output entered that checkpoint.

## Implementation

Stage 4A adds two deliberately separated layers:

- `tools.pokeagent.qa`: tracked-scenario validation, deterministic action-plan
  hashing, ignored artifact-path enforcement, bounded subprocess orchestration,
  report assembly, and CLI integration;
- `tools.pokeagent.qa_emulator`: DeSmuME adapter, semantic state snapshots,
  deterministic input/movement, assertions, traces, captures, and worker result.

The adapter reuses the revision-specific, emulator-proven readers from
`tools.pokeagent.world_emulator`; it does not duplicate their pointer traversal
or change any prior specialized worker. All prior proof fixtures and test entry
hooks remain unchanged.

## Canonical scenarios and schema

Three tracked schema-1 scenarios were added:

| Scenario | Existing fixture | Purpose |
|---|---|---|
| `stage4a_basic_world` | Stage 2 | boot, map/events, movement, blocked tile, capture, stability |
| `stage4a_elevation` | Stage 3D | lower terrain, two transitions, raised heights, cliff blocking, return |
| `stage4a_world_persistence` | Stage 3E2 | headers 540/541, native edge, resources/dialogue, save/reset/Continue |

Top-level scenario fields are version, stable ID, tracked fixture path, declared
Make target, explicit entry strategy, and ordered steps. The schema rejects
unknown keys and unsafe paths/names before launching DeSmuME. New canonical QA
files contain semantic names and values, not revision-specific memory addresses.

The canonical action plans hash to:

| Scenario | Steps | SHA-256 |
|---|---:|---|
| basic world | 13 | `541202f17b5b40443ad83783ef925ff317859889eefc20edebcab346491f1f26` |
| elevation | 28 | `55a4f2225d88218ab47960d134c232a449b78a0314001980c682b0147f9f226b` |
| world/persistence | 36 | `90faeb8785851f5c13b7c6a075896c3489140951e6aa0ea0e49df49e5b731bbd` |

Repeated parsing produces these same hashes. Runtime timestamps, wall duration,
absolute output paths, and emulator observations remain outside deterministic
scenario semantics.

## Action vocabulary and movement

Schema 1 supports `wait`, `press`, `hold`, `release`, `move`, `interact`,
`capture`, `reset`, and `continue`. Every action has bounded parameters and a
trace record. Invalid buttons/directions, excessive waits or moves, unsafe
capture names, unsupported fields, and overlarge scenarios fail validation.

The shared movement primitive supports cardinal tile counts and deterministic
X/Z targets. Each requested tile uses the proven field-input cadence and checks
the resulting coordinate. It distinguishes successful movement, expected
position-stable collision, unexpected displacement, and attempt exhaustion,
and exposes the result in the trace. It does not implement pathfinding.

## Assertion vocabulary and state

Schema 1 supports:

```text
rom_running, map_id, matrix_id, map_member, position, local_position,
height, event_counts, warp_state, marker, memory_value, screenshot_valid,
header_field, resource_id, bdhc_ready, movement_succeeded,
collision_blocked, native_transition
```

The reusable snapshot contains frame/running state, full map/location identity,
global and member-local coordinates, height/fixed-point Y, active matrix/member,
header resource banks, event counts, warp state, BDHC readiness/stripes, and
known proof markers. Revision addresses remain centralized behind the adapter.
Raw memory assertions require a known linker symbol and bounded offset/width.

## Entry and persistence

`new_game_controlled` exposes the existing, explicit proof entry hook and title
sequence as a reusable entry strategy. `continue_existing_save` follows normal
Continue without creating or loading an emulator savestate.

The Stage 3E2 east NPC script remains the normal in-game save trigger. Scenario
C interacts with it, waits for the proven scripted return to header 540, resets
DeSmuME, selects Continue, and asserts that the battery save restores header
541, map member 677, event 492, and dialogue marker 46. The field then remains
stable for 600 frames.

## Trace, reports, and screenshots

Each ignored `build/qa/<scenario-id>/trace.json` entry records source step,
start/end frame, duration, before/after snapshot, result, success, and structured
error. `report.json` adds scenario/build identity, ROM SHA-256, plan, entry
strategy, emulator/binding evidence, assertion totals, final state, duration,
errors, and artifact paths. `emulator.log` retains the DeSmuME startup/version
banner and subprocess output.

Named captures record path, 256 x 384 dimensions, unique-color count, SHA-256,
frame, and snapshot. Codex visually inspected the Stage 2 map/NPC, Stage 3D
terrace/cliff, Stage 3E2 dialogue, and post-Continue field. Geometry, sprites,
dialogue, and collision-correlated positions rendered coherently. Screenshot
hashes are not used as brittle visual assertions.

## Runtime results

### Scenario A: basic world movement

- PASS: 13 steps and 9/9 assertions;
- controlled entry reached map 267 at `(16,16)`;
- live event counts were one NPC and two warps;
- east movement into the deliberate blocked tile did not change position;
- west/east normal movement returned to `(16,16)`;
- the ROM remained running for another 600 frames;
- final frame: 8,146;
- screenshot SHA-256:
  `bfad3801a9b8ad654017d68fbca2b7d26d0f5d01f5ff5e16549b215293689df0`.

### Scenario B: elevation and collision

- PASS: 28 steps and 13/13 assertions;
- controlled entry reached Stage 3D map 538 on height 0;
- transition A reached height 4 / fixed Y 131,072;
- the irregular cliff boundary blocked direct movement;
- transition B returned through the separate south connection to height 0;
- lower-terrain traversal then reached position `(14,27)`;
- live BDHC state was ready with six stripes;
- the ROM remained running for another 600 frames;
- final frame: 9,667;
- three named screenshots were captured and visually inspected.

### Scenario C: world and persistence

- PASS: 36 steps and 19/19 assertions;
- controlled entry reached project header 540, matrix 288, member 676, event
  491, and the west NPC/dialogue marker 45;
- one ordinary east movement crossed X 31 to 32, changed to header 541/member
  677, wrapped local X to zero, and left warp state at `-1`;
- east event 492, script 966, script-header 968, text 855, and dialogue marker 46
  were observed through the project header;
- the normal script save completed, reset/Continue restored header 541 and its
  distinct resources, and the ROM remained stable for 600 frames;
- final position `(36,15)`, local `(4,15)`, final frame 15,958;
- four named screenshots were captured and visually inspected.

## Controlled failure/fix experiment

An ignored one-step scenario entered through `continue_existing_save` and
intentionally asserted `map_id = 999`. It failed at step zero with:

```text
code: semantic_assertion_failed
expected: 999
observed: 541
position: (36,15)
member: 677
warp: -1
```

The failed report and trace were retained under ignored build evidence. Changing
only the scenario expectation to 541 produced a pass with 1/1 assertions. No
game source was modified for the experiment.

## Tests and regressions

- New QA unit tests: 14 passed.
- Full suite: 121 tests ran; 118 passed and 3 opt-in integration tests skipped.
- Registry validation: 11 namespaces / 32 resources, passed.
- Preflight: all command, Docker-context, Git-hygiene, Python, ROM, and system
  checks passed.
- Stage 2: clean build and specialized headless runtime passed.
- Stage 3A: clean build and specialized headless runtime passed.
- Stage 3B: clean build and specialized headless runtime passed.
- Stage 3C: clean build and specialized headless runtime passed.
- Stage 3D: clean build and specialized headless runtime passed.
- Stage 3E1: clean build and specialized headless runtime passed.
- Stage 3E2: final clean build and specialized headless runtime passed.

Stage 3E2 world determinism also reran with zero mismatches across its generated
header table, registry snapshot, world components, NARCs, and patched ARM9.
Stage 4A deterministic-plan tests cover identical semantics independent of
runtime metadata. Existing PER `0x14`, BDHC, matrix-transition, registry,
append, header-expansion, revision-lock, and artifact-safety checks remain
unchanged.

## Unit failure coverage

Tests cover schema version/shape, unknown action/assertion, invalid button and
direction, invalid/excessive frames, unsafe capture and fixture paths,
deterministic plans, semantic snapshot/assertion success and failure, movement
success and collision, structured diagnostics, reset/Continue planning,
screenshot metadata, native transition, and malformed fixture references.
Synthetic adapters keep these tests network-free and independent of local ROM
material.

## DeepSeek

No DeepSeek call was needed. Stage 4A was a project-local architecture and
integration task over already proven readers and emulator behavior; Codex
implemented and verified it directly. Token usage: 0. Estimated cost: `$0`.

## Boundaries and migration

The reusable layer now expresses representative checks from Stages 2, 3D, and
3E2. Specialized regressions remain in place for detailed format/binary checks
and broader proof-specific coverage from Stages 2--3E2. They can migrate
incrementally only when equivalent semantic readers are justified.

Not yet supported: general pathfinding, OCR/text extraction, arbitrary touch,
battle/menu/inventory/party automation, generic save-menu navigation,
savestate setup, visual-AI assertions, other ROM revisions, or automatic source
repair. Explicit `hold`/`release`, target movement, and low-level masked linker
symbol reads have unit/synthetic coverage but are not separate acceptance
scenarios.

## Recommendation

Stage 4A passes. The reusable QA foundation is sufficient to support a later,
separately scoped Stage 4B environment asset pipeline: future asset work can
reuse declarative boot, movement, collision, height, transition, capture, trace,
and diagnostics. Stage 4B should proceed only after this Stage 4A source/report
is checkpointed; it has not begun here.
