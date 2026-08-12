# Presentation Bible — Adriatic Field Journal

Status: Stage 6 canonical direction

Selection: autonomous Codex decision

Native target: Nintendo DS, 256×192 per screen
Dominant parent: Adriatic Field Journal

## Direction in one sentence

A warm field journal made by a confident coastal civic culture: pale limestone,
terracotta, blue-green water, dark ink, and alpine pine organized with the
clarity of a good station sign.

This is a Pokémon interface and world first. Pokémon silhouettes, names, health,
choices, paths, doors, and traversal affordances must remain more legible than
decoration. The direction should feel authored for this Adriatic/Alpine region,
not pasted onto stock HGSS and not shrunk from a web application.

## Controlled hybrid

The primary design philosophy is **Adriatic Field Journal**.

- From **Alpine Signal**, borrow only high-contrast information rails,
  unmistakable focus outlines, and condensed numeric treatment. These solve
  dense battle/menu states while fitting the region's railway and civic-signage
  vocabulary.
- From **Karst Nocturne**, borrow only a restricted copper-on-slate dramatic
  variant for caves, ruins, climax moments, and Championship spectacle. It is
  not the default UI or world exposure.

Warm paper, limestone cards, terracotta focus, sea-teal semantics, and natural
material logic remain dominant. The borrowed pieces serve clarity and dramatic
range; they do not form a third mixed style.

## Core palette

| Token | RGB | Use |
|---|---|---|
| `ink` | `#263238` | Primary text, outlines, deep rails, structural contrast |
| `paper` | `#F2E8D5` | Main panels, text grounds, quiet interiors |
| `limestone` | `#D8C8A8` | Secondary panels, paths, masonry, inactive controls |
| `terracotta` | `#B95E46` | Selection, important tabs, roofs, warm identity |
| `sea` | `#247B87` | Information, water, selected meters, navigation accents |
| `pine` | `#355F4A` | Healthy states, vegetation, grounded secondary emphasis |
| `sun` | `#E4B44A` | Focus edge, rare reward, caution; never long body text |
| `shadow` | `#6E5546` | Secondary text, stone shadow, disabled/inactive structure |

### Palette rules

- A normal screen uses `ink`, `paper`, and no more than three main accents.
- `terracotta` means current action or regional warmth; it must not compete with
  HP/status semantics.
- `sea` carries informational and navigation meaning. `pine` carries healthy or
  grounded meaning.
- `sun` is a small-area focus light. Large yellow panels are prohibited.
- Red/green battle state must remain distinguishable by value and shape, not hue
  alone.
- Biome palettes shift material colors while the semantic UI palette remains
  recognizable.

## Typography

### Roles

- **Data/body:** compact humanist sans, optimized for the existing DS font
  renderer and short line lengths.
- **Section labels:** squared small caps or all caps, one weight heavier than
  body text.
- **Numbers:** tabular where the engine/font route permits; level, HP, PP,
  money, and Dex numbers must not jump horizontally as values change.
- **Dramatic title:** a limited carved/serif accent may be rendered as a graphic
  for title cards or landmarks. It must not become the routine text font.

### Hierarchy

1. Current action, Pokémon name, or screen identity.
2. Primary values needed for a choice: HP, move, item, quantity, selected row.
3. Supporting labels: level, type, status, category.
4. Descriptions and help.

Use size, weight, panel contrast, and placement before adding colors. Do not use
outline-heavy decorative text for dense data.

## UI geometry

### Frames and windows

- Primary panels are offset limestone/paper cards sitting against a dark ink
  rail or field.
- Corners are clipped or softly stepped, not desktop-rounded pills.
- Borders are normally 1–2 native pixels. A selected element may add a second
  `sun` edge or a terracotta tab.
- A panel needs a job: containment, hierarchy, selection, or touch affordance.
  Decorative boxes around every label are prohibited.
- Visual depth is two levels: field and card. A third modal layer is reserved
  for confirmations and item/move details.

### Spacing

- Native base spacing unit: 4 px.
- Common gaps: 4, 8, 12, and 16 px.
- Text should normally retain 4 px vertical and 6 px horizontal interior clear
  space.
- Pokémon battle sprites receive generous clear zones and may overlap the world
  ground, but not essential HUD text.
- Edge-safe margin is at least 4 px; touch actions use larger hit regions than
  their visible labels.

### Focus and selection

- Selected cards use terracotta fill or tab plus a `sun` 1–2 px edge.
- Cursor motion is short and direct; a 2–4 px settle or palette pulse is enough.
- Disabled states reduce contrast and add a structural cue; they do not simply
  become a hard-to-read grey.
- Touch targets expose a clear pressed state on the same frame that accepts the
  input where the engine permits.

### Iconography

- Icons are compact, filled, and built from one dominant silhouette.
- Functional icons use consistent stroke weight and a 16×16 or 24×24 design
  grid before DS conversion.
- Pokémon and item icons remain authoritative; surrounding decoration yields to
  their existing palette/readability needs.
