"""Answer a GUI test's tap-targets request: every tappable widget on screen, and where.

The request and its answer are ``barks_reader.core.tap_targets``; this is the
widget walk behind the answer. A target is a widget a press acts on - a button
(tree nodes, index items and menu entries are all buttons), a tree node, a text
input, the virtual keyboard, an open popup's panel - or a region a widget names itself through a
``tap_target_regions()`` method returning ``{name: Rect}`` in window pixels (the
reader's page-turn margins). Its rectangle is what a
press can reach: clipped to every scroll view above it and to the window, with
what sits under an open popup left out, since the popup takes every touch.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from kivy.clock import Clock
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.stencilview import StencilView
from kivy.uix.textinput import TextInput
from kivy.uix.treeview import TreeViewNode
from kivy.uix.vkeyboard import VKeyboard
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.tap_targets import (
    TAP_TARGETS_FILE_ENV_VAR,
    TapTarget,
    TapTargetRequests,
    encode_targets,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.widget import Widget

# Ten polls a second: an answer comes within two of the layout coming to rest.
POLL_SECS = 0.1

Rect = tuple[float, float, float, float]  # x, y, w, h in window pixels, origin bottom-left

# The installed poll, held here because Kivy's clock only holds it weakly.
_SERVICE: list[Callable[[float], None]] = []

# A popup is listed too, as the panel it is: a tap outside it closes most of them.
_TAPPABLE = (ButtonBehavior, TreeViewNode, TextInput, VKeyboard, ModalView)
_MARKUP_TAG_RE = re.compile(r"\[/?[a-z_]+(?:=[^\]]*)?\]")
# Kivy markup's escapes for its own brackets, and the ampersand last.
_MARKUP_ESCAPES = (("&bl;", "["), ("&br;", "]"), ("&amp;", "&"))


def window_rect(widget: Widget, x: float, y: float, width: float, height: float) -> Rect:
    """Return a rectangle in `widget`'s position space as a window rectangle.

    Args:
        widget: The widget whose ``pos`` shares the space `x` and `y` are in.
        x: Left edge.
        y: Bottom edge.
        width: Width.
        height: Height.

    Returns:
        ``(x, y, w, h)`` in window pixels, origin bottom-left.

    """
    wx, wy = widget.to_window(x, y)
    return wx, wy, width, height


def _intersect(a: Rect, b: Rect) -> Rect:
    left = max(a[0], b[0])
    bottom = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    top = min(a[1] + a[3], b[1] + b[3])
    return left, bottom, max(0.0, right - left), max(0.0, top - bottom)


def _deref(value: Any) -> Any:  # noqa: ANN401
    """Return what a Kivy WeakProxy (as ``ids`` holds) stands for, or the value itself."""
    ref = getattr(value, "__ref__", None)
    return ref() if callable(ref) else value


def _kv_id(widget: Widget) -> str:
    """Return the kv id a rule above `widget` gave it, or ""."""
    ancestor = widget.parent
    while ancestor is not None:
        for name, value in getattr(ancestor, "ids", {}).items():
            if _deref(value) is widget:
                return name
        if ancestor.parent is ancestor:
            break  # the window, which is its own parent
        ancestor = ancestor.parent
    return ""


def _text(widget: Widget) -> str:
    """Return what a test names `widget` by: a tree node's name, else its visible text."""
    get_name = getattr(widget, "get_name", None)
    if isinstance(widget, TreeViewNode) and callable(get_name):
        name = get_name()
        if isinstance(name, str) and name != "<unknown>":
            return name
    text = getattr(widget, "text", None)
    if not isinstance(text, str):
        title = getattr(widget, "title", None)  # a popup's
        return " ".join(title.split()) if isinstance(title, str) else ""
    if getattr(widget, "markup", False):
        text = _MARKUP_TAG_RE.sub("", text)
        for escape, char in _MARKUP_ESCAPES:
            text = text.replace(escape, char)
    return " ".join(text.split())


