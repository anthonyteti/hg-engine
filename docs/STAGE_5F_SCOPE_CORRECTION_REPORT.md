# Stage 5F-S Technical Report — Final Roster Scope Correction

## Verdict

`STAGE_5F_SCOPE_CORRECTION_PASSED`

`FULL_1025_BASE_ROSTER_PRODUCTION_READY`

`FULL_MEGA_SCOPE_CLASSIFIED`

`STAGE_5_FOUNDATION_FINALIZED_WITH_NONBLOCKING_CONTENT_DEBT`

Stage 5F-S corrects the stale #1–905 production boundary to all 1,025
implemented base species through Pecharunt. The correction preserves the
historical Stage 5A–F evidence, separates full-game support from a later
curated approximately 300–350-species main-story pool, and starts no Stage 6
implementation.

## Checkpoint and scope boundary

The completed Stage 5F work was reviewed, explicitly staged, committed, and
pushed as `95f31e781727a07d0a82064bb1d5fa4067adbbb9`
(`Add Stage 5F roster production readiness`). The correction uses the ordered
`sPokedexSort_NationalNum` table, not raw species IDs; HG-Engine's reserved
494–543 internal slots make ID arithmetic an invalid National Dex mapping.

Authoritative policy is now:

```text
engine/full-game support:  National Dex #1–1025
main-story encounter pool: approximately 300–350, selected later
postgame/completion:        all 1,025 bases ultimately obtainable
Gigantamax:                 out of scope
Mega Evolution:             in scope
```

No wild or trainer table was bulk-expanded by this scope correction.

## Deterministic production readiness

Two clean generations were byte-identical. The corrected report contains 1,475
identities: 1,025 bases, 400 form identities, and 50 reserved HGSS identities.
The canonical JSON SHA-256 is
`e5ff4033722f5a5484b2df253e444b5575819d6dc805f4977f5d5d1a637a8606`.
Historical audit labels remain 560 `COMPLETE`, 859 `PARTIAL`, two `DATA_ONLY`,
two `ASSET_ONLY`, two `UNKNOWN`, and 50 `NOT_IMPLEMENTED`.

Semantic readiness is:

| Readiness | Count |
|---|---:|
| READY | 1,177 |
| ARCHITECTURALLY_COVERED_UNEXECUTED | 212 |
| OUT_OF_SCOPE_FOR_GAME | 34 |
| RESERVED_PLACEHOLDER | 52 |
| REQUIRED_FUNCTIONAL_GAP | 0 |
| REQUIRED_CONTENT_GAP | 0 |
| EXTERNAL_CONTENT_BLOCKED | 0 |

All 1,025 required bases are `READY`; functional gaps, content gaps, and cry
runtime gaps are zero. Generation coverage is 151/100/135/107/156/72/88/96/
120 in scope for Generations 1–9 respectively. The 120 Generation 9 bases have
zero functional, Dex-content, cry-runtime, or other required gaps.

## Pecharunt boundary

The canonical source maps `SPECIES_PECHARUNT` to internal engine ID 1075 and
National Dex #1025. A Stage 5F-S-only runtime fixture marks that existing
identity seen/caught through normal Dex APIs and navigates the ordinary
National Dex UI. It validates the upper mapping and presentation boundary; it
does not seed normal gameplay or add species content.

Runtime screenshot, plan, assertion, and ROM hashes are recorded in the final
Stage 5F-S handoff. The proof passed 6/6 assertions with plan SHA-256
`6cf38445e7993475de303a91578bbb38b1c06a4f094c3e71846f18d532a82c85`,
ROM SHA-256
`7e83a02d155c46b66ae452f1abb9c300b7265f50d587e2406138fd8027e2f54b`,
and screenshot SHA-256
`f21035522345a2c540218c8b29dedce31a477895877683f8e0c36817a62de121`.
Visual inspection confirmed #1025 Pecharunt, its sprite, Subjugation category,
project description, Poison/Ghost typing, measurements, and caught marker with
no index or text corruption.

## Cry truth

