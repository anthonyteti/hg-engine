# HGSS Stage 4S: real TripoSR derived attempt

## Finding

The immutable Stage 4H TripoSR source passes the proven COLOR_0, exact topology,
and target-null gates, but unchanged Stage 4O cannot reduce its main component
to the bounded Stage 4P input envelope. The complete generated-asset pipeline
therefore remains unproven.

Confidence: high. Confirmed from the hash-locked source, deterministic Q/R
derived geometry, unchanged Stage 4O, clean-root comparison, and regressions.

## Reproduction

```bash
python -m tools.pokeagent asset generated-pipeline \
  assets/manifests/stage4s_real_generated_shrine.json \
  --output build/stage4s --json
```

The command intentionally exits nonzero. Expected terminal gate:

```text
phase: stage4o
code: geometry_predecimation_target_unreachable
allocated main target: 56 faces / 58 positions
best valid main state: 177 faces / 103 positions
```

No reduced geometry is emitted after this failure.

## Proven prefix

- Raw SHA-256: `7327a0a6...ef60`.
- COLOR_0: normalized U8 VEC4, 3,360 entries, explicit discard eligible.
- Stage 4Q: zero exact faces removed.
- Stage 4R: semantic face `4ce5eedec161d4af` removed because all production
  VTX_16 points equal `(-507,3735,-1636)`.
- Post-Q/R: 3,360 positions, 6,663 faces, two components, 99 boundary edges,
  25 valid loops.
- Small component: preserved at 6 positions / 8 faces.

## Exact blocker

Stage 4O allocates its unchanged total 64-face/64-position target across both
components. The large component exhausts every legal collapse at 177 faces /
103 positions. Boundary, topology-link, and face-rotation constraints account
for most non-batch rejections. Lowering fidelity, deleting the small component,
or bypassing Stage 4P was not attempted.

Stage 4J cannot move ahead unchanged: it protects UV seams, normals, and
materials that do not exist until Stage 4P. Stage 4P accepts at most 80 faces,
so the 177-face state cannot cross that boundary.

## Remaining unknowns

- Whether an explicitly scoped preprocessing architecture can bridge 177 faces
  to the Stage 4P envelope without weakening fidelity.
- Whether another generator/export configuration naturally yields simpler
  topology while retaining the concept.
- Final 4 KiB fit, runtime stability, and visual usefulness; none were reached.

The Stage 4H historical rejection and raw hash remain unchanged. The Stage 4S
post-Q/R GLB is ignored diagnostic output, not approved project content.
