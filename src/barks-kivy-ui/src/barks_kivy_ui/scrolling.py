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


class ReaderScrollView(_ReaderScrollDefaults, ScrollView):
    """A ScrollView wearing the shared Barks Reader scroll-pane look."""


class ReaderDropDown(_ReaderScrollDefaults, DropDown):
    """A DropDown (itself a ScrollView) wearing the shared scroll-pane look."""
