# Stage 6I Technical Report — Environment Art Kit

## Verdict

`STAGE_6I_ENVIRONMENT_ART_KIT_PASSED`

Stage 6I establishes a project-owned, deterministic Adriatic/Alpine environment
vocabulary without introducing Blender or another GUI into ordinary authoring.
The canonical kit contains 58 symbolic modules spanning terrain, vegetation,
architecture, reusable architecture parts, props, and interiors. Every module
declares dimensions, biome applicability, symbolic material, and visual tags.

## Factory boundary

Canonical source is
`presentation/environment/stage6i_environment_kit.json`. The compiler
`tools/pokeagent/environment_kit.py` validates the vocabulary and emits
reproducible OBJ proof meshes plus `docs/data/stage6_environment_kit.json`.
Generated meshes use only the proven symbolic texture catalog and flow through
the unchanged Stage 4 asset normalization, Nitro display-list, texture-container,
collision, placement, map-install, ROM-build, and emulator paths.

The kit covers all eight Presentation Bible environment families. Counts are:

| Family | Modules |
|---|---:|
| terrain | 14 |
| vegetation | 9 |
| architecture | 9 |
| architecture parts | 8 |
| props | 10 |
| interiors | 8 |

The production texture/material capacity remains the three proven symbolic
32×32 4bpp resources: ground, wood, and stone. Stage 6I did not weaken the
one-material-per-proof-asset rule or expand any model/display-list ceiling.

## Runtime sandbox

`fixtures/stage6i_presentation_sandbox.json` places two generated composites:

- rural timber kit: house/tree silhouette, 32 positions, 24 quads, 2,124-byte
  display list (85.096% of its 2,496-byte shape);
- coastal civic kit: plaster/stone civic silhouette, 16 positions, 12 quads,
  1,068-byte display list (100% of its inherited secondary shape).

The proof ROM SHA-256 is
`576b41358875a6b59801ec3f297fa8996e50655fa27022a773ecd1190259798b`.
The semantic scenario passed 13/13 assertions, including controlled entry,
traversal, both collision proxies, screenshots, and 600 stable frames.

Screenshot SHA-256 values:

- rural: `063f156f0266c15753ecfed4cc6842bf8868c8801262190375d314779e0e244e`;
- coastal: `3328e3b25cedb9aa2deb442110f52e3b1670f6443930da913708a6b39d284b6a`.

Native-resolution review confirms distinct rural and civic silhouettes,
grounding, collision, readable scale, and coherent wood/stone separation. The
sandbox is intentionally sparse and modular; it proves the production
vocabulary and compiler boundary, not a finished Stage 7 location.

## Determinism and safety

Two in-process generations are byte-identical. The compiler rejects duplicate
symbols, invalid biome coverage, unsupported materials, and mixed-material
Stage 4 proof meshes. Project-authored outputs are CC0-1.0. No retail asset,
ROM, save, screenshot, or emulator output is tracked.

DeepSeek was not used. Cost: `$0`.

Advance automatically to Stage 6J.
