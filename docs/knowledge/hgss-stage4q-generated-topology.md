# HGSS Stage 4Q: Exact Generated-Topology Sanitation

## Finding

A bounded generated-style mesh can safely cross into the Stage 4O -> Stage 4P
pipeline when its only invalid faces have exactly zero float32-decoded area and
its disconnected components are individually valid. Exact faces are removed
with full provenance; all valid components and non-branching boundary loops
are preserved. This is sanitation, not repair.

The real Stage 4H candidate is not currently eligible: its smallest face is
near-zero but mathematically nonzero, so the Stage 4Q policy preserves it and
Stage 4O continues to reject it.

Confidence: high for the bounded controlled class, confirmed by reference
bytes, independent reopening, topology/fidelity tests, and unchanged Stage 4F.

## Reproduction

```bash
python -m tools.pokeagent asset topology-sanitize \
  assets/manifests/stage4q_generated_topology.json \
  --output build/stage4q --json
python -m unittest -v tests.test_pokeagent_stage4q_topology
```

The first command emits ignored sanitized, reduced, bootstrapped, and report
artifacts. The tracked raw/reference fixtures remain immutable.

## Exact face rule

Given float32-decoded `p0`, `p1`, and `p2`:

```text
c = cross(p1 - p0, p2 - p0)
remove iff dot(c, c) == 0.0
```

No epsilon participates. Repeated-index, repeated-position, and collinear
cases are labeled separately. A nonzero face survives regardless of visual
size or aspect ratio.

## Component and boundary rule

- 1..4 components.
- Stable ID from canonical component positions and oriented faces.
- Sixteen-face minimum per component, then surface-area-weighted distribution.
- Ten-position minimum, then the same stable distribution.
- Independent Stage 4O reduction; no cross-component edges.
- Source/final component count identical; no split, merge, or deletion.
- Boundary vertices form non-branching cycles.
- Boundary-loop count and per-component ownership survive.
- Impossible targets fail rather than delete a component.

## Evidence files

- `tools/pokeagent/mesh_sanitize.py`
- `tools/pokeagent/glb_topology.py`
- `tools/pokeagent/mesh_predecimate.py`
- `tools/pokeagent/stage4q_fixture.py`
- `assets/source/stage4q_generated_multicomponent.glb`
- `assets/source/stage4q_sanitized_reference.glb`
- `assets/manifests/stage4q_generated_topology.json`
- `tests/test_pokeagent_stage4q_topology.py`
- `docs/STAGE_4Q_TECHNICAL_REPORT.md`

## Controlled metrics

- raw: 566 positions / 1,089 faces / COLOR_0 / one exact zero face;
- sanitized: 563 positions / 1,088 faces / two components / one loop;
- reduced: 32 positions / 55 faces / same two components / same loop;
- accepted collapses: 531;
- rejected collapse evaluations: 21,462;
- bounds error: zero;
- surface-area delta: 3.411682%;
- maximum geometric-error ratio: 0.047176;
- minimum aggregate silhouette IoU: 0.922699;
- Stage 4F: accepted after Stage 4P;
- projected Nitro display list: 3,752 / 4,096 tested bytes.

## Real-candidate correction

Stage 4O's earlier read-only quality report called one Stage 4H triangle zero
area because `_normal` rejects cross lengths at or below `1e-9`. Exact Stage
4Q inspection finds squared cross magnitude `2.6948343349697145e-19`, which is
nonzero. With that face retained, the raw index topology has two components,
96 boundary edges, 24 non-branching loops, and no isolated positions. Excluding
it under the older tolerance view yields the previously reported 99 edges / 25
loops.

This semantic distinction is important: Stage 4Q does not erase the face to
make a candidate pass. `DERIVED_GENERATED_CANDIDATE_NOT_READY` is the correct
readiness result.

## Remaining unknowns

- Whether a narrowly bounded relative tiny-face policy can be justified.
- Whether that policy can preserve appearance and topology without becoming
  heuristic repair.
- Runtime/visual quality of a future authorized derived generated candidate.
- The true Nintendo DS geometry hardware ceiling remains outside this stage.
