# Declarative UI authoring on HG-Engine

## Finding

HGSS does not provide one universal runtime UI scene graph. A practical
high-level factory therefore consists of a shared validated schema plus
owner-specific native adapters. The Stage 6D proof compiles JSON into bounded
C configuration and lets the existing field task render it through native
windows and font functions.

## Authoring route

```text
presentation/ui/screens/stage6d_field_journal.json
  -> tools/pokeagent/ui_layout.py
  -> include/generated/stage6d_ui.h
  -> opt-in native window adapter
  -> proof ROM
  -> semantic QA + screenshot review
```

Run static compilation with:

```bash
make stage6d-ui-compile
```

Build the isolated proof with:

```bash
make stage6d-ui-proof
```

## Confirmed native behavior

- Field `MAIN_BG3` accepts the proof's native windows and text.
- Selection can be expressed as source configuration and rendered by fill
  state without patching raw coordinates.
- Live party values are safely obtained from `SaveData_GetPlayerPartyPtr`,
  `Party_GetMonByIndex`, and `GetMonData`.
- Input edge detection can drive compiled navigation without revision-specific
  addresses in canonical source or scenario JSON.
- Runtime QA can synchronize on a semantic lifecycle state rather than an
  arbitrary frame delay.

## Layer-ownership warning

The live field bottom screen already owns `SUB_BG0` character and tilemap
resources. Adding project windows to that layer without an owner allocation
causes tile corruption. A visible bottom-screen declarative adapter must be
integrated with the overlay that owns the layer or receive an explicit safe
allocation. Do not treat physical touch coordinates mapped to an invisible
top-screen control as valid touch UI.

## Confidence

High for the canonical source/compiler path, static budget checks, semantic
field adapter, focus navigation and native rendering. Medium for the reusable
TouchButton primitive until a battle/menu owner renders it visibly on the
touch screen in 6E/6F. Sprite/icon components and formatted dynamic text are
not yet implemented.

## Reproduction evidence

`docs/stage6/6D_RUNTIME_EVIDENCE.json` records source/header/report/ROM/plan
and screenshot hashes. Generated ROMs, saves, logs and screenshots remain
ignored.
