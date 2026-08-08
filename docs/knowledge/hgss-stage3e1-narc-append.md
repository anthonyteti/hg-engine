# HGSS Stage 3E1 world-resource NARC append

## Finding

The US HeartGold runtime can load newly appended members from each NARC used
by the proven world pipeline. The project may now allocate a small,
revision-locked, contiguous append window for map members, matrices, events,
the shared script NARC, and text. This is new archive capacity, not an unused
vanilla-slot claim.

Confidence is **high inside the exact tested windows and build pipeline**.
This proof does not establish the whole `u16` domain, map-header capacity, or
other archives.

## Supported revision and pristine evidence

- game code: `IPKE`
- ROM SHA-256:
  `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`
- ARM9 SHA-256:
  `5eeaa2dcabfb66b4ff5d151687cff2c9214de9e272ba7afdae7a01d57cf319af`
- pret/pokeheartgold evidence revision:
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`

| Resource | Path | Retail members | Retail NARC SHA-256 |
|---|---|---:|---|
| map members | `a/0/6/5` | 676 | `0817bd81cc30342bc40dd6ce829121e9a8be4e9d04d0b790f8d9d99688c4bebe` |
| matrices | `a/0/4/1` | 288 | `c7254a9e18d40b18e5acd0fe77d1a0e0519b021af05f7a5211b354158db5abdd` |
| events | `a/0/3/2` | 491 | `70815852d040ed7831830fbec2f9e9282371ff6cf544260b900b9dcd6049c020` |
| scripts | `a/0/1/2` | 965 | `bab429408b962c513d3e3ba89f67d8d74d6824563cd30fc317d473edacd05d18` |
| text | `a/0/2/7` | 829 | `570433fadb7f2959c99e73ee446ad7bc770702dd71b472acf51c0e358a51136c` |

The metadata inventory contains hashes/counts only. It does not redistribute
member bytes.

## NARC mechanics

`src/filesystem.c` in the inspected pokeheartgold revision is the primary
runtime evidence. `NARC_New` reads BTAF's `u16 num_files`. Member APIs assert
`file_id < num_files` and locate the FAT record at
`btaf_start + 12 + 8 * file_id`. The inspected matrix, land-data, event,
script, script-header, and message callers pass their header/matrix `u16`
references into those APIs. No retail archive-count constant was found in
these lookup paths.

Project generation uses `ndspy.NARC.files.append` in sorted numeric order.
After serialization it reloads the archive and verifies:

- BTAF `num_files` equals the parsed member count;
- no undeclared pre-existing member changed;
- each generated member exists byte-for-byte at its resolved ID;
- no gap was created.

The ROM copy of every rebuilt proof NARC was byte-identical to the file under
`base/root`, confirming HG-Engine/`ndstool` repacking preserved it.

## Proven windows and ownership

| Collision domain | Persistent project IDs | Runtime use | Rebuilt count |
|---|---|---|---:|
| map NARC | 676, 677 | both active through native adjacency | 678 |
| matrix NARC | 288, 289 | 288 loaded; 289 is a binary tail probe | 290 |
| event NARC | 491, 492 | both loaded with distinct NPC records | 493 |
| script NARC | 965, 966, 967, 968 | local scripts 965/966 execute; headers 967/968 load | 969 |
| text NARC | 854, 855 | both display distinct dialogue | 856 |

The text exception is important. HG-Engine rebuilds `a/0/2/7` from tracked
text sources to 854 members before the world installer runs. IDs 829--853 are
therefore `ENGINE_OWNED`, not project append capacity. Stage 3E1 appends 854
and 855 to the engine-produced source while retaining the retail boundary 829
as evidence.

The script NARC is one physical collision domain shared by local scripts,
common scripts, and script headers. Allocation across those logical
namespaces is globally contiguous and collision-checked. Proof member 3
remains the explicit controlled-start replacement; it is not appended.

## Registry policy

Stage 3E1 adds three provenance classifications:

- `APPEND_PROVEN`: a revision-locked range whose append mechanism was tested;
- `PROJECT_APPENDED`: a persistent project-owned member within that range;
- `ENGINE_OWNED`: post-retail members produced by HG-Engine before project
  world installation.

Each append-enabled namespace records archive, pristine count, allocation
start, proven maximum, and a contiguous policy. Allocation verifies the ROM
revision first, selects the next free ID across the physical collision domain,
persists it, and never recalculates existing allocations. Pins below the
boundary, gaps, collisions, exhaustion, unproven archives, or mismatched
scanner evidence fail deterministically.

## Runtime evidence

The schema-6 fixture starts on header 538, whose live header reference names
matrix 288. Runtime memory showed a 2 x 1 grid `[676, 677]`, active member 676,
event 491, local script 965, script header 967, and text 854. The west script
set marker 43 and displayed its expected bank.

Normal walking crossed X 31 to X 32 with no warp records. Header 9 then named
the same matrix, active member 677, event 492, local script 966, script header
968, and text 855. The east script set marker 44 and displayed its expected
bank. Movement continued and the game remained stable for 600 more frames.

One implementation detail is intentionally exposed: `MapMatrix_Load` accepts
the full `u16` ID, but the loaded `MapMatrix` structure caches `matrix_id` in a
`u8`. Matrix 288 therefore appears there as 32. The proof identifies the full
ID from the live map-header entry and validates the loaded grid/member bytes;
the truncated cache must not be used as sole identity evidence.

## Reproduction

```bash
.venv/bin/python -m tools.pokeagent registry validate --json
.venv/bin/python -m tools.pokeagent map determinism \
  --fixture fixtures/stage3e1_narc_append_world.json --json
make stage3e1-narc-append-proof -j16
.venv/bin/python -m tools.pokeagent map test \
  --fixture fixtures/stage3e1_narc_append_world.json --timeout 360 --json
```

Ignored evidence is under `build/stage3e1/`. Canonical source, registry
records, tests, and documentation remain tracked.

## Confidence boundary and unknowns

Confirmed by source, generated bytes, ROM parsing, and runtime:

- count-driven lookup for all five archive paths;
- the exact append windows above;
- shared script-NARC collision handling;
- first/later appended runtime members except matrix 289, which is a binary
  second-position probe;
- native traversal between appended land-data members;
- deterministic rebuilding and repacking.

Confirmed by source/bytes only:

- matrix member 289 is present and valid at the second appended position;
- references are wide enough beyond the tested values.

Unknown or unsupported:

- practical limits beyond these small windows;
- sparse/gapped append ownership;
- append safety for any other NARC;
- other ROM regions/revisions;
- expansion of the fixed 540-entry map-header table;
- whether every use of the truncated matrix-ID cache is safe for arbitrary
  appended IDs. Stage 3E2 must address header capacity separately.
