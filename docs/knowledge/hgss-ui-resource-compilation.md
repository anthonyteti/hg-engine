# Project-owned HGSS UI resource compilation

## Finding

The HGSS start menu loads a standard Nitro BG resource triple from common NARC
`a/0/1/4`:

- member 12: compressed character data (`NCGR`)
- member 13: compressed 32 × 24 screen map (`NSCR`)
- member 15: palette (`NCLR`), loaded into BG palette slot 14

This is confirmed in the current local fork and by `pret/pokeheartgold`
revision `90e85d4e027f5e04800e7e015b3207094061402c`, `src/start_menu.c`.

## Existing map semantics

The retail screen is 32 × 24 tiles. Rows 0–16 repeat tile 0. Rows 17–23
repeat tiles 1–7 respectively. All cells select palette slot 14. This makes the
surface a useful bounded first proof: eight authored tiles produce a complete
native screen without changing start-menu code or navigation.

## Project authoring path

`tools/pokeagent/ui_resources.py` validates a symbolic source bundle, draws an
indexed deterministic sheet, emits tilemap JSON, and delegates Nitro binary
encoding to the existing open-source `nitrogfx` tool. The generated resources
are local build output.

Run:

```bash
make stage6c-ui-resources
```

The canonical source is
`presentation/ui/resources/stage6c_start_menu.json`. The source owns colors,
component roles and logical layout. The compiler target record owns the NARC
members and palette slot.

## Proof installation

`make stage6c-ui-resource-proof` builds the existing controlled world, compiles
the resources, replaces members 12/13/15 in a temporary reconstruction of the
user-local common archive, repacks the ignored proof ROM, and restores the
archive's original bytes even on failure.

The generated manifest records output hashes, sizes, proof ROM hash and archive
restoration. The QA scenario opens the ordinary start menu with X.

## Constraints

- native screen: 256 × 192 / 32 × 24 tiles
- current proof sheet: 32 4bpp tiles
- maximum 16 authored palette colors
- index 0 reserved by source policy
- this start-menu BG is opaque at runtime; palette index 0 does not reveal the
  field scene beneath it
- target members are unique and source-validated
- no extracted retail member enters Git
- normal builds do not invoke the proof installer

## Confidence

High for BG character/screen/palette compilation and runtime rendering. The
exact common-archive ownership and loader calls are confirmed by source and the
visible proof.

OAM cell/animation compilation and font-resource replacement remain bounded
future extensions. They should be added only when 6D–6G needs them.
