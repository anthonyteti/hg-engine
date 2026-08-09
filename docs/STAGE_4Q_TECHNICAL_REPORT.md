# Stage 4Q Technical Report: Bounded Generated Topology

Date: 2026-08-09

Verdict: `STAGE_4Q_GENERATED_TOPOLOGY_PASSED`

Topology classification: `GENERATED_TOPOLOGY_GAP_CLOSED`

Real-candidate readiness: `DERIVED_GENERATED_CANDIDATE_NOT_READY`

## Checkpoint and boundary

Stage 4P was committed and pushed before this work as
`07b5df1f346a44da2ad692f44f1a55ae23b50fce` (`Add Stage 4P attribute
bootstrap`). Local `HEAD`, `origin/main`, and remote `main` agreed and the
worktree was clean.

Stage 4Q proves one exact sanitation rule and one bounded component policy. It
does not weld positions, fill holes, close boundaries, merge components,
delete a small component, repair winding, retriangulate, or remove a merely
small face. The immutable Stage 4H GLB was only inspected.

## Exact sanitation

`tools.pokeagent.mesh_sanitize` decodes source POSITION as float32 and computes
the cross product of `(p1-p0)` and `(p2-p0)`. A face is removable only when the
squared magnitude of that cross product compares exactly equal to `0.0`.
There is no epsilon in the removal decision.

Removed-face records contain primitive, order-independent semantic face ID,
original face index, indices, decoded positions, cross squared, area, and one
of `repeated_index`, `repeated_position`, or `collinear_zero_area`. Surviving
positions and winding are unchanged. Deterministic compaction removes only
positions left unreferenced by the removed faces and records the old/new map.

A fixture whose cross squared is nonzero but below Stage 4O's normal-length
threshold survives. This is the guard that prevents sanitation from becoming
hidden simplification.

## Components and boundaries

The accepted source envelope remains Stage 4O's 8 MiB embedded GLB, 8,192
positions, 16,384 triangles, 49,152 indices, four identity-chain nodes, one
mesh and one primitive. Stage 4Q accepts at most four components.

Component IDs are SHA-256 prefixes over canonical positions and oriented face
signatures, independent of source face/component order. Components are
reduced separately with the unchanged Stage 4O QEM core. Sixteen faces are
reserved per component (bounded by its source capacity); remaining faces are
distributed by source surface area with stable ID tie-breaking. Position
budgets use the same deterministic scheme with a ten-position minimum. No
cross-component edge can enter a collapse queue.

Every component must survive one-to-one. Aggregate component count and
boundary-loop count must remain equal. Open boundaries must be non-branching
cycles. A square-frame fixture proves two legitimate loops on one component;
no loop is filled or bridged.

## Canonical proof

`assets/source/stage4q_generated_multicomponent.glb` is a project-authored
16,412-byte generated-style source with normalized U8 VEC4 `COLOR_0`, 566
positions, 1,089 triangles, two meaningful components, one open loop, and one
separate exact collinear triangle. SHA-256:

`629529520af2246825a25cfd6f779990005198d13e0adae061e910f3cb6afcec`

Stage 4P's explicit discard policy removes only COLOR_0. Exact sanitation
removes the one collinear face and its three now-unreferenced positions. The
result is byte-identical to independent reference
`assets/source/stage4q_sanitized_reference.glb`, SHA-256:

`8a1c21a0d9880645c9c458242a4bf6cff50ac1826f3fca224eddbd79292e63d5`

| Metric | Source valid surface | Final |
|---|---:|---:|
| positions | 563 | 32 |
| triangles | 1,088 | 55 |
| components | 2 | 2 |
| boundary loops | 1 | 1 |
| surface area | 117.109024 | 121.104411 |

Component allocation/result:

| Component | Source faces/positions/area | Target faces/positions | Final faces/positions/area |
|---|---:|---:|---:|
| detached cap | 32 / 18 / 4.311521 | 17 / 13 | 16 / 10 / 4.051590 |
| shrine body | 1,056 / 545 / 112.797502 | 39 / 83 | 39 / 22 / 117.052821 |

Both components retain nonzero projected occupancy. Their minimum silhouette
IoU values are 0.962720 and 0.917434. Aggregate minimum five-view silhouette
IoU is 0.922699; bounds error is zero; maximum geometric error is 0.539520
(0.047176 of source diagonal); surface-area delta is 3.411682%. All are inside
the predeclared 0.04 bounds ratio, 0.08 geometric ratio, 22% area, and 0.84
silhouette limits.

