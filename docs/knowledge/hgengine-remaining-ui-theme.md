# HG-Engine remaining UI presentation boundary

## Finding

The remaining major UI can be themed deterministically without replacing its
native state machines. Nine source archives cover the principal visual owners;
shared windows/lists and previously proven battle, party, and summary owners
cover the other Stage 6G surfaces.

## Evidence

- canonical source: `presentation/ui/screens/stage6g_remaining_ui.json`
- compiler: `tools/pokeagent/remaining_ui.py`
- generated matrix: `docs/data/stage6_remaining_ui.json`
- reality source: `docs/data/hgengine_ui_reality_audit.json`
- runtime scenarios: `qa/scenarios/stage6g_*.json`

The selected archives are `a/0/1/4`, `a/0/4/6`, `a/1/1/3`, `a/0/6/8`,
`a/1/6/5`, `a/0/3/1`, `a/0/7/2`, `a/1/4/3`, and `a/1/4/4`.

## Confidence

High for archive structure, transforms, title/Continue, Dex #1025, PC, shop,
and dialogue. Medium for rarely exercised naming, Trainer Card, and Pokégear
submodes; their owners are source-confirmed but not separate runtime matrices.

## Reproduction

```bash
make stage6g-remaining-ui-compile
make stage6g-title-proof
python3 -m tools.pokeagent qa run qa/scenarios/stage6g_title_continue.json
```

Generated ROMs, saves, screenshots, and reports remain ignored.

## Remaining unknowns

Stage 6H should consolidate navigation and semantic smoke coverage. It should
not replace native save, boot, transaction, storage, capture, evolution, or
naming controllers.
