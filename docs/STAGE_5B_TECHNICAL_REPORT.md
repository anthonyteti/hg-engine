# Stage 5B Technical Report: Victini expanded-species runtime proof

## Current Stage 5B-R verdict

```text
STAGE_5B_EXPANDED_SPECIES_RUNTIME_PARTIAL
EXPANDED_BASE_SPECIES_RUNTIME_PARTIAL
EXPANDED_FOLLOWER_RUNTIME_PARTIAL
EXPANDED_SPECIES_STORAGE_PROVEN
RUNTIME_HARNESS_RECOVERED
```

Stage 5B-R recovered the generic execution prerequisites that blocked the
original Stage 5B run. Victini now has live two-sided battle presentation and
ordinary party/box battery-save evidence in addition to the earlier party,
personal-data, Dex API, follower, and PC evidence. The stage remains partial:
ordinary wild encounter/capture, trainer-NARC loading, party/PC icon UI, cry
resolver instrumentation, and a native follower map transition were not
completed. Those capabilities are not inferred from source or screenshots.

## Checkpoint and historical partial

The original Stage 5B partial implementation is committed and pushed at
`d76662420e195294840d8bf06ab4981b146a70df` (`Add Stage 5B Victini runtime
proof`). Local `HEAD`, `origin/main`, and remote main agreed before recovery.

That checkpoint correctly reported two generic blockers: the QA path did not
reach controlled entry and the battle runner lacked ignored `test.sav`. Its
positive evidence remains valid. Stage 5B-R supplements rather than rewrites
that history.

## Generic harness recovery

The controlled-entry root cause was stale ROM reuse. `qa run` loaded
`test.nds` without building the scenario's declared Make target. The failure
therefore reproduced in both `stage5b_victini_runtime` and the unchanged
`stage4a_world_persistence` control. The generic runner now has an explicit
`--build` mode, invokes the declared target, records the build result, and
fails with stable `qa_build_failed` evidence. It uses semantic readiness after
the build; no scenario contains revision-specific addresses or arbitrary
timing-only entry bypasses.

Recovered controls:

- `stage4a_basic_world`: 9/9 steps passed; plan SHA-256
  `541202f17b5b40443ad83783ef925ff317859889eefc20edebcab346491f1f26`.
- unchanged `stage4a_world_persistence`: 19/19 steps passed, including normal
  save, hard reset, title/Continue, and persisted map 541 position 36,15; plan
  SHA-256 `90faeb8785851f5c13b7c6a075896c3489140951e6aa0ea0e49df49e5b731bbd`.

## Reproducible battle-save provisioning

The repository battle runner requires an ignored 512 KiB raw battery save.
`make battle-test-save` now builds a proof-only ROM, starts a normal new game
headlessly, ensures an ordinary nonempty player party, calls the game's
`SaveGameNormal`, exports the DeSmuME battery container, validates its format,
and writes ignored `test.sav`. It never downloads or commits a save or retail
ROM data.

The recovered local fixture was 524,288 bytes with SHA-256
`0ae34b89b0a00acd19acd71648ed27c6e59532a88e49e3ccbfc6bb23a30f3ced`.
The byte hash is evidence for this run, not a cross-run determinism promise;
the canonical contract is semantic: successful normal save status, initialized
field state, nonempty party, and correct raw import size. A missing or malformed
fixture now reports the exact `make battle-test-save` command.

The known-good Color Change battle test passed after provisioning. The
existing two-sided Victini battle fixture then passed: Victini resolved on
both sides, its front and back sprites rendered, and Incinerate and Focus
Energy executed. This battle fixture proves expanded-species battle rendering
through the battle-test engine; it does not substitute for compiled trainer or
wild encounter tables.

## Victini source contract

| Field | Expected/live value |
|---|---:|
| Engine species ID | 544 |
| Level | 20 |
| Form | 0 |
| Base stats | 100 / 100 / 100 / 100 / 100 / 100 |
| Types | Psychic (14) / Fire (10) |
| Ability | Victory Star (162) |
| Moves | Confusion 93; Focus Energy 116; Work Up 529; Incinerate 513 |
| Seeded proof HP | 37 / 76 |
| Proof other stats | 51 each |
| Evolution | not applicable |
| Follower sprite tag | 3044 |

The live party state matched identity, level, form, moves, HP, all calculated
stats, ability, and types. Victini uses ordinary `PokeParaSet`, generated
moveset, stat recalculation, party, PC-storage, and save representations.

