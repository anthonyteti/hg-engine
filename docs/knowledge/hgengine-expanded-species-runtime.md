# HG-Engine expanded-species runtime: Victini proof boundary

## Finding

The current fork can instantiate `SPECIES_VICTINI` (544) through ordinary
Pokémon code and resolve its personal data, generated level-up moves, party
representation, Dex bits, follower mapping/graphics, and boxed-Pokémon
representation in a live field ROM. The requested end-to-end runtime matrix is
not complete because two shared test dependencies failed independently of the
species: controlled field entry and the missing ignored battle `test.sav`.

Confidence is **confirmed by live partial execution and source/build
inspection**, not confirmed end to end.

## Evidence

- `fixtures/stage5b_victini_runtime.json`: canonical expected identity/data.
- `src/stage5b_runtime.c`: opt-in ordinary party/Dex/follower/PC calls.
- `qa/scenarios/stage5b_victini_runtime.json`: semantic state and persistence
  plan.
- `data/battle_tests/stage5b/victini_runtime.c`: two-sided compiled battle
  scenario.
- `data/BaseStats.c`, `data/learnsets/learnsets.json`,
  `src/field/overworld_table.c`, and existing Victini graphics: upstream data
  sources retained unchanged.

Observed runtime values were species 544, level 20, base form, Psychic/Fire,
Victory Star, moves 93/116/529/513, HP 37/76, and 51 for every other calculated
stat. The follower resolver returned 3044. PC storage preserved species, form,
level, and all moves after deposit. Dex seen/caught APIs advanced the owned
count to nine in the controlled fixture.

## Reproduction

```bash
make stage5b-runtime-proof
python3 -m tools.pokeagent qa run \
  qa/scenarios/stage5b_victini_runtime.json --timeout 300

python3 scripts/build_tests.py stage5b
make AUTO_TEST=Y
python3 scripts/run_tests.py

python3 -m unittest \
  tests.test_pokeagent_qa \
  tests.test_pokeagent_stage5a_roster_inventory \
  tests.test_pokeagent_stage5b_runtime
```

The first command path currently has an intermittent/shared controlled-entry
failure also reproduced by `qa/scenarios/stage4a_world_persistence.json`. The
battle runner requires the ignored `test.sav`, which is absent locally and was
already documented by Stage 0.

## Architectural boundary

The Stage 5B hook is compiled only with `STAGE5B_RUNTIME_PROOF=Y`. It adds no
roster capability. Generic QA `write_memory` addresses an exported semantic
symbol and is bounded to 1/2/4-byte writes validated by the scenario schema.
The normal ROM has neither the hook nor the test state.

Source data and successful compilation establish availability. Runtime
classification requires live semantic assertions. Missing runtime routes must
remain `NOT_EXECUTED`/partial even when sprites and tables exist.

The canonical roster inventory records only the representative proof as
`PARTIAL_EXECUTED`; it does not spread Victini's runtime evidence across the
other 1,024 base-species records.

## Remaining unknowns

- battle front/back and cry playback under the live battle runner;
- trainer NARC and wild NARC live expanded-ID resolution;
- ordinary capture-created Victini;
- icon palette in party and PC UI;
- follower map-transition persistence;
- party and PC battery-save persistence through hard reset/Continue;
- expanded Dex UI behavior beyond seen/caught storage.
