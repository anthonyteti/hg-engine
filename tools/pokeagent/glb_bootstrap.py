"""Atomic Stage 4P hard-surface attribute bootstrap transaction."""

from __future__ import annotations

import hashlib
import json
import struct
from typing import Any

from .glb import GLBError, _chunks, pack_glb, parse_glb
from .glb_geometry_reduce import (
    GEOMETRY_LIMITS,
    GeometryGLBError,
    pack_geometry_glb,
    parse_geometry_glb,
)
from .glb_materials import MaterialSynthesisError, validate_source_material_name
from .glb_normals import NormalGenerationError, generate_missing_normals
from .glb_uvs import UVGenerationError, generate_planar_uvs_from_geometry


BOOTSTRAP_LIMITS = {
    "max_source_bytes": 262_144,
    "max_buffer_bytes": 262_144,
    "max_nodes": 1,
    "max_meshes": 1,
    "max_primitives": 1,
    "max_accessors": 4,
    "max_buffer_views": 4,
    "max_positions": 256,
    "max_faces": 80,
    "max_indices": 240,
}
BOOTSTRAP_POLICY = "hard_surface_static_v1"
COLOR0_REJECT = "reject"
COLOR0_DISCARD = "explicit_discard"
_COLOR_COMPONENT_BYTES = {5121: 1, 5123: 2}
_COLOR_COMPONENTS = {"VEC3": 3, "VEC4": 4}


class BootstrapError(ValueError):
    """The atomic transaction cannot produce the strict Stage 4F contract."""

    def __init__(self, code: str, message: str, *, phase: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.phase = phase
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "phase": self.phase, "details": self.details}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _color0_payload(document: dict[str, Any], binary: bytes, *, maximum: int) -> dict[str, object]:
    primitive = document["meshes"][0]["primitives"][0]
    accessor_index = primitive["attributes"]["COLOR_0"]
    accessors = document.get("accessors"); views = document.get("bufferViews")
    if (
        isinstance(accessor_index, bool) or not isinstance(accessor_index, int)
        or not isinstance(accessors, list) or not 0 <= accessor_index < len(accessors)
        or not isinstance(views, list) or not isinstance(accessors[accessor_index], dict)
    ):
        raise BootstrapError("bootstrap_color0_invalid", "COLOR_0 accessor is invalid", phase="source")
    accessor = accessors[accessor_index]
    component = accessor.get("componentType"); kind = accessor.get("type"); count = accessor.get("count")
    if (
        component not in _COLOR_COMPONENT_BYTES or kind not in _COLOR_COMPONENTS
        or accessor.get("normalized") is not True
        or isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= maximum
        or "sparse" in accessor
    ):
        raise BootstrapError(
            "bootstrap_color0_invalid",
            "discardable COLOR_0 must be bounded normalized unsigned VEC3/VEC4 data",
            phase="source",
        )
    view_index = accessor.get("bufferView")
    if isinstance(view_index, bool) or not isinstance(view_index, int) or not 0 <= view_index < len(views):
        raise BootstrapError("bootstrap_color0_invalid", "COLOR_0 bufferView is invalid", phase="source")
    view = views[view_index]
    element = _COLOR_COMPONENT_BYTES[component] * _COLOR_COMPONENTS[kind]
    stride = view.get("byteStride", element) if isinstance(view, dict) else None
    view_offset = view.get("byteOffset", 0) if isinstance(view, dict) else None
    view_length = view.get("byteLength") if isinstance(view, dict) else None
    accessor_offset = accessor.get("byteOffset", 0)
    values = (stride, view_offset, view_length, accessor_offset)
    if (
        not isinstance(view, dict) or view.get("buffer") != 0
        or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values)
        or stride < element or stride > 252
        or accessor_offset + (count - 1) * stride + element > view_length
        or view_offset + view_length > len(binary)
    ):
        raise BootstrapError("bootstrap_color0_invalid", "COLOR_0 payload exceeds embedded BIN", phase="source")
    payload = b"".join(
        binary[view_offset + accessor_offset + row * stride:view_offset + accessor_offset + row * stride + element]
        for row in range(count)
    )
    return {
        "accessor": accessor_index,
        "count": count,
        "component_type": component,
        "type": kind,
        "normalized": True,
        "payload_bytes": len(payload),
        "payload_sha256": _sha256(payload),
    }


