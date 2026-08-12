# Stage 6 integrated presentation boundary

## Finding

One ignored HGSS ROM can safely compose the project-owned Stage 6 UI themes,
two different world display-list owners, ordinary battle construction, and the
existing native Mega machinery. Composition requires explicit screen/resource
ownership; blindly applying all theme transforms in sequence is unsafe.

## Evidence

- compiler: `tools/pokeagent/stage6l_showcase.py`
- fixture: `fixtures/stage6l_presentation_showcase.json`
- scenario: `qa/scenarios/stage6l_integrated_showcase.json`
- canonical report: `docs/data/stage6l_presentation_showcase.json`
- runtime: 22/22 semantic assertions, ROM SHA-256
  `59ca43a9b8caa9a01c469cfffa5d4bcb64b016b624b68a2eaa0bee3c751ecc3f`

The UI transaction owns 134 resources in 15 NARCs. Specific core-menu owners
override a colliding generic remaining-UI transform. Battle replacements must
not collide. The source archives are restored after the ROM is packed.

World composition uses one Stage 6I module and the Stage 6K generated
landmark, in shapes 1 and 6 respectively. Their display lists use 2,124/2,496
and 4,092/4,096 bytes. A schema-14 fixture is allowed two placements only for
the integrated showcase; it does not expand normal placement policy.

## Confidence

- Resource/world composition: confirmed by deterministic source and ROM.
- Native battle/Mega/reversion integration: confirmed at runtime.
- Presentation quality: candidate evidence only until human Stage 6L review.
- Suitability as final Stage 7 art: not claimed; the sandbox is intentionally
  bounded and sparse.

## Reproduction

```bash
make stage6l-presentation-showcase
. .venv/bin/activate
python3 -m tools.pokeagent qa run \
  qa/scenarios/stage6l_integrated_showcase.json --json
```

## Remaining unknowns

- Whether the current balance of native HGSS geometry and Field Journal color
  treatment is visually distinct enough for the creative director.
- Whether the sparse sandbox communicates the environmental direction strongly
  enough without being mistaken for a finished route.
- Whether the first generated landmark's heavy faceting is acceptable as a
  pipeline proof or needs a better presentation candidate later in Stage 7.
