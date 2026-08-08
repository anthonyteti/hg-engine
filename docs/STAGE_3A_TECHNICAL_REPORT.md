# Stage 3A Multi-Height World Proof

Verdict: **`STAGE_3A_HEIGHT_PROOF_PASSED`**

Recorded: 2026-08-08

## Answer

Yes. The existing deterministic zero-GUI HeartGold world compiler now generates and boots one primitive 32 x 32 map with lower terrain at height 0, a raised height-2 platform, a traversable two-tile ramp, and a height-aware impassable ledge. It builds through HG-Engine and passes live-memory plus movement assertions in headless DeSmuME.

Stage 3A stays bounded to one infrastructure fixture. It adds no second map, buildings, custom textures, content systems, GLB/OBJ import, general NSBMD writer, or Stage 3B work.

## Architecture and canonical fixture

Tracked canonical source is `fixtures/stage3a_height_proof_map.json` (schema version 2, SHA-256 `8528abef78290efc6514829fc8ea34f9cde4a1286aac867bbc159e4452e37df1`). It declares:

- one 32 x 32 member;
- lower region X 0-15 at height 0;
- raised region X 16-31 at height 2;
- transition override X 16-17, Z 14-17, rising 0 to 2;
- a blocked perimeter and blocked PER boundary outside the transition;
- controlled start `(14,12)`, facing east;
- controlled replacements: header 538, matrix 1, member 633, event 57, scripts 842/3, header 399, and text 542;
- no NPC and no warps, because they add no evidence to this height-only proof.

Schema 1 and `make stage2-proof` remain supported. Schema 2 adds only the exact Stage 3A profile and uses ignored `build/stage3a/` outputs.

The pipeline is:

```text
schema-2 JSON -> validation -> seven-quad display list -> hash-locked NSBMD
              -> PER + five-plate BDHC -> proven HGSS map-member assembly
              -> matrix/header/empty event/no-op scripts/text -> patched NARCs/ARM9
              -> HG-Engine Make -> test.nds -> headless DeSmuME assertions
```

The Stage 2 physical map-member invariant is preserved exactly: four lengths, BGS header, PER at fixed member offset `0x14`, BLD, remaining BGS payload, NSBMD, then BDHC. Permanent Stage 2 regression coverage checks that placement.

## Geometry and NSBMD decision

No new converter or proprietary dependency was introduced. The Stage 2 hash-locked user-local template approach remains the recommendation for this bounded proof:

- source member 0 SHA-256: `f9fbf0196f416739019288f24be604fd6c096a2ec4ebf7e820e116e7ecc329cc`;
- shape 6 display-list capacity: 1,068 bytes;
- generated display list: 628 bytes;
- seven quadrilaterals / 28 vertices;
- dictionaries, one node, 23 materials, texture bindings, and other template structure preserved;
- all unused shape display lists replaced with valid degenerate geometry as in Stage 2.

The seven quads are the lower surface, ramp, three non-overlapping raised-surface regions, and two visible wall spans. Model coordinates retain the Stage 2 quarter-scale display convention: visual lower Y `0.25`, raised Y `0.75`; the 0.5 display-space rise corresponds to two BDHC height units. No arbitrary topology, materials, textures, nodes, or animation are supported.

Generated model SHA-256: `ca9d06b7a3361079c605f7bdc3b9ffdd1bac7e862a8ca42068a6d94466bc4d57`.

Legal/reproducibility constraints are unchanged from Stage 2: the transformer is project-owned, but its verified material/texture template is user-local commercial data. Neither the template nor transformed model can be redistributed. Public CI requires a lawfully supplied supported ROM and cannot publish generated NARCs, ROMs, screenshots, or extracted assets. `g3dcvtr` is neither used nor silently required.

## BDHC generalization

