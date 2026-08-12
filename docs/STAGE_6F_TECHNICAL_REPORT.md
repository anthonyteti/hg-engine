# Stage 6F Technical Report — Core Menu UI

## Verdict

`STAGE_6F_CORE_MENU_UI_PASSED`

Stage 6F adds deterministic high-level presentation control over the field
start menu, party, Pokémon summary, and Bag while retaining native HG-Engine
behavior. The accepted language is the Stage 6A Adriatic Field Journal: deep
ink, warm paper, Adriatic teal, and copper selection accents.

## Authoring and isolation

The canonical source is
`presentation/ui/screens/stage6f_core_menus.json`. It names four semantic
owners, 30 unique data bindings, navigation contracts, visual roles, and one
owner-aware palette policy. The compiler resolves five native archives and 48
palette members. It rejects duplicate targets, malformed NCLR payloads, schema
drift, and palette/budget violations.

No retail resource is tracked. The proof packer extracts local NARCs, replaces
only declared members, packs ignored `test.nds`, and restores all five archives
byte-for-byte in a `finally` boundary. Ordinary `make` does not run the Stage
6F patcher, seed content, or add a runtime symbol.

## Visual iteration

The first runtime pass over-preserved saturated colors: party and summary were
coherent, but start remained neon green and Bag remained stock pink. The
second pass made preservation owner-specific. It exposed a Stage 6B omission:
active start-menu BG palettes 7 and 14. Adding those source-backed members made
the start menu teal; Bag chrome became copper with teal accents, while party HP
and summary type colors remained readable.

This is a semantic resource theme over existing menu geometry, not a new menu
controller. It materially changes hierarchy and screen coherence without
risking party actions, summary tabs, Bag use, or child-app transitions.

## Runtime evidence

| Scenario | Steps | Assertions | Result |
|---|---:|---:|---|
| `stage6f_core_menus` | 24 | 8 | PASS |
| `stage6f_bag` | 14 | 5 | PASS |

The path opens start, party, context actions, and summary; changes summary
page; returns to field; opens Bag; changes pocket/selection; and exits to map
540. Both ROM-running gates pass.

Proof ROM SHA-256:
`d602aa6f06f164213207b47efaa625614229d89581eb084445b481f5f58ebdb5`.
ROM, screenshots, reports, and extracts remain ignored.

Screenshot hashes:

- start: `bbc12b3e3ea00cd28b40f36500e8d06afabc5594abaaa0d584f615ef2f936956`
- party: `3744b4410925707e646eba8aee8e7fc7c41112bed8767be7fd5a21465882f476`
- context: `8d154feff541d51a362d903d10e91255864e6f52dfa12d45f8c40a9652a127ba`
- summary: `c9351c20cdce8f940fbab5b3b6cb977c3faacee3aef0671c28f446b0339d74c4`
- summary page: `db55e8ae31b15a7e5bf6522dee96fd3d12b9e6d3b73c1cfd9fb9cecb8df39a8a`
- Bag: `f69b05026ea2148859e323fb5d1c3043db1022680fbcd97c551790aaff47a620`
- Bag pocket: `04265c6e0a00a6de3d419c4f553635d91dbab006f9c2b651b067842a8a2e13e9`

## Determinism and validation

The manifest is byte-identical across two output roots. Source SHA-256 is
`3a67c3b566f77b563b11e57740645306d31c69dd7339b06c7cfb76cf8950b488`.
Six tests cover schema, owners, target uniqueness, budget failure, NCLR
determinism, semantic preservation, BG index-zero handling, report freshness,
and scenario coverage.

The focused Stage 6B/6F and Stage 5B–5E regression selection passed 41/41.
Project preflight passed 58/58. A clean ordinary build produced ROM SHA-256
`eab6f22023020ebd4e0a6844ead42169dd8539b18b4a42393aec7a083de75ace`.

## Adversarial review

Evidence proves repeatable high-level theming and preserved navigation for four
high-use owners. It does not prove arbitrary relocation of every native window
or every obscure party action page. Keeping native controllers is deliberate:
Stage 7 needs safe rapid visual revision, not a second implementation of mature
Pokémon menu logic.

At 256×192 the final screens retain Pokémon/icon focus, legible text, strong
selected states, and DS-authentic density. The teal/copper system is distinct
from stock HGSS without resembling a web interface.

## DeepSeek

Not used. Cost: `$0`.

## Next stage

Advance automatically to Stage 6G for the remaining player-facing surfaces and
the final UI coverage matrix.
