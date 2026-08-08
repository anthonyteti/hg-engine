# Stage 3C technical report: symbolic reference and ID registry

## Verdict

`STAGE_3C_REGISTRY_PROOF_PASSED`

One tracked symbolic world source resolves through one tracked, revision-locked
registry into collision-free numeric HeartGold references. The existing world
serializers generate deterministic artifacts, HG-Engine builds the ROM, and the
headless emulator completes all inherited native multi-map assertions.

Stage 3C adds no map, geometry, BDHC, building, asset-import, or game-content
capability.

## Architecture and canonical format

The durable registry is `world/registry.json` (schema 1). It is human-readable,
sorted, diffable JSON with:

- exact target ROM/ARM9/archive revision evidence;
- namespace storage and numeric bounds;
- collision domains;
- classified ranges and evidence-backed slot overrides;
- persistent symbol-to-ID records;
- explicit `write` or `read_only` access.

The proof source is `fixtures/stage3c_symbolic_registry_world.json` (schema 4).
Every registry-owned reference in this path is a string, including map headers,
map members, matrix, event/script/script-header/text banks, the start script,
the model template, area-data dependency, and map-header template. Raw numeric
references in those fields fail with `numeric_reference`.

Resolution produces the already-proven Stage 3B numeric intermediate form:

```text
schema-4 symbolic source
  -> registry load and target validation
  -> namespace and dependency-graph validation
  -> stable numeric resolution
  -> schema-3 serializer IR
  -> unchanged map/PER/BDHC/matrix/header/event/script/text serializers
```

Allocation logic is isolated in `tools/pokeagent/registry.py`; binary
serializers remain allocation-agnostic.

## Namespaces and allocation safety

| Namespace | Storage/limit | Stage 3C policy | Actual proof IDs |
|---|---|---|---|
| map headers | fixed ARM9 table, 540 × 24 bytes | controlled replacement only | 538, 9, 10, 11 |
| map members | 676-member land NARC; matrix field is `u16` | controlled replacement; appended IDs unknown | 633, 630, 631, 632 |
| matrices | 288-member NARC; header field is `u16` | controlled replacement; appended IDs unknown | 1 |
| event banks | 491-member NARC; header field is `u16` | controlled replacement; appended IDs unknown | 57 |
| local script banks | shared 965-member script NARC, `u16` | controlled replacement | 842 |
| common scripts | shared 965-member script NARC | controlled replacement | 3 |
| script headers | shared 965-member script NARC, `u16` | controlled replacement/reference | 399 |
| text banks | 829-member NARC; header field is `u16` | controlled replacement; appended IDs unknown | 542 |
| flags | persistent and temporary engine domains | unsupported for allocation | none |
| variables | `0x4000..0x416F` source-bounded domain | unsupported; Stage 2 marker remains test-controlled | none in Stage 3C |
| area-data banks | map-header `u8` | read-only pending separate audit | 2 template dependency |

The registry contains no `KNOWN_FREE` production range. This is intentional:
Stage 2/3A/3B proof IDs are `CONTROLLED_REPLACEMENT`, not automatically blessed
as free. Existing vanilla members are `VANILLA_OWNED`; structurally addressable
but untested appended ranges are `UNKNOWN`; temporary engine domains are
`RESERVED` where source establishes special semantics.

## Stable allocation behavior

Allocation records are persistent. The allocator never derives existing IDs
from sort position, filesystem enumeration, or a hash. A unit proof allocated
A/B/C, recorded their IDs, added unrelated D, and confirmed A/B/C were
unchanged. Removing or reintroducing an unrelated record therefore cannot
renumber committed resources.

Automatic allocation scans only explicitly `KNOWN_FREE` ranges in numeric
order, then persists the selected ID as `PROJECT_ALLOCATED`. Exhaustion fails.
Because the production registry has no proven free range, it refuses automatic
production allocation today while still centrally and safely owning the
deliberate replacement set used by the compiler.

## Symbolic proof resolution

The four authored maps are:

- `stage3c_proof_northwest`
- `stage3c_proof_northeast`
- `stage3c_proof_southwest`
- `stage3c_proof_southeast`

Resolution yielded:

| Symbolic resource | Numeric result |
|---|---:|
| `stage3c_proof_matrix` | 1 |
| NW/NE/SW/SE headers | 538 / 9 / 10 / 11 |
| NW/NE/SW/SE members | 633 / 630 / 631 / 632 |
| `stage3c_empty_events` | 57 |
| `stage3c_noop_scripts` | 842 |
| `stage3c_controlled_start_script` | 3 |
| `stage3c_script_header` | 399 |
| `stage3c_proof_text` | 542 |

