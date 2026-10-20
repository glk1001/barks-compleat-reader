"""How a focused widget is named in the log (barks_reader.core.nav_focus)."""

from __future__ import annotations

from unittest.mock import MagicMock

from barks_reader.core.nav_focus import describe_widget, log_nav_focus


class TestDescribeWidget:
    """A widget is named by its class and its text, cut to one log line."""

    def test_long_text_is_cut_and_whitespace_collapsed(self) -> None:
        widget = MagicMock()
        widget.text = "a  very\nlong " * 10
        described = describe_widget(widget)
        assert described.startswith('MagicMock "a very long a very long')
        assert described.endswith('…"')
        assert "\n" not in described

    def test_blank_text_counts_as_none(self) -> None:
        widget = MagicMock()
        widget.text = "   "
        assert describe_widget(widget) == "MagicMock"

    def test_a_kivy_weak_proxy_is_named_for_what_it_wraps(self) -> None:
        """Widgets reached through `ids` are WeakProxy objects; the log names the real class."""

        class _RealButton:
            text = "Goto wiki page"

        real = _RealButton()
        proxy = MagicMock()
        proxy.__ref__ = lambda: real
        proxy.text = real.text
        assert describe_widget(proxy) == '_RealButton "Goto wiki page"'

    def test_a_widget_without_text_is_its_class_alone(self) -> None:
        assert describe_widget(MagicMock()) == "MagicMock"  # its .text is no str


def test_log_nav_focus_writes_the_focus_line(loguru_sink: list[str]) -> None:
    widget = MagicMock()
    widget.text = "Titles"
    log_nav_focus(widget)
    assert 'Nav focus on MagicMock "Titles".' in loguru_sink
