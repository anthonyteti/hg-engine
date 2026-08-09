"""Bounded missing-only source-material identity synthesis for Stage 4N."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from .glb import GLBError, _chunks, pack_glb, parse_glb
from .glb_preprocess import GLBPreprocessError, _hierarchy


MATERIAL_LIMITS = {
    "max_source_bytes": 262_144,
    "max_nodes": 4,
    "max_meshes": 1,
    "max_primitives": 1,
    "max_materials": 1,
    "max_accessors": 16,
    "max_buffer_views": 16,
    "max_accessor_elements": 256,
    "max_buffer_bytes": 262_144,
}
MATERIAL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_COMPONENT_BYTES = {5121: 1, 5123: 2, 5125: 4, 5126: 4}
_TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}


class MaterialSynthesisError(ValueError):
    """A GLB cannot receive one bounded missing source-material identity."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_name(name: object) -> str:
    if not isinstance(name, str) or not name:
        raise MaterialSynthesisError("invalid_material_name", "source material name must be non-empty")
    try:
        name.encode("ascii")
    except UnicodeEncodeError as error:
        raise MaterialSynthesisError("invalid_material_name", "source material name must be ASCII") from error
    if not MATERIAL_NAME.fullmatch(name):
        raise MaterialSynthesisError(
            "invalid_material_name",
            "source material name must be 1..64 lower-snake-case ASCII characters",
            name=name,
        )
    return name


def validate_source_material_name(name: object) -> str:
    """Validate the shared bounded source-material identity policy."""
    return _validate_name(name)


def _source_document(data: bytes) -> tuple[dict[str, Any], bytes, list[int]]:
    try:
        document, binary = _chunks(data, MATERIAL_LIMITS)
    except GLBError as error:
        raise MaterialSynthesisError(error.code, str(error), **error.details) from error
    asset = document.get("asset")
    if not isinstance(asset, dict) or asset.get("version") != "2.0" or asset.get("minVersion") not in (None, "2.0"):
        raise MaterialSynthesisError("invalid_gltf_version", "material synthesis requires glTF 2.0")
    if document.get("extensionsUsed") or document.get("extensionsRequired"):
        raise MaterialSynthesisError("unsupported_gltf_extension", "material synthesis accepts no glTF extensions")
    for key, code in (("animations", "unsupported_animation"), ("skins", "unsupported_skin")):
        if document.get(key):
            raise MaterialSynthesisError(code, f"material synthesis rejects {key}")
    if any(document.get(key) for key in ("images", "textures", "samplers")):
        raise MaterialSynthesisError("embedded_texture", "material synthesis does not process texture resources")
    materials = document.get("materials", [])
    if not isinstance(materials, list):
        raise MaterialSynthesisError("invalid_material_table", "GLB materials must be absent or an array")
    if materials:
        raise MaterialSynthesisError("material_already_present", "missing-only policy never replaces an authored material")
    meshes = document.get("meshes")
    if not isinstance(meshes, list) or len(meshes) != 1 or not isinstance(meshes[0], dict):
        raise MaterialSynthesisError("unsupported_mesh_count", "material synthesis requires exactly one mesh")
    primitives = meshes[0].get("primitives")
    if not isinstance(primitives, list) or len(primitives) != 1 or not isinstance(primitives[0], dict):
        raise MaterialSynthesisError("unsupported_primitive_count", "material synthesis requires exactly one primitive")
    primitive = primitives[0]
    if "material" in primitive:
        raise MaterialSynthesisError("material_already_present", "primitive material assignment is already present")
    if primitive.get("mode", 4) != 4:
        raise MaterialSynthesisError("unsupported_primitive_mode", "material synthesis accepts TRIANGLES mode 4 only")
    if primitive.get("targets") is not None:
        raise MaterialSynthesisError("unsupported_morph_targets", "material synthesis rejects morph targets")
    attributes = primitive.get("attributes")
    required = {"POSITION", "NORMAL", "TEXCOORD_0"}
    if not isinstance(attributes, dict) or set(attributes) != required:
        missing = sorted(required - set(attributes or {})) if isinstance(attributes, dict) else sorted(required)
        unexpected = sorted(set(attributes or {}) - required) if isinstance(attributes, dict) else []
        raise MaterialSynthesisError(
            "missing_attribute" if missing else "unexpected_attribute",
            f"material source requires only POSITION/NORMAL/TEXCOORD_0; missing={missing}; unexpected={unexpected}",
            missing=missing,
            unexpected=unexpected,
        )
    try:
        path, _world = _hierarchy(document)
    except GLBPreprocessError as error:
        raise MaterialSynthesisError(error.code, str(error), **error.details) from error
    for key, limit_key, code in (
        ("accessors", "max_accessors", "unsupported_accessor_count"),
        ("bufferViews", "max_buffer_views", "unsupported_buffer_view_count"),
    ):
        value = document.get(key)
        if not isinstance(value, list) or len(value) > MATERIAL_LIMITS[limit_key]:
            raise MaterialSynthesisError(code, f"material source {key} exceeds its bounded count")
    return document, binary, path


