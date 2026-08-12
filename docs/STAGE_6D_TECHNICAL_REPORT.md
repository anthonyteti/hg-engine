# Stage 6D Technical Report — Declarative UI Engine

## Verdict

`STAGE_6D_DECLARATIVE_UI_ENGINE_PASSED`

Stage 6D proves a bounded declarative authoring boundary for native HGSS UI:
canonical JSON is validated and compiled into native window/component,
semantic-binding, selection and navigation configuration; an opt-in adapter
renders that configuration in the ROM and exposes semantic evidence to QA.
It is an extensible owner-adapter architecture, not a claim that every overlay
already consumes the schema. Battle and menu adapters are the work of 6E–6G.

## Canonical boundary

- source: `presentation/ui/screens/stage6d_field_journal.json`
- compiler: `tools/pokeagent/ui_layout.py`
- generated C: `include/generated/stage6d_ui.h`
- tracked machine report: `docs/data/stage6_ui_layouts.json`
- runtime adapter: `src/stage6d_runtime.c`
- QA plan: `qa/scenarios/stage6d_declarative_ui_runtime.json`

The ordinary source names the symbolic resource bundle
`ui.start_menu.adriatic_field_journal` and semantic values
`party[0].species`, `party[0].level`, `party[0].hp`, and
`party[0].max_hp`. It contains no raw runtime address, NARC member, VRAM
address, palette slot, or OAM index.

## Implemented primitives and behavior

The first compiled subset is deliberately small:

```text
Text
Panel
Button
TouchButton (schema/compiler/runtime adapter capability; not used by this
             top-screen proof)
```

It supports native tile bounds, fill/selected-fill state, symbolic bindings,
left/right focus navigation, confirm/cancel actions, source-defined trigger,
native touch rectangles for compatible bottom-screen owner adapters, and
bounded selection-animation metadata. The generated runtime arrays replace
manual coordinate editing for this supported screen class.

The proof screen is a top-screen field journal. SELECT opens it, directional
input changes selection, and B invokes the source-declared close action. The
adapter observes the live lead party record (Victini, species 544, level 20)
rather than reading revision-specific addresses. An empty party is handled as
`SPECIES_NONE` rather than dereferencing slot zero.

## Static rejection and budgets

The compiler rejects:

- unsupported component or binding types;
- raw/unknown semantic bindings;
- duplicate component/binding identities;
- out-of-native-resolution bounds;
- component overlap;
- unsupported text glyphs;
- missing/dead navigation targets;
- invalid touch rectangles;
- window, tile, touch-region, BG-layer, or palette budget overflow.

The canonical screen uses 5 windows and 296 of 308 allowed window tiles on one
BG layer. It declares three navigable controls and no touch region because its
visible surface is the non-touch top screen. Two output roots are byte
identical. A positive source-causality test changes title and initial focus and
requires a different generated header/hash.

## Runtime evidence

The proof ROM SHA-256 is
`4ded182ba358eb673a2af29f483b74eec65141a7bdaa2131a246369493b6a814`.
The deterministic QA plan SHA-256 is
`86d246a069500b5bd58b91b20a4cb722be9aafd788252f6fffbad0bf21822d7f`.
All 16 semantic assertions passed, including source token, component/binding/
tile counts, live party species/level, open state, selected-state transition,
source action, close lifecycle and continued ROM execution.

Ignored native-resolution screenshots:

| View | SHA-256 |
|---|---|
| initial Party focus | `3b3d9bb8190a42e74b9d786baa081c99dacf2a249ce4488f026090e16c3a99ab` |
| right-navigation Bag focus | `fd8e865f6f967d323e0e0e3905e88568e663b266373c203846da5480903e64c4` |

The visual proof is intentionally plain: it proves authored hierarchy,
spacing, source text and selected-state causality. Production styling and the
screen-specific visual systems begin in 6E. It is not presented as the final
Field Journal design.

## Evidence-driven correction

An exploratory adapter placed the windows on live field `SUB_BG0` so visible
buttons and touch regions would coincide. Runtime inspection showed that layer
already owns the native field touch shell; sharing its tile allocation caused
visible corruption. The experiment was rejected and is not acceptance
evidence. The safe audited `MAIN_BG3` route was restored, and the canonical
top-screen proof uses non-touch Buttons.

This establishes an important adapter rule: a bottom-screen `TouchButton`
must be rendered by the owning battle/menu overlay or by a layer allocation it
explicitly controls. Stage 6E/6F will provide that visible touch proof; Stage
6D does not pretend an invisible touch region is acceptable.

## Isolation and adversarial review

The adapter is compiled only under `STAGE6D_DECLARATIVE_UI_PROOF`. Normal
builds contain neither the hook nor `gStage6DRuntimeState`. No production
overlay lifecycle is replaced. The clean normal ROM SHA-256 is
`eab6f22023020ebd4e0a6844ead42169dd8539b18b4a42393aec7a083de75ace`;
symbol-table inspection confirms both Stage 6D runtime symbols are absent.

What is proven: diffable source can alter layout, text, selection and
navigation; semantic party data reaches a native window adapter; static
budgets fail before ROM; the screen renders and closes safely.

What remains bounded: screen-owner adapters, formatted dynamic text, sprite/
icon primitives, visible bottom-screen touch affordance, and production visual
polish. Implementing a general arbitrary UI VM now would be an infrastructure
spiral; these capabilities are added only where 6E–6G consume them.

DeepSeek was not used. Cost: `$0`.
