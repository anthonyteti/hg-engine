# Stage 6K Real Generated Landmark

## Finding

An official Hunyuan3D-2 anonymous Space export at low octree resolution can
naturally enter the existing Stage 4 topology and DS compilation contracts.
The successful boundary is the immutable official 100-triangle export, not a
repaired derivative and not a relaxed compiler threshold.

## Evidence

- `assets/provenance/stage6k_hunyuan_lighthouse.json`
- `assets/manifests/stage6k_hunyuan_lighthouse_pipeline.json`
- `docs/data/stage6k_landmark_pipeline.json`
- `tools/pokeagent/stage6k_landmark.py`
- `qa/scenarios/stage6k_generated_landmark.json`

The selected raw SHA-256 is
`f8d7a52221efdc273b87a553ae2df207d70314dbb232cc5f9a914060c09c7151`.
It has 54 positions, 100 triangles, two components, zero boundary edges, and
valid manifold topology. The final DS geometry has 34 positions, 60 triangles,
180 emitted vertices, and a 4,092-byte display list.

## Confidence

High for official provenance, raw immutability, topology, deterministic project
processing, DS budgets, ROM rendering, collision, and runtime stability.
Moderate for artistic fidelity: native-resolution evidence reads as a compact
faceted lighthouse/watchtower, but fine lantern detail was lost.

## Reproduction

```bash
make stage6k-generated-landmark
python3 -m tools.pokeagent qa run \
  qa/scenarios/stage6k_generated_landmark.json --timeout 600 --json
```

The official generation call is evidence, not part of the reproducible local
build. Local reproduction starts at the tracked immutable raw hash.

## Remaining unknowns

One successful architecture landmark does not prove broad image-to-3D quality,
texture generation, arbitrary topology, or automatic preservation of fine
architectural details. Stage 7 should reuse the proven bounded route and select
concepts whose identity survives DS-scale simplification.
