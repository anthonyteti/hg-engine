# Stage 5B Technical Report: Victini expanded-species runtime proof

## Verdict

```text
STAGE_5B_EXPANDED_SPECIES_RUNTIME_PARTIAL
EXPANDED_BASE_SPECIES_RUNTIME_PARTIAL
EXPANDED_FOLLOWER_RUNTIME_PARTIAL
EXPANDED_SPECIES_STORAGE_PARTIAL
```

Victini resolves through real party, personal-data, moveset, Dex-bit,
follower-lookup, follower-render, and PC-storage code in a live proof ROM. The
full requested matrix is not proven: the established controlled-entry route
became unavailable for both the Stage 5B and unchanged Stage 4A persistence
scenarios, and the repository battle runner cannot start without its ignored
`test.sav` fixture. Trainer/wild construction, battle front/back presentation,
PC UI/icon, capture, hard-reset/Continue, and cry playback therefore remain
unresolved rather than inferred from compiled source.

## Stage 5A checkpoint

Stage 5A is committed and pushed at
`2dd676e4a1389bd126f76778d21da899c0eb1a30` (`Add Stage 5A HG-Engine roster
audit`). Local `HEAD`, `origin/main`, and the remote main ref agreed and the
worktree was clean before Stage 5B began.

## Test-only architecture

`STAGE5B_RUNTIME_PROOF=Y` is an opt-in build flag. It compiles a bounded field
hook that seeds one ordinary `PartyPokemon`, exposes semantic proof state, and
uses existing APIs for party, Dex, follower, and PC operations. A normal build
does not compile or call this hook. The QA scenario addresses the exported
semantic state symbol; revision-specific addresses remain in the emulator
adapter.

The proof does not add a species, move, sprite, icon, cry, trainer, encounter,
or follower asset. The battle-test fixture places existing Victini data on
both sides of the existing test battle engine and compiles into
`BattleTests.bin`.

## Victini source contract

| Field | Expected/live value |
|---|---:|
| Engine species ID | 544 |
| Level | 20 |
| Form | 0 |
| Base stats | 100 / 100 / 100 / 100 / 100 / 100 |
| Types | Psychic (14) / Fire (10) |
| Ability | Victory Star (162) |
| Moves | Confusion 93; Focus Energy 116; Work Up 529; Incinerate 513 |
| Proof HP | 37 / 76 |
| Proof other stats | 51 each |
| Evolution | not applicable |
| Follower sprite tag | 3044 |

The live semantic state matched species, level, form, four moves, HP, all six
calculated stats, ability, and types. Victini was created with the ordinary
`PokeParaSet`, `InitBoxMonMoveset`, stat recalculation, and party-add path.

## Runtime evidence obtained

- The controlled proof reached map 540 and passed the initial 21/21 exact
  Victini state assertions.
- `SetPokemonSee` and `SetPokemonGet` executed live; owned-Dex count changed
  from the fixture baseline of 8 to 9.
- The follower resolver returned tag 3044. Two live captures show the Victini
  overworld graphic stationary and after one field movement. Screenshot hashes
  are `2498b52c...a04d` and `b3524213...b55e`.
- Ordinary PC storage placed Victini in a real box slot, removed it from party,
  and preserved species 544, level 20, form 0, and all four moves in the box
  representation.
- The two-sided Victini battle fixture compiled successfully. The headless
  runner stopped before emulation because local `test.sav` is absent, a
  limitation already recorded in `docs/AUTOMATION_AUDIT.md`.

## Unresolved runtime matrix

The complete deposit/save/reset/Continue/withdraw sequence was not accepted.
After partial live runs, both Stage 5B and the unchanged
`stage4a_world_persistence` scenario failed at controlled entry with no loaded
field location. This makes the failure attributable to the shared execution
route rather than evidence of a Victini serialization defect, but it still
prevents a storage pass.

No authoritative runtime assertion or screenshot was obtained for:

- party/box icon UI;
- player back and opponent front battle sprite presentation;
- compiled trainer-table runtime loading;
- wild encounter and ordinary capture construction;
- Dex caught state specifically resulting from capture;
- follower persistence across a map transition;
- battery-save party or box persistence through hard reset and Continue;
- Victini cry playback routing.

The battle, trainer, wild, icon, cry, and save-width source evidence from Stage
5A remains valid, but source evidence is not relabeled as Stage 5B runtime
proof.

## Validation

- Stage 5B proof ROM: built successfully.
- Victini battle test: generated and compiled successfully.
- Battle execution: blocked before test start by missing ignored `test.sav`.
- Focused unit suite: 28/28 passed.
- QA scenario schema and deterministic plan: passed.
- Live Stage 5B partial assertions and screenshots: passed as listed above.
- Full Stage 5B QA: not passed.
- Unchanged Stage 4A persistence control: same controlled-entry failure.
- DeepSeek: not used; cost $0.

## Inventory interpretation and next scope

`docs/data/hgengine_roster_inventory.json` changes only the selected
representative's runtime annotation from `NOT_EXECUTED` to
`PARTIAL_EXECUTED`, with the four proven shared paths and exact blockers. No
per-species top-level classification changes. This stage provides
representative positive evidence for shared party, personal-data, Dex,
follower, and box paths, but not enough to promote all expanded species or
Victini to runtime-complete.

The next bounded Stage 5 task should restore/provision the documented battle
save fixture and repair the generic controlled-entry execution route, then
rerun this exact matrix without changing Victini. Only after this proof passes
should work proceed to evolution, forms, Mega runtime, or roster normalization.