Stage 3A implements the smallest runtime-proven subset: ten points, two normals, two constants, five plates, three stripes, and ten access entries (212 bytes). Plates partition lower, ramp, and three raised regions so tile centers are unambiguous. The ramp uses normal `(-2896,2896,0)` and horizontal height 2 uses constant `-131072`.

The engine queries centered tile coordinates and evaluates `Y = -(D + Nx*X + Nz*Z) / Ny`. Full format details, stripe behavior, source evidence, and confidence boundaries are recorded in `docs/knowledge/hgss-stage3a-bdhc-heights.md`.

A critical runtime discovery changed the controlled header. Stage 2 header 267 is a Battle Tower map; HeartGold forces its simple-collision mode and does not parse BDHC. Stage 3A uses verified normal-overworld `MAP_UNUSED` slot 538. Headless live memory confirms the active map's BDHC view is ready, has three stripes, and holds six non-null section pointers.

## Collision and elevation transition

PER and BDHC describe compatible surfaces. PER blocks only the perimeter and marks lower, ramp, and raised tiles walkable; it does not incorrectly forbid X 16-17 when approached on top of the platform. The height plates make lower-to-raised movement outside the corridor a two-unit discontinuity, rejected in both directions. The ramp is the only region with intermediate heights.

The intended transition is a true plane/ramp, not a visual-only polygon. Runtime evidence:

| Tile | `hCurr` | `positionVector.y` | World height |
|---|---:|---:|---:|
| `(15,16)` | 0 | 0 | 0.0 |
| `(16,16)` | 1 | 32768 | 0.5 |
| `(17,16)` | 3 | 98304 | 1.5 |
| `(18,16)` | 4 | 131072 | 2.0 |

The player moves normally at height 0, stops at `(15,12)` when pushed east into the ledge, traverses the ramp to `(18,16)`, moves on the raised plane while remaining at world Y 2.0, reaches the raised ledge edge `(16,12)` but cannot descend through it, and returns down the ramp to `(14,16)` at height 0.

## Emulator verification

`tools/pokeagent/world_emulator.py` extends the Stage 2 QA path. It follows `gFieldSysPtr` to the player avatar/map object for `hCurr` and `positionVector.y`, and follows the map-load manager to the parsed BDHC view. It asserts:

1. header 538 and controlled start `(14,12)` load;
2. the intentionally empty event fixture loads;
3. a real three-stripe BDHC view is ready with section pointers;
4. initial height is 0;
5. lower movement works;
6. direct lower-to-raised movement is blocked;
7. the four ramp samples reach `(18,16)` and world Y 2.0;
8. raised-plane movement works at that elevation;
9. the player cannot cross the ledge from the raised side and stays at world Y 2.0;
10. returning by the ramp restores Y 0;
11. the ROM remains on header 538 and running for another 600 frames.

All 14 emitted check fields passed. Structured evidence and ignored screenshots are at `build/stage3a/emulator/report.json`, `lower-terrain.png`, `lower-boundary.png`, `raised-terrain.png`, `raised-boundary.png`, and `returned-lower.png`. The final ROM SHA-256 was `4b1a0ccb20e12792dbaf8a930648030261d1ce84cfb9cfbbd74084d9a99c06a8`; the ROM itself remains ignored.

## Determinism

The harness deletes two output directories, generates independently, and compares every binary component, patched NARC, and patched ARM9. It reported zero mismatches. Representative hashes:

- NSBMD: `ca9d06b7a3361079c605f7bdc3b9ffdd1bac7e862a8ca42068a6d94466bc4d57`
- PER: `59a46c7038e894d2de55be70434c9277f3780c37436487c01d775090904368e6`
- BDHC: `438f9232871173f7c686aa35d1930d0620acc7c205dd020c4d2fd68b1481193e`
- map member: `e132cb03ac300bc33be5acbb8258ad20e515935f6271dc7dc904c80f3cbe8ac4`
- matrix: `1827e8b429777c2c5f4a919a7012c0d584fdc92a33df83a3593ddb91550b96e9`
- header: `0c751170f67faf1a55f2936f93c92fe9d4bc5c7eea409a7a94e6cd80758c781a`
- event: `374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb`
- generated map NARC: `9f8a4b57263c38781dd6e6bed26d2cef4ec84ec7a1f58ea4cac576582c5b14d1`
- patched ARM9: `2789fd562e2b9ab5c7b8b852f8ed0478150234af9a77edbe516e137e5edbd9f4`

