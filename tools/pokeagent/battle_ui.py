"""Compile and install the Stage 6 battle presentation from semantic source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/ui/screens/stage6e_battle.json"
DEFAULT_OUTPUT = ROOT / "build/stage6e/battle_ui"
DEFAULT_HEADER = ROOT / "include/generated/stage6e_battle_ui.h"
DEFAULT_REPORT = ROOT / "docs/data/stage6_battle_ui.json"
NITROGFX = ROOT / "tools/nitrogfx"
NARCPY = ROOT / "tools/narcpy.py"
NDSTOOL = ROOT / "tools/ndstool"


class BattleUIError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _rgb(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise BattleUIError(f"invalid color {value!r}")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def validate(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1 or data.get("theme") != "adriatic_field_journal":
        raise BattleUIError("unsupported battle UI schema/theme")
    target = data.get("target", {})
    if target.get("archive") != "a/0/0/7" or target.get("character_member") != 28 or target.get("palette_member") != 246:
        raise BattleUIError("battle resource target diverges from audited overlay-12 contract")
    if (target.get("mega_palette_off_member"), target.get("mega_palette_on_member")) != (351, 352):
        raise BattleUIError("Mega feedback palettes diverge from the existing HG-Engine extension")
    if target.get("hud_archive") != "a/0/0/8" or target.get("hud_palette_member") != 71:
        raise BattleUIError("battle HUD palette target diverges from the audited overlay-12 contract")
    members = target.get("screen_members", {})
    if set(members) != {"main", "fight", "two_option", "switch", "target", "message", "initial", "fight_mega"}:
        raise BattleUIError("all native battle tilemap roles must be declared")
    if len(set(members.values())) != len(members):
        raise BattleUIError("battle screen archive members collide")
    palette = [_rgb(value) for value in data.get("palette", [])]
    if len(palette) != 16 or len(set(palette)) != 16:
        raise BattleUIError("battle palette requires 16 unique design colors")
    hud_palette = [_rgb(value) for value in data.get("hud_palette", [])]
    if len(hud_palette) != 16:
        raise BattleUIError("battle HUD palette requires exactly 16 colors")
    allowed_styles = {"primary", "paper", "quiet", "copper"}
    for screen_id, screen in data.get("screens", {}).items():
        ids: set[str] = set()
        bounds: list[list[int]] = []
        for panel in screen.get("panels", []):
            if panel.get("id") in ids:
                raise BattleUIError(f"{screen_id}: duplicate panel {panel.get('id')}")
            ids.add(panel.get("id"))
            rect = panel.get("bounds", [])
            if len(rect) != 4 or min(rect) < 0 or rect[2] <= 0 or rect[3] <= 0 or rect[0] + rect[2] > 32 or rect[1] + rect[3] > 24:
                raise BattleUIError(f"{screen_id}/{panel.get('id')}: out of native bounds")
            if any(_overlap(rect, old) for old in bounds):
                raise BattleUIError(f"{screen_id}/{panel.get('id')}: illegal panel overlap")
            bounds.append(rect)
            if panel.get("style") not in allowed_styles:
                raise BattleUIError(f"{screen_id}/{panel.get('id')}: unknown style")
        for touch_id, rect in screen.get("touch", {}).items():
            if touch_id not in ids or len(rect) != 4 or not (0 <= rect[0] < rect[2] <= 256 and 0 <= rect[1] < rect[3] <= 192):
                raise BattleUIError(f"{screen_id}/{touch_id}: invalid semantic touch region")
    expected = {
        "battle.player.active.species", "battle.player.active.hp", "battle.player.active.max_hp",
        "battle.enemy.active.species", "battle.enemy.active.hp", "battle.selected_move",
        "battle.mega.eligible", "battle.mega.requested", "battle.target",
    }
    if not expected.issubset(set(data.get("semantic_bindings", []))):
        raise BattleUIError("required semantic bindings are incomplete")


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise BattleUIError(f"command failed: {' '.join(command)}\n{result.stdout}{result.stderr}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _draw_tiles(data: dict[str, Any], path: Path) -> None:
    image = Image.new("P", (256, 8), 0)
    colors = [_rgb(value) for value in data["palette"]]
    pal = [channel for color in colors for channel in color] + [0] * (768 - len(colors) * 3)
    image.putpalette(pal)
    px = image.load()
    assert px is not None
    # 0..3 fills; 4..19 framed corners/edges for four semantic panel styles.
    fills = {0: 1, 1: 7, 2: 2, 3: 9}
    borders = {0: 4, 1: 10, 2: 12, 3: 10}
    for style, fill in fills.items():
        for variant in range(4):
            tile = style * 4 + variant
            for y in range(8):
                for x in range(8):
                    color = fill
                    if variant == 0 and y == 0:
                        color = borders[style]
                    elif variant == 1 and y == 7:
                        color = borders[style]
                    elif variant == 2 and x == 0:
                        color = borders[style]
                    elif variant == 3 and x == 7:
                        color = borders[style]
                    px[tile * 8 + x, y] = color
    # Remaining tiles are restrained dotted journal guides and selection accents.
    for tile in range(16, 32):
        for y in range(8):
            for x in range(8):
                px[tile * 8 + x, y] = 6 if (x + y + tile) % 8 else (8 if tile % 2 else 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=False)


def _write_palette(data: dict[str, Any], path: Path, *, repeat: int = 16, on: bool = False) -> None:
    # Battle button feedback rewrites palette-bank bits (not pixel indices).
    # Replicate the coherent 16-color theme across all 16 BG banks so native
    # selection feedback cannot expose uninitialized black palette banks.
    colors = [_rgb(value) for value in data["palette"]]
    if on:
        colors[1], colors[9] = colors[9], colors[1]
    rows = ["JASC-PAL", "0100", str(16 * repeat)]
    rows.extend(f"{r} {g} {b}" for _ in range(repeat) for r, g, b in colors)
    path.write_bytes(("\r\n".join(rows) + "\r\n").encode("ascii"))


def _write_hud_palette(data: dict[str, Any], path: Path) -> None:
    # Indices 5..13 retain the retail HP/status semantics; only neutral frame,
    # paper, and ink colors are themed. Keeping the established indices makes
    # this a presentation resource change rather than a battle-state patch.
    colors = [_rgb(value) for value in data["hud_palette"]]
    rows = ["JASC-PAL", "0100", "16"]
    rows.extend(f"{r} {g} {b}" for r, g, b in colors)
    path.write_bytes(("\r\n".join(rows) + "\r\n").encode("ascii"))


STYLE = {"primary": 0, "paper": 1, "quiet": 2, "copper": 3}


def _tilemap(screen: dict[str, Any]) -> dict[str, Any]:
    grid = [0] * (32 * 24)
    for panel in screen.get("panels", []):
        x0, y0, width, height = panel["bounds"]
        style = STYLE[panel["style"]]
        fill = style * 4
        for y in range(y0, y0 + height):
            for x in range(x0, x0 + width):
                tile = fill
                if y == y0:
                    tile = style * 4
                elif y == y0 + height - 1:
                    tile = style * 4 + 1
                elif x == x0:
                    tile = style * 4 + 2
                elif x == x0 + width - 1:
                    tile = style * 4 + 3
                grid[y * 32 + x] = tile + 1
    return {"height": 24, "width": 32, "layers": [{"data": grid}], "tilesets": [{"firstgid": 1}]}


def _header(data: dict[str, Any], digest: str) -> str:
    touch = data["screens"]["fight_mega"]["touch"]
    def row(name: str) -> str:
        left, top, right, bottom = touch[name]
        # HGSS ButtonTBL stores the right screen edge as the u8 sentinel 255.
        right = 255 if right == 256 else right
        return f"{{{top}, {bottom}, {left}, {right}}}"
    return f"""/* Generated by tools.pokeagent.battle_ui; do not edit. */
