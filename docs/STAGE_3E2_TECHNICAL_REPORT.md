# Stage 3E2 technical report: expandable map-header capacity

## Verdict

`STAGE_3E2_HEADER_EXPANSION_PASSED`

The supported US HeartGold revision now has a deterministic, registry-owned
map-header tier beyond the retail 540-entry ARM9 table. Project headers 540 and
541 loaded through normal field gameplay, selected distinct appended world
resources, participated in native matrix adjacency and normal script warps,
survived a real save/reset/Continue cycle, and remained stable for 600 frames.

## Stage 3E1 checkpoint

Stage 3E2 began only after the completed Stage 3E1 tree was intentionally
staged, committed, pushed, and remotely verified:

- commit: `65ddae7b8 Add Stage 3E1 appended world resource capacity`;
- full commit: `65ddae7b842090df6d11594f6047c25504671abc`;
- branch: `main`;
- local `HEAD`, `origin/main`, and `git ls-remote origin main` agreed;
- the worktree was clean before Stage 3E2 source changes.

## Architecture

Stage 3E2 uses a resident hybrid table, not a NARC-backed per-access lookup:

```text
map_id 0..539  -> untouched retail table at 0x020F6BE0
map_id 540..N  -> generated project table[map_id - 540]
other map_id   -> diagnostic invalid count + retail MAP_NOTHING/header 0
```

`src/map_header_expansion.c` implements project-owned equivalents for all 27
public accessors that directly read the retail table. The `hooks` manifest
redirects each retail entry point using HG-Engine's existing eight-byte Thumb
trampoline. Derived helpers already call those accessors, so call-site-wide
patching and runtime archive I/O are unnecessary. Lookup remains constant-time.

The generated table is resident HG-Engine data. Its size is derived from the
contiguous registry-owned project header records and compiled into the final
ARM9. The retail table remains physically unchanged.

## Retail evidence and binary validation

The revision lock is:

- game code `IPKE`;
- ROM SHA-256
  `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`;
- ARM9 SHA-256
  `5eeaa2dcabfb66b4ff5d151687cff2c9214de9e272ba7afdae7a01d57cf319af`;
