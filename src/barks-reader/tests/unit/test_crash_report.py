"""What the crash popup says (barks_reader.core.crash_report)."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime
from unittest.mock import patch

import barks_reader.core.crash_report as crash_report_module
from barks_reader._version import VERSION
from barks_reader.core.crash_report import crash_report


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
