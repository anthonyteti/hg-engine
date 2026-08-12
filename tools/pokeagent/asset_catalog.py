"""Build the deterministic Stage 6 world-planner asset catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .environment_kit import ROOT, SOURCE as KIT_SOURCE, load_and_validate

SOURCE = ROOT / "presentation/environment/stage6j_variants.json"
OUTPUT = ROOT / "docs/data/stage6_asset_catalog.json"


class AssetCatalogError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pick(seed: str, family: str, index: int, slot: str, options: list[str]) -> str:
    digest = hashlib.sha256(f"{seed}:{family}:{index}:{slot}".encode()).digest()
    return options[int.from_bytes(digest[:8], "big") % len(options)]


def _metadata(module: dict[str, Any]) -> dict[str, Any]:
    width, height, depth = [float(value) for value in module["dimensions"]]
    return {
        "id": module["id"],
        "category": module["family"],
        "biomes": module["biomes"],
        "footprint": [width, depth],
        "bounds": {"min": [-width / 2, 0.0, -depth / 2], "max": [width / 2, height, depth / 2]},
        "height": height,
        "rotations": [0, 90, 180, 270],
        "collision": "footprint_rect",
        "textures": [module["material"]],
        "geometry_budget": "stage4_bounded_module",
        "texture_budget": "nitro_32x32_4bpp_symbolic",
        "source": str(KIT_SOURCE.relative_to(ROOT)),
        "variant_of": None,
        "components": [],
        "status": "approved",
        "visual_tags": module["tags"],
    }


def compile_catalog(source: Path = SOURCE, *, write: bool = True) -> dict[str, Any]:
    variant_source = json.loads(source.read_text(encoding="utf-8"))
    if variant_source.get("schema_version") != 1 or not isinstance(variant_source.get("seed"), str):
        raise AssetCatalogError("unsupported controlled-variant schema")
    if variant_source.get("source_kit") != str(KIT_SOURCE.relative_to(ROOT)):
        raise AssetCatalogError("variant source must bind the canonical Stage 6I kit")
    kit = load_and_validate(KIT_SOURCE)
    modules = {item["id"]: item for item in kit["modules"]}
    assets = [_metadata(module) for module in kit["modules"]]
    try:
        variant_source_label = str(source.relative_to(ROOT))
    except ValueError:
        variant_source_label = source.name
    family_counts: dict[str, int] = {}
    variant_ids: set[str] = set()
    for family in variant_source.get("families", []):
        if set(family) != {"id", "count", "bases", "components"}:
            raise AssetCatalogError("variant family fields are invalid")
        if family["count"] <= 0 or not family["bases"]:
            raise AssetCatalogError("variant family must be bounded and non-empty")
        referenced = family["bases"] + [item for values in family["components"].values() for item in values]
        if any(item not in modules for item in referenced):
            raise AssetCatalogError(f"variant family {family['id']} references an unknown module")
        family_counts[family["id"]] = family["count"]
        for index in range(1, family["count"] + 1):
            base = _pick(variant_source["seed"], family["id"], index, "base", family["bases"])
            components = [
                _pick(variant_source["seed"], family["id"], index, slot, options)
                for slot, options in sorted(family["components"].items())
            ]
            asset_id = f"{family['id']}_{index:02d}"
            if asset_id in modules or asset_id in variant_ids:
                raise AssetCatalogError(f"duplicate generated variant id: {asset_id}")
            variant_ids.add(asset_id)
            record = _metadata(modules[base])
            record.update({
                "id": asset_id,
                "source": variant_source_label,
                "variant_of": base,
                "components": components,
                "visual_tags": sorted(set(record["visual_tags"] + [family["id"], "controlled-variant"])),
            })
            assets.append(record)
    ids = [asset["id"] for asset in assets]
    if len(ids) != len(set(ids)):
        raise AssetCatalogError("catalog asset identities must be unique")
    output = {
        "schema_version": 1,
        "id": "stage6_production_asset_catalog",
        "source_kit_sha256": _sha(KIT_SOURCE.read_bytes()),
        "variant_source_sha256": _sha(source.read_bytes()),
        "seed": variant_source["seed"],
        "base_module_count": len(modules),
        "variant_count": len(variant_ids),
        "asset_count": len(assets),
        "variant_family_counts": family_counts,
        "world_planner_contract": "request asset_id; compiler owns Nitro shape, texture slot, NARC member, and material index",
        "assets": sorted(assets, key=lambda item: item["id"]),
    }
    if write:
        OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = compile_catalog(write=not args.check)
    print(json.dumps({key: payload[key] for key in (
        "asset_count", "base_module_count", "variant_count", "variant_family_counts", "seed",
    )}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
