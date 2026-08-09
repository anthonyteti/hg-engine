"""Bounded GLB adapter for Stage 4Q exact topology sanitation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .glb import GLBError, _chunks
from .glb_bootstrap import BootstrapError, _color0_payload
from .glb_geometry_reduce import (
    BOOTSTRAP_ENVELOPE, GEOMETRY_LIMITS, GeometryGLBError, _validate_policy,
    pack_geometry_glb, parse_geometry_glb,
)
from .mesh_sanitize import MAX_COMPONENTS, MeshSanitizeError, analyze_topology, sanitize_mesh
from .mesh_predecimate import GeometryReductionError, reduce_geometry_components
from .glb_bootstrap import bootstrap_geometry_glb


TOPOLOGY_POLICY = "generated_static_exact_sanitize_v1"
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TopologyGLBError(ValueError):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_topology_policy(policy: object) -> dict[str, Any]:
    expected = {
        "policy", "remove_exact_zero_area_faces", "preserve_components",
        "preserve_boundary_loops", "max_components", "color0_policy",
    }
    if not isinstance(policy, dict) or set(policy) != expected or policy.get("policy") != TOPOLOGY_POLICY:
        raise TopologyGLBError("invalid_topology_sanitize_policy", "Stage 4Q topology policy is incomplete")
    if any(policy.get(field) is not True for field in (
        "remove_exact_zero_area_faces", "preserve_components", "preserve_boundary_loops",
    )):
        raise TopologyGLBError("invalid_topology_sanitize_policy", "all preservation flags must be true")
    maximum = policy.get("max_components")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= MAX_COMPONENTS:
        raise TopologyGLBError("invalid_topology_sanitize_policy", "max_components exceeds the proven bound")
    if policy.get("color0_policy") not in {"reject", "explicit_discard"}:
        raise TopologyGLBError("invalid_topology_sanitize_policy", "COLOR_0 policy is invalid")
    return dict(policy)


def sanitize_topology_glb(data: bytes, policy: dict[str, Any]) -> dict[str, Any]:
    """Discard authorized COLOR_0, remove exact-zero faces, and write geometry only."""
    policy = validate_topology_policy(policy)
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
    except (GLBError, GeometryGLBError) as error:
        raise TopologyGLBError(error.code, str(error), **getattr(error, "details", {})) from error
    auxiliary = parsed["auxiliary_attributes"]
    if auxiliary not in ([], ["COLOR_0"]):
        raise TopologyGLBError(
            "unsupported_topology_aux_attribute", "sanitation accepts no auxiliary attribute except COLOR_0",
            attributes=auxiliary,
        )
    color = None
    if auxiliary == ["COLOR_0"]:
        if policy["color0_policy"] != "explicit_discard":
            raise TopologyGLBError("topology_color0_policy_required", "COLOR_0 requires Stage 4P explicit discard")
        try:
            color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"])
        except BootstrapError as error:
            raise TopologyGLBError(error.code, str(error), **error.details) from error
    elif policy["color0_policy"] == "explicit_discard":
        raise TopologyGLBError("topology_color0_absent", "explicit COLOR_0 discard requested but absent")
    geometry = parsed["geometry"]
    try:
        sanitized, sanitation = sanitize_mesh(
            geometry["positions"], geometry["faces"],
            remove_exact_zero_area_faces=policy["remove_exact_zero_area_faces"],
            max_components=policy["max_components"],
        )
    except MeshSanitizeError as error:
        raise TopologyGLBError(error.code, str(error), **error.details) from error
    canonical = pack_geometry_glb(sanitized)
    try:
        reopened = parse_geometry_glb(canonical)
    except GeometryGLBError as error:
        raise TopologyGLBError("topology_sanitize_canonical_invalid", str(error), source_code=error.code) from error
    if reopened["geometry"] != sanitized:
        raise TopologyGLBError("topology_sanitize_canonical_mismatch", "independent reopen changed sanitized geometry")
    report = {
        "schema_version": 1,
        "success": True,
        "policy": policy,
        "operation_order": ["validate_source", "discard_color0_if_authorized", "remove_exact_zero_area", "validate_components_and_boundaries", "canonical_reopen"],
        "source_sha256": _sha(data),
        "source_size_bytes": len(data),
        "canonical_sha256": _sha(canonical),
        "canonical_size_bytes": len(canonical),
        "color0": {
            "policy": policy["color0_policy"], "discarded": color is not None,
            "evidence": color,
        },
        "position_index_semantics": "surviving_faces_exact_positions_and_winding",
        "sanitation": sanitation,
        "canonical_topology": reopened["topology"],
    }
    report["report_sha256"] = _sha(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
    return {"canonical_glb": canonical, "geometry": sanitized, "report": report}


def inspect_topology_sanitation_applicability(data: bytes) -> dict[str, Any]:
    """Read-only Stage 4Q projection; never emits a derived GLB."""
    raw_hash = _sha(data)
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
        auxiliary = parsed["auxiliary_attributes"]
        color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"]) if auxiliary == ["COLOR_0"] else None
    except (GLBError, GeometryGLBError, BootstrapError) as error:
        return {
            "applicable": False, "raw_source_sha256": raw_hash, "raw_source_unchanged": True,
            "derived_candidate_created": False, "error": {
                "code": error.code, "message": str(error), "details": getattr(error, "details", {}),
            },
        }
    analysis = analyze_topology(parsed["geometry"]["positions"], parsed["geometry"]["faces"])
    if not analysis["applicable"]:
        return {
            "applicable": False, "color0_discard_applicable": color is not None,
            "auxiliary_attributes": auxiliary, "analysis": analysis,
            "raw_source_sha256": raw_hash, "raw_source_unchanged": True,
            "derived_candidate_created": False,
        }
    topology = analysis["report"]["topology"]
    return {
        "applicable": color is not None and auxiliary == ["COLOR_0"],
        "color0_discard_applicable": color is not None,
        "color0": color,
        "auxiliary_attributes": auxiliary,
        "exact_zero_area_removal_applicable": analysis["report"]["removed_face_count"] > 0,
        "hypothetical_sanitized_topology": topology,
        "stage4o_after_sanitation_applicable": topology["connected_components"] <= MAX_COMPONENTS,
        "raw_source_sha256": raw_hash,
        "raw_source_unchanged": True,
        "derived_candidate_created": False,
        "error": None,
    }


def run_generated_topology_pipeline(
    data: bytes,
    *,
    topology_policy: dict[str, Any],
    reduction_policy: dict[str, Any],
    bootstrap_policy: dict[str, Any],
) -> dict[str, Any]:
    """Compose Q -> O -> P while retaining each stage's explicit report."""
    sanitized = sanitize_topology_glb(data, topology_policy)
    try:
        reduced, reduction = reduce_geometry_components(
            sanitized["geometry"], reduction_policy,
            max_components=topology_policy["max_components"],
        )
    except GeometryReductionError as error:
        raise TopologyGLBError(error.code, str(error), **error.details) from error
    reduced_glb = pack_geometry_glb(reduced)
    try:
        bootstrapped = bootstrap_geometry_glb(
            reduced_glb, bootstrap_policy, max_components=topology_policy["max_components"],
        )
    except BootstrapError as error:
        raise TopologyGLBError(error.code, str(error), phase=error.phase, **error.details) from error
    report = {
        "schema_version": 1,
        "success": True,
        "operation_order": ["stage4p_color0_discard", "stage4q_exact_sanitize", "stage4o_component_reduction", "stage4p_attribute_bootstrap", "stage4f_validate"],
        "source_sha256": _sha(data),
        "sanitation": sanitized["report"],
        "reduction": reduction,
        "reduced_geometry_sha256": _sha(reduced_glb),
        "bootstrap": bootstrapped["report"],
        "canonical_sha256": _sha(bootstrapped["canonical_glb"]),
        "stage4f_accepted": True,
    }
    report["report_sha256"] = _sha(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
    return {
        "sanitized_glb": sanitized["canonical_glb"],
        "reduced_glb": reduced_glb,
        "canonical_glb": bootstrapped["canonical_glb"],
        "canonical_mesh": bootstrapped["canonical_mesh"],
        "geometry": reduced,
        "report": report,
    }


def load_topology_manifest(path: Path, root: Path) -> tuple[dict[str, Any], bytes]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TopologyGLBError("invalid_topology_manifest", f"cannot read Stage 4Q manifest: {path}") from error
    expected = {"schema_version", "id", "source", "source_format", "source_sha256", "provenance", "preprocessing"}
    if not isinstance(manifest, dict) or set(manifest) != expected or manifest.get("schema_version") != 14:
        raise TopologyGLBError("invalid_topology_manifest", "Stage 4Q manifest must use exact schema 14")
    if not isinstance(manifest.get("id"), str) or SAFE_ID.fullmatch(manifest["id"]) is None:
        raise TopologyGLBError("invalid_topology_manifest", "Stage 4Q id is invalid")
    if manifest.get("source_format") != "glb" or not isinstance(manifest.get("source_sha256"), str) or SHA256.fullmatch(manifest["source_sha256"]) is None:
        raise TopologyGLBError("invalid_topology_manifest", "source format/hash is invalid")
    if manifest.get("provenance") != {"kind": "project_authored", "license": "CC0-1.0"}:
        raise TopologyGLBError("invalid_topology_manifest", "proof source must be project-authored CC0")
    preprocessing = manifest.get("preprocessing")
    if not isinstance(preprocessing, dict) or set(preprocessing) != {"topology", "geometry_reduction", "bootstrap"}:
        raise TopologyGLBError("invalid_topology_manifest", "Stage 4Q requires topology, reduction, and bootstrap policies")
    preprocessing["topology"] = validate_topology_policy(preprocessing["topology"])
    try:
        preprocessing["geometry_reduction"] = _validate_policy(preprocessing["geometry_reduction"])
    except GeometryGLBError as error:
        raise TopologyGLBError(error.code, str(error), **error.details) from error
    bootstrap = preprocessing["bootstrap"]
    expected_bootstrap = {
        "policy": "hard_surface_static_v1", "material_name": "generated_surface", "color0_policy": "reject",
        "patch_normal_degrees": 0.1, "plane_epsilon": 0.00001, "texture_size": 32,
        "padding_texels": 1, "crease_angle_degrees": 60, "normal_weighting": "area",
    }
    if bootstrap != expected_bootstrap:
        raise TopologyGLBError("invalid_topology_manifest", "bootstrap policy differs from Stage 4P semantics")
    relative = Path(manifest["source"]) if isinstance(manifest.get("source"), str) else Path("/")
    if relative.is_absolute() or ".." in relative.parts:
        raise TopologyGLBError("unsafe_path", "Stage 4Q source path must be repository-relative")
    source = (root / relative).resolve(); required = (root / "assets/source").resolve()
    try: source.relative_to(required)
    except ValueError as error: raise TopologyGLBError("unsafe_path", "Stage 4Q source must be below assets/source") from error
    if not source.is_file(): raise TopologyGLBError("missing_source", f"Stage 4Q source does not exist: {source}")
    data = source.read_bytes()
    if _sha(data) != manifest["source_sha256"]:
        raise TopologyGLBError("source_hash_mismatch", "Stage 4Q source differs from its tracked hash")
    manifest["_source_path"] = str(source)
    return manifest, data


def run_topology_manifest(path: Path, root: Path) -> dict[str, Any]:
    manifest, source = load_topology_manifest(path, root)
    result = run_generated_topology_pipeline(
        source,
        topology_policy=manifest["preprocessing"]["topology"],
        reduction_policy=manifest["preprocessing"]["geometry_reduction"],
        bootstrap_policy=manifest["preprocessing"]["bootstrap"],
    )
    final = result["report"]["reduction"]["final"]
    if final["triangles"] > BOOTSTRAP_ENVELOPE["max_faces"] or final["positions"] > BOOTSTRAP_ENVELOPE["max_positions"]:
        raise TopologyGLBError("topology_pipeline_envelope_mismatch", "reduced geometry exceeds Stage 4P")
    result["report"]["asset_id"] = manifest["id"]
    result["report"]["source"] = manifest["source"]
    return {**result, "manifest": manifest}


def write_topology_outputs(path: Path, output: Path, root: Path) -> dict[str, Any]:
    result = run_topology_manifest(path, root)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "sanitized_glb": output / "sanitized-geometry.glb",
        "reduced_glb": output / "reduced-geometry.glb",
        "canonical_glb": output / "bootstrapped.glb",
        "report": output / "generated-topology-report.json",
    }
    files["sanitized_glb"].write_bytes(result["sanitized_glb"])
    files["reduced_glb"].write_bytes(result["reduced_glb"])
    files["canonical_glb"].write_bytes(result["canonical_glb"])
    files["report"].write_text(json.dumps(result["report"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**result["report"], "outputs": {key: str(value) for key, value in files.items()}}
