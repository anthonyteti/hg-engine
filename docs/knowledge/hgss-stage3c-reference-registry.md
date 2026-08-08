# HGSS Stage 3C symbolic reference registry

## Finding

Project-authored world source can use stable symbolic identities while a
single tracked registry owns every numeric ID used by the proven HeartGold
world pipeline. The registry resolves symbols before the existing serializers
run, validates cross-namespace ownership, and refuses unclassified allocation.

Confidence: **high** for symbolic resolution, collision detection, persistent
allocation behavior, revision coupling, and the controlled Stage 3C proof.
Confidence is **low/unknown** for allocating new NARC members beyond the retail
archive lengths because structural addressability has not yet been confirmed by
an emulator test.

## Architecture

Canonical files:

- `world/registry.json`: persistent allocation/provenance records.
- `fixtures/stage3c_symbolic_registry_world.json`: schema-4 symbolic proof.

Compiler flow:

```text
symbolic world source
  -> load + validate registry
  -> validate symbolic dependency graph
  -> resolve to Stage 3B numeric IR
  -> existing deterministic serializers
  -> generated binaries / NARCs / ARM9
```

`tools/pokeagent/registry.py` owns allocation and reference policy.
`tools/pokeagent/world.py` continues to own binary serialization. The generated
`components/resolved-registry.json` snapshot makes the exact resolution part of
the determinism comparison.

## Persistent allocation rule

Each resource record commits a `symbol`, numeric `id`, and access mode. Existing
records are never recomputed. A new automatic allocation scans numeric ranges in
ascending order, but only ranges explicitly marked `KNOWN_FREE`; the selected
ID is persisted as `PROJECT_ALLOCATED`. Filesystem iteration and hash-modulo
allocation are not used.

The production registry deliberately contains **no `KNOWN_FREE` range yet**.
The Stage 2/3A/3B numeric IDs are represented as
`CONTROLLED_REPLACEMENT`, not silently promoted to free slots. NARC positions
beyond the supported ROM's current member counts remain `UNKNOWN` until an
append/read runtime proof exists.

## Collision domains

Numeric uniqueness is enforced per physical collision domain. In particular,
`local_script_banks`, `common_scripts`, and `script_headers` share
`script_narc`, so numeric ownership conflicts across those logical namespaces
fail. Symbol names are globally unique, which is stricter than per-namespace
uniqueness and keeps `registry resolve <symbol>` unambiguous.

Read-only template symbols may refer to source-backed `VANILLA_OWNED` data.
Writable resources may only own `KNOWN_FREE`, `CONTROLLED_REPLACEMENT`, or
`PROJECT_ALLOCATED` slots. `VANILLA_OWNED`, `RESERVED`, and `UNKNOWN` writable
claims fail.

## Supported revision evidence

Allocation is coupled to the user-local US HeartGold ROM:

- game code: `IPKE`
- ROM SHA-256: `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`
- ARM9 SHA-256: `5eeaa2dcabfb66b4ff5d151687cff2c9214de9e272ba7afdae7a01d57cf319af`

The metadata-only inventory verifies these pristine archive facts:

| Namespace/archive | Path | Members | SHA-256 |
|---|---:|---:|---|
| scripts | `a/0/1/2` | 965 | `bab429408b962c513d3e3ba89f67d8d74d6824563cd30fc317d473edacd05d18` |
| text | `a/0/2/7` | 829 | `570433fadb7f2959c99e73ee446ad7bc770702dd71b472acf51c0e358a51136c` |
| events | `a/0/3/2` | 491 | `70815852d040ed7831830fbec2f9e9282371ff6cf544260b900b9dcd6049c020` |
| matrices | `a/0/4/1` | 288 | `c7254a9e18d40b18e5acd0fe77d1a0e0519b021af05f7a5211b354158db5abdd` |
| map members | `a/0/6/5` | 676 | `0817bd81cc30342bc40dd6ce829121e9a8be4e9d04d0b790f8d9d99688c4bebe` |

Source evidence:

- pret/pokeheartgold revision
  `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`
- `include/map_header.h`: matrix/script/script-header/message/event references
  are `u16`; area data is `u8`.
- `src/map_header.c` and `include/constants/maps.h`: map headers are a fixed
  compiled table of 540 24-byte entries.
- `src/map_matrix.c`: matrix members are NARC-loaded by ID and contain `u16`
  map-member and header grids.
- `src/save_vars_flags.c`, `armips/include/flags.s`, and
  `armips/include/vars.s`: persistent/temporary flag and variable bounds.

## Namespace safety result

Confirmed controlled replacements used by Stage 3C:

- map headers: 538, 9, 10, 11
- map members: 633, 630, 631, 632
- matrix: 1
- event bank: 57
- local script bank: 842
- common/start script: 3
- script header: 399
- text bank: 542

Confirmed source dependencies, read-only: map header 67, map member 0, area-data
bank 2.

Unsupported for new production allocation: flags, variables, and all currently
unproven appended-NARC ranges. An `UNK` constant or blank-looking member is not
free-slot evidence.

## Reproduction

```bash
python -m tools.pokeagent registry validate --json
python -m tools.pokeagent registry inspect --json
python -m tools.pokeagent registry resolve stage3c_proof_northwest_header --json
python -m tools.pokeagent map determinism \
  --fixture fixtures/stage3c_symbolic_registry_world.json --json
make stage3c-registry-proof
python -m tools.pokeagent map test \
  --fixture fixtures/stage3c_symbolic_registry_world.json --json
```

The ignored inventory is written to `build/registry/slot-inventory.json` and
contains only IDs, classifications, counts, and hashes—not extracted members.

## Remaining unknowns

- Whether appending each proven NARC type is runtime-safe in unmodified HGSS.
- Which controlled vanilla replacements are acceptable for the eventual game
  design; Stage 3C proves central ownership, not design policy.
- A production-safe persistent flag/variable block.
- Whether the fixed map-header table should eventually be expanded or managed
  entirely as deliberate replacements.
