"""Compile declarative Stage 6 UI screens into bounded native configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/ui/screens/stage6d_field_journal.json"
DEFAULT_HEADER = ROOT / "include/generated/stage6d_ui.h"
DEFAULT_REPORT = ROOT / "docs/data/stage6_ui_layouts.json"

TYPE_IDS = {"Text": 1, "Panel": 2, "Button": 3, "TouchButton": 4}
ACTION_IDS = {"none": 0, "inspect_party": 1, "inspect_bag": 2, "close": 3}
BUTTON_IDS = {"a": 1, "b": 2, "select": 4, "start": 8, "left": 32, "right": 16}
ALLOWED_BINDINGS = {
    "party[0].species": "STAGE6D_BINDING_PARTY0_SPECIES",
    "party[0].level": "STAGE6D_BINDING_PARTY0_LEVEL",
    "party[0].hp": "STAGE6D_BINDING_PARTY0_HP",
    "party[0].max_hp": "STAGE6D_BINDING_PARTY0_MAX_HP",
}


class UILayoutError(ValueError):
    pass


def _canonical(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _charmap() -> dict[str, int]:
    result: dict[str, int] = {}
    for raw in (ROOT / "charmap.txt").read_text(encoding="utf-8").splitlines():
        if not raw or raw.lstrip().startswith("//") or "=" not in raw:
            continue
        code, value = raw.split("=", 1)
        if len(value) == 1:
            result[value] = int(code.strip(), 16)
    return result


def _validate(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if data.get("schema_version") != 1:
        raise UILayoutError("schema_version must be 1")
    screen = data.get("screen", {})
    if screen.get("id") != "ui.proof.field_journal" or screen.get("native_screen") != "top":
        raise UILayoutError("Stage 6D proof must target its audited top-screen identity")
    if screen.get("background_layer") != "MAIN_BG3":
        raise UILayoutError("only the audited MAIN_BG3 proof adapter is supported")
    if screen.get("trigger") not in BUTTON_IDS:
        raise UILayoutError("unknown trigger")
    bindings = data.get("bindings", [])
    binding_ids: set[str] = set()
    for binding in bindings:
        if binding.get("id") in binding_ids:
            raise UILayoutError(f"duplicate binding {binding.get('id')}")
        binding_ids.add(binding.get("id"))
        if binding.get("source") not in ALLOWED_BINDINGS:
            raise UILayoutError(f"raw or unsupported binding {binding.get('source')}")
    components = data.get("components", [])
    if not components or len(components) > data["budgets"]["windows"]:
        raise UILayoutError("component/window budget exceeded")
    ids: set[str] = set()
    occupied: list[tuple[int, int, int, int, str]] = []
    touch_count = 0
    total_tiles = 0
    charmap = _charmap()
    for component in components:
        cid = component.get("id")
        if not cid or cid in ids:
            raise UILayoutError(f"missing or duplicate component id {cid}")
        ids.add(cid)
        if component.get("type") not in TYPE_IDS:
            raise UILayoutError(f"unsupported component type {component.get('type')}")
        bounds = component.get("bounds", [])
        if len(bounds) != 4:
            raise UILayoutError(f"{cid}: bounds must be x,y,width,height")
        x, y, width, height = map(int, bounds)
        if min(x, y, width, height) < 0 or width == 0 or height == 0 or x + width > 32 or y + height > 24:
            raise UILayoutError(f"{cid}: out of 256x192 native bounds")
        for ox, oy, ow, oh, oid in occupied:
            if x < ox + ow and x + width > ox and y < oy + oh and y + height > oy:
                raise UILayoutError(f"illegal component overlap: {cid} with {oid}")
        occupied.append((x, y, width, height, cid))
        total_tiles += width * height
        if total_tiles > data["budgets"]["tiles"]:
            raise UILayoutError("window tile budget exceeded")
        text = component.get("text", "")
        missing = sorted({char for char in text if char not in charmap})
        if missing:
            raise UILayoutError(f"{cid}: unsupported text characters {missing}")
        for binding_id in component.get("bindings", []):
            if binding_id not in binding_ids:
                raise UILayoutError(f"{cid}: unknown binding {binding_id}")
        if component["type"] == "TouchButton":
            touch_count += 1
            touch = component.get("touch", [])
            if len(touch) != 4 or not (0 <= touch[0] < touch[2] <= 256 and 0 <= touch[1] < touch[3] <= 192):
                raise UILayoutError(f"{cid}: invalid native touch rectangle")
            if component.get("action") not in ACTION_IDS:
                raise UILayoutError(f"{cid}: unknown action")
    if touch_count > data["budgets"]["touch_regions"]:
        raise UILayoutError("touch-region budget exceeded")
    nav = data.get("navigation", {})
    buttons = [item["id"] for item in components if item["type"] in {"Button", "TouchButton"}]
    if nav.get("initial") not in buttons:
        raise UILayoutError("navigation initial target is not a button")
    for button in buttons:
        if button not in nav:
            raise UILayoutError(f"missing navigation for {button}")
        for direction in ("left", "right"):
            if nav[button].get(direction) not in buttons:
                raise UILayoutError(f"{button}: unreachable {direction} target")
        for action in ("confirm", "cancel"):
            if nav[button].get(action) not in ACTION_IDS:
                raise UILayoutError(f"{button}: unknown {action} action")
    return components, bindings


def compile_layout(source: Path, header: Path, report: Path) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    components, bindings = _validate(data)
    cmap = _charmap()
    buttons = [item for item in components if item["type"] in {"Button", "TouchButton"}]
    button_index = {item["id"]: index for index, item in enumerate(buttons)}
    nav = data["navigation"]
    base_tile = 1
    component_rows = []
    text_rows = []
    for component in components:
        x, y, width, height = component["bounds"]
        touch = component.get("touch", [0, 0, 0, 0])
        button_slot = button_index.get(component["id"], 255)
        component_rows.append(
            "    {%d, %d, %d, %d, %d, %d, %d, %d, %d, %d, {%d, %d, %d, %d}}," % (
                TYPE_IDS[component["type"]], x, y, width, height,
                component["palette"], component["fill"], component.get("selected_fill", component["fill"]),
                base_tile, button_slot, *touch,
            )
        )
        base_tile += width * height
        codes = [cmap[ch] for ch in component.get("text", "")] + [0xFFFF]
        text_rows.append("    {" + ", ".join(f"0x{code:04X}" for code in codes) + "},")
    max_text = max(len(component.get("text", "")) + 1 for component in components)
    nav_rows = []
    for button in buttons:
        record = nav[button["id"]]
        nav_rows.append("    {%d, %d, %d, %d}," % (
            button_index[record["left"]], button_index[record["right"]],
            ACTION_IDS[record["confirm"]], ACTION_IDS[record["cancel"]],
        ))
    binding_rows = [f"    {ALLOWED_BINDINGS[item['source']]}," for item in bindings]
    digest = hashlib.sha256(_canonical(data)).hexdigest()
    header_text = f"""/* Generated by tools.pokeagent.ui_layout; do not edit. */