## External source revisions

- Pokemon DS Map Studio `ac30b653e5b090ce116278ed6ba9758fff956673`: HGSS BDHC writer/loader, plate normals, stripe records.
- `pret/pokeheartgold` `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`: map-load modes, map constants/headers, BDHC parser and height query assembly, map-object state.
- Stage 2's already documented NSBMD evidence and user-local template are unchanged; no editor code was imported.

PDSMS has no repository license at the inspected revision. It was used only as format evidence; the project serializer is an independent bounded implementation corroborated by HeartGold runtime source and emulator behavior.

## DeepSeek investigations

All requests used pinned `deepseek-ai/DeepSeek-V4-Flash-0731`, high reasoning, the bounded worker, and no repository context files. Relevant source excerpts were selected explicitly in the prompts; the model had no unrestricted repository access.

| Task | Explicit source supplied | Result | Usage / estimated cost | Codex disposition |
|---|---|---|---|---|
| Summarize the HGSS BDHC writer fields | narrow excerpts from PDSMS `BdhcWriterHGSS`, `BdhcLoaderHGSS`, `Plate`, `Stripe`; no worker context files | request timed out | no reported usage / `$0` reported | no conclusion used |
| Explain counts, plate references, stripe slices, and candidate access | same bounded PDSMS structures, reduced prompt | correctly identified the six counts and cumulative access offsets | 372 prompt + 580 completion = 952 tokens; `$0.00013788` | verified field-by-field against Java source, generated bytes, HeartGold parser assembly, and live pointers |
| Review plane/height arithmetic | narrow plane fields/formula excerpt | `empty_response` | no reported usage / `$0` reported | rejected; Codex derived and verified the equation independently from runtime assembly and live heights |

The first request used a 4,096-token completion cap and 180-second timeout. The two later requests used 3,072 tokens and 300 seconds. DeepSeek supplied advisory reconnaissance only.

## Verification record

Final verification commands:

```bash
make stage3a-height-proof -j16
.venv/bin/python -m tools.pokeagent map test --fixture fixtures/stage3a_height_proof_map.json --timeout 240 --json
.venv/bin/python -m tools.pokeagent map determinism --fixture fixtures/stage3a_height_proof_map.json --json
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m tools.pokeagent preflight --json
make stage2-proof -j16
.venv/bin/python -m tools.pokeagent map test --timeout 180 --json
git diff --check
```

Stage 3A build, runtime assertions, determinism, Stage 2 regression, full tests, preflight, and tracked-artifact hygiene all passed.

## Limitations and decision

- Only one positive-X 45-degree ramp, two horizontal elevations, five plates, and three stripes are proven.
- The template transform remains bounded by one verified model/shape capacity and reused local materials/textures.
- The primitive template's visual presentation is adequate for infrastructure evidence, not content production.
- Header 538 and the other controlled slots are test replacements, not a production allocator.
- Multi-map matrices, buildings/BLD, stacked floors, bridges, arbitrary slopes/topology, and import pipelines remain unimplemented.
- The repository claimed Stage 2 was committed, but the working tree presented the Stage 2 files as uncommitted. Stage 3A preserved those changes and did not rewrite or discard them.

HeartGold remains the recommended foundation. The normal overworld runtime demonstrably parses project-generated multi-plate BDHC and supports the bounded elevation transition. Stage 3B may proceed as a separately authorized stage, but this work stops at the Stage 3A verdict.
