# Stage 5E Technical Report — Mega Evolution Runtime

## Verdict

`STAGE_5E_MEGA_RUNTIME_PASSED`

`MEGA_TRANSFORMATION_RUNTIME_PROVEN`

`MEGA_BATTLE_DATA_PROVEN`

`MEGA_BATTLE_PRESENTATION_PROVEN`

`MEGA_REVERSION_PROVEN`

`MEGA_USAGE_RULE_PROVEN`

Stage 5E proves the existing player-side Mega architecture with ordinary
Altaria and Mega Altaria. No Mega mapping, species data, item data, sprite,
form rule, or production battle behavior was added or corrected.

## Checkpoint and proof boundary

Stage 5D was committed and pushed as
`0c366d4d8da77e25f93ba3cbdb4131343aa9f594` (`Add Stage 5D regional form
runtime proof`). Local `HEAD`, `origin/main`, and remote main agreed before
Stage 5E began.

All Stage 5E fixture and observation behavior is compiled only with
`STAGE5E_MEGA_PROOF=Y`. The fixture seeds one ordinary Altaria, enables the
existing Mega feature flag, grants the existing Altarianite, installs one
ordinary encounter table, and exports semantic observations. It does not seed
Mega Altaria or call the transformation routine. The player selects Mega using
the retail touchscreen control and selects a normal move through the retail
battle menu.

## Current-fork source contract

| Property | Ordinary Altaria | Mega Altaria |
|---|---:|---:|
| species/adjusted identity | 334 | 1108 |
| battle form | 0 | 1 |
| types | Dragon/Flying (16/2) | Dragon/Fairy (16/9) |
| ability | Natural Cure (30) | Pixilate (182) |
| base stats | 75/70/90/70/105/80 | 75/110/110/110/105/80 |

`sMegaTable` maps species 334 plus `ITEM_ALTARIANITE` (755) to form 1.
`PokeFormDataTbl[SPECIES_ALTARIA]` maps form 1 to
`NEEDS_REVERSION | SPECIES_MEGA_ALTARIA`, and `FormToSpeciesMapping` maps
adjusted identity 1108 back to base species 334. The runtime feature gate is
`FLAG_MEGA_EVOLUTION_ENABLED` (2518).

`CheckCanDrawMegaButton` checks the feature flag, the persistent party form,
Transform state, held item/move mapping, and the per-battle Mega state. The
native fight-menu touch path sets `playerWantMega`. `ServerBeforeAct` validates
the request, marks `SideMega`/`needMega`, and `MegaEvolutionOrUltraBurst`
changes only the battle form before calling `BattleFormChange`. The latter
reloads personal data, recalculates battle stats, and replaces ability/types.

At battle end, `BattleEndRevertFormChange` clears `SideMega`,
`playerWantMega`, `PlayerMegaed`, `CanMega`, and the UI state, then calls
`RevertFormChange` for every persistent party Pokémon. Mega identity is thus a
temporary battle form, unlike Stage 5D's saved regional form.

## Deterministic representative

The persistent Pokémon is ordinary level-50 Altaria, form 0, PID `0x050E0010`
(84803600), OT ID `0x050E0A11`, Hardy nature, all IVs 31, holding Altarianite.
Its moves are Cotton Guard, Take Down, Moonblast, and Perish Song
(541/36/588/195). The ordinary encounter engine supplies a level-5 Magikarp.

The calculated neutral-nature battle values matched source-derived values:

| State | HP | Atk | Def | Spe | SpA | SpD |
|---|---:|---:|---:|---:|---:|---:|
| base | 150 | 90 | 110 | 100 | 90 | 125 |
| Mega | 150 | 130 | 130 | 100 | 130 | 125 |

HP remained 150/150 across transformation because Mega Altaria has the same
base HP. The other five calculated battle stats changed exactly as implied by
the Mega personal table.

## Live transformation and battle evidence

Before activation the live battler was species 334/form 0, held item 755, and
the native eligibility predicate returned true. The fight menu displayed the
Mega control. A real touchscreen press selected it; the selected control
changed visual state, and the subsequent ordinary Cotton Guard selection
queued and accepted the Mega request.