def _target(
    kind: str, text: str, kv_id: str, rect: Rect, window_height: float, *, whole: bool
) -> TapTarget:
    x, y, w, h = rect
    return TapTarget(
        kind=kind,
        text=text,
        id=kv_id,
        left=round(x),
        top=round(window_height - (y + h)),
        width=round(w),
        height=round(h),
        whole=whole,
    )


def _is_whole(clipped: Rect, full: Rect) -> bool:
    """Whether clipping left the rectangle as it was, to within half a pixel."""
    return all(abs(a - b) < 0.5 for a, b in zip(clipped, full, strict=True))  # noqa: PLR2004


def _collect(widget: Widget, clip: Rect, window_height: float, out: list[TapTarget]) -> None:
    if widget.opacity == 0 or widget.disabled:
        return  # hidden, or taking no presses (a hidden action bar is both)
    kind = type(widget).__name__
    full = window_rect(widget, widget.x, widget.y, widget.width, widget.height)
    own = _intersect(full, clip)
    if isinstance(widget, _TAPPABLE) and own[2] >= 1 and own[3] >= 1:
        out.append(
            _target(
                kind, _text(widget), _kv_id(widget), own, window_height, whole=_is_whole(own, full)
            )
        )
    get_regions = getattr(widget, "tap_target_regions", None)
    if callable(get_regions):
        kv_id = _kv_id(widget)
        regions = cast("Callable[[], dict[str, Rect]]", get_regions)()
        for name, region in regions.items():
            rect = _intersect(region, clip)
            if rect[2] >= 1 and rect[3] >= 1:
                out.append(
                    _target(kind, name, kv_id, rect, window_height, whole=_is_whole(rect, region))
                )
    # A scroll view (every StencilView) shows its children only inside itself.
    inner = own if isinstance(widget, StencilView) else clip
    for child in widget.children:  # children[0] is on top: the order a press tries them
        _collect(child, inner, window_height, out)


def _screen_changing(widget: Any) -> bool:  # noqa: ANN401
    """Whether a screen manager at or under `widget` is mid-transition.

    Between two screens the one going and the one coming may both show nothing
    tappable (the reader holds itself back until its first page), and a list taken
    then is empty however still it holds.
    """
    if isinstance(widget, ScreenManager) and widget.transition.is_active:
        return True
    return any(_screen_changing(child) for child in widget.children)


def screen_changing(window: Any) -> bool:  # noqa: ANN401
    """Whether any screen manager in `window` is mid-transition."""
    return any(_screen_changing(child) for child in window.children)


def snapshot(window: Any) -> list[TapTarget]:  # noqa: ANN401
    """Return every tappable target `window` shows, in the order a press reaches them.

    Args:
        window: The Kivy window.

    Returns:
        The targets, in window pixels with the origin top-left.

    """
    children = list(window.children)
    if children and isinstance(children[0], ModalView):
        children = children[:1]  # an open popup takes every press
    window_clip: Rect = (0.0, 0.0, float(window.width), float(window.height))
    out: list[TapTarget] = []
    for child in children:
        _collect(child, window_clip, float(window.height), out)
    return out


def install_tap_targets_service(window: Any) -> bool:  # noqa: ANN401
    """Answer tap-targets requests when the GUI probe asked for them; else do nothing.

    Args:
        window: The Kivy window.

    Returns:
        Whether the service is running (the request file's variable is set).

    """
    request_file = os.environ.get(TAP_TARGETS_FILE_ENV_VAR, "")
    if not request_file:
        return False
    requests = TapTargetRequests(Path(request_file))

    def poll(_dt: float) -> None:
        answer = requests.poll(lambda: snapshot(window), lambda: screen_changing(window))
        if answer is None:
            return
        request, targets = answer
        logger.debug(
            log_markers.TAP_TARGETS.format(
                request=request,
                width=round(window.width),
                height=round(window.height),
                targets=encode_targets(targets),
            )
        )

    # Kivy's clock holds its callbacks weakly: the poll must be kept alive here.
    _SERVICE.append(poll)
    Clock.schedule_interval(poll, POLL_SECS)
    logger.info(f"Tap targets: answering requests in {request_file}.")
    return True
