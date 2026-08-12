# HG-Engine roster production readiness

## Finding

The Stage 5A flat audit status is useful provenance but is not a production
backlog. A deterministic semantic layer now evaluates each identity according
to project scope and its real runtime family. For the corrected #1-1025 roster,
there are no required base-species, Dex, cry-routing, regional-form, or Mega
static gaps.

Scope must use `sPokedexSort_NationalNum`, not the numeric species constant:
HG-Engine reserves internal IDs 494-543, so internal IDs cannot define game
scope. The ordered `sPokedexSort_NationalNum` mapping establishes all 1,025
base identities through `SPECIES_PECHARUNT` (internal ID 1075, National Dex
#1025).

Confidence: high. Counts and source/generated equality are deterministic;
shared runtime claims come only from Stages 5B-E. Cry authenticity for expanded
source WAVs remains explicitly unverified.

## Evidence and reproduction

Canonical evidence:

- `01_PROJECT_SPEC.md`: #1-1025 roster, curated main-story pool, and no
  Dynamax/Gigantamax;
- `include/constants/species.h`, `data/Species.c`, `data/Evolutions.c`,
  `data/FormToSpeciesMapping.c`;
- `src/field/overworld_table.c`, `data/FollowerProperties.c`;
- `src/battle/mega.c`, `src/field/enemy_party.c`;
- `data/PokedexSort.c`, `armips/asm/pokedex.s`,
  `tools/source/speciesdatagen/species_data_gen.c`, `narcs.mk`;
- `src/pokemon.c`, `src/sound.c`, `armips/asm/cries.s`, `sound/cries/`,
  and `CREDITS.md`;
- Stage 5B-E technical reports and runtime artifacts.

Reproduce:

```bash
make stage5f-dex-proof
make stage5fs-dex-boundary-proof
make stage5f-roster-readiness
python3 -m tools.pokeagent qa run qa/scenarios/stage5f_expanded_dex_ui.json --timeout 600
python3 -m tools.pokeagent qa run qa/scenarios/stage5f_expanded_dex_gen6.json --timeout 600
python3 -m tools.pokeagent qa run qa/scenarios/stage5f_expanded_dex_gen7.json --timeout 600
python3 -m tools.pokeagent qa run qa/scenarios/stage5f_expanded_dex_gen8.json --timeout 600
python3 -m tools.pokeagent qa run qa/scenarios/stage5f_expanded_dex_gen9.json --timeout 600
python3 -m tools.pokeagent qa run qa/scenarios/stage5fs_pecharunt_dex_boundary.json --timeout 600
```

Inventory output is canonical at
`docs/data/hgengine_roster_inventory.json`; archive comparison output is
ignored at `build/reports/stage5f-dex-archive-validation.json`.

## Classification model

Every record retains `status` and gains `production`:

```json
{
  "scope": "IN_SCOPE",
  "family": "MEGA_TEMPORARY",
  "readiness": "READY",
  "required_gaps": [],
  "optional_gaps": [],
  "not_applicable": [
    "ordinary_follower",
    "persistent_form_storage",
    "independent_national_dex_identity"
  ],
  "reason_codes": [
    "STAGE_5E_REPRESENTATIVE_MEGA_ARCHITECTURE_PROVEN"
  ]
}
```

Primary readiness values include `READY`, required functional/content gaps,
authenticity-unverified, intentional-not-applicable, out-of-scope, reserved,
architecturally-covered-unexecuted, and external-content-blocked. Optional debt
does not overwrite a functional `READY` result.

## Dex correction

The old later-generation category/description `false` values were audit
heuristics, not missing source. All 1,025 base records contain content in
`Species.c`, and three generated message members match exactly by identity.
The historical booleans remain unchanged so the correction is transparent.
Production Dex readiness is based on the actual source/generator/archive/UI
path.

## Cry truth

Safe route and authentic provenance are separate. Retail #1-493 uses the
user-supplied HeartGold route. Gen 5+ bases have source WAVs and deterministic
pseudo-bank routing, but credits/source presence does not independently prove
canon authenticity. Their readiness therefore reads runtime `READY` plus
authenticity `ROUTED_SOURCE_PRESENT_UNVERIFIED`.

## Remaining unknowns

- Authentic/canonical provenance of the 532 expanded source WAVs is not
  independently verified.
- The 212 non-regional/non-Mega special forms are statically complete under a
  shared form contract but are not individually runtime-executed or selected
  as required game content.
- All 97 current-fork Mega identities are production-classified by an exact
  base/source-form/target-form/trigger/reversion contract. Only Mega Altaria is
  the representative executed runtime proof; the rest use the shared Stage 5E
  architecture plus complete static contracts.
- Specialized evolution/form triggers remain targeted regressions only when
  chosen production content depends on them.

These are nonblocking Stage 5 debts, not hidden required gaps.
