# Stage 6B Technical Report — Complete UI Reality Audit

## Verdict

`STAGE_6B_UI_REALITY_AUDIT_PASSED`

The current HeartGold/HG-Engine checkout has a deterministic, source-backed
inventory of the important player-facing UI. The audit does **not** claim that
high-level control exists yet. It establishes the ownership and modification
boundaries that Stages 6C–6H must use.

## Revisions and evidence boundary

- audited project baseline: `9e9b76c6cac9e6fd0dc035d834388a1f4cf6a7eb`
- same-version retail implementation reference: `pret/pokeheartgold`
  revision `90e85d4e027f5e04800e7e015b3207094061402c`
- local fork source, overlay binaries and local NARC members remain
  authoritative for what this checkout actually contains
- the temporary `pret/pokeheartgold` checkout was used only to recover stable
  function and archive names; it was not vendored

## Canonical model

The authored model is
`presentation/ui/ui_reality_source.json`. The deterministic expanded report is
`docs/data/hgengine_ui_reality_audit.json`.

| Measure | Result |
|---|---:|
| UI systems | 18 |
| player-facing/support surfaces | 49 |
| required core surfaces | 40 / 40 |
| HIGH-confidence surfaces | 38 |
| MEDIUM-confidence surfaces | 11 |
| UNKNOWN surfaces | 0 |

Classifications are multi-valued because a screen can combine overlay code,
hard-coded behavior and generated resources. Across the 49 records the model
contains 46 `MIXED`, 26 `OVERLAY_CODE`, 21 `CODE_DRIVEN`, two `LAYOUT_DATA`, and
two `ENGINE_PATCH_REQUIRED` classifications.

## Architectural finding

There is no single HGSS UI skinning boundary. UI responsibility is divided
between ARM9/shared code and many overlays:

| System | Primary owner |
|---|---|
| title | overlay 60 |
| New Game / Continue | overlay 74 |
| field/start/dialogue | overlay 1 plus ARM9 shared code |
| party | ARM9 plus overlay 94 helper |
| summary | ARM9/shared implementation |
| Bag | overlay 15 |
| PC storage | overlay 14 |
| Pokédex | overlay 18 plus project extension 132 |
| shop | overlay 3 |
| battle | overlay 12 plus support overlays and project extension |
| save | overlay 30 plus field save code |
| Trainer Card | overlays 50–52 |
| options | overlay 54 |
| Pokegear/Town Map | overlays 100–101 |
| naming/evolution | substantially ARM9/shared tasks |

Consequently Stage 6D must use a shared semantic schema with bounded
per-surface adapters. A universal binary-coordinate patch would neither cover
the UI nor preserve overlay-specific behavior.

## Runtime reference matrix

The audit exercised existing native UI paths. Screenshots are ignored runtime
evidence; their hashes are recorded in `docs/stage6/6B_RUNTIME_REFERENCES.json`.

| Surface | Runtime path |
|---|---|
| title / boot | `stage6b_title_reference` |
| start menu / party | `stage5bc_victini_icon_ui` |
| summary | `stage6b_summary_reference` |
| Bag | `stage6b_bag_reference` |
| PC | `stage5bc_victini_pc_icon_ui` |
| Pokédex | `stage5f_expanded_dex_ui` |
| battle | `stage5bc_victini_trainer_runtime` |
| dialogue / Continue | existing `stage4a_world_persistence` control |
| shop | `stage6b_shop_reference`, native Cherrygrove Mart header and clerk |

The shop reference fixture changes only an opt-in test warp destination. It
uses retail map header 68, the ordinary object event and the ordinary shop
overlay; no alternate shop implementation was created.

## Modification strategy

Stage 6C should first cover shared tiled panel/window resources and a bounded
OAM resource class. Stage 6D should compile semantic screen descriptions into
generated layout/resource tables consumed by adapters. Battle, Bag, PC,
Pokédex, title and other overlays retain their native state machines.

The registry records for every surface include ownership, resources, BG/OAM
behavior, palette/tilemap route, window/font route, input and touch ownership,
semantic bindings, transitions, constraints, confidence, and the recommended
adapter strategy.

## Validation

- canonical report generated twice byte-identically
- every local evidence path resolves
- every core surface has ownership and an authoring strategy
- no surface remains `UNKNOWN`
- bounded reference scenarios use opt-in proof targets
- normal production UI has not been altered in Stage 6B
- normal `make -j2` ROM SHA-256:
  `4a61b75387bcf369b9f6de4d7eae128829a089edec55bae75d58147e8772e469`
- Stage 6A and Stage 5F focused regressions remain green

The first shop-reference attempt reached header 69 rather than 68. Review
showed that the newly added Make target had accidentally retained the old
Stage 5B-C clean/rebuild commands beneath it, so the valid Mart fixture was
overwritten by the Pokémon Center fixture. The target boundary was corrected;
the unchanged scenario then passed 7/7 assertions on header 68. This was a
test-build ordering defect, not a shop or overlay defect.

## Adversarial review

The audit proves enough ownership to build a factory; it does not prove that
every coordinate or archive member has already been named. Eleven surfaces are
MEDIUM confidence, chiefly because their local implementation remains partly
binary/assembly. They are bounded by known module, resources, state machine and
adapter boundary. Deeper recovery should happen only when the responsible
Stage 6C–6G adapter needs it.

It would be wasteful to decompile every obscure or unused screen now. No major
player-facing screen is omitted, and no `ENGINE_FIXED` claim has been made.

## DeepSeek and external cost

DeepSeek was not used. Cost: `$0`.

The official public `pret/pokeheartgold` Git repository was accessed at no
cost. No paid service, proprietary asset download, or retail asset
redistribution occurred.