The reduction accepts 531 collapses and rejects 21,462 candidate evaluations
(17,257 batch conflicts, 100 ground constraints, 1,063 boundary constraints,
2,770 excessive face rotations, and 272 topology-link failures). Stable reasons are retained
per component in the generated report. Faces fall
94.945% and positions 94.316%. The reduced GLB is SHA-256
`388e0bcca5472da51f1bae7aa647dfb8d875f9975ac1746dc8413be2595313ed`.

## Stage 4P and Stage 4F integration

The 55-face/32-position geometry is inside Stage 4P's 80-face/256-position
envelope. Stage 4P produces 163 attribute vertices, 135 UV values, 54 unique
normal values, one `generated_surface` identity, and a strict GLB accepted by
unchanged Stage 4F. Canonical SHA-256:

`ef022994ecdd5574940284d992de237236b1ff32313695ae60e942baca77f0f7`

The normal asset encoder projects 55 triangles / 165 emitted vertices to 3,752
bytes, SHA-256
`144f555b4cc98cf20f0d092000463f4eb19d7c52f67f971c14cba74451ef4c11`,
inside Stage 4I's tested 4,096-byte project capacity. `generated_surface` maps
to the existing `stage4d_stone` project texture. Stage 4Q does not build a ROM:
runtime would add no topology evidence beyond the already-proven Stage 4P and
Stage 4I paths and would require a new world/catalog schema solely for this
intermediate proof. Visual acceptance is therefore the deterministic source,
per-component silhouette, bounds, area, and Stage 4F evidence—not emulator
screenshots. Collision remains outside the sanitation/reduction transaction.

## Mutations and determinism

- Reversing all face/component ordering and moving the degenerate face yields
  byte-identical sanitized and reduced GLBs, identical component IDs/budgets,
  and identical final canonical output.
- Translating the detached component changes only its spatial result; the
  body reduction and `[17,39]` face allocation remain stable.
- Scaling the detached component changes allocation from 17/39 to 19/37
  predictably while retaining both components.
- Tightening the total target to 40 fails as
  `geometry_predecimation_target_unreachable`; no component is deleted.
- Two clean output roots match sanitized GLB, reduced GLB, bootstrapped GLB,
  complete report, component plans, and fidelity metrics.
- Canonical processing is about 5.63 seconds with 35,928 KiB maximum resident
  memory on the development host.

## Stage 4H read-only finding

The raw Stage 4H SHA-256 remains
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
Its COLOR_0 is eligible for the proven explicit-discard policy, and its two
components are manifold/open-manifold with non-branching boundaries. With all
faces retained, exact topology inspection finds 96 boundary edges in 24
loops, two components (6 positions/8 faces and 3,354 positions/6,656 faces),
and zero isolated positions.

However, the face previously reported as zero area by Stage 4O is not exact
zero. Its float32-decoded cross-product squared is
`2.6948343349697145e-19`; the cross length is about `5.19e-10`, below Stage
4O's `1e-9` normal-length validity threshold but mathematically nonzero.
Stage 4Q therefore removes zero Stage 4H faces. Stage 4O still rejects the
near-zero face. A derived attempt is not authorized.

This corrects, rather than weakens, the prior evidence: excluding that face
under Stage 4O's tolerant quality inspection produced 99 boundary edges / 25
loops; exact topology with it retained has 96 / 24. Both descriptions are now
labeled by their test semantics.

The historical verdict remains `STAGE_4H_GENERATED_ASSET_REJECTED` /
`REJECTED_UNSUPPORTED_STRUCTURE`; no file, catalog entry, or ROM path changed.

## Tests and regressions

Focused tests cover exact/reference equality, near-zero survival, multiple and
all-zero faces, non-manifold/winding/branching rejection, component limits,
loop preservation, impossible targets, order/translation/scale mutations,
two-root determinism, Q -> O -> P -> Stage 4F, Stage 4I byte eligibility, and
immutable Stage 4H inspection.

The focused suite passes 16/16. The full suite passes 286 tests with three
expected opt-in integration skips. `make stage4q-generated-topology-proof`,
Python compilation, preflight (58/58 grouped checks), and diff/artifact hygiene
are green.

Stage 4O's canonical SHA-256 remains `7550ffe4...3957`; Stage 4P remains
`06b798f8...5e1`; Stage 4J remains 4,024 bytes with display-list SHA-256
`e01fcce1...b04`. Stage 4K/L/M/N canonical hashes and all earlier strict GLB,
OBJ, texture, registry, QA, preflight, and artifact-hygiene gates remain
regression targets.

DeepSeek was not used; token and monetary cost are zero.

## Recommendation

If Stage 4R is authorized, isolate the newly proven real-candidate blocker:
decide whether a representation-aware, very-small-but-nonzero face can ever be
discarded safely before Stage 4O. It must be a separate quantitative policy,
not a reinterpretation of Stage 4Q exact sanitation, and must not process a
derived Stage 4H file without explicit authorization.
