"""The window's two modes and the windowed rectangle kept across fullscreen. Kivy-free.

The values the window manager (``ui/platform_window_utils.py``) and its platform
backends pass about; reading Kivy's window and moving it stay with them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class FullscreenEnum(Enum):
    """The window's two modes."""

    FULLSCREEN = "fullscreen"
    WINDOWED = "windowed"


def screen_mode(fullscreen: object) -> FullscreenEnum:
    """Return the mode a window is in, from Kivy's ``Window.fullscreen``.

    Args:
        fullscreen: Kivy's value: False or 0 windowed; True, "auto" or "fake" fullscreen.

    Returns:
        The mode.

    """
    return FullscreenEnum.FULLSCREEN if fullscreen else FullscreenEnum.WINDOWED


@dataclass(frozen=True, slots=True)
class WindowModeCallbacks:
    """The per-screen completion callbacks for one window-mode transition.

    Passed to ``WindowManager.goto_fullscreen_mode`` / ``goto_windowed_mode`` on
    each call rather than baked into the manager, so a single shared
    ``WindowManager`` can serve multiple screens.
    """

    on_windowed_first_resize: Callable[[], None]
    on_finished_windowed: Callable[[], None]
    on_finished_fullscreen: Callable[[], None]


@dataclass(slots=True)
class WindowState:
    """The windowed size and position saved for the return from fullscreen."""

    # In Window.system_size units, the ones a ``Window.size =`` restore takes. Window.size
    # reads in pixels, twice as many on a Retina Mac, so saving it doubled the window
    # on leaving fullscreen.
    size: tuple[int, int] = (0, 0)
    pos: tuple[int, int] = (-1, -1)

    def edges(self) -> tuple[int, int, int, int]:
        """Return the saved rectangle as its edges: left, top, right, bottom."""
        x, y = self.pos
        width, height = self.size
        return x, y, x + width, y + height

    def save(self, size: tuple[int, int], pos: tuple[int, int]) -> None:
        """Keep a window's size and position.

        Args:
            size: Its size, in ``Window.system_size`` units (not ``Window.size`` pixels).
            pos: Its left and top.

        """
        self.size = (size[0], size[1])
        self.pos = (pos[0], pos[1])

    def is_at(self, size: tuple[int, int], pos: tuple[int, int]) -> bool:
        """Return whether a window of `size` at `pos` is at the saved size and position."""
        return tuple(size) == self.size and tuple(pos) == self.pos

    def is_unsaved(self) -> bool:
        """Return True while no geometry has been captured (still the defaults).

        ``goto_fullscreen_mode`` skips its save when the window is *already*
        fullscreen (e.g. at app start), so a later windowed restore can be
        reached with nothing to restore. Restoring the sentinel would apply a
        nonsense size/position, so the restore guards on this.

        A real window can sit at (-1, -1), and would read as unsaved here: its
        restore is then skipped. Not seen in use, and left so.
        """
        return self.size == (0, 0) or self.pos == (-1, -1)
