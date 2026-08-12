# Stage 6 Presentation Direction

## Finding

The canonical presentation direction is **Adriatic Field Journal**: warm
limestone/paper surfaces, terracotta focus, blue-green information/water,
dark-ink structural rails, and pine grounding. It is a controlled hybrid that
borrows only focus clarity from Alpine Signal and a restricted dramatic variant
from Karst Nocturne.

## Evidence

- `presentation/stage6/directions.json`
- `tools/pokeagent/stage6a_visuals.py`
- `docs/stage6/boards/manifest.json`
- `docs/stage6/boards/decision_matrix.md`
- `docs/stage6/PRESENTATION_BIBLE.md`
- `docs/STAGE_6A_TECHNICAL_REPORT.md`

The 17-criterion weighted matrix scores the selected direction 9.029, ahead of
Alpine Signal at 8.629 and Karst Nocturne at 7.571. Deterministic boards expose
battle, party, Dex, environment, palette, and typography intent at DS framing.

## Confidence

- Selection and source contract: `CONFIRMED_SOURCE`.
- Board determinism: `CONFIRMED_TEST` after the Stage 6A tests run.
- DS runtime visual quality: `PLANNED`; each later UI/world substage must prove
  its implementation in ROM at 256×192.

## Reproduction

```bash
make stage6a-presentation
```

The command regenerates boards and runs the Stage 6A validator/tests. Compare
the generated board manifest and file hashes across runs.

## Remaining unknowns

- Exact overlay/resource ownership for every UI surface (Stage 6B).
- Which audited UI resources share palette/VRAM allocations (Stage 6B/6C).
- Actual reusable building/terrain budgets in composed maps (Stage 6I).
- Which direction details need simplification after native ROM review.