The generated `components/resolved-registry.json` records all symbol,
namespace, numeric, classification, access, evidence, registry hash, and target
ROM hash values and participates in clean rebuild determinism.

## Cross-reference and collision validation

The registry/compiler validates:

- global symbolic uniqueness;
- numeric ownership per physical collision domain;
- shared script-NARC ownership across local/common/header logical namespaces;
- namespace-exact symbol resolution;
- writable versus read-only provenance;
- numeric bounds, non-overlapping ranges, and evidence-bearing overrides;
- matrix dimensions/cell count/order;
- matrix cells versus declared maps;
- map cell uniqueness and matrix agreement;
- shared event/script/script-header/text dependencies;
- player-start map existence;
- existing Stage 3B map/header/member/matrix binary cross-references.

Generation stops before serialization on any resolution error.

## Failure tests

Machine-readable `RegistryError.code` values cover and tests reproduce:

| Failure | Result code |
|---|---|
| duplicate symbolic resource | `duplicate_symbol` |
| duplicate numeric ownership | `duplicate_numeric_ownership` |
| exhausted range | `allocation_exhausted` |
| unknown reference | `unknown_reference` |
| wrong namespace | `wrong_namespace` |
| reserved/vanilla/unknown writable claim | `reserved_id` / `vanilla_owned_id` / `unknown_id` |
| invalid pin, including out of range | `invalid_manual_pin` |
| deletion of referenced resource | `unknown_reference` |
| numeric ID in symbolic source | `numeric_reference` |
| dangling matrix map or wrong matrix | `dangling_map` / `wrong_matrix_reference` |
| wrong ROM/hash | `unsupported_rom_revision` |

CLI JSON failures emit `{"success": false, "errors": [...]}`.

## CLI

Added commands:

```bash
python -m tools.pokeagent registry validate [--json]
python -m tools.pokeagent registry inspect [--json]
python -m tools.pokeagent registry resolve <symbol> [--namespace NAME] [--json]
```

`inspect` writes ignored metadata to `build/registry/slot-inventory.json` and
never emits ROM member bytes.

## Revision coupling and evidence

Supported target:

- game code `IPKE`
- US HeartGold ROM SHA-256
  `65f02a56842b75aa92d775d56d657a56fe3fa993550b04dc20704ab82d760105`
- ARM9 SHA-256
  `5eeaa2dcabfb66b4ff5d151687cff2c9214de9e272ba7afdae7a01d57cf319af`

The scanner re-read the user-local ROM and verified all five pristine NARC
counts and hashes recorded in the registry. Unsupported revisions are rejected
before Stage 3C generation/installation.

Source references:

- pret/pokeheartgold `8dcf4c981ac650ae1f4f80c926b588b06293ee0e`
- DSPRE `d86737c3c94a3a698fcb2c6be2d2fdff5e880411`
- local supported ROM/NARC metadata, never tracked
- prior Stage 2/3A/3B reports and knowledge notes

Detailed source-to-policy evidence is in
`docs/knowledge/hgss-stage3c-reference-registry.md`.

## Build and runtime result

`make stage3c-registry-proof` completed from a clean build and produced
`test.nds`. A final incremental HG-Engine repack restored the Stage 3C fixture
after legacy regression runs.

Headless DeSmuME passed all 21 inherited multi-map checks. Live memory showed:

- matrix 1, dimensions 2×2;
- header grid 538/9/10/11;
- member grid 633/630/631/632;
- correct NW→NE→SE→SW→NW native transitions;
- four distinct loaded members and PER signatures;
- no warp records loaded or triggered;
- blocked external NW boundary;
- continued stability for 600 frames.

Ignored evidence:

- `build/stage3c/emulator/report.json`
- `build/stage3c/emulator/{nw-start,ne-entered,se-entered,sw-entered,nw-returned,exterior-blocked}.png`

Final proof ROM SHA-256:
`05a2a6fb7d9345d8c19ff2745cbf37cac3edfa0c1ebf4e8571cb6e12e9fcb01a`
(ignored, not tracked).

## Determinism

Two clean generation roots produced 32 compared artifacts with zero
mismatches. Key hashes:

