# Stage 4C technical report: project-authored texture and palette pipeline

## Verdict

`STAGE_4C_TEXTURE_PIPELINE_PASSED`

A tracked project-authored PNG now compiles deterministically into opaque
Nitro PLTT16 texels and a BGR555 palette, patches one hash-verified area-texture
payload pair, binds through the existing `road01_r` material name to the Stage
4B imported shed, survives HG-Engine ROM repacking byte-for-byte, and renders
correctly in headless HeartGold. Collision and geometry remain synchronized,
the reusable Stage 4A scenario passes, and Codex visually verified the atlas.

## Stage 4B checkpoint

Stage 4C began only after the intentional Stage 4B source, project-authored
asset, fixture, scenario, tests, Make integration, and documentation were
staged explicitly, checked, committed, pushed, and remotely verified:

- commit: `a960769c6 Add Stage 4B external environment asset pipeline`;
- full commit: `a960769c63b96e0e939f5b809b8fb5688e3bd163`;
- branch: `main`;
- local `HEAD`, `origin/main`, and remote main agreed;
- worktree was clean before Stage 4C implementation.

No ROM, generated NARC, base/build output, screenshot, save/state, normalized
mesh, display list, extracted asset, log, credential, or other unsafe artifact
entered that checkpoint.

## Canonical proof source

The sole proof texture is
`assets/textures/stage4c_shed_atlas.png`, a project-authored CC0 32 x 32 RGB
PNG with nine colors. Its top half is a directional red/magenta roof pattern
with contrasting trim; the lower half contains brown/tan plank and door/window
features. This makes wrong slot selection, U/V inversion, mirroring, or atlas
scale visible.

`stage4c_textured_shed.obj` preserves the Stage 4B shed geometry: 16 positions,
six normals, 12 quads, one source material, the same 4.5 x 3.0 x 3.5-tile
bounds, and the same rectangular collision proxy. It adds eight purposeful
atlas UVs. Triangles and N-gons remain unsupported.

Manifest schema 2 extends, rather than replaces, the Stage 4B boundary. It
declares one project-local texture symbol, PNG path/format, exact Nitro format,
dimensions, opaque/quantization policy, hash-locked container target, and
source-material mapping `{alias: prop, texture: stage4c_shed_atlas}`. The
schema-9 world fixture resolves the existing Stage 3C symbolic world graph and
places the asset symbolically at `(16,16)`; no raw author-managed world IDs or
new registry namespace were introduced.

## Compiler architecture

```text
tracked PNG + schema-2 asset manifest
  -> strict PNG validation (Pillow)
  -> deterministic image IR
  -> RGB888 to BGR555 exact palette
  -> PLTT16 row-major 4bpp texels
  -> hash-locked BTX0/TEX0 payload replacement
  -> rebuilt area texture NARC a/0/4/4
  -> Stage 4B OBJ IR + atlas-aware TEXCOORD display list
  -> existing map member / PER / BDHC / world serializers
  -> HG-Engine build
  -> Stage 4A QA and visual review
```

`tools.pokeagent.textures` owns image validation/IR, BGR555 and texel encoding,
the bounded BTX0/TEX0 dictionary parser, exact payload patch, and generated
texture reports. `assets.py` owns manifest binding and converts OBJ UVs to
Nitro texel coordinates. `world.py` only assembles the compiled products and
validates/rebuilds the NARC. Low-level image/container policy is not spread
through world serializers.

CLI commands are:

```bash
python -m tools.pokeagent texture validate assets/manifests/stage4c_textured_shed.json --json
python -m tools.pokeagent texture inspect assets/manifests/stage4c_textured_shed.json --json
python -m tools.pokeagent texture compile assets/manifests/stage4c_textured_shed.json --json
```

Ignored output includes image IR, texels, palette, texture report, normalized
mesh, display list, collision, patched container/NARC validation, world
components, and semantic hashes.

## Texture format and image policy

The only implemented format is verified Nitro format field 3,
`GX_TEXFMT_PLTT16`: 4 bits per texel, 32 x 32, 512 texture bytes, and 16
little-endian BGR555 palette entries (32 bytes). Row order is PNG top-to-bottom;
the left/even pixel is the low nibble. RGB888 becomes
`R5 | G5<<5 | B5<<10`; bit 15 stays clear.

Only RGB and fully opaque RGBA PNGs are accepted. Transparency is rejected.
The proof performs exact deterministic conversion: post-BGR555 colors are
sorted numerically and used as stable palette order, with zero-filled unused
entries. More than 16 encoded colors fails; no lossy quantization or random
tie-breaking is implemented. The canonical PNG has nine encoded colors.

