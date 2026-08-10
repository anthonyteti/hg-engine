# Stage 4U technical report: official SPAR3D access gate

## Verdict

```text
STAGE_4U_GENERATOR_EXPERIMENT_BLOCKED
SPAR3D_AUTHORIZED_EXECUTION_UNAVAILABLE
STAGE_4_ASSET_INFRASTRUCTURE_HAS_SPECIFIC_BLOCKER
```

Stage 4U stopped at its required access gate. The official Stability AI hosted
Space is currently in `BUILD_ERROR`; the official model is gated; this
environment has no Hugging Face credential, accepted model access, or cached
SPAR3D weights. No unofficial Space, mirror, account creation, credential
request, or alternate generator was used.

This is not topology evidence against SPAR3D. No SPAR3D candidate was generated,
so raw topology, fidelity, Q/R/O/P/F/J/I, ROM, QA, and visual gates were not
reached.

## Stage 4T checkpoint

Stage 4T was committed and pushed before Stage 4U began:

```text
2a5d7d4e5043f1f82aaa0e7b0250372d9ff87f81
Add Stage 4T TripoSR topology experiment
```

Local `HEAD`, `origin/main`, and remote `refs/heads/main` matched, and the
worktree was clean.

## Official SPAR3D identities

The only sources inspected were official Stability AI properties:

- code repository:
  `https://github.com/Stability-AI/stable-point-aware-3d`;
- repository `main` revision at inspection:
  `fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1`;
- model identifier: `stabilityai/stable-point-aware-3d`;
- model revision:
  `5699918cb34f55cd7d828493d2725f3038313761`;
- official Space: `stabilityai/stable-point-aware-3d`;
- Space revision:
  `981f20868211097b5b980d7e2474400627f9e1ea`;
- Space SDK: Gradio `4.43.0`;
- Space runtime state: `BUILD_ERROR`, requested hardware `l4x1`;
- model gating: Hugging Face `auto` gate with contact/license acceptance;
- license: Stability AI Community License
  (`stabilityai-ai-community`, model-card `license: other` plus `LICENSE.md`).

The Community License allows research/non-commercial use and limited commercial
use subject to its terms; organizations above its stated annual-revenue limit
need an enterprise license. Stage 4U made no license acceptance on the user's
behalf.

## Official execution paths

The official repository documents:

1. the official Gradio Space;
2. local `run.py` inference after obtaining gated Hugging Face access;
3. local Gradio inference;
4. a ComfyUI extension using the same official model.

None was authorized and usable here:

- `gradio_client.Client("stabilityai/stable-point-aware-3d")` fails before API
  discovery because the Space is in `BUILD_ERROR`;
- no `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN` is present;
- `huggingface_hub.get_token()` returns no cached login;
- direct retrieval of gated model content returns HTTP `401`;
- no local `config.yaml`/`model.safetensors` cache exists;
- the local RTX 3050 Ti exposes 4,096 MiB VRAM, below the repository's
  documented approximately 7 GiB low-VRAM mode and 10.5 GiB default mode.

CPU execution exists in source, but without authorized model weights it is not
an execution path. The repository also warns that CPU inference is very slow.

## Actual remeshing contract

Source inspection confirms the prompt's topology hypothesis is mechanically
supported by official code, but it could not be executed.

- Remesh choices are conditionally exposed as `none`, `triangle`, and `quad`.
- Triangle remeshing requires `gpytoolbox` and uses decimation followed by the
  Botsch-Kobbelt remesher.
- Quad remeshing requires `pynanoinstantmeshes`; GLB export triangulates it.
- The UI exposes `Keep Vertex Count`, `Target Vertex Count`, and
  `Target Face Count`.
- The UI target slider spans `0..20000`, default `2000`; CLI targets must be
  positive.
- A requested face target is converted to an approximate vertex target using
  integer `target_count // 2`; the remesher aims for, but does not guarantee,
  the count.

Therefore the predeclared face targets would have been interpreted as:

| Requested faces | Internal approximate vertex target |
|---:|---:|
| 1,000 | 500 |
| 500 | 250 |
| 250 | 125 |
| 125 | 62 |

No additional target was selected.

## Other exposed controls

The current official Space source exposes:

- automatic background removal unless a usable alpha channel is supplied;
- no-crop toggle;
- padding/foreground ratio `1.0..2.0`, default `1.3`, step `0.05`;
- guidance `1..10`, default `3`, step `1`;
- seed `0..10000`, default `0`, step `1`;
- texture size `512..2048`, default `1024`, step `256`;
- optional point-cloud upload/editing.

The CLI's actual foreground-ratio default is `1.3`, although its help text says
`0.85`; the Space and executable default agree on `1.3`. Had generation been
available, Stage 4U would have fixed the official UI defaults across all four
triangle-remesh targets and performed no point-cloud edits.

## Expected output structure from source inspection

The official implementation exports a `trimesh.Trimesh` as GLB with normals.
Before export, the remeshed mesh is UV-unwrapped, UV seams duplicate attribute
vertices, and the system constructs `TextureVisuals` with a PBR material:

- `POSITION` and triangle indices;
- generated vertex normals;
- generated UV coordinates;
- base-color texture;
- scalar roughness and metallic factors;
- optional normal texture;
- GLB export through Trimesh.

This is source-confirmed expected behavior, not an observed Stage 4U candidate
structure. Scene/node/primitive/accessor counts, embedding details, extensions,
and actual payload hashes remain unknown because no output was generated.

Any later authorized run must inspect these fields independently before using a
proof-only geometry projection. Stage 4U created no appearance-discard policy.

## Fixed input and sweep disposition

The unchanged project-owned concept remains:

```text
assets/concepts/stage4h_generated_shrine_concept.png
SHA-256:
06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f
```

The authorized targets were `1000`, `500`, `250`, and `125` faces. All four are
recorded as `not attempted: authorized execution unavailable`. Consequently:

| Target | Actual faces | Actual positions | Components | Boundary | Raw IoU | Q | R | O | P | F | Pre-J | Post-J | ROM | Visual |
|---:|---:|---:|---:|---|---:|---|---|---|---|---|---:|---:|---|---|
| 1000 | — | — | — | — | — | not run | not run | not run | no | no | — | — | no | not reached |
| 500 | — | — | — | — | — | not run | not run | not run | no | no | — | — | no | not reached |
| 250 | — | — | — | — | — | not run | not run | not run | no | no | — | — | no | not reached |
| 125 | — | — | — | — | — | not run | not run | not run | no | no | — | — | no | not reached |

No raw candidate hash, processed-input hash, generation duration, geometry
projection, selected candidate, model, ROM, screenshot, or runtime visual
classification exists.

## Pipeline and determinism result

Because generation never occurred:

- native appearance payloads: unavailable;
- `PROOF_ONLY_SOURCE_APPEARANCE_DISCARDED`: not applied;
- raw topology and fidelity: unavailable;
- Stage 4Q/R/O/P/F/J/I: not run;
- pre/post-J bytes: unavailable;
- two-root candidate processing: not applicable;
- Stage 4A QA and visual classification: not reached.

The deterministic boundary remains the unchanged concept and official metadata
inspection. No partial generator output was produced or preserved.

## Historical invariants and regressions

Stage 4H remains immutable at
`7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60`
with its historical rejection. Stage 4S remains the failed MC64 kill gate.
Stage 4T remains the committed MC48/MC32 topology experiment. No prior source,
manifest, canonical hash, threshold, capacity, or runtime asset changed.

The full existing unit suite passed: 316 tests, with three expected opt-in
integration skips. Preflight passed all 58 checks (12 commands, four Python
packages, one system dependency, two ROM identities, 12 git-hygiene checks,
and 27 Docker-context checks). DeepSeek was not used; token usage and cost are
zero.

## Exact blocker and recommendation

The exact blocker is not SPAR3D topology. It is the absence of an authorized,
working official execution path:

```text
official Space BUILD_ERROR
+ gated official model
+ no existing accepted credential
+ no local authorized weights
= no lawful executable candidate source
```

Do not infer `SPAR3D_TOPOLOGY_INCOMPATIBLE`. Resume this exact predeclared sweep
only in a separately authorized task after either the official Space is running
or the environment already has accepted official model access and suitable
hardware. Do not substitute a mirror, add topology repair, tune TripoSR, or
begin Stage 5 automatically.
