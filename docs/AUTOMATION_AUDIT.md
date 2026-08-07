# HG-Engine Automation Audit

Date: 2026-08-07

Scope: Stage 0 only; no fan-game content was produced.

Repository: `anthonyteti/hg-engine` at `417f4ff0ccfb8a451d7f2c46f4fc3c8d982a32ac`

Upstream reference: `BluRosie/hg-engine` at `c6d63fd8a34f63431214284dc08c3b7942ab0593`

## Executive verdict

**Verdict: `PROCEED_WITH_SPECIFIC_RISK`.**

The native HG-Engine build and a useful emulator-control path already work headlessly. Most gameplay data surfaces are source-driven today, and current open-source projects contain credible readers and writers for the remaining world metadata. The specific risk is the map model step: Pokemon DS Map Studio's useful serializers can be extracted from its GUI, but its final IMD-to-NSBMD conversion calls Nintendo's separately supplied `g3dcvtr.exe`. No maintained, open, general-purpose replacement was confirmed.

Do not scale game content after Stage 1. Stage 2 must pass a one-map, zero-GUI proof case first. The kill gate is an end-to-end build in which a tiny canonical map specification deterministically produces geometry, collision/height data, matrix/header/event changes, a ROM, and an emulator screenshot. If that proof requires manual GUI edits or cannot use a legally available pinned model converter, pause and pivot the map strategy.

## Evidence and classification

Confidence labels used below:

- **Confirmed by test**: executed in this checkout.
- **Confirmed by source inspection**: traced through local or pinned external source.
- **Inferred**: consistent with source and formats, but not exercised end to end.
- **Unknown**: insufficient evidence.

Automation classes:

- `HEADLESS_NOW`: an existing command or build rule performs the operation.
- `HEADLESS_WITH_WRAPPER`: deterministic core logic exists, but a small CLI/library adapter is needed.
- `REQUIRES_FORMAT_IMPLEMENTATION`: the needed writer or integration is absent.
- `GUI_ONLY_TEMPORARILY`: the current user-facing path is GUI-only, but source inspection exposes a credible extraction route.
- `UNKNOWN`: feasibility is not established.

## Baseline confirmed in this checkout

| Check | Result | Evidence |
|---|---|---|
| Repository state before audit | Clean | `git status --short` |
| Native HG-Engine build | Passed | `make -j$(nproc)` produced ignored `test.nds`; 11.39 s elapsed, 179,072 KiB maximum RSS |
| ROM identity guard | Passed | Build and emulator identified US HeartGold, game code `IPKE` |
| Headless emulator boot | Passed | py-desmume/DeSmuME 0.9.12 cycled 213 frames with `SDL_VIDEODRIVER=dummy` |
| Scripted input | Passed | A-button press/release was submitted through `keypad_add_key` / `keypad_rm_key` |
| Screenshot | Passed | Captured a 256 x 384 frame showing the HG copyright/startup screen; PNG SHA-256 `d3128eeccd3eb39c764c4f0be348835a8da3b5df26fa93372ded28ef4b990743` |
| Save state | Passed | Saved and loaded an 11,670,284-byte `.dst` under `/tmp` |
| Existing battle integration tests | Not run | `scripts/run_tests.py` is headless-capable, but the ignored `test.sav` fixture is absent locally; CI downloads it |
| GUI/editor runtimes | Absent | No Java/Javac/Gradle, .NET, DeSmuME executable, melonDS, or Xvfb is installed |
| Container fallback | Unavailable | A Windows Docker shim is visible, but Docker is not integrated with this WSL distribution |

The local ignored inputs and outputs (`rom.nds`, `test.nds`, `base/`, `build/`, emulator saves/states) did not enter Git. One packaging risk remains: the repository has a `Dockerfile` with `ADD . /hg-engine` but no `.dockerignore`, so a future Docker build could copy local ROM material into its build context and layers.

## Current end-to-end build

`Makefile` already implements the basic headless spine:

```text
user-owned rom.nds
  -> ndstool extraction into ignored base/
  -> generated NARCs and compiled C/assembly patches in ignored build/
  -> replacement of selected extracted files
  -> ndstool repack to ignored test.nds
  -> optional py-desmume battle test runner
```

