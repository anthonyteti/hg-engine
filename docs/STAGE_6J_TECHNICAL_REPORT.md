# Stage 6J Technical Report — Procedural Variants and Asset Catalog

## Verdict

`STAGE_6J_ASSET_CATALOG_PASSED`

Stage 6J turns the Stage 6I environment vocabulary into a deterministic,
planner-facing catalog. It contains 99 approved identities: 58 base modules and
41 controlled variants across houses, trees, rocks, fences, market stalls,
lamps, furniture, and small props.

## Controlled variants

Canonical variant policy lives in
`presentation/environment/stage6j_variants.json`. Each family declares a
bounded base set, named component slots, an exact output count, and the stable
seed `stage6j-v1-adriatic-field-journal`. The compiler uses SHA-256 selection;
the same source and seed produce byte-identical compositions. Changing the seed
changes component choices without changing schemas, counts, or safety budgets.

Arbitrary transformations and materials are not exposed. Every selected base
and component must be a known Stage 6I module. Unknown references and duplicate
identities fail before asset generation.

## Canonical catalog

`docs/data/stage6_asset_catalog.json` records, for every identity:

- category and biome tags;
- footprint, three-dimensional bounds, height, and legal rotations;
- collision policy;
- symbolic textures;
- geometry and texture budgets;
- canonical source and variant lineage;
- controlled components, approval state, and visual tags.

The catalog SHA-256 is
`ca0647e09bed9de6114818287f1ea1aa1aa7381debec239b60912b8b0a29bd34`.
The world-planner contract is explicit: request `asset_id`; deterministic
compilers own Nitro shapes, material indices, texture slots, and NARC members.

## Validation

Four Stage 6J tests prove completeness, unique IDs, planner-facing metadata,
byte determinism, seed sensitivity, and rejection of unknown components. Four
Stage 6I regressions remain green. Runtime representation remains established
by the Stage 6I sandbox; Stage 6J adds no second one-off world proof.

DeepSeek was not used. Cost: `$0`.

Advance automatically to Stage 6K.
