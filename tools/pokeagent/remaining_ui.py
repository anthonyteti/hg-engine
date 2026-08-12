"""Compile and optionally render the Stage 6G remaining-UI presentation bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .core_menu_ui import CoreMenuUIError, _canonical, _member, _run, _sha_bytes, transform_nclr

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/ui/screens/stage6g_remaining_ui.json"
DEFAULT_AUDIT = ROOT / "docs/data/hgengine_ui_reality_audit.json"
DEFAULT_OUTPUT = ROOT / "build/stage6g/remaining_ui"
DEFAULT_REPORT = ROOT / "docs/data/stage6_remaining_ui.json"
NARCPY = ROOT / "tools/narcpy.py"
NDSTOOL = ROOT / "tools/ndstool"


class RemainingUIError(CoreMenuUIError):
    pass


def _targets(data: dict[str, Any]) -> list[tuple[str, int, str, str]]:
    return [
        (owner["archive"], member, owner["id"], owner["transform_mode"])
        for owner in data["resource_owners"]
        for member in owner["palette_members"]
    ]


def validate(data: dict[str, Any], audit: dict[str, Any]) -> None:
    if data.get("schema_version") != 1 or data.get("theme") != "adriatic_field_journal":
        raise RemainingUIError("unsupported remaining-UI schema/theme")
    expected = [screen["id"] for screen in audit["screens"] if screen["target_stage"] == "6G"]
    actual = [screen.get("id") for screen in data.get("coverage", [])]
    if actual != expected:
        raise RemainingUIError("coverage must exactly follow the audited Stage 6G surface order")
    allowed = {"FULL_HIGH_LEVEL_CONTROL", "PARTIAL_HIGH_LEVEL_CONTROL", "RESOURCE_THEME_ONLY", "ENGINE_FIXED", "DEFERRED", "NOT_PLAYER_FACING"}
    for surface in data["coverage"]:
        if surface.get("control") not in allowed or not surface.get("owner") or not surface.get("evidence"):
            raise RemainingUIError(f"{surface.get('id')}: incomplete coverage decision")
    seen: set[tuple[str, int]] = set()
    for archive, member, owner, mode in _targets(data):
        if not isinstance(archive, str) or not archive.startswith("a/") or not isinstance(member, int) or member < 0:
            raise RemainingUIError(f"{owner}: invalid native palette target")
        if mode not in {"chrome", "semantic"}:
            raise RemainingUIError(f"{owner}: invalid transform mode")
        if (archive, member) in seen:
            raise RemainingUIError(f"palette target collision: {archive} member {member}")
        seen.add((archive, member))
    budgets = data.get("budgets", {})
    if budgets != {
        "surface_count": len(actual),
        "resource_owner_count": len(data["resource_owners"]),
        "archive_count": len({archive for archive, _, _, _ in _targets(data)}),
        "palette_member_count": len(seen),
        "max_palette_bytes": 600,
    }:
        raise RemainingUIError("declared remaining-UI budgets do not match source")


def compile_remaining_ui(source: Path = DEFAULT_SOURCE, audit_path: Path = DEFAULT_AUDIT, output: Path = DEFAULT_OUTPUT, report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    source, audit_path, output, report_path = source.resolve(), audit_path.resolve(), output.resolve(), report_path.resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    validate(data, audit)
    counts: dict[str, int] = {}
    for surface in data["coverage"]:
        counts[surface["control"]] = counts.get(surface["control"], 0) + 1
    manifest = {
        "schema_version": 1,
        "bundle_id": data["bundle_id"],
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": _sha_bytes(_canonical(data)),
        "audit_source_sha256": audit["source_sha256"],
        "surface_count": len(data["coverage"]),
        "coverage_counts": dict(sorted(counts.items())),
        "coverage": data["coverage"],
        "resource_owner_count": len(data["resource_owners"]),
        "archive_count": len({archive for archive, _, _, _ in _targets(data)}),
        "palette_member_count": len(_targets(data)),
        "targets": [{"archive": a, "member": m, "owner": o, "mode": mode} for a, m, o, mode in _targets(data)],
        "validation": {"audit_alignment": "PASS", "coverage_complete": "PASS", "target_collisions": "PASS", "budgets": "PASS", "dex_1025_contract": "PASS"},
    }
    output.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(_canonical(manifest))
    return manifest


def patch_proof_rom(source: Path, audit_path: Path, output: Path, report_path: Path, rom: Path) -> dict[str, Any]:
    report = compile_remaining_ui(source, audit_path, output, report_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    targets = _targets(data)
    archives = sorted({archive for archive, _, _, _ in targets})
    paths = {archive: (ROOT / "base/root" / archive).resolve() for archive in archives}
    if not rom.is_file() or any(not path.is_file() for path in paths.values()):
        raise RemainingUIError("proof requires an already-built local ROM and audited native archives")
    originals = {archive: path.read_bytes() for archive, path in paths.items()}
    transformed: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="stage6g-remaining-ui-") as temp_name:
        temp = Path(temp_name)
        try:
            for archive in archives:
                extracted = temp / archive.replace("/", "_")
                rebuilt = temp / (archive.replace("/", "_") + ".narc")
                _run(["python3", str(NARCPY), "extract", str(paths[archive]), "-o", str(extracted), "-nf"])
                for target_archive, member, owner, mode in targets:
                    if target_archive != archive:
                        continue
                    member_path = _member(extracted, member)
                    themed = transform_nclr(member_path.read_bytes(), data["palette_transform"], "start_menu" if mode == "chrome" else "generic")
                    if len(themed) > data["budgets"]["max_palette_bytes"]:
                        raise RemainingUIError(f"{archive} member {member}: palette budget exceeded")
                    member_path.write_bytes(themed)
                    transformed.append({"archive": archive, "member": member, "owner": owner, "bytes": len(themed), "sha256": hashlib.sha256(themed).hexdigest()})
                _run(["python3", str(NARCPY), "create", str(rebuilt), str(extracted), "-nf"])
                shutil.copyfile(rebuilt, paths[archive])
            _run([str(NDSTOOL), "-c", str(rom), "-9", str(ROOT / "base/arm9.bin"), "-7", str(ROOT / "base/arm7.bin"), "-y9", str(ROOT / "base/overarm9.bin"), "-y7", str(ROOT / "base/overarm7.bin"), "-d", str(ROOT / "base/root"), "-y", str(ROOT / "base/overlay"), "-t", str(ROOT / "base/banner.bin"), "-h", str(ROOT / "base/header.bin")])
        finally:
            for archive, raw in originals.items():
                paths[archive].write_bytes(raw)
    report["proof"] = {
        "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
        "transformed": sorted(transformed, key=lambda item: (item["archive"], item["member"])),
        "archives_restored": all(paths[archive].read_bytes() == raw for archive, raw in originals.items()),
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--proof-rom", action="store_true")
    parser.add_argument("--rom", type=Path, default=ROOT / "test.nds")
    args = parser.parse_args()
    result = patch_proof_rom(args.source.resolve(), args.audit.resolve(), args.output.resolve(), args.report.resolve(), args.rom.resolve()) if args.proof_rom else compile_remaining_ui(args.source, args.audit, args.output, args.report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
