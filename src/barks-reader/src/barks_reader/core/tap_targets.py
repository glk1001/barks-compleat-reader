"""Where the app's tappable widgets are on screen, for the GUI tests that tap them.

A GUI test that taps a widget has to know where it is, and only the app knows
that. So a test asks: it writes a request id to the file named by
``TAP_TARGETS_FILE_ENV_VAR``, and the app answers with one ``TAP_TARGETS`` log
line listing every tappable widget it shows - its class, text, kv id and window
rectangle - once the layout has held still for two polls running (a list taken
mid-transition would send the tap to where a widget was). The GUI probe sets the
variable; with it unset, which is every normal run, the app never looks.

This module is the part without Kivy: the record, its encoding into the log
line and back, and the request/answer state. ``barks_reader.ui.tap_targets``
walks the widgets and drives it from a clock.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

TAP_TARGETS_FILE_ENV_VAR = "BARKS_READER_TAP_TARGETS_FILE"

# Work that is moving the layout on purpose and will move it again: the tree's
# scroll pinner, between a row expanding and its scroll correction a few frames
# later. A still layout is not enough - on a loaded machine the frames between
# are slow, and the uncorrected tree holds still for longer than two polls - so
# no request is answered while any of it runs.
_SETTLING: set[int] = set()


def settling_began(owner: object) -> None:
    """Note that `owner` has started moving the layout; answers wait until it ends."""
    _SETTLING.add(id(owner))


def settling_ended(owner: object) -> None:
    """Note that `owner` has finished moving the layout (a no-op if it never began)."""
    _SETTLING.discard(id(owner))


def layout_settling() -> bool:
    """Whether anything is still moving the layout on purpose."""
    return bool(_SETTLING)


@dataclass(frozen=True, slots=True)
class TapTarget:
    """One tappable thing on screen, in window pixels with the origin top-left.

    Attributes:
        kind: The widget's class name.
        text: Its text (a tree node's name, a region's name), or "".
        id: Its kv id, or "".
        left: Left edge, in window pixels.
        top: Top edge, in window pixels, counted down from the window's top.
        width: Width in window pixels.
        height: Height in window pixels.
        whole: False when a scroll view or the window edge hides part of it:
            the rectangle is then only the part on show, and a tap near its
            edge can land on what hides the rest.

    """

    kind: str
    text: str
    id: str
    left: int
    top: int
    width: int
    height: int
    whole: bool = True

    @property
    def center(self) -> tuple[int, int]:
        """The target's centre, in window pixels with the origin top-left."""
        return self.left + self.width // 2, self.top + self.height // 2

    def describe(self) -> str:
        """Name the target for a failure message: ``Button "Titles" #menu_button``."""
        name = self.kind
        if self.text:
            name += f' "{self.text}"'
        if self.id:
            name += f" #{self.id}"
        return name


def encode_targets(targets: Sequence[TapTarget]) -> str:
    """Return `targets` as the one-line JSON the ``TAP_TARGETS`` marker carries.

    Args:
        targets: The targets, in the order a touch would reach them.

    Returns:
        A JSON array with no newlines, non-ASCII text kept as it is.

    """
    return json.dumps([asdict(t) for t in targets], ensure_ascii=False, separators=(",", ":"))


def decode_targets(text: str) -> list[TapTarget]:
    """Return the targets a ``TAP_TARGETS`` line carries, from its JSON.

    Args:
        text: The JSON array `encode_targets` wrote.

    Returns:
        The targets, in the order they were logged.

    """
    return [TapTarget(**item) for item in json.loads(text)]


class TapTargetRequests:
    """The app's side of the request file: when to answer, and with what.

    Poll it on a clock. It answers a request only once two polls running have
    taken the same list, and never while `layout_settling`, so a layout still
    moving (a screen sliding in, a tree populating, a scroll) is never reported.
    """

    def __init__(self, request_file: Path) -> None:
        """Watch `request_file` for requests.

        Args:
            request_file: The file a test writes a request id into.

        """
        self._request_file = request_file
        self._last: list[TapTarget] | None = None

    def poll(
        self,
        snapshot: Callable[[], list[TapTarget]],
        busy: Callable[[], bool] = lambda: False,
    ) -> tuple[str, list[TapTarget]] | None:
        """Take a list if a request is waiting; return it once it is the same twice.

        Args:
            snapshot: Returns the targets on screen now.
            busy: Returns whether the layout is mid-change right now (a screen
                transition): no list is taken then, and the count starts again.

        Returns:
            ``(request id, targets)`` when the request is answered - the file is
            then gone - else None.

        """
        try:
            request = self._request_file.read_text(encoding="utf-8").strip()
        except OSError:
            self._last = None
            return None
        if not request:
            return None  # written but not yet filled in: look again next poll
        if layout_settling() or busy():
            self._last = None  # what was on screen before it began no longer counts
            return None
        targets = snapshot()
        if targets != self._last:
            self._last = targets
            return None
        self._last = None
        self._request_file.unlink(missing_ok=True)
        return request, targets
