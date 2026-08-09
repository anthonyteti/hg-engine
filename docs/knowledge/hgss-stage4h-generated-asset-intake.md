# Stage 4H generated-asset intake boundary

## Finding

A real image-to-3D generator is accessible without an account or payment, but
its bounded output does not satisfy the strict static-mesh contract already
proven by Stages 4F and 4G. The correct reusable boundary is therefore an
immutable raw-GLB hash plus a read-only structural intake report. Intake must
not imply catalog approval or mesh compilation.

Confidence: **confirmed by generator output, byte inspection, project parser,
unit tests, and diagnostic rendering**.

## Generator evidence

- Tool: `stabilityai/TripoSR`, official public Hugging Face Space.
- Space revision observed on 2026-08-09:
  `f84354eb350eb07a108faf33a6bc564d455f9764`.
- Access: anonymous Gradio API; no user credential, payment, or ROM upload.
- Canonical parameters: background removal enabled, foreground ratio `0.85`,
  marching-cubes resolution `64`, GLB output.
- The [official TripoSR repository](https://github.com/VAST-AI-Research/TripoSR)
  and [model card](https://huggingface.co/stabilityai/TripoSR) identify the
  project as single-image 3D reconstruction under MIT. The exact license text
  is in the [official repository](https://github.com/VAST-AI-Research/TripoSR/blob/main/LICENSE).
- `gradio_client==1.3.0` was installed only in ignored `.venv` to call the
  public proof endpoint. It is not a project runtime dependency.

The project-authored concept is
`assets/concepts/stage4h_generated_shrine_concept.png`, SHA-256
`06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f`.
No commercial ROM or retail asset was uploaded.

## Canonical raw boundary

The unedited canonical output is
`assets/source/generated/stage4h_generated_shrine_raw.glb`:

- size: `134,740` bytes;
- SHA-256:
  `7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`;
- generator container marker: `https://github.com/mikedh/trimesh`;
- GLB 2.0, one JSON chunk and one embedded BIN chunk;
- one scene, two nodes, one mesh, one independent-triangle primitive;
- `3,360` positions, `19,992` indices, `6,664` triangles;
- no materials, images, textures, animations, skins, morphs, or extensions;
- attributes: `POSITION` and normalized `COLOR_0` only;
- no authored `NORMAL` or `TEXCOORD_0`;
- bounds:
  - minimum `[-0.3970181942, -0.3725461960, -0.4249185324]`;
  - maximum `[0.3447825909, 0.4532465935, 0.3675161600]`.

The external generator may be nondeterministic. The project makes no claim
that rerunning it recreates this GLB. The reproducible boundary begins at this
raw hash; processing from that hash is deterministic.

## Intake architecture

`tools.pokeagent.generated_intake` performs bounded, read-only inspection:

```text
tracked provenance + expected hashes
                 +
         immutable raw GLB
                 |
                 v
      safe GLB container scan
                 |
        +--------+---------+
        |                  |
 strict Stage 4F parse   structural/budget summary
        |                  |
        +--------+---------+
                 |
       deterministic report
```

The command is:

```bash
python -m tools.pokeagent asset intake \
  assets/manifests/stage4h_generated_shrine_intake.json --json
```

An optional `--output` writes an ignored `intake-report.json`. The analyzer
does not normalize, repair, simplify, generate normals/UVs, bind a material,
or modify the GLB.

Canonical generated source directories must not be matched by build cleanup.
`make clean` therefore removes only `armips/include/generated`,
`include/constants/generated`, and `data/generated`; a repository-wide
`find ... -name generated` is unsafe once generated outputs become tracked
canonical inputs.

The manifest is intentionally not an ordinary approved asset manifest and the
candidate is not added to `assets/catalog.json`. A generated candidate acquires
catalog/world identity only after it passes the existing compiler contract.

## Rejection evidence

The canonical candidate is `REJECTED_UNSUPPORTED_STRUCTURE` for independent,
source-backed reasons:

1. two nodes and a parent/child hierarchy, while Stage 4F accepts one leaf mesh
   node with implicit identity transform;
2. zero named materials, while the source-to-project binding requires one;
3. missing authored normals;
4. missing UV0;
5. unexpected vertex-color data;
6. all accessors exceed the Stage 4F limit of 256 elements;
7. `3,360` positions exceed the Stage 4G source budget of 128;
8. `6,664` faces exceed its source budget of 64;
9. conditional independent-triangle Nitro projection is `453,164` bytes versus
   the unchanged shape-6 capacity of `1,068` bytes.

The byte projection is conditional because the source lacks the normal and UV
attributes required to emit those commands. It is still the correct
like-for-like cost of representing all source triangles through the proven
independent-triangle encoder.

Stage 4G exact simplification cannot apply: the raw asset cannot reach typed IR
without forbidden normal/UV generation and hierarchy preprocessing, and its
general non-coplanar reconstructed surface is not an exact redundant coplanar
patch proof.

## Visual finding

A read-only diagnostic projection of raw positions, indices, and vertex colors
shows a recognizable squat shrine/watchtower with a blue roof and dark doorway.
The major concept silhouette survives, but the surface is highly irregular and
faceted, the roof/body planes are lumpy, and the output is far beyond the DS
budget. This is useful generator-compatibility evidence, not emulator evidence.

Because the candidate is rejected before normalized IR, no material binding,
collision proxy, NSBMD, map member, ROM, gameplay QA, or in-game screenshot was
generated. Doing so would require weakening earlier validators or adding the
explicitly excluded preprocessing capabilities.

## Candidate history

- Stable Fast 3D public Space: bounded anonymous attempts returned an upstream
  application error and produced no file.
- TripoSR resolution 128: `571,492` bytes,
  SHA-256 `62223647001388e7a4503f09a566da10660b8f782292f62328368726a5b33021`;
  rejected at the Stage 4F `262,144`-byte input bound.
- TripoSR resolution 64: canonical preserved raw input described above.

Rejected intermediates remain ignored; the tracked provenance record preserves
their hashes and reasons without adding unnecessary binary fixtures.

## Reproduction

From the tracked canonical input:

```bash
python -m tools.pokeagent asset intake \
  assets/manifests/stage4h_generated_shrine_intake.json \
  --output build/stage4h/intake --json
python -m unittest tests.test_pokeagent_stage4h_intake -v
```

The semantic report hash is
`776a654889d6a16f4ef5a180aee4c636cf2e71fee30e79d65a07c196aee4ca86`.
The pretty-printed report file hash is
`abc04f245fc1caa48caef1c4f9b2ef2c9cabfd0d00eff828883751a941704c08`.

## Confirmed, inferred, unknown

### Confirmed

- TripoSR public generation was accessible and produced the tracked raw GLB.
- The raw structure, attributes, counts, hashes, bounds, and budget projection.
- Existing Stage 4F rejects it without modifying it.
- Existing Stage 4G cannot receive it as typed IR.
- Intake reports are byte-identical across clean output roots.

### Inferred

- A generator/export mode that emits one identity node, one material, authored
  normals and UV0, and far lower topology could fit the current pipeline.
- The concept is deliberately favorable, so the observed incompatibilities are
  likely representative of TripoSR's geometry-first output rather than concept
  complexity alone.

### Unknown

- Whether another accessible generator can natively produce the exact Stage 4F
  contract without preprocessing.
- Whether deterministic transform baking, normal generation, UV generation, or
  approximate constrained decimation should be the next scoped stage.
- Generator-run reproducibility; only downstream processing is reproducible.
