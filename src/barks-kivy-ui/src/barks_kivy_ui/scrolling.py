"""The one scroll-pane look shared by every scrollbar in the Barks Reader.

Every scrollable widget (plain scroll panes and DropDowns alike, DropDown being
a ScrollView subclass) must look and behave the same: a 12dp bar that can be
dragged (``scroll_type`` includes "bars"; with Kivy's default ``['content']``
the bar renders but ignores the mouse), a ``ScrollEffect`` that stops dead at
the edges instead of rubber-banding, and no overscroll bounce for content that
already fits.

Precedence rule (verified against Kivy 2.3.1, ``Widget.__init__`` applies kv
class rules with ``ignored_consts=self._kwargs_applied_init``):

    constructor kwargs  >  kv class rule  >  class-level property default

The defaults here are therefore *redeclared Kivy properties*, never
``kwargs.setdefault`` in ``__init__`` -- a kwarg-supplied value would be
treated as caller intent and silently block the app's kv rule (which themes
``bar_color``/``bar_inactive_color`` from the active palette). The neutral
greys below are what a widget wears when no such rule is loaded: the pre-app
error/first-run popups and the standalone okf launcher.

This package depends only on kivy; the themed colours live with the app's kv.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.effects.scroll import ScrollEffect
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    OptionProperty,
)
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

# Kivy's own option list for ScrollView.scroll_type.
_SCROLL_TYPE_OPTIONS = (["content"], ["bars"], ["bars", "content"], ["content", "bars"])


class _ReaderScrollDefaults:
    """Redeclared ScrollView properties carrying the shared defaults.

    Mixed in ahead of the Kivy base so Kivy's property discovery, which walks
    the MRO most-derived first, picks these over ``ScrollView``'s. ``bar_width``
    is the string form: ``dp()`` at import time would initialise the Window
    before the entry point has configured it.
    """

    do_scroll_x = BooleanProperty(defaultvalue=False)
    scroll_type = OptionProperty(["bars", "content"], options=_SCROLL_TYPE_OPTIONS)
    always_overscroll = BooleanProperty(defaultvalue=False)
    effect_cls = ObjectProperty(ScrollEffect, allownone=True)
    bar_width = NumericProperty("12dp")
    bar_color = ColorProperty((0.7, 0.7, 0.7, 0.9))
    bar_inactive_color = ColorProperty((0.7, 0.7, 0.7, 0.4))


def scroll_widget_into_view(
    scroll_view: ScrollView, widget: Widget, *, padding: float = 10
) -> None:
    """Scroll `scroll_view` so `widget` shows, when its content is taller than the view.

    Kivy's ``scroll_to`` on content no taller than the view converts the distance over
    no scrollable height and leaves ``scroll_y`` at 0: nothing moves, the content
    staying at the top, until the content grows past the view and shows from its
    bottom (a keyboard focus on a short tag list, then a group opened under it).
    Content that fits is kept at its top instead. The fit is judged once a layout the
    content has pending has run, as ``scroll_to`` waits for one: judged before, a list
    that just grew still measures as it was.

    Args:
        scroll_view: The scroll view.
        widget: A widget in its content.
        padding: The space to leave between the widget and the view's edge, in dp
            (``scroll_to`` applies ``dp()`` itself).

    """
    content = scroll_view.children[0] if scroll_view.children else None
    if content is None:
        return
    layout_trigger = getattr(content, "_trigger_layout", None)  # a Layout's, if one
    if layout_trigger is not None and layout_trigger.is_triggered:
        Clock.schedule_once(
            lambda _dt: scroll_widget_into_view(scroll_view, widget, padding=padding)
        )
        return
    if content.height > scroll_view.height:
        scroll_view.scroll_to(widget, padding=padding)
    else:
        scroll_view.scroll_y = 1.0


class ReaderScrollView(_ReaderScrollDefaults, ScrollView):
    """A ScrollView wearing the shared Barks Reader scroll-pane look."""

    def scroll_into_view(self, widget: Widget, *, padding: float = 10) -> None:
        """Scroll so `widget` shows; content that fits stays at its top."""
        scroll_widget_into_view(self, widget, padding=padding)


class ReaderDropDown(_ReaderScrollDefaults, DropDown):
    """A DropDown (itself a ScrollView) wearing the shared scroll-pane look."""

    def scroll_into_view(self, widget: Widget, *, padding: float = 10) -> None:
        """Scroll so `widget` shows; content that fits stays at its top."""
        scroll_widget_into_view(self, widget, padding=padding)

    def open_if_shown(self, widget: Widget) -> bool:
        """Open on ``widget`` if it is in a window, else leave the dropdown closed.

        Kivy's ``open`` raises on a widget with no window, and every widget of a
        screen has none while a fade between screens draws them offscreen. A key
        pressed in that moment must do nothing, not end the app. A dropdown already
        open (by mouse, say, the keys now asking) is left open and counted as opened:
        Kivy raises on adding it to the window a second time.

        Args:
            widget: The widget to open the dropdown on.

        Returns:
            Whether the dropdown is open.

        """
        if self.parent is not None:
            return True
        if widget.get_parent_window() is None:
            return False
        self.open(widget)
        return True
