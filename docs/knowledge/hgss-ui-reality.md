# HGSS UI reality and authoring boundaries

## Finding

HGSS UI is a federation of application-specific renderers rather than one
theme system. The project can still provide a coherent high-level authoring
layer, but it must compile shared descriptions through surface-specific
adapters while retaining the native application state machines.

## Confirmed ownership

- overlay 60: title
- overlay 74: New Game / Continue and save summary
- overlay 1 plus ARM9: dialogue and field/start shell
- ARM9 plus overlay 94 helper: party
- ARM9/shared: summary, naming and evolution tasks
- overlay 15: Bag
- overlay 14: PC storage
- overlay 18 plus project overlay 132: Pokédex
- overlay 3: shop
- overlay 12 plus support overlays: battle
- overlay 30 plus field code: save UI
- overlays 50–52: Trainer Card
- overlay 54: options
- overlays 100–101: Pokegear and Town Map

This is confirmed by local source/binaries and cross-checked against
`pret/pokeheartgold` revision
`90e85d4e027f5e04800e7e015b3207094061402c`.

## Shared primitives already present

`Window`/`WindowTemplate`, system-font rendering, message/string formatting,
list menus, `TouchscreenHitbox`, fades and sprite/OAM managers are reusable
native foundations. They are implementation mechanisms, not yet stable
project-level presentation APIs.

## Recommended authoring boundary

Canonical future source should name semantic components and bindings. A
compiler should validate budgets and generate resource/layout tables. Small
adapters in the owner module translate those tables to native windows, BG
resources, sprites, touch hitboxes and state transitions. UI source must never
name a RAM address, NARC member number, VRAM address, raw palette slot or OAM
index as its ordinary interface.

The native logic to retain includes save detection, party context modes,
PC manipulation, item use, Pokédex indexing, battle command dispatch, shop
transactions, script text control codes and overlay lifecycle transitions.

## Resource routes

The implementation-reference names establish these important families:

- title: `demo/title/titledemo` plus title 3D resources
- main menu: `a/1/1/3`
- common frames/windows: `a/0/1/4`
- party: `graphic/plist_gra` plus Pokémon icons
- Pokédex: `graphic/zukan_gra` plus project expanded text
- options: `a/0/7/2`
- battle presentation: `a/0/0/7` and `a/0/0/8`

The local ROM-derived members remain local and must not be redistributed.

## Runtime reproduction

Use the existing QA runner with the scenarios listed in
`docs/stage6/6B_RUNTIME_REFERENCES.json`. The Stage 6B shop fixture warps through
an ordinary field script into retail map header 68; the clerk then launches the
native overlay 3 shop flow.

Regenerate and validate the model with:

```bash
make stage6b-ui-audit
```

## Confidence and unknowns

Confidence is HIGH for 38 surfaces and MEDIUM for 11. There are zero unbounded
UNKNOWN surfaces. MEDIUM means that exact member/coordinate recovery remains
adapter work, not that ownership or user flow is unknown.

Remaining bounded unknowns include exact resource-member semantics inside some
binary overlays, invocation-mode differences in summary/party, and per-mode
touch geometry. These should be recovered only as required by 6C–6G.