def _logical_accessor_payload(document: dict[str, Any], binary: bytes, accessor_index: object) -> bytes:
    if isinstance(accessor_index, bool) or not isinstance(accessor_index, int):
        raise MaterialSynthesisError("invalid_accessor", "accessor index must be a non-negative integer")
    accessors = document.get("accessors")
    views = document.get("bufferViews")
    if not isinstance(accessors, list) or not 0 <= accessor_index < len(accessors) or not isinstance(views, list):
        raise MaterialSynthesisError("invalid_accessor", "accessor does not exist")
    accessor = accessors[accessor_index]
    if not isinstance(accessor, dict) or "sparse" in accessor:
        raise MaterialSynthesisError("unsupported_sparse_accessor", "material synthesis rejects sparse accessors")
    view_index = accessor.get("bufferView")
    if isinstance(view_index, bool) or not isinstance(view_index, int) or not 0 <= view_index < len(views):
        raise MaterialSynthesisError("invalid_accessor", "accessor bufferView does not exist")
    view = views[view_index]
    component_type = accessor.get("componentType")
    accessor_type = accessor.get("type")
    count = accessor.get("count")
    if (
        not isinstance(view, dict) or component_type not in _COMPONENT_BYTES or accessor_type not in _TYPE_COMPONENTS
        or isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MATERIAL_LIMITS["max_accessor_elements"]
    ):
        raise MaterialSynthesisError("invalid_accessor", "accessor metadata is outside the bounded subset")
    element_size = _COMPONENT_BYTES[component_type] * _TYPE_COMPONENTS[accessor_type]
    stride = view.get("byteStride", element_size)
    if isinstance(stride, bool) or not isinstance(stride, int) or stride < element_size:
        raise MaterialSynthesisError("invalid_byte_stride", "accessor stride is invalid")
    view_offset = view.get("byteOffset", 0)
    accessor_offset = accessor.get("byteOffset", 0)
    view_length = view.get("byteLength")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (view_offset, accessor_offset)):
        raise MaterialSynthesisError("accessor_out_of_bounds", "accessor offsets must be non-negative integers")
    if isinstance(view_length, bool) or not isinstance(view_length, int) or view_length <= 0:
        raise MaterialSynthesisError("buffer_view_out_of_bounds", "bufferView length must be positive")
    required = accessor_offset + (count - 1) * stride + element_size
    if required > view_length or view_offset + view_length > len(binary):
        raise MaterialSynthesisError("accessor_out_of_bounds", "accessor payload exceeds the embedded BIN chunk")
    return b"".join(
        binary[view_offset + accessor_offset + index * stride:view_offset + accessor_offset + index * stride + element_size]
        for index in range(count)
    )


def _payload_hashes(document: dict[str, Any], binary: bytes) -> dict[str, str]:
    primitive = document["meshes"][0]["primitives"][0]
    attributes = primitive["attributes"]
    roles = {
        "position": attributes["POSITION"],
        "normal": attributes["NORMAL"],
        "texcoord_0": attributes["TEXCOORD_0"],
        "indices": primitive.get("indices"),
    }
    return {role: _sha256(_logical_accessor_payload(document, binary, accessor)) for role, accessor in roles.items()}


def _synthesized_document(document: dict[str, Any], name: str) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["materials"] = [{"name": name}]
    result["meshes"][0]["primitives"][0]["material"] = 0
    return result


