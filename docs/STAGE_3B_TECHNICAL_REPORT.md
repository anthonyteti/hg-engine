# Stage 3B Native Multi-Map World Proof

Verdict: **`STAGE_3B_MULTIMAP_PROOF_PASSED`**

Recorded: 2026-08-08

## Answer

Yes. One tracked machine-readable fixture deterministically generates four
distinct 32 x 32 HeartGold land-data members, places them in one authentic 2 x
2 matrix, builds through HG-Engine, and completes this native edge loop under
headless DeSmuME control:

```text
NW --east--> NE --south--> SE --west--> SW --north--> NW
```

No event warp exists or fires during these transitions. Live matrix, header,
member, global-coordinate, local-coordinate, load-manager, event, and PER state
all agree with the canonical fixture. A blocked NW exterior edge prevents the
player from entering nonexistent matrix data. Stage 3B adds no Stage 3C
registry, buildings, production allocation, assets, content, or new geometry
capability.

## Preflight and baseline

The requested preflight found Stage 2 and Stage 3A source/docs/tests present but
uncommitted despite the task premise. Their complete existing work was first
validated, preserved, and committed as baseline commit `7fa76a42e` (`Add
deterministic Stage 2 and Stage 3A world proofs`). Stage 3B began only after a
clean working tree. No legitimate earlier work was discarded or rewritten.

## Canonical fixture and compiler architecture

Tracked canonical source is
`fixtures/stage3b_multimap_proof_world.json` (schema 3, SHA-256
`571ede2121ccd42a02462cee0592be47fcdd08dc768cb8e7cf7a6628de488ff7`).
It declares exactly one matrix and four maps in row-major order:

| Cell | Header | Land-data member | Unique blocked identity tile |
|---|---:|---:|---|
| NW | 538 | 633 | `(4,4)` |
| NE | 9 | 630 | `(5,4)` |
| SW | 10 | 631 | `(4,5)` |
| SE | 11 | 632 | `(5,5)` |

Each map has flat geometry, the Stage 2 one-plate BDHC, an independently
generated PER, reciprocal one-tile openings for the intended internal edges,
and blocked collision on every exterior edge. The controlled start is NW local
`(16,16)`, global `(16,16)`. Events are empty; the common start script is the
only warp used to reach the fixture. There are no event warp records and the
live location warp field stays `-1` around all four edge crossings.

`tools/pokeagent/world.py` generalizes the proven compiler only to schema 3:

```text
schema-3 JSON -> bounded cross-reference validation
              -> four flat NSBMD/PER/BDHC map members
              -> one 2 x 2 matrix + four controlled header patches
              -> shared empty event/no-op script/text + controlled start
              -> deterministic multi-member NARC replacement + patched ARM9
              -> existing HG-Engine Make pipeline -> test.nds
```

`make stage2-proof` and `make stage3a-height-proof` are unchanged. The scoped
successor is `make stage3b-multimap-proof`; all generated files remain below
ignored `build/stage3b/`, extracted `base/`, or ignored ROM paths.

## Matrix binary format

The implemented binary order, confirmed against `pret/pokeheartgold` and
DSPRE, is:

```text
u8 width
u8 height
u8 has_header_grid
u8 has_altitude_grid
u8 name_length
u8 name[name_length]
u16 headers[width * height]       # if present
u8  altitudes[width * height]     # if present
u16 map_members[width * height]
```

All three grids are row-major at `row * width + column`. Stage 3B emits 37
exact bytes: width/height `2,2`, both optional grids present, name
`stage3b-2x2`, headers `[538,9,10,11]`, altitudes `[0,0,0,0]`, and members
`[633,630,631,632]`. Golden SHA-256:
`9b1440975e4e5a9515524075351516c2ab5249bfbd1c6bac398b6aceec4968aa`.

The all-zero altitude grid is explicit. Source shows each altitude translated
as `altitude << 15`; Stage 3B intentionally exercises no height behavior.

## Header grid and runtime composition

`FieldMap_ChangeZone` divides matrix-global player X/Z by 32, reads the header
at `[row * width + column]`, and changes `location.mapId` when necessary. It
then reloads map events/script-header data, reconciles objects, and updates
music/weather. Thus event/script/text banks can naturally vary per header/cell,
although this bounded fixture shares empty banks and does not re-prove content
systems already covered by Stage 2.

