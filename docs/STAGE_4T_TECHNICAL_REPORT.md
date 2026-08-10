# Stage 4T technical report: TripoSR extraction topology

## Verdict

```text
STAGE_4T_GENERATOR_TOPOLOGY_BLOCKED
TRIPOSR_TOPOLOGY_REMAINS_TOO_COMPLEX
STAGE_4_ASSET_INFRASTRUCTURE_HAS_SPECIFIC_BLOCKER
```

The lower-resolution TripoSR hypothesis did not cross the existing pipeline.
MC48 preserves the MC64 raw silhouette, but its open boundary graph contains
two degree-4 branching vertices and is rejected by unchanged Stage 4Q. MC32
has one degree-4 branching boundary vertex and independently fails the
predeclared `0.88` raw silhouette floor. MC24 and MC16 are below the official
Space API's accepted minimum resolution of 32.

No Stage 4O threshold, Stage 4P envelope, Stage 4J protection, Stage 4I model
capacity, or Stage 4F rule changed. No candidate reached Stage 4O, a model, a
ROM, runtime QA, or in-game visual judgment.

## Stage 4S checkpoint

Stage 4S was committed and pushed before this experiment:

```text
99ac5e631acc52eb0a01ca080a5aeb821e8a9355
Add Stage 4S real generated asset kill gate
```

Local `HEAD`, `origin/main`, and remote `refs/heads/main` agreed, and the
worktree was clean before Stage 4T began.

## Fixed generator provenance

Stage 4T reused exactly:

- concept: `assets/concepts/stage4h_generated_shrine_concept.png`;
- concept SHA-256:
  `06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f`;
- model/Space: `stabilityai/TripoSR`;
- revision: `f84354eb350eb07a108faf33a6bc564d455f9764`;
- background removal: enabled;
- foreground ratio: `0.85`;
- output: GLB.

The Hugging Face Space metadata reported that exact revision while the sweep
ran. The live `/generate` endpoint exposed marching-cubes values from 32 to
320. Therefore MC48 and MC32 ran; MC24 and MC16 were recorded as unsupported
rather than sent as invalid requests. No other generator input changed.

The common processed-image SHA-256 was
`2c10c83a98cd5162974f1f6216012f9b9bfc23e7dc28cad0ffb36302468306d6`.
Each raw candidate and its provenance are immutable tracked evidence:

| MC | Raw bytes | Raw SHA-256 | Generation time |
|---:|---:|---|---:|
| 48 | 74,884 | `b797e1851c0e517190f95a981a5b9dab61fe889d9c87a6a680e9217090242d7b` | 3.497 s |
| 32 | 32,124 | `da389a6595a8fb59e5bff19f2a480f1683d3c8aef7b4a590af396873c125fa2e` | 1.432 s |

The generator itself is outside the project determinism boundary. These raw
hashes are the new boundaries for deterministic project inspection.

## Baseline comparison

The fixed raw-fidelity gate was minimum five-view silhouette IoU `>= 0.88`
after the same 4 x 6 x 4 normalization.

| MC | Raw faces | Raw positions | Components | Boundary result | Q/R faces | Stage 4O | P | F | Pre-J | Post-J | ROM | Visual |
|---:|---:|---:|---:|---|---:|---|---|---|---:|---:|---|---|
| 64 | 6,664 | 3,360 | 2 | 24 valid loops | 6,663 | blocked at 177 faces / 103 positions | no | no | n/a | n/a | no | not reached |
| 48 | 3,671 | 1,864 | 1 | 23 cycles + 2 branching subgraphs | n/a | not reached | no | no | n/a | n/a | no | not reached |
| 32 | 1,544 | 787 | 1 | 11 cycles + 1 branching subgraph | n/a | not reached | no | no | n/a | n/a | no | not reached |
| 24 | n/a | n/a | n/a | API unsupported | n/a | not reached | no | no | n/a | n/a | no | not reached |
| 16 | n/a | n/a | n/a | API unsupported | n/a | not reached | no | no | n/a | n/a | no | not reached |

For MC48 the five IoUs were front/rear `0.904105`, left/right `0.895533`,
and three-quarter `0.907692` (mean `0.901394`, minimum `0.895533`). Its
normalized bounds maximum delta from MC64 was `0.2203188799573983`, or
`0.0320022601677952` of the MC64 normalized diagonal. Deterministic wireframes
retain the broad shrine roof/body massing and principal opening.

For MC32 the five IoUs were front/rear `0.809144`, left/right `0.818048`,
and three-quarter `0.828632` (mean `0.816603`, minimum `0.809144`). Its
normalized bounds maximum delta was `0.39573706064417635`, or
`0.05748250161412554` of the MC64 normalized diagonal. The shrine remains
coarsely recognizable, but roof/body and opening detail are visibly weaker;
the quantitative raw gate rejects it.

