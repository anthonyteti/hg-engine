# Stage 4S Technical Report: Real Generated-Asset Kill Gate

Date: 2026-08-09

Verdict: `STAGE_4S_REAL_GENERATED_ASSET_BLOCKED`

Technical classification: `REAL_GENERATED_ASSET_PIPELINE_UNPROVEN`

Visual classification: `GENERATED_ASSET_VISUAL_UNCERTAIN`

Stage 4 disposition: `STAGE_4_ASSET_INFRASTRUCTURE_HAS_SPECIFIC_BLOCKER`

## Authorization and checkpoint

Stage 4R was committed and pushed before this experiment as
`136ceb45c21a84d8616c7f3ff88172fdd8d413d8` (`Add Stage 4R target-null face
policy`). Local `HEAD`, `origin/main`, and remote `main` agreed, and the
worktree was clean.

Stage 4S was explicitly authorized to create one ignored derived working copy
from the immutable Stage 4H candidate. It did not authorize a generator rerun,
manual mesh editing, policy tuning, topology repair, component deletion, a new
decimator, a larger model budget, or rewriting the raw source. The first
authoritative failing gate ends the transaction.

## Immutable source and provenance

Before processing, the tracked raw file independently matched SHA-256
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
The tracked concept and provenance hashes also matched.

The source is the 134,740-byte GLB produced by `stabilityai/TripoSR`, revision
`f84354eb350eb07a108faf33a6bc564d455f9764`, through its anonymous public
Gradio API with background removal, foreground ratio `0.85`, marching-cubes
resolution `64`, and GLB output. The concept is the project-owned OpenAI image
generation input already documented by Stage 4H.

The raw source remains byte-identical and tracked only under its historical
Stage 4H identity. Stage 4S derived artifacts are ignored build output.

## Thin orchestration and policy

`tools.pokeagent.generated_pipeline` verifies manifest/source/concept/
provenance hashes, invokes existing Stage 4P/Q/R/O functions, records every
gate, and stops closed. It contains no geometry algorithm.

The tracked schema-16 manifest declares fit-inside size `4 x 6 x 4` tiles,
explicit Stage 4P COLOR_0 discard, Stage 4Q exact sanitation, Stage 4R target
quantization, unchanged canonical Stage 4O target `64 faces / 64 positions`,
unchanged Stage 4P and Stage 4J policies, Stage 4I's 4,096-byte limit,
`generated_surface -> prop_secondary -> stage4d_stone`, and a conservative
`[-2,2] x [-2,2]` collision rectangle.

The completed order is:

```text
raw hash
  -> explicit COLOR_0 discard
  -> Stage 4Q no-op exact sanitation
  -> Stage 4R one-face removal
  -> Stage 4O rejection
  -> STOP
```

No Stage 4P, Stage 4F, Stage 4J, Stage 4I, model, ROM, or QA artifact was
produced after the rejection.

## Raw and Q/R evidence

The raw mesh contains 3,360 positions, 6,664 triangles, two components, 96
boundary edges, and 24 non-branching loops. Component counts are 6 positions /
8 faces and 3,354 positions / 6,656 faces.

COLOR_0 is accessor 2: normalized U8 VEC4, 3,360 elements, 13,440 payload
bytes, SHA-256
`019534d056ff0fc4713bfdedcbf6bb6adf320eb23a64edb407edc21c9bdb910e`.
Only COLOR_0 is discarded; POSITION and indices retain exact semantics.

Stage 4Q independently finds no exact-zero face and performs a validated no-op.
It preserves the one nonzero near-zero face for Stage 4R.

At `units_to_tiles = 5.047734581094872`, Stage 4R discovers semantic face
`4ce5eedec161d4af`, indices `[3262,3263,3264]`, without hardcoding its source
index. Source cross squared is `2.6948343349697145e-19`; all production points
quantize to `(-507,3735,-1636)`. Removing that one blocker preserves two
components, changes boundary topology from 96 edges / 24 loops to 99 edges /
25 valid loops, and leaves bounds and tested silhouettes unchanged.

The post-Q/R derived geometry has 3,360 positions and 6,663 triangles:

| Component | Positions | Faces | Surface area | Target positions | Target faces |
|---|---:|---:|---:|---:|---:|
| main reconstruction | 3,354 | 6,655 | 1.865758288 | 58 | 56 |
| small detached component | 6 | 8 | 0.004017552 | 6 | 8 |

