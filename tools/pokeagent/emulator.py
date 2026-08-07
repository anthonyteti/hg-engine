"""Bounded headless DeSmuME smoke testing for generated HG-Engine ROMs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import struct
import sys
import time

from .command import run_command
from .rom import (
    GENERATED_ROM_NAME,
    PROJECT_ROOT,
    REPORT_DIRECTORY,
    inspect_rom,
    path_is_git_ignored,
    sha256_file,
    utc_now,
    write_json_report,
)


SCREEN_WIDTH = 256
SCREEN_HEIGHT_BOTH = 384
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def smoke_worker_command(
    *,
    root: Path,
    rom_path: Path,
    screenshot_path: Path,
    result_path: Path,
    boot_frames: int,
    input_frames: int,
    post_input_frames: int,
    timeout_seconds: float,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "tools.pokeagent.emulator",
        "--worker",
        "--root",
        str(root),
        "--rom",
        str(rom_path),
        "--screenshot",
        str(screenshot_path),
        "--result",
        str(result_path),
        "--boot-frames",
        str(boot_frames),
        "--input-frames",
        str(input_frames),
        "--post-input-frames",
        str(post_input_frames),
        "--timeout",
        str(timeout_seconds),
    ]


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with Path(path).open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("file is not a valid PNG header")
    return struct.unpack(">II", header[16:24])


def _cycle_with_deadline(emu, frame_count: int, deadline: float) -> None:
    for _ in range(frame_count):
        if time.monotonic() >= deadline:
            raise TimeoutError("emulator worker exceeded its wall-clock deadline")
        emu.cycle(False)


def _run_worker(
    *,
    rom_path: Path,
    screenshot_path: Path,
    result_path: Path,
    boot_frames: int,
    input_frames: int,
    post_input_frames: int,
    timeout_seconds: float,
) -> int:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    started = time.monotonic()
    deadline = started + timeout_seconds
    emu = None
    payload: dict[str, object] = {
        "schema_version": 1,
        "operation": "rom_smoke_worker",
        "created_at": utc_now(),
        "success": False,
        "rom": str(rom_path),
        "screenshot": str(screenshot_path),
        "frames": {
            "boot": boot_frames,
            "input": input_frames,
            "post_input": post_input_frames,
            "total": boot_frames + input_frames + post_input_frames,
        },
        "input": {"button": "A", "pressed_frames": input_frames},
    }

    try:
        from desmume.controls import Keys, keymask
        from desmume.emulator import DeSmuME

        emu = DeSmuME()
        emu.open(str(rom_path))
        _cycle_with_deadline(emu, boot_frames, deadline)

        a_key = keymask(Keys.KEY_A)
        emu.input.keypad_add_key(a_key)
        try:
            _cycle_with_deadline(emu, input_frames, deadline)
        finally:
            emu.input.keypad_rm_key(a_key)
        _cycle_with_deadline(emu, post_input_frames, deadline)

        image = emu.screenshot().convert("RGB")
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(screenshot_path, format="PNG")

        pixel_bytes = image.tobytes()
        pixels = [pixel_bytes[index : index + 3] for index in range(0, len(pixel_bytes), 3)]
        colors = set(pixels)
        non_black_pixels = sum(1 for pixel in pixels if pixel != b"\0\0\0")
        dimensions_ok = image.size == (SCREEN_WIDTH, SCREEN_HEIGHT_BOTH)
        meaningful_frame = non_black_pixels > 0 and len(colors) > 1
        payload.update(
            {
                "success": dimensions_ok and meaningful_frame,
                "running_after_cycles": bool(emu.is_running()),
                "screenshot_result": {
                    "width": image.width,
                    "height": image.height,
                    "sha256": sha256_file(screenshot_path),
                    "pixel_sha256": hashlib.sha256(pixel_bytes).hexdigest(),
                    "unique_colors": len(colors),
                    "non_black_pixels": non_black_pixels,
                    "dimensions_ok": dimensions_ok,
                    "meaningful_frame": meaningful_frame,
                },
                "py_desmume_version": importlib.metadata.version("py-desmume"),
            }
        )
        if not payload["success"]:
            payload["error"] = "captured frame was blank or had unexpected dimensions"
    except Exception as error:  # Worker boundary must always emit a structured failure.
        payload.update(
            {
                "success": False,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
    finally:
        if emu is not None:
            try:
                emu.destroy()
            except Exception as error:
                payload.setdefault("cleanup_error", str(error))
        payload["duration_seconds"] = round(time.monotonic() - started, 6)
        payload["completed_at"] = utc_now()
        write_json_report(result_path, payload)

    return 0 if payload["success"] else 1


def run_smoke(
    root: Path = PROJECT_ROOT,
    *,
    boot_frames: int = 180,
    input_frames: int = 3,
    post_input_frames: int = 30,
    timeout_seconds: float = 30,
) -> dict[str, object]:
    root = Path(root).resolve()
    rom_path = root / GENERATED_ROM_NAME
    artifact_dir = root / REPORT_DIRECTORY
    screenshot_path = artifact_dir / "smoke.png"
    report_path = artifact_dir / "smoke-report.json"
    log_path = artifact_dir / "smoke.log"
    worker_result_path = artifact_dir / ".smoke-worker-result.json"
    errors: list[str] = []

    report: dict[str, object] = {
        "schema_version": 1,
        "operation": "rom_smoke",
        "created_at": utc_now(),
        "project_root": str(root),
        "success": False,
        "rom": inspect_rom(rom_path),
        "artifacts": {
            "report": str(report_path),
            "log": str(log_path),
            "screenshot": str(screenshot_path),
        },
        "errors": errors,
    }

    unsafe_artifacts = [
        path
        for path in (screenshot_path, report_path, log_path, worker_result_path)
        if path_is_git_ignored(root, path) is not True
    ]
    if unsafe_artifacts:
        errors.append(
            "refusing to write non-ignored smoke artifacts: "
            + ", ".join(str(path) for path in unsafe_artifacts)
        )
        return report
    if not report["rom"]["exists"]:
        errors.append(f"generated ROM is missing: {rom_path}")
        write_json_report(report_path, report)
        return report
    if not report["rom"]["supported"]:
        errors.append(
            f"generated ROM game code {report['rom'].get('game_code')!r} is unsupported"
        )
        write_json_report(report_path, report)
        return report
    if min(boot_frames, input_frames, post_input_frames) < 1:
        errors.append("all frame counts must be positive")
        write_json_report(report_path, report)
        return report
    if timeout_seconds <= 0:
        errors.append("timeout must be positive")
        write_json_report(report_path, report)
        return report

    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path.unlink(missing_ok=True)
    worker_result_path.unlink(missing_ok=True)
    command = smoke_worker_command(
        root=root,
        rom_path=rom_path,
        screenshot_path=screenshot_path,
        result_path=worker_result_path,
        boot_frames=boot_frames,
        input_frames=input_frames,
        post_input_frames=post_input_frames,
        timeout_seconds=max(1, timeout_seconds - 1),
    )
    command_result = run_command(
        command,
        cwd=root,
        timeout_seconds=timeout_seconds,
        log_path=log_path,
        env_overrides={"SDL_VIDEODRIVER": "dummy"},
    )

    worker_result: dict[str, object] | None = None
    if worker_result_path.is_file():
        try:
            worker_result = json.loads(worker_result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"worker result is unreadable: {error}")
    else:
        errors.append("emulator worker did not produce a structured result")

    if not command_result.succeeded:
        errors.append(
            "emulator worker timed out"
            if command_result.timed_out
            else f"emulator worker exited {command_result.exit_code}"
        )
    if worker_result is not None and not worker_result.get("success"):
        errors.append(f"emulator smoke failed: {worker_result.get('error', 'unknown error')}")

    screenshot_result: dict[str, object] | None = None
    if screenshot_path.is_file():
        try:
            width, height = read_png_dimensions(screenshot_path)
            screenshot_result = {
                "path": str(screenshot_path),
                "size_bytes": screenshot_path.stat().st_size,
                "sha256": sha256_file(screenshot_path),
                "width": width,
                "height": height,
                "valid_dimensions": (width, height) == (SCREEN_WIDTH, SCREEN_HEIGHT_BOTH),
            }
            if not screenshot_result["valid_dimensions"]:
                errors.append(f"unexpected screenshot dimensions: {width}x{height}")
            worker_hash = (worker_result or {}).get("screenshot_result", {}).get("sha256")
            if worker_hash and worker_hash != screenshot_result["sha256"]:
                errors.append("screenshot hash does not match the worker result")
        except (OSError, ValueError) as error:
            errors.append(f"invalid screenshot: {error}")
    else:
        errors.append("emulator worker did not produce a screenshot")

    worker_result_path.unlink(missing_ok=True)
    report.update(
        {
            "command": command_result.to_dict(),
            "worker": worker_result,
            "screenshot": screenshot_result,
            "success": not errors,
            "completed_at": utc_now(),
        }
    )
    write_json_report(report_path, report)
    return report


def _worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--boot-frames", type=int, required=True)
    parser.add_argument("--input-frames", type=int, required=True)
    parser.add_argument("--post-input-frames", type=int, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    return parser


def _worker_main(argv: list[str] | None = None) -> int:
    args = _worker_parser().parse_args(argv)
    return _run_worker(
        rom_path=args.rom,
        screenshot_path=args.screenshot,
        result_path=args.result,
        boot_frames=args.boot_frames,
        input_frames=args.input_frames,
        post_input_frames=args.post_input_frames,
        timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(_worker_main())