The checked build uses GNU Make, Python, CMake/GCC for host tools, and devkitARM's `arm-none-eabi` toolchain. Host tools include `ndstool`, `armips`, `narcpy.py`, `o2narc`, `msgenc`, `speciesdatagen`, `trainerdatagen`, `movedatagen`, Nitro graphics tools, and audio converters. This is a source-plus-overlay patcher, not a full canonical representation of the original ROM.

Bootstrap reproducibility is incomplete. `nitrogfx` is a pinned submodule and the ndstool Make rule pins a commit, but several downloaded tools use a branch tip. Stage 1 should record resolved tool versions and fail on drift rather than silently rebuilding from newer sources.

## Automation inventory

### 1. ROM extraction, file replacement, NARC packing, and ROM rebuild

- **Class:** `HEADLESS_NOW`; high confidence, confirmed by test.
- **Relevant files:** `Makefile` (including its `move_narc` target), `Dockerfile`, `narcs.mk`, `scripts/make.py`, `tools/ndstool`, `tools/narcpy.py`, `base/`, `build/`, `rom.nds`, `test.nds`.
- **Current workflow:** `make` validates `IPKE`, extracts the base ROM when needed, builds tools/code/data, copies generated files into the extracted tree, and invokes `ndstool -c`.
- **Proposed workflow:** retain Make as the authority. Put a thin Python orchestrator around it for preflight, structured logs, hashes, timeouts, and artifact validation. Do not reimplement ROM packing.
- **Smallest proof:** rebuild with one harmless source change, verify a changed output hash, boot it, then revert the proof change.
- **Risks/unknowns:** first-run network downloads are not all pinned; a truly clean machine bootstrap was not tested; no `.dockerignore`; only US HeartGold is supported by the present guard.

### 2. Map geometry and HGSS land-data container

- **Class:** current path `GUI_ONLY_TEMPORARILY`; target `HEADLESS_WITH_WRAPPER`; a fully open converter is `REQUIRES_FORMAT_IMPLEMENTATION`. Medium confidence, confirmed by source inspection only.
- **Relevant files:** ROM NARC `a/0/6/5`; Pokemon DS Map Studio `editor/grid/MapGrid.java`, `formats/obj/ObjWriter.java`, `formats/imd/ImdModel.java`, `formats/mapbin/MapBinHGSS.java`, and `editor/MainFrame.java`; DSPRE `ROMFiles/MapFile.cs`.
- **Current workflow:** Pokemon DS Map Studio edits a 32 x 32, eight-layer grid in Swing, writes OBJ/IMD, launches `g3dcvtr.exe`, and assembles the HGSS map member. DSPRE can import/edit members through WinForms. HG-Engine currently preserves the base NARC unchanged.
- **Proposed workflow:** define a very small canonical JSON map fixture; extract or port only PDSMS's grid-to-OBJ/IMD and `MapBinHGSS` logic; invoke the converter as a subprocess; replace one NARC member with existing `narcpy.py`; wire the generated NARC into Make. Treat PDSMS as a format oracle, not a required GUI.
- **Smallest proof:** one flat 32 x 32 outdoor map using one existing texture set, no decorative buildings, and a deterministic byte-for-byte rebuild.
- **Risks/unknowns:** `g3dcvtr.exe` is proprietary, absent from PDSMS, and untested here; Java is absent locally; licensing/distribution and Wine behavior need explicit resolution; no credible maintained open OBJ/GLB-to-NSBMD compiler was confirmed. Apicula reads/extracts Nintendo models but is not this writer.

`MapBinHGSS.java` confirms the member layout as BGS data followed by PER, BLD, NSBMD, and BDHC, with a 16-byte length header for the latter four regions. That is enough to make container assembly headless; it does not solve NSBMD generation.

### 3. Collision permissions and height data

