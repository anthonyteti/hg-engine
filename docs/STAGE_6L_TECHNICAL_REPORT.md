# Stage 6L Technical Report — Integrated Presentation Candidate

## Status

`INTEGRATED_PRESENTATION_CANDIDATE_READY_FOR_HUMAN_REVIEW`

Stage 6L is still in progress. The automated integrated candidate has passed,
but the Stage 6 master contract reserves final presentation acceptance for the
human creative review. This report deliberately does not issue the final Stage
6 verdict.

## Integrated build

The opt-in `stage6l-presentation-showcase` target combines, in one ROM:

- the Stage 6E battle presentation and native Mega path;
- the Stage 6F start-menu, party, summary, and Bag presentation;
- the Stage 6G remaining-screen resource theme;
- the Stage 6I rural environment module;
- the Stage 6K real Hunyuan3D lighthouse/watchtower;
- a normal wild-battle constructor and the existing Stage 5E Altaria proof
  observer.

The build is isolated behind `STAGE6L_PRESENTATION_SHOWCASE`. Its field fixture
uses existing project map 538/member 633, contains two symbolic asset
placements, and limits encounter terrain to one narrow proof-only region.
Normal encounter tables and production geography are unchanged.

The integrated UI pack applies 134 deterministic resources across 15 audited
NARCs. A screen-specific owner wins any collision with a generic theme owner;
battle resources reject collisions. Every ignored retail-derived archive is
restored byte-for-byte after ROM packing.

## Automated route

`qa/scenarios/stage6l_integrated_showcase.json` passed 22/22 semantic
assertions against ROM SHA-256
`59ca43a9b8caa9a01c469cfffa5d4bcb64b016b624b68a2eaa0bee3c751ecc3f`.
The route covers controlled entry, start menu, party, summary, Bag, field
traversal, rural-kit collision, generated-landmark collision, native wild
battle, redesigned commands, native Mega request, Mega Altaria identity 1108,
move execution, battle completion, reversion to Altaria 334/form 0, return to
field, and 600 stable frames.

The integrated ROM contains the Stage 6G theme resources as part of the same
134-resource transaction. Because title/Continue, Pokédex, PC, and shop require
different controlled save/world fixtures, their established focused runtime
routes were rerun as a companion review matrix rather than fabricating one
impossible field sequence: title/Continue passed 6/6, Pokédex #1025 passed
6/6, PC/storage passed 7/7, and shop/dialogue passed 5/5. These runs compile
from the same canonical Stage 6G source packed into the integrated ROM.

The AI visual pass found and corrected two evidence defects before the human
gate: an early blank start-menu capture and a field capture taken before the
battle overlay had fully released presentation state. The final scenario
captures the loaded menu and waits for the field presentation to settle.

## Presentation evidence

Ten native 256x384 dual-screen captures are written under
`build/qa/stage6l_integrated_showcase/screenshots/`:

- `showcase_start_menu.png`
- `showcase_party.png`
- `showcase_summary.png`
- `showcase_bag.png`
- `showcase_field_corridor.png`
- `showcase_rural_environment.png`
- `showcase_generated_landmark.png`
- `showcase_battle_commands.png`
- `showcase_mega_active.png`
- `showcase_return_to_field.png`

The candidate is coherent and readable, but intentionally honest about its
limits. The UI factory currently has strong deterministic resource ownership
and native-state preservation, while several major screens retain native HGSS
geometry. The sandbox world proves the production pipeline and visual
vocabulary; it is sparse and is not a finished route. The generated landmark
is recognizable but heavily faceted. Those are the principal questions for
the final human review rather than hidden technical failures.

## Determinism and safety

Static showcase compilation is byte-deterministic. The two environment display
lists remain within their inherited/project capacities: 2,124/2,496 bytes for
the rural module and 4,092/4,096 bytes for the generated landmark. The ignored
showcase ROM, save, logs, traces, and screenshots are not tracked. No Stage 4
budget or Stage 5 gameplay invariant was weakened.

The normal non-proof build succeeds at SHA-256
`b6d5243ee553a63134fbb957a80ddbded98b35d3cfa9dd558ce461ee17b6c278`.
Focused Stage 4/5/6 tests pass, preflight passes 58/58 grouped checks, and the
Stage 4A basic-world runtime smoke passes 9/9 assertions against ROM SHA-256
`9cdd6cd9c599580b0b8fb00515fb2bc7c5c381c2bfde7f7d33af82fbbd0f0c42`.

DeepSeek was not used. DeepSeek cost: `$0`.

## Human gate

Stage 6L now pauses at `HUMAN_REVIEW_REQUIRED`. Any feedback becomes a tracked
presentation issue, is applied to canonical high-level source, and receives
affected QA plus the integrated smoke before the candidate is shown again.
