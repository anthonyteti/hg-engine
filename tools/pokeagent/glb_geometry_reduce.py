"""Bounded geometry-only GLB adapter and Stage 4O preprocessing manifest."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import struct
from typing import Any

from .glb import GLBError, _chunks, pack_glb
from .glb_preprocess import GLBPreprocessError, _hierarchy
from .mesh_predecimate import (
    GeometryReductionError,
    canonical_geometry,
    inspect_geometry_quality,
    reduce_geometry,
    validate_geometry,
)


GEOMETRY_LIMITS = {
    "max_source_bytes": 8 * 1024 * 1024,
    "max_buffer_bytes": 8 * 1024 * 1024,
    "max_nodes": 4,
    "max_meshes": 1,
    "max_primitives": 1,
    "max_accessors": 8,
    "max_buffer_views": 8,
    "max_positions": 8192,
    "max_triangles": 16384,
    "max_indices": 49152,
}
BOOTSTRAP_ENVELOPE = {"max_faces": 80, "max_positions": 256, "max_accessor_elements": 256}
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY = (
    (1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0),
)
_COMPONENTS = {5121: ("B", 1), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_TYPES = {"SCALAR": 1, "VEC3": 3}


class GeometryGLBError(ValueError):
    """A GLB or policy is outside the bounded geometry-only contract."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _list(document: dict[str, Any], key: str, maximum: int, code: str, *, exact: int | None = None) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list) or len(value) > maximum or (exact is not None and len(value) != exact):
        raise GeometryGLBError(code, f"{key} count is outside the bounded Stage 4O contract")
    return value


def _accessor(
    document: dict[str, Any], binary: bytes, index: object, expected_type: str, components: set[int], maximum: int,
) -> list[tuple[int | float, ...]]:
    if isinstance(index, bool) or not isinstance(index, int):
        raise GeometryGLBError("geometry_predecimation_invalid_accessor", "accessor index must be an integer")
    accessors = document["accessors"]; views = document["bufferViews"]
    if not 0 <= index < len(accessors) or not isinstance(accessors[index], dict):
        raise GeometryGLBError("geometry_predecimation_invalid_accessor", "accessor index is out of bounds")
    accessor = accessors[index]
    if "sparse" in accessor:
        raise GeometryGLBError("geometry_predecimation_sparse_accessor", "sparse accessors are unsupported")
    component = accessor.get("componentType"); kind = accessor.get("type"); count = accessor.get("count")
    if component not in components or kind != expected_type:
        raise GeometryGLBError("geometry_predecimation_accessor_type", "accessor component/type is unsupported")
    if accessor.get("normalized", False) is not False:
        raise GeometryGLBError("geometry_predecimation_normalized_accessor", "geometry accessors must not be normalized")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= maximum:
        raise GeometryGLBError("geometry_predecimation_accessor_budget", "accessor count exceeds its source limit")
    view_index = accessor.get("bufferView")
    if isinstance(view_index, bool) or not isinstance(view_index, int) or not 0 <= view_index < len(views):
        raise GeometryGLBError("geometry_predecimation_invalid_accessor", "accessor bufferView is missing")
    view = views[view_index]
    if not isinstance(view, dict) or view.get("buffer") != 0:
        raise GeometryGLBError("geometry_predecimation_buffer_view", "bufferView must reference embedded buffer 0")
    fmt, component_size = _COMPONENTS[component]; element_size = component_size * _TYPES[kind]
    stride = view.get("byteStride", element_size)
    if expected_type == "SCALAR" and "byteStride" in view:
        raise GeometryGLBError("geometry_predecimation_invalid_stride", "index accessor must be tightly packed")
    if isinstance(stride, bool) or not isinstance(stride, int) or stride < element_size or stride > 252:
        raise GeometryGLBError("geometry_predecimation_invalid_stride", "accessor stride is invalid")
    values = (view.get("byteOffset", 0), view.get("byteLength"), accessor.get("byteOffset", 0))
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise GeometryGLBError("geometry_predecimation_accessor_bounds", "accessor offsets/length are invalid")
    view_offset, view_length, accessor_offset = values
    if view_length < 1 or view_offset + view_length > len(binary):
        raise GeometryGLBError("geometry_predecimation_accessor_bounds", "bufferView exceeds embedded BIN")
    if (view_offset + accessor_offset) % component_size:
        raise GeometryGLBError("geometry_predecimation_accessor_alignment", "accessor is misaligned")
    required = accessor_offset + (count - 1) * stride + element_size
    if required > view_length:
        raise GeometryGLBError("geometry_predecimation_accessor_bounds", "accessor exceeds its bufferView")
    format_code = "<" + fmt * _TYPES[kind]
    result = [struct.unpack_from(format_code, binary, view_offset + accessor_offset + row * stride) for row in range(count)]
    if component == 5126 and any(not math.isfinite(float(item)) for row in result for item in row):
        raise GeometryGLBError("geometry_predecimation_nonfinite", "POSITION contains NaN or infinity")
    return result