Post-Q/R GLB SHA-256 is
`3208947b96fe402006c409a601fc7df4806ff5a1ad3a3a54b61a3bc494aae3a3`.
Five deterministic wireframe views are emitted under ignored build output.

## Stage 4O kill-gate result

The unchanged policy requires bounds delta ratio at most `0.04`, geometric
error ratio at most `0.08`, surface-area delta at most `22%`, silhouette IoU at
least `0.84`, and preservation of boundaries, ground contact, components, and
loops. These values were not tuned after observing the real asset.

Stable area-weighted allocation preserves the small component at 8 faces / 6
positions and gives the main component 56 faces / 58 positions. The main
component cannot reach that envelope. Existing constrained QEM stalls at its
best valid state of 177 faces / 103 positions after 3,251 accepted collapses.
No valid constrained edge remains.

Stable rejected-candidate counts are:

| Reason | Count |
|---|---:|
| batch conflict | 105,982 |
| boundary protection | 12,452 |
| degenerate result | 61 |
| face rotation | 23,443 |
| ground contact | 270 |
| topology link | 10,421 |

The failure is `geometry_predecimation_target_unreachable`: `no valid
constrained collapse can reach the preprocessing envelope`.

This cannot be handed to Stage 4J as-is. Stage 4P's bounded input contract is
80 faces / 256 positions, so the 177-face state cannot receive attributes.
Stage 4J deliberately operates after Stage 4P and requires complete UV,
normal, and material data. Reordering those contracts or inventing provisional
attributes would be new preprocessing outside Stage 4S.

Stage 4O emits no authoritative reduced geometry on failure. Consequently no
final Stage 4O bounds, area, error, silhouette, or raw-to-coarse rendering
exists. Treating an internal best state as output would violate the kill gate.

## Downstream and visual disposition

Stage 4P, Stage 4F, Nitro projection, Stage 4J, Stage 4I, texture binding,
collision generation, map integration, ROM construction, and Stage 4A QA were
not attempted. Therefore no display-list utilization, model, ROM, screenshot,
runtime, or gameplay claim exists.

The post-Q/R wireframe remains recognizably shrine-like and preserves the
concept's broad body/roof massing, but is visibly noisy and reconstruction-like.
That cannot predict whether a final DS-budget asset would be usable. The only
supported classification is `GENERATED_ASSET_VISUAL_UNCERTAIN`.

The detached six-position/eight-face component survives Q/R and receives its
full Stage 4O allocation; it is never treated as debris. No final grounding or
scale assessment is possible.

## Determinism, mutations, and performance

Two clean ignored output roots produce byte-identical post-Q/R GLBs, reports,
and five view images. No later artifact appears in either root.

The intended-size mutation to `4.5 x 6.75 x 4.5` changes target normalization
to `5.678701403731731`; Stage 4R still discovers one blocker and Stage 4O fails
identically. It is diagnostic only and does not select a nicer scale.

Temporarily mapping the source identity to existing `stage4d_wood` leaves Q/R/O
results unchanged. The canonical manifest remains `stage4d_stone`; no texture
bytes are generated because Stage 4O blocks the transaction.

Host measurements are approximately 0.038 seconds for Stage 4Q, 0.595 seconds
for Stage 4R, 14.0 seconds for Stage 4O to reject, and 15.09 seconds / 73,280
KiB maximum resident memory for the full report/view transaction. Stage 4P/J
times do not exist.

## Regression and recommendation

The immutable Stage 4H hash and rejection remain unchanged. Focused tests lock
the provenance stop, COLOR_0 evidence, Q/R topology, untuned allocation,
failure-closed outputs, mutations, two-root determinism, and exact Stage
4R/Q/P/O/J/K/L/M/N artifacts. The focused suite passes 8/8. The full suite
passes 309 tests with three expected opt-in integration skips. The Make proof,
Python compilation, preflight (58/58), diff checks, and artifact hygiene pass.
DeepSeek was not used; token and monetary cost are zero.

The specific reusable blocker is concrete: geometry-only Stage 4O cannot reduce
this boundary-rich TripoSR component into the Stage 4P envelope while retaining
its existing constraints. Do not begin another Stage 4 substage automatically.
The next explicit decision must choose between a separately justified
pre-bootstrap reduction architecture and a generator/export path that yields
simpler topology. Stage 5 should not begin under the `HAS_SPECIFIC_BLOCKER`
disposition.
