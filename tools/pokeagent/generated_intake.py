"""Read-only intake analysis for untrusted externally generated GLB assets.

The intake boundary deliberately does not normalize, repair, or compile a mesh.
It records what a generator emitted and compares that structure with the strict
Stage 4F parser and the exact Stage 4G simplifier contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any

from .glb import BIN_CHUNK, GLB_MAGIC, GLB_VERSION, JSON_CHUNK, GLB_LIMITS, GLBError, parse_glb
from .glb_bootstrap import inspect_color0_discard_applicability
from .glb_preprocess import inspect_static_hierarchy
from .glb_geometry_reduce import inspect_geometry_applicability
from .glb_materials import inspect_material_applicability
from .glb_normals import NORMAL_LIMITS, inspect_normal_applicability
from .glb_uvs import UV_LIMITS, inspect_uv_applicability


INTAKE_SCHEMA_VERSION = 1
INTAKE_REPORT_SCHEMA_VERSION = 1
MAX_INTAKE_GLB_BYTES = 8 * 1024 * 1024
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TRIANGLE_DISPLAY_LIST_HEADER_BYTES = 12
TRIANGLE_DISPLAY_LIST_BYTES = 68


class GeneratedIntakeError(ValueError):
    """A generated-asset intake manifest or container is invalid."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_path(root: Path, value: object, parent: str, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise GeneratedIntakeError("invalid_manifest", f"{field} must be a repository-relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise GeneratedIntakeError("unsafe_path", f"{field} escapes its canonical project directory")
    path = (root / relative).resolve()
    required = (root / parent).resolve()
    try:
        path.relative_to(required)
    except ValueError as error:
        raise GeneratedIntakeError("unsafe_path", f"{field} must be below {parent}") from error
    return path


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GeneratedIntakeError(code, f"required file does not exist: {path}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeneratedIntakeError(code, f"file is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise GeneratedIntakeError(code, f"JSON root must be an object: {path}")
    return value


def load_intake_manifest(path: Path, root: Path) -> dict[str, Any]:
    """Load the exact Stage 4H generated-input manifest."""
    manifest = _load_json(path, "invalid_intake_manifest")
    required = {
        "schema_version", "id", "source", "source_format", "source_sha256",
        "concept_image", "concept_sha256", "provenance", "target",
    }
    if set(manifest) != required or manifest.get("schema_version") != INTAKE_SCHEMA_VERSION:
        raise GeneratedIntakeError(
            "invalid_intake_manifest",
            "generated intake manifest must use schema 1 and the exact bounded key set",
        )
    if not isinstance(manifest.get("id"), str) or SAFE_ID.fullmatch(manifest["id"]) is None:
        raise GeneratedIntakeError("invalid_asset_id", "generated asset id is not a stable project symbol")
    if manifest.get("source_format") != "glb":
        raise GeneratedIntakeError("unsupported_source_format", "Stage 4H intake accepts GLB only")
    for field in ("source_sha256", "concept_sha256"):
        if not isinstance(manifest.get(field), str) or SHA256.fullmatch(manifest[field]) is None:
            raise GeneratedIntakeError("invalid_source_hash", f"{field} must be a lowercase SHA-256")
    source = _safe_path(root, manifest["source"], "assets/source/generated", "source")
    concept = _safe_path(root, manifest["concept_image"], "assets/concepts", "concept_image")
    provenance_path = _safe_path(root, manifest["provenance"], "assets/provenance", "provenance")
    target = manifest.get("target")
    if not isinstance(target, dict) or set(target) != {
        "shape", "capacity_bytes", "material_alias", "texture_symbol", "intended_size_tiles", "collision_footprint"
    }:
        raise GeneratedIntakeError("invalid_target", "target must describe the bounded existing DS asset envelope")
    if target.get("shape") != 6 or target.get("capacity_bytes") != 1068:
        raise GeneratedIntakeError("invalid_target", "Stage 4H target must retain verified shape 6 capacity 1068")
    if target.get("material_alias") != "prop_secondary" or target.get("texture_symbol") != "stage4d_stone":
        raise GeneratedIntakeError("invalid_target", "Stage 4H may only reuse the proven stone material binding")
    for field in ("intended_size_tiles", "collision_footprint"):
        value = target.get(field)
        if (
            not isinstance(value, list) or len(value) != 3
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) or item <= 0 for item in value)
        ):
            raise GeneratedIntakeError("invalid_target", f"{field} must contain three positive dimensions")
    for resolved, field in ((source, "source"), (concept, "concept_image"), (provenance_path, "provenance")):
        if not resolved.is_file():
            raise GeneratedIntakeError("missing_input", f"{field} does not exist: {resolved}")
    source_data = source.read_bytes()
    concept_data = concept.read_bytes()
    if _sha256(source_data) != manifest["source_sha256"]:
        raise GeneratedIntakeError("source_hash_mismatch", "raw generated GLB does not match its immutable hash")
    if _sha256(concept_data) != manifest["concept_sha256"]:
        raise GeneratedIntakeError("concept_hash_mismatch", "concept image does not match its immutable hash")
    provenance = _load_json(provenance_path, "invalid_provenance")
    if provenance.get("asset_id") != manifest["id"]:
        raise GeneratedIntakeError("provenance_mismatch", "provenance asset_id disagrees with the intake manifest")
    if provenance.get("raw_output_sha256") != manifest["source_sha256"]:
        raise GeneratedIntakeError("provenance_mismatch", "provenance raw output hash disagrees with the intake manifest")
    if provenance.get("concept_sha256") != manifest["concept_sha256"]:
        raise GeneratedIntakeError("provenance_mismatch", "provenance concept hash disagrees with the intake manifest")
    return {**manifest, "_paths": {"source": source, "concept": concept, "provenance": provenance_path}, "_provenance": provenance}


