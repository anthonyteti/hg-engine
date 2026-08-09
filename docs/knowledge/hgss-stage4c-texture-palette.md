# HGSS Stage 4C texture and palette ingestion

## Finding

A project-authored opaque 32 x 32 PNG can be compiled deterministically to
Nitro `GX_TEXFMT_PLTT16` texels plus a 16-entry BGR555 palette and rendered on
the Stage 4B imported shed. The proven integration is an exact-size,
hash-locked replacement of one existing texture/palette payload pair in the
area-data texture resource; it is not a general TEX0/NSBTX/material writer.

Confidence is **high for the exact US HeartGold revision, area-data bank 2,
`road01_r` slot, and opaque PLTT16 subset tested by source, binary parsing,
clean ROM build, and live rendering**.

## Runtime resource architecture

The generated map member's model begins with `BMD0` and contains `MDL0`; it
does not contain `TEX0`. Textures are loaded separately through area data:

```text
MapHeader.areaDataBank = 2
  -> fielddata/areadata/area_data (a/0/4/2), record 2
  -> area texture member 2 in a/0/4/4
  -> BTX0 / TEX0
  -> NNS_G3dGetTex + GF3dRender_AllocAndLoadTexResources
  -> GF3dRender_BindModelSet / NNS_G3dBindMdlSet
  -> material and texture/palette dictionaries bind by Nitro names
```

Evidence:

- `pret/pokeheartgold` revision
  `008257708bd41df5b8c9037e019088ba24df0a87`,
  `include/map_header.h`, defines `areaDataBank`;
- the same revision's `asm/overlay_01_021FB878.s`,
  `AreaDataManager_Load`, reads the area resource and archive ID `0x2C`, calls
  `NNS_G3dGetTex`, allocates texture resources, and binds loaded models;
- `src/gf_3d_render.c` confirms `NNS_G3dBindMdlSet` is the model/texture bind;
- pristine area-data record 2 is `00 00 02 00 00 00 01 01` and selects texture
  member 2;
- runtime screenshots show the project atlas on model material `road01_r`.

The decomp source was used as behavioral evidence, not copied. The project
implementation is a new bounded Python parser/patcher. The local HG-Engine
`nitrogfx` source is MIT licensed; Pillow 12.3.0 is MIT-CMU licensed and is the
PNG decoder. No Nintendo converter or `g3dcvtr` is required.

## Verified TEX0 target

Supported US HeartGold local inputs:

| Object | Verified value |
|---|---|
| pristine `a/0/4/4` SHA-256 | `6385837c11139c543884434a54768e7279b485214b7ca309cf8a670d8f98d647` |
| archive members | 106 |
| target member | 2 |
| pristine member SHA-256 | `bfecfce0640b92a69c32fe4339cafc5a77a088a668a66f67b12e6be8cf727de1` |
| member container | `BTX0`, one `TEX0` section |
| member bytes | 37,092 |
| texture dictionary entries | 67 |
| palette dictionary entries | 66 |
| texture entry | index 26, `road01_r` |
| texture metadata | format 3, 32 x 32, parameters `0x0D20` |
| texture payload | offset 19,124, 512 bytes |
| palette entry | index 26, `road01_r`, flag 0 |
| palette payload | offset 36,180, 32 bytes |

Stage 4B assigns `prop` to map-model shape 1 / material 18 / material name
`road01_r`. Shape 1's display list is replaced by the proof asset, so this map
uses the target name only for that prop; the ground remains shape 5 / material
12 / `grass01`. The Stage 4C fixture therefore dedicates the bounded
`road01_r` payload pair without corrupting its terrain.

The patcher requires both archive and member hashes before writing. It parses
the dictionaries, proves the entry dimensions/format and exact capacities,
replaces only the two payload ranges, reparses the result, and requires the
entire parsed dictionary/offset/capacity layout to remain equal. The rebuilt
NARC retains 106 members and changes only member 2. The final ROM contains the
generated `a/0/4/4` byte-for-byte.

