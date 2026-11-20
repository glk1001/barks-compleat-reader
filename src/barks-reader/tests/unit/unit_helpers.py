"""Stand-ins and small builders that more than one unit test file needs.

Reached as ``unit_helpers``: the conftest puts this directory on ``sys.path`` (see
there). Free of Kivy, so the core tests can use it; what needs Kivy is a conftest
fixture with its imports inside.
"""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from loguru import logger
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class FakeTreeViewNode:
    """A minimal node satisfying `SavableTreeViewNode` structurally."""

    def __init__(self, name: str, level: int, parent: FakeTreeViewNode | None = None) -> None:
        self._name = name
        self.level = level
        self.parent_node = parent
        self.nodes: list[FakeTreeViewNode] = []
        self.is_open = False
        self.saved_state: dict[str, Any] = {}

    def get_name(self) -> str:
        """Return the node's name, as a tree node does."""
        return self._name


def write_zip(zip_path: Path, entries: dict[str, str] | dict[str, bytes]) -> Path:
    """Write a zip holding each of `entries` under its name; return its path."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return zip_path


def image_bytes(fmt: str, size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    """Return a one-colour RGB image of `size`, encoded as `fmt` ("PNG", "JPEG")."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def run_frames(clock: MagicMock, frames: int) -> None:
    """Run what was scheduled on a mocked Clock, a frame at a time, as the clock would."""
    for _ in range(frames):
        if not clock.schedule_once.call_args_list:
            return
        callback = clock.schedule_once.call_args_list.pop(0).args[0]
        callback(0)


def progress_with_a_window(
    on_dismiss: MagicMock | None = None, *, before_return: Callable[[], None] | None = None
) -> Callable[..., tuple[Any, bool]]:
    """Return a stand-in for an installer's `run_showing_progress` whose window came up.

    It does the work, then shows what follows in the window, as the real one does,
    and answers that a window was shown.

    Args:
        on_dismiss: What the follow-on popup is handed to end the loop with.
        before_return: Called once the follow-on is shown, while the window is still up.

    """
    dismiss = on_dismiss if on_dismiss is not None else MagicMock()

    def run(work: Callable[[], Any], *_args: object, show_next: Any, **_kwargs: object) -> Any:  # noqa: ANN401
        result = work()
        show_next(result, dismiss)
        if before_return is not None:
            before_return()
        return result, True

    return run


def progress_with_a_window_logging_a_failed_follow_on() -> Callable[..., tuple[Any, bool]]:
    """Return the same stand-in, logging a follow-on that raises as the real one does."""

    def run(
        work: Callable[[], Any],
        *_args: object,
        show_next: Any,  # noqa: ANN401
        report_not_shown: str,
        **_kwargs: object,
    ) -> Any:  # noqa: ANN401
        result = work()
        try:
            show_next(result, MagicMock())
        except RuntimeError:
            logger.exception(report_not_shown)
        return result, True

    return run


def run_at_once(callback: Callable[[float], Any], *_args: object) -> None:
    """Stand in for `Clock.schedule_once` as its `side_effect`: no frame is waited for."""
    callback(0)


def run_last_scheduled(schedule: MagicMock, dt: float = 0) -> Any:  # noqa: ANN401
    """Run the callback last handed to a mocked `schedule_once` or `schedule_interval`.

    Returns:
        What the callback returned: an interval's callback says whether to go on.

    """
    return schedule.call_args.args[0](dt)
