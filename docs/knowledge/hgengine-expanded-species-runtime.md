# HG-Engine expanded-species runtime: Victini proof boundary

## Finding

The current fork can instantiate `SPECIES_VICTINI` (544) through ordinary
Pokémon code and retain it through party and boxed battery-save serialization.
The existing battle-test engine resolves its front/back graphics and moves,
and field runtime resolves its data, Dex bits, follower sprite, and PC storage.

Stage 5B remains partial because ordinary wild/capture, trainer-NARC, icon UI,
cry routing, and native follower-transition paths have not all executed.
Confidence is **confirmed for the explicitly listed live paths**, not for every
expanded species or form.

## Generic recovery finding

The original controlled-entry failure was stale-ROM reuse: `qa run` did not
build the scenario's declared target. An explicit `--build` path now records
and gates that build. The unchanged Stage 4A basic and persistence scenarios
pass again, including normal battery save, hard reset, and Continue.

The battle runner's ignored `test.sav` can now be provisioned reproducibly:

```bash
make battle-test-save
```

The command boots a locally built proof ROM, follows normal new-game behavior,
calls the game's normal save routine, exports a raw 512 KiB battery save, and
validates semantic readiness. It does not download or track a save. Missing or
malformed saves produce an actionable error naming this command.

## Evidence and reproduction

- `fixtures/stage5b_victini_runtime.json`: expected identity/data.
- `fixtures/stage5b_victini_world.json`: opt-in ordinary save NPC.
- `src/stage5b_runtime.c`: ordinary party/Dex/follower/PC operations.
- `src/battle_save_provision.c` and `tools/pokeagent/battle_save.py`: local
  normal-save provisioning.
- `qa/scenarios/stage5b_victini_runtime.json`: semantic persistence plan.
- `data/battle_tests/stage5b/victini_runtime.c`: two-sided battle proof.
- `tools/pokeagent/qa.py`: scenario-declared build gate.

```bash
python3 -m tools.pokeagent qa run \
  qa/scenarios/stage4a_world_persistence.json --build --timeout 300

make battle-test-save
TEST_RUNNER_SCREENSHOT_DIR=build/stage5br-battle-screens \
  python3 scripts/run_tests.py

python3 -m tools.pokeagent qa run \
  qa/scenarios/stage5b_victini_runtime.json --build --timeout 600
```

Observed Victini values are species 544, level 20, base form,
Psychic/Fire, Victory Star, moves 93/116/529/513, seeded HP 37/76, and 51 for
every other calculated stat. Follower resolution is sprite tag 3044.

The field rerun passed 73/73 semantic assertions. Party and box save/reset/
Continue preserved identity, form, level, and moves; party persistence retained
HP 37, while normal box withdrawal reconstructed full HP 76. The battle runner
passed a known-good Color Change control and the Victini two-sided test with
front/back rendering and move execution.

## Architectural boundary

`STAGE5B_RUNTIME_PROOF` and `BATTLE_SAVE_PROVISION` are independent opt-in
flags. Neither adds roster data or changes normal builds. Runtime state is
asserted through exported semantic symbols; scenario JSON contains no raw
revision address. Generated ROMs, saves, screenshots, and reports stay ignored.

The inventory representative remains `PARTIAL_EXECUTED`. A representative
pass increases confidence only in shared paths actually executed; it does not
promote all 1,025 expanded base identities or any forms.

## Remaining unknowns

- trainer and wild compiled-table expanded-ID resolution;
- ordinary capture-created Victini and encounter/capture Dex-bit causality;
- party and PC icon UI/palette rendering;
- cry resolver/playback routing for pseudo-bank index 778;
- follower continuity through a native map transition;
- expanded Dex UI content beyond already-proven number/name/sprite/bit storage.
