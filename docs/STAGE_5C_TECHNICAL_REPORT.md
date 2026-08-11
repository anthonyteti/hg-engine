# Stage 5C Technical Report: expanded level-evolution runtime

## Verdict

```text
STAGE_5C_EXPANDED_EVOLUTION_PASSED
EXPANDED_LEVEL_EVOLUTION_RUNTIME_PROVEN
EVOLUTION_POKEMON_IDENTITY_PRESERVED
EVOLVED_SPECIES_PERSISTENCE_PROVEN
```

Stage 5C executes the existing Popplio -> Brionne -> Primarina line through
ordinary Rare Candy use, HG-Engine's normal level-up evolution checks, the
retail evolution presentation, and ordinary battery saves. It adds no species,
evolution, learnset, form, sprite, icon, follower, cry, or Dex content.

## Checkpoint and isolation

Stage 5B-C was committed and pushed at
`afea033480ea2d510dc17218fe1cd92caf3b08ab` (`Complete Stage 5B expanded
species runtime proof`). Local `HEAD`, `origin/main`, and remote main agreed,
and the worktree was clean before Stage 5C began.

`STAGE5C_EVOLUTION_PROOF=Y` is the sole enablement boundary. It reuses the
proven map-540 Stage 5B world and ordinary save NPC. The normal build contains
no seeded Popplio, Rare Candy grant, observation state, or Stage 5C commands.
The proof fixture is `fixtures/stage5c_evolution_runtime.json`; the declarative
runtime plan is `qa/scenarios/stage5c_evolution_runtime.json`.

The proof initializer uses three proof-only persistent save variables
(`0x416D..0x416F`). An early diagnostic version incorrectly used HGSS temporary
variables `0x4010..0x4012`; the ordinary menu/evolution scripts legitimately
overwrote them. No production save layout or normal-build semantics changed.

## Authoritative source contract

The current fork defines:

| Species | Engine ID | Evolution source |
|---|---:|---|
| Popplio | 778 | `EVO_LEVEL`, parameter 17, target Brionne |
| Brionne | 779 | `EVO_LEVEL`, parameter 34, target Primarina |
| Primarina | 780 | no further base-form evolution |

The definitions are in `data/Evolutions.c`; identities are in
`include/constants/species.h`. `EVO_LEVEL` is method 4 and the observed runtime
context is `EVOCTX_LEVELUP` (0) for both triggers.

Relevant source learnset boundaries are Popplio Icy Wind at 15 and Sing at 18;
Brionne Sing at 20, Bubble Beam at 25, Encore at 30, and Misty Terrain at 35;
and Primarina's level-zero Sparkling Aria. The proof deterministically declines
new moves through the ordinary prompt, so the original moves remain Disarming
Voice (577), Aqua Jet (453), Baby-Doll Eyes (611), and Icy Wind (196). No
learnset is edited or suppressed.

## One continuous Pokémon identity

The initializer creates exactly one level-16 base-form Popplio with PID
`0x050C0001` (84672513), OT ID `0x050C0A11`, and all IVs 31. That same party
record is mutated by `SetPartyPokemonParamsForEvoCutscene`; the proof hook only
observes the normal evolution check and species mutation boundaries.

Stable fields include PID, OT, form 0, IV word `0x3FFFFFFF`, friendship, held
item, ball, gender, party slot, and the four retained moves. The runtime module
does not call `SetMonData`, `GetMonEvolution`, or the evolution cutscene setter.
It never directly writes a level or evolved species.

## Ordinary triggers and results

The Bag is opened normally and the Medicine pocket is selected through its
normal touch tab. Every level from 16 through 34 is gained with ordinary Rare
Candy item use. Proof-only checkpoints observe the existing Rare Candy reuse
boundary; they do not advance it. The first two assertions establish the
negative boundary: Popplio remains Popplio at level 16 before the trigger.

Observed calculated states were:

| State | Level / EXP | HP / Atk / Def / Spe / SpA / SpD | Types | Ability |
|---|---|---|---|---|
| Popplio | 16 / 2535 | 46 / 27 / 27 / 24 / 27 / 27 | Water / Water | Torrent (67) |
| Brionne | 17 / 3120 | 52 / 33 / 33 / 29 / 36 / 37 | Water / Water | Torrent (67) |
| Primarina | 34 / 33084 | 108 / 65 / 65 / 61 / 90 / 94 | Water / Fairy | Torrent (67) |

At level 17, the normal evolution scene changed 778 -> 779. At level 34, it
changed 779 -> 780. Each transition recorded method 4/context 0, preserved PID
84672513 and form 0, recalculated stats, and retained the same party slot.
Primarina's Sparkling Aria prompt was exercised and declined normally; the
proof did not consume an unintended level-35 Candy.

