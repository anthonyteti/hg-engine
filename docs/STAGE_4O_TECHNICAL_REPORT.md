# Stage 4O Technical Report: Geometry-Only Predecimation

Date: 2026-08-09

Verdict: `STAGE_4O_GEOMETRY_PREDECIMATION_PASSED`

Classification: `RAW_GEOMETRY_GAP_CLOSED`

## Checkpoint and boundary

Stage 4N was committed and pushed before Stage 4O began as
`b4a7a9a7a35cd0a3c30c3cb2b6a6bcd6bed09e37`
(`Add Stage 4N material synthesis`). Local `HEAD`, `origin/main`, and remote
`main` agreed, and the worktree was clean.

Stage 4O reduces valid geometry before source normals, UV0, or material
identity exist. Its output deliberately remains a pre-Stage-4F artifact:

```text
large POSITION + indices GLB
  -> bounded geometry inspection
  -> format-independent geometry-only IR
  -> constrained deterministic QEM reduction
  -> small POSITION + indices GLB
  -> later attribute bootstrap
```

It writes no `NORMAL`, `TEXCOORD_0`, or material. It does not convert
`COLOR_0`, repair topology, target Nitro bytes, or replace Stage 4J.

## Architecture and source contract

`tools.pokeagent.glb_geometry_reduce` owns bounded GLB decoding, identity node
chain validation, schema-13 policy, canonical geometry-only GLB writing, and
independent output reopening. `tools.pokeagent.mesh_predecimate` owns the
format-independent positions/faces IR, topology checks, deterministic collapse
planning, and fidelity metrics. `tools.pokeagent.stage4o_fixture` produces the
tracked project-authored proof source; it is not part of the runtime compiler.

The accepted source is embedded GLB 2.0 with one scene, one mesh, one indexed
independent-TRIANGLES primitive, `POSITION`, and a 1..4-node unique
root-to-mesh chain whose combined transform is identity. The transformation
path accepts no auxiliary vertex attribute. In particular, `COLOR_0` fails
with `unsupported_geometry_aux_attribute`. Non-identity TRS fails with
`predecimation_requires_transform_bake` rather than duplicating Stage 4K.

Safety limits are:

| Resource | Limit |
|---|---:|
| GLB bytes | 8 MiB |
| BIN bytes | 8 MiB |
| nodes | 4 |
| meshes | 1 |
| primitives | 1 |
| accessors | 8 |
| buffer views | 8 |
| positions | 8,192 |
| triangles | 16,384 |
| indices | 49,152 |

Sparse accessors, external resources, compression/extensions, malformed
buffer ranges, unsupported component types, and non-finite data are rejected
before large allocations.

## Geometry validation and algorithm

The geometry-only IR contains canonical lexicographically ordered positions,
oriented indexed triangles, stable semantic vertex/face identities, bounds,
and connectivity. Faces are cyclically normalized without reversing winding,
then sorted, so source triangle order does not affect the simplifier.

Input must have finite distinct positions, three distinct indices per face,
nonzero face area, no duplicate faces, consistently oriented manifold interior
edges, non-branching open boundaries, and one connected component under the
canonical policy. Open boundaries are allowed. Invalid geometry is rejected;
no welding, winding repair, hole filling, or component deletion occurs.

The reducer uses deterministic manifold edge collapse with quadric error. It
reuses the pure quadric, area, normal, and point/triangle-distance primitives
already proven by Stage 4J, but does not call Stage 4J with invented attributes.
Stage 4J's attribute-aware policy and output remain untouched.

Candidate ordering uses normalized coordinates, error cost, and stable
canonical edge IDs. Non-overlapping deterministic batches reduce queue rebuild
cost without changing output. The reducer rejects link-condition violations,
boundary-to-interior collapses, ground-to-nonground collapses, face inversions,
degeneracy, duplicate output faces, and rotations above 80 degrees. Open
boundary vertices may collapse only along their boundary, preserving the
number of boundary loops. Vertices at minimum Y within `1e-6` normalized units
are ground-contact protected. Geometric creases at or above 60 degrees receive
a fixed deterministic QEM penalty.

