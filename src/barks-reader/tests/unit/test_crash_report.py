"""What the crash popup says (barks_reader.core.crash_report)."""

from __future__ import annotations

import sys

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

    message, details = crash_report(exc_type, exc_value, exc_traceback)

    assert message == "ValueError: boom"
    assert details.startswith("Full Traceback:\nTraceback (most recent call last):")
    assert "raise ValueError(msg)" in details
    assert f"  - Version: {VERSION}\n" in details
    assert "  - Python Version: " in details
