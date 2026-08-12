# HG-Engine Mega Runtime

## Finding

The current fork represents Mega Altaria as a temporary battle form of
persistent Altaria:

```text
persistent species 334, form 0, Altarianite 755
  -> native fight-menu Mega request
battle species 334, form 1, adjusted identity 1108
  -> BattleEndRevertFormChange
persistent species 334, form 0
```

Form 1 selects Mega Altaria's Dragon/Fairy typing, Pixilate ability, personal
stats, and battle sprite. Battle end clears the one-use flags and reverts every
party record before field/save persistence. PID and held item remain stable.

## Evidence

- mapping and eligibility: `src/battle/mega.c`, `data/PokeFormDataTbl.c`,
  `data/FormToSpeciesMapping.c`, `include/config.h`;
- activation and transform: `src/battle/battle_input.c`,
  `src/individual/ServerBeforeAct.c`;
- battle data and reversion: `src/battle/battle_pokemon.c`, `src/pokemon.c`;
- source data/assets: `data/Species.c`,
  `data/graphics/sprites/mega_altaria/`;
- proof observer: `src/stage5e_runtime.c`, `include/stage5e_runtime.h`;
- QA: `fixtures/stage5e_mega_runtime.json`,
  `qa/scenarios/stage5e_mega_runtime.json`.

## Reproduction

```bash
make stage5e-mega-proof -j2
. .venv/bin/activate
python3 -m tools.pokeagent qa run qa/scenarios/stage5e_mega_runtime.json --timeout 600
```

Expected result: 85/85 semantic assertions, ordinary Altaria before battle,
Mega identity 1108 while battling, ordinary identity 334 after battle and
after battery-save Continue, and renewed Mega eligibility in a second battle.
Generated ROMs, saves, traces, reports, and screenshots remain ignored.

## Confidence and remaining unknowns

Confidence is high for the executed player-side item-triggered Mega and shared
reversion path. This is not per-identity proof for all Megas. AI Mega use,
multi-battle ownership, move-triggered Mega forms, every mapping/asset, and
Mega animation/cry authenticity remain targeted future regressions if actual
content requires them.
