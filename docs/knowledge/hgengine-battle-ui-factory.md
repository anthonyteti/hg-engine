# HG-Engine battle UI factory

## Finding

Overlay 12 is a mixed UI owner. Its lower command/fight presentation is resource-driven from `a/0/0/7`, while native C owns text, button feedback, touch decoding, Mega request state, and transitions. Battle HP/name/status HUDs are OAM sprite/cell assemblies using the shared 16-color palette at `a/0/0/8` member 71.

The Stage 6E compiler safely owns:

```text
a/0/0/7 char       28
a/0/0/7 screens    36,37,38,39,41,42,43,353
a/0/0/7 palette    246
a/0/0/7 touch pal  271
a/0/0/7 Mega pals  351,352
a/0/0/8 HUD pal    71
```

The source is `presentation/ui/screens/stage6e_battle.json`; generated outputs are local proof artifacts. Archive replacement is temporary during ROM packing, and both original archives are restored.

## Important implementation behavior

The lower command character resource is 4bpp. An 8bpp replacement is incompatible with this audited BG mode and visibly corrupts the screen. Native button feedback rewrites tile palette-bank bits, so every one of the 16 banks must contain a valid themed palette. Native screen setup can also reload cached palettes; a screen-owner adapter must synchronize authored palette data at the actual callback seams instead of relying on arbitrary frame waits.

The shared HUD palette indices 5–13 carry HP and status semantics. Preserve those positions unless production battle logic is intentionally being changed. Neutral indices can be themed without altering battle calculations or HUD state.

## Evidence

- `src/battle/battle_input.c`
- local pokeheartgold decomp `src/battle/battle_hp_bar.c`
- `tools/pokeagent/battle_ui.py`
- `docs/data/stage6_battle_ui.json`
- `qa/scenarios/stage6e_battle_ui.json`
- `qa/scenarios/stage6e_battle_commands.json`
- `docs/STAGE_6E_TECHNICAL_REPORT.md`

## Confidence

High for the accepted resource identities, native callback seams, touch rectangles, Mega flow, Bag/switch/run branches, and live 256×192 presentation. Medium for obscure multiplayer and special battle variants not exercised by the bounded proof.

## Reproduction

```bash
make stage6e-battle-ui-proof
. .venv/bin/activate
python3 -m tools.pokeagent qa run qa/scenarios/stage6e_battle_ui.json --timeout 900
python3 -m tools.pokeagent qa run qa/scenarios/stage6e_battle_commands.json --timeout 900
```

## Remaining unknowns

- Link/multiplayer battle presentation constraints.
- Runtime visual evidence for the unchanged double-battle target screen.
- Whether a later presentation pass should replace the HUD sprite silhouette rather than only its neutral palette.
