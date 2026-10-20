"""The log line every keyboard focus move ends in.

The GUI path tests wait on it instead of on the clock, so it is part of the nav
contract: every way of showing the focus (a drawn ring, a colour change) must reach
`log_nav_focus`. Kivy-free: a widget is named by duck typing, so a row of chips in
core can log its focus too.
"""

from __future__ import annotations

from loguru import logger

from . import log_markers

_MAX_LOGGED_TEXT = 40


def describe_widget(widget: object) -> str:
    """Name a widget for the log: its class, plus its text when it has some.

    Args:
        widget: The widget keyboard focus has landed on.

    Returns:
        ``Button "Titles"`` for a labelled widget, ``BoxLayout`` for one with no
        text; long text is cut so a log line stays one line.

    """
    # Widgets reached through `ids` arrive as Kivy WeakProxy objects; name what
    # they stand for.
    ref = getattr(widget, "__ref__", None)
    target = ref() if callable(ref) else None
    name = type(widget if target is None else target).__name__
    text = getattr(widget, "text", None)
    if not isinstance(text, str) or not text.strip():
        return name
    text = " ".join(text.split())
    if len(text) > _MAX_LOGGED_TEXT:
        text = text[: _MAX_LOGGED_TEXT - 1] + "…"
    return f'{name} "{text}"'


def log_nav_focus(widget: object) -> None:
    """Log that keyboard focus now sits on `widget`.

    Called by `draw_focus_highlight`, so every ring drawn logs itself; a focus
    shown some other way (a colour change, say) calls this directly.
    """
    logger.debug(log_markers.NAV_FOCUS.format(widget=describe_widget(widget)))
