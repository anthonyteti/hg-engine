"""Bounded, shell-free subprocess execution with compact result capture."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from typing import Mapping, Sequence


DEFAULT_OUTPUT_LIMIT_BYTES = 64 * 1024
TIMEOUT_EXIT_CODE = 124


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    cwd: str
    started_at: str
    duration_seconds: float
    exit_code: int
    timed_out: bool
    output_tail: str
    output_bytes: int
    output_truncated: bool
    log_path: str | None

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["succeeded"] = self.succeeded
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        process.terminate()

    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
    else:
        process.kill()
    process.wait(timeout=5)


def _read_output_tail(handle, limit_bytes: int) -> tuple[str, int, bool]:
    handle.flush()
    handle.seek(0, os.SEEK_END)
    output_bytes = handle.tell()
    start = max(0, output_bytes - limit_bytes)
    handle.seek(start)
    data = handle.read()
    return (
        data.decode("utf-8", errors="replace"),
        output_bytes,
        output_bytes > limit_bytes,
    )


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    log_path: Path | None = None,
    env_overrides: Mapping[str, str] | None = None,
    output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
) -> CommandResult:
    """Run an argv sequence without a shell and retain only a bounded output tail."""

    if not command:
        raise ValueError("command must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if output_limit_bytes <= 0:
        raise ValueError("output_limit_bytes must be positive")

    argv = [str(part) for part in command]
    resolved_cwd = Path(cwd).resolve()
    resolved_log = Path(log_path).resolve() if log_path is not None else None
    if resolved_log is not None:
        resolved_log.parent.mkdir(parents=True, exist_ok=True)
        output_handle = resolved_log.open("w+b")
    else:
        output_handle = tempfile.TemporaryFile(mode="w+b")

    environment = os.environ.copy()
    if env_overrides:
        environment.update({str(key): str(value) for key, value in env_overrides.items()})

    started_at = _utc_now()
    started = time.monotonic()
    timed_out = False
    exit_code = 126
    process: subprocess.Popen[bytes] | None = None

    try:
        process = subprocess.Popen(
            argv,
            cwd=resolved_cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output_handle,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=(os.name == "posix"),
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process_tree(process)
            exit_code = TIMEOUT_EXIT_CODE
    except FileNotFoundError as error:
        exit_code = 127
        output_handle.write(f"command not found: {error}\n".encode())
    except OSError as error:
        exit_code = 126
        output_handle.write(f"unable to execute command: {error}\n".encode())
    finally:
        duration = time.monotonic() - started
        output_tail, output_bytes, output_truncated = _read_output_tail(
            output_handle, output_limit_bytes
        )
        output_handle.close()

    return CommandResult(
        command=argv,
        cwd=str(resolved_cwd),
        started_at=started_at,
        duration_seconds=round(duration, 6),
        exit_code=exit_code,
        timed_out=timed_out,
        output_tail=output_tail,
        output_bytes=output_bytes,
        output_truncated=output_truncated,
        log_path=str(resolved_log) if resolved_log is not None else None,
    )
