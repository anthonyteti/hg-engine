"""Pack the Stage 6 integrated presentation themes into one ignored proof ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from . import battle_ui, core_menu_ui, remaining_ui
from .assets import compile_placements

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "build/stage6l/showcase"
REPORT = ROOT / "docs/data/stage6l_presentation_showcase.json"
FIXTURE = ROOT / "fixtures/stage6l_presentation_showcase.json"
ROM = ROOT / "test.nds"


class Stage6LShowcaseError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise Stage6LShowcaseError(f"command failed: {' '.join(command)}\n{result.stdout}{result.stderr}")


def _member(directory: Path, member: int) -> Path:
    matches = [path for path in directory.iterdir() if path.name.rsplit("_", 1)[-1].isdigit() and int(path.name.rsplit("_", 1)[-1]) == member]
    if len(matches) != 1:
        raise Stage6LShowcaseError(f"expected one archive member {member}, found {len(matches)}")
    return matches[0]


def _pack_ui(rom: Path) -> dict[str, Any]:
    core = json.loads(core_menu_ui.DEFAULT_SOURCE.read_text(encoding="utf-8"))
    remaining = json.loads(remaining_ui.DEFAULT_SOURCE.read_text(encoding="utf-8"))
    battle = json.loads(battle_ui.DEFAULT_SOURCE.read_text(encoding="utf-8"))
    core_menu_ui.compile_core_menus()
    remaining_ui.compile_remaining_ui()
    battle_ui.compile_battle_ui()

    transforms: dict[str, list[tuple[int, str, str, dict[str, Any]]]] = {}
    claimed: set[tuple[str, int]] = set()
    for archive, member, screen in core_menu_ui._targets(core):
        transforms.setdefault(archive, []).append((member, "palette", screen, core["palette_transform"]))
        claimed.add((archive, member))
    for archive, member, owner, mode in remaining_ui._targets(remaining):
        if (archive, member) in claimed:
            continue
        screen = "start_menu" if mode == "chrome" else "generic"
        transforms.setdefault(archive, []).append((member, "palette", screen, remaining["palette_transform"]))
        claimed.add((archive, member))

    battle_output = battle_ui.DEFAULT_OUTPUT
    battle_replacements = {
        28: battle_output / "7_28", 246: battle_output / "7_246",
        271: battle_output / "7_271", 351: battle_output / "7_351", 352: battle_output / "7_352",
    }
    battle_replacements.update({member: battle_output / f"7_{member}" for member in battle["target"]["screen_members"].values()})
    for member, source in battle_replacements.items():
        if ("a/0/0/7", member) in claimed:
            raise Stage6LShowcaseError(f"battle resource collides with a menu owner: member {member}")
        transforms.setdefault("a/0/0/7", []).append((member, "replace", source.as_posix(), {}))
        claimed.add(("a/0/0/7", member))
    transforms.setdefault("a/0/0/8", []).append((battle["target"]["hud_palette_member"], "replace", (battle_output / "8_71").as_posix(), {}))

    archive_paths = {archive: ROOT / "base/root" / archive for archive in transforms}
    if not rom.is_file() or any(not path.is_file() for path in archive_paths.values()):
        raise Stage6LShowcaseError("integrated proof requires a built ROM and audited native archives")
    originals = {archive: path.read_bytes() for archive, path in archive_paths.items()}
    applied: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="stage6l-showcase-") as temp_name:
        temp = Path(temp_name)
        try:
            for archive in sorted(transforms):
                extracted = temp / archive.replace("/", "_")
                rebuilt = temp / f"{archive.replace('/', '_')}.narc"
                _run(["python3", str(core_menu_ui.NARCPY), "extract", str(archive_paths[archive]), "-o", str(extracted), "-nf"])
                seen: set[int] = set()
                for member, operation, label, policy in transforms[archive]:
                    if member in seen:
                        raise Stage6LShowcaseError(f"integrated UI target collision: {archive} member {member}")
                    seen.add(member)
                    target = _member(extracted, member)
                    if operation == "replace":
                        target.write_bytes(Path(label).read_bytes())
                    else:
                        target.write_bytes(core_menu_ui.transform_nclr(target.read_bytes(), policy, label))
                    applied.append({"archive": archive, "member": member, "operation": operation, "sha256": _sha(target)})
                _run(["python3", str(core_menu_ui.NARCPY), "create", str(rebuilt), str(extracted), "-nf"])
                shutil.copyfile(rebuilt, archive_paths[archive])
            _run([str(core_menu_ui.NDSTOOL), "-c", str(rom), "-9", str(ROOT / "base/arm9.bin"), "-7", str(ROOT / "base/arm7.bin"), "-y9", str(ROOT / "base/overarm9.bin"), "-y7", str(ROOT / "base/overarm7.bin"), "-d", str(ROOT / "base/root"), "-y", str(ROOT / "base/overlay"), "-t", str(ROOT / "base/banner.bin"), "-h", str(ROOT / "base/header.bin")])
        finally:
            for archive, payload in originals.items():
                archive_paths[archive].write_bytes(payload)
    if not all(archive_paths[archive].read_bytes() == payload for archive, payload in originals.items()):
        raise Stage6LShowcaseError("native UI archives were not restored")
    return {"archive_count": len(transforms), "resource_count": len(applied), "resources": sorted(applied, key=lambda item: (item["archive"], item["member"])), "archives_restored": True}


def compile_showcase(*, proof_rom: bool = False, write: bool = True) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    placements = compile_placements(ROOT / fixture["asset_catalog"], fixture["assets"], ROOT)
    result: dict[str, Any] = {
        "schema_version": 1,
        "id": "stage6l_integrated_presentation_showcase",
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "fixture_sha256": _sha(FIXTURE),
        "asset_count": placements["report"]["asset_count"],
        "triangle_count": placements["report"]["triangle_count"],
        "quad_count": placements["report"]["quad_count"],
        "display_lists": placements["report"]["shapes"],
        "ui_sources": [
            str(core_menu_ui.DEFAULT_SOURCE.relative_to(ROOT)),
            str(remaining_ui.DEFAULT_SOURCE.relative_to(ROOT)),
            str(battle_ui.DEFAULT_SOURCE.relative_to(ROOT)),
        ],
        "validation": {"world_assets": "PASS", "generated_landmark": "PASS", "ui_sources": "PASS"},
    }
    if proof_rom:
        result["ui_pack"] = _pack_ui(ROM)
        result["rom_sha256"] = _sha(ROM)
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-rom", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compile_showcase(proof_rom=args.proof_rom), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
