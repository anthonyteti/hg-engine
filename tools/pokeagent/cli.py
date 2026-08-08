"""Command-line surface for HG-Engine build, generation, and emulator checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

from .emulator import run_smoke
from .registry import (
    DEFAULT_INVENTORY,
    DEFAULT_REGISTRY,
    RegistryError,
    load_registry,
    resolve_symbol,
    verify_rom_revision,
    write_inventory,
)
from .rom import PROJECT_ROOT, build_rom, run_preflight
from .world import DEFAULT_FIXTURE, DEFAULT_OUTPUT, generate_world, load_fixture, verify_determinism
from .world_emulator import run_world_test


def _add_output_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the complete machine-readable result instead of the compact human summary",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.pokeagent",
        description="HG-Engine Stage 1 build and emulator orchestration",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser(
        "preflight", help="verify local tools, ROM identity, and artifact safety"
    )
    _add_output_argument(preflight_parser)

    rom_parser = subparsers.add_parser("rom", help="build or smoke-test the generated ROM")
    rom_subparsers = rom_parser.add_subparsers(dest="rom_command", required=True)

    build_parser_ = rom_subparsers.add_parser("build", help="delegate the ROM build to Make")
    build_parser_.add_argument("--jobs", type=int, default=None, help="parallel Make jobs")
    build_parser_.add_argument(
        "--timeout", type=float, default=1200, help="hard build timeout in seconds"
    )
    _add_output_argument(build_parser_)

    smoke_parser = rom_subparsers.add_parser(
        "smoke", help="boot test.nds headlessly, inject input, and capture a frame"
    )
    smoke_parser.add_argument("--boot-frames", type=int, default=180)
    smoke_parser.add_argument("--input-frames", type=int, default=3)
    smoke_parser.add_argument("--post-input-frames", type=int, default=30)
    smoke_parser.add_argument("--timeout", type=float, default=30)
    _add_output_argument(smoke_parser)

    map_parser = subparsers.add_parser("map", help="generate a bounded world proof fixture")
    map_subparsers = map_parser.add_subparsers(dest="map_command", required=True)
    for command, help_text in (
        ("validate", "validate the canonical proof fixture"),
        ("generate", "generate proof artifacts without installing them"),
        ("install", "generate and install proof artifacts into the extracted ROM tree"),
        ("determinism", "generate twice and compare every binary artifact"),
        ("test", "run headless gameplay assertions against the proof map"),
    ):
        child = map_subparsers.add_parser(command, help=help_text)
        child.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
        if command in ("generate", "install"):
            child.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
        if command == "test":
            child.add_argument("--timeout", type=float, default=180)
        _add_output_argument(child)

    registry_parser = subparsers.add_parser("registry", help="validate and inspect stable symbolic IDs")
    registry_subparsers = registry_parser.add_subparsers(dest="registry_command", required=True)
    registry_validate = registry_subparsers.add_parser("validate", help="validate registry structure and ROM coupling")
    registry_validate.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    registry_validate.add_argument("--rom", type=Path, default=PROJECT_ROOT / "rom.nds")
    _add_output_argument(registry_validate)
    registry_inspect = registry_subparsers.add_parser("inspect", help="write a metadata-only slot inventory")
    registry_inspect.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    registry_inspect.add_argument("--rom", type=Path, default=PROJECT_ROOT / "rom.nds")
    registry_inspect.add_argument("--output", type=Path, default=DEFAULT_INVENTORY)
    _add_output_argument(registry_inspect)
    registry_resolve = registry_subparsers.add_parser("resolve", help="resolve one stable symbol")
    registry_resolve.add_argument("symbol")
    registry_resolve.add_argument("--namespace")
    registry_resolve.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    _add_output_argument(registry_resolve)
    return parser


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_preflight(payload: dict[str, object]) -> None:
    print(f"preflight: {'PASS' if payload['success'] else 'FAIL'}")
    for group, result in payload["summary"].items():
        status = "PASS" if result["success"] else "FAIL"
        print(f"  {group}: {status} ({result['passed']}/{result['total']})")
    for check in payload["checks"]:
        if not check["passed"]:
            print(f"  ERROR [{check['group']}.{check['name']}] {check['message']}")
    print(f"  Python: {payload['python_executable']} ({payload['python_version']})")
    print(f"  Supported ROM code: {payload['supported_game_code']}")


def _relative_or_absolute(path: str | None) -> str:
    if path is None:
        return "not written"
    candidate = Path(path)
    try:
        return str(candidate.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(candidate)


def _print_build(payload: dict[str, object]) -> None:
    print(f"rom build: {'PASS' if payload['success'] else 'FAIL'}")
    command = payload.get("command")
    if command:
        print(f"  Command: {shlex.join(command['command'])}")
        print(
            f"  Exit: {command['exit_code']} in {command['duration_seconds']:.3f}s"
            + (" (timed out)" if command["timed_out"] else "")
        )
    output = payload.get("output_rom")
    if output:
        print(
            f"  ROM: {output.get('game_code')} {output.get('size_bytes')} bytes "
            f"sha256={output.get('sha256')}"
        )
    artifacts = payload["artifacts"]
    print(f"  Report: {_relative_or_absolute(artifacts.get('report'))}")
    print(f"  Log: {_relative_or_absolute(artifacts.get('log'))}")
    for error in payload["errors"]:
        print(f"  ERROR {error}")


def _print_smoke(payload: dict[str, object]) -> None:
    print(f"rom smoke: {'PASS' if payload['success'] else 'FAIL'}")
    command = payload.get("command")
    if command:
        print(
            f"  Worker exit: {command['exit_code']} in {command['duration_seconds']:.3f}s"
            + (" (timed out)" if command["timed_out"] else "")
        )
    worker = payload.get("worker") or {}
    frames = worker.get("frames") or {}
    screenshot = payload.get("screenshot") or {}
    if frames:
        print(
            f"  Frames: {frames.get('total')} "
            f"(A pressed for {worker.get('input', {}).get('pressed_frames')} frames)"
        )
    if screenshot:
        print(
            f"  Screenshot: {_relative_or_absolute(screenshot.get('path'))} "
            f"{screenshot.get('width')}x{screenshot.get('height')} "
            f"sha256={screenshot.get('sha256')}"
        )
    artifacts = payload["artifacts"]
    print(f"  Report: {_relative_or_absolute(artifacts.get('report'))}")
    print(f"  Log: {_relative_or_absolute(artifacts.get('log'))}")
    for error in payload["errors"]:
        print(f"  ERROR {error}")


def _print_map(payload: dict[str, object]) -> None:
    print(f"map: {'PASS' if payload.get('success', True) else 'FAIL'}")
    if "slots" in payload:
        print(f"  Slots: {payload['slots']}")
    if "hashes" in payload:
        print(f"  Binary hashes: {len(payload['hashes'])}")
    for mismatch in payload.get("mismatches", []):
        print(f"  MISMATCH {mismatch}")
    for error in payload.get("errors", []):
        print(f"  ERROR {error}")


def _print_registry(payload: dict[str, object]) -> None:
    print(f"registry: {'PASS' if payload.get('success') else 'FAIL'}")
    if "symbol" in payload:
        print(
            f"  {payload['symbol']} -> {payload['namespace']}:{payload['id']} "
            f"({payload['classification']}, {payload['access']})"
        )
    if "namespace_count" in payload:
        print(f"  Namespaces: {payload['namespace_count']}; resources: {payload['resource_count']}")
    if "revision" in payload:
        print(f"  ROM: {payload['revision']['game_code']} sha256={payload['revision']['rom_sha256']}")
    if "output" in payload:
        print(f"  Inventory: {_relative_or_absolute(payload['output'])}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "preflight":
            payload = run_preflight(PROJECT_ROOT)
            _print_json(payload) if args.json else _print_preflight(payload)
        elif args.command == "rom" and args.rom_command == "build":
            payload = build_rom(PROJECT_ROOT, jobs=args.jobs, timeout_seconds=args.timeout)
            _print_json(payload) if args.json else _print_build(payload)
        elif args.command == "rom" and args.rom_command == "smoke":
            payload = run_smoke(
                PROJECT_ROOT,
                boot_frames=args.boot_frames,
                input_frames=args.input_frames,
                post_input_frames=args.post_input_frames,
                timeout_seconds=args.timeout,
            )
            _print_json(payload) if args.json else _print_smoke(payload)
        elif args.command == "map" and args.map_command == "validate":
            fixture = load_fixture(args.fixture)
            payload = {"success": True, "fixture": str(args.fixture), "slots": fixture["slots"]}
            _print_json(payload) if args.json else _print_map(payload)
        elif args.command == "map" and args.map_command in ("generate", "install"):
            payload = generate_world(args.fixture, args.output, PROJECT_ROOT, install=args.map_command == "install")
            payload["success"] = True
            _print_json(payload) if args.json else _print_map(payload)
        elif args.command == "map" and args.map_command == "determinism":
            payload = verify_determinism(args.fixture, PROJECT_ROOT)
            _print_json(payload) if args.json else _print_map(payload)
        elif args.command == "map" and args.map_command == "test":
            payload = run_world_test(PROJECT_ROOT, args.fixture, args.timeout)
            _print_json(payload) if args.json else _print_map(payload)
        elif args.command == "registry" and args.registry_command == "validate":
            registry = load_registry(args.registry)
            payload = {
                "success": True,
                "registry": str(args.registry),
                "namespace_count": len(registry["namespaces"]),
                "resource_count": sum(len(namespace["resources"]) for namespace in registry["namespaces"].values()),
                "revision": verify_rom_revision(registry, args.rom),
            }
            _print_json(payload) if args.json else _print_registry(payload)
        elif args.command == "registry" and args.registry_command == "inspect":
            payload = write_inventory(args.registry, args.rom, args.output)
            _print_json(payload) if args.json else _print_registry(payload)
        elif args.command == "registry" and args.registry_command == "resolve":
            payload = resolve_symbol(load_registry(args.registry), args.symbol, args.namespace, require_writable=False)
            payload["success"] = True
            _print_json(payload) if args.json else _print_registry(payload)
        else:
            parser.error("unsupported command")
            return 2
    except (OSError, ValueError) as error:
        if getattr(args, "json", False):
            detail = error.as_dict() if isinstance(error, RegistryError) else {"code": "error", "message": str(error)}
            _print_json({"success": False, "errors": [detail]})
        else:
            print(f"pokeagent: ERROR {error}", file=sys.stderr)
        return 1

    return 0 if payload["success"] else 1
