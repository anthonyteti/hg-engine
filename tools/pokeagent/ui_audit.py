"""Validate and expand the Stage 6B HGSS/HG-Engine UI reality model."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/ui/ui_reality_source.json"
DEFAULT_OUTPUT = ROOT / "docs/data/hgengine_ui_reality_audit.json"

REQUIRED_SYSTEM_FIELDS = {
    "module",
    "overlay",
    "local_evidence",
    "reference_evidence",
    "resources",
    "bg_layers",
    "sprites_oam",
    "palette",
    "tilemap",
    "window_usage",
    "font_route",
    "hardcoded_coordinates",
    "input",
    "touch",
    "transitions",
    "hooks",
    "constraints",
    "recommended_strategy",
}
REQUIRED_SURFACE_FIELDS = {
    "id",
    "name",
    "system",
    "classification",
    "bindings",
    "navigation",
    "touch_handling",
    "transition",
    "strategy",
    "confidence",
    "runtime_evidence",
    "target_stage",
}
CORE_SURFACES = {
    "title",
    "new_game",
    "continue",
    "dialogue",
    "start_menu",
    "party",
    "summary_overview",
    "summary_stats",
    "summary_moves",
    "bag",
    "pc_storage",
    "pokedex_list",
    "pokedex_entry",
    "trainer_card",
    "town_map",
    "shop_buy",
    "shop_sell",
    "save_prompt",
    "options",
    "naming",
    "battle_hud_player",
    "battle_hud_enemy",
    "battle_commands",
    "battle_fight_menu",
    "battle_switch",
    "battle_bag",
    "battle_run",
    "battle_target",
    "battle_mega",
    "battle_messages",
    "capture",
    "evolution",
    "item_use",
    "yes_no_prompt",
    "generic_list",
    "touch_regions",
    "font_system",
    "window_system",
    "fades_transitions",
    "oam_animation",
}


class UIAuditError(ValueError):
    pass


def _evidence_metadata(path_text: str) -> dict[str, Any]:
    path = ROOT / path_text
    if not path.exists():
        raise UIAuditError(f"local UI evidence path does not exist: {path_text}")
    record: dict[str, Any] = {"path": path_text, "kind": "directory" if path.is_dir() else "file"}
    # `base/` is a user-local, ignored ROM extraction that build variants patch
    # in place.  Its existence is valid local implementation evidence, but a
    # content hash would make the tracked audit depend on whichever opt-in ROM
    # happened to be built most recently.
    if path_text == "base" or path_text.startswith("base/"):
        record["volatile_local_runtime_artifact"] = True
        return record
    if path.is_file():
        data = path.read_bytes()
        record.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    else:
        record["file_count"] = sum(1 for child in path.rglob("*") if child.is_file())
    return record


def validate(source: dict[str, Any]) -> None:
    if source.get("schema_version") != 1:
        raise UIAuditError("unsupported UI reality schema")
    classifications = set(source.get("classifications", []))
    if classifications != {
        "RESOURCE_ONLY",
        "LAYOUT_DATA",
        "CODE_DRIVEN",
        "OVERLAY_CODE",
        "ENGINE_PATCH_REQUIRED",
        "MIXED",
        "UNKNOWN",
    }:
        raise UIAuditError("classification vocabulary does not match the Stage 6B contract")
    systems = source.get("systems", {})
    if not systems:
        raise UIAuditError("UI reality model has no systems")
    for system_id, system in systems.items():
        missing = REQUIRED_SYSTEM_FIELDS - set(system)
        if missing:
            raise UIAuditError(f"system {system_id} missing fields: {sorted(missing)}")
        for evidence in system["local_evidence"]:
            _evidence_metadata(evidence)
        if not system["reference_evidence"]:
            raise UIAuditError(f"system {system_id} lacks reference source evidence")
    surfaces = source.get("surfaces", [])
    ids = [surface.get("id") for surface in surfaces]
    if len(ids) != len(set(ids)):
        raise UIAuditError("surface IDs must be unique")
    missing_core = CORE_SURFACES - set(ids)
    if missing_core:
        raise UIAuditError(f"UI reality model missing core surfaces: {sorted(missing_core)}")
    for surface in surfaces:
        missing = REQUIRED_SURFACE_FIELDS - set(surface)
        if missing:
            raise UIAuditError(f"surface {surface.get('id')} missing fields: {sorted(missing)}")
        if surface["system"] not in systems:
            raise UIAuditError(f"surface {surface['id']} references unknown system {surface['system']}")
        if not surface["classification"] or not set(surface["classification"]) <= classifications:
            raise UIAuditError(f"surface {surface['id']} has invalid classification")
        if surface["confidence"] not in {"HIGH", "MEDIUM", "LOW"}:
            raise UIAuditError(f"surface {surface['id']} has invalid confidence")
        if surface["target_stage"] not in {"6C", "6D", "6E", "6F", "6G", "6H"}:
            raise UIAuditError(f"surface {surface['id']} has invalid target stage")
        if not surface["bindings"] or not surface["navigation"] or not surface["strategy"]:
            raise UIAuditError(f"surface {surface['id']} has incomplete authoring contract")


def build(source_path: Path = DEFAULT_SOURCE, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    validate(source)

    systems: dict[str, Any] = {}
    for system_id in sorted(source["systems"]):
        system = dict(source["systems"][system_id])
        system["local_evidence_metadata"] = [_evidence_metadata(path) for path in system["local_evidence"]]
        systems[system_id] = system

    expanded_surfaces = []
    for surface in sorted(source["surfaces"], key=lambda row: row["id"]):
        record = dict(surface)
        system = systems[surface["system"]]
        record["ownership"] = {
            "module": system["module"],
            "overlay": system["overlay"],
            "local_evidence": system["local_evidence"],
            "reference_evidence": system["reference_evidence"],
        }
        record["resource_archives"] = system["resources"]
        record["rendering"] = {
            "bg_layers": system["bg_layers"],
            "sprites_oam": system["sprites_oam"],
            "palette": system["palette"],
            "tilemap": system["tilemap"],
            "window_usage": system["window_usage"],
            "font_route": system["font_route"],
            "hardcoded_coordinates": system["hardcoded_coordinates"],
        }
        record["input_ownership"] = {
            "input": system["input"],
            "touch": system["touch"],
            "surface_touch": surface["touch_handling"],
            "navigation": surface["navigation"],
        }
        record["existing_hooks"] = system["hooks"]
        record["resource_constraints"] = system["constraints"]
        record["system_strategy"] = system["recommended_strategy"]
        expanded_surfaces.append(record)

    classification_counts = Counter(
        classification for surface in expanded_surfaces for classification in surface["classification"]
    )
    confidence_counts = Counter(surface["confidence"] for surface in expanded_surfaces)
    target_counts = Counter(surface["target_stage"] for surface in expanded_surfaces)
    overlay_counts = Counter(
        "ARM9_OR_SHARED" if surface["ownership"]["overlay"] is None else str(surface["ownership"]["overlay"])
        for surface in expanded_surfaces
    )
    result = {
        "schema_version": 1,
        "source": source_path.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "audited_project_revision": source["audited_project_revision"],
        "retail_reference": source["retail_reference"],
        "summary": {
            "surface_count": len(expanded_surfaces),
            "system_count": len(systems),
            "unknown_surface_count": classification_counts.get("UNKNOWN", 0),
            "classification_counts": dict(sorted(classification_counts.items())),
            "confidence_counts": dict(sorted(confidence_counts.items())),
            "target_stage_counts": dict(sorted(target_counts.items())),
            "overlay_ownership_counts": dict(sorted(overlay_counts.items())),
            "core_surface_count": len(CORE_SURFACES),
            "core_surface_coverage": "PASS",
        },
        "systems": systems,
        "screens": expanded_surfaces,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build(args.source, args.output)
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
