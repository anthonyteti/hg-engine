# Full-roster production scope

## Finding

The production-supported base roster is every implemented National Dex identity
from #1 through #1025 (Bulbasaur through Pecharunt). Scope is derived from
`sPokedexSort_NationalNum`, never from the shifted HG-Engine species IDs. The
main story will later select an approximately 300–350-species encounter pool;
whole-game and postgame completion must eventually make all 1,025 bases
obtainable.

This correction does not put 1,025 species into encounter tables. It changes
the production-readiness and design boundary only.

Confidence: high. Two clean deterministic inventory generations resolve exactly
1,025 base identities, including all 120 Generation 9 bases. Every required
base is `READY`, with zero functional, Dex-content, or cry-routing gaps.

## Form scope

- 55 regional persistent identities are in scope and pass the persistent-form
  static contract. Stage 5D remains the representative runtime proof.
- 97 Mega temporary identities are in scope and pass the exact base/source-
  form/target-form/trigger/reversion contract. Stage 5E remains the shared
  runtime proof.
- 34 Gigantamax identities remain `OUT_OF_SCOPE_FOR_GAME`.
- the two Alcremie filler identities remain reserved structural slots.
- other battle, cosmetic, size, weather, item, Totem/large, Lord, and special
  identities retain family-specific optional or architecturally-covered status;
  base-roster scope does not make each independently obtainable.

The corrected Mega audit exposed source-table defects, not a new mechanic:
missing Heatran and Darkrai rows and incomplete or incorrect form-specific
Meowstic/Magearna/Tatsugiri rows. The runtime table now selects exact source
forms and all 97 repository-backed Mega identities have complete temporary-form
contracts. Historical Stage 5A audit labels remain unchanged. The general-item
pocket retains its existing 48-slot incremental Mega reserve: every one of the
92 distinct item triggers is classified and usable, but simultaneously
collecting the complete ordinary-item catalog and every stone is not guaranteed.
Widening that save/UI capacity is explicit nonblocking completion-content debt.

## Upper boundary

`SPECIES_PECHARUNT` is internal engine ID 1075 and National Dex #1025. The
Stage 5F-S opt-in fixture uses the existing Stage 5F Dex UI route to verify its
number, name, sprite, category, description, and seen/caught presentation. It
does not add roster data or normal-build behavior.

## Evidence

- `01_PROJECT_SPEC.md`
- `data/PokedexSort.c`
- `include/constants/species.h`
- `data/Species.c`
- `data/FormToSpeciesMapping.c`
- `data/PokeFormDataTbl.c`
- `src/battle/mega.c`
- `include/constants/item.h`
- `docs/data/hgengine_roster_inventory.json`
- `qa/scenarios/stage5fs_pecharunt_dex_boundary.json`
- Stages 5B–5E representative runtime reports

## Reproduction

```bash
python3 -m tools.pokeagent.roster_inventory \
  --output docs/data/hgengine_roster_inventory.json
make stage5f-roster-readiness
make stage5fs-dex-boundary-proof
python3 -m tools.pokeagent qa run \
  qa/scenarios/stage5fs_pecharunt_dex_boundary.json --timeout 600
```

## Remaining limitations

- Provenance establishes safe routing but not canon authenticity for 532
  expanded cry sources.
- Only representative members of shared base, evolution, regional, and Mega
  architectures were executed; deterministic static contracts cover the rest.
- The exact main-story Regional Dex and full-game acquisition distribution are
  later content-design work.
- Mega records are classified from repository source. This task did not acquire
  external commercial art or invent missing mechanics.
