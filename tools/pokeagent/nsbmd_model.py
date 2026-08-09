"""Bounded NSBMD/MDL0 shape inspection and project display-list relocation.

This is intentionally not a general NSBMD writer.  It accepts the single-model,
single-MDL0, no-inverse-bind layout of the hash-locked HGSS map template and can
append one or more already-encoded project display lists to the model tail.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any


PROJECT_DISPLAY_LIST_TESTED_MAX = 4096
_GX_PARAM_WORDS = {0x21: 1, 0x22: 1, 0x23: 2, 0x40: 1, 0x41: 0}


class ModelLayoutError(ValueError):
    """The bounded map-model layout or relocation request is invalid."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dict_offsets(data: bytes, base: int) -> tuple[list[int], bytes]:
    if base < 0 or base + 8 > len(data):
        raise ModelLayoutError("malformed_shape_dictionary", "Nitro dictionary header is truncated")
    revision, count, size, _padding, entry_offset = struct.unpack_from("<BBHHH", data, base)
    if revision not in (0, 1) or count == 0 or size < 8 or base + size > len(data):
        raise ModelLayoutError("malformed_shape_dictionary", "Nitro dictionary header is unsupported")
    values_base = base + entry_offset + 4
    if values_base < base or values_base + count * 4 > base + size:
        raise ModelLayoutError("malformed_shape_dictionary", "Nitro dictionary entries exceed its size")
    offsets = [struct.unpack_from("<I", data, values_base + index * 4)[0] for index in range(count)]
    return offsets, data[base:base + size]


def _inspect_canonical_display_list(data: bytes) -> dict[str, Any]:
    """Parse the exact command-word subset emitted by the project encoder."""
    if not data or len(data) % 4:
        raise ModelLayoutError("target_display_list_truncation", "display-list allocation is empty or misaligned")
    offset = 0
    active: int | None = None
    vertices = 0
    triangles = 0
    quads = 0
    blocks: list[dict[str, int | str]] = []
    block_start = 0
    while offset < len(data):
        if data[offset:offset + 4] == b"\0\0\0\0":
            if any(data[offset:]):
                raise ModelLayoutError("target_display_list_truncation", "nonzero data follows display-list padding")
            break
        if offset + 4 > len(data) or any(data[offset + index] for index in (1, 2, 3)):
            raise ModelLayoutError("target_display_list_truncation", "display list does not use canonical command words")
        opcode = data[offset]
        if opcode not in _GX_PARAM_WORDS:
            raise ModelLayoutError("target_display_list_truncation", f"unsupported canonical opcode {opcode:#x}")
        command_bytes = 4 + _GX_PARAM_WORDS[opcode] * 4
        if offset + command_bytes > len(data):
            raise ModelLayoutError("target_display_list_truncation", "display-list command parameters are truncated")
        if opcode == 0x40:
            if active is not None:
                raise ModelLayoutError("target_display_list_truncation", "nested BEGIN command")
            mode = struct.unpack_from("<I", data, offset + 4)[0]
            if mode not in (0, 1):
                raise ModelLayoutError("target_display_list_truncation", "only TRIANGLES and QUADS are supported")
            active = mode
            vertices = 0
            block_start = offset
        elif opcode == 0x41:
            if active is None:
                raise ModelLayoutError("target_display_list_truncation", "END appears outside a primitive block")
            arity = 3 if active == 0 else 4
            if vertices == 0 or vertices % arity:
                raise ModelLayoutError("target_display_list_truncation", "primitive block has incomplete vertices")
            primitive_count = vertices // arity
            if active == 0:
                triangles += primitive_count
            else:
                quads += primitive_count
            blocks.append({
                "primitive": "triangle" if active == 0 else "quad",
                "count": primitive_count,
                "vertices": vertices,
                "bytes": offset + command_bytes - block_start,
            })
            active = None
        elif opcode == 0x23:
            if active is None:
                raise ModelLayoutError("target_display_list_truncation", "vertex command appears outside BEGIN/END")
            vertices += 1
        elif active is None:
            raise ModelLayoutError("target_display_list_truncation", "vertex-state command appears outside BEGIN/END")
        offset += command_bytes
    if active is not None or not blocks:
        raise ModelLayoutError("target_display_list_truncation", "display list is unterminated or empty")
    return {
        "command_bytes": offset,
        "allocated_bytes": len(data),
        "triangle_count": triangles,
        "quad_count": quads,
        "vertex_count": triangles * 3 + quads * 4,
        "polygon_count": triangles + quads,
        "primitive_blocks": blocks,
        "sha256": _hash(data[:offset]),
        "allocation_sha256": _hash(data),
    }