- **Class:** `HEADLESS_WITH_WRAPPER`; medium-high confidence, confirmed by source inspection.
- **Relevant files:** PDSMS `formats/collisions/Collisions.java` and `formats/bdhc/BdhcWriterHGSS.java`; embedded PER and BDHC regions inside each `a/0/6/5` member.
- **Current workflow:** edited and exported from PDSMS dialogs.
- **Proposed workflow:** port or isolate these deterministic writers behind the same canonical map schema, with explicit tile permission, height, slope, and camera fields.
- **Smallest proof:** flat walkable plane, one blocked tile, and one height transition; round-trip the bytes and confirm collision in emulator.
- **Risks/unknowns:** semantic meanings and safe ranges of all permission/BDHC fields are not fully documented; visual geometry and collision coordinates must be tested together.

### 4. Map matrices

- **Class:** `HEADLESS_WITH_WRAPPER`; high confidence, confirmed by source inspection.
- **Relevant files:** ROM NARC `a/0/4/1`; DSPRE `ROMFiles/GameMatrix.cs`; pokeheartgold `src/map_matrix.c` and `files/fielddata/mapmatrix/map_matrix/*.bin`.
- **Current workflow:** DSPRE's WinForms matrix editor serializes the binary. HG-Engine preserves the base NARC.
- **Proposed workflow:** implement the small documented binary structure in a project-owned deterministic module or extract DSPRE's serializer: width, height, header-grid flag, altitude-grid flag, name length/name, optional `u16` header grid, optional `u8` altitude grid, then `u16` map-model indices.
- **Smallest proof:** replace one 1 x 1 matrix entry and verify parsing, NARC rebuild, and boot.
- **Risks/unknowns:** map/header index coupling and altitude semantics must be validated; malformed dimensions can make areas unloadable.

### 5. Map headers and per-map music assignment

- **Class:** `HEADLESS_WITH_WRAPPER`; medium-high confidence, confirmed by source inspection.
- **Relevant files:** base ARM9 map-header table; DSPRE `ROMFiles/MapHeader.cs` and `RomInfo.cs`; pokeheartgold `include/map_header.h` and `src/data/map_headers.h`; HG-Engine `src/music_tables.c` for battle/trainer music only.
- **Current workflow:** DSPRE edits the fixed 24-byte HGSS entries in ARM9. The current HG-Engine source tree does not generate the vanilla map-header table.
- **Proposed workflow:** serialize a canonical map-header record and patch only the selected ARM9 entry during the existing extracted-ROM phase. Keep a checked assertion on the supported ROM revision and original bytes. Consider DSPRE's dynamic-header NARC patch only later because it is a larger upstream engine modification.
- **Smallest proof:** change one test map's day/night music IDs, rebuild, and verify both the bytes and audible/observable behavior.
- **Risks/unknowns:** table offset/revision coupling; incorrect matrix, script, event, text, encounter, or area IDs can cross-link unrelated data. DSPRE's ds-rom YAML header is the Nintendo ROM header, not these Pokemon map headers.

### 6. Area data, textures, and buildings

- **Class:** `HEADLESS_WITH_WRAPPER` for reusing existing records/assets; `REQUIRES_FORMAT_IMPLEMENTATION` for creating arbitrary new NSBTX/NSBMD assets. Medium-low confidence.
- **Relevant files:** area data `a/0/4/2`, exterior building models `a/0/4/0`, building configuration `a/0/4/3`, map textures `a/0/4/4`, building textures `a/0/7/0`; DSPRE area, map, NSBTX, and building editor code; PDSMS BLD/BGS writers.
- **Current workflow:** GUI editors select and mutate these records. HG-Engine preserves the original NARCs.
- **Proposed workflow:** for the first proof, reference an existing area-data record and texture/building set; expose record serializers only as needed. Defer arbitrary texture/model import until the model-conversion decision is resolved.
- **Smallest proof:** a map using an existing tileset with zero buildings, then one existing building reference.
- **Risks/unknowns:** palette/material constraints, model-to-texture associations, BLD semantics, and index expansion are not yet tested. New asset import shares the proprietary converter risk.

### 7. Warps, NPCs, triggers, and event placement

