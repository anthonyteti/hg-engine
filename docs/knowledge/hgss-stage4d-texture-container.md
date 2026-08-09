# HGSS Stage 4D project texture-container allocation

## Finding

US HeartGold can load a newly appended area-data record and a newly appended
area-texture BTX0 member through the normal `MapHeader.areaDataBank` path. A
project-owned member derived from hash-locked TEX0 layout metadata can carry
multiple independently compiled PLTT16 texture/palette payloads at once while
the complete retail archive prefix remains byte-identical.

Confidence is **high for the exact US revision, appended member 106, the three
verified 32 x 32 PLTT16 slot pairs, and the material names tested by binary
validation, clean ROM build, and live rendering**. This is a bounded project
container allocator, not a general TEX0 dictionary writer.

## Runtime path and append boundary

```text
map header areaDataBank = 106
  -> appended a/0/4/2 member 106
     {buildings=0, texture=106, dynamic=0xffff, area=1, light=1}
  -> appended a/0/4/4 member 106
  -> NNS_G3dGetTex / texture VRAM allocation
  -> model binding by Nitro texture and palette resource names
```

Both pristine archives contain 106 members. The supported hashes are:

| Archive | SHA-256 |
|---|---|
| area data `a/0/4/2` | `991506d5626fee587e4bf27042ae7b2945e167b89d6ec9f2d834d29e7476d58f` |
| area textures `a/0/4/4` | `6385837c11139c543884434a54768e7279b485214b7ca309cf8a670d8f98d647` |
| metadata template member 2 | `bfecfce0640b92a69c32fe4339cafc5a77a088a668a66f67b12e6be8cf727de1` |

The generated archives contain 107 members. Members 0--105 remain
byte-identical. The project area record is
`00 00 6a 00 ff ff 01 01`; its SHA-256 is
`1bf3ebfe4782140fe4ae3894b221ce8fa215b342ad9b5b7a81d4e104f365d515`.

`pret/pokeheartgold` revision
`008257708bd41df5b8c9037e019088ba24df0a87` confirms that field map setup
passes `MapHeader_GetAreaDataBank(mapId)` to `AreaDataManager_Alloc`, obtains
the map texture through `AreaDataManager_GetMapTexture`, and loads/binds it
through the field texture manager. DSPRE revision
`d86737dfccaec7a603a6f27474180a49945158a6` was used only as corroborating
format evidence for the eight-byte HGSS area record and append behavior; no
code was copied.

## Bounded BTX0/TEX0 strategy

The project does not redistribute or clone retail pixels. It uses member 2
only as a local, hash-verified metadata template:

1. parse BTX0 and its sole TEX0 section;
2. preserve header, dictionaries, entry metadata, names, offsets, and sizes;
3. zero all 32,000 texture-payload bytes and all 1,520 palette-payload bytes;
4. write only centrally allocated project texels/palettes;
5. reopen with the independent bounded parser;
6. prove metadata byte identity and non-overlapping in-bounds payloads.

The parser covers the Nitro resource subset required here: BTX0/TEX0 lengths,
texture and palette resource dictionaries, names, PLTT16 size parameters,
eight-byte-relative payload offsets, bounds, and unique names. Apicula revision
`3d4e91e14045392a49c89e86dab8cb936225588c` (0BSD) independently confirms the
TEX0 header fields and the texture `(u32,u32)` / palette `(u16,u16)` resource
records. The implementation is project-owned Python, not copied editor code.

The generated member is 37,092 bytes and retains 67 texture plus 66 palette
dictionary entries. Its SHA-256 is
`8dcfd7074afbb6c5c37e03bf57b45e083292c17824cf5d0e4ef6d67e7bc02a9d`.
The rebuilt texture NARC SHA-256 is
`249cb771f4d8b629b37e1f4e2b8a6c46720a7686b578de3aad6839d5f20bec2f`;
the rebuilt area-data NARC SHA-256 is
`b70995e24989d25a2cd6dc797479eefd636fe4ac4dbf807b6b691f7673449ec2`.

## Project identities and physical bindings

`assets/texture_catalog.json` is the persistent allocation record. Authors use
project symbols; the compiler owns physical Nitro names and indices:

| Allocation | Project symbol | Texture name/index | Palette name/index | Consumer |
|---:|---|---|---|---|
| 0 | `stage4d_ground` | `grass01gs` / 21 | `grass01` / 21 | shape 5, material 12 |
| 1 | `stage4d_wood` | `road01_r` / 26 | `road01_r` / 26 | shape 1, material 18 |
| 2 | `stage4d_stone` | `road01` / 25 | `road01` / 25 | shape 6, material 17 |

The inherited names are implementation-level name-binding keys; they do not
grant ownership of the same retail resources. Their payloads live only in the
new project member. Manifests contain symbols such as `stage4d_wood`, never
physical indices. The allocation integer, slot pair, and physical names are
persistent catalog records, so unrelated additions do not renumber existing
entries. Duplicate symbols, names, allocations, writable slot pairs, gaps,
unsupported revisions, retail member targets, missing bindings, overflow,
malformed dictionaries, invalid offsets/alignment, and overlapping payloads
fail deterministically.

This policy can grow only through additional hash-verified compatible slot
pairs in this metadata layout. It does not yet create or rename dictionary
entries. That bounded capacity is materially more scalable and legally cleaner
than replacing one retail NARC member per asset, but it is not an unlimited
texture namespace.

## Confirmed, inferred, and unknown

Confirmed by source, binary validation, build, and runtime:

- `areaDataBank=106` loads appended area-data and texture members;
- two prop textures plus one project ground texture coexist in one member;
- wood and stone materials bind to different project payloads simultaneously;
- retail NARC prefixes, unrelated members, and terrain remain intact;
- collision, movement, deterministic generation, and ROM repacking pass.

Confirmed by source and binary tests only:

- stable catalog allocation when a fourth unrelated record is appended;
- parser rejection for malformed dictionaries, offsets, slot collisions, and
  unsupported revision/member provenance;
- all inherited payload bytes are zero rather than copied.

Unknown or deliberately unsupported:

- rebuilding Patricia dictionaries, arbitrary physical names, new material
  state, or payload relocation outside the existing layout;
- capacity beyond explicitly cataloged compatible slot pairs;
- other dimensions/formats, transparency, palette sharing, animation, other
  ROM revisions, or appending many area resources;
- triangles, GLB, simplification, BLD, image-to-3D, and production assets.

## Reproduction

```bash
python -m tools.pokeagent texture catalog --json
python -m tools.pokeagent texture catalog --compile --output build/assets/stage4d-catalog --json
python -m tools.pokeagent map determinism --fixture fixtures/stage4d_scalable_textures_world.json --json
make stage4d-texture-scaling-proof
.venv/bin/python -m tools.pokeagent qa run qa/scenarios/stage4d_scalable_textures.json --timeout 300 --json
```

All generated models, archives, ROMs, reports, screenshots, and local template
bytes remain ignored.