def _source_geometry(data: bytes, color0_policy: str) -> dict[str, Any]:
    if color0_policy not in {COLOR0_REJECT, COLOR0_DISCARD}:
        raise BootstrapError("invalid_bootstrap_color0_policy", "COLOR_0 policy is invalid", phase="source")
    if len(data) > BOOTSTRAP_LIMITS["max_source_bytes"]:
        raise BootstrapError(
            "bootstrap_source_budget",
            "source exceeds the bounded Stage 4P byte envelope",
            phase="source",
            source_bytes=len(data),
            maximum_bytes=BOOTSTRAP_LIMITS["max_source_bytes"],
        )
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
    except GLBError as error:
        raise BootstrapError("bootstrap_source_failed", str(error), phase="source", source_code=error.code) from error
    nodes = document.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 1:
        raise BootstrapError("bootstrap_source_failed", "Stage 4P requires one identity mesh node", phase="source")
    accessors = document.get("accessors", [])
    views = document.get("bufferViews", [])
    if (
        len(binary) > BOOTSTRAP_LIMITS["max_buffer_bytes"]
        or not isinstance(accessors, list) or len(accessors) > BOOTSTRAP_LIMITS["max_accessors"]
        or not isinstance(views, list) or len(views) > BOOTSTRAP_LIMITS["max_buffer_views"]
    ):
        raise BootstrapError(
            "bootstrap_source_budget",
            "source container exceeds the bounded Stage 4P accessor/buffer envelope",
            phase="source",
            buffer_bytes=len(binary),
            accessor_count=len(accessors) if isinstance(accessors, list) else None,
            buffer_view_count=len(views) if isinstance(views, list) else None,
        )
    primitive = (
        document.get("meshes", [{}])[0].get("primitives", [{}])[0]
        if isinstance(document.get("meshes"), list) and document.get("meshes") else {}
    )
    materials = document.get("materials", [])
    if materials or (isinstance(primitive, dict) and "material" in primitive):
        raise BootstrapError(
            "bootstrap_material_already_present",
            "missing-all bootstrap source already contains a source material",
            phase="source",
        )
    attributes = primitive.get("attributes") if isinstance(primitive, dict) else None
    present = sorted(set(attributes or {}) - {"POSITION"}) if isinstance(attributes, dict) else []
    for forbidden, code in (("NORMAL", "bootstrap_normal_already_present"), ("TEXCOORD_0", "bootstrap_uv_already_present")):
        if forbidden in present:
            raise BootstrapError(code, f"missing-all bootstrap source already contains {forbidden}", phase="source")
    unexpected = sorted(set(present) - {"COLOR_0"})
    if unexpected:
        raise BootstrapError(
            "bootstrap_unsupported_aux_attribute",
            "bootstrap source contains an unsupported auxiliary attribute",
            phase="source", attributes=unexpected,
        )
    color_evidence = None
    if "COLOR_0" in present:
        color_evidence = _color0_payload(document, binary, maximum=BOOTSTRAP_LIMITS["max_positions"])
        if color0_policy != COLOR0_DISCARD:
            raise BootstrapError(
                "bootstrap_color0_policy_required",
                "COLOR_0 requires explicit opt-in discard",
                phase="source", color0=color_evidence,
            )
    elif color0_policy == COLOR0_DISCARD:
        raise BootstrapError(
            "bootstrap_color0_absent",
            "explicit COLOR_0 discard was requested but the source has no COLOR_0",
            phase="source",
        )
    try:
        parsed = parse_geometry_glb(data, allow_auxiliary=bool(color_evidence))
    except GeometryGLBError as error:
        raise BootstrapError("bootstrap_source_failed", str(error), phase="source", source_code=error.code, **error.details) from error
    topology = parsed["topology"]
    if (
        topology["positions"] > BOOTSTRAP_LIMITS["max_positions"]
        or topology["triangles"] > BOOTSTRAP_LIMITS["max_faces"]
        or topology["triangles"] * 3 > BOOTSTRAP_LIMITS["max_indices"]
    ):
        raise BootstrapError("bootstrap_source_budget", "source exceeds the bounded Stage 4P envelope", phase="source")
    if topology["connected_components"] != 1:
        raise BootstrapError("bootstrap_source_component_count", "Stage 4P requires one connected component", phase="source")
    return {**parsed, "color0": color_evidence, "source_document": document}


