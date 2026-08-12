# Stage 6K Technical Report — Real Generated Landmark Kill Gate

## Verdict

`REAL_GENERATED_LANDMARK_PIPELINE_PROVEN`

An official anonymous Tencent Hunyuan3D-2 execution produced a real generated
Adriatic lighthouse/watchtower source. The selected immutable 100-triangle GLB
passed the existing topology contracts, constrained Stage 4O reduction,
unchanged Stage 4P/F compilation, Stage 4I relocation, ROM installation,
collision, multi-view traversal, and 600 stable frames.

This is the first positive real-generator result. It does not reinterpret the
negative/access findings from Stages 4H, 4S, 4T, or 4U.

## Official generator and provenance

- official repository: `Tencent-Hunyuan/Hunyuan3D-2`
- repository revision: `f8db63096c8282cb27354314d896feba5ba6ff8a`
- official Space: `tencent/Hunyuan3D-2`
- Space revision: `40b9abf02675534b9e80e3150bd97b85c135c8c8`
- model: `tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0`
- model repository revision: `9cd649ba6913f7a852e3286bad86bfa9a2d83dcf`
- license metadata: `tencent-hunyuan-community`
- execution: official anonymous Hugging Face Space
- cost: `$0`

The project-owned concept is
`assets/concepts/stage6k_adriatic_lighthouse.png`, SHA-256
`0d035d07e9a624464a28b97345ff0f858451a26d09ca72f56136a8088b24e23b`.
The immutable selected raw GLB is
`assets/source/generated/stage6k_hunyuan_lighthouse_octree16_100_raw.glb`,
SHA-256
`f8d7a52221efdc273b87a553ae2df207d70314dbb232cc5f9a914060c09c7151`.
Exact settings and rejected recovery evidence are tracked in
`assets/provenance/stage6k_hunyuan_lighthouse.json`.

## Generation and selection

The selected run held the concept, seed `1234`, 20 steps, guidance `5.0`,
background removal, and texture generation off. Official octree resolution 16
produced 506 positions/1,004 triangles in 4.644 seconds. The official exporter
requested 100 faces and returned 54 positions/100 triangles in 0.792 client
seconds.

The earlier octree-128 output was valid manifold geometry but its 306-triangle
export stalled at 302 triangles under unchanged Stage 4O. Stable Fast 3D's
official Space was reachable, but three bounded anonymous calls failed on the
service. No unofficial mirror, gated-weight bypass, or paid service was used.

## Immutable processing path

The canonical deterministic pipeline is implemented by
`tools/pokeagent/stage6k_landmark.py` and declared in
`assets/manifests/stage6k_hunyuan_lighthouse_pipeline.json`:

```text
immutable official raw GLB
  -> exact geometry projection
  -> Stage 4Q (no-op)
  -> Stage 4R (no-op)
  -> unchanged Stage 4O target 60
  -> unchanged Stage 4P
  -> unchanged Stage 4F
  -> Nitro projection
  -> unchanged Stage 4I relocation
  -> ROM/world placement
```

The raw mesh is a valid, closed, two-component manifold. Stage 4O preserved
both components and reduced 100 to 60 triangles with minimum silhouette IoU
`0.971939`, maximum geometric error ratio `0.043444`, and surface-area delta
`0.871692%`. Stage 4P emitted 34 unique positions, 60 faces/normals, 180 UVs,
and 180 attribute vertices. Stage 4F accepted the result.

The Nitro display list is 4,092 of 4,096 bytes with 180 emitted vertices.
Stage 4J is not required. The existing inherited shape region is 2,496 bytes,
so unchanged Stage 4I project relocation is required. Asset schema 14 adds only
the generated-source provenance boundary while retaining the existing 256
attribute-element preprocessing envelope and 4,096-byte storage ceiling.

## Runtime proof

`qa/scenarios/stage6k_generated_landmark.json` passed 16/16 semantic
assertions against ROM SHA-256
`3b77f223551a4d434af267202f9148c22dbaf9c73fee90ee2e27d718be6087f3`.
It proves controlled entry, the expected map/header/member, front collision,
walk-around access, front/rear/side screenshots, stable final position, and
600 additional frames.

Screenshot SHA-256 values:

- front: `93290605861fe9f9a6f6078036eaf2f976ab98422583a58e3953b8df6b6bf8a1`
- rear: `36657332a4a68fdceaaceb9d275b24e217ea1087db49a7c354532b936c8367d7`
- side: `3e5a030f35f7bed7bb22f85b6dfd3895f48d04ce9a9039e75de82a88d801a380`

At native resolution the asset reads as a compact, heavily faceted coastal
watchtower/lighthouse. The tower silhouette, cap, elevated opening/band, scale,
grounding, and walk-around depth are readable. Fine lighthouse detail and a
distinct lantern are not retained. That is nonblocking presentation debt for
this first kill-gate proof, not evidence of high-fidelity generator output.

## Determinism and safety

Two project pipeline runs produce byte-identical derived GLBs and reports. The
raw source is immutable and hash-pinned. No generated ROM, save, emulator log,
or screenshot is tracked. Normal builds do not activate the Stage 6K fixture.
Historical Stage 4 thresholds were not weakened.

DeepSeek was not used. DeepSeek cost: `$0`.

Advance automatically to Stage 6L integrated presentation QA.
