# HG-Engine expanded level-evolution runtime

## Finding

The current fork executes the existing Popplio (778) -> Brionne (779) ->
Primarina (780) line through `EVO_LEVEL` thresholds 17 and 34. One Pokémon with
PID `0x050C0001` survives both ordinary evolution scenes, presentation refresh,
party battery saves, and final PC-box battery persistence.

Confidence: confirmed by source inspection, compiled proof build, semantic
emulator assertions, battery save/reset/Continue, and ignored screenshots.

## Source evidence

- `data/Evolutions.c`: `{ EVO_LEVEL, 17, SPECIES_BRIONNE }` and
  `{ EVO_LEVEL, 34, SPECIES_PRIMARINA }`.
- `data/Species.c`: base stats, Water/Water -> Water/Fairy typing, Torrent.
- `data/learnsets/learnsets.json`: level move prompts, including Primarina's
  Sparkling Aria.
- `src/field/overworld_table.c` and `data/FollowerProperties.c`: all three
  follower mappings/properties.
- `src/party_menu.c` and `src/pokemon.c`: ordinary Rare Candy reuse,
  `GetMonEvolution`, and cutscene mutation path.

## Proof boundary

`STAGE5C_EVOLUTION_PROOF` seeds the initial test individual and grants Rare
Candies. The player-facing Bag and evolution UI perform every level and species
transition. Proof hooks observe species, level checkpoints, evolution method,
cutscene mutation, icon selection, follower resolution, and persisted data.
They do not call the evolution engine or write species/level fields.

Proof bookkeeping must not use `0x4000..0x401F`: HGSS defines those as
temporary script variables, and normal menu/evolution scripts overwrite them.
The isolated fixture uses otherwise-unused persistent proof variables
`0x416D..0x416F`. Normal builds omit all Stage 5C code.

## Reproduction

```bash
make stage5c-evolution-proof
.venv/bin/python -m tools.pokeagent qa run \
  qa/scenarios/stage5c_evolution_runtime.json --timeout 1200
```

Expected milestones are level-17 Brionne and level-34 Primarina with PID
84672513. The proof declines all new moves normally and retains move IDs
577/453/611/196. Party Brionne, party Primarina, and boxed Primarina each pass
ordinary battery-save hard-reset/Continue validation.

The canonical plan has 347 steps and SHA-256
`de6addc58fe9065adf821df4172a0c2cdfcef7ddab8ae96700605e0658ef190f`.
Two complete executions each passed 167/167 semantic assertions and produced
the same proof-ROM SHA-256
`ce6adafd70dcae417ed5a64a5c3f6ce4a475b7d570149090aacd0cbb8554a741`
and the same canonical screenshot hashes.

## Interpretation

This is representative architectural evidence, not per-line completion. It
does not alter the roster inventory's content-completeness classification and
does not establish regional-form or Mega behavior. Expanded Dex descriptions,
cry authenticity, non-level evolution methods, split evolution choices, and
evolution-driven form transitions remain separate unknowns.
