# Stage 4H technical report: first generated-asset intake

## Verdict

`STAGE_4H_GENERATED_ASSET_REJECTED`

Generated-asset quality classification:

`REJECTED_UNSUPPORTED_STRUCTURE`

A genuine image-to-3D run succeeded and its unedited GLB is tracked with a full
provenance chain. The candidate does not reach the existing normalized typed
mesh IR: it has a hierarchy, no named material, no normals, no UVs, unexpected
vertex colors, and orders of magnitude too much geometry. Passing it would
require the exact repair/importer/decimation capabilities excluded from Stage
4H. The correct outcome is a source-backed rejection, not a weakened validator.

## Stage 4G checkpoint

Stage 4G was committed as `5f690fe42 Add Stage 4G deterministic mesh
simplification` and pushed. Local `HEAD`, `origin/main`, and remote `main`
matched full SHA `5f690fe42ad7575c14fbc2c3cb88a09568faabb0` before Stage 4H began.
The worktree was clean except for ignored build/runtime artifacts.

## Architecture

Stage 4H adds a read-only intake layer before approved asset compilation:

```text
project-authored PNG
       -> external image-to-3D service
       -> immutable raw GLB + provenance hash
       -> bounded intake analyzer
          -> strict Stage 4F compatibility result
          -> Stage 4G applicability result
          -> DS byte projection
          -> accept/reject classification
```

The existing `assets.py`, `glb.py`, normalized typed IR, exact simplifier,
textures, world compiler, and emulator QA remain unchanged. A rejected candidate
is not inserted into the approved asset catalog or a world fixture.

The existing `make clean` rule was narrowed from deleting every directory named
`generated` to the three known build-output directories. The broad rule erased
the new canonical `assets/source/generated/` path during regression testing;
the raw GLB was restored from the generator cache only after its SHA-256 matched.
A permanent test now prevents that source-destruction regression.

## Generator and provenance

The concept image was produced for this project using the OpenAI image
generation tool from an explicit prompt for an isolated, boxy, low-poly stone
shrine/watchtower. The tool did not expose a model version. It is tracked at:

`assets/concepts/stage4h_generated_shrine_concept.png`

- dimensions: `1254 x 1254`, RGB PNG;
- size: `1,375,386` bytes;
- SHA-256:
  `06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f`.

The image contains no Pokémon, Nintendo model, logo, or retail texture.

The selected image-to-3D tool was the official public TripoSR Space:

- provider: Stability AI and Tripo AI;
- model: `stabilityai/TripoSR`;
- Space revision:
  `f84354eb350eb07a108faf33a6bc564d455f9764`;
- access: anonymous Gradio API, no credential or payment;
- settings: remove background, foreground ratio `0.85`, marching cubes `64`;
- output: GLB;
- model/code license evidence: MIT in the official repository/model card.

The project did not upload a ROM, extracted commercial asset, credential, or
private user data. `gradio_client==1.3.0` was installed only into ignored
`.venv`; no project dependency was introduced.

The tracked provenance record contains the exact concept prompt, settings,
hashes, revision, rights note, and candidate history:

`assets/provenance/stage4h_generated_shrine.json`

## Candidate attempts

1. Stable Fast 3D: its public anonymous Space exposed a suitable API, but
   bounded default attempts failed upstream and produced no artifact.
2. TripoSR at marching-cubes resolution `128`: generated a `571,492`-byte GLB,
   SHA-256 `62223647001388e7a4503f09a566da10660b8f782292f62328368726a5b33021`;
   rejected by the existing `262,144`-byte Stage 4F source limit.
3. TripoSR at resolution `64`: generated the canonical raw candidate. It is
   small enough for safe intake parsing but structurally incompatible.

The bounded attempts ended here; there was no open-ended candidate shopping.

## Canonical raw GLB

Path: `assets/source/generated/stage4h_generated_shrine_raw.glb`

- size: `134,740` bytes;
- SHA-256:
  `7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`;
- scene/node/mesh/primitive counts: `1 / 2 / 1 / 1`;
- materials/textures/images: `0 / 0 / 0`;
- animation/skin/morph counts: `0 / 0 / 0`;
- position count: `3,360`;
- referenced vertex count: `3,360`;
- index count: `19,992`;
- triangle count: `6,664`;
- attributes: `POSITION`, normalized `COLOR_0`;
- bounds minimum:
  `[-0.3970181942, -0.3725461960, -0.4249185324]`;
- bounds maximum:
  `[0.3447825909, 0.4532465935, 0.3675161600]`.

The raw file was copied from the generator output without mesh edits. The raw
hash is the canonical reproducibility boundary; generator reruns are not
claimed deterministic.

## Intake analyzer

`tools/pokeagent/generated_intake.py` validates:

- repository-contained manifest, concept, provenance, and raw-source paths;
- immutable concept/raw/provenance hash agreement;
- an 8 MiB analysis-only GLB size ceiling;
- GLB magic, version, declared length, JSON/BIN chunks, JSON root, embedded
  buffer length, accessor alignment/stride, and accessor byte bounds;
- structural counts and unsupported feature presence;
- accessor summaries, decoded index/position counts, finite position values,
  verified index bounds, computed geometry bounds, and material names;
- the actual strict Stage 4F parser result;
- Stage 4G exact-simplifier prerequisites;
- a conditional independent-triangle Nitro byte projection against the existing
  shape capacity.

It never loads external URIs, mutates the GLB, repairs geometry, decodes PBR
state, generates normals/UVs, or compiles a model.

CLI:

```bash
python -m tools.pokeagent asset intake \
  assets/manifests/stage4h_generated_shrine_intake.json --json
```

`--output` writes an ignored deterministic `intake-report.json`.