def parse_geometry_glb(
    data: bytes, *, allow_auxiliary: bool = False, validate_topology: bool = True,
) -> dict[str, Any]:
    """Decode the bounded geometry-only source without interpreting attributes."""
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
    except GLBError as error:
        raise GeometryGLBError(error.code, str(error), **error.details) from error
    asset = document.get("asset")
    if not isinstance(asset, dict) or asset.get("version") != "2.0" or asset.get("minVersion") not in (None, "2.0"):
        raise GeometryGLBError("invalid_gltf_version", "Stage 4O requires glTF 2.0")
    if document.get("extensionsUsed") or document.get("extensionsRequired"):
        raise GeometryGLBError("unsupported_gltf_extension", "Stage 4O accepts no extensions or compression")
    for key, code in (("animations", "unsupported_animation"), ("skins", "unsupported_skin")):
        if document.get(key): raise GeometryGLBError(code, f"Stage 4O rejects {key}")
    if any(document.get(key) for key in ("materials", "images", "textures", "samplers", "cameras")):
        raise GeometryGLBError("unsupported_geometry_resource", "Stage 4O processes geometry only")
    try:
        path, world = _hierarchy(document)
    except GLBPreprocessError as error:
        raise GeometryGLBError(error.code, str(error), **error.details) from error
    if any(abs(world[row][column] - _IDENTITY[row][column]) > 1e-12 for row in range(4) for column in range(4)):
        raise GeometryGLBError(
            "predecimation_requires_transform_bake",
            "Stage 4O accepts only an identity root-to-mesh chain; Stage 4K owns transform baking",
        )
    meshes = _list(document, "meshes", GEOMETRY_LIMITS["max_meshes"], "unsupported_mesh_count", exact=1)
    accessors = _list(document, "accessors", GEOMETRY_LIMITS["max_accessors"], "unsupported_accessor_count")
    views = _list(document, "bufferViews", GEOMETRY_LIMITS["max_buffer_views"], "unsupported_buffer_view_count")
    buffers = _list(document, "buffers", 1, "unsupported_buffer_count", exact=1)
    document["accessors"] = accessors; document["bufferViews"] = views
    if not isinstance(buffers[0], dict) or "uri" in buffers[0]:
        raise GeometryGLBError("external_uri", "Stage 4O never loads external buffers")
    declared = buffers[0].get("byteLength")
    if isinstance(declared, bool) or not isinstance(declared, int) or not 1 <= declared <= GEOMETRY_LIMITS["max_buffer_bytes"]:
        raise GeometryGLBError("invalid_buffer", "embedded buffer length is invalid")
    if len(binary) < declared or len(binary) > declared + 3 or any(binary[declared:]):
        raise GeometryGLBError("invalid_buffer", "BIN length/padding disagrees with the buffer record")
    mesh = meshes[0]
    primitives = mesh.get("primitives") if isinstance(mesh, dict) else None
    if not isinstance(primitives, list) or len(primitives) != 1 or not isinstance(primitives[0], dict):
        raise GeometryGLBError("unsupported_primitive_count", "Stage 4O requires one primitive")
    primitive = primitives[0]
    if primitive.get("mode", 4) != 4:
        raise GeometryGLBError("unsupported_primitive_mode", "Stage 4O accepts indexed TRIANGLES mode 4 only")
    if primitive.get("targets") is not None:
        raise GeometryGLBError("unsupported_morph_targets", "Stage 4O rejects morph targets")
    if "material" in primitive:
        raise GeometryGLBError(
            "unsupported_geometry_material",
            "Stage 4O cannot discard or reinterpret a source material assignment",
        )
    attributes = primitive.get("attributes")
    if not isinstance(attributes, dict) or "POSITION" not in attributes:
        raise GeometryGLBError("missing_position", "Stage 4O requires POSITION")
    auxiliary = sorted(set(attributes) - {"POSITION"})
    if auxiliary and not allow_auxiliary:
        raise GeometryGLBError(
            "unsupported_geometry_aux_attribute",
            "Stage 4O does not interpolate, delete, or convert auxiliary vertex attributes",
            attributes=auxiliary,
        )
    positions_raw = _accessor(document, binary, attributes["POSITION"], "VEC3", {5126}, GEOMETRY_LIMITS["max_positions"])
    indices_raw = _accessor(document, binary, primitive.get("indices"), "SCALAR", {5121, 5123, 5125}, GEOMETRY_LIMITS["max_indices"])
    positions = [tuple(float(value) for value in row) for row in positions_raw]
    indices = [int(row[0]) for row in indices_raw]
    if len(indices) % 3 or len(indices) // 3 > GEOMETRY_LIMITS["max_triangles"]:
        raise GeometryGLBError("geometry_predecimation_face_budget", "index count is not a bounded triangle list")
    if any(index < 0 or index >= len(positions) for index in indices):
        raise GeometryGLBError("geometry_predecimation_invalid_indices", "index references a missing POSITION")
    raw_faces = [tuple(indices[offset:offset + 3]) for offset in range(0, len(indices), 3)]
    if validate_topology:
        try:
            geometry = canonical_geometry(positions, raw_faces)
            topology = validate_geometry(geometry)
        except GeometryReductionError as error:
            raise GeometryGLBError(error.code, str(error), **error.details) from error
    else:
        geometry = {"schema_version": 1, "positions": positions, "faces": raw_faces}
        topology = inspect_geometry_quality(positions, raw_faces)
    return {
        "geometry": geometry,
        "topology": topology,
        "document": document,
        "binary": binary,
        "node_path": path,
        "auxiliary_attributes": auxiliary,
    }