## Canonical image and manifest subset

Asset manifest schema 2 extends Stage 4B with exactly one `textures` entry and
one source-material mapping of `{alias, texture}`. The tracked identity
`stage4c_shed_atlas` is project-local; it does not allocate an HGSS registry
ID. Its declaration owns:

- repository-relative PNG source under `assets/textures/`;
- source format `png`;
- Nitro format `nitro_pltt16_4bpp`;
- exact dimensions `[32, 32]`;
- opaque alpha policy;
- exact BGR555 palette policy;
- revision/hash-locked archive, member, texture entry, and palette entry.

Only PNG modes RGB and fully opaque RGBA are accepted. The decoded image must
be 32 x 32 and at most 128 KiB. Other image formats, dimensions, modes,
transparency, more than 16 encoded colors, multiple textures/materials, and
unverified slots fail before ROM generation with stable error codes.

## Texel and palette encoding

The sole supported texture mode is Nitro format field 3,
`GX_TEXFMT_PLTT16`:

- 4 bits per texel;
- 1,024 texels produce exactly 512 bytes;
- row-major source order;
- the left/even pixel occupies the low nibble and the next pixel the high
  nibble;
- 16 little-endian two-byte palette slots;
- unused slots are zero-filled;
- the proof is fully opaque and does not depend on transparent index behavior.

RGB888 channels are truncated to five bits and packed as:

```text
(R >> 3) | ((G >> 3) << 5) | ((B >> 3) << 10)
```

Bit 15 is clear. Golden tests prove red `0x001F`, green `0x03E0`, blue
`0x7C00`, and white `0x7FFF`. The encoder collects exact post-BGR555 colors,
sorts their numeric values ascending, maps pixels through that stable palette,
and rejects more than 16 colors. There is no lossy quantizer in the proven
subset. This makes tie-breaking and output independent of hash/dictionary
iteration.

## UV convention

Stage 4B stores normalized OBJ UVs. For schema-2 textured assets the compiler
converts them at primitive construction:

```text
Nitro S = OBJ u * 32 texels
Nitro T = (1 - OBJ v) * 32 texels
```

The existing display-list encoder then writes the Nitro `TEXCOORD` command in
1/16-texel fixed-point units. The V inversion reconciles OBJ's lower-left
origin with PNG/Nitro row zero at the top. The tracked atlas deliberately uses
different roof and wall halves plus directional planks/trim so a flipped,
mirrored, or mis-scaled mapping would be visually obvious.

## Deterministic artifacts

Two clean roots matched across all 34 generated Stage 4C artifacts. Important
SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| canonical PNG | `146849af64f73c999221d282c71123d43846bea9a379b51afe0edf38a0463f21` |
| semantic image IR | `af483190bf784584bd04ed6dab3d2fbd533b2d76512dc62ac9314d8ccb4689cc` |
| PLTT16 texels | `f05679df7e820caf2b0047b3853fb0c9df496029a8af9c7a9e5c50edfc7fa3e6` |
| BGR555 palette | `c8c051bb3ab1b6191f7f5f2160c1bfca417b31afaa50cca293b1e2c7ab9d594e` |
| patched BTX0 member | `d0d25765560901445426c64fd4f7d9c462f35929eb8cda0c354be813de4c9a72` |
| rebuilt `a/0/4/4` | `4b293128edef69177c4ebb4abdbd66b501519f87b084e6db911c45abf880ed2c` |
| asset display list | `0467b7a3ac556c1852fdf55371b929bf4668877fd404a55606406297d77adf60` |
| transformed NSBMD | `400e80d4040a19b5bcb540f4841a5b5d11cb9d4e4a56ddd233164f0c5cd909bb` |
| PER | `b2adea8887e2b12949e040caec8843e06fb58c186bb770c321ae93dbe2e572b5` |
| map member | `487aa756ca5d86086da5a56d98d48f6bb858ba9043777d1ebec6c810aecf4c63` |

