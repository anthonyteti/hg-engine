# HG-Engine expanded-species runtime: Victini proof boundary

## Finding

The current fork executes `SPECIES_VICTINI` (544) end to end through ordinary
party, trainer-NARC, wild encounter, capture, Dex state, battle presentation,
party/PC icon UI, expanded cry routing, follower transition, PC storage, and
battery-save systems. Stage 5B-C therefore proves the shared expanded
base-species runtime architecture for one representative. This does not prove
every species/form or fill Victini's missing expanded Dex category/description.

## Generic recovery finding

The original controlled-entry failure was stale-ROM reuse: `qa run` did not
build the scenario's declared target. An explicit `--build` path now records
and gates that build. The unchanged Stage 4A basic and persistence scenarios
pass again, including normal battery save, hard reset, and Continue.

The battle runner's ignored `test.sav` can now be provisioned reproducibly:

```bash
make battle-test-save
```

The command executes the ordinary Stage 5B save/reset/Continue QA path,
extracts its DeSmuME battery container into an ignored raw 512 KiB save, and
validates semantic readiness. Clean AUTO builds explicitly install the
Stage 5B-C proof world and preserved common-script bank. It does not download
or track a save. Missing or malformed saves produce an actionable error naming
this command.

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

The inventory representative is `COMPLETE_EXECUTED`, with shared runtime
architecture `REPRESENTATIVE_PROVEN`. Victini's top-level content status stays
`PARTIAL`; a representative pass does not promote all 1,025 expanded base
identities or any forms.

## Stage 5B-C closure evidence

- trainer 737 serialized and loaded species 544, level 5, form 0, moves
  93/116/529/513 through the ordinary trainer NARC;
- encounter bank 142 produced ordinary level-20 base-form Victini battles;
- encounter changed Dex state 0/0 -> 1/0 and native capture changed it to 1/1;
- capture produced an ordinary species-544 party Pokémon with valid PID,
  ability 162, and moves 93/116/529/513;
- live cry routing observed 544 -> expanded pseudo-bank 778 and playback load;
- party and retail PC UIs selected/rendered Victini icon resources/palettes;
- native map 540 -> 541 transition retained follower species 544/tag 3044 and
  continued movement;
- the unchanged 73/73 party/box persistence matrix, Stage 4A controls,
  known-good Color Change battle, and two-sided Victini battle all pass.

## Remaining unknowns

- expanded Dex category/description content;
- authenticity/quality of every expanded cry (routing is proven for Victini);
- ordinary expanded evolution lines and evolution-form persistence;
- regional-form and Mega runtime behavior;
- per-species correctness beyond the one representative and static inventory.