def pack_uv_material_without_normals(
    vertices: list[tuple[tuple[float, float, float], tuple[float, float]]],
    triangles: list[tuple[int, int, int]],
    material: str,
) -> bytes:
    positions = [vertex[0] for vertex in vertices]; uvs = [vertex[1] for vertex in vertices]
    indices = [index for triangle in triangles for index in triangle]
    binary = bytearray(); views: list[dict[str, int]] = []; accessors: list[dict[str, object]] = []

    def append(values: list[Any], fmt: str, kind: str, component: int, bounds: bool = False) -> int:
        while len(binary) % 4: binary.append(0)
        offset = len(binary)
        for value in values: binary.extend(struct.pack(fmt, *value) if isinstance(value, tuple) else struct.pack(fmt, value))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(binary) - offset})
        accessor: dict[str, object] = {"bufferView": len(views) - 1, "componentType": component, "count": len(values), "type": kind}
        if bounds:
            packed = [struct.unpack("<3f", struct.pack("<3f", *value)) for value in values]
            accessor["min"] = [min(value[axis] for value in packed) for axis in range(3)]
            accessor["max"] = [max(value[axis] for value in packed) for axis in range(3)]
        accessors.append(accessor); return len(accessors) - 1

    p = append(positions, "<3f", "VEC3", 5126, True)
    uv = append(uvs, "<2f", "VEC2", 5126)
    component, fmt = (5121, "<B") if len(vertices) <= 256 else (5123, "<H")
    ix = append(indices, fmt, "SCALAR", component)
    document = {
        "asset": {"generator": "pokeagent-stage4p-uv-intermediate-v1", "version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "bootstrap_uv_mesh"}],
        "meshes": [{"name": "bootstrap_uv_mesh", "primitives": [{
            "attributes": {"POSITION": p, "TEXCOORD_0": uv}, "indices": ix, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": material}], "accessors": accessors,
        "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    return pack_glb(document, bytes(binary))


def discard_color0_to_geometry(data: bytes) -> dict[str, Any]:
    """Explicitly discard only COLOR_0 and emit canonical geometry-only GLB."""
    parsed = _source_geometry(data, COLOR0_DISCARD)
    canonical = pack_geometry_glb(parsed["geometry"])
    reopened = parse_geometry_glb(canonical)
    report = {
        "schema_version": 1,
        "success": True,
        "policy": "explicit_discard_non_runtime_color0",
        "source_sha256": _sha256(data),
        "canonical_sha256": _sha256(canonical),
        "color0": parsed["color0"],
        "source_topology": parsed["topology"],
        "canonical_topology": reopened["topology"],
        "position_index_semantics_preserved": parsed["geometry"] == reopened["geometry"],
        "removed_attributes": ["COLOR_0"],
        "generated_attributes": [],
    }
    semantic = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = _sha256(semantic)
    return {"canonical_glb": canonical, "geometry": reopened["geometry"], "report": report}


def bootstrap_geometry_glb(data: bytes, policy: dict[str, Any]) -> dict[str, Any]:
    """Atomically bootstrap material, planar UV0, then UV-aware normals."""
    if not isinstance(policy, dict) or policy.get("policy") != BOOTSTRAP_POLICY:
        raise BootstrapError("invalid_bootstrap_policy", "Stage 4P policy is incomplete", phase="policy")
    try:
        material = validate_source_material_name(policy.get("material_name"))
    except MaterialSynthesisError as error:
        raise BootstrapError("bootstrap_material_failed", str(error), phase="material", source_code=error.code) from error
    source = _source_geometry(data, policy.get("color0_policy"))
    geometry = source["geometry"]
    try:
        uv = generate_planar_uvs_from_geometry(
            geometry["positions"], geometry["faces"], material,
            patch_normal_degrees=policy.get("patch_normal_degrees"),
            plane_epsilon=policy.get("plane_epsilon"),
            texture_size=policy.get("texture_size"),
            padding_texels=policy.get("padding_texels"),
        )
    except UVGenerationError as error:
        raise BootstrapError("bootstrap_uv_failed", str(error), phase="uv", source_code=error.code, **error.details) from error
    uv_intermediate = pack_uv_material_without_normals(uv["vertices"], uv["triangles"], material)
    try:
        normals = generate_missing_normals(
            uv_intermediate,
            crease_angle_degrees=policy.get("crease_angle_degrees"),
            weighting=policy.get("normal_weighting"),
        )
    except NormalGenerationError as error:
        raise BootstrapError("bootstrap_normal_failed", str(error), phase="normal", source_code=error.code, **error.details) from error
    canonical = normals["canonical_glb"]
    try:
        accepted = parse_glb(canonical)
    except GLBError as error:
        raise BootstrapError("bootstrap_stage4f_rejected", str(error), phase="stage4f", source_code=error.code) from error
    report = {
        "schema_version": 1,
        "success": True,
        "policy": BOOTSTRAP_POLICY,
        "atomic": True,
        "operation_order": ["validate_geometry", "assign_material", "generate_uv0", "generate_final_normals", "stage4f_validate"],
        "limits": dict(BOOTSTRAP_LIMITS),
        "source_sha256": _sha256(data),
        "uv_intermediate_sha256": _sha256(uv_intermediate),
        "canonical_sha256": _sha256(canonical),
        "source_size_bytes": len(data),
        "canonical_size_bytes": len(canonical),
        "source_topology": source["topology"],
        "color0": {"policy": policy["color0_policy"], "discarded": source["color0"] is not None, "evidence": source["color0"]},
        "material": {"name": material, "count": 1, "index": 0, "provenance": "stage4p_via_stage4n_policy"},
        "uv": {**uv["metrics"], "provenance": "stage4p_via_stage4m_planar_patch_policy"},
        "normals": {**normals["report"], "provenance": "stage4p_via_stage4l_crease_aware_policy"},
        "final_counts": {
            "attribute_vertices": normals["report"]["canonical_attribute_vertices"],
            "unique_positions": len(accepted.vertices), "uvs": len(accepted.uvs),
            "normals": len(accepted.normals), "faces": len(accepted.faces),
        },
        "stage4f_accepted": True,
    }
    semantic = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = _sha256(semantic)
    return {"canonical_glb": canonical, "canonical_mesh": accepted, "uv_intermediate_glb": uv_intermediate, "report": report}


def inspect_color0_discard_applicability(data: bytes) -> dict[str, Any]:
    """Read-only COLOR_0/geometry projection; never emits a derived candidate."""
    raw_hash = _sha256(data)
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
        auxiliary = parsed["auxiliary_attributes"]
        color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"]) if auxiliary == ["COLOR_0"] else None
    except (GLBError, GeometryGLBError, BootstrapError) as error:
        return {
            "color0_policy_match": False, "post_discard_stage4o_applicable": False,
            "raw_source_sha256": raw_hash, "raw_source_unchanged": True,
            "error": {"code": error.code, "message": str(error), "details": getattr(error, "details", {})},
        }
    quality = parsed["topology"]
    topology_ok = bool(quality["valid_for_predecimation"]) and quality["connected_components"] == 1
    return {
        "color0_policy_match": color is not None,
        "color0": color,
        "auxiliary_attributes": auxiliary,
        "post_discard_stage4o_applicable": color is not None and topology_ok,
        "topology": quality,
        "raw_source_sha256": raw_hash,
        "raw_source_unchanged": True,
        "derived_candidate_created": False,
        "error": None if topology_ok else {
            "code": "bootstrap_topology_still_blocked",
            "message": "COLOR_0 policy does not repair source topology",
        },
    }