The rebuilt archive differs in 516 byte positions, all inside the allowed
512-byte texture and 32-byte palette ranges; equal old/new values account for
the remainder of those ranges.

## Source mutation

A temporary one-pixel roof mutation changed the source hash to
`294b34d3ed2d7425edb418dd057d1ac7011cf52732e1ac38282abad1c8ae22eb`,
the semantic image IR to
`f6be870fc2724b5b5604da3a13dcedeb4dfa9862b938e3e1151c0f9c6cbd9a39`,
the texel stream to
`1fe55b9f5778508d7f5abd2152949b34e1ffbf67104ee1f2f389de0c1b27330a`,
and the patched container to
`081271d74b1f1b860a3612d4fdd63eb00fbf8fd766ed3df1ad42a1c8590e1b1c`.

The palette stayed unchanged because the mutation used an already-present
atlas color. Asset identity, display-list hash, collision hash, PER, and all
world resource IDs stayed unchanged. The tracked canonical PNG was never
modified.

## Runtime and visual result

The final clean ROM SHA-256 is
`2235a38c5eb998a2dd5dfc2e9d369b7caaea645e5cc2146e5dfdeb4f5e5dc947`.
The 21-step Stage 4A scenario passed 14/14 assertions: controlled map/header/
member identity, approach, two captures, footprint collision, adjacent/rear
movement, and 600-frame stability.

Codex inspected both final screenshots. The shed has a recognizable red/
magenta shingle roof, yellow trim, brown plank walls/door, and cyan accent. Roof
and wall atlas halves land on their intended faces; U and V are coherent from
front and rear, the mesh is not mirrored/exploded, the object is upright and
grounded, and neighboring terrain is intact. This is visibly distinct from
Stage 4B's dark-green `road01_r` shell.

## Battery-save hardening

Stage 4A QA runs now set `XDG_CONFIG_HOME` to an ignored scenario-owned
`build/qa/<scenario>/desmume-config`. `new_game_controlled` clears only that
private directory; `continue_existing_save` preserves its own directory.
Legacy specialized world-emulator subprocesses now use an equivalent
proof-owned directory. Stage 3E2's specialized save proof and Stage 4A's 19/19
assertion save/reset/Continue scenario both pass with separate private battery
files. The global save hash remained unchanged across the hardened reruns.

One pre-hardening Stage 3E2 regression invocation in this development session
did update the old global `~/.config/desmume/test.dsv`; this exposed and caused
the legacy-runner fix. Its post-update hash was preserved across every
subsequent isolated run. No tracked artifact contains battery data.

## Confirmed, inferred, and unknown

Confirmed by source, binary validation, build, and runtime:

- separate area texture loading and name-based model binding;
- one 32 x 32 PLTT16 texture/palette payload replacement;
- exact BGR555/nibble encoding, dictionary preservation, NARC repacking;
- visible UV/material binding, collision, movement, and stability;
- deterministic image-to-ROM propagation and isolated QA battery state.

Confirmed by source and binary tests only:

- stable rejection of malformed dictionaries and all declared failure modes;
- fixed payload offsets/capacities for the hash-locked pristine member;
- one-pixel mutation propagation without geometry/resource renumbering.

Unknown or deliberately unsupported:

- other ROM revisions, area-data banks, TEX0/NSBTX members, texture slots or
  dimensions;
- multiple/new texture or material dictionary entries, payload relocation,
  general TEX0/NSBTX generation;
- PLTT4, PLTT256, 4x4-compressed, direct-color, A3I5/A5I3, transparency,
  palette sharing/allocation, arbitrary material state, texture animation;
- lossy quantization, triangles/N-gons, GLB, simplification, BLD, image-to-3D,
  or production asset generation.