#ifndef GENERATED_STAGE6D_UI_H
#define GENERATED_STAGE6D_UI_H

#define STAGE6D_UI_SOURCE_SHA \"{digest}\"
#define STAGE6D_UI_SOURCE_TOKEN 0x{digest[:8].upper()}u
#define STAGE6D_UI_COMPONENT_COUNT {len(components)}
#define STAGE6D_UI_BUTTON_COUNT {len(buttons)}
#define STAGE6D_UI_BINDING_COUNT {len(bindings)}
#define STAGE6D_UI_INITIAL_SELECTION {button_index[nav['initial']]}
#define STAGE6D_UI_TRIGGER_MASK {BUTTON_IDS[data['screen']['trigger']]}
#define STAGE6D_UI_MAX_TEXT {max_text}
#define STAGE6D_UI_TILE_COUNT {base_tile - 1}

enum Stage6DBindingId {{
    STAGE6D_BINDING_PARTY0_SPECIES = 1,
    STAGE6D_BINDING_PARTY0_LEVEL,
    STAGE6D_BINDING_PARTY0_HP,
    STAGE6D_BINDING_PARTY0_MAX_HP
}};

typedef struct Stage6DUIComponent {{
    unsigned char type, x, y, width, height, palette, fill, selectedFill;
    unsigned short baseTile;
    unsigned char buttonSlot;
    unsigned short touch[4];
}} Stage6DUIComponent;

typedef struct Stage6DUINavigation {{
    unsigned char left, right, confirmAction, cancelAction;
}} Stage6DUINavigation;

static const Stage6DUIComponent sStage6DUIComponents[STAGE6D_UI_COMPONENT_COUNT] = {{
{chr(10).join(component_rows)}
}};

static const unsigned short sStage6DUIText[STAGE6D_UI_COMPONENT_COUNT][STAGE6D_UI_MAX_TEXT] = {{
{chr(10).join(text_rows)}
}};

static const Stage6DUINavigation sStage6DUINavigation[STAGE6D_UI_BUTTON_COUNT] = {{
{chr(10).join(nav_rows)}
}};

static const unsigned char sStage6DUIBindings[STAGE6D_UI_BINDING_COUNT] = {{
{chr(10).join(binding_rows)}
}};

#endif
"""
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(header_text, encoding="utf-8")
    try:
        source_label = source.relative_to(ROOT).as_posix()
    except ValueError:
        source_label = source.name
    result = {
        "schema_version": 1,
        "screen_id": data["screen"]["id"],
        "source": source_label,
        "source_sha256": digest,
        "resource_bundle": data["screen"]["resource_bundle"],
        "component_count": len(components),
        "component_types": sorted({item["type"] for item in components}),
        "binding_sources": [item["source"] for item in bindings],
        "navigation_targets": [item["id"] for item in buttons],
        "touch_region_count": sum(item["type"] == "TouchButton" for item in components),
        "tile_count": base_tile - 1,
        "budgets": data["budgets"],
        "header_sha256": hashlib.sha256(header_text.encode()).hexdigest(),
        "validation": {
            "native_bounds": "PASS", "overlap": "PASS", "bindings": "PASS",
            "navigation_reachability": "PASS", "touch_bounds": "PASS", "budgets": "PASS"
        },
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(_canonical(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    result = compile_layout(args.source.resolve(), args.header.resolve(), args.report.resolve())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
