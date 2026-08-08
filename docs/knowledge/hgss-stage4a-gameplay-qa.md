# HGSS Stage 4A declarative gameplay QA

## Finding

The existing DeSmuME proof harness can be exposed as a reusable, declarative,
bounded gameplay-QA layer without replacing its proven revision-specific
readers. A tracked JSON scenario now selects a fixture and entry strategy,
then lists actions and semantic assertions. The runner validates the complete
plan before starting DeSmuME, executes it in the existing subprocess timeout
boundary, and writes an ignored structured trace, report, screenshots, and
emulator log.

Confidence is **high for the normal HeartGold field behaviors exercised by the
three Stage 4A scenarios**. This is not a general game-playing agent, pathfinder,
OCR system, battle harness, or replacement for proof-specific binary checks.

## Architecture

```text
qa/scenarios/*.json
  -> tools.pokeagent.qa validation
  -> canonical deterministic action plan + SHA-256
  -> bounded tools.pokeagent.qa_emulator worker
  -> revision-specific semantic adapter
  -> py-desmume / DeSmuME
  -> trace.json + report.json + screenshots + emulator.log
```

`tools.pokeagent.qa` owns schema validation, deterministic plan construction,
safe ignored-output checks, subprocess orchestration, and CLI-facing reports.
`tools.pokeagent.qa_emulator` owns runtime execution. It reuses the already
runtime-proven readers in `tools.pokeagent.world_emulator` for field location,
map-header banks, matrix/member state, event counts, BDHC state, height, linker
symbols, and screenshots. Stage-specific workers remain intact as deeper
regressions.

## Scenario schema

Schema version 1 has exactly these top-level fields:

```json
{
  "schema_version": 1,
  "id": "lower_snake_case_id",
  "fixture": "fixtures/tracked_fixture.json",
  "build_target": "existing-make-target",
  "entry": {"mode": "new_game_controlled"},
  "steps": []
}
```

The alternative entry mode is `continue_existing_save`. Fixture paths must be
repository-relative and may not traverse upward. Scenario IDs, Make targets,
capture names, button names, directions, numeric widths, frame counts, move
limits, and step counts are bounded before emulator startup. Unknown fields,
actions, and assertions fail with stable error codes.

The deterministic plan is canonical JSON over schema version, identity,
fixture, target, entry, and steps. It deliberately excludes runtime timestamps,
durations, absolute artifact paths, and observed emulator state.

## Action vocabulary

| Action | Proven behavior |
|---|---|
| `wait` | advances a bounded number of frames |
| `press` | applies a named key for a bounded cadence, then releases it |
| `hold` | keeps a named key down for bounded frames |
| `release` | releases a named key and optionally advances frames |
| `move` | cardinal movement by tiles or to an X/Z target |
| `interact` | performs the proven field A-button interaction cadence |
| `capture` | records a named PNG and semantic state |
| `reset` | resets DeSmuME without substituting an emulator savestate |
| `continue` | follows the normal Continue path with an optional map target |

The controlled new-game entry still uses the proven title-screen touch point
internally. Touch is not yet a general scenario action. Real saving is triggered
by normal game/script interaction in the proof fixture; there is no synthetic
`save` action that bypasses gameplay.

All frame waits observe the worker deadline. Scenario waits are limited to
3,600 frames per step, holds to 600, movement to 96 tiles/attempts, Continue to
12,000 frames, scenarios to 256 steps, and the whole worker to the caller's
subprocess timeout.

## Semantic state snapshot

The adapter snapshot exposes:

- monotonic scenario frame and emulator running state;
- full map ID and `Location` including global X/Z, direction, and warp state;
- local X/Z derived with the proven 32-tile member width;
- active matrix ID, parsed matrix grids, and active land-data member;
- active header resource fields;
- current field height and fixed-point player Y;
- event counts;
- BDHC readiness, stripe counts, and loader slots;
- selected test marker symbols.

Ordinary scenarios do not carry revision-specific addresses. Raw memory is a
restricted escape hatch keyed by known linker symbols, validated offset,
validated width, and optional mask. The adapter intentionally reads only the
state needed at each scenario boundary rather than polling the entire engine on
every emulated frame.

## Assertion vocabulary

Supported semantic assertions are:

```text
rom_running        map_id             matrix_id
map_member         position           local_position
height             event_counts       warp_state
marker             memory_value       screenshot_valid
header_field       resource_id        bdhc_ready
movement_succeeded collision_blocked  native_transition
```

