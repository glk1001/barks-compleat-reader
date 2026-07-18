"""Keyboard focus-ring drawing for the OKF viewer.

A trimmed local equivalent of the Barks Reader's ``draw_focus_highlight``
(``barks_reader.ui.reader_keyboard_nav``), which this standalone package cannot
import: a rectangular outline on ``canvas.after`` that follows the widget
through moves and resizes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.graphics import Color, Line

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

FOCUS_RING_GROUP = "okf_focus_ring"
SIDEBAR_RING_GROUP = "okf_sidebar_ring"
# Gold — the page-heading/concept accent, marking the focused item.
FOCUS_RING_COLOR = (1.0, 0.835, 0.29, 1.0)
# Link blue — the "this region owns the keys" indicator around the sidebar.
SIDEBAR_RING_COLOR = (0.306, 0.631, 1.0, 0.9)


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


def clear_focus_ring(widget: Widget, group: str = FOCUS_RING_GROUP) -> None:
    """Remove the focus ring drawn by `draw_focus_ring`, if any."""
    redraw = getattr(widget, "_focus_ring_cb", None)
    if redraw is not None:
        widget.unbind(pos=redraw, size=redraw)
        widget._focus_ring_cb = None  # noqa: SLF001
    widget.canvas.after.remove_group(group)  # ty: ignore[unresolved-attribute]