The player coordinates are not rewritten at a header change. For non-negative
coordinates:

```text
cell_column = global_x // 32
cell_row    = global_z // 32
local_x     = global_x % 32
local_z     = global_z % 32
matrix_index = cell_column + cell_row * matrix_width
```

The map-load manager exposes its active row-major matrix index at `+0xA4`,
active quadrant at `+0xAC`, width/height at `+0xC4/+0xC8`, and four moving
loaded-buffer pointers at `+0x90..+0x9C`. A loaded buffer's `+0x860` field is
the matrix index and `+0x864` is its ready flag. It is not the member ID; the
active member is the live matrix member grid indexed by active index. This was
resolved in emulator RAM, where buffer indices were `0,1,2,3` and members were
`633,630,631,632`.

## Geometry, PER identity, and the BGS/PER finding

All four maps reuse the Stage 2 hash-locked local template family and identical
100-byte one-quad display lists. The generated NSBMD hash is
`bd60f360cadd10e2c2061c318e75e83795e0d11b9c211f759ff4945eecf8608d`;
the one-plate BDHC hash is
`07584c4215ceed2216ba6928d51273b36fa3345815e076390ed5e8ca340980e1`.
No new material, texture, topology, slope, converter, or proprietary tool was
introduced.

Map identity is instead deterministic and runtime-readable through distinct
PER layouts. The four live 2,048-byte terrain-buffer hashes exactly matched
the four generated PER hashes:

| Map | PER SHA-256 | Map-member SHA-256 |
|---|---|---|
| NW | `ab9be144f926238e5686fdf65fdd6194dedc9be4c3dee784ce82c9a0c7f58b2a` | `a48cc48fac07cc4a12b145ee1504254900fbe360ad1f28d4ca9a5bf22f990472` |
| NE | `497bf8bc767e3bba54897717588a14ee6533f0907fdcc0946a3405fd33e91cb9` | `1e65609936ac599f20bc27043bfe9948d24d606a20bc789eb26c77c16a7abc99` |
| SW | `33c38f062f01cb2df81894aaf01dd45aa6371316836d6bbde3ea5eb17f1c3d50` | `4cd29e6a90e955ae408fdb6e230b04eeb12c19b7f66fd81615c7c6496fb94b1b` |
| SE | `d02ee86ae61bba908bdc9f1aad2e352de0a624adc832423596850a14e4dbe304` | `5c07eee4317786b3ffc64133aef77535dcfd7fb8828eea17fa8d0fbb3d49d379` |

Normal-overworld verification exposed one container requirement. The reused
BGS header advertised an 88-byte payload, causing the runtime terrain copy to
begin 88 bytes into the fixed-position PER. Packaged-ROM extraction proved the
ROM contained the intended bytes at `0x14`; reconstructing the live buffer
proved it matched member bytes beginning at `0x6C`. Stage 3B therefore preserves
the Stage 2 physical ordering and `PER @ 0x14`, but declares the optional BGS
payload empty (`34 12 00 00`) and emits no payload. A permanent unit test locks
this declaration. Stage 2 and Stage 3A runtime regressions remain green.

Reusable source, byte, and confidence details are in
`docs/knowledge/hgss-stage3b-source-evidence.md`.

## Controlled test IDs and validation

These are deterministic test replacements, not production-safe allocations:

- matrix 1; event 57; local script 842; common start script 3; script header
  399; text 542;
- land-data members 630, 631, 632, 633. A scan of the original US HG matrix
  archive found members 628 through 633 unreferenced; 634 and above were not
  assumed free;
- header 538 (`MAP_UNUSED`) plus normal-overworld route header IDs 9, 10, 11.
  All four generated entries copy verified normal-overworld header 67 before
  patching controlled references. IDs 9-11 replace real route headers and are
  emphatically test-only. Battle Tower/simple-collision IDs 267-270 are not
  used.

Validation rejects dimensions other than 2 x 2, a wrong cell count/order,
missing map references, duplicate controlled member/header assignments,
unknown or malformed cells, inconsistent cell coordinates, invalid IDs,
non-reciprocal internal openings, exterior openings, nonzero altitudes,
nonempty warp/NPC content, and generated headers pointing at the wrong matrix.
Numeric header/member grids are derived from named fixture cells rather than
authored independently.

