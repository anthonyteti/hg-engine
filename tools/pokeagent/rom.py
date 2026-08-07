"""ROM identity, safety preflight, and HG-Engine Make orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fnmatch
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Iterable, Sequence

from .command import run_command


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_GAME_CODE = "IPKE"
BASE_ROM_NAME = "rom.nds"
GENERATED_ROM_NAME = "test.nds"
REPORT_DIRECTORY = Path("build/pokeagent")

REQUIRED_COMMANDS = (
    "make",
    "git",
    "gcc",
    "g++",
    "cmake",
    "autoconf",
    "automake",
    "pkg-config",
    "python3",
    "arm-none-eabi-gcc",
    "arm-none-eabi-ld",
    "arm-none-eabi-objcopy",
)

REQUIRED_PYTHON_DEPENDENCIES = (
    ("ndspy", "ndspy"),
    ("pandas", "pandas"),
    ("Pillow", "PIL"),
    ("py-desmume", "desmume"),
)

GIT_IGNORE_PROBES = {
    "base ROM": Path("rom.nds"),
    "generated ROM": Path("test.nds"),
    "other generated ROM": Path("pokeagent-generated.nds"),
    "raw save": Path("pokeagent-test.sav"),
    "DeSmuME save": Path("pokeagent-test.dsv"),
    "generic state": Path("pokeagent-test.state"),
    "DeSmuME state": Path("pokeagent-test.dst"),
    "extracted ROM material": Path("base/pokeagent-check/file.bin"),
    "build output": Path("build/pokeagent-check/file.bin"),
    "smoke screenshot": Path("build/pokeagent/smoke.png"),
    "build log": Path("build/pokeagent/build.log"),
}

DOCKER_EXCLUSION_PROBES = {
    **GIT_IGNORE_PROBES,
    "Git object": Path(".git/objects/example"),
    "virtual environment": Path(".venv/lib/example"),
    "screenshot directory": Path("screenshots/smoke.png"),
    "artifact directory": Path("artifacts/report.json"),
    "scratch directory": Path(".scratch/example"),
    "DSPRE extraction": Path("example_DSPRE_contents/files/example"),
    "archived ROM": Path("local-rom.zip"),
    "extracted sound data": Path("sdat/example.sdat"),
    "local tool binary": Path("tools/armips"),
    "downloaded local tool": Path("tools/ntrWavTool.py"),
    "Windows local tool": Path("tools/armips.exe"),
}

DOCKER_REQUIRED_INPUTS = (
    Path("Makefile"),
    Path("requirements.txt"),
    Path("tools/narcpy.py"),
    Path("tools/source/msgenc/Makefile"),
    Path("data/graphics/item/base/normal.png"),
)

SENSITIVE_SUFFIXES = {".nds", ".sav", ".dsv", ".state", ".dst"}
SENSITIVE_PREFIXES = ("base/", "build/", "narc/")


@dataclass(frozen=True)
class CheckResult:
    group: str
    name: str
    passed: bool
    message: str
    details: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_rom(path: Path, *, include_hash: bool = True) -> dict[str, object]:
    path = Path(path)
    result: dict[str, object] = {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "supported": False,
    }
    if not path.is_file():
        return result

    size = path.stat().st_size
    result["size_bytes"] = size
    if size < 0x14:
        result["error"] = "file is too small to contain a Nintendo DS header"
        return result

    with path.open("rb") as handle:
        header = handle.read(0x14)

    title = header[0:12].rstrip(b"\0 ").decode("ascii", errors="replace")
    game_code = header[0x0C:0x10].decode("ascii", errors="replace")
    maker_code = header[0x10:0x12].decode("ascii", errors="replace")
    result.update(
        {
            "title": title,
            "game_code": game_code,
            "maker_code": maker_code,
            "supported": game_code == SUPPORTED_GAME_CODE,
        }
    )
    if include_hash:
        result["sha256"] = sha256_file(path)
    return result


def write_json_report(path: Path, payload: dict[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def path_is_git_ignored(root: Path, path: Path) -> bool | None:
    root = Path(root).resolve()
    candidate = Path(path)
    try:
        relative = candidate.resolve().relative_to(root) if candidate.is_absolute() else candidate
    except ValueError:
        return False
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", str(relative)],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.returncode == 0


def check_commands(command_names: Sequence[str] = REQUIRED_COMMANDS) -> list[CheckResult]:
    checks = []
    for name in command_names:
        location = shutil.which(name)
        checks.append(
            CheckResult(
                group="commands",
                name=name,
                passed=location is not None,
                message=location or f"required command not found on PATH: {name}",
                details={"path": location} if location else None,
            )
        )
    return checks


def check_python_dependencies(
    dependencies: Sequence[tuple[str, str]] = REQUIRED_PYTHON_DEPENDENCIES,
) -> list[CheckResult]:
    checks = []
    for distribution, module in dependencies:
        importable = importlib.util.find_spec(module) is not None
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = None
        passed = importable and version is not None
        checks.append(
            CheckResult(
                group="python",
                name=distribution,
                passed=passed,
                message=(
                    f"{distribution} {version} ({module})"
                    if passed
                    else f"Python dependency unavailable: {distribution} ({module})"
                ),
                details={"distribution": distribution, "module": module, "version": version},
            )
        )
    return checks


def check_system_dependencies() -> list[CheckResult]:
    pkg_config = shutil.which("pkg-config")
    if pkg_config is None:
        return [
            CheckResult(
                group="system",
                name="libpng",
                passed=False,
                message="cannot probe libpng because pkg-config is unavailable",
            )
        ]
    try:
        result = subprocess.run(
            [pkg_config, "--exists", "libpng"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        passed = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            CheckResult(
                group="system",
                name="libpng",
                passed=False,
                message=f"libpng probe failed: {error}",
            )
        ]
    return [
        CheckResult(
            group="system",
            name="libpng",
            passed=passed,
            message=(
                "libpng detected by pkg-config"
                if passed
                else "libpng not detected by pkg-config"
            ),
        )
    ]


def check_rom_identity(root: Path) -> list[CheckResult]:
    checks = []
    for name, required in ((BASE_ROM_NAME, True), (GENERATED_ROM_NAME, False)):
        info = inspect_rom(Path(root) / name, include_hash=False)
        if not info["exists"] and not required:
            checks.append(
                CheckResult(
                    group="rom",
                    name=name,
                    passed=True,
                    message=f"{name} has not been generated yet",
                    details=info,
                )
            )
        elif not info["exists"]:
            checks.append(
                CheckResult(
                    group="rom",
                    name=name,
                    passed=False,
                    message=f"required local ROM is missing: {name}",
                    details=info,
                )
            )
        elif not info["supported"]:
            checks.append(
                CheckResult(
                    group="rom",
                    name=name,
                    passed=False,
                    message=(
                        f"unsupported ROM game code {info.get('game_code')!r}; "
                        f"expected {SUPPORTED_GAME_CODE}"
                    ),
                    details=info,
                )
            )
        else:
            checks.append(
                CheckResult(
                    group="rom",
                    name=name,
                    passed=True,
                    message=(
                        f"{name}: {info.get('title') or 'Nintendo DS ROM'} "
                        f"({SUPPORTED_GAME_CODE})"
                    ),
                    details=info,
                )
            )
    return checks


def _tracked_sensitive_files(root: Path) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    paths = [
        entry.decode("utf-8", errors="replace")
        for entry in result.stdout.split(b"\0")
        if entry
    ]
    return [
        path
        for path in paths
        if Path(path).suffix.lower() in SENSITIVE_SUFFIXES
        or path.replace("\\", "/").startswith(SENSITIVE_PREFIXES)
    ]


def check_git_hygiene(root: Path) -> list[CheckResult]:
    root = Path(root).resolve()
    checks = []
    if not (root / ".git").exists():
        return [
            CheckResult(
                group="git_hygiene",
                name="repository",
                passed=False,
                message=f"not a Git checkout: {root}",
            )
        ]

    for label, path in GIT_IGNORE_PROBES.items():
        ignored = path_is_git_ignored(root, path)
        checks.append(
            CheckResult(
                group="git_hygiene",
                name=str(path),
                passed=ignored is True,
                message=(
                    f"ignored: {label} ({path})"
                    if ignored is True
                    else (
                        f"not ignored: {label} ({path})"
                        if ignored is False
                        else f"unable to verify Git ignore rule: {label} ({path})"
                    )
                ),
            )
        )

    tracked = _tracked_sensitive_files(root)
    checks.append(
        CheckResult(
            group="git_hygiene",
            name="tracked-sensitive-files",
            passed=tracked == [],
            message=(
                "no ROM, save/state, base, build, or NARC artifacts are tracked"
                if tracked == []
                else (
                    "unable to query tracked files"
                    if tracked is None
                    else "sensitive/generated files are tracked: " + ", ".join(tracked)
                )
            ),
            details={"tracked": tracked},
        )
    )
    return checks


def _load_dockerignore_patterns(path: Path) -> list[str]:
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(stripped)
    return patterns


def _docker_pattern_matches(pattern: str, candidate: Path) -> bool:
    normalized = candidate.as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    directory_only = pattern.endswith("/")
    anchored = pattern.startswith("/") or "/" in pattern.strip("/")
    normalized_pattern = pattern.lstrip("/").rstrip("/")
    if not normalized_pattern:
        return False

    if anchored:
        return fnmatch.fnmatchcase(normalized, normalized_pattern) or normalized.startswith(
            normalized_pattern + "/"
        )

    parts = normalized.split("/")
    if directory_only:
        return any(fnmatch.fnmatchcase(part, normalized_pattern) for part in parts[:-1])
    return any(fnmatch.fnmatchcase(part, normalized_pattern) for part in parts)


def docker_path_is_ignored(patterns: Iterable[str], candidate: Path) -> bool:
    ignored = False
    for raw_pattern in patterns:
        negated = raw_pattern.startswith("!")
        pattern = raw_pattern[1:] if negated else raw_pattern
        if _docker_pattern_matches(pattern, candidate):
            ignored = not negated
    return ignored


def check_docker_context(root: Path) -> list[CheckResult]:
    dockerignore = Path(root) / ".dockerignore"
    if not dockerignore.is_file():
        return [
            CheckResult(
                group="docker_context",
                name=".dockerignore",
                passed=False,
                message=".dockerignore is missing; Docker context may expose ROM material",
            )
        ]

    patterns = _load_dockerignore_patterns(dockerignore)
    checks = []
    for label, candidate in DOCKER_EXCLUSION_PROBES.items():
        ignored = docker_path_is_ignored(patterns, candidate)
        checks.append(
            CheckResult(
                group="docker_context",
                name=str(candidate),
                passed=ignored,
                message=(
                    f"excluded from Docker context: {label} ({candidate})"
                    if ignored
                    else f"DANGEROUS Docker exposure: {label} ({candidate})"
                ),
            )
        )

    for candidate in DOCKER_REQUIRED_INPUTS:
        ignored = docker_path_is_ignored(patterns, candidate)
        checks.append(
            CheckResult(
                group="docker_context",
                name=f"required:{candidate}",
                passed=not ignored,
                message=(
                    f"required build input remains in Docker context: {candidate}"
                    if not ignored
                    else f"required build input is accidentally excluded: {candidate}"
                ),
            )
        )
    return checks


def summarize_checks(checks: Sequence[CheckResult]) -> dict[str, dict[str, int | bool]]:
    summary: dict[str, dict[str, int | bool]] = {}
    for check in checks:
        group = summary.setdefault(check.group, {"passed": 0, "total": 0, "success": True})
        group["total"] = int(group["total"]) + 1
        if check.passed:
            group["passed"] = int(group["passed"]) + 1
        else:
            group["success"] = False
    return summary


def run_preflight(
    root: Path = PROJECT_ROOT,
    *,
    command_names: Sequence[str] = REQUIRED_COMMANDS,
    python_dependencies: Sequence[tuple[str, str]] = REQUIRED_PYTHON_DEPENDENCIES,
) -> dict[str, object]:
    root = Path(root).resolve()
    checks = [
        *check_commands(command_names),
        *check_python_dependencies(python_dependencies),
        *check_system_dependencies(),
        *check_rom_identity(root),
        *check_git_hygiene(root),
        *check_docker_context(root),
    ]
    return {
        "schema_version": 1,
        "operation": "preflight",
        "created_at": utc_now(),
        "project_root": str(root),
        "python_executable": os.path.abspath(os.sys.executable),
        "python_base_executable": os.path.realpath(os.sys.executable),
        "python_version": os.sys.version.split()[0],
        "supported_game_code": SUPPORTED_GAME_CODE,
        "success": all(check.passed for check in checks),
        "summary": summarize_checks(checks),
        "checks": [check.to_dict() for check in checks],
    }


def make_build_command(jobs: int | None = None) -> list[str]:
    resolved_jobs = jobs if jobs is not None else (os.cpu_count() or 1)
    if resolved_jobs < 1:
        raise ValueError("jobs must be at least 1")
    return ["make", f"-j{resolved_jobs}"]


def build_rom(
    root: Path = PROJECT_ROOT,
    *,
    jobs: int | None = None,
    timeout_seconds: float = 1200,
) -> dict[str, object]:
    root = Path(root).resolve()
    report_path = root / REPORT_DIRECTORY / "build-report.json"
    log_path = root / REPORT_DIRECTORY / "build.log"
    preflight = run_preflight(root)
    errors: list[str] = []

    report: dict[str, object] = {
        "schema_version": 1,
        "operation": "rom_build",
        "created_at": utc_now(),
        "project_root": str(root),
        "success": False,
        "preflight": {
            "success": preflight["success"],
            "summary": preflight["summary"],
        },
        "artifacts": {
            "report": str(report_path),
            "log": str(log_path),
        },
        "errors": errors,
    }

    report_is_safe = path_is_git_ignored(root, report_path) is True
    if not preflight["success"]:
        errors.append("preflight failed; Make was not invoked")
        report["preflight_failures"] = [
            check for check in preflight["checks"] if not check["passed"]
        ]
        if report_is_safe:
            write_json_report(report_path, report)
        else:
            report["artifacts"]["report"] = None
            report["artifacts"]["log"] = None
            errors.append("build report path is not ignored; no artifacts were written")
        return report

    input_rom = inspect_rom(root / BASE_ROM_NAME)
    output_path = root / GENERATED_ROM_NAME
    output_before = inspect_rom(output_path) if output_path.exists() else None
    command = make_build_command(jobs)
    started_wall_ns = time.time_ns()
    command_result = run_command(
        command,
        cwd=root,
        timeout_seconds=timeout_seconds,
        log_path=log_path,
    )
    output_after = inspect_rom(output_path) if output_path.exists() else None
    output_fresh = bool(
        output_after
        and output_path.stat().st_mtime_ns >= started_wall_ns - 2_000_000_000
    )

    if not command_result.succeeded:
        errors.append(
            "Make timed out"
            if command_result.timed_out
            else f"Make exited {command_result.exit_code}"
        )
    if output_after is None:
        errors.append(f"expected output ROM was not created: {GENERATED_ROM_NAME}")
    elif not output_after["supported"]:
        errors.append(
            f"output ROM game code {output_after.get('game_code')!r} is not {SUPPORTED_GAME_CODE}"
        )
    if output_after is not None and not output_fresh:
        errors.append("output ROM was not refreshed by this Make invocation")

    report.update(
        {
            "command": command_result.to_dict(),
            "input_rom": input_rom,
            "output_rom_before": output_before,
            "output_rom": output_after,
            "output_fresh": output_fresh,
            "success": not errors,
            "completed_at": utc_now(),
        }
    )
    write_json_report(report_path, report)
    return report