def inspect_nsbmd_model(data: bytes, *, validate_commands: bool = True) -> dict[str, Any]:
    """Independently reopen the exact generated map-model subset."""
    if len(data) < 20 or data[:4] != b"BMD0":
        raise ModelLayoutError("unsupported_model_revision", "model is not a BMD0 container")
    byte_order, version, file_size, header_size, section_count = struct.unpack_from("<HHIHH", data, 4)
    if (byte_order, version, file_size, header_size, section_count) != (0xFEFF, 2, len(data), 16, 1):
        raise ModelLayoutError("container_size_mismatch", "Stage 4I requires one exact BMD0 v2 section")
    mdl_base = struct.unpack_from("<I", data, header_size)[0]
    if mdl_base != 20 or mdl_base + 8 > len(data) or data[mdl_base:mdl_base + 4] != b"MDL0":
        raise ModelLayoutError("unsupported_model_revision", "BMD0 does not contain the bounded MDL0 section")
    mdl_size = struct.unpack_from("<I", data, mdl_base + 4)[0]
    if mdl_base + mdl_size != len(data):
        raise ModelLayoutError("container_size_mismatch", "MDL0 section size does not reach the BMD0 end")
    model_offsets, model_dictionary = _dict_offsets(data, mdl_base + 8)
    if len(model_offsets) != 1:
        raise ModelLayoutError("unsupported_model_revision", "Stage 4I requires one model")
    model_base = mdl_base + model_offsets[0]
    if model_base + 68 > len(data):
        raise ModelLayoutError("section_size_overflow", "model header is truncated")
    model_size, ofs_sbc, ofs_mat, ofs_shape, ofs_evp = struct.unpack_from("<5I", data, model_base)
    if model_base + model_size != len(data) or ofs_evp != model_size:
        raise ModelLayoutError("section_size_overflow", "bounded model must end at its empty inverse-bind offset")
    if not 68 <= ofs_sbc < ofs_mat < ofs_shape < ofs_evp:
        raise ModelLayoutError("relocation_into_protected_metadata", "model substructure offsets are inconsistent")
    num_nodes, num_materials, num_shapes = struct.unpack_from("<xxxBBB", data, model_base + 20)
    if num_nodes != 1 or num_shapes < 1:
        raise ModelLayoutError("unsupported_model_revision", "bounded model requires one node and at least one shape")
    counters = struct.unpack_from("<4H", data, model_base + 36)
    shape_set = model_base + ofs_shape
    shape_offsets, shape_dictionary = _dict_offsets(data, shape_set)
    if len(shape_offsets) != num_shapes:
        raise ModelLayoutError("malformed_shape_dictionary", "shape dictionary count disagrees with model info")
    shapes: list[dict[str, Any]] = []
    ranges: list[tuple[int, int, int]] = []
    metadata_end = len(data)
    for index, relative in enumerate(shape_offsets):
        shape_base = shape_set + relative
        if shape_base < shape_set or shape_base + 16 > model_base + model_size:
            raise ModelLayoutError("invalid_shape_offset", f"shape {index} record is outside the model")
        item_tag, header_len, flags, display_offset, display_size = struct.unpack_from("<HHIII", data, shape_base)
        if item_tag != 0 or header_len != 16 or flags & ~0xF:
            raise ModelLayoutError("invalid_shape_offset", f"shape {index} record is unsupported")
        start = shape_base + display_offset
        end = start + display_size
        if display_size == 0 or start % 4 or display_size % 4:
            raise ModelLayoutError("misaligned_display_list", f"shape {index} display list is empty or misaligned")
        if start < shape_base + 16:
            raise ModelLayoutError("relocation_into_protected_metadata", f"shape {index} points into protected metadata")
        if end > model_base + model_size or end < start:
            raise ModelLayoutError("display_list_range_outside_section", f"shape {index} display list leaves the model")
        metadata_end = min(metadata_end, start)
        payload = data[start:end]
        shapes.append({
            "shape": index,
            "record_offset": shape_base,
            "display_offset_relative": display_offset,
            "display_offset": start,
            "display_length": display_size,
            "payload_sha256": _hash(payload),
            "commands": None,
        })
        ranges.append((start, end, index))
    for shape in shapes:
        if shape["record_offset"] + 16 > metadata_end:
            raise ModelLayoutError("relocation_into_protected_metadata", "shape records overlap display-list storage")
    ordered = sorted(ranges)
    for (start, end, index), (next_start, _next_end, next_index) in zip(ordered, ordered[1:]):
        if next_start < end:
            raise ModelLayoutError(
                "overlapping_display_list_ranges",
                f"shape {index} overlaps shape {next_index}",
            )
    if validate_commands:
        for shape in shapes:
            start = int(shape["display_offset"])
            end = start + int(shape["display_length"])
            shape["commands"] = _inspect_canonical_display_list(data[start:end])
        observed = (
            sum(int(shape["commands"]["vertex_count"]) for shape in shapes),
            sum(int(shape["commands"]["polygon_count"]) for shape in shapes),
            sum(int(shape["commands"]["triangle_count"]) for shape in shapes),
            sum(int(shape["commands"]["quad_count"]) for shape in shapes),
        )
        if observed != counters:
            raise ModelLayoutError(
                "invalid_model_counters", "model counters disagree with independently parsed display lists",
                expected=list(counters), observed=list(observed),
            )
    return {
        "file_size": len(data),
        "mdl_base": mdl_base,
        "mdl_size": mdl_size,
        "model_base": model_base,
        "model_size": model_size,
        "model_offsets": {"sbc": ofs_sbc, "materials": ofs_mat, "shapes": ofs_shape, "inverse_binds": ofs_evp},
        "counts": {
            "nodes": num_nodes, "materials": num_materials, "shapes": num_shapes,
            "vertices": counters[0], "polygons": counters[1], "triangles": counters[2], "quads": counters[3],
        },
        "model_dictionary_sha256": _hash(model_dictionary),
        "shape_dictionary_sha256": _hash(shape_dictionary),
        "metadata_end": metadata_end,
        "shapes": shapes,
    }