## Native traversal evidence

Headless runtime evidence from `build/stage3b/emulator/report.json`:

| Edge | Approach: header/global/local/index/member | Entered: header/global/local/index/member |
|---|---|---|
| NW east | `538 (31,16) (31,16) 0/633` | `9 (32,16) (0,16) 1/630` |
| NE south | `9 (48,31) (16,31) 1/630` | `11 (48,32) (16,0) 3/632` |
| SE west | `11 (32,48) (0,16) 3/632` | `10 (31,48) (31,16) 2/631` |
| SW north | `10 (16,32) (16,0) 2/631` | `538 (16,31) (16,31) 0/633` |

After every crossing, one more ordinary movement step succeeded in the new
cell. The live warp field was `-1` before and after every transition. Event
counts remained zero backgrounds, NPCs, warps, and coordinate events.

For the exterior test, the player approached NW north at global/local `(16,1)`
and remained there after north input. Header 538, active index 0, and member 633
were unchanged. The proof never asks the engine to resolve an invalid matrix
index; malformed-index behavior is not treated as safe.

All 21 runtime check fields passed, including the four approaches, four native
transitions, correct coordinate wrapping, continued movement in every cell,
distinct member identity, no warp records, exterior blocking, and another 600
stable frames. Ignored screenshots are:

- `build/stage3b/emulator/nw-start.png`
- `build/stage3b/emulator/ne-entered.png`
- `build/stage3b/emulator/se-entered.png`
- `build/stage3b/emulator/sw-entered.png`
- `build/stage3b/emulator/nw-returned.png`
- `build/stage3b/emulator/exterior-blocked.png`

Final generated ROM SHA-256:
`6cc9447e0aa6ae425401efe14296e0ad1833e510e87328e5a49d5b65ee33c585`.
The ROM and screenshots remain ignored.

## Determinism

The determinism harness removed two clean roots, generated independently, and
compared every binary component, four map members, replacement NARC, and
patched ARM9. All 31 compared binary artifacts matched byte-for-byte; zero
mismatches were reported. Representative hashes:

- matrix NARC: `30846851481a31f5e79bfe380de283109c8263dc69d3816de8d49046bc763791`
- land-data NARC: `c66c42f42859855e9b540191b1949370188cb477fa26a7846d121d71d132869b`
- event NARC: `f975773984033c907bd69790794d7586154b45f45a8aad3b03d228c74bc7e7b3`
- script NARC: `27eedf86b98acadab40bc1a1bbe2f17af26779c80b19d45871a2ab3764e85a3d`
- text NARC: `98dc3a57970366822e3397aa505958fc5bc763aa79abe30504383dc3a7690be6`
- patched ARM9: `ae3b701a3b80cea931178b451520258e89fc2cb70076077f37f10bafc5d55dff`

The ignored complete report is `build/stage3b/determinism-report.json`.

## External evidence and legal/reproducibility constraints