- **Class:** `HEADLESS_WITH_WRAPPER`; high confidence for the binary format, medium confidence for HG-Engine integration.
- **Relevant files:** event NARC `a/0/3/2`; DSPRE `ROMFiles/EventFile.cs`; Uxie `src/event_file/binary.rs` and HGSS JSON support; pokeheartgold `files/fielddata/eventdata/zone_event/*.json` and its JSON template.
- **Current workflow:** DSPRE edits events through WinForms; HG-Engine does not generate the event NARC.
- **Proposed workflow:** use a small JSON schema aligned with pokeheartgold, serialize with a pinned Uxie library/CLI extension or a minimal project-owned writer, and replace one NARC member.
- **Smallest proof:** one reciprocal warp and one stationary NPC with a known script ID; assert coordinates and round-trip bytes, then interact in emulator.
- **Risks/unknowns:** direction/coordinate conventions and global script/flag IDs; Uxie's CLI is mostly read-oriented today even though its library contains binary writers; Rust is not installed locally.

### 8. Field scripts, flags, variables, items, and trainer battles

- **Class:** `HEADLESS_NOW` for hand-authored assembly already supported by HG-Engine; `HEADLESS_WITH_WRAPPER` for higher-level canonical input. Medium-high confidence.
- **Relevant files:** script NARC `a/0/1/2`; `armips/scr_seq/`, `armips/include/scriptmacros.s`, `armips/include/flags.s`, `armips/include/vars.s`, `armips/global.s`; DSPRE `ROMFiles/ScriptFile.cs`; pokeheartgold `files/fielddata/script/scr_seq/*.s`.
- **Current workflow:** HG-Engine assembles tracked custom/common scripts and overlays generated members; DSPRE provides GUI/plaintext import-export for broader vanilla scripts.
- **Proposed workflow:** first use the established armips syntax directly. Add a deterministic ID registry and a thin generator only for repetitive declarations; never let an LLM allocate raw flag/variable/script IDs independently.
- **Smallest proof:** an NPC script with dialogue, one guarded item grant, a persistent flag, and a trainer-battle command, using reserved test IDs.
- **Risks/unknowns:** incomplete vanilla script decompilation, ID collisions, command variant differences, and cross-references to trainers/text/events. The initial proof should modify one existing script slot, not expand tables.

### 9. Dialogue and message archives

- **Class:** `HEADLESS_NOW`; high confidence, confirmed by successful build.
- **Relevant files:** `data/text/*.txt`, `tools/msgenc`, `narcs.mk`, output text NARC `a/0/2/7`.
- **Current workflow:** tracked text files are encoded and packed by Make.
- **Proposed workflow:** keep text canonical in the existing format; add validation for archive/member IDs, control codes, line limits, and references from scripts.
- **Smallest proof:** alter one test string, rebuild, and read it through the proof NPC.
- **Risks/unknowns:** character map/control-code constraints and collisions with untracked vanilla archive members.

### 10. Trainers and trainer parties

- **Class:** `HEADLESS_NOW`; high confidence, confirmed by build/source inspection.
- **Relevant files:** `data/Trainers.c`, `tools/trainerdatagen`, trainer NARCs `a/0/5/5` and `a/0/5/6`, trainer text outputs `a/0/5/7` and `a/1/3/1`.
- **Current workflow:** C source is compiled by the trainer generator and packed by Make.
- **Proposed workflow:** retain the C schema; add ID/reference validation and one small fixture test.
- **Smallest proof:** one reserved test trainer referenced by the proof field script and exercised in emulator.
- **Risks/unknowns:** trainer-class/name text coupling, party type flags, AI masks, and table-size limits.

### 11. Wild encounters

- **Class:** `HEADLESS_NOW` for HG-Engine's current encounter tables; `HEADLESS_WITH_WRAPPER` for map-level canonical JSON. High confidence.
- **Relevant files:** `data/Encounters.c`, `data/SafariEncounters.c`, `data/Headbutt.c`, output HeartGold encounter NARC `a/0/3/7`; Uxie encounter reader/writer; pokeheartgold `files/fielddata/encountdata/gs_enc_data.json`.
- **Current workflow:** C data is converted with the HG-Engine build.
- **Proposed workflow:** preserve current source initially; validate species/level/rate bounds and map-header encounter IDs. JSON can be considered only if it reduces, rather than duplicates, canonical sources.
- **Smallest proof:** change one slot on the proof map and force/observe an encounter.
- **Risks/unknowns:** time-of-day and method-specific tables, swarm/radio dependencies, and header linkage.

