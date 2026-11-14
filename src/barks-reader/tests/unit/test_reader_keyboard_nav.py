from __future__ import annotations

from barks_reader.ui.reader_keyboard_nav import clear_focus_highlight, draw_focus_highlight
from kivy.graphics import Line
from kivy.uix.widget import Widget

_GROUP = "test_focus_ring"


def _rings(widget: Widget) -> tuple[list[Line], list[Line]]:
    """Return the widget's focus rings under its children and over them."""
    canvas = widget.canvas
    assert canvas is not None

    def in_layer(layer: object) -> list[Line]:
        return [i for i in layer.get_group(_GROUP) if isinstance(i, Line)]  # ty: ignore[missing-attribute]

    return in_layer(canvas.before), in_layer(canvas.after)


class TestFocusRingLayer:
    def test_a_ring_is_drawn_over_the_children_by_default(self) -> None:
        widget = Widget()
        draw_focus_highlight(widget, _GROUP)

        under, over = _rings(widget)
        assert (len(under), len(over)) == (0, 1)

    def test_a_ring_under_the_children_leaves_a_caption_on_the_edge_on_top(self) -> None:
        widget = Widget()
        draw_focus_highlight(widget, _GROUP, under_children=True)

        under, over = _rings(widget)
        assert (len(under), len(over)) == (1, 0)

    def test_a_ring_under_the_children_follows_the_widget_there(self) -> None:
        widget = Widget()
        draw_focus_highlight(widget, _GROUP, under_children=True)
        first_ring = _rings(widget)[0][0]
        widget.size = (300, 200)

        # Redrawn for the new size, in the same layer, and only once.
        under, over = _rings(widget)
        assert (len(under), len(over)) == (1, 0)
        assert under[0] is not first_ring

    def test_clearing_removes_a_ring_from_either_layer(self) -> None:
        drawn_over, drawn_under = Widget(), Widget()
        draw_focus_highlight(drawn_over, _GROUP)
        draw_focus_highlight(drawn_under, _GROUP, under_children=True)

        clear_focus_highlight(drawn_over, _GROUP)
        clear_focus_highlight(drawn_under, _GROUP)

        assert _rings(drawn_over) == ([], [])
        assert _rings(drawn_under) == ([], [])
