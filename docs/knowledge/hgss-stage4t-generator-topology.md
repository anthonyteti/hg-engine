# HGSS Stage 4T: TripoSR extraction-resolution topology

## Finding

Reducing only TripoSR's marching-cubes resolution does not naturally enter the
existing generated-asset pipeline for the Stage 4H shrine concept.

- MC48 preserves MC64 silhouette (`min IoU 0.895533 >= 0.88`) but emits two
  degree-4 branching boundary vertices, so unchanged Stage 4Q rejects it.
- MC32 emits one degree-4 branching boundary vertex and loses too much raw
  silhouette (`min IoU 0.809144`).
- The exact official API accepts 32 through 320; MC24 and MC16 are unavailable.

Confidence: high. Counts come from independently reopened tracked GLBs and the
existing project topology/silhouette code. No repair or threshold change was
used.

## Evidence

Fixed inputs:

- concept SHA:
  `06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f`;
- TripoSR revision:
  `f84354eb350eb07a108faf33a6bc564d455f9764`;
- foreground ratio: `0.85`;
- processed-image SHA:
  `2c10c83a98cd5162974f1f6216012f9b9bfc23e7dc28cad0ffb36302468306d6`.

Tracked candidates:

- MC48: 1,864 positions / 3,671 faces, SHA
  `b797e1851c0e517190f95a981a5b9dab61fe889d9c87a6a680e9217090242d7b`;
- MC32: 787 positions / 1,544 faces, SHA
  `da389a6595a8fb59e5bff19f2a480f1683d3c8aef7b4a590af396873c125fa2e`.

MC48 has 107 boundary edges, 23 closed cycle subgraphs, and two branching
subgraphs. MC32 has 52 boundary edges, 11 closed cycle subgraphs, and one
branching subgraph. Each offending vertex has boundary degree four. Neither
mesh has an exact-zero face, non-manifold shared edge, or inconsistent
shared-edge winding.

Source files:

- `tools/pokeagent/generator_topology.py`;
- `assets/manifests/stage4t_triposr_topology_sweep.json`;
- `assets/provenance/stage4t_triposr_shrine_mc48.json`;
- `assets/provenance/stage4t_triposr_shrine_mc32.json`;
- `tests/test_pokeagent_stage4t_generator_topology.py`;
- `docs/STAGE_4T_TECHNICAL_REPORT.md`.

## Architectural consequence

Stage 4T is generator evidence, not a new compiler stage. The project keeps the
same Q -> R -> O -> P -> F -> optional J -> I architecture. MC48 stops at Q;
MC32 stops at raw fidelity and would also stop at Q. No downstream algorithm
receives either candidate.

Do not reinterpret the 23/11 valid cycle subgraphs as a valid loop count for
the entire mesh: a boundary graph with a degree-4 vertex is outside the Stage
4Q contract. Fixing it would require a separately authorized topology policy.

## Reproduction

The external raw generation boundary used the official Space `/preprocess`
and `/generate` endpoints with the fixed inputs above. Once the tracked raw
hashes exist, project evidence is reproduced headlessly:

```bash
python -m tools.pokeagent asset generator-topology \
  assets/manifests/stage4t_triposr_topology_sweep.json \
  --output build/stage4t/proof --json
python -m unittest -v tests.test_pokeagent_stage4t_generator_topology
```

The proof command exits nonzero because the sweep is intentionally blocked.
Its report and wireframes are deterministic ignored outputs.

## Remaining unknowns

- Whether another generator/exporter can preserve the shrine while emitting a
  valid non-branching open-manifold boundary graph.
- Whether TripoSR has an upstream extraction/export setting other than
  marching-cubes resolution that changes this topology class; Stage 4T did not
  vary any such setting.
- Whether a narrowly specified branching-boundary operation could ever be
  proven non-heuristic. No such operation is authorized or inferred here.
