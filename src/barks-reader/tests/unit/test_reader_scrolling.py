"""Unit tests for the shared scroll-pane classes (barks_kivy_ui.scrolling).

Pin the shared defaults and, above all, the precedence rule the design rests
on: constructor kwargs beat a kv class rule, which beats the class default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_kivy_ui.scrolling import ReaderDropDown, ReaderScrollView
from kivy.effects.scroll import ScrollEffect
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.dropdown import DropDown

if TYPE_CHECKING:
    from kivy.uix.scrollview import ScrollView


def _assert_shared_defaults(widget: ScrollView) -> None:
    assert widget.scroll_type == ["bars", "content"]
    assert widget.effect_cls is ScrollEffect
    assert widget.always_overscroll is False
    assert widget.do_scroll_x is False
    assert widget.bar_width == dp(12)


class TestSharedDefaults:
    def test_scroll_view_defaults(self) -> None:
        _assert_shared_defaults(ReaderScrollView())

    def test_drop_down_defaults(self) -> None:
        drop_down = ReaderDropDown()
        assert isinstance(drop_down, DropDown)
        _assert_shared_defaults(drop_down)

    def test_kwargs_override_the_defaults(self) -> None:
        """A horizontal scroller (the wiki's wide tables) keeps its axes."""
        widget = ReaderScrollView(do_scroll_x=True, do_scroll_y=False)
        assert widget.do_scroll_x is True
        assert widget.do_scroll_y is False


class TestKvRulePrecedence:
    """The app's kivy_helpers.kv rule themes bar colours; kwargs must still win."""

    RULE = "<ReaderScrollView>:\n    bar_color: (1, 0, 0, 1)\n"

    def test_class_rule_overrides_the_class_default_but_not_a_kwarg(self) -> None:
        Builder.load_string(self.RULE)
        try:
            assert ReaderScrollView().bar_color == [1, 0, 0, 1]
            assert ReaderScrollView(bar_color=(0, 1, 0, 1)).bar_color == [0, 1, 0, 1]
        finally:
            Builder.unload_file(self.RULE)