The authored schema-13 policy is explicit opt-in. It targets 64 faces and 64
positions, preserves boundaries, ground contact, and components, and uses:

- maximum bounds delta ratio: 0.04
- maximum geometric error ratio: 0.08
- maximum surface-area delta: 22%
- minimum five-view silhouette IoU: 0.84

All error distances are normalized by the source bounds diagonal. This makes
the collapse policy translation invariant and uniform-scale relative. The
reducer stops at the first least-destructive deterministic state satisfying
both target counts and every fidelity gate.

## Canonical proof

The tracked source is
`assets/source/stage4o_dense_geometry_shrine.glb`, a reconstruction-style
hard-surface shrine shell with irregular noncoplanar wall, ledge, roof, and
doorway surfaces. It is not redundant planar subdivision.

| Property | Source | Reduced |
|---|---:|---:|
| GLB size | 13,592 bytes | 1,312 bytes |
| SHA-256 | `c37fac771cff1f5c77fd71bab27ea02631442f9260176ac0a0ef12aedcd6bcfc` | `7550ffe46c28d122c93d060312261b105f885cfbe483af4f27e835a6e1983957` |
| positions | 545 | 35 |
| triangles | 1,056 | 64 |
| components | 1 | 1 |
| boundary edges | 32 | 4 |
| boundary loops | 1 | 1 |

Face reduction is 93.939% and position reduction is 93.578%. The plan accepts
510 collapses. It records 20,485 rejected candidate evaluations: 17,501 batch
conflicts, 1,983 face-rotation violations, 945 boundary violations, and 56
topology link violations. The collapse-plan SHA-256 is
`9b753248aade51c2c3562294baf60cb69c497a21a2dd4cb27f45edfb34ba214d`.

The source semantic hash is
`da99d2fade94c20d2f3758828653eb4e304b10f8057142c57db651a3bfec2a45`;
the final mesh hash is
`4be9b430ed040e6ec06efce77f73a29282ae42166dd34ccfbe7fe89513399f9c`.

## Fidelity and topology evidence

| Metric | Result | Limit |
|---|---:|---:|
| maximum bounds delta ratio | 0.000000 | <= 0.04 |
| maximum geometric error / source diagonal | 0.047417 | <= 0.08 |
| mean geometric error / source diagonal | 0.010067 | recorded |
| source surface area | 112.797502 | recorded |
| final surface area | 109.091278 | recorded |
| surface-area delta | 3.285732% | <= 22% |
| front/rear silhouette IoU | 0.959734 | >= 0.84 |
| left/right silhouette IoU | 0.945570 | >= 0.84 |
| three-quarter silhouette IoU | 0.961292 | >= 0.84 |
| minimum silhouette IoU | 0.945570 | >= 0.84 |

The final mesh independently reopens and revalidates with no degenerate or
duplicate faces, no non-manifold or inconsistently oriented edge, one
component, and one open boundary loop. Bounds, recognizable body/roof/doorway
volumes, and ground contact remain intact.

## Negative and mutation proofs

The failure manifest requests 12 faces and 16 positions under the same fidelity
limits. The attempted 12-face/9-position state violates bounds, geometric,
surface, and silhouette gates. The best valid state is 30 faces and 18
positions with minimum silhouette IoU 0.908346. The operation fails
deterministically as `geometry_predecimation_target_unreachable`; it never
forces the destructive result.

- Reversing source face order yields byte-identical reduced GLB and report.
- Translating the source by `(100, -20, 7)` preserves collapse topology and
  produces only the expected translated result.
- Uniform scale by 3 preserves collapse topology and proportional output.
- Raising the roof to 6.8 changes source, reduced mesh, plan, and fidelity
  evidence while preserving identity.
- Tightening the target to 48 faces deterministically produces 48 faces and 27
  positions with minimum silhouette IoU 0.926898.
- Two independent output roots produce byte-identical geometry-only IR, plan,
  report, positions, indices, and canonical GLB.

