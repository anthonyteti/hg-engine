"""Build the reusable Stage 6H UI semantic/static/navigation QA registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .qa import load_scenario

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/ui/qa/stage6_ui_smoke.json"
DEFAULT_LAYOUT = ROOT / "presentation/ui/screens/stage6d_field_journal.json"
DEFAULT_AUDIT = ROOT / "docs/data/hgengine_ui_reality_audit.json"
DEFAULT_OUTPUT = ROOT / "docs/data/stage6_ui_qa.json"


class UIQAError(ValueError):
    pass


def _canonical(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def validate(source: dict[str, Any], layout: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    if source.get("schema_version") != 1 or source.get("policy", {}).get("pixel_hash_primary") is not False:
        raise UIQAError("unsupported UI QA schema or pixel-hash policy")
    audit_ids = {screen["id"] for screen in audit["screens"]}
    missing = set(source.get("required_screens", [])) - audit_ids
    if missing:
        raise UIQAError(f"required screens absent from audit: {sorted(missing)}")
    scenarios = [ROOT / item for item in source.get("runtime_scenarios", [])]
    missing_paths = [path.relative_to(ROOT).as_posix() for path in scenarios if not path.is_file()]
    if missing_paths:
        raise UIQAError(f"runtime scenarios missing: {missing_paths}")
    nav = layout["navigation"]
    initial = nav.get("initial")
    nodes = {key for key in nav if key != "initial"}
    if initial not in nodes:
        raise UIQAError("navigation initial target is missing")
    reachable = {initial}
    queue = [initial]
    while queue:
        node = queue.pop()
        for direction, target in nav[node].items():
            if direction in {"left", "right", "up", "down"} and target not in nodes:
                raise UIQAError(f"navigation target {target} is missing")
            if target in nodes and target not in reachable:
                reachable.add(target); queue.append(target)
    if reachable != nodes:
        raise UIQAError(f"unreachable navigation nodes: {sorted(nodes - reachable)}")
    if any("cancel" not in nav[node] for node in nodes):
        raise UIQAError("every interactive navigation node requires cancel behavior")
    width, height = 32, 24
    components = layout["components"]
    for item in components:
        x, y, w, h = item["bounds"]
        if min(x, y, w, h) < 0 or w == 0 or h == 0 or x + w > width or y + h > height:
            raise UIQAError(f"component {item['id']} is out of native bounds")
    touch = [item for item in components if item["type"] in {"Button", "TouchButton"}]
    return {"navigation_nodes": len(nodes), "reachable_nodes": len(reachable), "component_count": len(components), "touch_region_count": len(touch), "runtime_scenario_count": len(scenarios)}


def compile_ui_qa(source_path: Path = DEFAULT_SOURCE, layout_path: Path = DEFAULT_LAYOUT, audit_path: Path = DEFAULT_AUDIT, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    metrics = validate(source, layout, audit)
    scenario_steps = 0
    scenario_assertions = 0
    plans = []
    for rel in source["runtime_scenarios"]:
        scenario = load_scenario(ROOT / rel)
        raw = _canonical(scenario)
        scenario_steps += len(scenario["steps"])
        scenario_assertions += sum("assert" in step for step in scenario["steps"])
        plans.append({"id": scenario["id"], "path": rel, "step_count": len(scenario["steps"]), "sha256": hashlib.sha256(raw).hexdigest()})
    report = {
        "schema_version": 1,
        "source": source_path.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(_canonical(source)).hexdigest(),
        "screen_count": len(source["required_screens"]),
        "semantic_assertions": source["semantic_assertions"],
        "static_checks": source["static_checks"],
        "screenshot_review": source["screenshot_review"],
        "runtime_plans": plans,
        "runtime_step_count": scenario_steps,
        "runtime_assertion_count": scenario_assertions,
        **metrics,
        "validation": {"screen_registry": "PASS", "navigation_graph": "PASS", "cancel_paths": "PASS", "native_bounds": "PASS", "scenario_plans": "PASS", "semantic_primary": "PASS"},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_canonical(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(compile_ui_qa(args.source.resolve(), args.layout.resolve(), args.audit.resolve(), args.output.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
