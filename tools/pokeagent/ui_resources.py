"""Deterministic project-owned Nintendo DS UI resource compiler."""

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
DEFAULT_SOURCE = ROOT / "presentation/ui/resources/stage6c_start_menu.json"
DEFAULT_OUTPUT = ROOT / "build/stage6c/ui_resources"
NITROGFX = ROOT / "tools/nitrogfx"
NARCPY = ROOT / "tools/narcpy.py"
NDSTOOL = ROOT / "tools/ndstool"


class UIResourceError(ValueError):
    pass


def _hex_color(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise UIResourceError(f"invalid color {value!r}")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    except ValueError as exc:
        raise UIResourceError(f"invalid color {value!r}") from exc


def validate(source: dict[str, Any]) -> None:
    if source.get("schema_version") != 1:
        raise UIResourceError("unsupported UI resource schema")
    if not isinstance(source.get("bundle_id"), str) or not source["bundle_id"].startswith("ui."):
        raise UIResourceError("bundle_id must be a symbolic ui.* identity")
    sheet = source.get("sheet", {})
    if sheet != {
        "width": 256,
        "height": 32,
        "bit_depth": 4,
        "transparency_index": 0,
        "tile_count": 32,
    }:
        raise UIResourceError("Stage 6C proof sheet must be 256x32, 4bpp and 32 tiles")
    palette = source.get("palette", [])
    if not 1 <= len(palette) <= source.get("budgets", {}).get("max_palette_colors", 0):
        raise UIResourceError("palette exceeds its declared budget")
    colors = [_hex_color(value) for value in palette]
    if len(colors) != len(set(colors)):
        raise UIResourceError("palette colors must be unique")
    components = source.get("components", [])
    ids = [row.get("id") for row in components]
    if len(ids) < 3 or len(ids) != len(set(ids)) or not all(isinstance(value, str) and value.startswith("ui.") for value in ids):
        raise UIResourceError("components require at least three unique symbolic ui.* identities")
    covered: list[int] = []
    for component in components:
        if component.get("pattern") not in {"field_window", "tide_gradient", "paper_guide", "shore_accent"}:
            raise UIResourceError(f"unknown component pattern for {component.get('id')}")
        for tile in component.get("tiles", []):
            if not isinstance(tile, int) or not 0 <= tile < sheet["tile_count"]:
                raise UIResourceError(f"component {component.get('id')} has invalid tile")
            covered.append(tile)
    if sorted(covered) != list(range(8)) or len(covered) != len(set(covered)):
        raise UIResourceError("proof component tiles must cover 0..7 exactly once")
    layout = source.get("layout", {})
    if layout.get("width_tiles") != 32 or layout.get("height_tiles") != 24:
        raise UIResourceError("proof tilemap must target the 256x192 native screen")
    rows = layout.get("row_tiles", [])
    if len(rows) != 24 or any(not isinstance(tile, int) or tile not in covered for tile in rows):
        raise UIResourceError("layout must define 24 valid tile rows")
    target = source.get("target", {})
    if target.get("archive") != "a/0/1/4" or target.get("palette_slot") != 14:
        raise UIResourceError("proof target does not match the audited start-menu resource contract")
    members = [target.get(key) for key in ("character_member", "screen_member", "palette_member")]
    if members != [12, 13, 15] or len(set(members)) != 3:
        raise UIResourceError("proof target members must be the audited 12/13/15 triple")


def _draw_sheet(source: dict[str, Any], path: Path) -> None:
    palette = [_hex_color(value) for value in source["palette"]]
    image = Image.new("P", (256, 32), 0)
    flattened: list[int] = []
    for color in palette:
        flattened.extend(color)
    flattened.extend([0] * (768 - len(flattened)))
    image.putpalette(flattened)
    pixels = image.load()
    assert pixels is not None
    # Tile 0 preserves the ordinary field view behind the start menu.
    for y in range(8):
        for x in range(8):
            pixels[x, y] = 0
    # Tiles 1..3: a restrained cool tide from the main field to the footer.
    tide = [(2, 3), (3, 4), (4, 5)]
    for tile, (top, bottom) in enumerate(tide, start=1):
        for y in range(8):
            color = top if y < 4 else bottom
            for x in range(8):
                pixels[tile * 8 + x, y] = 13 if y == 0 and (x % 4 == 0) else color
    # Tiles 4..5: the warm journal-paper bridge.
    paper = [(6, 7, 13), (7, 8, 14)]
    for tile, (top, bottom, guide) in enumerate(paper, start=4):
        for y in range(8):
            for x in range(8):
                pixels[tile * 8 + x, y] = guide if y == 0 and x % 4 == 0 else (top if y < 4 else bottom)
    # Tiles 6..7: copper shoreline accent that terminates in warm paper.
    shore = [(7, 8, 11), (8, 9, 12)]
    for tile, (top, bottom, accent) in enumerate(shore, start=6):
        for y in range(8):
            color = top if y < 4 else bottom
            for x in range(8):
                pixels[tile * 8 + x, y] = accent if y == 3 else color
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=False)


def _tilemap_json(source: dict[str, Any]) -> dict[str, Any]:
    tile_count = source["sheet"]["tile_count"]
    palette_slot = source["target"]["palette_slot"]
    data = []
    for tile in source["layout"]["row_tiles"]:
        gid = palette_slot * tile_count + tile + 1
        data.extend([gid] * source["layout"]["width_tiles"])
    return {
        "height": source["layout"]["height_tiles"],
        "width": source["layout"]["width_tiles"],
        "layers": [{"data": data}],
        "tilesets": [{"firstgid": 1}, {"firstgid": tile_count + 1}],
    }


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise UIResourceError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout}{completed.stderr}"
        )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path, output_dir: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return f"generated/{path.relative_to(output_dir).as_posix()}"