### 12. Pokemon personal data

- **Class:** `HEADLESS_NOW`; high confidence.
- **Relevant files:** `data/Species.c`, `include/species_data.h`, `tools/speciesdatagen`, output `a/0/0/2`.
- **Current workflow:** typed C definitions are converted and packed by Make.
- **Proposed workflow:** keep these files canonical and add schema/range/reference checks before generation.
- **Smallest proof:** a non-content test-only field change followed by generator and binary inspection; do not create a new species during infrastructure stages.
- **Risks/unknowns:** parallel tables and sprite/icon/cry/evolution/learnset references must remain aligned.

### 13. Forms, evolutions, learnsets, and related species tables

- **Class:** `HEADLESS_NOW`; high confidence.
- **Relevant files:** `data/PokeFormDataTbl.c`, `data/FormToSpeciesMapping.c`, `data/FormReversionMapping.c`, `data/Evolutions.c`, `data/learnsets/learnsets.json`, `data/HiddenAbilityTable.c`, `data/FollowerProperties.c`, and generated includes.
- **Current workflow:** Make generates or compiles these tracked sources.
- **Proposed workflow:** preserve the existing representations; add a cross-table validator for species/form IDs and archive cardinality.
- **Smallest proof:** parse all current canonical files and report dangling/out-of-range references without changing content.
- **Risks/unknowns:** many tables are positional, so an individually valid edit can still misalign related data.

### 14. Battle sprites, icons, and overworld/follower graphics