The live transformed battler was species 334/form 1/adjusted identity 1108.
It resolved types 16/9, ability 182, the six calculated Mega stats above, and
the Mega Altaria player-back graphic. Cotton Guard completed while form 1 was
active; the proof observes the move-end boundary and independently validates
Cotton Guard's live Defense-stage effect when native command selection
returns, recording move 541, battle form 1, and identity 1108. The battler
remained Mega when command selection returned.

The per-battle `PlayerMegaed` and `SideMega` values were both set, which is the
current fork's one-Mega-per-side restriction state and disables another native
activation during that battle. After Continue, the first eligibility check in
a new battle returned true again, proving that the usage state reset at the
battle/save boundary.

## Reversion, presentation, and persistence

The wild battle ended through the ordinary Run command after executing the
Mega move. Immediately before battle-end reversion the persistent battle-party
copy was species 334/form 1/identity 1108. Immediately afterward it was
species 334/form 0/identity 334. PID 84803600 and held item 755 were unchanged,
and all Mega-use flags were clear.

The ordinary party UI then rendered Altaria, not Mega Altaria. The field
follower resolved ordinary Altaria and continued rendering/moving; no Mega
follower mapping was required or synthesized.

An ordinary save NPC invoked the retail battery-save path. After hard reset,
title, and Continue, the party record remained species 334/form 0 with the
same PID, level, moves, HP/state, and Altarianite. No adjusted identity 1108 or
Mega-active flag leaked into persistent storage. The second battle exposed the
native Mega action again.

## QA, determinism, and visual evidence

The canonical scenario passed 85/85 assertions in 142 steps. Its deterministic
plan SHA-256 is
`303f0a5db9beb511e4de980919413b625055a3df24c4b8086748d269c9fe4ade`.
The proof ROM SHA-256 is
`c368147d77a735c59abe9e48c8f504ec6ebac167b1b2cc0186870658eec204a2`.

Representative ignored screenshot hashes:

- pre-battle ordinary follower: `a642099f25160a9b35ee2a1302f27939fa39734682df9241325d9cb8a7815214`;
- Mega fight-menu control: `e2f0243667450022aefde986d50d362fbed8ce1a617f3b255e1aa66488e63c20`;
- selected Mega request: `75c039ff2f9a9cafa2a30002a8fb0508ca8d276f24389b9a29bf824aeb29a08c`;
- active Mega Altaria: `5444e957432ddfa49a508118d25aacb5ba2cb89614b503d46759bc04c0a2f5fe`;
- post-battle ordinary party Altaria: `879dcf7aab501d2a17209463b39e128a1f47ee12eb30dac5e9986b6f47987895`;
- post-battle ordinary follower: `0038d990b3956024bac2ffc65854b02400557b34e4f16ba5a44392cb29c7d190`.

Repeated executions from the same proof ROM produce the same plan, assertion
count, semantic values, final map, and final position. Battle screenshots may
capture different frames of an animated sprite and are therefore treated as
visual evidence rather than byte-deterministic state.

## Inventory, regressions, and remaining limits

The deterministic roster report now records
`expanded_mega_runtime.status = REPRESENTATIVE_PROVEN` and annotates only
`SPECIES_MEGA_ALTARIA` as `representative_mega_status = COMPLETE_EXECUTED`.
It does not classify Mega forms as normal persistent/follower-complete species
or promote the other 96 Mega identities.

The full Python suite passed 368 tests with three explicitly gated integration
skips. The known-good Color Change battle integration passed 1/1, and the
unchanged Stage 4A basic-world control passed 9/9 assertions with plan SHA-256
`541202f17b5b40443ad83783ef925ff317859889eefc20edebcab346491f1f26`.
The normal build completed with SHA-256
`2175928b5dc73640739ec625c17e7f300937f2a89941a8ed9077840957ca1013` and
contained no `Stage5E` symbols. Preflight passed all command, Python, system,
ROM, Git-hygiene, and Docker-context checks. No DeepSeek review was used; cost
was $0.

This representative does not prove every Mega mapping, opponent/AI Mega
activation, move-triggered Mega forms, multi/double battle ownership,
Mega-specific animation fidelity, or cry authenticity. Expanded Pokédex text,
individual incomplete identities/forms, and other content gaps also remain.

The recommended Stage 5F scope is evidence-backed roster/content gap closure
planning and implementation. It should separate missing runtime functionality,
missing data/content, incomplete identities/forms, cosmetic/authenticity gaps,
and cases already covered architecturally but not individually executed.