def compile_resources(
    source_path: Path = DEFAULT_SOURCE,
    output_dir: Path = DEFAULT_OUTPUT,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_dir = output_dir.resolve()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    validate(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    preview = output_dir / "start_menu_chrome.png"
    tilemap_json = output_dir / "start_menu_chrome.tilemap.json"
    character = output_dir / "start_menu_chrome.NCGR"
    compressed_character = output_dir / "start_menu_chrome.NCGR.lz"
    screen = output_dir / "start_menu_chrome.NSCR"
    compressed_screen = output_dir / "start_menu_chrome.NSCR.lz"
    palette = output_dir / "start_menu_chrome.NCLR"
    _draw_sheet(source, preview)
    tilemap_json.write_text(json.dumps(_tilemap_json(source), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _run([str(NITROGFX), str(preview), str(character), "-bitdepth", "4"])
    _run([str(NITROGFX), str(character), str(compressed_character)])
    _run([str(NITROGFX), str(tilemap_json), str(screen), "-bitdepth", "4"])
    _run([str(NITROGFX), str(screen), str(compressed_screen)])
    _run([str(NITROGFX), str(preview), str(palette), "-bitdepth", "4"])
    outputs = {
        "preview": preview,
        "tilemap_source": tilemap_json,
        "character": compressed_character,
        "screen": compressed_screen,
        "palette": palette,
    }
    budgets = source["budgets"]
    if len(compressed_character.read_bytes()) > budgets["max_character_bytes"]:
        raise UIResourceError("compiled character resource exceeds budget")
    if len(compressed_screen.read_bytes()) > budgets["max_screen_bytes"]:
        raise UIResourceError("compiled screen resource exceeds budget")
    if len(palette.read_bytes()) > budgets["max_palette_bytes"]:
        raise UIResourceError("compiled palette resource exceeds budget")
    if compressed_character.read_bytes()[:1] != b"\x10" or compressed_screen.read_bytes()[:1] != b"\x10":
        raise UIResourceError("character and screen outputs must use Nitro LZ compression")
    if palette.read_bytes()[:4] != b"RLCN":
        raise UIResourceError("palette output is not NCLR")
    report = {
        "schema_version": 1,
        "bundle_id": source["bundle_id"],
        "source": source_path.relative_to(ROOT).as_posix(),
        "source_sha256": _sha(source_path),
        "components": [row["id"] for row in source["components"]],
        "target": source["target"],
        "outputs": {
            key: {
                "path": _display_path(path, output_dir),
                "bytes": path.stat().st_size,
                "sha256": _sha(path),
            }
            for key, path in outputs.items()
        },
        "validation": {
            "native_dimensions": "PASS",
            "palette_depth": "PASS",
            "tile_budget": "PASS",
            "palette_budget": "PASS",
            "archive_members_unique": "PASS",
            "deterministic": "REQUIRES_TWO_ROOT_COMPARISON"
        }
    }
    report_path = output_dir / "manifest.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if catalog_path is not None:
        catalog_path = catalog_path.resolve()
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _member_path(directory: Path, member: int) -> Path:
    matches = sorted(directory.glob(f"*_{member:02d}"))
    if len(matches) != 1:
        raise UIResourceError(f"expected one extracted archive member {member}, found {len(matches)}")
    return matches[0]


def build_proof_rom(source_path: Path, output_dir: Path, archive: Path, rom: Path) -> dict[str, Any]:
    report = compile_resources(source_path, output_dir)
    archive = archive.resolve()
    rom = rom.resolve()
    if not archive.is_file():
        raise UIResourceError(f"missing local common UI archive: {archive}")
    original = archive.read_bytes()
    with tempfile.TemporaryDirectory(prefix="stage6c-ui-") as directory:
        extracted = Path(directory) / "archive"
        rebuilt = Path(directory) / "a014.narc"
        try:
            _run(["python3", str(NARCPY), "extract", str(archive), "-o", str(extracted), "-nf"])
            mapping = {
                12: output_dir / "start_menu_chrome.NCGR.lz",
                13: output_dir / "start_menu_chrome.NSCR.lz",
                15: output_dir / "start_menu_chrome.NCLR",
            }
            for member, source in mapping.items():
                shutil.copyfile(source, _member_path(extracted, member))
            _run(["python3", str(NARCPY), "create", str(rebuilt), str(extracted), "-nf"])
            shutil.copyfile(rebuilt, archive)
            _run([
                str(NDSTOOL), "-c", str(rom),
                "-9", str(ROOT / "base/arm9.bin"), "-7", str(ROOT / "base/arm7.bin"),
                "-y9", str(ROOT / "base/overarm9.bin"), "-y7", str(ROOT / "base/overarm7.bin"),
                "-d", str(ROOT / "base/root"), "-y", str(ROOT / "base/overlay"),
                "-t", str(ROOT / "base/banner.bin"), "-h", str(ROOT / "base/header.bin"),
            ])
        finally:
            archive.write_bytes(original)
    report["proof_rom"] = {
        "path": rom.relative_to(ROOT).as_posix(),
        "bytes": rom.stat().st_size,
        "sha256": _sha(rom),
        "archive_restored": archive.read_bytes() == original,
    }
    (output_dir / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--proof-rom", action="store_true")
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--archive", type=Path, default=ROOT / "base/root/a/0/1/4")
    parser.add_argument("--rom", type=Path, default=ROOT / "test.nds")
    args = parser.parse_args()
    if args.proof_rom:
        report = build_proof_rom(args.source, args.output, args.archive, args.rom)
    else:
        report = compile_resources(args.source, args.output, args.catalog)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