- Arrows, tabs, and category marks may use regional sign/wayfinding forms, but
  never become literal road-sign pastiche.

## Screen responsibilities

### Top screen

- World/battle presentation, selected Pokémon or item detail, dialogue portrait,
  and current contextual identity.
- Preserve a large quiet zone for sprites, maps, or descriptions.

### Bottom screen

- Choice, navigation, touch controls, lists, and inspectable secondary data.
- Touchable controls must look touchable without looking like web buttons.
- Avoid duplicating all top-screen information; use the pair as one composition.

When an existing overlay reverses these roles for architectural reasons, keep
the information hierarchy consistent rather than forcing a risky rewrite.

## Battle UI philosophy

- The Pokémon battle is the image; UI forms a supporting frame.
- Player and enemy HUDs use quiet limestone cards attached to an ink or sea
  information rail. Their silhouettes differ enough to communicate ownership.
- HP is long enough to read at a glance and retains explicit numeric detail for
  the player where existing behavior supports it.
- Status is a compact badge adjacent to HP/name, never floating ambiguously.
- Fight is the dominant action, but Bag, Pokémon, and Run remain equally
  discoverable.
- Move selection favors a 2×2 or clear compact list depending on audited engine
  ownership. Each move exposes name, type, and PP without crowding the Pokémon.
- Mega eligibility is a distinct sun-edged terracotta control. Its selected and
  requested states must differ, and it must feed the existing native Mega path.
- Battle messages use a stable reading region; animated UI never competes with
  text reveal.

## Menu hierarchy

- Start menu is a compact field kit: strong selection, quick scanning, no giant
  empty chrome.
- Party emphasizes the selected Pokémon with one larger card while retaining a
  fast six-slot scan.
- Summary uses stable tabs and makes the Pokémon sprite/name the anchor.
- Bag uses a strong pocket rail, a readable item list, and a calm description
  zone. It does not attempt to solve unrelated Mega-item capacity debt.
- Pokédex resembles a regional field index: number rail, specimen/sprite clear
  zone, category, concise description, and unmistakable seen/caught state.
- PC prioritizes spatial box comprehension and icon/form identity over ornament.

## Animation

- Standard response: 4–8 frames for focus/palette response, 6–12 frames for a
  short panel or cursor move, 12–20 frames for a major screen entrance.
- Use position, frame, visibility, palette/fade, cursor motion, and simple
  hardware-supported scale only where proven safe.
- One dominant moving element per interaction. Background decoration is still
  while reading or choosing.
- Transitions should communicate hierarchy: card in/out, rail wipe, short
  directional slide, or palette fade.
- Avoid elastic web-style easing, perpetual hover animation, and gratuitous
  parallax.

## Information density

- Present what the current decision needs. Keep secondary detail one action away
  when possible.
- Lists should show enough rows to preserve fast DS navigation; do not inflate
  every row into a touch card.
- Empty space is functional: it protects sprites, descriptions, and focus.
- At 256×192, if a label must shrink below the established readable font, change
  the composition or wording instead.

## World language

### Terrain and paths

- Terrain reads in broad color/value fields before texture detail.
- Paths use pale compacted stone, warm soil, or civic paving with clear edge
  contrast and predictable corners/junctions.
- Terrain transitions use a small vocabulary of deliberate edges. Avoid noisy
  checkerboard blending.
- Slopes and stairs need a strong leading edge and visible destination.

### Cliffs, karst, and mountains

- Limestone cliffs favor layered shelves, vertical fissures, and light upper
  planes rather than generic brown rock walls.
- Alpine rock grows darker/cooler with altitude. Snow, if used, is a sparse
  value cap, not texture noise.
- Karst interiors use slate shadow with controlled copper/sun highlights and
  clear navigable floors.

### Water and coastline

- Water is blue-green with broad bands and a restrained bright edge.
- Lake edges are calmer and more vegetated; Gulf and island edges expose pale
  stone, docks, retaining walls, and occasional foam accents.
- Traversable docks/bridges must remain distinct from decorative water edges.

### Architecture

- Buildings are compact Pokémon-world abstractions, not realistic miniatures.
- Typical wall-to-roof visual ratio is about 2:1; important civic landmarks may
  stretch vertically while retaining readable entrances.
- Rural/coastal roofs are low terracotta forms. Alpine roofs become steeper and
  darker. Metropolitan roofs flatten or hide behind cornices.
- Walls use pale render or limestone; dark ink/slate is structural trim, not the
  whole facade.
- Doors are oversized enough for field readability and collision intent.
  Windows group into strong rhythms rather than tiny repeated specks.
- Balconies, awnings, shutters, chimneys, and signs are modular accent families.

### Vegetation and rocks

- Tree families need distinct silhouettes: columnar cypress, rounded deciduous,
  alpine conifer, wind-shaped coastal pine.
- Bushes and ground plants form clusters with negative space; flowers are small
  palette accents, not confetti.
- Rocks use 2–4 primary planes and a readable base shadow. Avoid faceted noise.

