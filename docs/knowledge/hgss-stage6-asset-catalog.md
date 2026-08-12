# HGSS Stage 6 Asset Catalog

## Finding

A useful world-planner boundary is a stable approved asset identity with spatial,
biome, collision, visual, and budget metadata. Nitro resource coordinates must
remain compiler-owned. Controlled variants are reproducible compositions of
approved modules, not unconstrained random mutations.

## Evidence

- `presentation/environment/stage6j_variants.json`
- `tools/pokeagent/asset_catalog.py`
- `docs/data/stage6_asset_catalog.json`
- `tests/test_pokeagent_stage6j_asset_catalog.py`

The generated catalog contains 99 identities: 58 base modules and 41 variants.
Same-source/same-seed generation is byte-identical.

## Confidence

High for catalog schema, deterministic selection, source lineage, and planner
isolation. Runtime geometry/material/collision confidence comes from the Stage
6I representatives and unchanged Stage 4 compilers; all 99 identities are not
individually placed in an emulator.

## Reproduction

```bash
make stage6j-asset-catalog
sha256sum docs/data/stage6_asset_catalog.json
```

## Remaining unknowns

Stage 7 production composition will determine whether particular families need
additional approved components. That is catalog growth, not a change to this
authoring contract.
