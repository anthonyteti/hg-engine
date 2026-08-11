# HG-Engine Regional-Form Runtime

## Finding

The current fork stores regional Pokémon as base species plus an alternate-form number and derives an adjusted identity for form personal data and assets. Live representative evidence is:

```text
Zorua 620 + form 1 -> identity 1335
  -> ordinary EVO_LEVEL 30
Zoroark 621 + form 1 -> identity 1336
```

The same PID survived evolution and party/box battery saves. Icon, follower, personal data, and battle lookups refreshed to Hisuian Zoroark.

## Evidence

- constants and mappings: `include/constants/species.h`, `data/Species.c`, `data/FormToSpeciesMapping.c`;
- evolution: `data/Evolutions.c`, `src/pokemon.c`;
- storage: `include/pokemon.h`;
- wild form packing: `include/encounter.h`, `data/Encounters.c`, `src/field/enemy_party.c`;
- presentation: `src/field/overworld_table.c`, `data/FollowerProperties.c`, `src/pokemon.c`;
- proof runtime: `src/stage5d_runtime.c`;
- QA: `qa/scenarios/stage5d_regional_form_runtime.json`, `qa/scenarios/stage5d_hisuian_wild_form.json`.

## Reproduction

```bash
make stage5d-regional-form-proof -j2
. .venv/bin/activate
python3 -m tools.pokeagent qa run qa/scenarios/stage5d_regional_form_runtime.json --timeout 1000
python3 -m tools.pokeagent qa run qa/scenarios/stage5d_hisuian_wild_form.json --timeout 400
```

Expected: 154/154 and 14/14 assertions respectively. ROMs, saves, reports, traces, and screenshots remain ignored.

## Confidence and unknowns

Confidence is high for the executed line and shared base/form path. This is not proof of every regional identity. Trainer form bits, specialized regional evolutions, form-Dex UI, cry authenticity, expanded descriptions, and temporary battle forms remain unproven.
