import sys
import threading
from pathlib import Path

import pytest

from apps.conversion.runner import (
    ConversionCancelled,
    ConversionError,
    ToolFailedError,
    ToolNotFoundError,
    resolve_tool,
    run_tool,
)

PY = sys.executable


def test_streams_output_lines() -> None:
    lines: list[str] = []
    # Write UTF-8 bytes directly: the child's console encoding differs between platforms.
    code = r"import sys; sys.stdout.buffer.write(b'a\n\xc3\xbc\r\n')"
    run_tool([PY, "-c", code], tool_name="t", on_output=lines.append)
    assert lines == ["a", "ü"]


def test_failure_keeps_the_last_lines() -> None:
    code = "import sys; [print(i) for i in range(100)]; print('boom'); sys.exit(2)"
    with pytest.raises(ToolFailedError, match="exit code 2") as info:
        run_tool([PY, "-c", code], tool_name="t", tail_lines=5)
    assert info.value.output_tail == ["96", "97", "98", "99", "boom"]


def test_cancel_stops_the_tool() -> None:
    cancel = threading.Event()
    timer = threading.Timer(0.3, cancel.set)
    timer.start()
    with pytest.raises(ConversionCancelled):
        run_tool([PY, "-c", "import time; time.sleep(30)"], tool_name="t", cancel=cancel)


def test_timeout_stops_the_tool() -> None:
    with pytest.raises(ConversionError, match="did not finish"):
        run_tool([PY, "-c", "import time; time.sleep(30)"], tool_name="t", timeout=0.3)


def test_unstartable_tool() -> None:
    with pytest.raises(ToolNotFoundError):
        run_tool([str(Path("no") / "such" / "tool")], tool_name="t")


def test_resolve_tool_prefers_the_configured_path() -> None:
    assert Path(resolve_tool(PY, ["definitely-not-on-path"], "X_PATH")) == Path(PY)


def test_resolve_tool_falls_back_to_path() -> None:
    name = Path(PY).stem  # "python" (python.exe on Windows is found through PATHEXT)
    assert resolve_tool("", ["definitely-not-on-path", name], "X_PATH")


def test_resolve_tool_errors_name_the_setting(tmp_path: Path) -> None:
    with pytest.raises(ToolNotFoundError, match="X_PATH"):
        resolve_tool("", ["definitely-not-on-path"], "X_PATH")
    with pytest.raises(ToolNotFoundError, match="X_PATH"):
        resolve_tool(str(tmp_path / "missing"), ["python"], "X_PATH")
