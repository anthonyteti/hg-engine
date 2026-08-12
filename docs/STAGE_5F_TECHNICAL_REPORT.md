# Stage 5F Technical Report — Roster / Content Gap Closure

> Historical scope note (Stage 5F-S, 2026-08-11): this report records the
> originally executed Stage 5F decision under the then-current #1-905 project
> scope. That scope was subsequently corrected to all 1,025 implemented base
> species. The additive correction, regenerated counts, Pecharunt boundary
> proof, and complete Mega reconciliation are recorded in
> `docs/STAGE_5F_SCOPE_CORRECTION_REPORT.md`. The original measurements below
> are retained rather than rewritten as if the earlier scope had never existed.

## Verdict

`STAGE_5F_ROSTER_CONTENT_CLOSURE_PASSED`

`BASE_ROSTER_PRODUCTION_READY`

`EXPANDED_DEX_CONTENT_READY`

`CRY_RUNTIME_READY_AUTHENTICITY_CLASSIFIED`

`FORM_SCOPE_AND_READINESS_CLASSIFIED`

`STAGE_5_FOUNDATION_COMPLETE_WITH_NONBLOCKING_CONTENT_DEBT`

Stage 5F found no required roster/runtime gap for the game's declared National
Dex #905 scope. It preserves the Stage 5A flat audit statuses and adds a
separate semantic production-readiness model. The remaining debt is source
authenticity for expanded cry WAVs, optional/out-of-scope special forms, and
architecturally covered special-form cases that the current game has not
selected as production content.

## Stage 5E checkpoint

Stage 5E was intentionally uncommitted at entry. Its 25 intentional paths were
reviewed and committed as `2c7a53fe91302dc45505808cc2366b8998142b13`
(`Add Stage 5E Mega Evolution runtime proof`). Local `HEAD`, `origin/main`, and
remote `refs/heads/main` all resolved to that hash before Stage 5F began. No
ROM, save, screenshot, trace, cache, or extracted retail artifact was staged.

## Deterministic inventory baseline

Two clean regenerations from the Stage 5E checkpoint were byte-identical. The
pre-Stage-5F report SHA-256 was
`178c1d665e6923bc2d9aa37a4680ce7010cb435ff9f6a997c308774b11686e9c`.
It contained 1,475 identities: 1,025 implemented bases, 400 forms, and 50
reserved HGSS IDs. Historical audit status remained:

| Audit status | Count |
|---|---:|
| COMPLETE | 560 |
| PARTIAL | 859 |
| DATA_ONLY | 2 |
| ASSET_ONLY | 2 |
| UNKNOWN | 2 |
| NOT_IMPLEMENTED | 50 |

Those labels are not overwritten. The new `production` object beside every
record carries scope, family, readiness, required/optional/not-applicable
capabilities, reason codes, content truth, and representative shared-runtime
evidence.

Two clean final generations also matched the tracked canonical inventory
byte-for-byte. Its Stage 5F SHA-256 is
`1651bd5fbaf81e5b4e14793fe7da6e6727d89bd6b40d241cfc4888148acb4fb5`.

## Production scope and base-roster result

`01_PROJECT_SPEC.md` selects National Dex #1-905, relevant persistent regional
forms, and Mega Evolution, and excludes Dynamax/Gigantamax. Because IDs 494-543
are reserved in the engine's internal numbering, production scope is resolved
from `sPokedexSort_NationalNum`, not by comparing raw species IDs. The selected
base roster therefore contains the intended 905 implemented identities. Every
one of those 905 has required species/learnset/evolution data,
front/back/palette/icon resources, follower mapping/properties, safe cry
routing, Dex number/name/sprite/seen-caught support, and storage/trainer/wild
capabilities under the representative Stages 5B-E runtime evidence.

| Gen | Implemented bases | In scope | Functional gaps | Dex gaps | Cry runtime gaps | Cry authenticity unverified |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 151 | 151 | 0 | 0 | 0 | 0 |
| 2 | 100 | 100 | 0 | 0 | 0 | 0 |
| 3 | 135 | 135 | 0 | 0 | 0 | 0 |
| 4 | 107 | 107 | 0 | 0 | 0 | 0 |
| 5 | 156 | 156 | 0 | 0 | 0 | 156 |
| 6 | 72 | 72 | 0 | 0 | 0 | 72 |
| 7 | 88 | 88 | 0 | 0 | 0 | 88 |
| 8 | 96 | 96 | 0 | 0 | 0 | 96 |
| 9 | 120 | 0 | 0 | 0 | 0 | 120 |

National Dex #906-1025 remains usable engine capability, and the UI proof
includes Gen 9 as a scalability check, but those records are not silently
added to the game's #905 production scope.

## Dex architecture and corrected gap finding

The Stage 5A `pokedex_category`/`pokedex_description` booleans were a
conservative `id <= 493` heuristic. They did not inspect the real content
source. Source inspection established this live path:

```text
data/Species.c classification + pokedexEntry
  -> tools/source/speciesdatagen/species_data_gen.c
  -> build/rawtext/803.txt (description)
  -> build/rawtext/816.txt and 823.txt (category)
  -> message compiler / build/narc/msg_data.narc
  -> expanded National Dex UI
```

All 1,025 implemented base records already have nonempty category and
description content. No 532-entry text batch was generated or copied because
the supposed missing set did not exist. The existing canonical fork content
was retained and a project-owned manifest now declares its generator/archive
contract. Stage 5F validates uniqueness by species identity, UTF-8 decoding,
nonempty category/description, no NULs, and exact identity-indexed equality
between `Species.c` and all three generated raw-text members.

The generated members contain 1,476 identity rows each and passed 1,025 base
comparisons with zero mismatches. Their SHA-256 values are:

- descriptions/803: `6d3f695e0d17e10ff7e5f5f05ce7fd094b771a6cb8dd8739450bde4ca9c9c035`;
- categories/816: `a7d2dd9a3fbf4bb395cfd18497694767db1d932d8d760a2891affc856d8a3ebe`;
- categories/823: `a7d2dd9a3fbf4bb395cfd18497694767db1d932d8d760a2891affc856d8a3ebe`.

The maximum decoded category is 21 characters. Descriptions are at most 177
characters and three explicit lines; the runtime representative matrix is the
authoritative overflow/rendering check for expanded content.

## Representative Dex UI evidence

The opt-in `STAGE5F_DEX_PROOF` fixture uses ordinary save APIs to enable the
National Dex and mark five representatives seen/caught. It does not add or
modify a species or text record. Five ordinary UI scenarios rendered:

| Generation | Representative | National number | Category | Result |
|---:|---|---:|---|---|
| 5 | Victini | 494 | Victory Pokémon | PASS |
| 6 | Chespin | 650 | Spiny Nut Pokémon | PASS |
| 7 | Rowlet | 722 | Grass Quill Pokémon | PASS |
| 8 | Grookey | 810 | Chimp Pokémon | PASS |
| 9 | Sprigatito | 906 | Grass Cat Pokémon | PASS |

Each view showed the correct number, name, sprite, category, description,
types, measurements, and caught marker without overflow or corruption. The
tracked plans assert the exact internal representative ID and live seen/caught
bits before navigating the normal National Dex grid. Screenshots and reports
remain ignored evidence under `build/qa/`.

| Gen | Scenario plan SHA-256 | Screenshot SHA-256 | Assertions |
|---:|---|---|---:|
| 5 | `7f0a0f738492963d79a11f1153d1d426edce3df9e63c387e4e248892d2bb0c1f` | `505a9cb5048c762164ae7f066da3c258ed65b5f0f88bc2cf9b4b8f2f3e6292bd` | 9/9 |
| 6 | `da3d3a4a7dc4493c10f520a63f7fa5e019c78facdcb31db829f87973d5a4c41a` | `5f4f527a901f9503ae2570d352db2ae5dfd348cc93e21c1022353fbd81addb5b` | 6/6 |
| 7 | `33de81bc676ae8c3d69fa288fb12d9be5d1a8abace4dd0c6b09d828585db964c` | `d36ae025d2e1f70207493a6ebdd3a1ed1a2025efb67f262758afbc6cd8bb7b51` | 6/6 |
| 8 | `421cbdb004bf42acc80c51c42b04e8608901448935fc9c47f0634ca9180bb89f` | `140fb27c76af41f639e34267ea0594676b3e3b4b73777f454b3b8ed6b017345d` | 6/6 |
| 9 | `f3310099a768cc1741dba8cdec8f848845365f2d3e87a02fe3ffbdc62b9a4feb` | `d340fe27327e7ecdfa00eebae7b68cb9f6dd940bbdb6c03f5ad9a25c992554b9` | 6/6 |

All five used proof ROM SHA-256
`68e8d3368f0b7a1eef9eb03f4fa71ae255c1a3ecd52b298b193557f008603c21`.

## Cry truth audit

The current architecture routes #1-493 to retail cry banks from the
user-supplied base ROM. Expanded bases route through
`CRY_PSEUDOBANK_START=778` and the source WAV/SWAR build. Results for all 1,025
implemented bases:

| Classification | Count |
|---|---:|
| AUTHENTIC_PROVENANCE_VERIFIED | 493 |
| ROUTED_SOURCE_PRESENT_UNVERIFIED | 532 |
| KNOWN_PLACEHOLDER | 0 |
| FALLBACK | 0 |
| MISSING | 0 |

All 905 required bases have a safe route. Repository credits establish source
attribution for later WAV batches but do not prove every file canon-authentic,
so Stage 5F does not promote them beyond routed/present/unverified. Forms
inherit their mapped base route and are not counted as independent cries.

## Form-family readiness

All 400 forms are assigned exactly one semantic family. Counts are:

| Family | Count |
|---|---:|
| REGIONAL_PERSISTENT | 55 |
| MEGA_TEMPORARY | 97 |
| GIGANTAMAX_OUT_OF_SCOPE | 34 |
| BATTLE_MODE_FORM | 25 |
| COSMETIC_FORM | 38 |
| SIZE_SPECIAL_FORM | 5 |
| TOTEM_OR_LARGE | 14 |
| LORD | 5 |
| ITEM_DRIVE_FORM | 5 |
| WEATHER_OR_STATE_FORM | 4 |
| FILLER_OR_RESERVED | 2 |
| OTHER | 116 |

All 55 scoped regional forms pass the static persistent-form contract: data,
form mapping, battle assets, icon, follower mapping/properties, and storage
capabilities. Stage 5D supplies representative runtime evidence. All 49
current-scope Mega identities pass the temporary battle-form contract; Mega
Rayquaza's move trigger is distinguished from the item table. Stage 5E supplies
activation/reversion evidence. The later Legends: Z-A Mega identity block
remains outside the current through-Legends:-Arceus content boundary rather
than receiving invented production mechanics.

Trainer data stores the packed `u16` species/form identity. The independent
trainer constructor in `src/field/enemy_party.c` decodes bits 11-15, creates
the base species, writes `MON_DATA_FORM`, and resolves the adjusted identity
through `PokeOtherFormMonsNoGet`. This is classified
`ARCHITECTURALLY_COVERED_UNEXECUTED`; the already-executed Stage 5D wild path
proves the corresponding persistent form result. No new trainer runtime matrix
was justified.

## Exceptional identities

| Identity | Historical status | Semantic decision |
|---|---|---|
| GMAX Toxtricity Low Key | DATA_ONLY | preserve engine record; Gigantamax is out of game scope |
| GMAX Urshifu Rapid Strike | DATA_ONLY | preserve engine record; Gigantamax is out of game scope |
| Mega Tatsugiri Stretchy | ASSET_ONLY | later source block and post-#905 base; preserve source-backed record, out of current scope |
| Mega Baxcalibur | ASSET_ONLY | later source block and post-#905 base; preserve source-backed record, out of current scope |
| Alcremie Filler 1 | UNKNOWN | structural filler; reserved/not applicable |
| Alcremie Filler 2 | UNKNOWN | structural filler; reserved/not applicable |

No stats, items, mappings, Dex identities, follower records, or gameplay uses
were fabricated to make these historical labels green.

## Production-readiness totals

Across all 1,475 identities the semantic result is:

| Readiness | Count |
|---|---:|
| READY | 1,009 |
| ARCHITECTURALLY_COVERED_UNEXECUTED | 178 |
| OUT_OF_SCOPE_FOR_GAME | 236 |
| RESERVED_PLACEHOLDER | 52 |
| REQUIRED_FUNCTIONAL_GAP | 0 |
| REQUIRED_CONTENT_GAP | 0 |
| EXTERNAL_CONTENT_BLOCKED | 0 |

`READY` is the 905 required bases plus 55 persistent regional forms and 49
scoped Megas. The 178 other in-scope-engine special forms have complete static
form contracts but are not individually executed or selected as required game
content. This is not concealed as per-species runtime proof.

## Isolation, regressions, and Stage 6 boundary

Normal builds do not compile `stage5f_runtime.c`, seed proof Pokémon, set proof
Dex state, or install Stage 5F symbols/content. Stage 5F adds no production
Pokémon behavior. A clean ordinary `make -j2` passed with ROM SHA-256
`2175928b5dc73640739ec625c17e7f300937f2a89941a8ed9077840957ca1013`;
the linked image and ROM contained no Stage 5F proof symbols.

The complete Python suite passed 380 tests with three documented
environment-gated skips. The focused Stage 5A-F and QA selection passed 79
tests; after the final National-Dex-versus-engine-ID scope correction, all 23
directly affected Stage 5A/5F tests were rerun and passed. A known-good Color
Change battle passed 1/1 through the real battle
runner and locally provisioned ignored battery save. `stage4a_basic_world`
then passed 9/9 semantic assertions, including movement, capture, and 600 stable
frames, using plan SHA-256
`541202f17b5b40443ad83783ef925ff317859889eefc20edebcab346491f1f26`;
its ROM SHA-256 was
`eb9c6252be532639d4e313bb640a3b517e2c25eb6832a9e17a765d736879e8b3`
and screenshot SHA-256 was
`2498b52c30d5e82726dc5ea3eb220a84fa555d19338de8056dd6c2996549a04d`.
Project preflight passed all 58 checks. Generated ROMs, saves, screenshots,
logs, reports, and build products remain ignored and untracked.

Roadmap, architecture, and decisions now define Stage 6 as the Presentation
Factory: 6A visual bible, 6B UI reality audit, 6C UI resource factory, 6D
declarative UI engine, 6E battle UI, 6F core menus, 6G remaining UI, 6H UI QA,
6I environment kit, 6J variants/catalog, 6K real generated-landmark kill gate,
and 6L integrated presentation QA. It requires persistent autonomous state,
automatic technical checkpoints/recovery, explicit per-substage gates, and
only sparse human creative gates. Stage 6 implementation was not started.

DeepSeek was not used; cost was $0.
