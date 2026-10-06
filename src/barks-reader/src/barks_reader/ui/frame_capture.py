"""Answer a GUI test's frame request: what the window draws, saved as a PNG.

A test that judges whether the app drew anything (``barks_gui.shots``) once
judged a capture of the screen. On Windows a fullscreen window that has stood
for a few seconds can be handed the screen directly, and a screen capture then
reads black whatever the app drew: the soak failed so on 2026-10-03 and
2026-10-06, the reader showing a page all the while. So a test asks the app. It
writes a request id to the file named by ``FRAME_CAPTURE_FILE_ENV_VAR``, and the
app draws its whole window again into an off-screen buffer, saves that beside the
request file, and answers with one ``FRAME_CAPTURED`` log line naming it.

Drawn again rather than read back: what a window's buffer holds after it has been
shown is up to the driver. The GUI probe sets the variable; with it unset, which
is every normal run, the app never looks.
"""

# cspell:ignore stencilbuffer clearcolor

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import ClearBuffers, ClearColor, Fbo
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.memory_census import take_request

if TYPE_CHECKING:
    from collections.abc import Callable

FRAME_CAPTURE_FILE_ENV_VAR = "BARKS_READER_FRAME_CAPTURE_FILE"

# A test asks, then waits: four looks a second answer well inside its timeout.
POLL_SECS = 0.25

# The installed poll, held here because Kivy's clock only holds it weakly.
_SERVICE: list[Callable[[float], None]] = []


def capture_window(path: Path) -> tuple[int, int]:
    """Draw everything the window draws into an off-screen buffer and save it to `path`.

    Args:
        path: The PNG to write.

    Returns:
        The frame's width and height, in pixels.

    """
    width, height = (round(side) for side in Window.size)
    fbo = Fbo(size=(width, height), with_stencilbuffer=True)
    with fbo:
        ClearColor(*(Window.clearcolor or (0, 0, 0, 1)))
        ClearBuffers()
    fbo.add(Window.render_context)
    try:
        fbo.draw()
    finally:
        fbo.remove(Window.render_context)
    fbo.texture.save(str(path), flipped=True)
    return width, height


def answer(request: str, out_dir: Path) -> None:
    """Capture the window as ``frame-<request>.png`` in `out_dir` and log where."""
    path = out_dir / f"frame-{request}.png"
    width, height = capture_window(path)
    logger.debug(
        log_markers.FRAME_CAPTURED.format(request=request, width=width, height=height, path=path)
    )


def install_frame_capture_service() -> bool:
    """Answer frame requests when the GUI probe asked for them; else do nothing.

    Returns:
        Whether the service is running (the request file's variable is set).

    """
    request_file = os.environ.get(FRAME_CAPTURE_FILE_ENV_VAR, "")
    if not request_file:
        return False
    path = Path(request_file)

    def poll(_dt: float) -> None:
        request = take_request(path)
        if request is not None:
            answer(request, path.parent)

    _SERVICE.append(poll)
    Clock.schedule_interval(poll, POLL_SECS)
    logger.info(f"Frame capture: answering requests in {request_file}.")
    return True
