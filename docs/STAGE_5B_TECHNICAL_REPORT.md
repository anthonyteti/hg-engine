# Stage 5B Technical Report: Victini expanded-species runtime proof

## Final Stage 5B-C verdict

```text
STAGE_5B_EXPANDED_SPECIES_RUNTIME_PASSED
EXPANDED_BASE_SPECIES_RUNTIME_PROVEN
EXPANDED_FOLLOWER_RUNTIME_PROVEN
EXPANDED_SPECIES_STORAGE_PROVEN
EXPANDED_TRAINER_WILD_RUNTIME_PROVEN
EXPANDED_ICON_UI_PROVEN
EXPANDED_CRY_ROUTING_PROVEN
```

Stage 5B-C closes the remaining shared runtime matrix without changing Victini
or adding roster content. Ordinary trainer-NARC and wild-table paths, native
capture and Dex causality, party and retail PC icon UIs, expanded cry routing,
and a native follower map transition all executed. The earlier Stage 5B and
Stage 5B-R partial results remain historical evidence below.

## Stage 5B-C shared-runtime closure

The opt-in schema-7 proof world keeps project headers 540/541. Map A contains
trainer 737, an ordinary 100% encounter area backed by bank 142, and an access
warp to the retail Cherrygrove Pokémon Center. Map B provides a clear native
east/west transition route. The fixture preserves the retail common-script
bank; AUTO battle builds also install this fixture explicitly, so clean battle
tests no longer depend on stale map/script artifacts.

The six declarative closure scenarios passed:

| Scenario | Assertions | Plan SHA-256 |
|---|---:|---|
| trainer NARC | 17/17 | `03df22d2f6ad0eea251025faf8392c8c4ce748166d286555ff9a4892c38b520f` |
| wild seen causality | 9/9 | `ac2c403d2a74ab30c3925e948bcf021d94fc207bee6d2f809c3756aaa66340bc` |
| wild capture/cry | 33/33 | `5cc59d6617727e8f485de1a989b4258e2b9ef85fac11518316463a2df17c8160` |
| party icon UI | 9/9 | `eab2e7c61ebf34ab0284eae61b65e0a03d9d32859ce65a598cacfe0783d26b69` |
| PC icon UI | 14/14 | `8fb736cfb61992795cd79d4af08889bf0e723b1adeabd0add9e81a0cdaa70ac4` |
| follower transition | 15/15 | `c665a2d8af67b6ed9586cf52aea719a178ae0c9e5fdae6b4faebd43e62d2a83f` |

Trainer slot 737 is replaced only under `STAGE5BC_RUNTIME_PROOF`. Its ordinary
trainer source and serialized NARC member contain species 544, level 5, form
0, and moves 93/116/529/513. Field interaction loaded the same values, rendered
Victini's front sprite, executed battle turns, and returned safely to the
field. The normal build retains the original Silver trainer 737.

Encounter bank 142 is proof-only and uses ordinary encounter serialization:
all land slots are base-form Victini at level 20 with walk rate 100. A normal
grass step constructed the wild battle. Before encounter, seen/caught were
0/0; cry-time observation after encounter was 1/0; after ordinary capture they
were 1/1. The capture path produced species 544, level 20, form 0, moves
93/116/529/513, ability 162, and a nonzero ordinary PID in party storage. No
Dex setter or Pokémon-construction shortcut participated in this proof.

Live cry instrumentation observed species 544 resolving to expanded
pseudo-bank index 778, followed by the ordinary expanded-bank load/playback
boundary. It proves routing and playback invocation, not audio authenticity.

The actual party UI and retail PC storage UI both selected species 544/form 0
icon resources and palettes. Semantic resource observations matched the party
or box slot, and screenshots showed Victini without fallback or corruption.
The PC route used ordinary deposit, a temporary companion because retail HGSS
cannot deposit the last party member, and ordinary box UI rendering.

Victini began on map 540 with follower tag 3044, crossed the native fixture
connection into map 541, retained species/tag/graphic/palette, and followed for
another tile after arrival. No emulator teleport, raw coordinate write, or
test-only respawn occurred.

The previously proven storage scenario reran unchanged: 73/73 assertions in
99 steps, plan SHA-256
`79145933af6146a16a83fd4e382d602ff4051b84316d67d59d3b90f219e3887d`.
Party and box battery saves, hard reset, Continue, deposit/withdraw, and 600
stable frames remain green.

The battle harness was also revalidated from a clean build. `make
battle-test-save` now extracts its ignored 512 KiB fixture from the ordinary
Stage 5B save/reset/Continue QA path. AUTO builds explicitly install the
Stage 5B-C world, preserve common scripts, wait for a semantic host range, and
retain the original field settling delay. Both the known-good Color Change
test and the two-sided Victini battle test passed. The latter screenshot hash
was `56f7b3ca42779010c7b454f5f25f8f5579e8316d30f31f35ef342ca025aa114c`.