## Presentation and persistence

After the first transition, the actual party UI selected Brionne's icon and
the follower resolver returned species 779 / sprite tag 3279. After the second,
the party UI selected Primarina and the follower resolver returned species 780
/ sprite tag 3280. Primarina followed for an ordinary eastward tile. These are
identity-refresh checks, not repetitions of the complete Victini matrix.

Three ordinary battery-save checkpoints execute through hard reset, title,
and Continue:

1. party Brionne at level 17;
2. party Primarina at level 34;
3. boxed Primarina at level 34 after ordinary PC-storage placement.

The first two restore the same PID, species, form, level, EXP, and moves. The
final box check restores species 780, form 0, PID 84672513, EXP 33084, and the
same moves in the same recorded box slot. No savestate is used.

Evolution caused the ordinary seen/caught state observed by this fork for both
Brionne and Primarina. The plan records those actual effects rather than
calling Dex setters or assuming mainline-game behavior.

## Determinism and evidence

The tracked plan is deterministic and contains no raw addresses. It writes
only the exported command word; all Pokémon state is read semantically.
Generated ROMs, battery saves, traces, reports, and screenshots remain ignored.
Representative captures cover Popplio/Brionne/Primarina icons, both evolution
scenes, both evolved followers, party persistence, and final box persistence.
Visual evidence supplements the exact semantic assertions.

Two complete executions from the same tracked inputs produced the same
347-step plan SHA-256
`de6addc58fe9065adf821df4172a0c2cdfcef7ddab8ae96700605e0658ef190f`,
the same proof-ROM SHA-256
`ce6adafd70dcae417ed5a64a5c3f6ce4a475b7d570149090aacd0cbb8554a741`,
the same 167/167 semantic assertions, the same final map/position/frame, and
the same canonical screenshot hashes. The representative screenshot hashes
are:

| Capture | SHA-256 |
|---|---|
| Popplio party icon | `d33c8d93189fa3dc508fd20286030973cb69431e0cda6ecd302accb98d3dd162` |
| Popplio -> Brionne | `b2d93a498762d8b8d78add6821e9086a61802ddda61ca1cbb1aa0dd6766dc45b` |
| Brionne party icon | `1446e49b0a99f02662baab4d541e1abb79681ed8ce688a265a52c0fe98540d0c` |
| Brionne follower | `b5e942bea5b11bc139d83b5891c84dfd7e634372fb5d7d81515ca720af5d7232` |
| Brionne after Continue | `9ab1199cc34b4967cd5e96462c790d49c87db1e8226474b37085fd4e91be6970` |
| Brionne -> Primarina | `b82dbb548e2226a6663ec3d504fde264749de0511fa4f2bc90955a51e7beb1bc` |
| Primarina party icon | `84a0130a914bd16d8ac186630d3c57489db674e39cb3199b6b1ae283a2637bbb` |
| Primarina follower | `b15d59c618936bfd78819c9f6997ba0f3d26331612efc06671c44f54d4ae26a8` |
| Primarina after Continue | `51ed786bb996ed2719dcd8740c06ce3b2cd158422446bbe7629a5de2888dc712` |
| Boxed Primarina after Continue | `1f00d8df806b3e1262f0f0d1cdf14ff469ed9bc600152207649c7c196102e85d` |

Visual inspection confirmed correct evolution targets, refreshed icons, and
Brionne/Primarina follower graphics without a stale Popplio presentation.

The normal non-proof ROM built from a clean tree with SHA-256
`2175928b5dc73640739ec625c17e7f300937f2a89941a8ed9077840957ca1013`;
linked-symbol and ROM-string inspection found no Stage 5C proof symbols. The
unchanged Stage 4A basic-world and persistence controls passed 9/9 and 19/19
assertions. Fifty-five focused QA/Stage 5A/5B/5C tests and preflight passed.
The filtered Stage 5B battle smoke exposed a reversed message expectation in
the Stage 5B-C checkpoint; restoring the original observed Incinerate-then-
Focus-Energy order made the real one-test battle run pass and added an order
regression assertion. No battle or species behavior changed.

The inventory now records one representative evolution line as
`REPRESENTATIVE_PROVEN` and annotates only Popplio, Brionne, and Primarina with
`representative_evolution_status: COMPLETE_EXECUTED`. Their top-level status
remains `PARTIAL`; missing expanded Dex text and cry-authenticity evidence are
independent content gaps.

## Remaining boundary

This proves one ordinary two-step, base-form, level-triggered line. It does not
prove trade, item, friendship, time, move-known, location, party-composition,
gender, regional-form, split, or form-changing evolutions. It does not prove
regional forms or Mega Evolution. The next bounded Stage 5 task should test an
expanded evolution method outside plain level thresholds, before forms or
Megas are inferred.
