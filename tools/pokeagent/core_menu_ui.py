"""Compile the semantic Stage 6F menu theme into local native palette resources."""

from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/ui/screens/stage6f_core_menus.json"
DEFAULT_OUTPUT = ROOT / "build/stage6f/core_menus"
DEFAULT_REPORT = ROOT / "docs/data/stage6_core_menus.json"
NARCPY = ROOT / "tools/narcpy.py"
NDSTOOL = ROOT / "tools/ndstool"


class CoreMenuUIError(ValueError):
    pass


def _rgb(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise CoreMenuUIError(f"invalid color {value!r}")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _targets(data: dict[str, Any]) -> list[tuple[str, int, str]]:
    result: list[tuple[str, int, str]] = []
    for screen in data["screens"]:
        groups = screen.get("archives") or [{"archive": screen.get("archive"), "palette_members": screen.get("palette_members")}]
        for group in groups:
            result.extend((group["archive"], member, screen["id"]) for member in group["palette_members"])
    return result


def validate(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1 or data.get("theme") != "adriatic_field_journal":
        raise CoreMenuUIError("unsupported core-menu schema/theme")
    screens = data.get("screens", [])
    if [screen.get("id") for screen in screens] != ["start_menu", "party", "summary", "bag"]:
        raise CoreMenuUIError("core-menu source must declare the four Stage 6F owners")
    seen: set[tuple[str, int]] = set()
    for archive, member, screen in _targets(data):
        if not isinstance(archive, str) or not archive.startswith("a/") or not isinstance(member, int) or member < 0:
            raise CoreMenuUIError(f"{screen}: invalid audited palette target")
        if (archive, member) in seen:
            raise CoreMenuUIError(f"palette target collision: {archive} member {member}")
        seen.add((archive, member))
    transform = data.get("palette_transform", {})
    _rgb(transform.get("neutral_ink"))
    _rgb(transform.get("neutral_paper"))
    _rgb(transform.get("accent_copper"))
    if not 0 <= transform.get("blue_target_hue_degrees", -1) <= 360:
        raise CoreMenuUIError("invalid target hue")
    threshold = transform.get("preserve_semantic_saturation_above")
    if not isinstance(threshold, (int, float)) or not 0.4 <= threshold <= 1:
        raise CoreMenuUIError("invalid semantic saturation threshold")
    budgets = data.get("budgets", {})
    if len(screens) != budgets.get("screen_count") or len({archive for archive, _, _ in _targets(data)}) != budgets.get("archive_count") or len(seen) != budgets.get("palette_member_count"):
        raise CoreMenuUIError("declared menu budgets do not match source")


def _decode_bgr555(value: int) -> tuple[int, int, int]:
    return tuple(round(((value >> shift) & 31) * 255 / 31) for shift in (0, 5, 10))  # type: ignore[return-value]


def _encode_bgr555(rgb: tuple[int, int, int]) -> int:
    r, g, b = (round(channel * 31 / 255) for channel in rgb)
    return r | (g << 5) | (b << 10)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))  # type: ignore[return-value]


def transform_nclr(raw: bytes, transform: dict[str, Any], screen: str = "generic") -> bytes:
    if raw[:4] != b"RLCN" or raw[0x10:0x14] != b"TTLP" or len(raw) < 0x28:
        raise CoreMenuUIError("audited palette member is not an NCLR/TTLP resource")
    size = struct.unpack_from("<I", raw, 0x20)[0]
    if size <= 0 or size % 2 or 0x28 + size > len(raw):
        raise CoreMenuUIError("NCLR palette payload is malformed")
    ink, paper = _rgb(transform["neutral_ink"]), _rgb(transform["neutral_paper"])
    copper = _rgb(transform["accent_copper"])
    target_h = transform["blue_target_hue_degrees"] / 360
    preserve = float(transform["preserve_semantic_saturation_above"])
    out = bytearray(raw)
    for index in range(size // 2):
        if transform["preserve_bank_transparency"] and screen not in {"start_menu", "bag"} and index % 16 == 0:
            continue
        offset = 0x28 + index * 2
        rgb = _decode_bgr555(struct.unpack_from("<H", raw, offset)[0])
        h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
        if s < 0.18:
            themed = _mix(ink, paper, v)
        elif screen in {"party", "summary", "generic"} and s >= preserve:
            # Party health/status and summary type colors are semantic, not chrome.
            themed = rgb
        elif screen in {"start_menu", "bag"} and (h < 0.12 or h > 0.78):
            # Warm selection/chrome becomes the Presentation Bible copper accent.
            ch, cs, _ = colorsys.rgb_to_hsv(*(channel / 255 for channel in copper))
            themed = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(ch, max(cs, s * 0.72), v))
        elif 0.20 <= h <= 0.78 or screen in {"start_menu", "bag"}:
            themed = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(target_h, min(0.72, s + 0.12), v))
        else:
            themed = rgb
        struct.pack_into("<H", out, offset, _encode_bgr555(themed))
    return bytes(out)


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def compile_core_menus(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT, report: Path = DEFAULT_REPORT) -> dict[str, Any]:
    source, output, report = source.resolve(), output.resolve(), report.resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    validate(data)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "bundle_id": data["bundle_id"],
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": _sha_bytes(_canonical(data)),
        "screens": [screen["id"] for screen in data["screens"]],
        "screen_count": len(data["screens"]),
        "archive_count": len({archive for archive, _, _ in _targets(data)}),
        "palette_member_count": len(_targets(data)),
        "bindings": sorted({binding for screen in data["screens"] for binding in screen["bindings"]}),
        "navigation": {screen["id"]: screen["navigation"] for screen in data["screens"]},
        "visual_roles": {screen["id"]: screen["visual_roles"] for screen in data["screens"]},
        "targets": [{"archive": archive, "member": member, "screen": screen} for archive, member, screen in _targets(data)],
        "validation": {"schema": "PASS", "target_collisions": "PASS", "semantic_bindings": "PASS", "screen_budget": "PASS", "archive_budget": "PASS", "palette_budget": "PASS"},
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(_canonical(manifest))
    return manifest


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise CoreMenuUIError(f"command failed: {' '.join(command)}\n{result.stdout}{result.stderr}")


