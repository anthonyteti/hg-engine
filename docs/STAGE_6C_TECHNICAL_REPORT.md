# Stage 6C Technical Report — UI Resource Factory

## Verdict

`STAGE_6C_UI_RESOURCE_FACTORY_PASSED`

Stage 6C proves a project-owned, deterministic route from symbolic visual
source to native Nintendo DS UI resources and a visible ROM surface. It does
not redesign a production screen; that begins with the declarative adapter in
6D and the battle/menu work in 6E–6G.

## Canonical source and compiler

- source: `presentation/ui/resources/stage6c_start_menu.json`
- compiler: `tools/pokeagent/ui_resources.py`
- tracked catalog: `docs/data/stage6_ui_resources.json`
- proof scenario: `qa/scenarios/stage6c_ui_resource_runtime.json`

The bundle has the stable symbolic identity
`ui.start_menu.adriatic_field_journal`. It composes a quiet field-journal
surface and three visibly distinct project chrome resources:

- `ui.surface.field_window`
- `ui.rail.lake_gradient`
- `ui.rail.paper_guide`
- `ui.rail.copper_shore`

Ordinary source names no raw NARC member, palette slot, VRAM address or OAM
index. The audited target allocation is isolated in the bundle target record.

## Supported Stage 6C formats

The current factory emits:

```text
structured palette/style/layout source
    -> indexed PNG preview/source raster
    -> compressed 4bpp NCGR
    -> compressed native-size NSCR
    -> 4bpp NCLR
```

The proof target is the audited start-menu BG3 triple in common archive
`a/0/1/4`: character member 12, screen member 13 and palette member 15. The
runtime palette occupies the retail-defined slot 14. These allocation details
belong to the adapter/compiler boundary, not ordinary presentation authorship.

## Validation and budgets

The compiler fails before ROM build on:

- invalid dimensions or non-tile-aligned layout;
- palette depth/count or duplicate colors;
- unknown visual pattern;
- missing, duplicate or out-of-range tile ownership;
- tilemap rows outside the bundle tile set;
- archive-member collisions;
- target allocation drift;
- character, screen or palette size overflow;
- missing Nitro compression/header signatures.

| Output | Budget |
|---|---:|
| palette colors | 16 |
| character tiles | 32 |
| compressed character bytes | 4,096 |
| compressed screen bytes | 2,048 |
| NCLR bytes | 552 |

Two independent output roots produce byte-identical PNG, tilemap JSON, NCGR,
NSCR and NCLR bytes.

## Runtime proof

The proof uses the existing Stage 5B controlled world and native start-menu
state machine:

```text
symbolic resource source
  -> deterministic Nitro compilation
  -> temporary common-archive member replacement
  -> proof ROM repack
  -> emulator controlled entry
  -> ordinary X-button start menu
  -> native-resolution screenshot
```

The screenshot visibly contains all three project resource roles while the
native menu icons, navigation and field lifecycle remain intact. Its ignored
runtime evidence SHA-256 is
`402c5d5368aefae2f8557230e3ef6a3b5e95ae0f515be327f001d2347655d74c`.
The proof ROM SHA-256 is
`d1f4312024c185836f47d23e790e381a05dc3c477de262d3e0ed762d304ef535`;
the subsequent isolated normal ROM is
`2522ab4fffef423e63efad9b5b1e7600767e71ad929540101d166dbba9409ad7`.

## Isolation and recovery safety

The user-local `base/root/a/0/1/4` is retail-derived and never tracked. The
proof wrapper reads its exact original bytes, rebuilds a temporary NARC, packs
the proof ROM, and restores the original archive in a `finally` boundary.
Restoration equality is asserted in the generated proof report.

No production C, overlay, normal resource manifest, retail archive, generated
ROM, screenshot or save is committed. A subsequent normal `make -j2` produces
the normal ROM without Stage 6C chrome.

## Adversarial review

This proves reusable BG tile/screen/palette authorship, not yet arbitrary OAM
animation or font replacement. Adding unused general converters now would be
an infrastructure spiral. Stage 6D can extend the factory with an OAM class
when an actual declarative component requires it, using the same identity,
budget and deterministic-output contracts.

The first proof render made the upper field too uniformly opaque. A second
canonical-source revision separated the lake grid, paper guide, and copper
shore rails. The HGSS start-menu BG mode renders palette index zero as an
opaque BG color rather than revealing the field scene; the final design treats
that constraint as a quiet journal surface instead of claiming transparency.
It remains deliberately bolder than stock HGSS so source-to-ROM causality is
visually unambiguous while retaining useful negative space.

## Tests and cost

- Stage 6C resource tests: schema, negative validation, Nitro headers/budgets,
  two-root determinism, tracked catalog and proof isolation
- Stage 6B UI reality regression
- Stage 5B controlled-world regression
- proof ROM boot and native menu screenshot
- normal ROM build and artifact hygiene

DeepSeek was not used. Cost: `$0`.