All 1,025 bases have safe runtime routes. Provenance remains deliberately
separate:

| Classification | Count |
|---|---:|
| AUTHENTIC_PROVENANCE_VERIFIED | 493 |
| ROUTED_SOURCE_PRESENT_UNVERIFIED | 532 |
| KNOWN_PLACEHOLDER | 0 |
| FALLBACK | 0 |
| MISSING | 0 |

The 532 expanded routes are nonblocking authenticity debt, not hidden runtime
gaps.

## Regional and special forms

All 55 regional persistent forms remain in scope and pass their static data,
mapping, battle asset, icon, follower, and storage contract. The count is
unchanged because Stage 5F already enumerated every current-fork regional form;
Stage 5D remains representative runtime evidence.

Gigantamax remains explicitly excluded (34 identities). The two Alcremie
fillers remain reserved. Other temporary, cosmetic, battle-state, size,
weather, item, Totem/large, Lord, and special forms retain family-specific
requirements rather than being mistaken for independently obtainable bases.

## Complete Mega reconciliation

The corrected scope includes all 97 current-fork Mega identities. The audit now
resolves every identity through exact base species, source form, target form,
item or move trigger, Mega-stone classification, adjusted identity, personal
data/assets, and `NEEDS_REVERSION` semantics.

Repository evidence exposed bounded source-table defects: Heatran and Darkrai
had form records and stones but no runtime trigger; female Meowstic, Original
Color Magearna, and Droopy/Stretchy Tatsugiri needed source-form-specific rows;
and the Magearna and Tatsugiri base rows targeted non-Mega forms. The table now
matches exact source forms. All 97 are `IN_SCOPE_READY`, with zero required
identity gaps.

`SPECIES_MEGA_TATSUGIRI_STRETCHY` and `SPECIES_MEGA_BAXCALIBUR` retain their
historical Stage 5A `ASSET_ONLY` label, but their complete source-backed
temporary-form contracts make their production readiness `READY`. No species
data, stats, typing, abilities, stones, or art were invented or downloaded.

There are 92 distinct item triggers across the 97 identities (plus Mega
Rayquaza's move trigger). The existing general-item pocket reserves 48 extra
slots for Mega items. Expanding that reserve to the complete stone count
overflowed the engine's byte-sized pocket-count interface during the initial
validation build, so it was not shipped: individual stones remain classified
and usable, while simultaneous full ordinary-item-plus-stone collection is
documented as nonblocking capacity debt rather than hidden behind a roster
pass.

## Isolation, validation, and closure

The Pecharunt observer is compiled only with `STAGE5FS_SCOPE_PROOF`; ordinary
builds do not seed Dex state or include scope-proof observations. The production
Mega table fixes are shared engine corrections and therefore receive focused
Stage 5E and battle regression coverage in addition to inventory/readiness,
Stage 5B–D, normal-build, Stage 4A, and preflight validation.

Stage 6 remains the already-approved Presentation Factory (6A–6L); no Stage 6
code or orchestration state was created in Stage 5F-S.

Validation completed as follows:

- canonical Dex archive comparison: 1,025/1,025 bases, zero mismatches;
- focused Stage 5A–F static/runtime tests: 62/62;
- Stage 5E live Mega regression: 85/85 assertions, including reversion and
  persistence;
- known-good Color Change battle: 1/1;
- complete Python suite: 380 tests passed, three environment-gated skips;
- clean normal ROM SHA-256:
  `eab6f22023020ebd4e0a6844ead42169dd8539b18b4a42393aec7a083de75ace`,
  with no Stage 5 proof symbols;
- Stage 4A basic-world smoke: 9/9 assertions;
- preflight: 58/58 checks across commands, Python, system, ROM, Git hygiene,
  and Docker context.

The Stage 5E regression exposed a timing race in its opt-in move observer: the
retail overlay advanced the command/client state before the observation. The
observer now brackets the overlay and filters on Mega Altaria; native Mega
behavior remains unchanged and the complete scenario passed.

DeepSeek was not used. Cost: $0.
