# Stage 3D technical report: reusable static-terrain geometry compiler

## Verdict

`STAGE_3D_GEOMETRY_COMPILER_PASSED`

One registry-backed, machine-readable fixture now drives a generic bounded
terrain IR, deterministic quad generation, three valid Nitro display lists,
multi-shape NSBMD transformation, PER, and 14-plate BDHC. HG-Engine builds the
result and headless DeSmuME proves two elevation transitions, raised/lower
movement, an irregular terrace path, cliff blocking, and 600 stable frames.

No fixture-specific geometry emitter, GUI, proprietary converter, OBJ/GLB
import, new texture/material, or general NSBMD writer was added.

## Stage 3C checkpoint

Stage 3D implementation began only after the completed Stage 3C work was
checked, intentionally staged, committed, pushed, and remotely verified:

- commit: `aaaf26348 Add Stage 3C symbolic reference registry`
- full commit: `aaaf263488f2240d31fe9790d6d0ffc9ad1b38c4`
- branch: `main`
- local `HEAD`, `origin/main`, and remote `ls-remote` all matched;
- working tree was clean before Stage 3D changes.

Direct `git push` succeeded. The local GitHub CLI credential was invalid, but
no GitHub API operation or PR was required for the requested checkpoint.

## Canonical fixture and registry resolution

`fixtures/stage3d_static_geometry_world.json` is schema 5. Its global resources
are Stage 3C symbols, not authored numeric IDs. Resolution uses the deliberate
test-controlled replacements matrix 1, header 538, member 633, event 57,
scripts 842/3, script header 399, and text 542. Template member 0, area data 2,
and header template 67 remain verified read-only dependencies.

Those slots are still **controlled test replacements**, not production-free
allocation. Stage 3D adds no new global ID.

The 32 x 32 source declares:

- lower terrain at height 0;
- a broad northeast height-2 terrace which narrows to a four-tile stem;
- one eastward X ascent and one southward Z descent;
- irregular cliff boundaries around the terrace/stem;
- a blocked perimeter;
- controlled start `(8,12)`;
- no NPC, warp, story, building, imported asset, or custom texture.

## Compiler architecture

`tools/pokeagent/geometry.py` owns the bounded geometry subset:

```text
canonical surfaces/transitions/collision
  -> exact schema and topology validation
  -> immutable feature IR + full 32x32 ownership grid
  -> surface/ramp quads + derived cliff quads
  -> material partition + capacity check
  -> Nitro display-list encoding
  -> shared PER and BDHC derivation
```

`tools/pokeagent/world.py` remains the integration layer. It resolves schema 5,
loads and hash-checks the user-local template, replaces selected shape display
lists inside known regions, emits the unchanged physical HGSS map-member
ordering (including PER at offset `0x14`), and reuses existing matrix/header/
event/script/text/NARC/ARM9 installation.

The ignored build materializes `geometry-ir.json`, `geometry-report.json`, and
each selected display list separately. Binary serializers receive resolved
numeric values and do not own registry policy.

## Primitive and encoder subset

Stage 3D uses quads only. Rectangular terrain did not justify adding triangles;
rejecting them keeps the command and budget model exact. Supported commands are
`BEGIN(QUADS)`, `NORMAL`, `TEXCOORD`, `VTX_16`, and `END`.

The proof generates:

| Class | Quads | Vertices | Display-list bytes |
|---|---:|---:|---:|
| ground | 12 | 48 | 1,068 |
| transition | 2 | 8 | 188 |
| derived cliff | 8 | 32 | 716 |
| **total** | **22** | **88** | **1,972** |

Primitive order follows canonical source order, followed by deterministically
sorted/merged derived walls. A list length is exactly `12 + 88*N` bytes.

## Multi-shape packing and material reuse

The verified template has 18 fixed display-list regions. All offsets and
capacities were inventoried; no list is relocated or expanded. The proof's
deterministic assignments are:

| Shape | Existing material | Alias | Used / capacity | Utilization |
|---:|---|---|---:|---:|
| 5 | material 12 `grass01` | ground | 1,068 / 1,936 | 55.165% |
| 6 | material 17 `road01` | transition | 188 / 1,068 | 17.603% |
| 1 | material 18 `road01_r` | cliff | 716 / 2,496 | 28.686% |

All other shapes receive the earlier valid degenerate stream. Model/material/
texture dictionaries, SBC, NSBTX data, and material associations remain
unchanged. Exceeding a known shape capacity returns
`display_list_overflow`; no unknown model region is overwritten.

## Geometry, PER, and BDHC synchronization

