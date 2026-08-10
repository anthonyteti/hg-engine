# HGSS Stage 4U: official SPAR3D access and remesh contract

## Finding

SPAR3D could not be executed through an authorized official route on
2026-08-09. The official hosted Space was in `BUILD_ERROR`, while the official
model repository was gated and the environment had no existing Hugging Face
credential or cached weights.

Classification:

```text
SPAR3D_AUTHORIZED_EXECUTION_UNAVAILABLE
```

This is an access finding, not a topology or fidelity finding.

## Official identities

- Repository: `https://github.com/Stability-AI/stable-point-aware-3d`
- Code revision: `fdc311b16809e6a8adc2f5a3407ebb3db1a95bd1`
- Model: `stabilityai/stable-point-aware-3d`
- Model revision: `5699918cb34f55cd7d828493d2725f3038313761`
- Space: `stabilityai/stable-point-aware-3d`
- Space revision: `981f20868211097b5b980d7e2474400627f9e1ea`
- License metadata: `stabilityai-ai-community`
- Space state: `BUILD_ERROR`

Confidence: high. Revisions and runtime state came from official GitHub and
Hugging Face APIs. Gradio client initialization independently failed with the
same Space state. Gated model retrieval returned HTTP 401, and local credential
and model-cache checks were negative.

## Remesh semantics confirmed by source

Official code exposes triangle and quad remesh modes when their optional
dependencies are installed. Triangle mode uses `gpytoolbox`; face targets are
not hard face constraints. Both `run.py` and the Space convert a requested face
count to an approximate vertex count using:

```text
internal_vertex_target = requested_face_target // 2
```

The predeclared 1000/500/250/125 sweep would therefore pass approximate vertex
targets 500/250/125/62 into triangle remeshing. The official UI accepts target
counts from 0 through 20,000; CLI validation requires a positive integer.

Other current Space defaults are padding ratio `1.3`, guidance `3`, seed `0`,
and texture resolution `1024`. The UI exposes automatic background removal and
a no-crop option. No point-cloud editing was authorized for Stage 4U.

## Expected GLB semantics

Source inspection shows that generated/remeshed meshes are UV-unwrapped and
exported by Trimesh with normals, texture coordinates, a base-color texture,
roughness/metallic factors, and an optional normal texture. Actual GLB counts,
payload layout, extensions, and hashes remain unconfirmed because no candidate
could be generated.

Do not silently strip this appearance. A future authorized Stage 4U retry must
first record every native payload and explicitly label any geometry-only
projection `PROOF_ONLY_SOURCE_APPEARANCE_DISCARDED`.

## Evidence and reproduction

Official metadata checks:

```bash
git ls-remote \
  https://github.com/Stability-AI/stable-point-aware-3d.git \
  refs/heads/main

python - <<'PY'
from gradio_client import Client
Client("stabilityai/stable-point-aware-3d", verbose=False)
PY
```

The second command currently fails with the official Space's `BUILD_ERROR`.
Model access must not be tested by printing tokens. Use
`huggingface_hub.get_token()` only as a boolean check, then honor the gate.

Project concept evidence:

```text
assets/concepts/stage4h_generated_shrine_concept.png
06ef9543876681bd63d066b65f254dbe983a5f5bec112ba5dc128ce517e5644f
```

See `docs/STAGE_4U_TECHNICAL_REPORT.md` for the full access decision.

## Remaining unknowns

- Actual SPAR3D topology at targets 1000/500/250/125.
- Actual target-count deviation from requested values.
- Actual GLB scene, node, accessor, material, image, and extension layout.
- Raw silhouette fidelity against the concept and MC64 TripoSR reconstruction.
- Whether unchanged Stage 4O and Stage 4J can finish SPAR3D remeshes.

These unknowns require a future authorized official execution path. They are
not reasons to weaken any current asset-factory contract.