## Compatibility and DS budget result

Stage 4F compliance: **failed**.

Independent findings:

- two-node parent/child hierarchy instead of one leaf mesh node;
- no named material;
- missing authored `NORMAL`;
- missing authored `TEXCOORD_0`;
- unexpected `COLOR_0`;
- all three accessors exceed the Stage 4F element limit;
- `3,360` positions exceed the Stage 4G source budget of `128`;
- `6,664` triangles exceed its source face budget of `64`.

Conditional Nitro projection:

```text
12-byte primitive framing + 6,664 * 68 bytes/triangle = 453,164 bytes
verified shape-6 capacity                              =   1,068 bytes
overflow                                               = 452,096 bytes
```

The projection says what the existing encoder would require if normals and UVs
existed; the source cannot actually be encoded without them.

Stage 4G simplification: **not used and not applicable**. It requires valid
normalized typed IR and exact redundant coplanar patches. This candidate needs
hierarchy flattening, normal generation, UV generation, and approximate general
surface reduction before that boundary.

## Texture, scale, and collision

The intended mapping was the already-proven `prop_secondary` material with
project texture `stage4d_stone`; no new texture slot was allocated. No binding
was performed because the GLB has no source material or UV0.

The intake manifest records an intended `4 x 6 x 4`-tile presentation and an
intended `4 x 1 x 4` rectangular footprint. Scale normalization and collision
generation were not run because they occur after valid source parsing. No
collision claim is made.

## Binary, ROM, QA, and visual result

The GLB container itself passed safe intake-level binary validation. It did not
pass the Stage 4F mesh contract, so no display list, NSBMD, map member, NARC,
ARM9 patch, ROM, or gameplay scenario was produced.

This is not a missing test: building around this failure would require excluded
capabilities or validator weakening. Therefore Stage 4A gameplay QA is **not
applicable** for the rejected candidate.

A read-only diagnostic projection of the raw vertex-color mesh was inspected.
It is recognizably related to the concept: a squat stone structure, blue roof,
dark opening, and broadly similar proportions. It is also visibly lumpy and
irregular, with noisy faceting and softened architectural planes. The concept's
clean block masonry, planar roof, and crisp silhouette did not survive at a
quality/budget suitable for the current DS path. No in-game visual claim is
made.

## Determinism and mutation boundary

Two independent report writes from the tracked raw GLB matched byte-for-byte.

- semantic report SHA-256:
  `776a654889d6a16f4ef5a180aee4c636cf2e71fee30e79d65a07c196aee4ca86`;
- pretty report SHA-256:
  `abc04f245fc1caa48caef1c4f9b2ef2c9cabfd0d00eff828883751a941704c08`.

The immutable-boundary mutation test changes a temporary source/hash pairing
and proves that the manifest/provenance guard refuses mismatches with
`source_hash_mismatch`. A downstream geometry mutation was not attempted:
there is no valid typed IR or model output to mutate, and the canonical raw
generator artifact must remain unedited.

## Tests and regressions

Stage 4H adds tests for:

- exact canonical counts, bounds, hashes, reasons, and quality classification;
- no source modification during analysis;
- deterministic semantic/file reports;
- acceptance of an already-valid Stage 4F GLB through the same analyzer;
- unsafe paths, hash mismatch, malformed GLB, and CLI parsing;
- tracked concept/raw evidence.

The final command/result matrix is recorded below after completion.

| Check | Result |
|---|---|
| Stage 4H intake unit tests | 6 passed |
| Stage 4G simplification regression | clean ROM build passed; QA 15/15 through frame 8,809 |
| Stages 2--4G determinism | 13 fixtures, zero mismatches |
| Stages 4B--4G asset regressions | passed in full suite |
| Registry validation | passed, 12 namespaces / 34 resources |
| Full unit suite | 190 run, 187 passed / 3 opt-in integrations skipped |
| Preflight/artifact hygiene | passed; tracked diff contains no ROM/build/save/screenshot/log output |

The Stage 4G ROM regression reproduced SHA-256
`a249ca932bb31a4c7dd3c1824017987976e7d0db7c2a0a836e34a48eac377224`.
Its declarative plan remained
`5a135b532e17a12af094659bde63701de8ca637ac8519f56f10dc6a105db1423`;
all 15 assertions passed, including collision, walk-around, and 600 stable
frames. No Stage 4H gameplay scenario exists because the generated candidate
was rejected before world integration.

DeepSeek was not used. This work was direct byte/schema inspection and local
architecture; no advisory call materially reduced risk. Token use and cost are
both zero.

## Confirmed, inferred, unknown

### Confirmed by bytes and tests

- generator access and output hashes;
- canonical raw GLB structure and geometry counts;
- the Stage 4F rejection surface;
- conditional DS byte projection;
- Stage 4G inapplicability;
- deterministic intake reports and immutable-source guard.

### Confirmed only by visual diagnostic

- the raw reconstruction broadly resembles the shrine concept;
- its surface quality is too irregular for the current constrained DS path.

### Inferred

- native one-node, single-material, normal+UV, low-topology export would be the
  cleanest generator-side solution.

### Unknown/deferred

- which future generator can emit that contract directly;
- whether transform baking, authored-normal synthesis, UV creation, or
  approximate constrained simplification should be the next separately scoped
  preprocessing proof;
- external generator rerun determinism.

## Recommendation

Do not begin production asset generation. The next stage should first choose
one bounded compatibility gap based on real output evidence. The highest-value
gaps are authored normal/UV preparation and a conservative approximate
simplifier; hierarchy flattening alone would not address the 424x display-list
overflow. Preserve Stage 4F/4G validation as the acceptance contract.