The same feature list drives visible surfaces and BDHC plates. The same tile
ownership grid drives wall derivation and PER. A permanent test compares every
visual feature and BDHC plate ID, rectangle, height endpoints, and axis.

PER is 2,048 bytes, row-major Z then X, with a blocked perimeter and walkable
interior. The fixed physical placement at map-member offset `0x14` remains
covered by Stage 2/3B serializer regressions.

BDHC contains:

- 28 rectangle points;
- 3 normals;
- 4 plane constants;
- 14 plates;
- 6 Z stripes;
- 26 access indices.

Normals are horizontal `(0,4096,0)`, X ascent `(-2896,2896,0)`, and Z descent
`(0,2896,2896)`. Stripe candidates include the immediately following band and
are stably X-sorted. The final banded plate layout is source- and runtime-
confirmed. Arbitrary overlapping/ambiguous plates remain unsupported.

## CLI and capacity report

Added:

```bash
python -m tools.pokeagent map geometry inspect \
  --fixture fixtures/stage3d_static_geometry_world.json [--json]
make stage3d-geometry-proof
```

The JSON inspection/report includes primitive/vertex counts, triangle/quad
counts, per-material shape and material IDs, list bytes, capacity/utilization,
all 18 template capacities, BDHC counts, blocked-tile count, template hash, and
SHA-256 values for PER, BDHC, and every display list.

## Build, emulator, and visual result

Final clean `make stage3d-geometry-proof -j16` completed and produced ignored
`test.nds`. Final ignored ROM SHA-256:

`3e8d1b451a8f4f7c7447cd769eaccbd2cd08ff983d8ccec645ad9363e99dc22a`

All 14 Stage 3D runtime checks passed:

1. map/header/member and controlled start loaded;
2. parsed 14-plate/six-stripe BDHC became ready;
3. empty event fixture remained empty;
4. lower height was 0 / Y 0;
5. lower movement worked;
6. transition A traversed X 14/15/16/17;
7. transition A heights were 1/3/4/4 and final Y was `131072`;
8. direct cliff movement from `(16,9)` remained blocked at height 4;
9. the irregular raised path reached `(18,23)` at height 4;
10. transition B traversed Z 24/25/26/27;
11. transition B heights were 3/1/0/0 and final Y was 0;
12. lower movement after transition B reached `(14,27)`;
13. no blocked-geometry shortcut was taken;
14. the ROM remained stable for another 600 frames.

Ignored evidence:

- `build/stage3d/emulator/report.json`
- `build/stage3d/emulator/lower-start.png`
- `build/stage3d/emulator/transition-a.png`
- `build/stage3d/emulator/cliff-blocked.png`
- `build/stage3d/emulator/raised-terrace.png`
- `build/stage3d/emulator/transition-b.png`

Codex visually inspected all five final screenshots. They show the primitive
ground, the two road-material transition regions, raised/cliff faces, and the
player at the asserted regions. No missing/exploded surface, invalid camera, or
model corruption was visible. Texture reuse is intentionally crude and is not
production art.

## Controlled-start QA correction

The test-only `STAGE2_MAP_TEST` hook previously queued its generated warp at
counter 30. A diagnostic run proved that both exact Stage 3A golden bytes and
Stage 3D could load while D-pad input remained owned by the new-game field
script. The hook now queues at counter 300 and advances at 301. This code is
inside the existing test-only preprocessor path and does not affect normal ROM
builds.

The matrix QA helper also uses the standard one-tile key cadence with its
original 96-attempt bound. A temporary shorter diagnostic bound could not span
a full 32-tile Stage 3B cell and was rejected.

## Determinism

Two clean roots compared 22 generated artifacts with zero mismatches.
Key final hashes:

| Artifact | SHA-256 |
|---|---|
| geometry IR | `0d81216335b537f9929f0212e876a83e707210a0ab03e8c90a736df6fe5935e5` |
| geometry report | `a9fc470daef604887646680266851944d1bafd36834ca39f97b5f4995357e064` |
| shape 1 list | `3787fe59399f5efc9aaf86886cd0a70770030411222a0b1230d4ef2562e727d6` |
| shape 5 list | `6dbb5a8f0ee108f4cb17b39dcd68b4c86faedf830cf096c64f6e22f3ac7e83ab` |
| shape 6 list | `676719a075b91fcd5582e4b6f54a611030d4b452c2d2372f382cc9bd6a71dab1` |
| transformed NSBMD | `92b19251e9a918da5bf889194a7007668fadf2785b30fd4a34068ea8bd84dfda` |
| PER | `59a46c7038e894d2de55be70434c9277f3780c37436487c01d775090904368e6` |
| BDHC | `67feb2e03d0f3a47869ca8073dc9599148143a3fe2d5ed9d2ec6242bab174653` |
| map member | `fd1c47b0b8e931a214247e5301b5aadb1f069360d4d97ba0197104562b408f86` |
| matrix | `233c1e94fc66afe141c42873197311d74b110f2b9edced9dde28d283a953850a` |
| resolved registry | `edff3a2ae9c659110e95b0bb25dfd88880f2e0bf28d2fea82e3fbe62133cb70e` |
| patched ARM9 | `9dea7882c33cd431c53731eeca294741e64163eea90fd2ce44cdd88e932984c1` |
| map NARC | `6a3b13e5024c14a9d1a25a7f043f494618931b6094f4071f8ecefcf1f5fcb87e` |