def synthesize_named_material(data: bytes, name: str) -> dict[str, Any]:
    """Assign one manifest-declared source name while preserving all BIN data."""
    material_name = _validate_name(name)
    document, binary, path = _source_document(data)
    before_hashes = _payload_hashes(document, binary)
    canonical_document = _synthesized_document(document, material_name)
    canonical = pack_glb(canonical_document, binary)

    validation_document = copy.deepcopy(canonical_document)
    validation_document["scene"] = 0
    validation_document["scenes"] = [{"nodes": [0]}]
    validation_document["nodes"] = [{"mesh": 0, "name": "stage4n_validation"}]
    try:
        semantic_mesh = parse_glb(pack_glb(validation_document, binary))
    except GLBError as error:
        raise MaterialSynthesisError(error.code, str(error), **error.details) from error

    direct_mesh = None
    direct_error = None
    try:
        direct_mesh = parse_glb(canonical)
    except GLBError as error:
        if error.code not in {"unsupported_scene", "unsupported_node_transform"}:
            raise MaterialSynthesisError("material_generation_canonical_mismatch", str(error), stage4f_code=error.code) from error
        direct_error = error.code

    reparsed_document, reparsed_binary = _chunks(canonical, MATERIAL_LIMITS)
    after_hashes = _payload_hashes(reparsed_document, reparsed_binary)
    if binary != reparsed_binary or before_hashes != after_hashes:
        raise MaterialSynthesisError("geometry_accessor_mutation", "material synthesis changed embedded attribute/index payloads")
    report_core = {
        "schema_version": 1,
        "success": True,
        "policy": "assign_single_named_material",
        "limits": dict(MATERIAL_LIMITS),
        "source_sha256": _sha256(data),
        "canonical_sha256": _sha256(canonical),
        "source_size_bytes": len(data),
        "canonical_size_bytes": len(canonical),
        "source_material_count": 0,
        "source_material_index": None,
        "canonical_material_count": 1,
        "canonical_material_index": 0,
        "material_name": material_name,
        "source_node_count": len(document["nodes"]),
        "source_node_path": path,
        "source_mesh_count": 1,
        "source_primitive_count": 1,
        "triangle_count": len(semantic_mesh.faces),
        "source_bin_sha256": _sha256(binary),
        "canonical_bin_sha256": _sha256(reparsed_binary),
        "accessor_payload_sha256": before_hashes,
        "geometry_attributes_preserved": True,
        "node_hierarchy_preserved": document.get("nodes") == reparsed_document.get("nodes"),
        "scene_preserved": document.get("scenes") == reparsed_document.get("scenes"),
        "stage4f_accepted": direct_mesh is not None,
        "stage4f_deferred_reason": direct_error,
    }
    semantic = json.dumps(report_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report_core["report_sha256"] = _sha256(semantic)
    return {
        "canonical_glb": canonical,
        "canonical_mesh": direct_mesh,
        "semantic_mesh": semantic_mesh,
        "report": report_core,
    }


def inspect_material_applicability(data: bytes, proposed_name: str = "generated_surface") -> dict[str, Any]:
    """Read-only bounded projection; never emits or retains a derived candidate."""
    try:
        name = _validate_name(proposed_name)
        result = synthesize_named_material(data, name)
    except MaterialSynthesisError as error:
        structure_applicable = False
        structure_error: dict[str, Any] | None = None
        try:
            document, _binary = _chunks(data, MATERIAL_LIMITS)
            path, _world = _hierarchy(document)
            structure_applicable = True
            structure_error = None
        except (GLBError, GLBPreprocessError) as structure:
            structure_error = {"code": structure.code, "message": str(structure), "details": structure.details}
            path = []
        return {
            "applicable": False,
            "structure_applicable": structure_applicable,
            "source_node_path": path,
            "proposed_name": proposed_name,
            "error": {"code": error.code, "message": str(error), "details": error.details},
            "structure_error": structure_error,
        }
    return {
        "applicable": True,
        "structure_applicable": True,
        "source_node_path": result["report"]["source_node_path"],
        "proposed_name": proposed_name,
        "error": None,
    }
