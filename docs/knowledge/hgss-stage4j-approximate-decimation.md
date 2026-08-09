# HGSS Stage 4J approximate decimation

## Finding

A valid, single-material static triangle mesh can be reduced deterministically
after Stage 4G's exact pass and before Stage 4I model relocation. The bounded
project implementation uses constrained quadric-error-ranked edge collapses and
targets encoded Nitro display-list bytes rather than a polygon quota.

```text
OBJ or strict GLB
  -> normalized typed IR
  -> exact coplanar reduction
  -> constrained approximate edge collapse
  -> typed-IR validation and Nitro encoding
  -> Stage 4I relocated display list (maximum 4,096 bytes)
```

Approximate reduction is manifest opt-in. It does not run for legacy manifests
or repair malformed input.

## Implementation boundary

`tools/pokeagent/mesh_decimate.py` consumes and returns typed mesh IR. It knows
nothing about GLB/OBJ containers, HGSS registries, textures, collision, or
NSBMD. The implementation is project-owned Python standard-library code.

It canonicalizes wedge vertices and faces, ranks manifold edge collapses by a
quadric error plus stable canonical keys, and rejects changes that would create
duplicate/degenerate faces, invert winding, exceed normal or UV bounds, cross
protected material/texture/UV/hard-normal boundaries, or alter protected ground
contact. Reversing source face order produces the same simplified output.

## Policy and source envelope

Manifest schema 8 requires explicit approximate simplification and Stage 4I
geometry storage. The proof thresholds were declared before the final run:

```text
target encoded bytes                 4,096
maximum geometric displacement       0.25 world unit
maximum bounds delta                 0.25 world unit
maximum surface-area delta           12 percent
minimum five-view silhouette IoU     0.90
maximum normal deviation             50 degrees
maximum UV distortion                70 percent
hard-normal protection threshold     80 degrees
```

The bounded preprocessing envelope is 524,288 source bytes, 512 positions, 512
UVs, 256 normals, 256 faces, and 24,000 projected Nitro bytes. These are project
limits, not DS hardware limits. Failure to satisfy both fidelity and budget
returns `approximate_simplification_target_unreachable`; commands are never
truncated.

## Canonical evidence

The project-authored `stage4j_dense_stone_shrine.glb` is a valid identity-node
Stage 4F GLB with authored normals/UV0 and one stone material. Its faceted tiers
and roof are genuinely non-coplanar.

```text
source                         208 triangles, 120 positions
source projected display list 14,156 bytes
after Stage 4G exact pass      64 triangles + 72 quads, 10,928 bytes
after Stage 4J approximate    59 triangles, 37 referenced vertices
final emitted vertices        177
final display list            4,024 bytes (98.242% of 4,096)
```

The exact pass remains 6,832 bytes over capacity. Stage 4J accepts 83 collapses
and reduces faces by 71.635% and command bytes by 71.574%.

```text
maximum vertex displacement   0.123495
mean geometric error          0.006194
maximum bounds delta          0.175000
surface-area delta            7.439966%
maximum normal deviation      42.807662 degrees
mean normal deviation         14.258270 degrees
maximum UV distortion         65.097121%
minimum five-view silhouette  0.933789 IoU
```

Front/rear silhouette IoU is 0.953540, left/right is 0.954574, and the fixed
three-quarter view is 0.933789. All thresholds pass. Localized roof UV stretch
makes the evidence `FIDELITY_ACCEPTABLE`, not `FIDELITY_HIGH`.

## Binary, runtime, and failure evidence

The final stream contains 59 independent triangles and terminates cleanly.
Stage 4I relocates it to shape 6 at offset 16,604. The model grows from 16,604
to 20,628 bytes while all 17 other shape payloads remain byte-identical. The
independent parser confirms all ranges, counters, and commands.

The declarative scenario passes 15/15 assertions through frame 9,004. It proves
map identity, approach, collision, walk-around, captures, nearby movement, and
600 stable frames. Visual inspection confirms a complete, recognizable,
upright, grounded, coherently textured shrine with intact terrain.

The tracked strict-fidelity fixture deterministically fails: its best valid
candidate remains 14,020 bytes. A roof-height mutation propagates through IR,
display list, and model while identity, texture, collision, and world IDs stay
stable. A temporary 3,500-byte target yields a valid deterministic 3,480-byte
result. Reversed source face order is byte-identical after canonicalization.

## Confidence and unknowns

Confirmed by source, tests, independent binary parsing, ROM build, runtime
memory assertions, visual review, and two-root determinism: exact-first
approximate reduction for the schema-8 subset under the 4 KiB tested ceiling.

Unsupported: topology repair, hierarchy/transform baking, missing normals/UVs,
UV unwrapping, material-seam collapse, curved/high-frequency fidelity claims,
arbitrary generated assets, the rejected Stage 4H candidate, and model capacity
above 4,096 bytes.

## Reproduction

```bash
python -m tools.pokeagent asset inspect assets/manifests/stage4j_dense_stone_shrine.json --json
python -m unittest tests.test_pokeagent_stage4j_decimation
make stage4j-approx-decimation-proof
python -m tools.pokeagent qa run qa/scenarios/stage4j_approximate_decimation.json --json
python -m tools.pokeagent world determinism --fixture fixtures/stage4j_approximate_decimation_world.json --json
```

Evidence is coupled to the supported US HeartGold revision and hash-locked local
templates documented by earlier stages.