- **Class:** `HEADLESS_NOW` for established HG-Engine graphics inputs; `HEADLESS_WITH_WRAPPER` for ergonomic asset import. Medium-high confidence.
- **Relevant files:** `data/graphics/pokegra.mk`, `data/graphics/sprites/` (including each species' `icon.png`), `data/graphics/overworlds/`, `armips/asm/sprites.s`, `armips/asm/overworlds.s`, `data/IconPaletteTable.c`, `data/SpriteOffsets.c`, `tools/nitrogfx`, `tools/btx`, `tools/overworld-btx.py`.
- **Current workflow:** Make and graphics tools encode assets and patch tables/NARCs.
- **Proposed workflow:** add deterministic PNG dimension/palette/transparency checks and a manifest tying assets to IDs; keep generated binary graphics ignored.
- **Smallest proof:** round-trip one existing fixture through validation and generation, comparing dimensions and output hashes.
- **Risks/unknowns:** palette limits, animation frames, female/form variants, sprite offsets, follower model associations, and index expansion.

### 15. Moves and battle scripts/animations

- **Class:** `HEADLESS_NOW`; high confidence.
- **Relevant files:** `data/Moves.c`, `tools/movedatagen`, output `a/0/1/1`, battle script source directories, `armips/move/move_anim/*.s`, and `armips/include/movemacros.s`.
- **Current workflow:** generator plus assembler/build rules.
- **Proposed workflow:** retain current source and add cross-reference validation for effect scripts, animations, text, types, and IDs.
- **Smallest proof:** validate every current move reference; use an existing move in battle tests rather than authoring content.
- **Risks/unknowns:** script-engine behavior is code-sensitive; semantic validation is more important than binary serialization.

### 16. Abilities

- **Class:** `HEADLESS_NOW`, source-driven rather than table-driven; high confidence.
- **Relevant files:** `include/constants/ability.h`, `src/battle/ability.c`, ability-related battle code/scripts, `armips/asm/abilities.s`, and ability-name text archives.
- **Current workflow:** C/assembly implementation and constants compile into engine patches.
- **Proposed workflow:** continue treating abilities as code features; require focused battle tests and text/reference validation.
- **Smallest proof:** run an existing ability's targeted battle test after the battle save fixture is restored.
- **Risks/unknowns:** there is no single ability-data serializer; behavior can span hooks, scripts, UI text, AI, and edge cases.

### 17. Items

- **Class:** `HEADLESS_NOW`; high confidence.
- **Relevant files:** `data/itemdata/itemdata.c`, `data/itemdata/itemdata.mk`, item graphics rules/assets, `include/constants/item.h`, `src/item.c`, and item/battle scripts.
- **Current workflow:** tracked C data is generated/packed by Make.
- **Proposed workflow:** keep the current table canonical and add ID, effect, text, price, pocket, icon, and script-reference checks.
- **Smallest proof:** validate and rebuild one existing item fixture; use that item in the proof field script without adding new content.
- **Risks/unknowns:** item effects are split across data and code/scripts; table expansion limits need separate proof before new IDs are allocated.

### 18. Audio and music

- **Class:** `HEADLESS_NOW` for existing sound conversion and battle/trainer assignment; `HEADLESS_WITH_WRAPPER` for map day/night assignment. Medium confidence.
- **Relevant files:** `tools/SDATTool.py`, `tools/ntrWavTool.py`, `tools/adpcm-xq`, `armips/asm/cries.s`, audio source/build rules, `src/music_tables.c`, and map headers for field music IDs.
- **Current workflow:** command-line converters and source tables handle supported assets; map music remains embedded in headers.
- **Proposed workflow:** validate source sample format and target IDs, then route field music through the map-header serializer described above.
- **Smallest proof:** reference an existing track on the proof map; do not add a new composition or sound library.
- **Risks/unknowns:** SDAT bank/sequence constraints, looping metadata, volume, and archive growth; arbitrary music import was not tested.

### 19. Emulator verification, input, screenshots, save states, and smoke tests

- **Class:** `HEADLESS_NOW` at the binding/API level; `HEADLESS_WITH_WRAPPER` for a stable project QA command. High confidence, confirmed by test.
- **Relevant files:** `requirements.txt`, `scripts/run_tests.py`, `scripts/run_tests.sh`, `.github/workflows/build.yml`, py-desmume's `desmume/emulator.py`, ignored `test.nds` and `test.sav`.
- **Current workflow:** CI sets `SDL_VIDEODRIVER=dummy`, downloads a battle-test save, builds with `AUTO_TEST=Y`, and runs partitioned DeSmuME tests using a memory communication address. Locally, the same binding can cycle frames, press keys/touch, capture images, access memory, and save/load states.
- **Proposed workflow:** add a small emulator adapter with declarative actions (`wait`, `press`, `touch`, `load_state`, `capture`, memory assertions), deterministic timeouts, screenshot hashes/artifacts, and a distinct boot smoke test that does not require the battle fixture.
- **Smallest proof:** build, boot to a known frame, press A, capture a screenshot, and assert a stable pixel-region/hash policy; then add a map proof using a pinned save or test-only warp hook.
- **Risks/unknowns:** screenshots can vary with emulator/render settings; save states are emulator/version-specific; the local battle suite remains blocked by missing `test.sav`; DeSmuME 0.9.12 compatibility is not equivalent to hardware or melonDS compatibility.

## External tool assessment

The source snapshots below were inspected in temporary directories and were not added to this repository.

| Project | Inspected revision | Useful automation surface | Decision |
|---|---|---|---|
| [Pokemon DS Map Studio](https://github.com/Trifindo/Pokemon-DS-Map-Studio) | `ac30b653e5b090ce116278ed6ba9758fff956673`, 2021-07-13 | Java serializers for grid/OBJ/IMD, PER, BDHC, BGS/BLD, and HGSS map container | Extract/wrap the smallest core for a Stage 2 spike; do not automate Swing. Project is stale and the NSBMD step depends on external `g3dcvtr.exe`. |
| [DSPRE](https://github.com/DS-Pokemon-Rom-Editor/DSPRE) | `d86737dfccaec7a603a6f27474180a49945158a6`, 2026-07-30 | C# readers/writers for maps, matrices, headers, events, scripts, text, trainers, encounters, and NARCs; invokes bundled `dsrom` CLI for ROM extract/build | Use as current format/reference code. Extract serializers or port small formats; do not make WinForms or .NET Framework a production dependency. |
| [pret/pokeheartgold](https://github.com/pret/pokeheartgold) | `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`, 2026-08-06 | Canonical C/JSON/assembly definitions for headers, events, encounters, scripts, and matrix parser | Primary schema and naming reference. It still retains opaque world geometry and binary matrices and is not a drop-in HG-Engine builder. |
| [Uxie](https://github.com/KalaayPT/uxie) | `8cc3bc57e2663a87bb5e2bbdbb699311adb4cbd2`, 2026-08-02, v0.9.3 | Rust parsers and library writers for HGSS events, encounters, map headers, and NARCs; adapters for DSPRE/ds-rom/decomp projects | Strong Stage 2 library/reference candidate. Extend a pinned CLI or port only needed writers; HGSS support is documented as partial and Rust is absent locally. |
| `ndstool` / `narcpy.py` in HG-Engine | Current local build | ROM and NARC pack/unpack | Keep as the immediate production path because it is already integrated and tested. |
| Apicula | Assessed from DSPRE/PDSMS usage and project scope | Nintendo DS model viewing/extraction/conversion out of NSBMD | Useful for inspection, not confirmed as an NSBMD writer. |
| `dsrom` bundled by DSPRE | Current DSPRE snapshot | Headless `extract` and `build` using project YAML | Credible alternative ROM container backend, but no migration benefit over the working HG-Engine build was demonstrated. |

PDSMS invokes `g3dcvtr.exe <imd> -eboth|-emdl -o <output>` through `ProcessBuilder` (and Wine on Linux). The converter is deliberately not shipped. Any production use must document acquisition, hash, invocation, license constraints, and CI availability. It must never be committed if redistribution is not authorized.

Exact extraction/wrapper targets worth spiking are:

- PDSMS: `MapGrid.saveMapToOBJ`, the `ImdModel` OBJ constructors plus `saveToXML`, `Collisions.toByteArray`, `BdhcWriterHGSS.bdhcToByteArray`, and `MapBinHGSS.toByteArray`. Their data dependencies need separation from Swing/editor state before use.
- DSPRE: `Narc.Open` / `FromFolder` / `Save`, `MapHeader.LoadFromByteArray` / `SaveFile`, and the serialization portions of `GameMatrix.SaveToFileDefaultDir` and `EventFile.SaveToFileDefaultDir`. Porting the small pure portions is preferable to importing WinForms dependencies.
- Uxie: `EventFile::to_binary_for`, `BinaryEncounterFile::to_binary`, `write_map_header_to_bytes`, and `Narc::to_bytes` / `write_to_file`. Its NARC API can read and rebuild archives, but a clean public member-replacement operation still needs an adapter.

## Canonical source boundary

Use the existing HG-Engine source files whenever a surface is already source-driven. New project-owned canonical data should be introduced only for world structures HG-Engine currently leaves opaque:

```text
canonical world fixture (small JSON/TOML documents)
  -> validated IDs and cross-references
  -> deterministic serializers/converters
  -> generated members under build/
  -> generated NARCs under build/
  -> existing HG-Engine replacement/repack steps
  -> ignored test.nds
  -> headless emulator evidence under build/
```

Generated map binaries, NARCs, ROMs, screenshots, logs, and save states must stay under ignored `build/` or another explicitly ignored directory. The base ROM and extracted assets remain user-local inputs. Do not copy opaque assets from pokeheartgold or other ROM-derived repositories into project-owned source merely because they are available.

## Recommended Stage 1 architecture

Stage 1 should build only the orchestration and safety spine. It should not implement a map DSL, import external editor code, add species, write story, or generate bulk assets.

Create these files first:

```text
.dockerignore
tools/pokeagent/__init__.py
tools/pokeagent/__main__.py
tools/pokeagent/cli.py
tools/pokeagent/command.py
tools/pokeagent/rom.py
tools/pokeagent/emulator.py
tests/test_pokeagent_rom.py
tests/test_pokeagent_emulator.py
docs/knowledge/toolchain-baseline.md
```

Responsibilities:

- `.dockerignore`: exclude `*.nds`, saves/states, `base/`, `build/`, `.venv/`, `.git/`, logs, and local tools so Docker cannot ingest ROM material accidentally.
- `cli.py` / `__main__.py`: expose only `preflight`, `rom build`, and `rom smoke` initially.
- `command.py`: subprocess execution with structured command, duration, exit status, and bounded log capture; no shell interpolation.
- `rom.py`: validate the input game code, verify ignored input/output locations, call the existing Make targets, and validate the resulting ROM identity/hash/size.
- `emulator.py`: set the dummy SDL driver, boot for bounded frames, execute a tiny input sequence, capture screenshots, and optionally save/load a state. It must not contain game-specific navigation yet.
- tests: unit-test preflight and command construction without a commercial ROM; mark the local ROM smoke as an explicit integration test.
- `toolchain-baseline.md`: record tool versions, resolved source commits, supported host assumptions, reproduction commands, and the remaining unpinned dependencies.

Use the standard library (`argparse`, `subprocess`, `pathlib`, `json`, `hashlib`) and the already pinned py-desmume/Pillow environment. Do not add a workflow engine, database, web service, agent protocol, or new package manager in Stage 1.

Stage 1 acceptance criteria:

1. `python -m tools.pokeagent preflight` reports missing prerequisites and confirms ROM/output paths are ignored.
2. `python -m tools.pokeagent rom build` delegates to Make and emits a compact machine-readable report under ignored `build/`.
3. `python -m tools.pokeagent rom smoke` boots headlessly, injects one input, captures a frame, and exits with a bounded timeout.
4. Unit tests run without a ROM; the integration smoke skips clearly when `rom.nds` is absent.
5. No copyrighted or generated artifact becomes tracked.

## Stage 2 proof and kill gates

After Stage 1, implement exactly one representative map pipeline, not content volume:

1. Pin the external source revisions and write a tiny canonical flat-map fixture.
2. Generate or reuse one existing texture set.
3. Generate PER and BDHC; assemble one HGSS map member.
4. Generate one 1 x 1 matrix, patch one map header, and serialize one event file.
5. Add one armips script and one existing text entry using reserved test IDs.
6. Repack through the existing Make pipeline.
7. Boot from a controlled save/test hook, walk against the blocked tile, use the warp, talk to the NPC, and capture screenshots/log assertions.
8. Rebuild twice from clean generated directories and compare all generated member/NARC hashes.

Proceed to broader automation only if every step is command-line driven and reproducible. Pause and choose one of these explicit pivots if the model step fails:

- legally provision and pin `g3dcvtr` as a local, non-redistributed prerequisite;
- constrain early maps to modified/recombined existing NSBMD members while an open writer is researched;
- implement the minimal NSBMD writer required by the proof fixture, with golden tests against independently readable output;
- change the project scope if none is sustainable.

## Confirmed facts, inferences, and open blockers

### Confirmed

- HG-Engine builds and repacks a US HeartGold ROM headlessly in this checkout.
- py-desmume can boot that output with a dummy SDL driver, send input, capture pixels, and save/load states.
- HG-Engine already provides canonical, deterministic paths for the major gameplay data categories.
- HG-Engine does not currently own canonical world map, matrix, header, event, area-data, texture, or building sources.
- PDSMS contains separable HGSS map/container/collision serializers but shells out to a separately supplied Nintendo converter for NSBMD.
- DSPRE is current and serializer-rich, but its primary application remains Windows Forms/.NET Framework 4.8.
- pokeheartgold now supplies excellent schema/reference coverage for headers, events, encounters, scripts, and the matrix binary layout; it still does not supply a source map-model pipeline.
- Uxie contains useful HGSS binary writers in its Rust library, while its public CLI remains primarily inspection-oriented.

### Inferred

- A small headless wrapper/port can cover matrices, headers, events, map-container assembly, PER, and BDHC without a GUI.
- Existing HG-Engine NARC packing can integrate those generated members without restructuring upstream.
- A stable map smoke test can be built on py-desmume once a controlled save or test-only starting hook is defined.

### Blocking risks before content production

- The legal, available, reproducible NSBMD writer/converter path is unresolved.
- The full one-map generated output has not been loaded in game.
- Cross-format coordinate/index semantics have not been validated as one system.
- The local battle-test save fixture is missing.
- Fresh-machine bootstrap and all external tool revisions are not yet reproducibly pinned.

## Recommended next task

Perform Stage 1 exactly as scoped above: add the minimal `tools.pokeagent` build/smoke wrapper, tests, `.dockerignore`, and a pinned toolchain baseline. Do not begin game-content production and do not start map-format implementation until that wrapper can repeatedly build and headlessly boot the unchanged baseline.