def _glb_document(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) > MAX_INTAKE_GLB_BYTES:
        raise GeneratedIntakeError("intake_source_too_large", "generated GLB exceeds the 8 MiB intake-analysis bound")
    if len(data) < 20:
        raise GeneratedIntakeError("malformed_glb_length", "GLB is shorter than its header and JSON chunk")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != GLB_MAGIC:
        raise GeneratedIntakeError("invalid_glb_magic", "GLB magic must be ASCII glTF")
    if version != GLB_VERSION:
        raise GeneratedIntakeError("invalid_glb_version", "only GLB container version 2 is supported")
    if declared_length != len(data):
        raise GeneratedIntakeError("malformed_glb_length", "GLB declared length disagrees with the file length")
    chunks: list[tuple[int, bytes]] = []
    offset = 12
    while offset < len(data):
        if offset % 4 or offset + 8 > len(data):
            raise GeneratedIntakeError("malformed_chunk_length", "GLB chunk header is truncated or misaligned")
        length, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        if length % 4 or offset + length > len(data):
            raise GeneratedIntakeError("malformed_chunk_length", "GLB chunk length is misaligned or out of bounds")
        chunks.append((kind, data[offset:offset + length]))
        offset += length
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise GeneratedIntakeError("missing_json_chunk", "GLB JSON must be the first chunk")
    if len(chunks) != 2 or chunks[1][0] != BIN_CHUNK:
        raise GeneratedIntakeError("unsupported_glb_chunks", "intake requires exactly one JSON and one BIN chunk")
    try:
        document = json.loads(chunks[0][1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeneratedIntakeError("invalid_glb_json", "GLB JSON chunk is invalid") from error
    if not isinstance(document, dict):
        raise GeneratedIntakeError("invalid_glb_json", "GLB JSON root must be an object")
    binary = chunks[1][1]
    buffers = _list(document, "buffers")
    if len(buffers) != 1 or not isinstance(buffers[0], dict):
        raise GeneratedIntakeError("invalid_buffer", "intake requires one embedded GLB buffer")
    if "uri" in buffers[0]:
        raise GeneratedIntakeError("external_uri", "generated intake never follows external buffer URIs")
    declared = buffers[0].get("byteLength")
    if isinstance(declared, bool) or not isinstance(declared, int) or declared < 1:
        raise GeneratedIntakeError("invalid_buffer", "embedded buffer byteLength must be a positive integer")
    if len(binary) < declared or len(binary) > declared + 3 or any(binary[declared:]):
        raise GeneratedIntakeError("invalid_buffer", "embedded BIN length/padding disagrees with the buffer record")
    return document, binary


def _list(document: dict[str, Any], key: str) -> list[Any]:
    value = document.get(key, [])
    return value if isinstance(value, list) else []


def _problem(code: str, message: str, **details: object) -> dict[str, object]:
    return {"code": code, "message": message, "details": details}


_INTAKE_COMPONENTS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_INTAKE_TYPES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _accessor_layout(document: dict[str, Any], binary: bytes, index: int) -> tuple[dict[str, Any], int, int, int, str]:
    accessors = _list(document, "accessors")
    views = _list(document, "bufferViews")
    if not 0 <= index < len(accessors) or not isinstance(accessors[index], dict):
        raise GeneratedIntakeError("invalid_accessor", f"accessor {index} is missing")
    accessor = accessors[index]
    if "sparse" in accessor:
        raise GeneratedIntakeError("unsupported_sparse_accessor", f"intake does not decode sparse accessor {index}")
    component_type = accessor.get("componentType")
    accessor_type = accessor.get("type")
    count = accessor.get("count")
    view_index = accessor.get("bufferView")
    if component_type not in _INTAKE_COMPONENTS or accessor_type not in _INTAKE_TYPES:
        raise GeneratedIntakeError("unsupported_accessor_component_type", f"accessor {index} has an unknown component/type pair")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise GeneratedIntakeError("invalid_accessor", f"accessor {index} count must be positive")
    if isinstance(view_index, bool) or not isinstance(view_index, int) or not 0 <= view_index < len(views):
        raise GeneratedIntakeError("invalid_accessor", f"accessor {index} references a missing bufferView")
    view = views[view_index]
    if not isinstance(view, dict) or view.get("buffer") != 0:
        raise GeneratedIntakeError("buffer_view_out_of_bounds", f"bufferView {view_index} must use embedded buffer 0")
    view_offset = view.get("byteOffset", 0)
    view_length = view.get("byteLength")
    accessor_offset = accessor.get("byteOffset", 0)
    for value, field, minimum in (
        (view_offset, "bufferView.byteOffset", 0),
        (view_length, "bufferView.byteLength", 1),
        (accessor_offset, "accessor.byteOffset", 0),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise GeneratedIntakeError("buffer_view_out_of_bounds", f"{field} must be an integer >= {minimum}")
    if view_offset + view_length > len(binary):
        raise GeneratedIntakeError("buffer_view_out_of_bounds", f"bufferView {view_index} exceeds the BIN chunk")
    format_code, component_size = _INTAKE_COMPONENTS[component_type]
    components = _INTAKE_TYPES[accessor_type]
    element_size = component_size * components
    stride = view.get("byteStride", element_size)
    if isinstance(stride, bool) or not isinstance(stride, int) or stride < element_size or stride > 252:
        raise GeneratedIntakeError("invalid_byte_stride", f"accessor {index} has an invalid byte stride")
    if (view_offset + accessor_offset) % component_size:
        raise GeneratedIntakeError("invalid_accessor_alignment", f"accessor {index} is not component aligned")
    required = accessor_offset + (count - 1) * stride + element_size
    if required > view_length:
        raise GeneratedIntakeError("accessor_out_of_bounds", f"accessor {index} exceeds bufferView {view_index}")
    return accessor, view_offset + accessor_offset, stride, count, "<" + format_code * components


def _decode_for_intake(document: dict[str, Any], binary: bytes, index: int) -> list[tuple[int | float, ...]]:
    accessor, start, stride, count, format_code = _accessor_layout(document, binary, index)
    values = [struct.unpack_from(format_code, binary, start + row * stride) for row in range(count)]
    if accessor.get("componentType") == 5126:
        for value in values:
            if any(not isinstance(item, float) or not (-float("inf") < item < float("inf")) for item in value):
                raise GeneratedIntakeError("nonfinite_coordinate", f"accessor {index} contains NaN or infinity")
    return values


def _primitive_metrics(document: dict[str, Any], binary: bytes) -> dict[str, Any]:
    accessors = _list(document, "accessors")
    primitive_summaries: list[dict[str, object]] = []
    total_triangles = 0
    referenced_vertices = 0
    position_count = 0
    bounds: dict[str, object] | None = None
    material_names = [item.get("name") for item in _list(document, "materials") if isinstance(item, dict)]
    for mesh_index, mesh in enumerate(_list(document, "meshes")):
        if not isinstance(mesh, dict):
            continue
        for primitive_index, primitive in enumerate(_list(mesh, "primitives")):
            if not isinstance(primitive, dict):
                continue
            attributes = primitive.get("attributes") if isinstance(primitive.get("attributes"), dict) else {}
            index_id = primitive.get("indices")
            index_count = 0
            max_index = None
            decoded_indices: list[tuple[int | float, ...]] = []
            if isinstance(index_id, int) and 0 <= index_id < len(accessors) and isinstance(accessors[index_id], dict):
                index_accessor = accessors[index_id]
                index_count = index_accessor.get("count", 0) if isinstance(index_accessor.get("count"), int) else 0
                decoded_indices = _decode_for_intake(document, binary, index_id)
                if decoded_indices and all(isinstance(value[0], int) for value in decoded_indices):
                    max_index = max(int(value[0]) for value in decoded_indices)
            position_id = attributes.get("POSITION")
            current_position_count = 0
            if isinstance(position_id, int) and 0 <= position_id < len(accessors) and isinstance(accessors[position_id], dict):
                position_accessor = accessors[position_id]
                current_position_count = position_accessor.get("count", 0) if isinstance(position_accessor.get("count"), int) else 0
                decoded_positions = _decode_for_intake(document, binary, position_id)
                if decoded_positions and all(len(value) == 3 for value in decoded_positions):
                    observed_min = [min(float(value[axis]) for value in decoded_positions) for axis in range(3)]
                    observed_max = [max(float(value[axis]) for value in decoded_positions) for axis in range(3)]
                    if bounds is None:
                        bounds = {"min": observed_min, "max": observed_max}
                    for label, observed in (("min", observed_min), ("max", observed_max)):
                        declared = position_accessor.get(label)
                        if (
                            not isinstance(declared, list) or len(declared) != 3
                            or any(not isinstance(item, (int, float)) or abs(float(item) - observed[axis]) > 1e-6 for axis, item in enumerate(declared))
                        ):
                            raise GeneratedIntakeError("invalid_accessor_bounds", f"POSITION accessor {position_id} {label} disagrees with decoded values")
            triangle_count = index_count // 3 if primitive.get("mode", 4) == 4 and index_count % 3 == 0 else 0
            if decoded_indices and max_index is not None and max_index >= current_position_count:
                raise GeneratedIntakeError("invalid_indices", f"primitive {primitive_index} references a position outside its accessor")
            total_triangles += triangle_count
            position_count += current_position_count
            referenced_vertices += max_index + 1 if isinstance(max_index, int) else current_position_count
            primitive_summaries.append({
                "mesh": mesh_index,
                "primitive": primitive_index,
                "mode": primitive.get("mode", 4),
                "attributes": sorted(attributes),
                "indices_accessor": index_id,
                "index_count": index_count,
                "triangle_count": triangle_count,
                "position_count": current_position_count,
                "max_referenced_index": max_index,
                "material": primitive.get("material"),
            })
    return {
        "primitives": primitive_summaries,
        "triangle_count": total_triangles,
        "position_count": position_count,
        "referenced_vertices": referenced_vertices,
        "bounds": bounds,
        "material_names": material_names,
    }


def _accessor_summaries(document: dict[str, Any]) -> list[dict[str, object]]:
    summaries = []
    for index, accessor in enumerate(_list(document, "accessors")):
        if not isinstance(accessor, dict):
            summaries.append({"index": index, "invalid": True})
            continue
        summaries.append({
            "index": index,
            "component_type": accessor.get("componentType"),
            "type": accessor.get("type"),
            "count": accessor.get("count"),
            "normalized": bool(accessor.get("normalized", False)),
            "has_bounds": "min" in accessor and "max" in accessor,
        })
    return summaries


def _compatibility(document: dict[str, Any], metrics: dict[str, Any], strict_error: dict[str, object] | None, capacity: int) -> list[dict[str, object]]:
    problems: list[dict[str, object]] = []
    nodes = _list(document, "nodes")
    materials = _list(document, "materials")
    if len(nodes) != 1:
        problems.append(_problem("node_count_exceeds_stage4f", "Stage 4F requires exactly one mesh node", observed=len(nodes), supported=1))
    if any(isinstance(node, dict) and node.get("children") for node in nodes):
        problems.append(_problem("hierarchy_unsupported", "Stage 4F does not bake node hierarchies"))
    if any(isinstance(node, dict) and any(key in node for key in ("matrix", "translation", "rotation", "scale")) for node in nodes):
        problems.append(_problem("node_transform_unsupported", "Stage 4F requires an implicit identity transform"))
    if len(materials) != 1:
        problems.append(_problem("material_count_invalid", "Stage 4F requires exactly one named source material", observed=len(materials), supported=1))
    if any(document.get(key) for key in ("images", "textures", "samplers")):
        problems.append(_problem("embedded_textures_unsupported", "generated embedded textures are outside Stage 4H policy"))
    if document.get("animations"):
        problems.append(_problem("animation_unsupported", "static generated-asset intake rejects animation"))
    if document.get("skins"):
        problems.append(_problem("skin_unsupported", "static generated-asset intake rejects skins"))
    if document.get("extensionsUsed") or document.get("extensionsRequired"):
        problems.append(_problem("extensions_unsupported", "Stage 4F accepts no GLTF extensions"))
    for primitive in metrics["primitives"]:
        attributes = set(primitive["attributes"])
        for attribute, code in (("NORMAL", "missing_normal"), ("TEXCOORD_0", "missing_texcoord_0")):
            if attribute not in attributes:
                problems.append(_problem(code, f"primitive {primitive['primitive']} lacks required {attribute}"))
        unexpected = sorted(attributes - {"POSITION", "NORMAL", "TEXCOORD_0"})
        if unexpected:
            problems.append(_problem("unexpected_attribute", "Stage 4F requires only POSITION/NORMAL/TEXCOORD_0", attributes=unexpected))
        if primitive["mode"] != 4:
            problems.append(_problem("primitive_mode_unsupported", "Stage 4F accepts independent triangles mode 4", observed=primitive["mode"]))
    oversized = [summary for summary in _accessor_summaries(document) if isinstance(summary.get("count"), int) and summary["count"] > GLB_LIMITS["max_accessor_elements"]]
    if oversized:
        problems.append(_problem(
            "accessor_element_budget_exceeded",
            "generated accessors exceed the Stage 4F untrusted-input element limit",
            accessors=[{"index": item["index"], "count": item["count"]} for item in oversized],
            supported=GLB_LIMITS["max_accessor_elements"],
        ))
    if metrics["position_count"] > 128:
        problems.append(_problem("vertex_budget_exceeded", "generated positions exceed the Stage 4G source budget", observed=metrics["position_count"], supported=128))
    if metrics["triangle_count"] > 64:
        problems.append(_problem("face_budget_exceeded", "generated triangles exceed the Stage 4G source budget", observed=metrics["triangle_count"], supported=64))
    projected = TRIANGLE_DISPLAY_LIST_HEADER_BYTES + metrics["triangle_count"] * TRIANGLE_DISPLAY_LIST_BYTES
    if projected > capacity:
        problems.append(_problem("ds_display_list_overflow", "independent-triangle projection exceeds the verified shape capacity", projected_bytes=projected, capacity_bytes=capacity, overflow_bytes=projected - capacity))
    if strict_error is not None and not any(item["code"] == strict_error["code"] for item in problems):
        problems.insert(0, strict_error)
    # Preserve a stable first-occurrence order while avoiding repeated missing-attribute codes.
    unique: list[dict[str, object]] = []
    seen: set[str] = set()
    for problem in problems:
        code = str(problem["code"])
        if code not in seen:
            seen.add(code)
            unique.append(problem)
    return unique


def inspect_generated_asset(manifest_path: Path, root: Path) -> dict[str, Any]:
    """Analyze an immutable generated GLB without changing or compiling it."""
    manifest = load_intake_manifest(manifest_path, root)
    source_path = manifest["_paths"]["source"]
    data = source_path.read_bytes()
    document, binary = _glb_document(data)
    metrics = _primitive_metrics(document, binary)
    strict_error = None
    try:
        parse_glb(data)
    except GLBError as error:
        strict_error = error.as_dict() if hasattr(error, "as_dict") else {
            "code": error.code,
            "message": str(error),
            "details": error.details,
        }
    target = manifest["target"]
    problems = _compatibility(document, metrics, strict_error, target["capacity_bytes"])
    structure_projection = inspect_static_hierarchy(data)
    normal_projection = inspect_normal_applicability(data)
    uv_projection = inspect_uv_applicability(data)
    material_projection = inspect_material_applicability(data)
    geometry_projection = inspect_geometry_applicability(data)
    bootstrap_projection = inspect_color0_discard_applicability(data)
    topology_projection_reasons = []
    if metrics["triangle_count"] > NORMAL_LIMITS["max_faces"]:
        topology_projection_reasons.append({
            "code": "normal_generation_face_budget",
            "observed": metrics["triangle_count"],
            "supported": NORMAL_LIMITS["max_faces"],
        })
    if metrics["position_count"] > NORMAL_LIMITS["max_accessor_elements"]:
        topology_projection_reasons.append({
            "code": "normal_generation_accessor_budget",
            "observed": metrics["position_count"],
            "supported": NORMAL_LIMITS["max_accessor_elements"],
        })
    uv_topology_projection_reasons = []
    if metrics["triangle_count"] > UV_LIMITS["max_faces"]:
        uv_topology_projection_reasons.append({
            "code": "uv_generation_face_budget",
            "observed": metrics["triangle_count"],
            "supported": UV_LIMITS["max_faces"],
        })
    if metrics["position_count"] > UV_LIMITS["max_accessor_elements"]:
        uv_topology_projection_reasons.append({
            "code": "uv_generation_accessor_budget",
            "observed": metrics["position_count"],
            "supported": UV_LIMITS["max_accessor_elements"],
        })
    projected = TRIANGLE_DISPLAY_LIST_HEADER_BYTES + metrics["triangle_count"] * TRIANGLE_DISPLAY_LIST_BYTES
    stage4f_compliant = not problems and strict_error is None
    simplification_reasons = []
    primitive_attributes = [set(item["attributes"]) for item in metrics["primitives"]]
    if not stage4f_compliant:
        simplification_reasons.append("source_does_not_reach_normalized_typed_ir")
    if any("NORMAL" not in attributes for attributes in primitive_attributes):
        simplification_reasons.append("authored_normals_required")
    if any("TEXCOORD_0" not in attributes for attributes in primitive_attributes):
        simplification_reasons.append("authored_uv0_required")
    if metrics["triangle_count"] > 64:
        simplification_reasons.append("general_non_coplanar_reduction_is_unproven")
    report_core = {
        "schema_version": INTAKE_REPORT_SCHEMA_VERSION,
        "success": True,
        "accepted": stage4f_compliant and projected <= target["capacity_bytes"],
        "asset_id": manifest["id"],
        "quality_classification": "ACCEPTABLE_WITHOUT_MANUAL_CLEANUP" if stage4f_compliant and projected <= target["capacity_bytes"] else "REJECTED_UNSUPPORTED_STRUCTURE",
        "canonical_boundary": "raw_generated_glb_sha256",
        "source": {
            "path": manifest["source"],
            "format": "glb",
            "size_bytes": len(data),
            "sha256": _sha256(data),
        },
        "concept": {
            "path": manifest["concept_image"],
            "sha256": manifest["concept_sha256"],
        },
        "provenance": {
            "path": manifest["provenance"],
            "generator": manifest["_provenance"].get("generator"),
            "generator_model": manifest["_provenance"].get("generator_model"),
            "generator_revision": manifest["_provenance"].get("generator_revision"),
        },
        "container": {
            "glb_version": struct.unpack_from("<I", data, 4)[0],
            "bin_chunk_bytes": len(binary),
            "generator": (document.get("asset") or {}).get("generator") if isinstance(document.get("asset"), dict) else None,
        },
        "structure": {
            "scene_count": len(_list(document, "scenes")),
            "node_count": len(_list(document, "nodes")),
            "mesh_count": len(_list(document, "meshes")),
            "primitive_count": len(metrics["primitives"]),
            "material_count": len(_list(document, "materials")),
            "texture_count": len(_list(document, "textures")),
            "image_count": len(_list(document, "images")),
            "animation_count": len(_list(document, "animations")),
            "skin_count": len(_list(document, "skins")),
            "morph_target_count": sum(
                len(primitive.get("targets", []))
                for mesh in _list(document, "meshes") if isinstance(mesh, dict)
                for primitive in _list(mesh, "primitives") if isinstance(primitive, dict) and isinstance(primitive.get("targets", []), list)
            ),
            "extensions_used": document.get("extensionsUsed", []),
            "node_hierarchy_present": any(isinstance(node, dict) and bool(node.get("children")) for node in _list(document, "nodes")),
            "node_transform_present": any(
                isinstance(node, dict) and any(key in node for key in ("matrix", "translation", "rotation", "scale"))
                for node in _list(document, "nodes")
            ),
        },
        "geometry": {
            "triangle_count": metrics["triangle_count"],
            "position_count": metrics["position_count"],
            "referenced_vertices": metrics["referenced_vertices"],
            "bounds": metrics["bounds"],
            "material_names": metrics["material_names"],
            "primitives": metrics["primitives"],
            "accessors": _accessor_summaries(document),
        },
        "budget": {
            "projection_basis": "independent triangles with required NORMAL/TEXCOORD/VTX commands",
            "projected_nitro_bytes_if_attributes_existed": projected,
            "shape": target["shape"],
            "capacity_bytes": target["capacity_bytes"],
            "overflow_bytes": max(0, projected - target["capacity_bytes"]),
            "utilization_percent": round(projected / target["capacity_bytes"] * 100, 2),
        },
        "stage4f": {
            "compliant": stage4f_compliant,
            "strict_parser_error": strict_error,
            "problems": problems,
        },
        "stage4g": {
            "exact_simplification_applicable": not simplification_reasons,
            "reasons": simplification_reasons,
        },
        "stage4k": {
            "structure_preprocess": structure_projection,
            "remaining_blockers": [
                problem["code"] for problem in problems
                if problem["code"] not in {
                    "unsupported_scene", "node_count_exceeds_stage4f",
                    "hierarchy_unsupported", "node_transform_unsupported",
                }
            ],
            "retroactive_approval": False,
        },
        "stage4l": {
            "normal_generation": normal_projection,
            "topology_subset": {
                "applicable": not topology_projection_reasons,
                "fully_evaluated": not topology_projection_reasons and normal_projection.get("applicable", False),
                "reasons": topology_projection_reasons,
            },
            "remaining_blockers": [problem["code"] for problem in problems],
            "raw_source_unchanged": True,
            "retroactive_approval": False,
        },
        "stage4m": {
            "uv_generation": uv_projection,
            "topology_subset": {
                "applicable": not uv_topology_projection_reasons,
                "fully_evaluated": not uv_topology_projection_reasons and uv_projection.get("applicable", False),
                "reasons": uv_topology_projection_reasons,
            },
            "remaining_blockers": [problem["code"] for problem in problems],
            "raw_source_unchanged": True,
            "retroactive_approval": False,
        },
        "stage4n": {
            "material_synthesis": material_projection,
            "remaining_blockers": [problem["code"] for problem in problems],
            "raw_source_unchanged": True,
            "retroactive_approval": False,
        },
        "stage4o": {
            "geometry_predecimation": geometry_projection,
            "raw_source_unchanged": True,
            "retroactive_approval": False,
        },
        "stage4p": {
            "color0_discard_projection": bootstrap_projection,
            "attribute_bootstrap_not_attempted": True,
            "raw_source_unchanged": True,
            "derived_candidate_created": False,
            "retroactive_approval": False,
        },
        "target": target,
    }
    semantic = json.dumps(report_core, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    report_core["report_sha256"] = _sha256(semantic)
    return report_core


def write_intake_report(manifest_path: Path, output: Path, root: Path) -> dict[str, Any]:
    """Write one deterministic ignored JSON report."""
    report = inspect_generated_asset(manifest_path, root)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "intake-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**report, "outputs": {"report": str(report_path)}}
