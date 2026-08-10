"""Stage 4T fixed TripoSR extraction-resolution sweep evidence.

This module verifies immutable generator candidates, compares their raw
geometry with the Stage 4H MC64 baseline, and routes only eligible candidates
to the unchanged Stage 4Q boundary.  It owns no generation or mesh algorithm.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .generated_pipeline import (
    GeneratedPipelineError,
    _actual_tiny_policy,
    _stage4q_exact_or_noop,
    _write_wireframe_views,
    load_generated_pipeline_manifest,
    run_generated_pipeline_manifest,
)
from .glb import GLBError, _chunks
from .glb_bootstrap import BootstrapError, _color0_payload
from .glb_geometry_reduce import GEOMETRY_LIMITS, GeometryGLBError, parse_geometry_glb
from .mesh_predecimate import _DIRECTIONS, _mask, _projection
from .mesh_sanitize import MeshSanitizeError, _hash, _rotated, _topology, analyze_topology
from .mesh_tinyface import TinyFaceError, _target_coordinates, classify_target_faces


SWEEP_SCHEMA = 17
SWEEP_RESOLUTIONS = [48, 32, 24, 16]
STAGE4H_SHA256 = "7327a0a619bdcd1bc401587f2ee7a4748978a153628374be6fb94176627eef60"
TRIPOSR_REVISION = "f84354eb350eb07a108faf33a6bc564d455f9764"
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class GeneratorTopologyError(ValueError):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "details": self.details}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hashed_file(root: Path, declaration: object, prefix: Path) -> tuple[Path, bytes]:
    if not isinstance(declaration, dict) or set(declaration) != {"path", "sha256"}:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "tracked file declaration is invalid")
    relative, expected = declaration["path"], declaration["sha256"]
    if not isinstance(relative, str) or not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "tracked path or SHA-256 is invalid")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise GeneratorTopologyError("generator_sweep_unsafe_path", "tracked paths must be repository-relative")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to((root / prefix).resolve())
    except ValueError as error:
        raise GeneratorTopologyError("generator_sweep_unsafe_path", f"input must remain below {prefix}") from error
    if not resolved.is_file():
        raise GeneratorTopologyError("generator_sweep_missing_input", f"missing tracked input: {relative}")
    data = resolved.read_bytes()
    if _sha(data) != expected:
        raise GeneratorTopologyError("generator_sweep_hash_mismatch", f"SHA-256 mismatch: {relative}")
    return resolved, data


def load_generator_topology_manifest(path: Path, root: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", f"cannot read Stage 4T manifest: {path}") from error
    expected = {
        "schema_version", "id", "concept", "baseline", "generator",
        "intended_size_tiles", "raw_fidelity", "pipeline_policy", "candidates",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected or manifest.get("schema_version") != SWEEP_SCHEMA:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "Stage 4T manifest must use exact schema 17")
    if not isinstance(manifest.get("id"), str) or SAFE_ID.fullmatch(manifest["id"]) is None:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "sweep id is invalid")
    _, concept = _hashed_file(root, manifest["concept"], Path("assets/concepts"))
    baseline = manifest["baseline"]
    if not isinstance(baseline, dict) or set(baseline) != {"resolution", "path", "sha256"} or baseline.get("resolution") != 64:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "MC64 baseline declaration is invalid")
    baseline_path, baseline_data = _hashed_file(root, {"path": baseline["path"], "sha256": baseline["sha256"]}, Path("assets/source/generated"))
    if baseline["sha256"] != STAGE4H_SHA256:
        raise GeneratorTopologyError("generator_sweep_hash_mismatch", "baseline is not the immutable Stage 4H source")
    generator = manifest["generator"]
    required_generator = {
        "model": "stabilityai/TripoSR",
        "revision": TRIPOSR_REVISION,
        "endpoint": "https://stabilityai-triposr.hf.space",
        "remove_background": True,
        "foreground_ratio": 0.85,
        "output_format": "glb",
        "accepted_resolution_range": [32, 320],
    }
    if not isinstance(generator, dict) or any(generator.get(key) != value for key, value in required_generator.items()):
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "generator settings differ from the authorized sweep")
    if not isinstance(generator.get("processed_image_sha256"), str) or SHA256.fullmatch(generator["processed_image_sha256"]) is None:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "processed image hash is invalid")
    size = manifest["intended_size_tiles"]
    if size != [4.0, 6.0, 4.0]:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "Stage 4T placement must remain 4 x 6 x 4 tiles")
    fidelity = manifest["raw_fidelity"]
    if fidelity != {"directions": list(_DIRECTIONS), "minimum_silhouette_iou": 0.88}:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "raw fidelity gate differs from Stage 4T")
    policy_path, policy_data = _hashed_file(root, manifest["pipeline_policy"], Path("assets/manifests"))
    pipeline_manifest, _ = load_generated_pipeline_manifest(policy_path, root)
    candidates = manifest["candidates"]
    if not isinstance(candidates, list) or [item.get("resolution") for item in candidates if isinstance(item, dict)] != SWEEP_RESOLUTIONS:
        raise GeneratorTopologyError("generator_sweep_invalid_manifest", "candidate order must be 48, 32, 24, 16")
    loaded: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("status") not in {"generated", "unsupported"}:
            raise GeneratorTopologyError("generator_sweep_invalid_manifest", "candidate declaration is invalid")
        resolution = candidate["resolution"]
        if candidate["status"] == "unsupported":
            if resolution not in (24, 16) or candidate != {
                "resolution": resolution,
                "status": "unsupported",
                "reason": "official_generate_api_minimum_resolution_32",
            }:
                raise GeneratorTopologyError("generator_sweep_invalid_manifest", "unsupported resolution evidence is invalid")
            loaded.append(dict(candidate)); continue
        if set(candidate) != {"resolution", "status", "path", "sha256", "provenance"} or resolution not in (48, 32):
            raise GeneratorTopologyError("generator_sweep_invalid_manifest", "generated candidate declaration is invalid")
        source_path, source = _hashed_file(root, {"path": candidate["path"], "sha256": candidate["sha256"]}, Path("assets/source/generated"))
        provenance_path, provenance_data = _hashed_file(root, candidate["provenance"], Path("assets/provenance"))
        provenance = json.loads(provenance_data.decode("utf-8"))
        if (
            provenance.get("generator_model") != "stabilityai/TripoSR"
            or provenance.get("generator_revision") != TRIPOSR_REVISION
            or provenance.get("concept_sha256") != _sha(concept)
            or provenance.get("processed_image_sha256") != generator["processed_image_sha256"]
            or provenance.get("raw_output_sha256") != _sha(source)
            or provenance.get("generation_parameters", {}).get("marching_cubes_resolution") != resolution
            or provenance.get("generation_parameters", {}).get("foreground_ratio") != 0.85
        ):
            raise GeneratorTopologyError("generator_sweep_provenance_mismatch", f"MC{resolution} provenance is inconsistent")
        loaded.append({**candidate, "_path": source_path, "_data": source, "_provenance_path": provenance_path})
    return {
        **manifest,
        "_baseline_path": baseline_path,
        "_baseline_data": baseline_data,
        "_pipeline_policy_path": policy_path,
        "_pipeline_policy_data": policy_data,
        "_pipeline_manifest": pipeline_manifest,
        "_candidates": loaded,
    }


def _bounds(positions: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    return {
        "min": [min(point[axis] for point in positions) for axis in range(3)],
        "max": [max(point[axis] for point in positions) for axis in range(3)],
    }


def _boundary_diagnostics(
    positions: list[tuple[float, float, float]], faces: list[tuple[int, int, int]],
) -> dict[str, Any]:
    edges: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for face_id, face in enumerate(faces):
        for start, end in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge = min(start, end), max(start, end)
            edges[edge].append((face_id, 1 if (start, end) == edge else -1))
    adjacency = [set() for _ in faces]
    for owners in edges.values():
        if len(owners) == 2:
            adjacency[owners[0][0]].add(owners[1][0]); adjacency[owners[1][0]].add(owners[0][0])
    remaining = set(range(len(faces))); components: list[dict[str, Any]] = []
    while remaining:
        seed = min(remaining); remaining.remove(seed); stack = [seed]; found = []
        while stack:
            current = stack.pop(); found.append(current)
            for neighbor in sorted(adjacency[current], reverse=True):
                if neighbor in remaining:
                    remaining.remove(neighbor); stack.append(neighbor)
        used = sorted({index for face_id in found for index in faces[face_id]})
        signature = {
            "positions": sorted(positions[index] for index in used),
            "faces": sorted(_rotated(faces[face_id]) for face_id in found),
        }
        components.append({
            "component_id": _hash(signature)[:16], "faces": len(found), "positions": len(used),
            "bounds": {"min": [min(positions[index][axis] for index in used) for axis in range(3)],
                       "max": [max(positions[index][axis] for index in used) for axis in range(3)]},
        })
    components.sort(key=lambda item: item["component_id"])
    boundary_edges = sorted(edge for edge, owners in edges.items() if len(owners) == 1)
    boundary_adjacency: dict[int, set[int]] = defaultdict(set)
    for left, right in boundary_edges:
        boundary_adjacency[left].add(right); boundary_adjacency[right].add(left)
    branching = sorted((vertex, len(neighbors)) for vertex, neighbors in boundary_adjacency.items() if len(neighbors) != 2)
    unseen = set(boundary_adjacency); subgraphs = []
    while unseen:
        seed = min(unseen); unseen.remove(seed); stack = [seed]; vertices = []
        while stack:
            current = stack.pop(); vertices.append(current)
            for neighbor in sorted(boundary_adjacency[current], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor); stack.append(neighbor)
        subgraphs.append({"vertices": len(vertices), "closed_cycle": all(len(boundary_adjacency[v]) == 2 for v in vertices)})
    return {
        "connected_components": len(components), "components": components,
        "non_manifold_edges": sum(len(owners) > 2 for owners in edges.values()),
        "inconsistent_shared_edge_winding": sum(
            len(owners) == 2 and owners[0][1] == owners[1][1] for owners in edges.values()
        ),
        "boundary_edges": len(boundary_edges), "boundary_subgraphs": len(subgraphs),
        "valid_closed_boundary_loops": sum(item["closed_cycle"] for item in subgraphs),
        "branching_boundary_vertices": len(branching),
        "branching_boundary_degrees": {str(degree): sum(value == degree for _, value in branching) for degree in sorted({value for _, value in branching})},
    }


def _normalized_mesh(mesh: dict[str, Any], pipeline_manifest: dict[str, Any]) -> dict[str, Any]:
    policy = _actual_tiny_policy(pipeline_manifest, mesh["positions"])
    normalized, _, _, _ = _target_coordinates(mesh["positions"], policy)
    return {"positions": normalized, "faces": mesh["faces"]}


def _silhouette_compare(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, float] = {}
    for direction in _DIRECTIONS:
        projected = [_projection(point, direction) for point in source["positions"] + candidate["positions"]]
        projection_bounds = (
            min(point[0] for point in projected), max(point[0] for point in projected),
            min(point[1] for point in projected), max(point[1] for point in projected),
        )
        left = _mask(source["positions"], source["faces"], direction, projection_bounds)
        right = _mask(candidate["positions"], candidate["faces"], direction, projection_bounds)
        values[direction] = round(len(left & right) / max(1, len(left | right)), 6)
    source_bounds, candidate_bounds = _bounds(source["positions"]), _bounds(candidate["positions"])
    maximum_delta = max(
        abs(candidate_bounds[side][axis] - source_bounds[side][axis])
        for side in ("min", "max") for axis in range(3)
    )
    diagonal = math.sqrt(sum(
        (source_bounds["max"][axis] - source_bounds["min"][axis]) ** 2 for axis in range(3)
    ))
    return {
        "directions": values, "minimum": min(values.values()),
        "mean": round(sum(values.values()) / len(values), 6),
        "normalized_bounds_max_delta": maximum_delta,
        "normalized_bounds_delta_ratio": maximum_delta / max(diagonal, 1e-12),
    }


def _inspect_raw(data: bytes, pipeline_manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        document, binary = _chunks(data, GEOMETRY_LIMITS)
        parsed = parse_geometry_glb(data, allow_auxiliary=True, validate_topology=False)
        color = _color0_payload(document, binary, maximum=GEOMETRY_LIMITS["max_positions"])
    except (GLBError, GeometryGLBError, BootstrapError) as error:
        raise GeneratorTopologyError(error.code, str(error), **getattr(error, "details", {})) from error
    mesh = parsed["geometry"]
    analysis = analyze_topology(mesh["positions"], mesh["faces"])
    policy = _actual_tiny_policy(pipeline_manifest, mesh["positions"])
    try:
        classified = classify_target_faces(mesh["positions"], mesh["faces"], policy)
    except TinyFaceError as error:
        raise GeneratorTopologyError(error.code, str(error), **error.details) from error
    classifications: dict[str, int] = {}
    for record in classified["faces"]:
        classifications[record["classification"]] = classifications.get(record["classification"], 0) + 1
    diagnostics = _boundary_diagnostics(mesh["positions"], mesh["faces"])
    q_error = None
    try:
        _topology(mesh["positions"], mesh["faces"])
    except MeshSanitizeError as error:
        q_error = error.as_dict()
    return {
        "sha256": _sha(data), "size_bytes": len(data), "positions": len(mesh["positions"]),
        "triangles": len(mesh["faces"]), "bounds": _bounds(mesh["positions"]),
        "auxiliary_attributes": parsed["auxiliary_attributes"], "color0": color,
        "exact_zero_faces": analysis["exact_zero_area_faces"],
        "near_zero_nonzero_faces": analysis["near_zero_nonzero_faces"],
        "target_face_classifications": classifications, "topology": diagnostics,
        "stage4q_topology_error": q_error, "_mesh": mesh,
    }


def run_generator_topology_manifest(path: Path, root: Path) -> dict[str, Any]:
    manifest = load_generator_topology_manifest(path, root)
    pipeline_manifest = manifest["_pipeline_manifest"]
    baseline = _inspect_raw(manifest["_baseline_data"], pipeline_manifest)
    baseline_normalized = _normalized_mesh(baseline["_mesh"], pipeline_manifest)
    stage4s = run_generated_pipeline_manifest(manifest["_pipeline_policy_path"], root)["report"]
    rows = [{
        "resolution": 64, "status": "historical_baseline", "raw_sha256": baseline["sha256"],
        "raw_faces": baseline["triangles"], "raw_positions": baseline["positions"],
        "components": baseline["topology"]["connected_components"],
        "boundary_loops": baseline["topology"]["valid_closed_boundary_loops"],
        "q_result": f"removed_{stage4s['stage4q']['removed_face_count']}",
        "r_result": f"removed_{stage4s['stage4r']['removed_face_count']}",
        "post_qr_faces": stage4s["stage4r"]["final_triangles"],
        "stage4o_result": f"blocked_best_{stage4s['failure']['details']['best_valid_faces']}_faces_{stage4s['failure']['details']['best_valid_positions']}_positions",
        "stage4p_reached": False, "stage4f_reached": False, "pre_j_bytes": None,
        "post_j_bytes": None, "rom": False, "visual_verdict": "not_reached",
    }]
    candidates: list[dict[str, Any]] = []
    for declaration in manifest["_candidates"]:
        resolution = declaration["resolution"]
        if declaration["status"] == "unsupported":
            record = {
                "resolution": resolution, "status": "unsupported", "reason": declaration["reason"],
                "stage4q": {"attempted": False}, "stage4r": {"attempted": False},
                "stage4o": {"attempted": False}, "stage4p": {"attempted": False},
                "stage4f": {"attempted": False}, "stage4j": {"attempted": False},
                "stage4i": {"attempted": False}, "rom": {"attempted": False},
            }
            candidates.append(record)
            rows.append({
                "resolution": resolution, "status": "unsupported", "raw_sha256": None,
                "raw_faces": None, "raw_positions": None, "components": None, "boundary_loops": None,
                "q_result": "not_attempted", "r_result": "not_attempted", "post_qr_faces": None,
                "stage4o_result": "not_attempted", "stage4p_reached": False,
                "stage4f_reached": False, "pre_j_bytes": None, "post_j_bytes": None,
                "rom": False, "visual_verdict": "not_reached",
            })
            continue
        inspected = _inspect_raw(declaration["_data"], pipeline_manifest)
        normalized = _normalized_mesh(inspected["_mesh"], pipeline_manifest)
        fidelity = _silhouette_compare(baseline_normalized, normalized)
        fidelity["threshold"] = manifest["raw_fidelity"]["minimum_silhouette_iou"]
        fidelity["passed"] = fidelity["minimum"] >= fidelity["threshold"]
        q_error = inspected["stage4q_topology_error"]
        q_attempted = fidelity["passed"]
        q_report: dict[str, Any] = {
            "attempted": q_attempted, "inspection_performed": True,
            "exact_zero_faces": inspected["exact_zero_faces"], "removed_face_count": 0,
        }
        if q_error is not None:
            q_report.update({"success": False, "error": q_error})
        elif q_attempted:
            try:
                _, exact_report = _stage4q_exact_or_noop(inspected["_mesh"], pipeline_manifest["topology"])
            except GeneratedPipelineError as error:
                q_report.update({"success": False, "error": error.as_dict()})
            else:
                q_report.update({"success": True, "report": exact_report})
        else:
            q_report.update({"success": False, "reason": "raw_fidelity_gate_failed"})
        blocker = (
            "raw_fidelity_below_0_88" if not fidelity["passed"] else
            q_report.get("error", {}).get("code", "unknown_stage4q_rejection")
        )
        public = {key: value for key, value in inspected.items() if key != "_mesh"}
        record = {
            "resolution": resolution, "status": "blocked", "raw": public, "raw_fidelity": fidelity,
            "provenance": declaration["provenance"],
            "stage4q": q_report,
            "stage4r": {"attempted": False, "reason": "blocked_by_stage4q" if q_attempted else "blocked_by_raw_fidelity"},
            "stage4o": {"attempted": False, "reason": "blocked_before_stage4o"},
            "stage4p": {"attempted": False}, "stage4f": {"attempted": False},
            "stage4j": {"attempted": False}, "stage4i": {"attempted": False},
            "rom": {"attempted": False}, "visual": {"runtime": "not_reached"},
            "blocking_gate": blocker,
        }
        candidates.append(record)
        boundary_display = (
            inspected["topology"]["valid_closed_boundary_loops"]
            if inspected["topology"]["branching_boundary_vertices"] == 0 else
            f"invalid:{inspected['topology']['valid_closed_boundary_loops']}_cycles_plus_branching"
        )
        rows.append({
            "resolution": resolution, "status": "blocked", "raw_sha256": inspected["sha256"],
            "raw_faces": inspected["triangles"], "raw_positions": inspected["positions"],
            "components": inspected["topology"]["connected_components"], "boundary_loops": boundary_display,
            "q_result": q_report.get("error", {}).get("code", q_report.get("reason", "not_reached")),
            "r_result": "not_attempted", "post_qr_faces": None,
            "stage4o_result": "not_attempted", "stage4p_reached": False,
            "stage4f_reached": False, "pre_j_bytes": None, "post_j_bytes": None,
            "rom": False, "visual_verdict": "not_reached",
        })
    generated = [candidate for candidate in candidates if candidate["status"] != "unsupported"]
    if generated and all(not candidate["raw_fidelity"]["passed"] for candidate in generated):
        classification = "TRIPOSR_LOW_RESOLUTION_FIDELITY_INSUFFICIENT"
    else:
        classification = "TRIPOSR_TOPOLOGY_REMAINS_TOO_COMPLEX"
    report: dict[str, Any] = {
        "schema_version": 1, "success": False,
        "verdict": "STAGE_4T_GENERATOR_TOPOLOGY_BLOCKED",
        "generator_classification": classification,
        "stage4_disposition": "STAGE_4_ASSET_INFRASTRUCTURE_HAS_SPECIFIC_BLOCKER",
        "asset_id": manifest["id"],
        "generator": manifest["generator"], "concept": manifest["concept"],
        "resolutions_attempted": SWEEP_RESOLUTIONS,
        "baseline": {key: value for key, value in baseline.items() if key != "_mesh"},
        "baseline_stage4s": {
            "verdict": "STAGE_4S_REAL_GENERATED_ASSET_BLOCKED",
            "stage4o_best_valid_faces": stage4s["failure"]["details"]["best_valid_faces"],
            "stage4o_best_valid_positions": stage4s["failure"]["details"]["best_valid_positions"],
        },
        "candidates": candidates, "comparison_table": rows,
        "selected_candidate": None,
        "exact_remaining_blocker": (
            "MC48 meets the raw silhouette gate but has degree-4 branching open-boundary topology rejected by unchanged Stage 4Q; "
            "MC32 has the same topology class and also fails the 0.88 raw silhouette floor."
        ),
        "stage4h_historical_invariant": {
            "sha256": STAGE4H_SHA256, "unchanged": True,
            "verdict": ["STAGE_4H_GENERATED_ASSET_REJECTED", "REJECTED_UNSUPPORTED_STRUCTURE"],
        },
        "stage4s_historical_invariant": {
            "commit": "99ac5e631acc52eb0a01ca080a5aeb821e8a9355",
            "verdict": ["STAGE_4S_REAL_GENERATED_ASSET_BLOCKED", "REAL_GENERATED_ASSET_PIPELINE_UNPROVEN"],
        },
    }
    report["semantic_sha256"] = _sha((json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode())
    return {"report": report, "meshes": {
        64: baseline["_mesh"],
        **{candidate["resolution"]: _inspect_raw(candidate["_data"], pipeline_manifest)["_mesh"]
           for candidate in manifest["_candidates"] if candidate["status"] == "generated"},
    }}


def write_generator_topology_outputs(path: Path, output: Path, root: Path) -> dict[str, Any]:
    result = run_generator_topology_manifest(path, root)
    output.mkdir(parents=True, exist_ok=True)
    view_hashes = {}
    for resolution, mesh in sorted(result["meshes"].items(), reverse=True):
        view_hashes[f"mc{resolution}"] = _write_wireframe_views(mesh, output / "views" / f"mc{resolution}")
    report = dict(result["report"])
    report["outputs"] = {
        "report": "stage4t-report.json", "views": {
            key: {name: f"views/{key}/{name}" for name in sorted(value)}
            for key, value in sorted(view_hashes.items())
        },
        "view_sha256": {key: dict(sorted(value.items())) for key, value in sorted(view_hashes.items())},
        "derived_glbs": [], "models": [], "rom": None, "screenshots": [],
    }
    (output / "stage4t-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
