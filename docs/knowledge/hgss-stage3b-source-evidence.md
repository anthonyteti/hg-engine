# HGSS Stage 3B source evidence

Recorded: 2026-08-08

This note preserves the narrow upstream source and runtime evidence used to
implement and review the Stage 3B matrix proof. It is intentionally limited to
matrix layout, zone selection, coordinate indexing, live cell identity, and the
normal-overworld terrain-buffer detail discovered during verification.

## Revisions

- `pret/pokeheartgold`: `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`
- `DS-Pokemon-Rom-Editor/DSPRE`: `d86737dfccaec7a603a6f27474180a49945158a6`

## Matrix parser (`pret/pokeheartgold/src/map_matrix.c`)

The runtime reads, in order:

```c
width = *(cursor++);
height = *(cursor++);
has_headers_section = *(cursor++);
has_altitudes_section = *(cursor++);
name_length = *(cursor++);
copy(cursor, name, name_length);
cursor += name_length;

if (has_headers_section) {
    copy(cursor, headers, width * height * sizeof(u16));
    cursor += width * height * sizeof(u16);
} else {
    fill_u16(headers, map_no, width * height);
}

if (has_altitudes_section) {
    copy(cursor, altitudes, width * height * sizeof(u8));
    cursor += width * height * sizeof(u8);
}

copy(cursor, maps.models, width * height * sizeof(u16));
```

The accessors are row-major:

```c
headers[y * width + x]
altitudes[y * matrix_width + x]
models[map_no]
```

The runtime-owned `MapMatrix` begins with `u8 width`, `u8 height`, and
`u8 matrix_id`. `MapMatrix_Load(map_no, matrix)` obtains `matrix_id` from the
initiating map header, parses that NARC member, then copies parsed width and
height to these leading fields.

## Zone/header selection (`pret/pokeheartgold/src/field/fieldmap.c`)

On player coordinate change, the running field map computes:

```c
headerX = PlayerAvatar_GetXCoord(playerAvatar) / 32;
headerZ = PlayerAvatar_GetZCoord(playerAvatar) / 32;
newMapID = MapMatrix_GetMapHeader(mapMatrix, headerX, headerZ);
```

If the header differs, it updates `location->mapId`, calls
`Field_InitMapEvents`, reconciles objects, and updates music/weather. Event,
script-header, and therefore script/text selection can vary naturally by cell
when the header grid contains distinct headers. Stage 3B deliberately points
all four headers at the same empty event/script/text banks, so this proof
confirms header-driven reload but does not re-prove distinct per-cell content.

The function does not rewrite the player's X or Z. Coordinates remain
matrix-global while local cell coordinates are the non-negative remainder
modulo 32.

## Matrix index (`pret/pokeheartgold/src/unk_02054E00.c`)

```c
posX = coordX / 32;
posY = coordY / 32;
return posX + posY * width;
```

Negative coordinates assert. The decompiled upper-bound guard uses
`posX >= width && posY >= height`; Stage 3B therefore does not rely on the
guard and blocks every exterior edge with normal collision permissions.

## Map-load state (`pret/pokeheartgold/asm/overlay_01_021F4704.s`)

The map-load manager owns four loaded-map buffer pointers at manager offsets
`0x90`, `0x94`, `0x98`, and `0x9C`. Each loaded-map buffer is `0xA74` bytes.

The loader calls `GetMapModelNo(matrix_index, map_matrix)` to choose the land
data member. On a successful load it stores the **row-major matrix index**, not
the member ID, at loaded-map offset `0x860`, then marks loaded-map offset
`0x864` ready. Initialization writes `0xFFFFFFFF` at `0x860`. This distinction
was initially ambiguous in assembly and was resolved by live evidence: the
four values were exactly `0,1,2,3`, while the live map-member grid was
`633,630,631,632`. The active member is therefore derived as
`matrix.members[manager.active_index]`.

`ov01_021F5F64` derives and stores the target/current row-major matrix index at
manager offset `0xA4`. It also stores the active render quadrant byte at
manager offset `0xAC`. The matrix width and height are stored at manager offsets
`0xC4` and `0xC8`; `width * 32` is at `0xCC`.

Altitude translation uses the selected matrix cell's altitude byte shifted by
15 (`altitude << 15`) for model Y translation. Stage 3B uses an explicitly
present all-zero altitude grid because this proof is flat.

The four loaded buffers are a moving window, not stable cell-specific slots.
Their `+0x860` values and ready flags must be read each time; slot/quadrant
numbers rotate as the player moves. At controlled start all four 2 x 2 cells
were resident and ready. Near exterior edges, out-of-window slots correctly
became `-1`/not-ready.

## Normal-overworld BGS/PER cursor finding

The Stage 2 physical member invariant remains:

```text
four u32 section lengths | four-byte BGS header | PER at 0x14 | BLD |
remaining BGS payload | NSBMD | BDHC
```

The reused template BGS header was `34 12 58 00`; its second `u16` advertised
an 88-byte payload. In the normal-overworld load path, retaining that length
caused the 2,048-byte terrain copy to start at member offset `0x6C` rather than
the required `0x14`. This was proven by reconstructing the live buffer: it was
byte-identical to generated member bytes `[0x6C:0x86C]`. The packaged ROM itself
contained the correct generated PER at `0x14`, ruling out packaging error.

Stage 3B keeps the `0x1234` signature, declares a zero BGS payload (`34 12 00
00`), and emits no trailing payload. The resulting live 2,048-byte buffer
hashes exactly match each generated PER hash. All four native transitions then
passed. This is a bounded normal-overworld container requirement, not a change
to PER placement or section ordering. Stage 2 and Stage 3A generators retain
their established behavior and both runtime regressions pass.

## DSPRE comparison (`DSPRE/DS_Map/ROMFiles/GameMatrix.cs`)

DSPRE independently parses the same sequence and loops `row` from zero to
`height - 1`, then `column` from zero to `width - 1` for headers, altitudes,
and map members. Its `BinaryWriter.Write(string)` emits the .NET length-prefixed
UTF-8 string form, matching the one-byte length for Stage 3B's short ASCII
matrix name. The project writer nevertheless emits the length byte and ASCII
bytes explicitly, matching the game parser directly and avoiding reliance on
.NET string serialization behavior.

## Evidence status

- Binary field order and row-major grids: confirmed by two source readers and
  the pokeheartgold runtime parser, exact golden bytes, and live RAM.
- Global coordinate/header selection, event reload, and 31/32 coordinate
  wrapping: confirmed by pokeheartgold source and all four emulator crossings.
- Matrix index at loaded buffer `+0x860`, active matrix index at manager
  `+0xA4`, and active member derivation: confirmed by assembly plus live RAM.
- Zero-length Stage 3B BGS declaration and live PER identity: confirmed by
  generated bytes, packaged-ROM extraction, live-buffer hashes, and movement.
- Exterior behavior beyond the matrix: deliberately not treated as safe; all
  exterior tiles use valid blocked collision and the NW north edge was tested.
- The malformed upper-bound guard's behavior after an actual escape remains
  unknown because the proof correctly prevents that state.