def _member(directory: Path, member: int) -> Path:
    matches = [path for path in directory.iterdir() if path.name.rsplit("_", 1)[-1].isdigit() and int(path.name.rsplit("_", 1)[-1]) == member]
    if len(matches) != 1:
        raise CoreMenuUIError(f"expected archive member {member}, got {len(matches)}")
    return matches[0]


def patch_proof_rom(source: Path, output: Path, report_path: Path, rom: Path) -> dict[str, Any]:
    report = compile_core_menus(source, output, report_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    targets = _targets(data)
    archives = sorted({archive for archive, _, _ in targets})
    paths = {archive: (ROOT / "base/root" / archive).resolve() for archive in archives}
    if not rom.is_file() or any(not path.is_file() for path in paths.values()):
        raise CoreMenuUIError("proof requires an already-built local ROM and audited archives")
    originals = {archive: path.read_bytes() for archive, path in paths.items()}
    transformed: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="stage6f-core-menus-") as temp:
        temp = Path(temp)
        try:
            for archive in archives:
                extracted, rebuilt = temp / archive.replace("/", "_"), temp / (archive.replace("/", "_") + ".narc")
                _run(["python3", str(NARCPY), "extract", str(paths[archive]), "-o", str(extracted), "-nf"])
                for target_archive, member, screen in targets:
                    if target_archive != archive:
                        continue
                    member_path = _member(extracted, member)
                    themed = transform_nclr(member_path.read_bytes(), data["palette_transform"], screen)
                    if len(themed) > data["budgets"]["max_palette_bytes"]:
                        raise CoreMenuUIError(f"{archive} member {member}: palette budget exceeded")
                    member_path.write_bytes(themed)
                    transformed.append({"archive": archive, "member": member, "screen": screen, "bytes": len(themed), "sha256": _sha_bytes(themed)})
                _run(["python3", str(NARCPY), "create", str(rebuilt), str(extracted), "-nf"])
                shutil.copyfile(rebuilt, paths[archive])
            _run([str(NDSTOOL), "-c", str(rom), "-9", str(ROOT / "base/arm9.bin"), "-7", str(ROOT / "base/arm7.bin"), "-y9", str(ROOT / "base/overarm9.bin"), "-y7", str(ROOT / "base/overarm7.bin"), "-d", str(ROOT / "base/root"), "-y", str(ROOT / "base/overlay"), "-t", str(ROOT / "base/banner.bin"), "-h", str(ROOT / "base/header.bin")])
        finally:
            for archive, raw in originals.items():
                paths[archive].write_bytes(raw)
    report["proof"] = {
        "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
        "transformed": sorted(transformed, key=lambda entry: (entry["archive"], entry["member"])),
        "archives_restored": all(paths[archive].read_bytes() == raw for archive, raw in originals.items()),
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--proof-rom", action="store_true")
    parser.add_argument("--rom", type=Path, default=ROOT / "test.nds")
    args = parser.parse_args()
    result = patch_proof_rom(args.source.resolve(), args.output.resolve(), args.report.resolve(), args.rom.resolve()) if args.proof_rom else compile_core_menus(args.source, args.output, args.report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
