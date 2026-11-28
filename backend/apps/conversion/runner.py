"""Run converter command-line tools as subprocesses.

Tools are found from a configured path (an environment variable via Django settings) or on
``PATH``. Output is streamed line by line to a callback, and a run can be cancelled from
another thread through a ``threading.Event``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from pathlib import Path

OutputCallback = Callable[[str], None]


class ConversionError(Exception):
    """A conversion failed; the message is meant for the user."""


class ToolNotFoundError(ConversionError):
    pass


class ToolFailedError(ConversionError):
    def __init__(self, message: str, returncode: int, output_tail: list[str]) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.output_tail = output_tail


class ConversionCancelled(ConversionError):
    pass


def resolve_tool(configured: str, names: Sequence[str], setting_name: str) -> str:
    """Return the executable to run.

    ``configured`` (from settings) wins when set: it may be a path or a bare command name.
    Otherwise each of ``names`` is looked up on ``PATH``. ``shutil.which`` adds ``.exe`` on
    Windows, so the same names work on Linux, macOS and Windows.
    """
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            if not os.access(path, os.X_OK):
                raise ToolNotFoundError(f"{setting_name}={configured} is not executable.")
            return str(path)
        found = shutil.which(configured)
        if found:
            return found
        raise ToolNotFoundError(f"{setting_name}={configured} does not point to an executable.")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise ToolNotFoundError(
        f"Could not find {names[0]} on PATH. Install it or set {setting_name} to its path."
    )


def run_tool(
    args: Sequence[str],
    *,
    tool_name: str,
    on_output: OutputCallback | None = None,
    cancel: threading.Event | None = None,
    timeout: float | None = None,
    cwd: Path | None = None,
    tail_lines: int = 40,
) -> None:
    """Run ``args`` and stream its combined stdout/stderr to ``on_output``.

    Raises ``ToolFailedError`` on a non-zero exit (with the last output lines, which usually
    hold the tool's error), ``ConversionCancelled`` when ``cancel`` is set, and
    ``ConversionError`` on timeout.
    """
    try:
        proc = subprocess.Popen(
            list(args),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        raise ToolNotFoundError(f"Could not start {tool_name} ({args[0]}): {exc}") from exc

    tail: deque[str] = deque(maxlen=tail_lines)

    def pump() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            tail.append(line)
            if on_output is not None:
                on_output(line)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()

    deadline = None if timeout is None else time.monotonic() + timeout
    stop_reason: str | None = None
    try:
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                stop_reason = "cancelled"
            elif deadline is not None and time.monotonic() > deadline:
                stop_reason = "timeout"
            if stop_reason:
                _stop(proc)
                break
            time.sleep(0.1)
    except BaseException:
        # KeyboardInterrupt and friends: never leave the tool running.
        _stop(proc)
        raise
    finally:
        reader.join(timeout=5)

    if stop_reason == "cancelled":
        raise ConversionCancelled(f"{tool_name} was cancelled.")
    if stop_reason == "timeout":
        raise ConversionError(f"{tool_name} did not finish within {timeout:.0f} s.")
    if proc.returncode != 0:
        detail = "\n".join(tail) or "(no output)"
        raise ToolFailedError(
            f"{tool_name} failed with exit code {proc.returncode}. Last output:\n{detail}",
            proc.returncode,
            list(tail),
        )


def _stop(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
