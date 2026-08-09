"""Command-line surface for HG-Engine build, generation, and emulator checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

from .assets import compile_asset, compile_asset_outputs
from .emulator import run_smoke
from .generated_intake import inspect_generated_asset, write_intake_report
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
from .qa import inspect_scenario, load_scenario, run_scenario
from .textures import compile_texture_catalog, compile_texture_catalog_outputs, compile_texture_outputs
from .world import (
    DEFAULT_FIXTURE, DEFAULT_OUTPUT, generate_world, inspect_geometry, load_fixture,
    verify_determinism, write_project_header_include,
)
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
    geometry_parser = map_subparsers.add_parser("geometry", help="inspect bounded static-terrain geometry")
    geometry_subparsers = geometry_parser.add_subparsers(dest="geometry_command", required=True)
    geometry_inspect = geometry_subparsers.add_parser("inspect", help="validate IR and report shape budgets")
    geometry_inspect.add_argument("--fixture", type=Path, required=True)
    _add_output_argument(geometry_inspect)
    headers_parser = map_subparsers.add_parser("headers", help="generate the Stage 3E2 project-header include")
    headers_parser.add_argument("--fixture", type=Path, required=True)
    headers_parser.add_argument("--output", type=Path, required=True)
    _add_output_argument(headers_parser)

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

    qa_parser = subparsers.add_parser("qa", help="validate and run declarative gameplay QA scenarios")
    qa_subparsers = qa_parser.add_subparsers(dest="qa_command", required=True)
    for command, help_text in (
        ("validate", "validate one tracked QA scenario"),
        ("inspect", "show its deterministic action/assertion plan"),
        ("run", "execute it through the bounded headless emulator worker"),
    ):
        child = qa_subparsers.add_parser(command, help=help_text)
        child.add_argument("scenario", type=Path)
        if command == "run":
            child.add_argument("--timeout", type=float, default=300)
        _add_output_argument(child)

    asset_parser = subparsers.add_parser("asset", help="validate and compile bounded environment assets")
    asset_subparsers = asset_parser.add_subparsers(dest="asset_command", required=True)
    for command, help_text in (
        ("validate", "validate one tracked asset manifest and source mesh"),
        ("inspect", "report normalized geometry, material, collision, and DS budgets"),
        ("simplify", "run the manifest-declared deterministic simplification and report its budget result"),
        ("preprocess", "flatten a manifest-declared bounded static GLB hierarchy"),
        ("normals", "generate manifest-declared bounded crease-aware normals"),
        ("uvs", "generate manifest-declared bounded planar-patch UV0"),
        ("materials", "assign one manifest-declared bounded source-material identity"),
        ("compile", "write deterministic ignored asset artifacts"),
    ):
        child = asset_subparsers.add_parser(command, help=help_text)
        child.add_argument("manifest", type=Path)
        if command in ("compile", "preprocess", "normals", "uvs", "materials"):
            child.add_argument("--output", type=Path)
        _add_output_argument(child)
    intake_parser = asset_subparsers.add_parser(
        "intake", help="inspect an immutable generated GLB without repair or compilation",
    )
    intake_parser.add_argument("manifest", type=Path)
    intake_parser.add_argument("--output", type=Path)
    _add_output_argument(intake_parser)

    texture_parser = subparsers.add_parser("texture", help="validate and compile bounded project PNG textures")
    texture_subparsers = texture_parser.add_subparsers(dest="texture_command", required=True)
    for command, help_text in (
        ("validate", "validate one asset manifest's Stage 4C PNG declaration"),
        ("inspect", "report image, palette, texel, and bounded container metadata"),
        ("compile", "write deterministic ignored texture artifacts"),
    ):
        child = texture_subparsers.add_parser(command, help=help_text)
        child.add_argument("manifest", type=Path)
        if command == "compile":
            child.add_argument("--output", type=Path)
        _add_output_argument(child)
    texture_catalog = texture_subparsers.add_parser(
        "catalog", help="inspect or compile the persistent Stage 4D project texture catalog",
    )
    texture_catalog.add_argument("--catalog", type=Path, default=PROJECT_ROOT / "assets/texture_catalog.json")
    texture_catalog.add_argument("--output", type=Path)
    texture_catalog.add_argument("--compile", action="store_true", dest="compile_catalog")
    _add_output_argument(texture_catalog)
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


def _print_qa(payload: dict[str, object]) -> None:
    print(f"qa: {'PASS' if payload.get('success') else 'FAIL'}")
    print(f"  Scenario: {payload.get('scenario')}")
    if "plan" in payload:
        print(f"  Plan: {payload['plan'].get('step_count')} steps sha256={payload['plan'].get('sha256')}")
    worker = payload.get("worker") or {}
    if worker:
        print(f"  Assertions: {worker.get('assertions_passed')}/{worker.get('assertions_total')}")
        final = worker.get("final_state") or {}
        print(f"  Final: map={final.get('map_id')} position={final.get('position')} frame={final.get('frame')}")
    for error in payload.get("errors", []):
        print(f"  ERROR {error}")


def _print_asset(payload: dict[str, object]) -> None:
    print(f"asset: {'PASS' if payload.get('success') else 'FAIL'}")
    print(f"  Asset: {payload.get('asset_id')}")
    counts = payload.get("normalized_counts") or {}
    print(f"  Geometry: {counts.get('vertices')} vertices, {counts.get('quads')} quads")
    if "display_list_bytes" in payload:
        print(
            f"  Display list: {payload['display_list_bytes']}/{payload['display_list_capacity_bytes']} bytes "
            f"({payload['shape_utilization_percent']}%)"
        )
    if "outputs" in payload:
        print(f"  Report: {_relative_or_absolute(payload['outputs'].get('report'))}")


def _print_intake(payload: dict[str, object]) -> None:
    status = "ACCEPT" if payload.get("accepted") else "REJECT"
    print(f"generated asset intake: {status}")
    print(f"  Asset: {payload.get('asset_id')}")
    print(f"  Quality: {payload.get('quality_classification')}")
    geometry = payload.get("geometry") or {}
    print(
        f"  Raw geometry: {geometry.get('triangle_count')} triangles, "
        f"{geometry.get('position_count')} positions"
    )
    budget = payload.get("budget") or {}
    print(
        f"  Projected display list: {budget.get('projected_nitro_bytes_if_attributes_existed')}/"
        f"{budget.get('capacity_bytes')} bytes"
    )
    problems = (payload.get("stage4f") or {}).get("problems") or []
    for problem in problems:
        print(f"  REJECT [{problem.get('code')}] {problem.get('message')}")
    if "outputs" in payload:
        print(f"  Report: {_relative_or_absolute(payload['outputs'].get('report'))}")


def _print_texture(payload: dict[str, object]) -> None:
    print(f"texture: {'PASS' if payload.get('success') else 'FAIL'}")
    if "allocations" in payload:
        print(f"  Project catalog: {payload.get('texture_count')} textures")
        for allocation in payload["allocations"]:
            print(
                f"  {allocation['symbol']} -> {allocation['nitro_texture']}/"
                f"{allocation['nitro_palette']} allocation={allocation['allocation']}"
            )
        return
    print(
        f"  {payload.get('texture_id')}: {payload.get('dimensions')} {payload.get('format')} "
        f"colors={payload.get('encoded_color_count')} texels={payload.get('texture_bytes')} bytes"
    )


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
        elif args.command == "map" and args.map_command == "headers":
            payload = write_project_header_include(args.fixture, args.output)
            _print_json(payload) if args.json else _print_map(payload)
        elif args.command == "map" and args.map_command == "geometry" and args.geometry_command == "inspect":
            payload = inspect_geometry(args.fixture, PROJECT_ROOT)
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
        elif args.command == "qa" and args.qa_command == "validate":
            scenario = load_scenario(args.scenario, PROJECT_ROOT)
            payload = {"success": True, "scenario": scenario["id"], "fixture": scenario["fixture"]}
            _print_json(payload) if args.json else _print_qa(payload)
        elif args.command == "qa" and args.qa_command == "inspect":
            payload = inspect_scenario(args.scenario, PROJECT_ROOT)
            _print_json(payload) if args.json else _print_qa(payload)
        elif args.command == "qa" and args.qa_command == "run":
            payload = run_scenario(args.scenario, PROJECT_ROOT, args.timeout)
            _print_json(payload) if args.json else _print_qa(payload)
        elif args.command == "asset" and args.asset_command in ("validate", "inspect", "simplify"):
            report = compile_asset(args.manifest, PROJECT_ROOT)["report"]
            if args.asset_command == "simplify" and "simplification" not in report:
                raise ValueError("asset simplify requires an opt-in simplification manifest")
            payload = report if args.asset_command != "simplify" else {
                "success": True,
                "asset_id": report["asset_id"],
                "simplification": report["simplification"],
                "hashes": report["hashes"],
            }
            _print_json(payload) if args.json else _print_asset(payload)
        elif args.command == "asset" and args.asset_command == "compile":
            compiled = compile_asset(args.manifest, PROJECT_ROOT)
            output = args.output or PROJECT_ROOT / "build" / "assets" / compiled["manifest"]["id"]
            payload = compile_asset_outputs(args.manifest, output, PROJECT_ROOT)
            _print_json(payload) if args.json else _print_asset(payload)
        elif args.command == "asset" and args.asset_command == "preprocess":
            compiled = compile_asset(args.manifest, PROJECT_ROOT)
            if compiled["preprocessed_glb"] is None:
                raise ValueError("asset preprocess requires an opt-in Stage 4K manifest")
            output = args.output or PROJECT_ROOT / "build" / "assets" / compiled["manifest"]["id"]
            report = compile_asset_outputs(args.manifest, output, PROJECT_ROOT)
            payload = dict(compiled["report"])
            payload["outputs"] = report["outputs"]
            _print_json(payload) if args.json else _print_asset(payload)
        elif args.command == "asset" and args.asset_command == "normals":
            compiled = compile_asset(args.manifest, PROJECT_ROOT)
            if compiled["normal_generated_glb"] is None:
                raise ValueError("asset normals requires an opt-in Stage 4L manifest")
            output = args.output or PROJECT_ROOT / "build" / "assets" / compiled["manifest"]["id"]
            report = compile_asset_outputs(args.manifest, output, PROJECT_ROOT)
            payload = dict(compiled["report"])
            payload["outputs"] = report["outputs"]
            _print_json(payload) if args.json else _print_asset(payload)
        elif args.command == "asset" and args.asset_command == "uvs":
            compiled = compile_asset(args.manifest, PROJECT_ROOT)
            if compiled["uv_generated_glb"] is None:
                raise ValueError("asset uvs requires an opt-in Stage 4M manifest")
            output = args.output or PROJECT_ROOT / "build" / "assets" / compiled["manifest"]["id"]
            report = compile_asset_outputs(args.manifest, output, PROJECT_ROOT)
            payload = dict(compiled["report"])
            payload["outputs"] = report["outputs"]
            _print_json(payload) if args.json else _print_asset(payload)
        elif args.command == "asset" and args.asset_command == "materials":
            compiled = compile_asset(args.manifest, PROJECT_ROOT)
            if compiled["material_generated_glb"] is None:
                raise ValueError("asset materials requires an opt-in Stage 4N manifest")
            output = args.output or PROJECT_ROOT / "build" / "assets" / compiled["manifest"]["id"]
            report = compile_asset_outputs(args.manifest, output, PROJECT_ROOT)
            payload = dict(compiled["report"])
            payload["outputs"] = report["outputs"]
            _print_json(payload) if args.json else _print_asset(payload)
        elif args.command == "asset" and args.asset_command == "intake":
            if args.output:
                payload = write_intake_report(args.manifest, args.output, PROJECT_ROOT)
            else:
                payload = inspect_generated_asset(args.manifest, PROJECT_ROOT)
            _print_json(payload) if args.json else _print_intake(payload)
        elif args.command == "texture" and args.texture_command == "catalog":
            if args.compile_catalog:
                output = args.output or PROJECT_ROOT / "build/assets/texture-catalog"
                payload = compile_texture_catalog_outputs(args.catalog, output, PROJECT_ROOT)
            else:
                payload = compile_texture_catalog(args.catalog, PROJECT_ROOT)["report"]
            _print_json(payload) if args.json else _print_texture(payload)
        elif args.command == "texture":
            asset = compile_asset(args.manifest, PROJECT_ROOT)
            if len(asset["textures"]) != 1:
                raise ValueError("texture command requires exactly one Stage 4C texture declaration")
            texture = next(iter(asset["textures"].values()))
            if args.texture_command in ("validate", "inspect"):
                payload = texture["report"]
            else:
                output = (
                    args.output
                    or PROJECT_ROOT / "build" / "assets" / asset["manifest"]["id"]
                    / "textures" / texture["spec"]["id"]
                )
                payload = compile_texture_outputs(texture["spec"], output, PROJECT_ROOT)
            _print_json(payload) if args.json else _print_texture(payload)
        else:
            parser.error("unsupported command")
            return 2
    except (OSError, ValueError) as error:
        if getattr(args, "json", False):
            detail = error.as_dict() if hasattr(error, "as_dict") else {"code": "error", "message": str(error)}
            _print_json({"success": False, "errors": [detail]})
        else:
            print(f"pokeagent: ERROR {error}", file=sys.stderr)
        return 1

    return 0 if payload["success"] else 1