Scripts, text, event, header, remaining replacement NARCs, and ARM9 also
matched; the complete ignored JSON report contains all hashes.

## Regression results

- Full suite: 88 tests ran; 85 passed and 3 opt-in integration tests skipped.
- Registry validation: passed against the supported local ROM revision.
- Preflight: every command, Python, ROM, system, Docker-context, and Git-hygiene
  check passed.
- Stage 2: clean build; all 11 NPC/dialogue/warp/collision/stability checks
  passed.
- Stage 3A: clean build; all 14 normal-overworld height checks passed.
- Stage 3B: clean build; all 21 native 2 x 2 edge-transition checks passed.
- Stage 3C: clean build; all 21 symbolic-registry/native-transition checks
  passed.
- Stage 3D: final clean build; all 14 geometry/height/stability checks passed.

## External evidence and DeepSeek

Source revisions:

- Pokemon DS Map Studio
  `ac30b653e5b090ce116278ed6ba9758fff956673`;
- pret/pokeheartgold
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`;
- supported local US HeartGold ROM/template hashes recorded by Stage 3C.

PDSMS files inspected were `BdhcWriterHGSS.java`, `Stripe.java`, and
`Plate.java`. No editor framework was imported. Neither external checkout
contained a top-level redistribution license file at the inspected revision;
source was used as evidence only. User-local retail bytes remain ignored and
hash-verified, never redistributed.

Bounded `deepseek-ai/DeepSeek-V4-Flash-0731` calls:

| Task | Explicit source | Effort | Tokens | Estimated cost | Disposition |
|---|---|---|---:|---:|---|
| combined encoder/BDHC review | `tools/pokeagent/geometry.py` | medium | no response/usage reported | unavailable | rejected as empty response |
| verify quad-list byte accounting | encoder excerpt from `tools/pokeagent/geometry.py` | none | 5,914 prompt + 991 completion = 6,905 | `$0.00071064` | verified: `12 + 88*N` and golden bytes |
| review BDHC plane/stripe math | BDHC excerpt from `tools/pokeagent/geometry.py` | none | 5,999 prompt + 1,104 completion = 7,103 | `$0.00073863` | math verified against PDSMS, Stage 3A, bytes, runtime |

Useful-call estimated total: `$0.00144927`. One imprecise slope-description
sentence was rejected; Codex retained the source/runtime-verified normal and
constant formula.

## Confirmed, inferred, and unknown

Confirmed by source and runtime:

- fixed template capacities and in-place multi-shape replacement;
- the five-command quad display-list subset;
- three existing material bindings;
- source-driven visual/PER/BDHC generation;
- 14-plate/six-stripe BDHC with two tested transition axes;
- runtime height, cliff, traversal, stability, and clean determinism.

Confirmed by source/bytes but not generalized by runtime:

- capacities of the 15 unused shapes;
- PDSMS's following-band access-list construction intent;
- other existing template material names/associations.

Inferred:

- the chosen template texture names are semantically suitable aliases for a
  primitive infrastructure fixture; visual inspection supports this but does
  not make them a production art contract.

Unknown/unsupported:

- triangles or arbitrary polygons/topology;
- other ramp directions and arbitrary plate partitions;
- bridges, stacked floors, overlapping floor ambiguity;
- shape relocation/expansion and arbitrary SBC/material binding;
- new materials, textures, palettes, NSBTX, animation, or node hierarchies;
- OBJ/GLB import and general NSBMD generation;
- practical limits beyond 22 quads / 14 plates in this tested family.

## Recommendation

HeartGold remains the recommended foundation. Stage 3D resolves the bounded
static-terrain compiler question without a proprietary converter or manual map
editor. Stage 3E may proceed if it respects this tested IR/template envelope
and treats unsupported geometry/material/import work as separate kill-gated
research. Stage 3E was not started.