def pack_geometry_glb(mesh: dict[str, Any]) -> bytes:
    """Write the canonical pre-Stage-4F POSITION/index-only GLB subset."""
    canonical = canonical_geometry(mesh["positions"], mesh["faces"])
    positions = [tuple(struct.unpack("<3f", struct.pack("<3f", *point))) for point in canonical["positions"]]
    indices = [index for face in canonical["faces"] for index in face]
    binary = bytearray()
    for point in positions: binary.extend(struct.pack("<3f", *point))
    position_length = len(binary)
    while len(binary) % 4: binary.append(0)
    index_offset = len(binary)
    component, fmt = (5121, "<B") if len(positions) <= 255 else (5123, "<H")
    for index in indices: binary.extend(struct.pack(fmt, index))
    index_length = len(binary) - index_offset
    document = {
        "asset": {"generator": "pokeagent-stage4o-geometry-v1", "version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "stage4o_reduced_geometry"}],
        "meshes": [{"name": "stage4o_reduced_geometry", "primitives": [{
            "attributes": {"POSITION": 0}, "indices": 1, "mode": 4,
        }]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": position_length},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": index_length},
        ],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3",
                "min": [min(point[axis] for point in positions) for axis in range(3)],
                "max": [max(point[axis] for point in positions) for axis in range(3)],
            },
            {"bufferView": 1, "componentType": component, "count": len(indices), "type": "SCALAR"},
        ],
    }
    return pack_glb(document, bytes(binary))


