"""Deterministic Stage 6K processing for an immutable official generator export.

The external service boundary ends at the hashed raw GLB.  This module applies
only the already-proven Stage 4 geometry contracts and emits reproducible,
project-owned derived geometry.  It never repairs topology or changes a raw
candidate in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .glb_bootstrap import bootstrap_geometry_glb
from .glb_geometry_reduce import pack_geometry_glb, parse_geometry_glb
from .mesh_predecimate import reduce_geometry_components
from .mesh_sanitize import analyze_topology
from .mesh_tinyface import classify_target_faces


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "assets/manifests/stage6k_hunyuan_lighthouse_pipeline.json"
REPORT = ROOT / "docs/data/stage6k_landmark_pipeline.json"


class Stage6KError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_hashed(relative: str, expected: str, parent: str) -> tuple[Path, bytes]:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise Stage6KError(f"unsafe Stage 6K input: {relative}")
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to((ROOT / parent).resolve())
    except ValueError as error:
        raise Stage6KError(f"Stage 6K input must remain below {parent}") from error
    if not resolved.is_file():
        raise Stage6KError(f"missing Stage 6K input: {relative}")
    payload = resolved.read_bytes()
    if _sha(payload) != expected:
        raise Stage6KError(f"immutable Stage 6K hash mismatch: {relative}")
    return resolved, payload


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "id", "concept", "provenance", "raw_source",
        "derived", "topology", "tiny_faces", "geometry_reduction", "bootstrap",
    }
    if not isinstance(data, dict) or set(data) != required or data.get("schema_version") != 1:
        raise Stage6KError("Stage 6K pipeline manifest must use exact schema 1")
    for field, parent in (("concept", "assets/concepts"), ("provenance", "assets/provenance"), ("raw_source", "assets/source/generated")):
        record = data[field]
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise Stage6KError(f"invalid hashed Stage 6K {field} declaration")
        _read_hashed(record["path"], record["sha256"], parent)
    outputs = data["derived"]
    if not isinstance(outputs, dict) or set(outputs) != {"geometry", "canonical"}:
        raise Stage6KError("Stage 6K derived declarations are incomplete")
    for record in outputs.values():
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise Stage6KError("invalid Stage 6K derived declaration")
        target = Path(record["path"])
        if target.is_absolute() or ".." in target.parts or target.parts[:3] != ("assets", "source", "generated"):
            raise Stage6KError("Stage 6K derived paths must remain below assets/source/generated")
    if data["topology"] != {"max_components": 2, "repair": False}:
        raise Stage6KError("Stage 6K topology contract must remain validation-only")
    return data


def compile_landmark(path: Path = MANIFEST, *, write: bool = False) -> dict[str, Any]:
    manifest = load_manifest(path)
    _, raw = _read_hashed(manifest["raw_source"]["path"], manifest["raw_source"]["sha256"], "assets/source/generated")
    parsed = parse_geometry_glb(raw, validate_topology=True)
    geometry = parsed["geometry"]

    q = analyze_topology(geometry["positions"], geometry["faces"])
    if q["exact_zero_area_faces"] or q.get("full_topology") is None:
        raise Stage6KError("unchanged Stage 4Q did not accept the raw candidate without repair")
    if q["full_topology"]["connected_components"] > manifest["topology"]["max_components"]:
        raise Stage6KError("raw candidate exceeds the declared component envelope")
    q_report = {
        "success": True, "no_op": True, "repair_applied": False,
        "exact_zero_area_faces": 0, "topology": q["full_topology"],
    }

    classified = classify_target_faces(geometry["positions"], geometry["faces"], manifest["tiny_faces"])
    blockers = classified["classification_counts"]["TARGET_QUANTIZED_DEGENERATE"]
    if blockers:
        raise Stage6KError("raw candidate has Stage 4R target-null blockers; Stage 6K does not repair them")
    r_report = {
        "success": True, "no_op": True, "removed_face_count": 0,
        "classification_counts": classified["classification_counts"],
        "target_representation": classified["target_transform"],
    }

    reduced, o_report = reduce_geometry_components(
        geometry, manifest["geometry_reduction"], max_components=manifest["topology"]["max_components"],
    )
    reduced_glb = pack_geometry_glb(reduced)
    bootstrap = bootstrap_geometry_glb(
        reduced_glb, manifest["bootstrap"], max_components=manifest["topology"]["max_components"],
    )
    canonical = bootstrap["canonical_glb"]

    for key, payload in (("geometry", reduced_glb), ("canonical", canonical)):
        expected = manifest["derived"][key]["sha256"]
        if _sha(payload) != expected:
            raise Stage6KError(f"deterministic Stage 6K {key} hash changed")
        if write:
            destination = ROOT / manifest["derived"][key]["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)

    report = {
        "schema_version": 1,
        "success": True,
        "asset_id": manifest["id"],
        "concept": manifest["concept"],
        "provenance": manifest["provenance"],
        "raw": {
            **manifest["raw_source"], "bytes": len(raw), "immutable": True,
            "node_path": parsed["node_path"], "positions": len(geometry["positions"]),
            "triangles": len(geometry["faces"]), "topology": parsed["topology"],
        },
        "stage4q": q_report,
        "stage4r": r_report,
        "stage4o": o_report,
        "stage4p": bootstrap["report"],
        "stage4f": {"accepted": bootstrap["report"]["stage4f_accepted"]},
        "stage4j": {"required": False, "reason": "pre-J projection fits the unchanged 4096-byte ceiling"},
        "derived": {
            "geometry": {**manifest["derived"]["geometry"], "bytes": len(reduced_glb)},
            "canonical": {**manifest["derived"]["canonical"], "bytes": len(canonical)},
        },
    }
    report["report_sha256"] = _sha(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compile_landmark(write=not args.check), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