- pokeheartgold source revision
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`.

Local source and ARM9 inspection established a 540-entry table of 24-byte
records at decompressed file offset `0xF6BE0` / RAM `0x020F6BE0`. Its SHA-256
remained:

`5600bae7c93612a2cb7f96fe4b8e3885657e9fa1a656a7cdb3df8ea9e786ab5a`

The generated 48-byte table contains exact IDs 540 and 541 and hashes to:

`0a518ef966537e7a7e503c47e57a6313dad986767a8f3ecd31838a4e79c176fd`

The complete records are:

- 540: `ff020f002001c503c7035603fb03fb03eb017f11000108f6`
- 541: `ff020f002001c603c8035703fb03fb03ec017f11000108f6`

All 27 patched entry points had the expected `00 4B 18 47 <target|1>` form and
resolved to the corresponding expansion symbol. Golden tests cover entry
size, exact bytes, the 539/540 table boundary, a gap/beyond-count ID, malformed
lengths, and revision/ownership failures. Source inspection verifies that the
runtime selector's one-past branch returns header 0 and records an invalid
lookup.

## Registry and canonical proof

`world/registry.json` adds two explicit header provenances:

- `HEADER_EXPANSION_PROVEN`: revision-locked addressable window 540--541;
- `PROJECT_HEADER`: persistent project ownership in that window.

Retail IDs remain `VANILLA_OWNED`; prior proof slots remain
`CONTROLLED_REPLACEMENT`; IDs beyond the tested window remain `UNKNOWN`.
`allocate_project_header` allocates only the next contiguous ID, never
renumbers existing symbols, and rejects gaps, pins below 540, collisions,
exhaustion, and wrong revisions.

`fixtures/stage3e2_header_expansion_world.json` is a symbolic schema-7 2 x 1
world. Its header grid is `[540, 541]`; its appended map members are 676/677,
events 491/492, local scripts 965/966, script headers 967/968, and text banks
854/855. The matrix is appended member 288. Canonical registry-managed
references are symbolic; serializers receive resolved numeric records.

Header 540 resolves matrix/script/script-header/text/event to
288/965/967/854/491. Header 541 resolves them to
288/966/968/855/492. Both use verified normal-overworld flags, area data 2,
and existing day/night music 1019.

## Runtime proof

All 18 Stage 3E2 assertions passed in headless DeSmuME:

1. controlled start performed a normal field-script warp into header 540;
2. live `Location.mapId` retained 540;
3. every required header-540 bank matched the canonical record;
4. appended matrix 288 exposed header grid `[540, 541]` and members 676/677;
5. west event 491 loaded one NPC and zero warp records;
6. script header 967 and local script 965 loaded;
7. text 854 displayed the expected west message;
8. normal movement/collision worked;
9. walking from world X 31 to 32 performed native adjacency;
10. local X wrapped to zero and `Location.mapId` changed to 541;
11. every required header-541 bank matched the canonical record;
12. east event 492 loaded one NPC and zero warp records;
13. script header 968 and local script 966 loaded;
14. text 855 displayed the expected east message;
15. the east script completed a normal save;
16. the same script performed a normal warp from 541 to 540;
17. emulator reset plus Continue restored saved header 541 and east resources;
18. the restored field remained stable for another 600 frames.

The existing test-only controlled-start hook has one Stage 3E2 guard: marker
46 suppresses re-queuing the bootstrap warp after reset. It does not restore a
map itself; Continue reads the normal battery save, which is why the persisted
541 assertion remains independent of an emulator savestate.

The accessor instrumentation observed 295 project lookups, last header 541,
and zero invalid lookups. The final ignored ROM SHA-256 was:

`a1bd1f9ea26a8eb00ab7b736f2529b10fe406e829fafa2ecbdbdeb292a258e8f`

Ignored evidence is in `build/stage3e2/emulator/`, including reports and six
screenshots. Codex visually inspected the dialogue and post-reload views; the
primitive maps, player, and NPCs rendered normally without model corruption.

## Map-ID width audit

The normal field path is viable above 539:

- `Location.mapId` and field warp inputs are 32-bit;
- persisted `LocalFieldData` stores full `Location` records;
- matrix header cells, event warp destinations, script warp operands, and
  saved map-object IDs are `u16`;
- live map objects use a wider map ID;
- public map-header accessors accept a wide ID after the central patch.

No `u8` map-header truncation was found on ordinary field progression. The
known `u8` matrix cache is a matrix-member ID limitation, not a map-header ID.
Normal save/reload at 541 provides runtime evidence against hidden truncation
in the required persistence path.

Optional/static systems remain separate content-registration work: Town Map
and Fly destination lists, preview lists, special story/minigame comparisons,
and vanilla healing/respawn mappings do not automatically gain project
semantics. They do not truncate the core field identity proved here.

## Determinism

Two clean roots compared all generated Stage 3E2 artifacts with zero
mismatches. This includes the header table and records, resolved registry,
append snapshot, maps/PER/BDHC/NSBMD, matrix, events, scripts, script headers,
text, five rebuilt NARCs, and patched ARM9.

Representative SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| project header table | `0a518ef966537e7a7e503c47e57a6313dad986767a8f3ecd31838a4e79c176fd` |
| header 540 | `d67dfd746ab779efa4162413897a9ff315aa414755915c80a5dbf66895d6ea6b` |
| header 541 | `f559a6267edd9624efc3ee50a54319275a8788660503d223a5659559ff97bfe9` |
| matrix | `33c792192a22bd92105bb991645e1b65fd0ee7f867ff398c93b9fa12c91d9750` |
| resolved registry | `81c5220b69c3df2916e08fffbdf89dd98dddf0c875b404c2a25fc3a163581106` |
| patched ARM9 | `8546fc7413662e02a12a5b596f1b623498d0407a805831db834d9c4d73bd2f75` |

## Tests and regressions

- Full suite: 107 tests ran; 104 passed and 3 opt-in tests skipped.
- Registry validation, preflight, clean determinism, and artifact hygiene:
  passed.
- Stage 2: clean build and headless runtime passed.
- Stage 3A: clean build and headless runtime passed.
- Stage 3B: clean build and headless runtime passed.
- Stage 3C: clean build and headless runtime passed.
- Stage 3D: clean build and headless runtime passed.
- Stage 3E1: clean build and headless runtime passed.
- Stage 3E2: final clean build and all 18 runtime checks passed.

The fixed PER offset `0x14`, normal-overworld BDHC, native matrix transitions,
symbolic registry resolution, append provenance, and revision lock remain
covered.

## DeepSeek investigations

Both bounded calls used `deepseek-ai/DeepSeek-V4-Flash-0731` and supplied only
`src/map_header_expansion.c` (3,849 bytes) plus a narrow prompt.

| Task | Effort / max | Tokens | Cost | Disposition |
|---|---|---:|---:|---|
| review hybrid selector and 539/540 boundaries | medium / 1,200 | no response/usage | unavailable | rejected: provider returned no content |
| mechanical selector safety review | none / 500 | 1,563 prompt + 500 completion = 2,063 | `$0.00023067` | basic branch/arithmetic observations retained; truncated test advice discarded |

Codex independently verified the retained points through source inspection,
unit/golden tests, patched ARM9 bytes, and emulator behavior.

## Confirmed, inferred, and unknown

Confirmed by source, bytes, and runtime:

- resident constant-time project headers 540/541;
- native transition, normal warp in/out, save/reload, field banks, and appended
  world resources using full project identities;
- unchanged retail header bytes and correct 27-accessor redirection;
- deterministic registry/table/ROM inputs.

Confirmed by source/bytes only:

- invalid lookup fallback and diagnostic counter;
- serialized `u16` references can encode values beyond the tested window.

Inferred:

- a deliberately extended contiguous project table should scale with the same
  constant-time lookup architecture.

Unknown/unsupported:

- safe allocation beyond the currently runtime-tested 540--541 window;
- automatic registration in Town Map, Fly, preview, healing, or special-mode
  tables;
- behavior on any other ROM revision;
- production limits imposed by other resource namespaces.

## Recommendation

HeartGold remains the recommended foundation. The fixed retail header table is
no longer a production-capacity blocker for normal field worlds. Stage 4 may
begin as a separate, explicitly scoped checkpoint, while optional UI/story
registrations stay guarded and project-header allocation expands only through
tested revision-locked windows.
