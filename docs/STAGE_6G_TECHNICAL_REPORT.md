# Stage 6G Technical Report — Remaining Game UI

## Verdict

`STAGE_6G_REMAINING_GAME_UI_PASSED`

Stage 6G classifies all 25 remaining Stage 6B surfaces and adds a deterministic
presentation bundle for nine native resource owners and 76 audited NCLR
members. Native controllers remain authoritative for save, boot, storage,
Dex indexing, transactions, naming, capture, and evolution.

## Coverage boundary

The canonical source is `presentation/ui/screens/stage6g_remaining_ui.json`.
Its final matrix records 21 surfaces as `PARTIAL_HIGH_LEVEL_CONTROL` and four
animation/mode surfaces as `RESOURCE_THEME_ONLY`; none remain unknown,
deferred, or unjustifiably engine-fixed. “Partial” is precise: visuals and
semantic window/list contracts are high-level, while mature native controllers
continue to own game state.

Resource owners are global windows, title, main menu, Pokédex, PC, naming,
options, Pokégear shell, and Town Map. The compiler preserves semantic colors,
rejects collisions and budget overflow, rebuilds only ignored proof ROMs, and
restores every source archive byte-for-byte.

## Runtime evidence

| Path | Assertions | Result | ROM SHA-256 |
|---|---:|---|---|
| title + battery Continue | 6/6 | PASS | `3053cdcb917534edb43186114a34b4bac785b6a0d46b9125adbf3fc68a8fb75e` |
| Pecharunt National Dex #1025 | 6/6 | PASS | `da2f3e708987aa1cdbfbb8339bf14b9d666992c875da5a8dac54c9d0c466f81f` |
| PC storage/form/icon | 7/7 | PASS | `3148b5cc5472cc576609572b508630bf2139cb7377aabf0fef7ede6760be71ea` |
| shop + field dialogue | 5/5 | PASS | `c4406956cd8ec251962054ccd8060551defe3fc9372098e4281758d9c0962bcc` |

The title path creates an ordinary battery save, hard-resets, reaches title,
and displays Continue. The Dex path retains #1025, Pecharunt’s name/category/
description/sprite and seen/caught allocation. PC retains Victini species/form
semantics. Shop retains ordinary transaction navigation and dialogue flow.

Screenshot SHA-256 values:

- title: `cb7748c7e3cbfad56f8ff073b99dbecc39420250ade0b18b08c5b585429365de`
- Continue: `5b6e6fc4884e97f984fa70894715cca14901770aa2d85568afae34326369dd59`
- Pecharunt #1025: `e774206132ba83fde3ae9f2a1243becbb2e55eaeb1cd0f279f195fc01d7036b3`
- PC: `d5641e75a479f0ba71a2c3451552019838d0a42caad5d448d23be8da10544084`
- dialogue: `ff266d9d5150c4b2716467fe68e872ff84e8a81030d6ad485da6081c5b842b5f`
- shop: `dff2e18306b7a75b35e4dd2f643f787aa738f3cd1b1c9ba52789bc5bf6b32c8e`

## Determinism and review

The report is byte-identical across two roots. Source SHA-256 is
`f7d6eba0bc9c90c39eb801e6145540fc4d757f7ad96da1cdccdf136447a25161`.
Static naming/keymap ownership remains source-confirmed and native; Stage 6G
does not replace the character encoder with a new keyboard engine.

Adversarial review found no raw address in author source, no tracked retail
resource, and no proof content in normal builds. Screens remain readable at
256×192 and preserve Pokémon/type/icon focus. This proves theme/layout-resource
authorship, not arbitrary replacement of every overlay state machine.

The focused Stage 6B–G and Stage 5F regression selection passed 49/49.
Preflight passed 58/58. A clean normal build passed with ROM SHA-256
`eab6f22023020ebd4e0a6844ead42169dd8539b18b4a42393aec7a083de75ace`.

## DeepSeek

Not used. Cost: `$0`.

## Next stage

Advance automatically to Stage 6H to consolidate semantic, navigation, budget,
and screenshot QA into a reusable UI smoke system.
