"""The focus ring names where it landed, so a host's tests can step focus by the log."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kivy.graphics import Line
from kivy.uix.widget import Widget
from okf_reader.ui import focus_ring
from okf_reader.ui.focus_ring import (
    FOCUS_RING_GROUP,
    SIDEBAR_RING_GROUP,
    clear_focus_ring,
    describe_widget,
    draw_focus_ring,
)


def test_describe_names_the_class_and_text() -> None:
    widget = MagicMock()
    widget.text = "Back"
    assert describe_widget(widget) == 'MagicMock "Back"'


def test_describe_without_text_is_the_class_alone() -> None:
    widget = MagicMock()
    widget.text = ""
    assert describe_widget(widget) == "MagicMock"


def test_describe_cuts_long_text() -> None:
    widget = MagicMock()
    widget.text = "word " * 20
    described = describe_widget(widget)
    assert described.endswith('…"')
    assert len(described) < len(widget.text)


def test_drawing_a_ring_logs_it(kivy_log: list[str]) -> None:
    widget = MagicMock()
    widget.text = "Back"
    with patch.object(focus_ring, "Color"), patch.object(focus_ring, "Line"):
        draw_focus_ring(widget)
    assert 'OKFViewer: Focus ring on MagicMock "Back".' in kivy_log


def _ring_rectangles(widget: Widget, group: str = FOCUS_RING_GROUP) -> list[tuple[float, ...]]:
    lines = [
        i
        for i in widget.canvas.after.get_group(group)  # ty: ignore[missing-union-attribute]
        if isinstance(i, Line)
    ]
    # A Line's rectangle reads back as its outline's points: the corner and the size
    # are the first point and the span to the opposite one.
    return [tuple(line.points) for line in lines]


def _outline(x: float, y: float, width: float, height: float) -> tuple[float, ...]:
    with Widget().canvas:  # ty: ignore[invalid-context-manager]
        return tuple(Line(rectangle=(x, y, width, height)).points)


class TestTheRingDrawn:
    """On a real widget: one outline, where the widget is, for as long as it is asked for."""

    @staticmethod
    def _widget() -> Widget:
        return Widget(pos=(10, 20), size=(300, 40))

    def test_it_is_one_outline_of_the_widget(self) -> None:
        widget = self._widget()

        draw_focus_ring(widget)

        assert _ring_rectangles(widget) == [_outline(10, 20, 300, 40)]

    def test_it_follows_the_widget_as_it_moves_and_resizes(self) -> None:
        widget = self._widget()
        draw_focus_ring(widget)

        widget.pos = (50, 60)
        widget.size = (120, 30)

        assert _ring_rectangles(widget) == [_outline(50, 60, 120, 30)]

    def test_drawing_it_again_does_not_stack_a_second(self) -> None:
        widget = self._widget()

        draw_focus_ring(widget)
        draw_focus_ring(widget)
        widget.x = 11  # one redraw bound, not two

        assert _ring_rectangles(widget) == [_outline(11, 20, 300, 40)]

    def test_each_group_s_ring_is_its_own(self) -> None:
        widget = self._widget()
        draw_focus_ring(widget, group=SIDEBAR_RING_GROUP)

        assert _ring_rectangles(widget) == []
        assert len(_ring_rectangles(widget, SIDEBAR_RING_GROUP)) == 1

    def test_a_cleared_ring_is_gone_and_does_not_come_back(self) -> None:
        widget = self._widget()
        draw_focus_ring(widget)

        clear_focus_ring(widget)
        widget.pos = (50, 60)  # a layout pass after the clear

        assert _ring_rectangles(widget) == []

    def test_clearing_a_widget_that_has_no_ring_is_harmless(self) -> None:
        widget = self._widget()

        clear_focus_ring(widget)

        assert _ring_rectangles(widget) == []
