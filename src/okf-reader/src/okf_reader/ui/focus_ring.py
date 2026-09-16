"""Keyboard focus-ring drawing for the OKF viewer.

A trimmed local equivalent of the Barks Reader's ``draw_focus_highlight``
(``barks_reader.ui.reader_keyboard_nav``), which this standalone package cannot
import: a rectangular outline on ``canvas.after`` that follows the widget
through moves and resizes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.graphics import Color, Line

from . import trace

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

_MAX_LOGGED_TEXT = 40


def describe_widget(widget: Widget) -> str:
    """Name a widget for the log: its class, plus its text when it has some.

    Args:
        widget: The widget the ring was drawn on.

    Returns:
        ``ActionButton "Back"`` for a labelled widget, ``BoxLayout`` for one
        with no text; long text is cut so a log line stays one line.

    """
    name = type(widget).__name__
    text = getattr(widget, "text", None)
    if not isinstance(text, str) or not text.strip():
        return name
    text = " ".join(text.split())
    if len(text) > _MAX_LOGGED_TEXT:
        text = text[: _MAX_LOGGED_TEXT - 1] + "\u2026"
    return f'{name} "{text}"'


FOCUS_RING_GROUP = "okf_focus_ring"
SIDEBAR_RING_GROUP = "okf_sidebar_ring"
# Gold — the page-heading/concept accent, marking the focused item.
FOCUS_RING_COLOR = (1.0, 0.835, 0.29, 1.0)
# The sidebar's "this region owns the keys" ring color is themable and lives on
# `ViewerThemeSpec.focus_ring` (default: link blue); the viewer passes it into
# `draw_focus_ring` for the sidebar group.


def draw_focus_ring(
    widget: Widget,
    group: str = FOCUS_RING_GROUP,
    color: tuple[float, float, float, float] = FOCUS_RING_COLOR,
    line_width: float = 2.0,
) -> None:
    """Draw (or refresh) a rectangular focus ring around ``widget``.

    The ring is drawn on ``canvas.after`` under ``group`` and redrawn whenever
    the widget moves or resizes, so it survives deferred Kivy layout passes.

    Args:
        widget: The widget to outline.
        group: Canvas instruction group naming this ring.
        color: RGBA of the ring.
        line_width: Outline width in pixels.

    """
    clear_focus_ring(widget, group)

    def redraw(*_args: object) -> None:
        widget.canvas.after.remove_group(group)  # ty: ignore[unresolved-attribute]
        with widget.canvas.after:  # ty: ignore[unresolved-attribute]
            Color(*color, group=group)
            Line(
                rectangle=(widget.x, widget.y, widget.width, widget.height),
                width=line_width,
                group=group,
            )

    widget.bind(pos=redraw, size=redraw)
    widget._focus_ring_cb = redraw  # noqa: SLF001
    redraw()
    trace.focus_ring(describe_widget(widget))


def clear_focus_ring(widget: Widget, group: str = FOCUS_RING_GROUP) -> None:
    """Remove the focus ring drawn by `draw_focus_ring`, if any."""
    redraw = getattr(widget, "_focus_ring_cb", None)
    if redraw is not None:
        widget.unbind(pos=redraw, size=redraw)
        widget._focus_ring_cb = None  # noqa: SLF001
    widget.canvas.after.remove_group(group)  # ty: ignore[unresolved-attribute]
