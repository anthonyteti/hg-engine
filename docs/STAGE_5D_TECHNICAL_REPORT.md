# Stage 5D Technical Report — Regional Form Runtime

## Verdict

`STAGE_5D_REGIONAL_FORM_PASSED`

`REGIONAL_FORM_RUNTIME_PROVEN`

`REGIONAL_EVOLUTION_LINEAGE_PROVEN`

`REGIONAL_FORM_STORAGE_PROVEN`

`REGIONAL_FORM_PRESENTATION_PROVEN`

Stage 5D proves the existing HG-Engine regional-form architecture with one continuous Hisuian Zorua individual. No species, form, personal, learnset, or evolution table was changed.

## Checkpoint and sequencing

Stage 5C is committed and pushed at `d5de3b109a1701949fa687893b99d9d700827544` (`Add Stage 5C expanded evolution proof`). Local `HEAD`, `origin/main`, and remote main agreed before Stage 5D began.

Stage 5C proves one ordinary expanded level-evolution line. Other generic evolution methods are now targeted regressions only when production content or a discovered gap requires them. Stage 5D addresses the distinct regional-form representation risk.

## Source contract

| Identity | Adjusted ID | Runtime base | Form |
|---|---:|---:|---:|
| `SPECIES_ZORUA_HISUIAN` | 1335 | `SPECIES_ZORUA` (620) | 1 |
| `SPECIES_ZOROARK_HISUIAN` | 1336 | `SPECIES_ZOROARK` (621) | 1 |

`PokeFormDataTbl` maps base/form to adjusted identity; `FormToSpeciesMapping` maps 1335/1336 back to 620/621. Party and box records store base species plus `MON_DATA_FORM`. Wild and trainer records pack species in the low 11 bits and form in the high 5 bits of a `u16`.

The unchanged evolution source is `EVO_LEVEL, 30, MON_WITH_FORM(SPECIES_ZOROARK, 1)` under `SPECIES_ZORUA_HISUIAN`. Runtime selected the adjusted source table and decoded target base 621/form 1.

## Runtime evidence

The deterministic individual used PID `0x050D0001` (84738049), OT ID `0x050D0A11`, form 1, and level 29. Hisuian Zorua resolved Normal/Ghost, Illusion (149), base stats 35/60/40/85/40/70, and moves Curse/Taunt/Knock Off/Spite (174/269/282/180).

One ordinary Rare Candy was used through the Bag. The retail evolution sequence produced base Zoroark 621/form 1/adjusted identity 1336 at level 30, not ordinary Zoroark, while retaining PID 84738049. It resolved Normal/Ghost, Illusion, experience 21760, HP 82/82, and stats 74/50/80/89/50. The existing four moves were retained after declining Shadow Claw through the ordinary prompt.

Before evolution, icon/follower/battle resolution selected adjusted identity 1335, icon 1342/palette 0, and follower tag 3835. After evolution it selected identity 1336, icon 1343/palette 0, follower tag 3836, and the Hisuian Zoroark battle back sprite.

The isolated ordinary wild path decoded `MON_WITH_FORM(SPECIES_ZORUA, 1)` as base 620/form 1/adjusted 1335 at level 29 and rendered the Hisuian front sprite. It is separate from the continuous individual proof.

## Persistence and Dex semantics

Three ordinary battery-save cycles passed: boxed Hisuian Zorua; party Hisuian Zoroark; and boxed Hisuian Zoroark. Each retained base species, form 1, adjusted identity, PID, level, experience, and moves as applicable. No savestate was used. Follower-map-object teardown is asynchronous, so the deterministic plan waits 600 frames after final deposit before interacting with the ordinary save NPC.

The expanded Dex remains species-oriented: evolution marked base Zoroark seen/caught 1/1, while adjusted identity 1336 remained 0/0 in the inspected expanded bit ranges. Stage 5D records this behavior and does not redesign form-Dex UI or add missing descriptions.

## QA, determinism, and isolation

The continuous scenario passed 154/154 assertions in 243 steps; plan SHA-256 `557b149ef790686c6f7c28e50e2ea3fced25397cdcc8c776892812761251e0db`. The isolated wild-form scenario passed 14/14 assertions in 22 steps; plan SHA-256 `0c2ce3cfbf6ac31604a4cb69613c529b4becf47710d3902415a1a1c6274d52c8`.

Representative ignored screenshot hashes:

- evolution: `881036921af3a607924ecfdf12dea9b9d942863b31b3e731c58aeb4407157209`;
- evolved icon: `41b68de2df50f89dc6eac00c141ec2ff13600492f4db0da460583084cf6c8ed8`;
- evolved follower after transition: `0b395fedd17c499376c33a5f420886651a733064a94d55b9c7a114f165b68332`;
- evolved battle back: `ad9d535d22fc8752c0318bc8dc0cbc68e6b2e89079c01cd367c37596ad8b1b31`;
- wild Hisuian front: `3842d36a370126171e7485f1103dad7bd91c22cd1380a02181d287c6a616e1ba`.

The complete scenarios were rerun from the same proof ROM and reproduced the same plan hashes and assertion totals. The inventory generator emitted identical bytes twice with SHA-256 `1831ebbac2de52deda25706f06286be93dea49042419374cce07e4803da62faf`.

All proof content is gated by `STAGE5D_REGIONAL_FORM_PROOF=Y`. A clean ordinary `make -j2` produced ROM SHA-256 `2175928b5dc73640739ec625c17e7f300937f2a89941a8ed9077840957ca1013`; its linked object contained no Stage 5D symbols. Thus the normal build contains no seeded Hisuian Zorua, proof encounter, Rare Candy grant, or Stage 5D observations. The independent `stage4a_basic_world` smoke passed 9/9 assertions, and project preflight passed every command, Python, system, ROM, hygiene, and Docker-context check.

The repository-wide Python suite passed all 362 tests with three expected skips. Focused Stage 5A/5B/5B-R/5B-C/5C/5D regression tests are included in that result.

Remaining limits include unexecuted regional identities, trainer form-bit execution, form-specific Dex UI, cry authenticity, and expanded Dex text. Mega Evolution remains a separate architecture and is the recommended next representative proof.
