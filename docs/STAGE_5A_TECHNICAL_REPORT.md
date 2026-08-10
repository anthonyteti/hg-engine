# Stage 5A Technical Report: HG-Engine roster capability audit

## Verdict

```text
STAGE_5A_ROSTER_AUDIT_PARTIAL
HGENGINE_ROSTER_PARTIALLY_EXPANDED
EXPANDED_OVERWORLD_COVERAGE_BROAD
```

The repository inventory is deterministic and evidence-backed, but the
required expanded-species runtime matrix was not completed. Static source and
binary-width evidence must not be promoted into battle/field/save visual proof.

## Stage 4 boundary

Stage 4U was committed and pushed as
`123b7e6e73d48f193d0c9d75b422885c8be1ccd8` (`Add Stage 4U SPAR3D access
finding`). Local `HEAD`, `origin/main`, and the remote main ref agreed before
Stage 5A began. Architecture, roadmap, and decision records now state that
controlled static asset/compiler infrastructure is proven, while real
image-to-3D generation is unproven and deferred to the mandatory Stage 6 Art
Factory generated-landmark gate. Stage 4H/S/T/U findings remain unchanged.

## Revision and method

- Local/origin revision: `123b7e6e73d48f193d0c9d75b422885c8be1ccd8`.
- BluRosie upstream revision: `c6d63fd8a34f63431214284dc08c3b7942ab0593`.
- Relationship: local is 30 commits ahead, zero behind; no roster-related path
  differs from upstream.
- Canonical output: `docs/data/hgengine_roster_inventory.json`.
- Generator: `tools/pokeagent/roster_inventory.py`.
- Tests: `tests/test_pokeagent_stage5a_roster_inventory.py`.

The generator parses declarations, direct/inherited data, asset payload
presence, generated archive rules, runtime follower lookup, Dex membership,
cry routing, and numeric storage definitions. It emits no timestamp and two
runs are byte-identical.

## Roster summary

| Generation | Engine species | Complete | Partial | Missing | Runtime OW |
|---:|---:|---:|---:|---:|---:|
| 1 | 151 | 151 | 0 | 0 | 151 |
| 2 | 100 | 100 | 0 | 0 | 100 |
| 3 | 135 | 135 | 0 | 0 | 135 |
| 4 | 107 | 107 | 0 | 0 | 107 |
| 5 | 156 | 0 | 156 | 0 | 156 |
| 6 | 72 | 0 | 72 | 0 | 72 |
| 7 | 88 | 0 | 88 | 0 | 88 |
| 8 | 96 | 0 | 96 | 0 | 96 |
| 9 | 120 | 0 | 120 | 0 | 120 |

These rows cover the 1,025 implemented base species. The canonical identity
space additionally contains 400 forms and 50 reserved HGSS slots. Across all
1,475 identities: 560 are `COMPLETE`, 859 `PARTIAL`, two `DATA_ONLY`, two
`ASSET_ONLY`, 50 `NOT_IMPLEMENTED`, and two `UNKNOWN`.

Battle front/back and icon source coverage is 1,475/1,475. Cry resolution is
1,421/1,475. Overworld source files exist for 1,475 identities, while 1,236
have both runtime follower mapping and properties. Every implemented base
species, including Gen 5 through Gen 9, is runtime-mapped.

## Storage and usability

- Party and boxed Pokémon store species in `u16`; alternate form is five bits.
- The expanded save keeps the box representation and enables
  `ALLOW_SAVE_CHANGES`.
- Wild source records use `u16`; live `WildEncounterWork` uses 11 species bits
  plus five form bits. Base maximum 1,075 fits 11 bits.
- Trainer source uses `u16`, and the generator emits `WriteLe16`.
- Highest base identity: `SPECIES_PECHARUNT` (1,075).
- Highest canonical form identity: `SPECIES_MEGA_BAXCALIBUR` (1,475).

The source uses no post-Gen-4 identity in current trainer or wild tables. Width
support is confirmed; existing-content runtime use is not.

## Pokédex and forms

The expanded National sort covers all 1,025 base species. Dex allocation uses
`POKEDEX_CANONICAL_SPECIES_COUNT` and the enabled expanded `0x700` save block.
Names and sprites resolve, and seen/caught bits have expanded storage. No
tracked post-Gen-4 category/description source was found, so expanded Dex
support is partial. Forms resolve to base Dex identities. Regional and Mega
detail is recorded in the knowledge note and machine report. Mega source has
91 rows across 84 base species, but declaration, data, transition mapping,
assets, and follower coverage are reported independently.

## Victini proof result

Victini was selected because it is the first post-Gen-4 identity and resolves
all audited source capabilities. The inventory verifies ID 544, personal data,
learnsets, empty evolution table semantics, front/back/icon graphics, cry,
Dex, follower mapping, and storage/compiler widths.

No deterministic runtime route currently proves all requested battle front and
back views, icon, party, PC, save/reset/Continue, trainer, wild, and field
follower behavior without adding game content. Stage 5A did not add content or
fake assets. Battle, follower, trainer, wild, party/box, save, and Mega runtime
results are therefore explicitly `NOT_EXECUTED`, and the main verdict is
partial.

## Tests and recommendation

The focused suite validates schema/statuses, exact identity ranges, generation
counts, duplicate identities, base OW mappings, source-versus-runtime OW
distinction, Victini evidence, storage widths, and byte determinism. Full
project results: 322 tests passed with three expected opt-in integration skips;
preflight passed 58/58; `make -j2` rebuilt `test.nds`; and a 1,023-frame
headless smoke produced a meaningful 256x384 frame while the emulator remained
running. That generic boot does not substitute for the unexecuted Victini
runtime matrix.

Stage 5B should be one bounded runtime-proof fixture, not bulk roster work:
place Victini through existing trainer, wild, party/box/save, battle sprite,
icon, and follower systems; add no missing species capability. If any path
fails, downgrade the affected inventory capability before considering one
later-species normalization or a Mega proof.