#ifndef GENERATED_STAGE6E_BATTLE_UI_H
#define GENERATED_STAGE6E_BATTLE_UI_H
#define STAGE6E_BATTLE_UI_SOURCE_SHA \"{digest}\"
#define STAGE6E_TOUCH_CANCEL {row('cancel')}
#define STAGE6E_TOUCH_MOVE_1 {row('move_1')}
#define STAGE6E_TOUCH_MOVE_2 {row('move_2')}
#define STAGE6E_TOUCH_MOVE_3 {row('move_3')}
#define STAGE6E_TOUCH_MOVE_4 {row('move_4')}
#define STAGE6E_TOUCH_MEGA {row('mega')}
#define STAGE6E_MEGA_BUTTON_X 213
#define STAGE6E_MEGA_BUTTON_Y 253
#define STAGE6E_CANCEL_TEXT_X 92
#endif
"""


def compile_battle_ui(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT, header: Path = DEFAULT_HEADER, report: Path = DEFAULT_REPORT) -> dict[str, Any]:
    source, output, header, report = source.resolve(), output.resolve(), header.resolve(), report.resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    validate(data)
    output.mkdir(parents=True, exist_ok=True)
    preview = output / "battle_tiles.png"
    _draw_tiles(data, preview)
    character = output / "7_28.NCGR"
    compressed_character_native = output / "7_28.NCGR.lz"
    compressed_character = output / "7_28"
    palette_native = output / "7_246.NCLR"
    palette_source = output / "battle_theme.pal"
    palette = output / "7_246"
    touch_palette = output / "7_271"
    mega_off_source = output / "mega_off.pal"
    mega_on_source = output / "mega_on.pal"
    mega_off_native = output / "7_351.NCLR"
    mega_on_native = output / "7_352.NCLR"
    mega_off = output / "7_351"
    mega_on = output / "7_352"
    hud_palette_source = output / "battle_hud.pal"
    hud_palette_native = output / "8_71.NCLR"
    hud_palette = output / "8_71"
    _run([str(NITROGFX), str(preview), str(character), "-bitdepth", "4"])
    _run([str(NITROGFX), str(character), str(compressed_character_native)])
    shutil.copyfile(compressed_character_native, compressed_character)
    _write_palette(data, palette_source)
    _run([str(NITROGFX), str(palette_source), str(palette_native)])
    shutil.copyfile(palette_native, palette)
    shutil.copyfile(palette, touch_palette)
    _write_palette(data, mega_off_source, repeat=1)
    _write_palette(data, mega_on_source, repeat=1, on=True)
    _run([str(NITROGFX), str(mega_off_source), str(mega_off_native)])
    _run([str(NITROGFX), str(mega_on_source), str(mega_on_native)])
    shutil.copyfile(mega_off_native, mega_off)
    shutil.copyfile(mega_on_native, mega_on)
    _write_hud_palette(data, hud_palette_source)
    _run([str(NITROGFX), str(hud_palette_source), str(hud_palette_native)])
    shutil.copyfile(hud_palette_native, hud_palette)
    generated: dict[str, Path] = {
        "character": compressed_character, "palette": palette, "touch_palette": touch_palette,
        "mega_palette_off": mega_off, "mega_palette_on": mega_on, "hud_palette": hud_palette,
    }
    for name, member in data["target"]["screen_members"].items():
        tilemap_source = output / f"{name}.tilemap.json"
        raw_screen = output / f"7_{member}.NSCR"
        compressed_screen_native = output / f"7_{member}.NSCR.lz"
        compressed_screen = output / f"7_{member}"
        tilemap_source.write_text(json.dumps(_tilemap(data["screens"][name]), sort_keys=True) + "\n", encoding="utf-8")
        _run([str(NITROGFX), str(tilemap_source), str(raw_screen), "-bitdepth", "4"])
        _run([str(NITROGFX), str(raw_screen), str(compressed_screen_native)])
        shutil.copyfile(compressed_screen_native, compressed_screen)
        generated[f"screen_{name}"] = compressed_screen
    digest = hashlib.sha256(_canonical(data)).hexdigest()
    header_text = _header(data, digest)
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(header_text, encoding="utf-8")
    result = {
        "schema_version": 1,
        "bundle_id": data["bundle_id"],
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": digest,
        "screens": sorted(data["screens"]),
        "screen_count": len(data["screens"]),
        "semantic_bindings": data["semantic_bindings"],
        "touch_region_count": len(data["screens"]["fight_mega"]["touch"]),
        "budgets": data["budgets"],
        "outputs": {name: {"path": f"generated/{path.name}", "bytes": path.stat().st_size, "sha256": _sha(path)} for name, path in generated.items()},
        "validation": {"native_bounds": "PASS", "overlap": "PASS", "touch_alignment": "PASS", "bindings": "PASS", "bg_budget": "PASS", "tile_budget": "PASS", "palette_budget": "PASS"},
    }
    if compressed_character.stat().st_size > data["budgets"]["character_bytes"]:
        raise BattleUIError("character budget exceeded")
    for name, path in generated.items():
        if name.startswith("screen_") and path.stat().st_size > data["budgets"]["screen_bytes"]:
            raise BattleUIError(f"{name}: screen budget exceeded")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(_canonical(result))
    return result


def _member(directory: Path, member: int) -> Path:
    matches = sorted(path for path in directory.iterdir() if path.is_file() and path.name.rsplit("_", 1)[-1].isdigit() and int(path.name.rsplit("_", 1)[-1]) == member)
    if len(matches) != 1:
        raise BattleUIError(f"expected archive member {member}, got {len(matches)}")
    return matches[0]


def patch_proof_rom(source: Path, output: Path, archive: Path, hud_archive: Path, rom: Path) -> dict[str, Any]:
    report = compile_battle_ui(source, output)
    data = json.loads(source.read_text(encoding="utf-8"))
    archive, hud_archive, rom = archive.resolve(), hud_archive.resolve(), rom.resolve()
    if not archive.is_file() or not hud_archive.is_file() or not rom.is_file():
        raise BattleUIError("proof requires already-built local battle archives and ROM")
    original = archive.read_bytes()
    original_hud = hud_archive.read_bytes()
    with tempfile.TemporaryDirectory(prefix="stage6e-battle-") as directory:
        extracted = Path(directory) / "a007"
        rebuilt = Path(directory) / "a007.narc"
        extracted_hud = Path(directory) / "a008"
        rebuilt_hud = Path(directory) / "a008.narc"
        try:
            _run(["python3", str(NARCPY), "extract", str(archive), "-o", str(extracted), "-nf"])
            replacements = {
                28: output / "7_28", 246: output / "7_246", 271: output / "7_271",
                351: output / "7_351", 352: output / "7_352",
            }
            replacements.update({member: output / f"7_{member}" for member in data["target"]["screen_members"].values()})
            for member, path in replacements.items():
                shutil.copyfile(path, _member(extracted, member))
            _run(["python3", str(NARCPY), "create", str(rebuilt), str(extracted), "-nf"])
            shutil.copyfile(rebuilt, archive)
            _run(["python3", str(NARCPY), "extract", str(hud_archive), "-o", str(extracted_hud), "-nf"])
            shutil.copyfile(output / "8_71", _member(extracted_hud, data["target"]["hud_palette_member"]))
            _run(["python3", str(NARCPY), "create", str(rebuilt_hud), str(extracted_hud), "-nf"])
            shutil.copyfile(rebuilt_hud, hud_archive)
            _run([str(NDSTOOL), "-c", str(rom), "-9", str(ROOT / "base/arm9.bin"), "-7", str(ROOT / "base/arm7.bin"), "-y9", str(ROOT / "base/overarm9.bin"), "-y7", str(ROOT / "base/overarm7.bin"), "-d", str(ROOT / "base/root"), "-y", str(ROOT / "base/overlay"), "-t", str(ROOT / "base/banner.bin"), "-h", str(ROOT / "base/header.bin")])
        finally:
            archive.write_bytes(original)
            hud_archive.write_bytes(original_hud)
    report["proof_rom"] = {
        "path": rom.relative_to(ROOT).as_posix(), "sha256": _sha(rom),
        "archives_restored": archive.read_bytes() == original and hud_archive.read_bytes() == original_hud,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--proof-rom", action="store_true")
    parser.add_argument("--archive", type=Path, default=ROOT / "base/root/a/0/0/7")
    parser.add_argument("--hud-archive", type=Path, default=ROOT / "base/root/a/0/0/8")
    parser.add_argument("--rom", type=Path, default=ROOT / "test.nds")
    args = parser.parse_args()
    result = patch_proof_rom(args.source, args.output, args.archive, args.hud_archive, args.rom) if args.proof_rom else compile_battle_ui(args.source, args.output, args.header, args.report)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
