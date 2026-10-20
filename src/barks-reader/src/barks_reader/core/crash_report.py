"""What the crash popup says: the error in a line, and the traceback with the system. Kivy-free."""

from __future__ import annotations

import platform
import traceback
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

from comic_utils.sys_utils import get_os_name, is_virtual_machine

from barks_reader._version import VERSION

if TYPE_CHECKING:
    from types import TracebackType


def crash_report(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> tuple[str, str]:
    """Return an uncaught exception as the popup's message and its details.

    Args:
        exc_type: The exception's type, as ``sys.excepthook`` gets it.
        exc_value: The exception.
        exc_traceback: Its traceback.

    Returns:
        The brief message, ``"ValueError: boom"``, and the details: the full traceback,
        then the app version, the system and the time.

    """
    stack = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

    message = f"{exc_type.__name__}: {exc_value}"

    details = dedent(f"""Full Traceback:
{stack}

System Information:
  - Version: {VERSION}
  - OS: {get_os_name()}
  - System: {platform.system()}
  - System Release: {platform.release()}
  - System Version: {platform.version()}
  - Processor: {platform.processor()}
  - Python Version: {platform.python_version()}
  - Virtual Machine: {is_virtual_machine()}
  - Cwd: {Path.cwd()}
  - Time: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}
""")

    return message, details
