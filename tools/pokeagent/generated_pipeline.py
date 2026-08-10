"""Stage 4S kill-gated orchestration for the immutable real TripoSR asset.

This module sequences the already-proven Stage 4P/Q/R/O boundaries.  It owns
hash/provenance verification and fail-closed reporting, but no mesh algorithm.
Later F/J/I/world stages are reached only when every earlier gate succeeds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw

from .glb import GLBError, _chunks
from .glb_bootstrap import BootstrapError, _color0_payload, bootstrap_geometry_glb
from .glb_geometry_reduce import GEOMETRY_LIMITS, GeometryGLBError, _validate_policy, pack_geometry_glb, parse_geometry_glb
from .glb_topology import TopologyGLBError, validate_topology_policy
from .mesh_predecimate import (
    GeometryReductionError, _allocate_component_budget, _component_meshes,
    _projection, canonical_geometry, reduce_geometry_components,
)
from .mesh_sanitize import MeshSanitizeError, _topology, analyze_topology, sanitize_mesh
from .mesh_tinyface import TinyFaceError, remove_target_null_faces, validate_tinyface_policy


PIPELINE_SCHEMA = 16
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
STAGE4H_SHA256 = "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60"
_DIRECTIONS = ("front", "rear", "left", "right", "three_quarter")


class GeneratedPipelineError(ValueError):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_hashed_path(
    root: Path, relative: object, expected: object, *, prefix: Path,
    mismatch_code: str = "source_provenance_mismatch",
) -> tuple[Path, bytes]:
    if not isinstance(relative, str) or not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
        raise GeneratedPipelineError("generated_pipeline_invalid_hash_path", "tracked path/hash declaration is invalid")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise GeneratedPipelineError("generated_pipeline_unsafe_path", "tracked inputs must be repository-relative")
    resolved = (root / path).resolve(); required = (root / prefix).resolve()
    try: resolved.relative_to(required)
    except ValueError as error:
        raise GeneratedPipelineError("generated_pipeline_unsafe_path", f"input must remain below {prefix}") from error
    if not resolved.is_file():
        raise GeneratedPipelineError("generated_pipeline_missing_input", f"missing tracked input: {path}")
    data = resolved.read_bytes()
    if _sha(data) != expected:
        raise GeneratedPipelineError(mismatch_code, f"hash mismatch for immutable input: {path}")
    return resolved, data


def _bootstrap_policy_is_proven(policy: object) -> bool:
    return policy == {
        "policy": "hard_surface_static_v1", "material_name": "generated_surface", "color0_policy": "reject",
        "patch_normal_degrees": 0.1, "plane_epsilon": 0.00001, "texture_size": 32,
        "padding_texels": 1, "crease_angle_degrees": 60, "normal_weighting": "area",
    }


def load_generated_pipeline_manifest(path: Path, root: Path) -> tuple[dict[str, Any], bytes]:
    try: manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", f"cannot read Stage 4S manifest: {path}") from error
    expected = {
        "schema_version", "id", "source", "source_sha256", "concept", "provenance", "intended_size_tiles",
        "appearance", "topology", "tiny_faces", "geometry_reduction", "bootstrap", "final_decimation", "model", "collision",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected or manifest.get("schema_version") != PIPELINE_SCHEMA:
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "Stage 4S manifest must use exact schema 16")
    if not isinstance(manifest.get("id"), str) or SAFE_ID.fullmatch(manifest["id"]) is None:
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "asset id is invalid")
    source_path, source = _load_hashed_path(
        root, manifest["source"], manifest["source_sha256"], prefix=Path("assets/source"),
        mismatch_code="SOURCE_PROVENANCE_MISMATCH",
    )
    if manifest["source_sha256"] != STAGE4H_SHA256:
        raise GeneratedPipelineError("SOURCE_PROVENANCE_MISMATCH", "Stage 4S accepts only the immutable Stage 4H source")
    for field, prefix in (("concept", Path("assets/concepts")), ("provenance", Path("assets/provenance"))):
        value = manifest[field]
        if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
            raise GeneratedPipelineError("generated_pipeline_invalid_manifest", f"{field} declaration is invalid")
        _load_hashed_path(root, value["path"], value["sha256"], prefix=prefix)
    provenance_document = json.loads((root / manifest["provenance"]["path"]).read_text(encoding="utf-8"))
    if provenance_document.get("raw_output_sha256") != STAGE4H_SHA256 or provenance_document.get("generator_model") != "stabilityai/TripoSR":
        raise GeneratedPipelineError("SOURCE_PROVENANCE_MISMATCH", "tracked provenance no longer identifies the immutable TripoSR source")
    size = manifest["intended_size_tiles"]
    if not isinstance(size, list) or len(size) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0 for v in size):
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "intended size must contain three positive values")
    appearance = manifest["appearance"]
    if appearance != {
        "color0_policy": "explicit_discard", "source_material": "generated_surface",
        "project_material_alias": "prop_secondary", "project_texture": "stage4d_stone",
    } and not (
        isinstance(appearance, dict) and set(appearance) == {"color0_policy", "source_material", "project_material_alias", "project_texture"}
        and appearance.get("color0_policy") == "explicit_discard" and appearance.get("source_material") == "generated_surface"
        and appearance.get("project_material_alias") == "prop_secondary" and appearance.get("project_texture") in {"stage4d_stone", "stage4d_wood"}
    ):
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "appearance policy is outside proven project bindings")
    try:
        manifest["topology"] = validate_topology_policy(manifest["topology"])
        manifest["geometry_reduction"] = _validate_policy(manifest["geometry_reduction"])
    except (TopologyGLBError, GeometryGLBError) as error:
        raise GeneratedPipelineError(error.code, str(error), **error.details) from error
    if manifest["tiny_faces"].get("normalization") != "fit_intended_size":
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "tiny-face normalization must use intended size")
    if not _bootstrap_policy_is_proven(manifest["bootstrap"]):
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "bootstrap differs from Stage 4P")
    expected_final = {
        "policy": "constrained_deterministic_qem", "target": "fit_project_geometry",
        "max_geometric_error": 0.25, "max_bounds_delta": 0.25,
        "max_surface_area_delta_percent": 12.0, "min_silhouette_iou": 0.9,
        "max_normal_deviation_degrees": 50.0, "max_uv_distortion_percent": 70.0,
        "hard_normal_degrees": 80.0, "preserve_boundaries": True,
        "preserve_uv_seams": True, "preserve_material_boundaries": True,
        "preserve_hard_normals": True,
    }
    if manifest["final_decimation"] != expected_final:
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "final decimation differs from Stage 4J")
    if manifest["model"] != {"policy": "project_relocated_display_list", "max_bytes": 4096}:
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "Stage 4I capacity must remain 4096")
    if manifest["collision"] != {"policy": "footprint_rect", "rectangle": {"min_x": -2.0, "max_x": 2.0, "min_z": -2.0, "max_z": 2.0}}:
        raise GeneratedPipelineError("generated_pipeline_invalid_manifest", "Stage 4S collision policy must remain the declared rectangle")
    manifest["_source_path"] = str(source_path)
    return manifest, source


def _stage4q_exact_or_noop(geometry: dict[str, Any], policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    analysis = analyze_topology(geometry["positions"], geometry["faces"])
    if analysis["exact_zero_area_faces"]:
        try:
            mesh, report = sanitize_mesh(
                geometry["positions"], geometry["faces"], remove_exact_zero_area_faces=True,
                max_components=policy["max_components"],
            )
        except MeshSanitizeError as error:
            raise GeneratedPipelineError(error.code, str(error), **error.details) from error
        return mesh, report
    error = analysis.get("error") or {}
    if error.get("code") != "topology_sanitize_no_exact_zero_area" or analysis.get("full_topology") is None:
        raise GeneratedPipelineError("generated_pipeline_stage4q_failed", "Stage 4Q could not validate the source", analysis=analysis)
    if analysis["full_topology"]["connected_components"] > policy["max_components"]:
        raise GeneratedPipelineError("topology_sanitize_component_limit", "component count exceeds Stage 4Q")
    mesh = {"schema_version": 1, "positions": list(geometry["positions"]), "faces": list(geometry["faces"])}
    report = {
        "schema_version": 1, "success": True, "algorithm": "generated_static_exact_sanitize_v1",
        "zero_area_definition": "float32_decoded_cross_squared_exactly_zero", "no_op": True,
        "source_positions": len(mesh["positions"]), "source_triangles": len(mesh["faces"]),
        "final_positions": len(mesh["positions"]), "final_triangles": len(mesh["faces"]),
        "removed_face_count": 0, "removed_faces": [],
        "near_zero_nonzero_faces_preserved": analysis["near_zero_nonzero_faces"],
        "topology": analysis["full_topology"], "positions_moved": False, "winding_changed": False,
        "faces_retriangulated": False, "vertices_welded": False, "components_merged_or_deleted": False,
    }
    return mesh, report


def _actual_tiny_policy(manifest: dict[str, Any], positions: list[tuple[float, float, float]]) -> dict[str, Any]:
    size = [float(v) for v in manifest["intended_size_tiles"]]
    minimum = [min(point[axis] for point in positions) for axis in range(3)]
    maximum = [max(point[axis] for point in positions) for axis in range(3)]
    dimensions = [maximum[axis] - minimum[axis] for axis in range(3)]
    scale = min(size[axis] / dimensions[axis] for axis in range(3))
    declared = dict(manifest["tiny_faces"])
    declared["normalization"] = {"units_to_tiles": scale, "anchor": "footprint_center_base"}
    try: return validate_tinyface_policy(declared)
    except TinyFaceError as error: raise GeneratedPipelineError(error.code, str(error), **error.details) from error


def _component_plan(mesh: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    canonical = canonical_geometry(mesh["positions"], mesh["faces"])
    components = _component_meshes(canonical)
    face_targets = _allocate_component_budget(components, int(policy["target_faces"]), "faces", minimum=16)
    position_targets = _allocate_component_budget(components, int(policy["target_positions"]), "positions", minimum=10)
    return [{
        "component_id": component["component_id"], "source_faces": len(component["faces"]),
        "source_positions": len(component["positions"]), "source_area": component["surface_area"],
        "target_faces": face_target, "target_positions": position_target,
    } for component, face_target, position_target in zip(components, face_targets, position_targets, strict=True)]


def run_generated_pipeline_manifest(path: Path, root: Path) -> dict[str, Any]:
    manifest, source = load_generated_pipeline_manifest(path, root)
    try:
        document, binary = _chunks(source, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(source, allow_auxiliary=True, validate_topology=False)
        color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"])
    except (GLBError, GeometryGLBError, BootstrapError) as error:
        raise GeneratedPipelineError(error.code, str(error), **getattr(error, "details", {})) from error
    if parsed["auxiliary_attributes"] != ["COLOR_0"]:
        raise GeneratedPipelineError("generated_pipeline_color0_contract", "raw source must contain only POSITION and discardable COLOR_0")
    exact, q_report = _stage4q_exact_or_noop(parsed["geometry"], manifest["topology"])
    tiny_policy = _actual_tiny_policy(manifest, exact["positions"])
    try: filtered, r_report = remove_target_null_faces(exact["positions"], exact["faces"], tiny_policy)
    except TinyFaceError as error: raise GeneratedPipelineError(error.code, str(error), phase="stage4r", **error.details) from error
    post_qr = pack_geometry_glb(filtered)
    plan = _component_plan(filtered, manifest["geometry_reduction"])
    report: dict[str, Any] = {
        "schema_version": 1, "success": False, "asset_id": manifest["id"],
        "authorization": "stage4s_real_candidate_derived_copy_only",
        "raw": {
            "path": manifest["source"], "sha256": _sha(source), "size_bytes": len(source),
            "positions": len(parsed["geometry"]["positions"]), "triangles": len(parsed["geometry"]["faces"]),
            "topology": _topology(parsed["geometry"]["positions"], parsed["geometry"]["faces"]),
            "immutable": True,
        },
        "provenance": {"concept": manifest["concept"], "generator": manifest["provenance"]},
        "appearance": manifest["appearance"],
        "color0": {"policy": "explicit_discard", "discarded": True, "evidence": color},
        "stage4q": q_report, "stage4r": r_report,
        "post_qr_sha256": _sha(post_qr), "post_qr_size_bytes": len(post_qr),
        "stage4o": {"policy": manifest["geometry_reduction"], "component_plan": plan},
        "stage4p": {"attempted": False, "reason": "blocked_by_stage4o"},
        "stage4f": {"attempted": False, "reason": "blocked_by_stage4o"},
        "stage4j": {"attempted": False, "reason": "blocked_by_stage4o"},
        "stage4i": {"attempted": False, "max_bytes": 4096, "reason": "blocked_by_stage4o"},
        "rom": {"attempted": False, "reason": "blocked_by_stage4o"},
        "qa": {"attempted": False, "reason": "blocked_by_stage4o"},
        "collision": manifest["collision"],
        "historical_stage4h": {
            "raw_sha256": STAGE4H_SHA256, "unchanged": True,
            "verdict": ["STAGE_4H_GENERATED_ASSET_REJECTED", "REJECTED_UNSUPPORTED_STRUCTURE"],
        },
    }
    try:
        reduced, reduction = reduce_geometry_components(filtered, manifest["geometry_reduction"], max_components=manifest["topology"]["max_components"])
    except GeometryReductionError as error:
        failure_details = dict(error.details)
        blocking_plan = next(
            (item for item in plan if item["target_faces"] == failure_details.get("target_faces") and item["target_positions"] == failure_details.get("target_positions")),
            None,
        )
        if blocking_plan is not None and isinstance(failure_details.get("best_valid_positions"), int):
            failure_details["blocking_component_id"] = blocking_plan["component_id"]
            failure_details["accepted_collapses_before_stall"] = blocking_plan["source_positions"] - failure_details["best_valid_positions"]
        enriched_error = {"code": error.code, "message": str(error), "details": failure_details}
        report["failure"] = {"phase": "stage4o", **error.as_dict()}
        report["failure"]["details"] = failure_details
        report["stage4o"].update({"success": False, "error": enriched_error})
        report["operation_order_completed"] = ["raw_hash", "color0_discard", "stage4q", "stage4r", "stage4o_rejected"]
        report["report_sha256"] = _sha(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
        return {"report": report, "post_qr_glb": post_qr, "reduced_glb": None, "canonical_glb": None}
    reduced_glb = pack_geometry_glb(reduced)
    try: bootstrap = bootstrap_geometry_glb(reduced_glb, manifest["bootstrap"], max_components=manifest["topology"]["max_components"])
    except BootstrapError as error: raise GeneratedPipelineError(error.code, str(error), phase=error.phase, **error.details) from error
    report["stage4o"].update({"success": True, "report": reduction})
    report["stage4p"] = bootstrap["report"]
    report["stage4f"] = {"attempted": True, "accepted": True}
    report["failure"] = {"phase": "stage4s_unimplemented_after_unexpected_stage4o_pass", "code": "kill_gate_scope_guard", "message": "Stage 4S orchestration must be extended only after observed evidence"}
    report["report_sha256"] = _sha(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
    return {"report": report, "post_qr_glb": post_qr, "reduced_glb": reduced_glb, "canonical_glb": bootstrap["canonical_glb"]}


def _write_wireframe_views(mesh: dict[str, Any], output: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True); hashes = {}
    for direction in _DIRECTIONS:
        projected = [_projection(point, direction) for point in mesh["positions"]]
        minimum = [min(point[axis] for point in projected) for axis in range(2)]
        maximum = [max(point[axis] for point in projected) for axis in range(2)]
        span = max(maximum[0] - minimum[0], maximum[1] - minimum[1], 1e-12)
        def pixel(index: int) -> tuple[int, int]:
            point = projected[index]
            return (int(round(16 + (point[0] - minimum[0]) / span * 479)), int(round(495 - (point[1] - minimum[1]) / span * 479)))
        image = Image.new("RGB", (512, 512), "white"); draw = ImageDraw.Draw(image)
        edges = sorted({tuple(sorted((a, b))) for face in mesh["faces"] for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))})
        for a, b in edges: draw.line((pixel(a), pixel(b)), fill=(32, 32, 32), width=1)
        path = output / f"post-qr-{direction}.png"; image.save(path, format="PNG", optimize=False)
        hashes[path.name] = _sha(path.read_bytes())
    return hashes


def write_generated_pipeline_outputs(path: Path, output: Path, root: Path) -> dict[str, Any]:
    result = run_generated_pipeline_manifest(path, root)
    output.mkdir(parents=True, exist_ok=True)
    post_path = output / "derived-post-qr.glb"; post_path.write_bytes(result["post_qr_glb"])
    parsed = parse_geometry_glb(result["post_qr_glb"])
    view_hashes = _write_wireframe_views(parsed["geometry"], output / "views")
    report = dict(result["report"])
    report["outputs"] = {
        "post_qr_glb": "derived-post-qr.glb", "report": "stage4s-report.json",
        "post_qr_views": {name: f"views/{name}" for name in sorted(view_hashes)},
        "view_sha256": dict(sorted(view_hashes.items())),
        "reduced_glb": None, "canonical_glb": None, "model": None, "rom": None, "screenshots": [],
    }
    report_path = output / "stage4s-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
