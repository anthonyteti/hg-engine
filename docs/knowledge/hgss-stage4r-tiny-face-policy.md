# HGSS Stage 4R: target-representation-null tiny faces

## Finding

A mathematically nonzero triangle may be removed before Stage 4O only when it
is already rejected by Stage 4O's `1e-9` geometric-normal gate, becomes exactly
degenerate after the real production `VTX_16` quantizer, and can be removed
without deleting/splitting/merging a component or invalidating boundary
topology. There is no relative-area or general epsilon removal policy.

Confidence: high. Confirmed by encoder source, golden integer-boundary tests,
independent reference equality, complete Q -> R -> O -> P -> unchanged Stage
4F integration, and exact prior-stage regressions.

## Target coordinate path

1. Apply declared source axes and `units_to_tiles`.
2. Anchor X/Z at footprint center and Y at source minimum.
3. Apply cardinal placement.
4. Multiply by model tile scale `0.25`; add base Y `0.25`.
5. Emit Nitro `VTX_16` (`0x23`) as signed 4.12 fixed point:
   `round(value * 4096)` in `[-32768,32767]`.

The exact increments are `1/4096` model unit and `1/1024` normalized tile.
Rounding is nearest, ties to even. Stage 4R reuses the encoder's public
quantizer rather than maintaining an approximation.

## Decision rule

```text
removable =
    source_cross_squared > 0
    AND source_cross_length <= 1e-9
    AND integer_target_cross_squared == 0
    AND topology_after_removal_is_valid
```

Exact zero belongs exclusively to Stage 4Q. Target-null faces with source
cross length above `1e-9` remain geometry because they do not block Stage 4O.
Any tiny face whose integer target cross is nonzero remains geometry.

## Evidence and reproduction

Run:

```bash
python -m tools.pokeagent asset tinyface-sanitize \
  assets/manifests/stage4r_target_null.json \
  --output build/stage4r-proof --json
python -m unittest -v tests.test_pokeagent_stage4r_tinyface
```

The controlled nonzero face has source cross squared
`1.9478342112530432e-19`, but its three target points all encode to
`(-115,6690,947)`. The output equals the independent no-face reference. A
separate face below the Stage 4O normal threshold encodes with integer target
cross squared one and survives. Probes at 0.4999/0.5/0.5001 quantizer steps
lock below/tie/above behavior.

## Stage 4H evidence

At a 4 x 6 x 4 tile intended size, source face 6404 encodes all three vertices
to `(-507,3735,-1636)`. It meets the Stage 4R rule. Hypothetical removal keeps
two components, changes 24 valid loops to 25, creates no isolated position,
and has zero tested bounds/silhouette impact. The raw file was not modified.

This closes only readiness for a separately authorized derived attempt. It
does not approve the generated asset, predict Stage 4O/4J fidelity, or prove
runtime visual quality. Stage 4H's historical rejection and raw hash remain.

## Remaining unknowns

- The policy is specific to the current normalization, placement, model scale,
  `VTX_16` encoder, and manifest size; a different encoder or scale must be
  reclassified.
- A target-null face whose removal damages topology remains rejected.
- Entire target-null components cannot be deleted.
- Relative-area Policy B was measured but not implemented; it is unnecessary
  for the observed face and would create a broader subjective boundary.
- A derived Stage 4H attempt may still fail coarse/final decimation fidelity,
  4 KiB capacity, runtime QA, or visual usefulness.