`native_transition` captures before/after snapshots, verifies the full source
and destination map IDs, performs one ordinary cardinal input, and optionally
requires the live warp state to remain unchanged. `collision_blocked` performs
the input and requires position to remain stable. They are inspectable compound
checks rather than hidden emulator features.

## Movement

One-tile movement uses the cadence already proven by Stages 2--3E2. Each tile
compares the observed coordinate to the expected cardinal delta. A mismatch is
classified as blocked when position is unchanged and unexpected otherwise.
The trace records requested/completed tiles, attempts, start/end location, and
blocked state. `move` may also target X and/or Z using deterministic X-then-Z
cardinal segments. This is deliberately not obstacle-aware pathfinding.

## Trace, diagnostics, and artifacts

Every step records:

- step index and exact source step;
- start/end frame and duration in frames;
- semantic state before and after;
- action/assertion result;
- success or structured error.

On failure the diagnostic includes a stable code, message, assertion,
expected/observed values, failing step/index, and last successful action. The
worker stops at the first failed step while retaining the trace accumulated so
far. The parent also distinguishes worker failure, timeout, missing/invalid
result, and semantic failure.

Ignored outputs use:

```text
build/qa/<scenario-id>/
  report.json
  trace.json
  emulator.log
  screenshots/<capture>.png
```

Screenshot metadata records absolute ignored path, dimensions, unique-color
count, SHA-256, frame, and semantic state. Screenshot hashes are evidence, not
pixel-perfect acceptance criteria.

## Reproduction

```bash
.venv/bin/python -m tools.pokeagent qa validate \
  qa/scenarios/stage4a_basic_world.json --json
.venv/bin/python -m tools.pokeagent qa inspect \
  qa/scenarios/stage4a_elevation.json --json
.venv/bin/python -m tools.pokeagent qa run \
  qa/scenarios/stage4a_world_persistence.json --timeout 420
```

The runner assumes the scenario's declared Make target has already produced
`test.nds`; it records that target and the ROM SHA-256 but does not silently
rebuild. This keeps build orchestration explicit and prevents one QA command
from mutating unrelated generated state.

## Confirmed behavior

Confirmed by unit tests and runtime:

- schema rejection and deterministic plan hashing;
- bounded headless worker execution and structured traces;
- cardinal movement, collision, height, native transition, event/header/member
  state, marker interaction, screenshots, reset, and normal Continue;
- real battery-save restoration of full project header 541;
- actionable expected/observed failure diagnostics;
- stable operation for 600 further frames in every representative scenario.

Confirmed by unit tests/synthetic adapters only:

- explicit `hold` and `release` actions;
- target-coordinate movement independent of a particular fixture;
- raw linker-symbol memory masks and several failure branches.

## Migration boundary

The declarative runner now covers representative Stage 2 movement/collision,
Stage 3D height/terrain, and Stage 3E2 project-header/persistence behavior.
Specialized historical tests remain authoritative for detailed binary/runtime
instrumentation: exact Stage 2 NPC/warp/dialogue checks, the Stage 3A height
profile, Stage 3B's four-cell loop, Stage 3C registry behavior, Stage 3D's
per-transition geometry assertions, Stage 3E1 archive identity/count checks,
and Stage 3E2 accessor counters and binary hook validation.

Unknown or deliberately unsupported:

- general pathfinding and recovery around obstacles;
- OCR or generic dialogue text extraction;
- battle, menu, inventory, party, encounter, and touch-screen action models;
- generic save-menu automation or emulator savestate authoring;
- arbitrary memory addresses not present in the revision-locked symbol map;
- other ROM revisions or emulator backends;
- automatic source repair or a Game Director loop.

## Battery-save isolation note

The py-desmume/DeSmuME process uses the shared user-local
`~/.config/desmume/test.dsv` path for `test.nds`. A specialized proof that saves
can therefore affect a later scenario whose entry contract is
`new_game_controlled`. Stage 4B regression reproduced this: Scenario C observed
the right header/resources but a persisted field follower blocked its first
movement. Isolating the generated DSV and rerunning from a clean battery state
passed 19/19 assertions without scenario changes.

Until the adapter gives every run a private battery-save path, orchestration
must explicitly preserve/remove or isolate that ignored DSV according to the
scenario's entry strategy. This is confirmed runtime behavior, not an emulator
savestate issue.