| Artifact | SHA-256 |
|---|---|
| resolved registry | `a1488469fa8f65f949ec9ab1fe373e1cd3a4ac88aa6e8e71dcc8c10d18188412` |
| matrix | `5ec818425b6bc5c549b3ffdc9971ec0492e22d0ad978637bace5a166df42134d` |
| NW member | `a48cc48fac07cc4a12b145ee1504254900fbe360ad1f28d4ca9a5bf22f990472` |
| NE member | `1e65609936ac599f20bc27043bfe9948d24d606a20bc789eb26c77c16a7abc99` |
| SW member | `4cd29e6a90e955ae408fdb6e230b04eeb12c19b7f66fd81615c7c6496fb94b1b` |
| SE member | `5c07eee4317786b3ffc64133aef77535dcfd7fb8828eea17fa8d0fbb3d49d379` |
| generated map NARC | `c66c42f42859855e9b540191b1949370188cb477fa26a7846d121d71d132869b` |
| generated matrix NARC | `27aa8363847c4eded5ec0351104578b87c79f26f5bf23cba9701c2ecc77af0f1` |
| generated event NARC | `f975773984033c907bd69790794d7586154b45f45a8aad3b03d228c74bc7e7b3` |
| generated script NARC | `27eedf86b98acadab40bc1a1bbe2f17af26779c80b19d45871a2ab3764e85a3d` |
| generated text NARC | `a6f9c217b6be0f1a7937041ac05dba98ffb89b20fab2a9b3f025d478c5624fe2` |
| patched ARM9 | `ae3b701a3b80cea931178b451520258e89fc2cb70076077f37f10bafc5d55dff` |

The four NSBMDs and BDHC files retain the Stage 3B hashes; each PER and member
remains independently compared.

## Regression results

- Full suite: 73 tests passed; 3 opt-in integration tests skipped.
- Preflight: all command, Docker-context, Git-hygiene, Python, ROM, and system
  groups passed.
- Stage 2: clean build passed; all 11 runtime checks passed (collision,
  NPC/dialogue, reciprocal warp, stability).
- Stage 3A: clean build passed; all 14 runtime checks passed (lower/raised
  terrain, transition, height-aware boundaries, return, 600 frames).
- Stage 3B: clean build passed; all 21 runtime checks passed (four native edge
  transitions, live member identity, exterior block, 600 frames).
- Stage 3C: clean build plus final repack passed; all 21 runtime checks passed.
- Fixed physical PER offset `0x14` remains covered by permanent serializer tests.

## DeepSeek investigations

Pinned model: `deepseek-ai/DeepSeek-V4-Flash-0731`.

One useful narrow policy review supplied no repository files. It used 308 prompt
tokens and 3,007 completion tokens (3,315 total), took 57.58 seconds, and cost
an estimated `$0.00056898`. Codex independently verified four suggestions with
existing/new tests: global symbol uniqueness, collision-domain numeric
uniqueness, writable-provenance rejection, and namespace-exact resolution.

The suggestion that mirrored logical script namespaces require disjoint
classification ranges was rejected: all three describe the same physical NARC,
so ranges intentionally mirror storage provenance while resource ownership is
made exclusive by `collision_domain`.

Two non-useful attempts are recorded for completeness: one failed before API
use because an external `/tmp` source path was not an allowed worker context
(no tokens/cost), and one returned empty content after 34.95 seconds (token use
and cost unavailable). Neither influenced implementation.

## Confirmed, inferred, and unknown

Confirmed by source + tests/runtime:

- fixed map-header table and reference field widths;
- symbolic-to-numeric resolution and dependency validation;
- controlled replacement ownership and collision rejection;
- exact US ROM/archive coupling;
- deterministic generated registry and binaries;
- unchanged Stage 2/3A/3B runtime behavior.

Confirmed by source/metadata only:

- NARC member counts and pristine hashes;
- u16 structural addressability of matrix/event/script/text/member references;
- flag and variable source bounds.

Inferred conservatively:

- no appended range is safe until runtime-proven; those ranges are `UNKNOWN`.

Unknown/unsupported:

- production-safe appended NARC members;
- production-safe flag/variable blocks;
- general map-header table expansion;
- allocation policy for trainer, encounter, species, item, move, ability, and
  graphics namespaces, which Stage 3C intentionally did not implement.

## Recommendation

HeartGold remains the recommended foundation. Stage 3D may proceed because raw
LLM-managed numeric world IDs have been removed from the new authoring path and
all earlier proofs remain green. Stage 3D must continue using registry-owned
symbols and must not treat `UNKNOWN`, `VANILLA_OWNED`, or proof-controlled slots
as newly free without separate evidence.
