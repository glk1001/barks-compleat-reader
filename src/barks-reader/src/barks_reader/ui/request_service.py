"""Poll a request file on the clock and answer what a GUI test writes there.

A test asks the running app for something (a memory census, a frame of the window) by
writing a request id to a file the GUI probe named in an environment variable; the
request file itself is ``barks_reader.core.memory_census.take_request``. With the
variable unset, which is every normal run, the app never looks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.clock import Clock
from loguru import logger

from barks_reader.core.memory_census import take_request

if TYPE_CHECKING:
    from collections.abc import Callable

# A test asks, then waits: four looks a second answer well inside its timeout.
POLL_SECS = 0.25

# The installed polls, held here because Kivy's clock only holds them weakly.
_SERVICES: list[Callable[[float], None]] = []


def install_request_service(
    request_file_env_var: str, what: str, answer: Callable[[str, Path], None]
) -> bool:
    """Answer the requests written to the file a variable names; do nothing with it unset.

    Args:
        request_file_env_var: The environment variable holding the request file's path.
        what: What is asked for, to start the log line ("Memory census").
        answer: Called with each request id and the request file's folder.

    Returns:
        Whether the service is running (the variable is set).

    """
    request_file = os.environ.get(request_file_env_var, "")
    if not request_file:
        return False
    path = Path(request_file)

    def poll(_dt: float) -> None:
        request = take_request(path)
        if request is not None:
            answer(request, path.parent)

    _SERVICES.append(poll)
    Clock.schedule_interval(poll, POLL_SECS)
    logger.info(f"{what}: answering requests in {request_file}.")
    return True
