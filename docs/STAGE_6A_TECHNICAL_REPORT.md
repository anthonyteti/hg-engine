# Stage 6A Technical Report — Visual Direction and Presentation Bible

## Verdict

`STAGE_6A_DIRECTION_SELECTED`

Selected direction: **Adriatic Field Journal**.

## Baseline and authorization

Stage 6 began from clean synchronized commit
`dedf0ee52b7ea2d8326834f3bd70249ecb94eb5c`. The master authorization replaces
the old early-human-gate policy with autonomous Codex selection at 6A. The sole
planned creative gate is the integrated Stage 6L review.

## Evidence inspected

- project specification, research/decisions, architecture, and roadmap;
- region families and current game-scope constraints in project documents;
- Stage 4 deterministic texture/model/world and visual-QA constraints;
- Stage 5 expanded Pokémon sprite/icon/UI evidence;
- existing local concept and proof fixtures;
- HGSS/HG-Engine native resolution, overlay, Nitro, OAM, palette, and build
  constraints already recorded by the project.

The repository does not yet contain a detailed final story/location art package.
Stage 6A therefore treats the eight authorized environment families and the
Adriatic/Alpine premise as the source contract, rather than inventing Stage 7
content.

## Candidate directions

1. **Adriatic Field Journal** — warm civic craft, sea clarity, limestone cards,
   terracotta focus, and a field-guide information hierarchy.
2. **Alpine Signal** — crisp railway signage, cobalt rails, geometric modular
   grids, high altitude clarity, and denser technical information.
3. **Karst Nocturne** — dark slate/cut-stone panels, copper light, dramatic
   negative space, monumental karst, and cinematic contrast.

These are not palette swaps. They differ in panel geometry, density,
typography, focus behavior, world massing, roofs, vegetation, dramatic range,
and production burden. Deterministic boards show a 256×192 battle study, party
study, Dex study, environment language, palette, and system notes for each.

The generated matrix is [decision_matrix.md](stage6/boards/decision_matrix.md),
and the canonical scores/visual parameters are
[`presentation/stage6/directions.json`](../presentation/stage6/directions.json).

## Matrix result

| Candidate | Weighted mean |
|---|---:|
| Adriatic Field Journal | 9.029 |
| Alpine Signal | 8.629 |
| Karst Nocturne | 7.571 |

The 17-criterion matrix weights Pokémon authenticity, native 256×192
readability, DS feasibility, UI/environment scalability, and 40+ hour coherence
most heavily. Scores are documented design judgments, not runtime metrics.

## Adversarial review

### Does the leader work at 256×192?

Yes in the planning evidence: broad value fields, compact cards, 1–2 px border
rules, restrained accent count, explicit sprite clear zones, and a four-pixel
spacing grid survive native framing. Detailed implementation must still prove
each screen at runtime.

### Does it still feel like Pokémon?

Yes. It preserves sprite primacy, fast scan patterns, concise touch decisions,
bright natural color, friendly compact geometry, and an exploratory field-guide
tone. It does not use desktop navigation, glass panels, tiny web typography, or
unbounded data density.

### Is it sufficiently distinct from stock HGSS?

Yes at the system level: asymmetrical offset cards, dark information rails,
limestone/paper material logic, terracotta focus tabs, sea semantic meters, and
a region-specific world kit replace a global stock palette swap. Stage 6B must
still identify stock remnants and actual ownership before implementation.

### Is it too modern or exhausting?

No. Warm low-contrast reading grounds and limited accent use make the default
quieter than Alpine Signal or Karst Nocturne. Modern clarity is borrowed through
focus rails, not web-card conventions or perpetual motion.

### Can it scale across UI and eight environment families?

Yes. The field-journal hierarchy covers dense menus while the material palette
maps naturally to rural, coastal, alpine, karst, urban, and ceremonial spaces.
The Bible defines controlled variants rather than eight unrelated art styles.

### Does it demand excessive bespoke art?

No. The core language favors reusable frames, signs, roof/wall/trim modules,
four vegetation silhouettes, symbolic palettes, and controlled variants.
Landmarks remain intentional exceptions.

### Can it survive DS texture and geometry limits?

Yes in principle. Broad silhouettes and material fields carry identity before
fine texture. The existing 4,096-byte model ceiling is preserved, and the Bible
explicitly separates geometry, texture, BG, and OAM roles. Stages 6C/6I must
provide runtime proof.

## Controlled hybrid decision

Adriatic Field Journal remains the dominant parent.

- Alpine Signal contributes high-contrast information rails and unmistakable
  focus outlines, improving battle/touch clarity.
- Karst Nocturne contributes only a restricted copper-on-slate mode for karst,
  ruins, Championship, and other dramatic spaces.

Neither borrowed element changes the normal warm paper/limestone/terracotta/sea
identity. This is a controlled functional hybrid, not a collage.

## Canonical outputs

- [Presentation Bible](stage6/PRESENTATION_BIBLE.md)
- [Direction source](../presentation/stage6/directions.json)
- [Adriatic Field Journal board](stage6/boards/adriatic_field_journal.png)
- [Alpine Signal board](stage6/boards/alpine_signal.png)
- [Karst Nocturne board](stage6/boards/karst_nocturne.png)
- [Board manifest](stage6/boards/manifest.json)
- [Weighted matrix](stage6/boards/decision_matrix.md)

## Determinism and safety

`tools/pokeagent/stage6a_visuals.py` validates the schema, exact native target,
palette tokens, unique candidates, score range, matrix leader, and bundled
deterministic font. Two clean generations must be byte-identical. The boards use
only project-owned shapes/text/colors; no retail or externally generated art is
embedded.

## Implementation implications and risks

- Stage 6B must establish which overlays can accept resource/layout generation
  and which need bounded engine adapters.
- The warm palette must not reduce battle HP/status contrast.
- Terracotta selection cannot collide with fire-type or error semantics.
- Existing Pokémon palettes/icons may constrain surrounding BG/OAM palettes.
- The dark dramatic variant must stay exceptional or it will undermine long-play
  comfort.
- Building proportions must be verified against the real overworld camera and
  player sprite before catalog approval.

These are implementation risks, not unresolved creative contradictions.

## DeepSeek and external services

DeepSeek calls: 0. Cost: $0.
External image-generation calls: 0. Cost: $0.

## Conclusion

The selected direction is coherent, DS-plausible, scalable across the approved
region, and specific enough to drive the UI audit/resource factory and
environment kit. Stage 6A passes and Stage 6B follows automatically.