## Field and storage rerun

The Stage 5B-only world fixture adds a proof NPC that executes the ordinary
`save_game_normal` script command. It does not add a direct save wrapper or
Victini-specific serialization.

The bounded rerun passed 73/73 assertions in 99 planned steps (plan SHA-256
`79145933af6146a16a83fd4e382d602ff4051b84316d67d59d3b90f219e3887d`).
It proved:

- the original exact Victini party/data assertions;
- direct seen/caught Dex API behavior retained from the initial proof;
- party save, hard reset, title/Continue, and restoration of species 544,
  level 20, form 0, moves 93/116/529/513, and current HP 37;
- ordinary PC deposit and intact box species/form/level/moves;
- box save, hard reset, Continue, and persistence in the same storage state;
- ordinary withdrawal to party; current HP becomes the correctly reconstructed
  full 76 because boxed data does not store party-only current HP;
- follower resolver/species 544 and sprite tag 3044 after withdrawal;
- 600 further stable frames.

The ignored captures were named `victini_party_save`,
`victini_party_persisted`, `victini_box_save`,
`victini_pc_box_persisted`, `victini_follower`, and
`victini_after_continue`. They supplement semantic assertions; generated
captures are deliberately removed by clean-root builds and are not tracked.
The final proof ROM SHA-256 was
`4978bc29ed59aaea2a850a5434f5a9c7cb5a38c5e1028d41f34355944f93e97b`.
Screenshot file hashes were:

- party save: `e4a242efb3a1e9139d8e5fbd28186ebcab9aecf7ff02c79dfea493ef5438eb73`;
- box save: `7cc5d0801059322907bad600ad2c601a400110b1e8ebf8e92d1b82ba589185fd`;
- persisted/follower/after-Continue field captures:
  `6aef6aa0f9fd6cbc8aabe229351e131fc1920f7fe6bdf2159f044f9208b9d373`.

Visual inspection confirms the Victini follower graphic and palette are
present beside the player. These field captures do not claim party/PC icon UI
evidence.

## Remaining matrix gaps

The rerun did not complete these required live paths:

- ordinary wild encounter and guaranteed ordinary capture;
- seen/caught state specifically caused by encounter/capture rather than the
  already-proven direct APIs;
- compiled trainer-table runtime loading (the two-sided test battle did pass);
- party and PC UI icon rendering;
- cry resolver index 778 invocation/playback routing;
- a native map transition with Victini continuing as follower.

The transition attempt exposed a bounded field-fixture problem: after
withdrawal and follower re-enable, Victini rendered with the correct resolver
identity, but movement toward available exits remained blocked and a prior
neighboring-map attempt locked after transition. No teleport, raw-memory warp,
or Victini-specific bypass was accepted. Historical one-tile follower
movement from the first Stage 5B run remains evidence, but transition is not
proven.

Evolution is `EVOLUTION_NOT_APPLICABLE_TO_REPRESENTATIVE` because Victini does
not evolve. No Mega proof was attempted.

## Isolation, determinism, and tests

The recovery adds only proof-gated hooks. `STAGE5B_RUNTIME_PROOF=Y` and
`BATTLE_SAVE_PROVISION=Y` are absent from normal builds. The Stage 5B world,
trainer/battle content, and semantic state are opt-in. The ordinary Stage 4A
fixture preserves its existing save/warp bytes.

The deterministic QA plans, fixture generation, and battle resources match
across repeat generation. Emulator reports contain runtime frame timing and
are not claimed byte-identical. The focused recovery/world/roster suite passes
41 tests; the complete `test_pokeagent_*.py` suite passes 313 tests with two
documented skips. Coverage includes build-failure behavior, save provisioning
boundaries, actionable missing-save errors, world-fixture isolation, and the
Stage 5B semantic plan. A clean normal ROM build and preflight also pass.
DeepSeek was not used; cost $0.

## Inventory interpretation and next scope

`docs/data/hgengine_roster_inventory.json` keeps Victini at
`PARTIAL_EXECUTED`. It now records battle presentation and ordinary party/box
persistence as executed, while naming the remaining live gaps. No other
species classification changes.

The generic harness is recovered and expanded-species storage is
representatively proven. The next bounded Stage 5 task should address the
remaining shared runtime evidence—preferably ordinary wild/capture plus icon
and cry observability in a reusable test route—without changing Victini or
promoting all expanded species.