OBJ's lower-left V convention is converted to the PNG/Nitro top-row convention
with `S=u*32`, `T=(1-v)*32`, then encoded by the existing Nitro command path in
1/16 texel units.

## Template and container architecture

Source/binary inspection established that the map NSBMD is an MDL0-only BMD0;
texture/palette bytes do not live inside it. `MapHeader.areaDataBank=2`
selects area data, which makes `AreaDataManager_Load` read member 2 of
`a/0/4/4`, obtain its TEX0, allocate VRAM, and name-bind it to loaded map
models.

The supported pristine archive has 106 members and SHA-256
`6385837c11139c543884434a54768e7279b485214b7ca309cf8a670d8f98d647`.
Member 2 is a 37,092-byte BTX0/TEX0 with 67 textures and 66 palettes, SHA-256
`bfecfce0640b92a69c32fe4339cafc5a77a088a668a66f67b12e6be8cf727de1`.
The dedicated target is texture index 26 `road01_r`, format 3, 32 x 32, 512
bytes at offset 19,124, plus palette index 26 `road01_r`, 32 bytes at offset
36,180.

The project preserves every dictionary, offset, size, material, and unrelated
payload. It changes only those two exact-size payload ranges. The transformed
member reparses with an identical layout; the NARC retains all 106 members and
only member 2 changes. The rebuilt NARC hash is
`4b293128edef69177c4ebb4abdbd66b501519f87b084e6db911c45abf880ed2c`,
and the final ROM's archive is byte-identical to that generated file.

Stage 4B's `prop` binding remains shape 1 / material 18 / `road01_r`; ground is
shape 5 / material 12 / `grass01`. Runtime source uses
`NNS_G3dBindMdlSet`, and the visible result independently confirms the intended
name binding. No new material/texture dictionary entry, material state, palette
allocator, or arbitrary NSBTX writer exists.

## Binary, runtime, and visual proof

Binary validation proved:

- texture/palette entries exist at the expected indices and offsets;
- format, dimensions, byte lengths, and palette capacity match exactly;
- the patched container retains identical parsed dictionaries/layout;
- all changes are inside the two allowed payload ranges;
- all other NARC members are byte-identical;
- HG-Engine repacking preserves the rebuilt NARC byte-for-byte.

The final clean ROM SHA-256 is
`2235a38c5eb998a2dd5dfc2e9d369b7caaea645e5cc2146e5dfdeb4f5e5dc947`.
The tracked 21-step scenario has plan SHA-256
`090cf1b2387c4dfb459a56775bf9f5a85a78bc9822f5078d0f297e1b538cf44a`
and passed 14/14 assertions: ROM/map/header/member/height/event identity,
approach, named captures, blocked footprint, valid adjacent/rear traversal,
and another 600 stable frames.

Codex inspected both final 256 x 384 screenshots. The project-authored red/
magenta roof and brown/tan wall pattern are unmistakable and replace the old
dark-green appearance. Roof and wall regions are on the intended faces, U and
V direction are coherent in both views, colors are recognizable, the asset is
upright and grounded, faces are present, geometry is not exploded, scale is
plausible, and neighboring terrain is uncorrupted. The approach/rear images
contain 44/48 unique colors and have SHA-256 values
`d8227416e2e1bc96554f4ad59b0f574ce29d37e135b41911152fa15a79a246ba`
and `1a7feda3dabe055405448cc6703da58b6c83d037e15dcfcad0bd4d86b30a39a7`.
Hashes support traceability; pass/fail did not depend on exact screenshot hash.

## Determinism and mutation

Two clean roots matched byte-for-byte across all 34 Stage 4C artifacts with
zero mismatches. Key hashes are:

| Artifact | SHA-256 |
|---|---|
| PNG | `146849af64f73c999221d282c71123d43846bea9a379b51afe0edf38a0463f21` |
| image IR semantics | `af483190bf784584bd04ed6dab3d2fbd533b2d76512dc62ac9314d8ccb4689cc` |
| texture | `f05679df7e820caf2b0047b3853fb0c9df496029a8af9c7a9e5c50edfc7fa3e6` |
| palette | `c8c051bb3ab1b6191f7f5f2160c1bfca417b31afaa50cca293b1e2c7ab9d594e` |
| patched member | `d0d25765560901445426c64fd4f7d9c462f35929eb8cda0c354be813de4c9a72` |
| display list | `0467b7a3ac556c1852fdf55371b929bf4668877fd404a55606406297d77adf60` |
| NSBMD | `400e80d4040a19b5bcb540f4841a5b5d11cb9d4e4a56ddd233164f0c5cd909bb` |
| PER | `b2adea8887e2b12949e040caec8843e06fb58c186bb770c321ae93dbe2e572b5` |
| BDHC | `07584c4215ceed2216ba6928d51273b36fa3345815e076390ed5e8ca340980e1` |
| map member | `487aa756ca5d86086da5a56d98d48f6bb858ba9043777d1ebec6c810aecf4c63` |

