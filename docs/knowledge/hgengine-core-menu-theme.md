# HG-Engine core-menu presentation ownership

## Finding

Stage 6F themes four structurally different native menu owners through one
project source while preserving their controllers:

| Surface | Native owner | Archive(s) | Themed palettes |
|---|---|---|---|
| Start/player menu | field shell / overlay 1 | `a/0/1/4` | 7, 14, 15, 61 |
| Party | party menu / overlay 94 | `a/0/2/1` | 4, 13, 16, 21, 23 |
| Summary | summary application | `a/0/3/9`, `a/1/6/2` | 26 members |
| Bag | overlay 15 | `a/0/1/5` | 13 members |

The common UI archive's members 7 and 14 are active start-menu BG palettes.
The Stage 6B summary named BG members 12/13 and palette 15, plus OAM members
61-64, but did not identify these two variants. Native-resolution evidence
remained green until both were included.

## Implementation contract

Canonical authoring lives in
`presentation/ui/screens/stage6f_core_menus.json`. It records stable screen
owners, semantic bindings, navigation actions, visual roles, and palette
intent. `tools/pokeagent/core_menu_ui.py` validates and compiles that source.

The transformation is owner-aware:

- neutrals interpolate from deep ink to warm paper;
- cool interface chrome maps to Adriatic teal;
- warm selection chrome maps to copper;
- party/status and summary/type semantic colors retain high saturation;
- BG owners may use palette-bank index zero as opaque color, while
  sprite-heavy owners preserve it as transparent.

The runtime proof patches only an ignored local ROM. Every extracted archive
is restored byte-for-byte even when compilation or packing fails.

## Evidence

- Source: `presentation/ui/screens/stage6f_core_menus.json`
- Compiler: `tools/pokeagent/core_menu_ui.py`
- Report: `docs/data/stage6_core_menus.json`
- QA: `qa/scenarios/stage6f_core_menus.json`, `qa/scenarios/stage6f_bag.json`
- Tests: `tests/test_pokeagent_stage6f_core_menus.py`

The final scenarios execute 38 steps and 13 assertions. They cover start-menu
open, party selection/context, summary open/page traversal, Bag open/pocket
navigation, cancellation, and safe return to map 540.

## Confidence

High for the four executed owners and 48 runtime-used palette resources. The
transformation does not claim every obscure party/summary mode has a unique
authored layout. Stage 6G/H will extend coverage and semantic QA rather than
replace these native state machines.

## Reproduction

```bash
make stage6f-core-menu-proof
. .venv/bin/activate
python3 -m tools.pokeagent qa run qa/scenarios/stage6f_core_menus.json --timeout 600
python3 -m tools.pokeagent qa run qa/scenarios/stage6f_bag.json --timeout 600
```

## Remaining unknowns

- Rare party action submodes share the themed resources but were not all run.
- Low-use summary contest/ribbon pages remain for Stage 6G's coverage matrix.
