# HGSS Stage 4I map-model display-list capacity

## Finding

The inherited shape-6 limit of 1,068 bytes is a property of the selected retail
template layout, not the size field used by the MDL0 shape record. In the
supported map template, every shape record stores a relative u32 display-list
offset and u32 byte length. A project display list can be appended to a
lengthened model tail, the selected shape can be redirected to it, and the
result loads and renders in HeartGold.

Confidence: **confirmed for the hash-locked US HeartGold template and a
4,096-byte project ceiling by source inspection, independent parsing, generated
bytes, HG-Engine build, and DeSmuME runtime**. Larger capacities remain unknown.

## Exact bounded layout

The pristine map-member-0 NSBMD has SHA-256
`f9fbf0196f416739019288f24be604fd6c096a2ec4ebf7e820e116e7ecc329cc`
and this relevant structure:

```text
BMD0 v2                       16,604 bytes
  section offset                    20
  MDL0                        16,584 bytes
    one-model dictionary
    model base                      68 absolute
    model                     16,536 bytes
      SBC offset                   108 relative
      materials offset             192 relative
      shapes offset              2,708 relative
      inverse-bind/end offset   16,536 relative
      18 shape records
      contiguous display lists to model end
```

Each supported shape record is exactly:

```text
u16 item tag       = 0
u16 record length  = 16
u32 flags
u32 command offset (relative to this shape record)
u32 command length
```

Shape 6's record is at absolute offset 3,320. Its inherited command range is
absolute `[10,048, 11,116)`, hence 1,068 bytes. The 18 inherited command ranges
are contiguous and end exactly at the original model/container end; there is no
unused tail allocation to claim.

Evidence:

- `tools/pokeagent/world.py`, legacy hash-locked transformer;
- `tools/pokeagent/nsbmd_model.py`, independent bounded parser and relocator;
- local Apicula 0BSD source under ignored `.scratch/apicula-stage4d`, whose
  model/piece parser independently identifies the section-size, relative
  command-offset, and command-length fields;
- `pret/pokeheartgold` local source, which reaches map models through Nitro's
  model-set/model-index API instead of hardcoding these retail command offsets.
  In particular, `ReadMModelFromNarcInternal` obtains the member's dynamic
  BTAF size with `NARC_GetMemberSize`, allocates exactly that many heap bytes,
  then calls `NARC_ReadWholeMember`; the filesystem implementation derives that
  size from the member's start/end pair. The Nitro model accessor then adds the
  model dictionary's relative offset to the loaded model-set base.

## Chosen relocation algorithm

Relocation is manifest-schema-7 opt-in:

1. Compile the typed asset IR into the existing Nitro command stream.
2. Run the unchanged legacy transformer, placing a structurally valid invisible
   placeholder into the inherited target region and preserving all other
   inherited regions.
3. Align the model tail to four bytes.
4. Append the complete project command stream.
5. Rewrite only the selected shape record's relative offset and length.
6. Increase BMD0 file size, MDL0 section size, model size, and the empty
   inverse-bind/end offset by the append delta.
7. Recalculate u16 model vertex/polygon/triangle/quad counters from every
   independently parsed command allocation.
8. Reopen and validate the finished model.

The proof needs no additional alignment padding because the original model and
3,820-byte payload are already four-byte aligned. The resulting target range
is `[16,604, 20,424)`. All 17 non-target ranges retain their original offsets,
lengths, and payload hashes.

## Parser invariants

The bounded independent parser rejects:

- a non-BMD0-v2 or multi-section container;
- inconsistent BMD0, MDL0, or model sizes;
- an unsupported model/shape dictionary;
- shape records outside the model;
- empty, misaligned, overlapping, metadata-overlapping, or out-of-bounds
  command ranges;
- truncated or unsupported commands in the project command subset;
- unterminated/incomplete primitive blocks;
- counters inconsistent with parsed primitives.

This is deliberately not a general NSBMD writer or validator. It supports one
MDL0, one model, one node, the existing dictionaries/materials/shapes, no
inverse binds, and the command subset already emitted by the project.

## Capacity classifications

```text
FORMAT_CAPACITY = u32 relative offset and u32 byte length fields
TESTED_PROJECT_CAPACITY = 4,096 bytes per relocated display list
UNKNOWN_HARDWARE_LIMIT = unmeasured beyond the 4 KiB bounded runtime proof
```

The compiler enforces 4,096 bytes even though the on-disk fields can encode
more. This ceiling is based on the bounded runtime proof, not a claim about DS
VRAM, Nitro command processing, aggregate map-model size, or multiple large
shapes.

Stress allocations at 1,032, 2,052, 3,072, and 3,820 bytes exercise roughly
25%, 50%, 75%, and 93% of the project ceiling. Every layout reopens cleanly;
the 3,820-byte canonical asset is the runtime-tested near-upper-bound case.

## Backward compatibility

Assets without `geometry_storage.policy = project_relocated_display_list`
continue through the old transformer. They retain the inherited capacity check
and output bytes. Stage 4I does not relocate all shapes and does not change
texture, material, collision, PER, BDHC, BGS, or NARC ordering.

The Stage 4H TripoSR candidate remains rejected. Its conditional 453,164-byte
projection is more than 110 times the Stage 4I tested capacity, and it still
lacks the required hierarchy, material, normal, and UV contract.

## Reproduction

```bash
python -m unittest tests.test_pokeagent_stage4i_model_capacity -v
python -m tools.pokeagent map generate \
  --fixture fixtures/stage4i_expanded_geometry_world.json \
  --output build/stage4i/generated --json
make stage4i-model-capacity-proof
python -m tools.pokeagent qa run \
  qa/scenarios/stage4i_expanded_geometry.json --json
```

Inspect `build/stage4i/generated/components/model-layout-report.json` for the
complete before/after shape table and payload hashes.

## Confirmed, inferred, unknown

### Confirmed

- The exact bounded record/offset/length/section semantics above.
- The original 1,068-byte region is fully allocated template storage.
- A 3,820-byte project list can be appended and selected by shape 6.
- Container/model lengths and model counters can be updated consistently.
- All non-target shape offsets, lengths, and payload bytes remain unchanged.
- The rebuilt model survives map-member/NARC/ROM assembly and runtime rendering
  under the declared 4 KiB ceiling.

### Inferred

- Other shapes using the same record form should be relocatable under the same
  constraints, but the runtime proof targets shape 6 only.
- A bounded deterministic rebuild of several project lists should work, but
  aggregate runtime budgeting needs its own evidence.

### Unknown

- The practical hardware/render-time limit beyond 4 KiB.
- Safe aggregate capacity across several relocated shapes or several visible
  large map models.
- Models with multiple model entries, inverse binds, skeletal data, arbitrary
  dictionaries, or relocated material/texture state.
