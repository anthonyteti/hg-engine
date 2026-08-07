from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.pokeagent.command import TIMEOUT_EXIT_CODE, run_command
from tools.pokeagent.rom import (
    CheckResult,
    PROJECT_ROOT,
    build_rom,
    check_commands,
    check_docker_context,
    docker_path_is_ignored,
    inspect_rom,
    make_build_command,
    run_preflight,
)


RUN_INTEGRATION = os.environ.get("POKEAGENT_RUN_INTEGRATION") == "1"


def write_fake_nds(path: Path, game_code: bytes = b"IPKE") -> None:
    header = bytearray(0x200)
    header[0:12] = b"POKEAGENT\0\0\0"
    header[0x0C:0x10] = game_code
    header[0x10:0x12] = b"01"
    path.write_bytes(header)


def initialize_safe_test_checkout(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=root,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    (root / ".gitignore").write_text(
        "\n".join(
            (
                "*.nds",
                "*.sav",
                "*.dsv",
                "*.state",
                "*.dst",
                "base/",
                "build/",
                "narc/",
                "*.log",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".dockerignore").write_text(
        "\n".join(
            (
                "*.nds",
                "*.sav",
                "*.dsv",
                "*.state",
                "*.dst",
                "*.zip",
                "/base/",
                "/build/",
                "/narc/",
                "/sdat/",
                ".git/",
                ".venv/",
                "/screenshots/",
                "/artifacts/",
                ".scratch/",
                "*_DSPRE_contents/",
                "tools/armips",
                "tools/ntrWavTool.py",
                "tools/*.exe",
                "*.log",
            )
        )
        + "\n",
        encoding="utf-8",
    )


class RomIdentityTests(unittest.TestCase):
    def test_inspect_rom_accepts_supported_game_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.nds"
            write_fake_nds(path)
            result = inspect_rom(path)

        self.assertTrue(result["supported"])
        self.assertEqual(result["game_code"], "IPKE")
        self.assertEqual(result["size_bytes"], 0x200)
        self.assertEqual(len(result["sha256"]), 64)

    def test_inspect_rom_rejects_wrong_game_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.nds"
            write_fake_nds(path, b"IPGE")
            result = inspect_rom(path, include_hash=False)

        self.assertFalse(result["supported"])
        self.assertEqual(result["game_code"], "IPGE")

    def test_make_command_is_shell_free_and_deterministic(self) -> None:
        self.assertEqual(make_build_command(7), ["make", "-j7"])
        with self.assertRaises(ValueError):
            make_build_command(0)


class SafetyTests(unittest.TestCase):
    def test_missing_command_is_reported(self) -> None:
        result = check_commands(("pokeagent-command-that-must-not-exist",))
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].passed)
        self.assertIn("not found", result[0].message)

    def test_root_anchored_base_rule_preserves_source_asset_directory(self) -> None:
        patterns = ["/base/"]
        self.assertTrue(docker_path_is_ignored(patterns, Path("base/root/file.bin")))
        self.assertFalse(
            docker_path_is_ignored(patterns, Path("data/graphics/item/base/normal.png"))
        )

    def test_docker_context_reports_missing_rom_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".dockerignore").write_text("/build/\n", encoding="utf-8")
            checks = check_docker_context(root)

        rom_check = next(check for check in checks if check.name == "rom.nds")
        self.assertFalse(rom_check.passed)
        self.assertIn("DANGEROUS", rom_check.message)

    def test_preflight_succeeds_with_synthetic_rom_and_safe_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_safe_test_checkout(root)
            write_fake_nds(root / "rom.nds")
            system_ok = [
                CheckResult("system", "libpng", True, "synthetic test dependency")
            ]
            with mock.patch(
                "tools.pokeagent.rom.check_system_dependencies", return_value=system_ok
            ):
                result = run_preflight(
                    root,
                    command_names=(),
                    python_dependencies=(),
                )

        self.assertTrue(result["success"])
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_preflight_returns_structured_failures_when_path_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_safe_test_checkout(root)
            write_fake_nds(root / "rom.nds")
            with mock.patch.dict(os.environ, {"PATH": ""}):
                result = run_preflight(
                    root,
                    command_names=("git",),
                    python_dependencies=(),
                )

        failures = [check for check in result["checks"] if not check["passed"]]
        self.assertFalse(result["success"])
        self.assertTrue(failures)
        self.assertTrue(any(check["group"] == "commands" for check in failures))
        self.assertTrue(any(check["group"] == "git_hygiene" for check in failures))


class CommandRunnerTests(unittest.TestCase):
    def test_command_output_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_command(
                [sys.executable, "-c", "print('x' * 1000)"],
                cwd=Path(directory),
                timeout_seconds=5,
                output_limit_bytes=32,
            )

        self.assertTrue(result.succeeded)
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.output_tail.encode()), 32)

    def test_command_timeout_returns_standard_timeout_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_command(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=Path(directory),
                timeout_seconds=0.05,
            )

        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, TIMEOUT_EXIT_CODE)
        self.assertFalse(result.succeeded)


class LocalBuildIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        RUN_INTEGRATION,
        "set POKEAGENT_RUN_INTEGRATION=1 to run the local ROM build integration test",
    )
    def test_local_rom_build(self) -> None:
        if not (PROJECT_ROOT / "rom.nds").is_file():
            self.skipTest("local rom.nds is not available")
        result = build_rom(PROJECT_ROOT, timeout_seconds=1200)
        self.assertTrue(result["success"], result["errors"])
        self.assertTrue(result["output_rom"]["supported"])
        self.assertTrue(result["output_fresh"])


if __name__ == "__main__":
    unittest.main()
