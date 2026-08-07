from __future__ import annotations

import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from tools.pokeagent.emulator import (
    PNG_SIGNATURE,
    read_png_dimensions,
    run_smoke,
    smoke_worker_command,
)
from tools.pokeagent.rom import PROJECT_ROOT


RUN_INTEGRATION = os.environ.get("POKEAGENT_RUN_INTEGRATION") == "1"


class ScreenshotValidationTests(unittest.TestCase):
    def test_png_dimensions_are_read_from_ihdr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            path.write_bytes(
                PNG_SIGNATURE + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 256, 384)
            )
            dimensions = read_png_dimensions(path)

        self.assertEqual(dimensions, (256, 384))

    def test_invalid_png_header_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            path.write_bytes(b"not a png")
            with self.assertRaises(ValueError):
                read_png_dimensions(path)


class SmokeCommandTests(unittest.TestCase):
    def test_worker_command_uses_current_python_and_explicit_bounds(self) -> None:
        command = smoke_worker_command(
            root=Path("/project"),
            rom_path=Path("/project/test.nds"),
            screenshot_path=Path("/project/build/pokeagent/smoke.png"),
            result_path=Path("/project/build/pokeagent/result.json"),
            boot_frames=10,
            input_frames=2,
            post_input_frames=5,
            timeout_seconds=8,
        )

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[1:4], ["-m", "tools.pokeagent.emulator", "--worker"])
        self.assertIn("10", command)
        self.assertIn("8", command)

    def test_smoke_without_generated_rom_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=root,
                check=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            (root / ".gitignore").write_text("build/\n", encoding="utf-8")
            result = run_smoke(root, timeout_seconds=2)

        self.assertFalse(result["success"])
        self.assertTrue(any("missing" in error for error in result["errors"]))


class LocalSmokeIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        RUN_INTEGRATION,
        "set POKEAGENT_RUN_INTEGRATION=1 to run the local ROM smoke integration test",
    )
    def test_local_generated_rom_smoke(self) -> None:
        if not (PROJECT_ROOT / "test.nds").is_file():
            self.skipTest("local test.nds is not available")
        result = run_smoke(PROJECT_ROOT, timeout_seconds=30)
        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(result["screenshot"]["width"], 256)
        self.assertEqual(result["screenshot"]["height"], 384)
        self.assertGreater(result["worker"]["screenshot_result"]["non_black_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