def _validate_policy(policy: object) -> dict[str, Any]:
    keys = {
        "policy", "target_faces", "target_positions", "preserve_boundaries", "preserve_ground_contact",
        "require_one_component", "crease_angle_degrees", "ground_tolerance_ratio", "max_face_rotation_degrees",
        "crease_penalty", "max_bounds_delta_ratio", "max_geometric_error_ratio",
        "max_surface_area_delta_percent", "min_silhouette_iou",
    }
    if not isinstance(policy, dict) or set(policy) != keys or policy.get("policy") != "constrained_geometry_qem":
        raise GeometryGLBError("invalid_geometry_reduction_policy", "Stage 4O policy is incomplete")
    integers = {"target_faces": (4, 64), "target_positions": (4, 128)}
    for field, bounds in integers.items():
        value = policy[field]
        if isinstance(value, bool) or not isinstance(value, int) or not bounds[0] <= value <= bounds[1]:
            raise GeometryGLBError("invalid_geometry_reduction_policy", f"{field} is outside {bounds}")
    for field in ("preserve_boundaries", "preserve_ground_contact", "require_one_component"):
        if policy[field] is not True:
            raise GeometryGLBError("invalid_geometry_reduction_policy", f"{field} must be true")
    numeric = {
        "crease_angle_degrees": (1, 179), "ground_tolerance_ratio": (0, 0.01),
        "max_face_rotation_degrees": (1, 89), "crease_penalty": (0, 1),
        "max_bounds_delta_ratio": (0, 0.25), "max_geometric_error_ratio": (0, 0.25),
        "max_surface_area_delta_percent": (0, 50), "min_silhouette_iou": (0.5, 1),
    }
    for field, bounds in numeric.items():
        value = policy[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not bounds[0] < float(value) <= bounds[1]:
            raise GeometryGLBError("invalid_geometry_reduction_policy", f"{field} is outside {bounds}")
    return dict(policy)


def load_geometry_manifest(path: Path, root: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeometryGLBError("invalid_geometry_manifest", f"cannot read Stage 4O manifest: {path}") from error
    expected = {"schema_version", "id", "source", "source_format", "source_sha256", "provenance", "preprocessing"}
    if not isinstance(manifest, dict) or set(manifest) != expected or manifest.get("schema_version") != 13:
        raise GeometryGLBError("invalid_geometry_manifest", "Stage 4O manifest must use exact schema 13")
    if not isinstance(manifest.get("id"), str) or SAFE_ID.fullmatch(manifest["id"]) is None:
        raise GeometryGLBError("invalid_asset_id", "Stage 4O id must be a stable lower-snake-case symbol")
    if manifest.get("source_format") != "glb" or not isinstance(manifest.get("source_sha256"), str) or SHA256.fullmatch(manifest["source_sha256"]) is None:
        raise GeometryGLBError("invalid_geometry_manifest", "source format/hash are invalid")
    if manifest.get("provenance") != {"kind": "project_authored", "license": "CC0-1.0"}:
        raise GeometryGLBError("invalid_geometry_manifest", "canonical Stage 4O fixture must be project-authored CC0")
    preprocessing = manifest.get("preprocessing")
    if not isinstance(preprocessing, dict) or set(preprocessing) != {"geometry_reduction"}:
        raise GeometryGLBError("invalid_geometry_manifest", "manifest requires only geometry_reduction preprocessing")
    manifest["preprocessing"]["geometry_reduction"] = _validate_policy(preprocessing["geometry_reduction"])
    relative = Path(manifest["source"]) if isinstance(manifest.get("source"), str) else Path("/")
    if relative.is_absolute() or ".." in relative.parts:
        raise GeometryGLBError("unsafe_path", "Stage 4O source path must be repository-relative")
    source = (root / relative).resolve(); required = (root / "assets/source").resolve()
    try: source.relative_to(required)
    except ValueError as error: raise GeometryGLBError("unsafe_path", "Stage 4O source must be below assets/source") from error
    if not source.is_file(): raise GeometryGLBError("missing_source", f"Stage 4O source does not exist: {source}")
    data = source.read_bytes()
    if _sha256(data) != manifest["source_sha256"]:
        raise GeometryGLBError("source_hash_mismatch", "Stage 4O source differs from its tracked hash")
    manifest["_source_path"] = source
    return manifest


def reduce_geometry_manifest(path: Path, root: Path) -> dict[str, Any]:
    manifest = load_geometry_manifest(path, root)
    data = manifest["_source_path"].read_bytes()
    parsed = parse_geometry_glb(data)
    try:
        reduced, reduction = reduce_geometry(parsed["geometry"], manifest["preprocessing"]["geometry_reduction"])
    except GeometryReductionError as error:
        raise GeometryGLBError(error.code, str(error), **error.details) from error
    canonical = pack_geometry_glb(reduced)
    reopened = parse_geometry_glb(canonical)
    if reopened["geometry"] != canonical_geometry(reduced["positions"], reduced["faces"]):
        raise GeometryGLBError("geometry_predecimation_canonical_mismatch", "independent parser disagrees with canonical output")
    final = reopened["topology"]
    if final["triangles"] > BOOTSTRAP_ENVELOPE["max_faces"] or final["positions"] > BOOTSTRAP_ENVELOPE["max_positions"] or final["triangles"] * 3 > BOOTSTRAP_ENVELOPE["max_accessor_elements"]:
        raise GeometryGLBError("geometry_predecimation_envelope_mismatch", "output exceeds downstream bootstrap limits")
    report = {
        "schema_version": 1,
        "success": True,
        "asset_id": manifest["id"],
        "source": manifest["source"],
        "source_sha256": _sha256(data),
        "source_size_bytes": len(data),
        "canonical_sha256": _sha256(canonical),
        "canonical_size_bytes": len(canonical),
        "source_contract": "POSITION_plus_indices_only",
        "canonical_contract": "POSITION_plus_indices_only_pre_stage4f",
        "source_limits": dict(GEOMETRY_LIMITS),
        "bootstrap_envelope": dict(BOOTSTRAP_ENVELOPE),
        "source_node_path": parsed["node_path"],
        "source_auxiliary_attributes": parsed["auxiliary_attributes"],
        "reduction": reduction,
        "canonical_topology": final,
        "stage4f_expected_acceptance": False,
        "stage4f_expected_reasons": ["unsupported_material", "missing_NORMAL", "missing_TEXCOORD_0"],
    }
    semantic = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = _sha256(semantic)
    return {"manifest": manifest, "source": parsed, "geometry": reduced, "canonical_glb": canonical, "report": report}


def write_geometry_outputs(path: Path, output: Path, root: Path) -> dict[str, Any]:
    result = reduce_geometry_manifest(path, root)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "canonical_glb": output / "reduced-geometry.glb",
        "geometry_ir": output / "geometry-only-ir.json",
        "report": output / "geometry-predecimation-report.json",
        "collapse_plan": output / "geometry-collapse-plan.json",
    }
    files["canonical_glb"].write_bytes(result["canonical_glb"])
    files["geometry_ir"].write_text(json.dumps(result["geometry"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["report"].write_text(json.dumps(result["report"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["collapse_plan"].write_text(json.dumps(result["report"]["reduction"]["collapse_plan"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Keep command output compact. The complete deterministic plan remains in
    # its dedicated artifact and in the machine report; emitting hundreds of
    # collapse records on every CLI run obscures the useful proof summary.
    summary = dict(result["report"])
    summary["reduction"] = {
        key: value for key, value in result["report"]["reduction"].items()
        if key != "collapse_plan"
    }
    return {**summary, "outputs": {name: str(file) for name, file in files.items()}}


def inspect_geometry_applicability(data: bytes) -> dict[str, Any]:
    """Read-only geometry/topology projection; never emits a derived source."""
    raw_hash = _sha256(data)
    try:
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
    except GeometryGLBError as error:
        return {"topology_applicable": False, "transformation_applicable": False, "error": error.as_dict(), "raw_source_sha256": raw_hash}
    auxiliary = parsed["auxiliary_attributes"]
    topology = parsed["topology"]
    fits = topology["positions"] <= GEOMETRY_LIMITS["max_positions"] and topology["triangles"] <= GEOMETRY_LIMITS["max_triangles"]
    topology_valid = bool(topology["valid_for_predecimation"])
    return {
        "topology_applicable": topology_valid,
        "transformation_applicable": fits and topology_valid and not auxiliary,
        "applicable_if_aux_attributes_resolved": fits and topology_valid,
        "auxiliary_attribute_blockers": auxiliary,
        "node_path": parsed["node_path"],
        "topology": topology,
        "source_envelope_fit": fits,
        "raw_source_sha256": raw_hash,
        "raw_source_unchanged": True,
        "error": (
            {
                "code": "geometry_predecimation_invalid_topology",
                "message": "raw geometry fails the non-repair topology contract",
                "details": {"quality": topology},
            }
            if not topology_valid else None
        ) or (
            {
                "code": "unsupported_geometry_aux_attribute",
                "message": "auxiliary attributes require a separate explicit decision",
                "details": {"attributes": auxiliary},
            }
            if auxiliary else None
        ),
    }