A temporary one-pixel roof mutation changed PNG, image IR, texel, patched
container, and ultimately model-container hashes. It preserved the texture and
asset symbols, Stage 4B display-list hash, collision hash, PER, and all world
IDs. Because it substituted an existing color, the palette correctly stayed
unchanged. The canonical tracked PNG was never altered.

## Validation and tests

Stable failures cover missing/escaping/non-PNG/invalid sources; unsupported
dimensions/modes/format/quantization/transparency; palette overflow; malformed
BTX0/TEX0 metadata; hash, slot, payload-length, dictionary-layout, texture, and
palette mismatches; duplicate texture IDs; bounded slot/material conflicts;
missing/invalid material-to-texture mappings; and deterministic mutation/
ordering behavior.

The final full suite ran 151 tests: 148 passed and three opt-in live/network
integration gates skipped as designed. Registry validation passed 11
namespaces / 32 resources. Preflight passed all command, Python, ROM,
git-hygiene, system, and Docker-context groups.

Clean build/runtime regressions passed:

- Stage 2: 11/11 specialized checks and Stage 4A basic scenario 9/9;
- Stage 3A: 14/14 height/collision checks;
- Stage 3B: 21/21 native multi-map checks;
- Stage 3C: 21/21 symbolic-registry runtime checks;
- Stage 3D: 14/14 specialized checks and Stage 4A elevation 13/13;
- Stage 3E1: 17/17 appended-resource runtime checks;
- Stage 3E2: 18/18 expanded-header checks and Stage 4A real persistence 19/19;
- Stage 4B: clean ROM hash unchanged and QA 14/14;
- Stage 4C: clean ROM build and QA 14/14.

## QA battery isolation

The reusable QA runner now sets an ignored scenario-owned `XDG_CONFIG_HOME`.
Fresh-entry scenarios clear only that private directory; preserve-entry
scenarios may intentionally reuse it. The legacy specialized world-emulator
runner received the same private config boundary. Stage 3E2's specialized and
declarative real-save tests pass with separate private `.dsv` files and the
global save hash remains unchanged across the hardened reruns.

One diagnostic Stage 3E2 run before the legacy runner was hardened changed the
pre-existing global `test.dsv`; this was the direct evidence that extended the
fix beyond the Stage 4A runner. Subsequent reruns are isolated. No save is
tracked or included in reports.

## Evidence, licensing, and DeepSeek

Primary/source evidence was inspected at `pret/pokeheartgold` revision
`008257708bd41df5b8c9037e019088ba24df0a87`. The decomp provided runtime and
SDK-API evidence only; no code was copied. The project-owned parser/encoder is
implemented independently. HG-Engine's local `nitrogfx` source is MIT licensed;
Pillow 12.3.0 is MIT-CMU licensed. The PNG/OBJ are project-authored CC0. Local
retail-derived template/archive bytes remain ignored and hash-locked; generated
ROM/NARC/model outputs remain ignored. No proprietary converter, `g3dcvtr`, or
GUI is required.

No DeepSeek task was necessary. Codex verified source, dictionaries, offsets,
golden color bytes, mutation propagation, clean builds, ROM-contained archive,
live gameplay, screenshots, and regressions directly. Usage: 0 tokens;
estimated cost: `$0`.

## Boundaries and recommendation

The proof is deliberately one opaque 32 x 32 PLTT16 atlas in one fixed
`road01_r` texture/palette slot of one hash-locked area resource. It does not
support other texture modes/dimensions, transparency, lossy quantization,
multiple textures/materials, dictionary extension/relocation, new material
properties, palette sharing, general TEX0/NSBTX authoring, triangles, GLB,
simplification, BLD, image-to-3D, asset kits, or production content.

The result supports a separately scoped Stage 4D, but that next stage should
choose one bounded capability and preserve this exact manifest/image IR,
revision-lock, binary validation, collision, deterministic-build, and visual-QA
boundary. Stage 4D has not begun.
