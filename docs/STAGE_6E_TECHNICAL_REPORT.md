# Stage 6E Technical Report — Battle UI Proof

## Verdict

`STAGE_6E_BATTLE_UI_PASSED`

Stage 6E materially redesigns the live HG-Engine battle command and move-selection presentation from the declarative Adriatic Field Journal source while retaining native battle, input, text, Bag, party, targeting, and Mega behavior.

## Authoring boundary

- canonical source: `presentation/ui/screens/stage6e_battle.json`
- compiler/installer: `tools/pokeagent/battle_ui.py`
- generated semantic constants: `include/generated/stage6e_battle_ui.h`
- tracked report: `docs/data/stage6_battle_ui.json`
- focused QA: `qa/scenarios/stage6e_battle_ui.json`
- command-branch QA: `qa/scenarios/stage6e_battle_commands.json`

The source owns panel geometry, semantic styles, palette, touch rectangles, screen roles, bindings, animation policy, and budgets. It does not expose raw runtime addresses. The audited adapter targets overlay 12 resources in `a/0/0/7`: character 28, palette 246, touch palette 271, screen members 36/37/38/39/41/42/43/353, and native Mega palettes 351/352. It also themes the shared battle HUD palette at `a/0/0/8` member 71.

## Visual result

The bottom screen now uses paper move cards, copper selection accents, deep-teal navigation rails, and a pale field-journal command field. Main commands use an asymmetric full-width Fight field plus a three-command lower rail. The Mega affordance remains a distinct bounded control beside Cancel. The top HUD retains its proven sprite/cell geometry while its neutral frame colors use paper, copper, and teal. HP and status indices 5–13 retain their existing semantic colors.

An exploratory 8bpp character resource produced striped corruption and was rejected. The accepted resource is 4bpp and 32 tiles. Native selection changes palette-bank bits, so the compiler repeats the 16-color theme across all BG banks and the proof-only overlay adapter reloads the authored palette at the native screen lifecycle seams. This is evidence-backed ownership synchronization, not arbitrary frame timing.

## Function and semantics

The canonical Mega route passed 51/51 focused assertions and the unchanged Stage 5E full route passed 85/85. It proves native eligibility, request, Mega Altaria identity 1108, personal battle data, one-move execution, battle completion, reversion, persistence, and later-battle reset with the redesigned UI active.

The command route passed 38/38 assertions. It opens and exits the native battle Bag, opens the party switch UI, switches from Altaria to a proof-only Magikarp through the ordinary party flow, exercises the legal trainer-battle Run denial/return path, and remains stable. The second party member is added only under `STAGE6E_BATTLE_UI_PROOF` through a generic proof command before battle. The Stage 5E canonical fixture remains one-member and unchanged.

Double-battle target selection remains source-covered through the audited native member 41 and semantic `battle.target` binding. A separate double-battle runtime matrix was deliberately not created: the adapter does not change the native target-selection controller, and Stage 6 avoids multiplying battle-mode proofs when the shared owner is unchanged.

## Determinism and budgets

Two independent output roots are byte-identical. The canonical source SHA-256 is `cab8f3cb73744e743d1d3bbdd080419e2f341f780e5f850221ee1f4802dd7815`. Generated resources remain below their declared 4,096-byte character and 2,048-byte per-screen limits; bounds, overlap, touch alignment, binding, BG, tile, and palette checks all pass before ROM packing.

The final proof ROM SHA-256 is recorded by the ignored proof manifest. Project-owned resources are installed only into a local built ROM; both retail-derived source archives are restored byte-for-byte after packing. No extracted retail UI resource is tracked.

## Adversarial review

The result is visibly distinct from stock HGSS without behaving like a desktop/web UI. Text and Pokémon sprites remain native and readable at 256×192. The material redesign is concentrated in the bottom command surface and neutral HUD framing; it does not replace reliable native Bag or party overlays ahead of Stage 6F. Proof-only behavior is feature-gated, normal source data is unchanged, and no Mega engine logic was reimplemented.

Known bounded debt: the top HUD silhouette remains native, and double-target runtime presentation is architecture-covered but not separately executed. Neither blocks the authored battle system or the core-menu work that follows.

DeepSeek was not used. Cost: `$0`.