Representative screenshots (ignored artifacts) had these SHA-256 values:

- trainer front: `ee7154b62f9ad1274e650ef2ae31cc98556237b87f24261eaeffe7ff4d6153cc`;
- wild front: `c905bce9405332420db4e07986b9817f28ec0153e20ce8fbfb96eec53f91d622`;
- capture complete: `a3ec9bfdfcbc18e7a56ddc97694eb92d81bc5e8079efa943c5bc5f275798314e`;
- party icon: `5de345e2a25455c8cb952b35dfd7acee0e6c0fb74fedccbf88eff92f135a444f`;
- PC icon: `d5641e75a479f0ba71a2c3451552019838d0a42caad5d448d23be8da10544084`;
- follower before transition: `bbcadf18d4f3cc21c4bac727fe824546754222a7f7f83e518b3899008fe57980`;
- follower after transition: `b1574bb95d61185a541dae4ab17e3900ab7d920e1c2a58a5b0c840982f7fc23f`;
- follower after movement: `0d67529d4cb32ca9d505cc8b75804b56e06c5f931dfdb2424ad5e220f8acb4c4`.

Visual evidence supplements semantic assertions. It confirms correct front,
icon, and follower presentation; it is not the primary identity proof.

## Checkpoint and historical partial

Stage 5B-R is committed and pushed at
`bee4126deb92a435124751614843ad5cf673990a` (`Recover Stage 5B runtime
harness`). Local `HEAD`, `origin/main`, and remote main agreed before Stage
5B-C began.

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
The original Stage 5B-R hook called `SaveGameNormal` directly; Stage 5B-C
discovered that clean cross-build reload also depends on a neutral completed
field script and matching proof-map resources. `make battle-test-save` now
runs the proven ordinary Stage 5B save/reset/Continue QA scenario, extracts its
DeSmuME battery container, validates its format, and writes ignored `test.sav`.
It never downloads or commits a save or retail ROM data.

The historical Stage 5B-R fixture was 524,288 bytes with SHA-256
`0ae34b89b0a00acd19acd71648ed27c6e59532a88e49e3ccbfc6bb23a30f3ced`;
the final Stage 5B-C QA-derived fixture was 524,288 bytes with SHA-256
`750ed77d8a5c708833105eed2b78fd60529f923872ccef67181d08a32e8e5937`.
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

## Historical Stage 5B-R matrix gaps (closed by Stage 5B-C)

Stage 5B-R did not complete these required live paths:

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
movement from the first Stage 5B run remains evidence. Stage 5B-C subsequently
closed every item above through the ordinary paths described in its closure
section.

Evolution is `EVOLUTION_NOT_APPLICABLE_TO_REPRESENTATIVE` because Victini does
not evolve. No Mega proof was attempted.

## Isolation, determinism, and tests

The recovery and closure add only proof-gated hooks.
`STAGE5B_RUNTIME_PROOF=Y`, `STAGE5BC_RUNTIME_PROOF=Y`, AUTO battle
instrumentation, trainer/wild substitutions, and semantic state are absent
from normal builds. The ordinary Stage 4A fixture preserves its existing
save/warp bytes.

The deterministic QA plans, fixture generation, and battle resources match
across repeat generation. Emulator reports contain runtime frame timing and
are not claimed byte-identical. The full suite passes 348 tests with three
documented skips, and preflight passes all 58 checks. Coverage includes build-failure
behavior, ordinary-save provisioning, clean battle handshakes, fixture
isolation, trainer/wild serialization, capture-created storage, icon
observation, cry routing, and follower-transition plans. A clean normal ROM
build passes with proof symbols absent. Two clean world generations report zero
mismatches, and the canonical inventory regenerates byte-identically at
SHA-256 `c59f3d95c282f9f9c71840abb1a767d161f4a08d653ba949ca5ff963290dc348`.
DeepSeek was not used; cost $0.

## Inventory interpretation and next scope

`docs/data/hgengine_roster_inventory.json` records Victini representative
runtime status `COMPLETE_EXECUTED` and shared architecture
`REPRESENTATIVE_PROVEN`. Victini's species record remains top-level `PARTIAL`
because expanded Pokédex category/description content is still absent. No
other species classification changes.

The shared base-species runtime architecture, follower transition, and storage
are representatively proven. The next bounded Stage 5 task should prove one
expanded evolution line through ordinary evolution and persistence. It must
not infer form, Mega, cry-authenticity, or expanded Dex-text completeness from
Victini's result.
