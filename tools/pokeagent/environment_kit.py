"""Compile the Stage 6 environment vocabulary into deterministic DS-safe proof meshes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "presentation/environment/stage6i_environment_kit.json"
REPORT = ROOT / "docs/data/stage6_environment_kit.json"
REQUIRED_BIOMES = {
    "upper_valleys", "lake_country", "karst_interior", "great_gulf", "islands",
    "high_country", "metropolitan_corridor", "championship_island",
}
REQUIRED_FAMILIES = {"terrain", "vegetation", "architecture", "architecture_part", "prop", "interior"}
SAFE_MATERIALS = {"stage4d_ground", "stage4d_wood", "stage4d_stone"}


class EnvironmentKitError(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_and_validate(path: Path = SOURCE) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("license") not in {"CC0-1.0", "MIT"}:
        raise EnvironmentKitError("unsupported environment-kit schema or license")
    if set(data.get("biomes", [])) != REQUIRED_BIOMES:
        raise EnvironmentKitError("environment kit must cover all eight presentation biomes")
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        raise EnvironmentKitError("environment kit modules must be a non-empty list")
    ids: set[str] = set()
    families: set[str] = set()
    for module in modules:
        if set(module) != {"id", "family", "kind", "dimensions", "material", "biomes", "tags"}:
            raise EnvironmentKitError("module records must use the canonical fields")
        if module["id"] in ids:
            raise EnvironmentKitError(f"duplicate module id: {module['id']}")
        ids.add(module["id"])
        families.add(module["family"])
        if module["material"] not in SAFE_MATERIALS:
            raise EnvironmentKitError(f"unsupported symbolic material: {module['material']}")
        if len(module["dimensions"]) != 3 or any(not isinstance(v, (int, float)) or v <= 0 for v in module["dimensions"]):
            raise EnvironmentKitError(f"invalid positive dimensions: {module['id']}")
        if not module["biomes"] or any(b != "all" and b not in REQUIRED_BIOMES for b in module["biomes"]):
            raise EnvironmentKitError(f"invalid biome binding: {module['id']}")
    if not REQUIRED_FAMILIES <= families:
        raise EnvironmentKitError("environment kit is missing a required module family")
    for showcase in data.get("showcases", []):
        if showcase.get("material") not in SAFE_MATERIALS or not showcase.get("placements"):
            raise EnvironmentKitError("invalid showcase")
        for placement in showcase["placements"]:
            if placement.get("module") not in ids:
                raise EnvironmentKitError("showcase references an unknown module")
            module = next(item for item in modules if item["id"] == placement["module"])
            if module["material"] != showcase["material"]:
                raise EnvironmentKitError("a Stage 4 proof mesh may bind only one material")
    return data


class ObjBuilder:
    def __init__(self, material: str) -> None:
        self.material = material
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[tuple[tuple[int, int, int, int], int]] = []

    def box(self, center: tuple[float, float, float], size: tuple[float, float, float]) -> None:
        cx, cy, cz = center
        sx, sy, sz = (value / 2 for value in size)
        start = len(self.vertices) + 1
        self.vertices.extend([
            (cx-sx, cy, cz-sz), (cx+sx, cy, cz-sz), (cx+sx, cy, cz+sz), (cx-sx, cy, cz+sz),
            (cx-sx, cy+2*sy, cz-sz), (cx+sx, cy+2*sy, cz-sz),
            (cx+sx, cy+2*sy, cz+sz), (cx-sx, cy+2*sy, cz+sz),
        ])
        a = start
        self.faces.extend([((a,a+1,a+2,a+3),3),((a+4,a+7,a+6,a+5),4),((a,a+3,a+7,a+4),1),
                           ((a+2,a+1,a+5,a+6),2),((a+1,a,a+4,a+5),5),((a+3,a+2,a+6,a+7),6)])

    def module(self, module: dict[str, Any], placement: dict[str, Any]) -> None:
        x, y, z = placement["position"]
        scale = placement["scale"]
        dims = tuple(float(module["dimensions"][i]) * float(scale[i]) for i in range(3))
        kind = module["kind"]
        if kind in {"gable", "facade", "gate", "stall"}:
            self.box((x, y, z), dims)
            roof_h = max(0.35, dims[1] * 0.22)
            self.box((x, y + dims[1], z), (dims[0] * 1.08, roof_h, dims[2] * 1.08))
        elif kind in {"conifer", "canopy"}:
            self.box((x, y, z), (dims[0] * .28, dims[1] * .55, dims[2] * .28))
            self.box((x, y + dims[1] * .42, z), (dims[0], dims[1] * .58, dims[2]))
        elif kind in {"fence", "railing"}:
            self.box((x, y, z), (dims[0], dims[1] * .25, dims[2]))
            self.box((x-dims[0]*.42, y, z), (dims[2], dims[1], dims[2]))
            self.box((x+dims[0]*.42, y, z), (dims[2], dims[1], dims[2]))
        elif kind in {"sign", "post"}:
            self.box((x, y, z), (dims[0] * .3, dims[1], dims[2] * .3))
            if kind == "sign":
                self.box((x, y + dims[1] * .5, z), (dims[0], dims[1] * .35, dims[2]))
        else:
            self.box((x, y, z), dims)

    def render(self, object_id: str) -> bytes:
        lines = [f"# Generated deterministically from {SOURCE.relative_to(ROOT)}", f"o {object_id}"]
        lines.extend(f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in self.vertices)
        lines.extend(["vt 0.0 0.0", "vt 0.0 1.0", "vt 1.0 1.0", "vt 1.0 0.0",
                      "vn -1.0 0.0 0.0", "vn 1.0 0.0 0.0", "vn 0.0 -1.0 0.0",
                      "vn 0.0 1.0 0.0", "vn 0.0 0.0 -1.0", "vn 0.0 0.0 1.0",
                      f"usemtl {object_id}_material"])
        for face, normal in self.faces:
            lines.append("f " + " ".join(f"{vertex}/{index}/{normal}" for index, vertex in enumerate(face, 1)))
        return ("\n".join(lines) + "\n").encode()


def compile_kit(path: Path = SOURCE, write: bool = True) -> dict[str, Any]:
    data = load_and_validate(path)
    modules = {item["id"]: item for item in data["modules"]}
    outputs: dict[str, dict[str, Any]] = {}
    for showcase in data["showcases"]:
        builder = ObjBuilder(showcase["material"])
        for placement in showcase["placements"]:
            builder.module(modules[placement["module"]], placement)
        payload = builder.render(showcase["id"])
        destination = ROOT / "assets/source" / f"{showcase['id']}.obj"
        if write:
            destination.write_bytes(payload)
        outputs[showcase["id"]] = {
            "path": str(destination.relative_to(ROOT)), "sha256": _sha(payload),
            "bytes": len(payload), "positions": len(builder.vertices), "quads": len(builder.faces),
            "material": showcase["material"],
        }
    family_counts = {family: sum(m["family"] == family for m in data["modules"]) for family in sorted(REQUIRED_FAMILIES)}
    biome_counts = {biome: sum(biome in m["biomes"] or "all" in m["biomes"] for m in data["modules"]) for biome in sorted(REQUIRED_BIOMES)}
    report = {
        "schema_version": 1, "id": data["id"], "source": str(path.relative_to(ROOT)),
        "source_sha256": _sha(path.read_bytes()), "direction": data["presentation_direction"],
        "module_count": len(data["modules"]), "family_counts": family_counts,
        "biome_counts": biome_counts, "symbolic_material_count": len(SAFE_MATERIALS),
        "symbolic_materials": sorted(SAFE_MATERIALS), "showcases": outputs,
    }
    if write:
        REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = compile_kit(write=not args.check)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