def relocate_display_lists(
    data: bytes,
    replacements: dict[int, bytes],
    *,
    configured_capacity: int,
) -> tuple[bytes, dict[str, Any]]:
    """Append selected display lists and redirect only their shape records."""
    if (
        isinstance(configured_capacity, bool)
        or not isinstance(configured_capacity, int)
        or configured_capacity <= 0
        or configured_capacity > PROJECT_DISPLAY_LIST_TESTED_MAX
    ):
        raise ModelLayoutError(
            "invalid_project_geometry_capacity",
            f"configured capacity must be in 1..{PROJECT_DISPLAY_LIST_TESTED_MAX}",
        )
    if not replacements:
        raise ModelLayoutError("invalid_relocation_request", "at least one shape must be relocated")
    before = inspect_nsbmd_model(data, validate_commands=False)
    for shape in before["shapes"]:
        start = int(shape["display_offset"])
        end = start + int(shape["display_length"])
        shape["commands"] = _inspect_canonical_display_list(data[start:end])
    if any(not isinstance(shape, int) or not 0 <= shape < len(before["shapes"]) for shape in replacements):
        raise ModelLayoutError("invalid_shape_offset", "relocation names an unavailable shape")
    for shape, payload in sorted(replacements.items()):
        if not isinstance(payload, bytes) or not payload or len(payload) % 4:
            raise ModelLayoutError("misaligned_display_list", f"shape {shape} replacement is empty or misaligned")
        if len(payload) > configured_capacity:
            raise ModelLayoutError(
                "project_geometry_capacity_exceeded",
                f"shape {shape} needs {len(payload)} bytes but project capacity is {configured_capacity}",
                shape=shape, required_bytes=len(payload), configured_capacity=configured_capacity,
            )
        _inspect_canonical_display_list(payload)
    output = bytearray(data)
    layout: list[dict[str, Any]] = []
    for shape, payload in sorted(replacements.items()):
        padding = (-len(output)) % 4
        if padding:
            output.extend(bytes(padding))
        start = len(output)
        output.extend(payload)
        record = before["shapes"][shape]
        relative = start - int(record["record_offset"])
        if not 0 <= relative <= 0xFFFFFFFF:
            raise ModelLayoutError("section_size_overflow", "relative display-list offset exceeds u32")
        struct.pack_into("<II", output, int(record["record_offset"]) + 8, relative, len(payload))
        layout.append({
            "shape": shape,
            "old_offset": record["display_offset"],
            "old_length": record["display_length"],
            "old_payload_sha256": record["payload_sha256"],
            "new_offset": start,
            "new_length": len(payload),
            "new_payload_sha256": _hash(payload),
            "alignment_padding": padding,
        })
    delta = len(output) - len(data)
    new_model_size = int(before["model_size"]) + delta
    new_mdl_size = int(before["mdl_size"]) + delta
    if max(len(output), new_model_size, new_mdl_size) > 0xFFFFFFFF:
        raise ModelLayoutError("section_size_overflow", "relocated container exceeds u32 section fields")
    struct.pack_into("<I", output, 8, len(output))
    struct.pack_into("<I", output, int(before["mdl_base"]) + 4, new_mdl_size)
    struct.pack_into("<I", output, int(before["model_base"]), new_model_size)
    struct.pack_into("<I", output, int(before["model_base"]) + 16, new_model_size)
    provisional = bytes(output)
    provisional_layout = inspect_nsbmd_model(provisional, validate_commands=False)
    command_reports = []
    for shape in provisional_layout["shapes"]:
        start = int(shape["display_offset"])
        end = start + int(shape["display_length"])
        command_reports.append(_inspect_canonical_display_list(provisional[start:end]))
    counters = (
        sum(int(command["vertex_count"]) for command in command_reports),
        sum(int(command["polygon_count"]) for command in command_reports),
        sum(int(command["triangle_count"]) for command in command_reports),
        sum(int(command["quad_count"]) for command in command_reports),
    )
    if any(value > 0xFFFF for value in counters):
        raise ModelLayoutError("invalid_model_counters", "relocated primitive counters exceed u16")
    struct.pack_into("<4H", output, int(before["model_base"]) + 36, *counters)
    rebuilt = bytes(output)
    after = inspect_nsbmd_model(rebuilt, validate_commands=True)
    relocated = set(replacements)
    unaffected = []
    for old, new in zip(before["shapes"], after["shapes"], strict=True):
        if int(old["shape"]) in relocated:
            continue
        if (
            old["display_offset"] != new["display_offset"]
            or old["display_length"] != new["display_length"]
            or old["payload_sha256"] != new["payload_sha256"]
        ):
            raise ModelLayoutError("unaffected_payload_mutation", f"shape {old['shape']} changed during relocation")
        unaffected.append({
            "shape": old["shape"], "offset": old["display_offset"],
            "length": old["display_length"], "payload_sha256": old["payload_sha256"],
        })
    if before["shape_dictionary_sha256"] != after["shape_dictionary_sha256"]:
        raise ModelLayoutError("malformed_shape_dictionary", "shape dictionary changed during relocation")
    return rebuilt, {
        "schema_version": 1,
        "strategy": "append_model_tail_and_redirect_shape_record",
        "configured_capacity_bytes": configured_capacity,
        "tested_project_capacity_bytes": PROJECT_DISPLAY_LIST_TESTED_MAX,
        "old_file_size": len(data), "new_file_size": len(rebuilt), "file_size_delta": delta,
        "old_mdl_size": before["mdl_size"], "new_mdl_size": after["mdl_size"],
        "old_model_size": before["model_size"], "new_model_size": after["model_size"],
        "shape_dictionary_sha256": after["shape_dictionary_sha256"],
        "relocations": layout,
        "unaffected_shapes": unaffected,
        "unaffected_payloads_preserved": True,
        "model_counters": after["counts"],
        "output_sha256": _hash(rebuilt),
        "validation": after,
    }
