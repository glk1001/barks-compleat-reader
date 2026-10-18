"""The shared scroll view's `scroll_into_view`: content that fits the view stays at its top."""

from __future__ import annotations

from unittest.mock import patch

from barks_kivy_ui import scrolling
from barks_kivy_ui.scrolling import ReaderDropDown, ReaderScrollView, scroll_widget_into_view
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget


def _view_over(content_height: float) -> tuple[ReaderScrollView, Widget]:
    view = ReaderScrollView(size_hint=(None, None), size=(100, 100))
    content = Widget(size_hint=(None, None), size=(100, content_height))
    view.add_widget(content)
    return view, content


def test_content_taller_than_the_view_is_scrolled_to_the_widget() -> None:
    view, content = _view_over(500)
    with patch.object(ReaderScrollView, "scroll_to") as scroll_to:
        view.scroll_into_view(content, padding=20)
    scroll_to.assert_called_once_with(content, padding=20)


def test_content_that_fits_is_kept_at_its_top() -> None:
    """Kivy's ``scroll_to`` would leave ``scroll_y`` at 0.

    Content that later grows past the view would then show from its bottom.
    """
    view, content = _view_over(50)
    view.scroll_y = 0.0
    with patch.object(ReaderScrollView, "scroll_to") as scroll_to:
        view.scroll_into_view(content)
    scroll_to.assert_not_called()
    assert view.scroll_y == 1.0


def test_content_with_a_layout_pending_is_judged_once_it_has_run() -> None:
    """A list that just grew still measures as it was: judged now, it would be kept at the top."""
    view = ReaderScrollView(size_hint=(None, None), size=(100, 100))
    content = BoxLayout(size_hint=(None, None), size=(100, 50))
    view.add_widget(content)
    chip = Widget()
    content.add_widget(chip)  # leaves the layout pending, as adding a chip does
    layout_pending = content._trigger_layout  # noqa: SLF001 - Kivy's pending-layout trigger
    assert layout_pending is not None
    assert layout_pending.is_triggered
    with (
        patch.object(scrolling.Clock, "schedule_once") as schedule,
        patch.object(ReaderScrollView, "scroll_to") as scroll_to,
    ):
        view.scroll_into_view(chip, padding=5)
    scroll_to.assert_not_called()
    schedule.assert_called_once()
    content.height = 500  # the list grew (which arms the trigger again)
    layout_pending.cancel()  # and its layout has run
    with patch.object(ReaderScrollView, "scroll_to") as scroll_to:
        schedule.call_args[0][0](0)
    scroll_to.assert_called_once_with(chip, padding=5)


def test_a_view_with_no_content_does_nothing() -> None:
    view = ReaderScrollView()
    with patch.object(ReaderScrollView, "scroll_to") as scroll_to:
        scroll_widget_into_view(view, Widget())
    scroll_to.assert_not_called()


def test_a_dropdown_has_it_too() -> None:
    dropdown = ReaderDropDown()
    assert callable(dropdown.scroll_into_view)