### Props

- Props explain place: dry-stone fence, rail sign, market awning, dock bollard,
  rural crate, civic lamp, planter, bench, utility pole, railing.
- Repetition uses controlled variants and spacing patterns.
- Props never hide doors, collision turns, or grass/encounter affordances.

### Interiors

- Floors and walls use calm large fields. Counters/shelves establish function;
  small decoration establishes personality.
- Interior palettes inherit local biome materials while retaining universal UI
  interaction readability.
- Furniture dimensions are driven by overworld sprite scale and collision, not
  real-world proportion.

## Environment families

### Upper Valleys

Warm meadow greens, pale stone lanes, compact farm compounds, low terracotta
roofs, orchards, dry-stone boundaries, and distant cool ridges. Density is low;
views and path clarity carry the scene.

### Lake Country

Softer blue-green water, rounded deciduous trees, garden walls, villas, small
piers, and calm civic promenades. Refined but not metropolitan.

### Karst Interior

Grey limestone shelves, deep slate openings, sparse hardy plants, copper lamps,
bridges and stair cuts. The Nocturne accent appears here in bounded doses while
walkable surfaces remain light.

### Great Gulf

Bright pale masonry, terracotta roof rhythm, seawalls, broad harbors, market
awnings, maritime utilities, and stronger sun/sea contrast. Civic spaces feel
open and wind-exposed.

### Islands

Low white/limestone volumes, scrub vegetation, wind-shaped pine, narrow stone
paths, docks, and singular silhouettes such as towers or shrines. Decoration is
sparse so landmarks dominate.

### High Country

Cooler stone, steeper dark roofs, conifers, snow/ice accents where appropriate,
rail/cable infrastructure, and strong elevation silhouettes. Alpine Signal's
clarity informs signs and transit props.

### Metropolitan Corridor

Denser pale facades, shadowed arcades, flat/corniced roofs, teal transit accents,
regular street furniture, rail structures, plazas, and controlled signage.
Terracotta becomes a selective heritage accent rather than covering every roof.

### Championship Island

Monumental limestone, formal water, dark ink/slate structural planes, copper and
sun highlights, disciplined vegetation, and large negative space. It combines
the core journal materials with the restricted dramatic variant.

## Technical visual rules

### Native readability

- Design and inspect at 256×192, not only enlarged.
- Critical shapes survive nearest-neighbor viewing with no antialiasing.
- One native pixel is meaningful; avoid subpixel assumptions and hairlines.
- Pokémon sprites/icons retain priority over decorative BG/OAM elements.

### Geometry versus texture

- Geometry carries silhouette, collision, roofline, major trim, and depth.
- Texture carries material, windows/doors where flat treatment is sufficient,
  and small repeated accents.
- Never spend polygons recreating invisible texture noise; never paint collision
  or important silhouette solely into a flat texture.

### Texture and palette discipline

- Prefer small repeatable power-of-two textures compatible with proven Stage 4
  paths; expand material capacity only through explicit symbolic allocation and
  runtime proof.
- A normal module should use one primary material family and at most one accent
  unless catalog evidence justifies more.
- Mip-like detail that disappears at field camera distance is waste.
- Seams belong on architectural/material boundaries.

### Geometry budgets

- Existing Stage 4 per-model display-list ceiling remains 4,096 bytes.
- Reusable modules should stay materially below the ceiling to preserve world
  composition headroom.
- Hard normals, UV seams, components, and collision are explicit budget inputs.
- A landmark may approach the ceiling only when its silhouette and runtime role
  justify it.

### Sprite/BG/OAM discipline

- Static full-screen structure favors BG/tilemap resources where audited.
- Interactive cursors, icons, Pokémon, and short animations favor OAM within
  explicit per-screen budgets.
- Do not duplicate the same visual simultaneously as BG and OAM without an
  animation/ownership reason.
- Touch targets are semantic regions and may exceed visible OAM bounds.

### Modularity and repetition

- Terrain, buildings, vegetation, and props expose stable symbolic identities.
- Controlled variants alter approved components, never arbitrary materials or
  transforms.
- Repetition is broken by rhythm, orientation, clustering, and a bounded accent
  set before bespoke geometry is introduced.

### Silhouette hierarchy

1. Traversable terrain and entrances.
2. Player, follower, people, and Pokémon.
3. Landmark/building mass.
4. Vegetation and functional props.
5. Decorative detail.

If a lower tier damages a higher tier at native resolution, simplify it.

### Camera assumptions

- Default authoring assumes the normal HGSS field camera.
- A wider fixed camera may be used on a separately proven suitable map.
- Smooth dynamic zoom/pan is not required by this direction.
- Roofs, cliffs, signs, and landmark tops must be composed for the actual camera,
  not a freely orbiting model viewer.

## Presentation quality gate

A presentation change passes only when it is functional, native-resolution
legible, coherent with this Bible, visible in the ROM, deterministic from
canonical source, and reusable by a future agent. “Technically renders” is not
enough for Stage 6 presentation work.