The MC64 detached six-position/eight-face component is absent from both lower
extractions. Their single major shrine component survives. This is an observed
generator-topology change, not a component-deletion preprocessing policy.

## Candidate intake and topology gates

Both candidates contain only `POSITION`, indices, and normalized U8 `VEC4`
`COLOR_0`. The already-proven explicit-discard policy is structurally
applicable, but discard is never reached as an authoritative derived pipeline
output in this blocked experiment.

MC48 contains no exact-zero face. Read-only Stage 4R intake sees one
Stage-4O-blocking target-quantized-degenerate face, seven target-null but
nonblocking faces, and 3,663 target-representable faces. Its edge graph is
manifold and consistently wound, but 107 boundary edges form 25 connected
boundary subgraphs: 23 cycles and two subgraphs containing a degree-4 boundary
vertex. Unchanged Stage 4Q returns
`topology_sanitize_branching_boundary`. Q removes nothing, and R is not run.

MC32 also contains no exact-zero face. It has six target-null nonblocking faces
and 1,538 target-representable faces. Its 52 boundary edges form 12 subgraphs:
11 cycles and one subgraph containing one degree-4 boundary vertex. It stops at
the raw fidelity gate; independent structural inspection confirms it would
also receive `topology_sanitize_branching_boundary` from Stage 4Q.

The Stage 4Q rule was not broadened. No face, boundary, component, or attribute
was changed in either raw candidate.

## Existing pipeline disposition

MC48 is the highest candidate that passes raw fidelity. It reaches Stage 4Q
and fails there. MC32 is below raw fidelity and is structurally invalid under
the same Q contract. Consequently:

- Stage 4R authoritative removal: not reached;
- Stage 4O: not reached for either candidate;
- Stage 4P: no candidate reached it;
- Stage 4F: not reached;
- pre-J bytes: unavailable;
- Stage 4J: not needed because no complete attributed asset exists;
- final bytes / Stage 4I: unavailable;
- ROM / Stage 4A QA: not run;
- in-game visual result: not reached.

This is deliberately fail-closed. Repairing a branching boundary would be a
new topology operation and is outside Stage 4T.

## Determinism and performance

Two clean Stage 4T analysis roots produced byte-identical reports and
wireframe diagnostics. The semantic report SHA-256 is
`9728dedc5e0e4cdf0d8530361e2dde6bf289daa56c44420d63932a1e039f6414`.
No derived GLB, model, NARC, ROM, or screenshot is emitted.

The two accepted generator runs plus preprocessing took `6.848` seconds in the
observed public session. The deterministic project analysis, including
re-running the unchanged MC64 Stage 4S baseline gate, took `17.99` seconds and
peaked at `75,156` KiB RSS. Performance is practical; correctness, not runtime,
blocks the experiment.

## Regression evidence

The focused Stage 4T suite has seven passing tests. It proves immutable source
and provenance hashes, MC48/MC32 metrics, raw-fidelity gating, exact Stage 4Q
rejection, 24/16 API bounds, fail-closed later stages, two-root determinism,
and prior-stage immutable bytes.

Canonical regressions remain exact, including:

- Stage 4Q canonical SHA
  `ef022994ecdd5574940284d992de237236b1ff32313695ae60e942baca77f0f7`;
- Stage 4R canonical SHA
  `69deff902150a082981a624a391a3b25629f8e6628dcbe1f6c3e21df0cfcd814`;
- Stage 4O canonical SHA
  `7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957`;
- Stage 4P canonical SHA
  `06b798f8de7661306a200bddf917ed75da06c122a0dc28ab785de94461b105e1`;
- Stage 4J display list: `4,024` bytes, SHA
  `e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04`.

The full unit suite passes `316` tests with three expected opt-in integration
skips. Preflight passes all `58` checks, including sensitive-artifact hygiene.
DeepSeek was not used, so token usage and cost are zero.

## Historical invariants and recommendation

Stage 4H remains immutable at
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`
with `STAGE_4H_GENERATED_ASSET_REJECTED / REJECTED_UNSUPPORTED_STRUCTURE`.
Stage 4S remains the committed failed MC64 kill gate. Stage 4T does not replace
either result.

The exact remaining blocker is generator-emitted branching open-boundary
topology at MC48, the only lower extraction that retains the required raw
silhouette. Do not add repair or relax Stage 4Q preemptively. The next decision
should separately evaluate a generator/exporter that can emit valid bounded
open-manifold topology while preserving this concept. Do not begin that
experiment or Stage 5 automatically.
