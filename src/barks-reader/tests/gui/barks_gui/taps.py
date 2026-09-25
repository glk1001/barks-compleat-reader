"""Tap what the app shows by name: its tap targets, asked for and read back from the log.

The suite never taps a pixel it worked out itself. It asks the app where its
tappable widgets are (``barks_reader.core.tap_targets``: a request id in, one
``TAP_TARGETS`` line out, once the layout is still) and taps the centre of the
one it names - by text, kv id or class - so a layout, font or theme change moves
the tap with the widget. A tap is a click, or in touch mode (the runner's
``--touch``, ``BARKS_PROBE_TOUCH=1``) a finger on a virtual touchscreen as well.
"""

from __future__ import annotations

import itertools
import os
import re
from typing import TYPE_CHECKING

from barks_gui.logs import messages
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.tap_targets import TapTarget, decode_targets

if TYPE_CHECKING:
    from gui_driver import Driver


class TapOutsideWindowError(AssertionError):
    """A target the app places outside the window the display actually shows.

    With no window manager on the nested display, "fullscreen" does not resize
    the window: the app draws a screen-sized frame into the windowed-size window,
    and what falls outside it cannot be tapped.
    """


TOUCH_ENV_VAR = "BARKS_PROBE_TOUCH"
ANSWER_TIMEOUT = 10

# Unique within a run: each test boots its own app, so a count is enough.
_REQUESTS = itertools.count(1)


def touch_mode() -> bool:
    """Whether this run taps by touch as well as by click (the runner's ``--touch``)."""
    return os.environ.get(TOUCH_ENV_VAR) == "1"


def targets(d: Driver) -> tuple[tuple[int, int], list[TapTarget]]:
    """Ask the app for its tap targets and return its window size and them.

    Args:
        d: The driver.

    Returns:
        ``((width, height), targets)``: the size the positions are measured in,
        and the targets in the order a press reaches them.

    """
    request = str(next(_REQUESTS))
    with d.expect(pattern(markers.TAP_TARGETS, request=request), ANSWER_TIMEOUT):
        d.request_tap_targets(request)
    regex = re.compile(
        pattern(
            markers.TAP_TARGETS,
            request=request,
            width=re.compile(r"(?P<width>\d+)"),
            height=re.compile(r"(?P<height>\d+)"),
            targets=re.compile(r"(?P<targets>\[.*\])"),
        )
    )
    text = messages(d.log_path.read_text(encoding="utf-8", errors="replace"))
    found = regex.search(text)
    assert found is not None, (
        f"the app answered tap-targets request {request} in a line this cannot read"
    )
    return (int(found["width"]), int(found["height"])), decode_targets(found["targets"])


def find(
    shown: list[TapTarget],
    *,
    text: str | re.Pattern[str] | None = None,
    kind: str | None = None,
    kv_id: str | None = None,
) -> TapTarget:
    """Return the first target that matches every criterion given, a whole one if any.

    A target a scroll view or the window edge cuts off is passed over while a
    whole one matches: a tap near a cut edge can land on what hides the rest.

    Args:
        shown: The targets, as `targets` returned them.
        text: The target's text exactly, or a regex it must fully match.
        kind: Its class name.
        kv_id: Its kv id.

    Raises:
        AssertionError: If none matches, naming what was on screen.

    """
    matches = [
        target
        for target in shown
        if (kind is None or target.kind == kind)
        and (kv_id is None or target.id == kv_id)
        and (not isinstance(text, re.Pattern) or text.fullmatch(target.text))
        and (not isinstance(text, str) or target.text == text)
    ]
    whole = [target for target in matches if target.whole]
    if whole or matches:
        return (whole or matches)[0]
    wanted = ", ".join(
        f"{name}={value!r}"
        for name, value in (("text", text), ("kind", kind), ("kv_id", kv_id))
        if value is not None
    )
    on_screen = "\n  ".join(t.describe() for t in shown) or "(nothing tappable)"
    msg = f"no tap target with {wanted}; on screen:\n  {on_screen}"
    raise AssertionError(msg)


def tap(
    d: Driver,
    *,
    text: str | re.Pattern[str] | None = None,
    kind: str | None = None,
    kv_id: str | None = None,
) -> TapTarget:
    """Tap the centre of the target named, as the app shows it now, and return it.

    Args:
        d: The driver.
        text: The target's text exactly, or a regex it must fully match.
        kind: Its class name.
        kv_id: Its kv id.

    """
    _, shown = targets(d)
    target = find(shown, text=text, kind=kind, kv_id=kv_id)
    # The app's window pixels are the probe's, unscaled; but the window may be
    # smaller than the app believes (see TapOutsideWindowError).
    x, y = target.center
    win_w, win_h, _, _ = d.window_geometry()
    if not (0 <= x < win_w and 0 <= y < win_h):
        msg = (
            f"{target.describe()} is at ({x}, {y}), outside the {win_w}x{win_h} window the"
            " display shows"
        )
        raise TapOutsideWindowError(msg)
    d.tap(x, y)
    return target


def tap_then_wait(
    d: Driver,
    wait: str,
    *,
    text: str | re.Pattern[str] | None = None,
    kind: str | None = None,
    kv_id: str | None = None,
    timeout: float = 15,
) -> TapTarget:
    """Tap the target named, then block until a NEW line matching `wait` is logged."""
    with d.expect(wait, timeout):
        return tap(d, text=text, kind=kind, kv_id=kv_id)


def tap_outside(d: Driver, *, kind: str) -> tuple[int, int]:
    """Tap the window outside the open popup of class `kind`, which closes most popups.

    Args:
        d: The driver.
        kind: The popup's class name, as the tap targets list it.

    Returns:
        The window pixel tapped.

    Raises:
        AssertionError: If the popup fills the window, leaving nowhere to tap.

    """
    (width, height), shown = targets(d)
    panel = find(shown, kind=kind)
    gaps = [
        (panel.top, (width // 2, panel.top // 2)),
        (
            height - (panel.top + panel.height),
            (width // 2, (panel.top + panel.height + height) // 2),
        ),
        (panel.left, (panel.left // 2, height // 2)),
        (
            width - (panel.left + panel.width),
            ((panel.left + panel.width + width) // 2, height // 2),
        ),
    ]
    size, point = max(gaps)
    assert size >= 2, f"{panel.describe()} fills the window: nowhere outside it to tap"  # noqa: PLR2004
    d.tap(*point)
    return point
