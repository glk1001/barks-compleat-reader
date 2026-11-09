"""What the crash popup says (barks_reader.core.crash_report)."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import barks_reader.core.crash_report as crash_report_module
import pytest
from barks_reader._version import VERSION
from barks_reader.core.crash_report import crash_report

if TYPE_CHECKING:
    from types import TracebackType


def test_a_traceback_becomes_the_message_and_the_details() -> None:
    try:
        msg = "boom"
        raise ValueError(msg)  # noqa: TRY301
    except ValueError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    assert exc_type is not None
    assert exc_value is not None

    with patch.object(crash_report_module, "datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 21, 1, 2, 3, tzinfo=UTC)
        message, details = crash_report(exc_type, exc_value, exc_traceback)

    assert message == "ValueError: boom"
    stack = "".join(traceback.format_exception(exc_value))
    assert details.startswith(f"Full Traceback:\n{stack}\n\nSystem Information:\n")
    assert stack.startswith("Traceback (most recent call last):\n  File ")
    assert stack.endswith("ValueError: boom\n")
    assert f"  - Version: {VERSION}\n" in details
    assert "  - Python Version: " in details
    clock.now.assert_called_once_with(UTC)  # the time is UTC, whatever the machine's zone
    assert details.endswith("  - Time: 2026-10-21 01:02:03\n")


def test_the_system_section_is_one_line_per_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    probes = (("System", lambda: "Linux"), ("Release", lambda: "7.0"))
    monkeypatch.setattr(crash_report_module, "_SYSTEM_PROBES", probes)

    with patch.object(crash_report_module, "datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 21, 1, 2, 3, tzinfo=UTC)
        _message, details = crash_report(*_raised())

    assert details.endswith(
        "\n\nSystem Information:\n  - System: Linux\n  - Release: 7.0\n"
        "  - Time: 2026-10-21 01:02:03\n"
    )


def _raised() -> tuple[type[BaseException], BaseException, TracebackType | None]:
    try:
        msg = "boom"
        raise ValueError(msg)  # noqa: TRY301
    except ValueError as exc:
        return type(exc), exc, exc.__traceback__


@pytest.mark.parametrize(
    ("label", "error"),
    [
        ("Cwd", FileNotFoundError(2, "No such file or directory")),  # a deleted working folder
        ("Virtual Machine", OSError("cannot start")),  # the VM check's subprocess
    ],
)
def test_a_failed_probe_does_not_lose_the_report(
    monkeypatch: pytest.MonkeyPatch, label: str, error: OSError
) -> None:
    """The report is built while the app is failing; a probe failing too must not hide it."""

    def failing() -> object:
        raise error

    probes = tuple(
        (name, failing if name == label else read)
        for name, read in crash_report_module._SYSTEM_PROBES  # noqa: SLF001
    )
    monkeypatch.setattr(crash_report_module, "_SYSTEM_PROBES", probes)

    message, details = crash_report(*_raised())

    assert message == "ValueError: boom"
    assert f"  - {label}: unknown ({type(error).__name__}: {error})\n" in details
    assert f"  - Version: {VERSION}\n" in details
    assert "  - Time: " in details