On the development host the canonical command completed in 3.27 seconds wall
time (3.26 seconds user CPU) with a maximum resident set of 35,876 KiB. The
strict failure search is slower because it evaluates fidelity snapshots while
finding the best valid state. The explicit source limits bound the
standard-library implementation's time and memory exposure.

## Downstream boundary and regressions

The final 64 faces and 35 positions are below the intended bootstrap envelope
of 80 faces, 256 positions, and 256 accessor elements. A test-only copy with
independently supplied normals, UVs, and material passes unchanged Stage 4F
with all 64 faces. This proves topology compatibility only; it is not an
automatic Stage 4L/4M/4N composition route.

The actual geometry-only output correctly remains rejected by Stage 4F with
`unsupported_material`; `NORMAL` and `TEXCOORD_0` also remain absent. No ROM
or Stage 4A runtime proof is appropriate because Stage 4O's canonical output is
intentionally not a renderable asset.

Stage 4J's canonical regression remains exact: 59 triangles, 37 referenced
vertices, 4,024 display-list bytes, normalized output hash
`e11af8b7d49ef338018135174f0a1f5851a382ef472f2436cd4e130c4a77a814`,
and display-list hash
`e01fcce1a25c474ace65b14251683600360c56d052dfd5216287a8f5b7a20b04`.
Stage 4N's canonical material output remains
`3443c8fc70323a9a4200fb1dd1ee338694e6731a9f4fd52650c067369caf7f66`.

## Stage 4H read-only geometry evidence

The immutable Stage 4H GLB remains SHA-256
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`.
It has 3,360 positions and 6,664 triangles, so its declared counts fit the
Stage 4O numeric envelope. Its two-node chain is identity and fits the bounded
structural shape. Read-only topology inspection finds two components, 99 open
boundary edges in 25 loops, no duplicate faces, no repeated-index faces, no
non-manifold edges, no inconsistent shared-edge orientation, and one zero-area
triangle.

Therefore Stage 4O transformation is not applicable: `COLOR_0` is an explicit
auxiliary-attribute blocker, the zero-area face violates valid-source geometry,
and the canonical one-component policy is not met. No derived candidate was
written. The Stage 4H verdict remains `STAGE_4H_GENERATED_ASSET_REJECTED` /
`REJECTED_UNSUPPORTED_STRUCTURE`.

Even after independent Stage 4K-4N proofs, raw multi-missing-attribute
composition is unproven. Remaining Stage 4H blockers include `COLOR_0`, absent
material, absent `NORMAL`, absent `TEXCOORD_0`, invalid geometry for Stage 4O,
the Stage 4L/4M source envelopes, and the large final geometry cost.

## Remaining limits

Stage 4O supports one bounded static indexed triangle surface, identity node
chain, no auxiliary attributes, and valid one-component manifold/open-manifold
topology. It does not repair or delete geometry, support curved-organic quality
guarantees, preserve source attributes, bake transforms, bootstrap missing
attributes, target DS bytes, or approve generated assets. Stage 4P should prove
one explicit bounded composition/bootstrap transaction and decide `COLOR_0`
handling before any derived generated-asset attempt.

DeepSeek usage: none; 0 tokens, $0.

## Verification

- `make stage4o-geometry-predecimation-proof`: pass
- `python -m compileall -q tools/pokeagent tests/test_pokeagent_stage4o_geometry_reduce.py`: pass
- `python -m tools.pokeagent registry validate --json`: pass, 12 namespaces / 34 resources
- `python -m tools.pokeagent preflight --json`: pass, 58 checks
- `python -m unittest discover -s tests -v`: 258 pass, 3 expected opt-in integration skips
- `git diff --check`: pass
- tracked-artifact audit: no ROM, generated model/NARC, build output, screenshot, save/state, cache, or credential added

No emulator QA or visual runtime claim is made. The controlled output is
purposefully incomplete and must not be put into a ROM before a separately
proven attribute-bootstrap composition stage.
