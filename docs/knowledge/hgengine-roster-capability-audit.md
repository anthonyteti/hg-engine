# HG-Engine roster capability audit

## Finding

At revision `123b7e6e73d48f193d0c9d75b422885c8be1ccd8`, the local HG-Engine
tree represents 1,475 canonical identities: 1,025 implemented base species,
400 form identities, and 50 reserved HGSS slots (`SPECIES_EGG`,
`SPECIES_BAD_EGG`, and `SPECIES_496` through `SPECIES_543`). All nine
generations of base species through `SPECIES_PECHARUNT` have static data,
battle graphics, icon, cry payload, Pokédex number/name/sprite/seen-caught
membership, and runtime follower mapping evidence. Full expanded Pokédex
category/description evidence is absent, so Gen 5-9 entries are partial rather
than complete. Form support is also less uniform.

The deterministic source inventory is
`docs/data/hgengine_roster_inventory.json`; regenerate it with:

```bash
make stage5a-roster-audit
```

## Classification

The generator assigns exactly one status:

- `COMPLETE`: core species/evolution/learnset data, battle graphics, cry,
  follower mapping/properties, Pokédex resolution, and party/box/save,
  trainer, and wild storage paths resolve.
- `PARTIAL`: core data and battle graphics resolve, but at least one runtime
  capability does not.
- `DATA_ONLY`: core data resolves but the complete battle asset set does not.
- `ASSET_ONLY`: the complete battle asset set resolves but core data does not.
- `NOT_IMPLEMENTED`: a reserved HGSS identity slot, not a Pokémon.
- `UNKNOWN`: neither complete core data nor complete battle assets can be
  established.

Forms inherit learnsets, cry identity, and Pokédex identity only when
`data/FormToSpeciesMapping.c` explicitly maps them. Overworld support requires
both files in `data/graphics/sprites/` and a `MON_FOLLOWER_ENTRY` in
`src/field/overworld_table.c`; filenames alone never count.

## Evidence

- Identity and generation boundaries: `include/constants/species.h`.
- Personal data: `data/Species.c`.
- Evolutions: `data/Evolutions.c`.
- Level, machine, tutor, and egg learnsets:
  `data/learnsets/learnsets.json`, `scripts/build_learnsets.py`, and
  `data/FormToSpeciesMapping.c`.
- Battle/icon/overworld sources and generated archive indices:
  `data/graphics/sprites/`, `data/graphics/pokegra.mk`, and
  `scripts/reformat_sprite_data.py`.
- Runtime follower lookup: `src/field/overworld_table.c` and
  `data/FollowerProperties.c`.
- Cries: `src/pokemon.c`, `armips/asm/cries.s`, and `sound/cries/`.
- Pokédex: `data/PokedexSort.c`, `include/pokedex_archive_data.h`, and
  `armips/asm/pokedex.s`.
- Party/box/save representation: `PokemonDataBlockA.species` (`u16`) and
  `PokemonDataBlockB.alternateForm` (5 bits) in `include/pokemon.h`.
- Wild runtime representation: 11-bit species plus 5-bit form in
  `WildEncounterWork`; source encounter records use `u16` in
  `include/encounter.h`.
- Trainer records: `TrainerPokemonData.species` is `u16` and
  `trainer_data_gen.c` serializes it with `WriteLe16`.

The National Dex sort contains all 1,025 implemented base species. The
expanded Dex uses `POKEDEX_CANONICAL_SPECIES_COUNT` and a `0x700` save block
under enabled `ALLOW_SAVE_CHANGES`. Forms use their base Dex identity rather
than independent National Dex entries.

## Counts

| Capability | Count / 1,475 identities |
|---|---:|
| Battle front | 1,475 |
| Battle back | 1,475 |
| Icon | 1,475 |
| Cry resolution | 1,421 |
| Overworld source graphic | 1,475 |
| Runtime follower mapping | 1,236 |

All 1,025 implemented base species are among the 1,236 runtime follower
mappings. Gen 5/6/7/8/9 base coverage is respectively 156/72/88/96/120.
The 239 source-only overworld identities are forms/reserved slots, not missing
later-generation base species.

Status totals are:

```text
COMPLETE          560
PARTIAL           859
DATA_ONLY           2
ASSET_ONLY           2
NOT_IMPLEMENTED     50
UNKNOWN              2
```

The 532 Gen 5-9 base species are `PARTIAL` because no tracked expanded Dex
category/description source was found. The two `UNKNOWN` entries are Alcremie filler identities without an explicit
form-to-base mapping. The two `DATA_ONLY` entries are alternate Gigantamax
forms lacking usable graphics/cry resolution. The two `ASSET_ONLY` entries are
the final PLZA Mega forms missing evolution records at this revision.

## Forms and Mega Evolution

The canonical form universe contains 400 identities. Source-name counts include
20 Alolan, 20 Galarian, 16 Hisuian, and one explicitly Paldean-suffixed form.
Their final status also reflects whether their base species has complete Dex
category/description evidence; source data, battle, icon, and follower support
are reported separately in the JSON.

There are 97 `SPECIES_MEGA_*` identities. `src/battle/mega.c` has 91 item/form
rows covering 84 unique base species, including the current PLZA additions.
Ninety-four Mega identities resolve through a base species present in that
table; three do not. A declaration or sprite is therefore not treated as proof
of a working Mega transition. No Mega runtime smoke test was performed in
Stage 5A.

## Expanded-species representative

Victini (`SPECIES_VICTINI`, engine ID 544) is the closest representative to a
complete expanded species because it is the first post-Gen-4 identity and has
direct personal data, evolution and learnset entries, front/back/icon assets,
cry `sound/cries/544.wav`, National Dex number/name/sprite/seen-caught paths,
and follower mapping and properties. Its expanded Dex category/description
path is unresolved, so its inventory status is `PARTIAL`.

The audit proves its data and serialization reachability, but not the requested
in-game matrix. Neither `data/Trainers.c` nor `data/Encounters.c` currently
references any post-Gen-4 species, and the existing declarative QA route does
not set up battle, party, PC, save/reset/Continue, trainer, wild, and follower
states without adding game content. Stage 5A deliberately did not add such
content. Victini therefore validates the inventory structurally but not at
runtime, making the stage result partial.

## Upstream relationship

The local revision is 30 commits ahead of BluRosie's `upstream/main` at
`c6d63fd8a34f63431214284dc08c3b7942ab0593` and zero commits behind at audit
time. The merge base is that same upstream commit. No roster, species data,
sprite, cry, follower, form, or learnset path differs in
`upstream/main...HEAD`; roster expansion is inherited from upstream rather
than added by this fork.

## Confidence and remaining unknowns

Source/build coverage and counts are confirmed by deterministic parsing and
tests. Runtime behavior for the chosen expanded species is unconfirmed. Cry
coverage confirms archive routing/payload presence, not authenticity against
official recordings. Form transition correctness, follower behavior for every
form, and Mega reversion/save behavior require representative runtime tests.

## Reproduction

```bash
make stage5a-roster-audit
.venv/bin/python -m unittest -v tests.test_pokeagent_stage5a_roster_inventory
git diff --exit-code -- docs/data/hgengine_roster_inventory.json
```
