"""Stage 4R GLB orchestration for target-representation-null tiny faces."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .glb import GLBError, _chunks
from .glb_bootstrap import BootstrapError, _color0_payload, bootstrap_geometry_glb
from .glb_geometry_reduce import (
    BOOTSTRAP_ENVELOPE,
    GEOMETRY_LIMITS,
    GeometryGLBError,
    _validate_policy,
    pack_geometry_glb,
    parse_geometry_glb,
)
from .glb_topology import TopologyGLBError, validate_topology_policy
from .mesh_predecimate import (
    GeometryReductionError,
    canonical_geometry,
    reduce_geometry_components,
    validate_geometry,
)
from .mesh_sanitize import MeshSanitizeError, _cross_squared, sanitize_mesh
from .mesh_tinyface import (
    TinyFaceError,
    _face_components,
    classify_target_faces,
    remove_target_null_faces,
    validate_tinyface_policy,
)


SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
STAGE4H_SHA256 = "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60"


class TinyFaceGLBError(ValueError):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _exact_stage4q_in_memory(data: bytes, policy: dict[str, Any]) -> dict[str, Any]:
    """Apply the proven Stage 4Q core without asking Stage 4O to pack a tiny face."""
    policy = validate_topology_policy(policy)
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
    except (GLBError, GeometryGLBError) as error:
        raise TinyFaceGLBError(error.code, str(error), **getattr(error, "details", {})) from error
    auxiliary = parsed["auxiliary_attributes"]
    if auxiliary not in ([], ["COLOR_0"]):
        raise TinyFaceGLBError(
            "unsupported_tinyface_aux_attribute", "Stage 4R accepts no auxiliary attribute except COLOR_0",
            attributes=auxiliary,
        )
    color = None
    if auxiliary == ["COLOR_0"]:
        if policy["color0_policy"] != "explicit_discard":
            raise TinyFaceGLBError("tinyface_color0_policy_required", "COLOR_0 requires the proven explicit discard")
        try:
            color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"])
        except BootstrapError as error:
            raise TinyFaceGLBError(error.code, str(error), **error.details) from error
    elif policy["color0_policy"] == "explicit_discard":
        raise TinyFaceGLBError("tinyface_color0_absent", "explicit COLOR_0 discard requested but absent")
    geometry = parsed["geometry"]
    try:
        sanitized, report = sanitize_mesh(
            geometry["positions"], geometry["faces"],
            remove_exact_zero_area_faces=True,
            max_components=policy["max_components"],
        )
    except MeshSanitizeError as error:
        raise TinyFaceGLBError(error.code, str(error), **error.details) from error
    return {
        "geometry": sanitized,
        "report": {
            "stage": "Stage 4Q exact core",
            "canonical_glb_deferred_until_stage4r": True,
            "reason": "the unchanged Stage 4O writer correctly rejects the surviving nonzero tiny face",
            "color0": {"discarded": color is not None, "evidence": color},
            "sanitation": report,
        },
    }


def run_tinyface_pipeline(
    data: bytes,
    *,
    topology_policy: dict[str, Any],
    tinyface_policy: dict[str, Any],
    reduction_policy: dict[str, Any],
    bootstrap_policy: dict[str, Any],
) -> dict[str, Any]:
    """Compose Q -> R -> O -> P -> unchanged F for a controlled source."""
    exact = _exact_stage4q_in_memory(data, topology_policy)
    try:
        filtered, tiny_report = remove_target_null_faces(
            exact["geometry"]["positions"], exact["geometry"]["faces"], tinyface_policy,
        )
        reduced, reduction = reduce_geometry_components(
            filtered, reduction_policy, max_components=topology_policy["max_components"],
        )
    except (TinyFaceError, GeometryReductionError) as error:
        raise TinyFaceGLBError(error.code, str(error), **error.details) from error
    target_filtered_glb = pack_geometry_glb(filtered)
    reduced_glb = pack_geometry_glb(reduced)
    try:
        bootstrapped = bootstrap_geometry_glb(
            reduced_glb, bootstrap_policy, max_components=topology_policy["max_components"],
        )
    except BootstrapError as error:
        raise TinyFaceGLBError(error.code, str(error), phase=error.phase, **error.details) from error
    report = {
        "schema_version": 1,
        "success": True,
        "operation_order": [
            "stage4p_explicit_color0_discard", "stage4q_exact_zero_sanitation",
            "stage4r_target_null_classification", "stage4r_topology_safe_removal",
            "stage4o_multicomponent_predecimation", "stage4p_attribute_bootstrap",
            "unchanged_stage4f_validation",
        ],
        "source_sha256": _sha(data),
        "stage4q": exact["report"],
        "stage4r": tiny_report,
        "target_filtered_sha256": _sha(target_filtered_glb),
        "stage4o": reduction,
        "reduced_geometry_sha256": _sha(reduced_glb),
        "stage4p": bootstrapped["report"],
        "canonical_sha256": _sha(bootstrapped["canonical_glb"]),
        "stage4f_accepted": True,
    }
    report["report_sha256"] = _sha(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
    return {
        "target_filtered_glb": target_filtered_glb,
        "reduced_glb": reduced_glb,
        "canonical_glb": bootstrapped["canonical_glb"],
        "canonical_mesh": bootstrapped["canonical_mesh"],
        "geometry": reduced,
        "report": report,
    }


def load_tinyface_manifest(path: Path, root: Path) -> tuple[dict[str, Any], bytes]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TinyFaceGLBError("invalid_tinyface_manifest", f"cannot read Stage 4R manifest: {path}") from error
    expected = {"schema_version", "id", "source", "source_format", "source_sha256", "provenance", "preprocessing"}
    if not isinstance(manifest, dict) or set(manifest) != expected or manifest.get("schema_version") != 15:
        raise TinyFaceGLBError("invalid_tinyface_manifest", "Stage 4R manifest must use exact schema 15")
    if not isinstance(manifest.get("id"), str) or SAFE_ID.fullmatch(manifest["id"]) is None:
        raise TinyFaceGLBError("invalid_tinyface_manifest", "Stage 4R id is invalid")
    if manifest.get("source_format") != "glb" or not isinstance(manifest.get("source_sha256"), str) or SHA256.fullmatch(manifest["source_sha256"]) is None:
        raise TinyFaceGLBError("invalid_tinyface_manifest", "source format/hash is invalid")
    if manifest.get("provenance") != {"kind": "project_authored", "license": "CC0-1.0"}:
        raise TinyFaceGLBError("invalid_tinyface_manifest", "Stage 4R proof source must be project-authored CC0")
    preprocessing = manifest.get("preprocessing")
    if not isinstance(preprocessing, dict) or set(preprocessing) != {"topology", "tiny_faces", "geometry_reduction", "bootstrap"}:
        raise TinyFaceGLBError("invalid_tinyface_manifest", "Stage 4R requires Q/R/O/P policies")
    try:
        preprocessing["topology"] = validate_topology_policy(preprocessing["topology"])
        preprocessing["tiny_faces"] = validate_tinyface_policy(preprocessing["tiny_faces"])
        preprocessing["geometry_reduction"] = _validate_policy(preprocessing["geometry_reduction"])
    except (TopologyGLBError, TinyFaceError, GeometryGLBError) as error:
        raise TinyFaceGLBError(error.code, str(error), **getattr(error, "details", {})) from error
    expected_bootstrap = {
        "policy": "hard_surface_static_v1", "material_name": "generated_surface", "color0_policy": "reject",
        "patch_normal_degrees": 0.1, "plane_epsilon": 0.00001, "texture_size": 32,
        "padding_texels": 1, "crease_angle_degrees": 60, "normal_weighting": "area",
    }
    if preprocessing["bootstrap"] != expected_bootstrap:
        raise TinyFaceGLBError("invalid_tinyface_manifest", "bootstrap policy differs from proven Stage 4P semantics")
    relative = Path(manifest["source"]) if isinstance(manifest.get("source"), str) else Path("/")
    if relative.is_absolute() or ".." in relative.parts:
        raise TinyFaceGLBError("unsafe_path", "Stage 4R source path must be repository-relative")
    source = (root / relative).resolve(); required = (root / "assets/source").resolve()
    try: source.relative_to(required)
    except ValueError as error: raise TinyFaceGLBError("unsafe_path", "Stage 4R source must be below assets/source") from error
    if not source.is_file(): raise TinyFaceGLBError("missing_source", f"Stage 4R source does not exist: {source}")
    data = source.read_bytes()
    if _sha(data) != manifest["source_sha256"]:
        raise TinyFaceGLBError("source_hash_mismatch", "Stage 4R source differs from its tracked hash")
    manifest["_source_path"] = str(source)
    return manifest, data


def run_tinyface_manifest(path: Path, root: Path) -> dict[str, Any]:
    manifest, data = load_tinyface_manifest(path, root)
    result = run_tinyface_pipeline(
        data,
        topology_policy=manifest["preprocessing"]["topology"],
        tinyface_policy=manifest["preprocessing"]["tiny_faces"],
        reduction_policy=manifest["preprocessing"]["geometry_reduction"],
        bootstrap_policy=manifest["preprocessing"]["bootstrap"],
    )
    final = result["report"]["stage4o"]["final"]
    if final["triangles"] > BOOTSTRAP_ENVELOPE["max_faces"] or final["positions"] > BOOTSTRAP_ENVELOPE["max_positions"]:
        raise TinyFaceGLBError("tinyface_pipeline_envelope_mismatch", "Stage 4O output exceeds Stage 4P")
    result["report"]["asset_id"] = manifest["id"]
    result["report"]["source"] = manifest["source"]
    return {**result, "manifest": manifest}


def write_tinyface_outputs(path: Path, output: Path, root: Path) -> dict[str, Any]:
    result = run_tinyface_manifest(path, root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "target-null-sanitized.glb").write_bytes(result["target_filtered_glb"])
    (output / "reduced-geometry.glb").write_bytes(result["reduced_glb"])
    (output / "bootstrapped.glb").write_bytes(result["canonical_glb"])
    report = dict(result["report"])
    report["outputs"] = {
        "target_filtered": "target-null-sanitized.glb",
        "reduced": "reduced-geometry.glb",
        "bootstrapped": "bootstrapped.glb",
        "report": "tiny-face-report.json",
    }
    (output / "tiny-face-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def inspect_stage4h_tiny_face(data: bytes, target_size_tiles: tuple[float, float, float]) -> dict[str, Any]:
    """Read-only Stage 4H representation and hypothetical topology analysis."""
    raw_hash = _sha(data)
    if raw_hash != STAGE4H_SHA256:
        raise TinyFaceGLBError("stage4h_hash_mismatch", "immutable Stage 4H source hash changed")
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
        color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"])
    except (GLBError, GeometryGLBError, BootstrapError) as error:
        raise TinyFaceGLBError(error.code, str(error), **getattr(error, "details", {})) from error
    geometry = parsed["geometry"]
    minimum = [min(point[axis] for point in geometry["positions"]) for axis in range(3)]
    maximum = [max(point[axis] for point in geometry["positions"]) for axis in range(3)]
    dimensions = [maximum[axis] - minimum[axis] for axis in range(3)]
    scale = min(target_size_tiles[axis] / dimensions[axis] for axis in range(3))
    policy = {
        "policy": "target_quantized_degenerate_v1",
        "candidate_scope": "stage4o_normal_rejected_only",
        "coordinate_system": {"up_axis": "+y", "forward_axis": "+z", "handedness": "right"},
        "normalization": {"units_to_tiles": scale, "anchor": "footprint_center_base"},
        "placement": {"x": 16, "z": 16, "rotation": 0},
        "preserve_components": True,
        "require_valid_boundaries": True,
    }
    classification = classify_target_faces(geometry["positions"], geometry["faces"], policy)
    candidates = [item for item in classification["faces"] if item["classification"] == "TARGET_QUANTIZED_DEGENERATE"]
    try:
        hypothetical, removal = remove_target_null_faces(geometry["positions"], geometry["faces"], policy)
        stage4o_mesh = canonical_geometry(hypothetical["positions"], hypothetical["faces"])
        stage4o_topology = validate_geometry(stage4o_mesh)
        applicable = True; error = None
    except (TinyFaceError, GeometryReductionError) as caught:
        hypothetical = None; removal = None; stage4o_topology = None
        applicable = False; error = {"code": caught.code, "message": str(caught), "details": caught.details}
    face_components = _face_components(geometry["faces"])
    component_areas = []
    for component in face_components:
        area = sum(
            math.sqrt(_cross_squared(*(geometry["positions"][index] for index in geometry["faces"][face_id]))) / 2
            for face_id in component
        )
        component_areas.append((component, area))
    total_area = sum(area for _component, area in component_areas)
    for candidate in candidates:
        source_index = int(candidate["source_face_index"])
        component_area = next(area for component, area in component_areas if source_index in component)
        candidate["source_area_ratio_total"] = candidate["source_area"] / total_area
        candidate["source_area_ratio_component"] = candidate["source_area"] / component_area
        owners = []
        face = geometry["faces"][source_index]
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = {a, b}
            owners.append(sum(edge <= set(other) for other in geometry["faces"]))
        candidate["edge_incident_face_counts"] = owners
        candidate["boundary_participation"] = any(count == 1 for count in owners)
    return {
        "raw_source_sha256": raw_hash,
        "raw_source_unchanged": True,
        "derived_candidate_created": False,
        "target_size_tiles": list(target_size_tiles),
        "fit_inside_target_units_to_tiles": scale,
        "source_bounds": {"min": minimum, "max": maximum},
        "source_dimensions": dimensions,
        "source_positions": len(geometry["positions"]),
        "source_triangles": len(geometry["faces"]),
        "auxiliary_attributes": parsed["auxiliary_attributes"],
        "color0_discard_applicable": parsed["auxiliary_attributes"] == ["COLOR_0"],
        "color0": color,
        "target_classification_counts": classification["classification_counts"],
        "stage4o_blocking_target_null_faces": candidates,
        "tinyface_policy_applicable": applicable and len(candidates) == 1,
        "hypothetical_removal": removal,
        "stage4o_structurally_applicable_after_hypothetical_removal": applicable,
        "hypothetical_stage4o_topology": stage4o_topology,
        "stage4p_applicable_after_bounded_reduction": applicable,
        "error": error,
        "historical_verdict": ["STAGE_4H_GENERATED_ASSET_REJECTED", "REJECTED_UNSUPPORTED_STRUCTURE"],
    }