- `pret/pokeheartgold` revision
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`: matrix parser/accessors,
  `FieldMap_ChangeZone`, map-event reload, matrix coordinate index, and
  map-load-manager assembly.
- DSPRE revision `d86737dfccaec7a603a6f27474180a49945158a6`: independent matrix parser and
  row/column serialization comparison.
- Stage 2's PDSMS/NSBMD evidence and hash-verified user-local template remain
  unchanged. No editor framework or external code was imported.

No proprietary converter, GUI, `g3dcvtr`, new downloaded tool, or redistributed
ROM-derived artifact is required. The project-owned serializer remains open
source and deterministic, but the local texture/material template and output
NARCs derive from the user's commercial ROM. Public CI therefore still needs a
lawfully supplied compatible ROM and must not publish ROMs, NARCs, screenshots,
or extracted assets.

## DeepSeek investigations

Every request used the bounded worker and pinned
`deepseek-ai/DeepSeek-V4-Flash-0731`. The only supplied repository context was
the explicit narrow source note
`docs/knowledge/hgss-stage3b-source-evidence.md`; prompts selected the relevant
matrix/parser/load-manager excerpts. No unrestricted repository context was
sent.

| Task | Effort/cap | Result | Reported usage / cost | Codex disposition |
|---|---|---|---|---|
| Review matrix/parser and adjacent-load interpretation | high / 3,072 | response hit length before completing the requested byte interpretation | 1,476 prompt + 3,072 completion = 4,548; `$0.00068580` | incomplete; no conclusion relied upon |
| Reduced header-grid question | medium / 2,048 | `empty_response` | provider reported no usage/cost | rejected |
| Reduced coordinate/load question | high / 4,096 | `empty_response` | provider reported no usage/cost | rejected |
| Identify useful live load-manager offsets | none / 1,024 | proposed `+0xA4`, four buffers, `+0x860`, `+0x864` | 1,427 + 329 = 1,756; `$0.00018765` | offsets verified in assembly and emulator; its `+0x860` member-ID interpretation was corrected to matrix index by live RAM |
| Review exact 2 x 2 matrix bytes | none / 1,024 | matched field order and expected bytes | 1,467 + 451 = 1,918; `$0.00021321` | verified against both source readers, golden unit test, and live matrix |
| Propose focused multi-map tests | none / 1,024 | proposed five checks | 1,443 + 495 = 1,938; `$0.00021897` | reciprocal/grid/identity ideas used; unsafe advice to step beyond an exterior matrix boundary was rejected |

Known reported total: 10,160 tokens and `$0.00130563`. The two
`empty_response` calls exposed no token or cost fields. All conclusions remained
advisory.

## Verification and regressions

Final commands included:

```bash
git status --short
git log --oneline -5
.venv/bin/python -m unittest discover -s tests -v
make stage2-proof -j2
.venv/bin/python -m tools.pokeagent map test --fixture fixtures/stage2_proof_map.json --timeout 240 --json
make stage3a-height-proof -j2
.venv/bin/python -m tools.pokeagent map test --fixture fixtures/stage3a_height_proof_map.json --timeout 300 --json
make stage3b-multimap-proof -j2
.venv/bin/python -m tools.pokeagent map test --fixture fixtures/stage3b_multimap_proof_world.json --timeout 300 --json
.venv/bin/python -m tools.pokeagent map determinism --fixture fixtures/stage3b_multimap_proof_world.json --json
.venv/bin/python -m tools.pokeagent preflight --json
git diff --check
```

Results:

- 58 unit tests passed; three explicitly opt-in live integrations skipped.
- Stage 2 clean build and all 11 runtime checks passed, including collision,
  NPC/dialogue, reciprocal warp, and stability. ROM hash:
  `e31c7c96b6e83b2c93a9b64c1d2e6d25ec5959a5fc4315886887bd194f365b64`.
- Stage 3A clean build and all 14 runtime checks passed, including parsed BDHC,
  lower/raised movement, blocked ledges, ramp traversal, live height, return,
  and stability. ROM hash:
  `4b1a0ccb20e12792dbaf8a930648030261d1ce84cfb9cfbbd74084d9a99c06a8`.
- Stage 3B final clean build, 21 runtime checks, determinism, preflight, diff
  whitespace, and tracked-artifact hygiene passed.
- No ROM, save/state, screenshot, extracted `base/`, generated `build/`, NARC,
  or other sensitive binary is tracked.

## Confidence boundaries and decision

Confirmed by source and runtime:

- matrix field order, row-major grids, active-cell selection, header change,
  event reload, global/local coordinate behavior, four native transitions,
  moving load-buffer identity, live PER identity, and safe collision boundary.

Confirmed by source only:

- a distinct header can select distinct event/script/text banks; Stage 3B uses
  shared empty banks, so per-cell content variation was intentionally not
  exercised.

Inferred and bounded:

- the zero BGS payload is appropriate for this primitive fixture because no
  sound-plate behavior is needed. The live copy and full runtime proof confirm
  it is correct here; production BGS authoring is not generalized.

Unknown / not claimed:

- behavior after malformed or escaped matrix coordinates; matrices larger than
  2 x 2; production-safe IDs; buildings/BLD; stacked floors; arbitrary
  geometry; cross-matrix composition; and production event populations.

HeartGold remains the recommended foundation. Native multi-member composition
works deterministically through the project-owned compiler and normal field
runtime. Stage 3C may proceed when separately authorized, specifically to solve
production ID/registry concerns; this work stops at the Stage 3B verdict.
