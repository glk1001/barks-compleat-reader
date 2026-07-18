"""Kivy-free keyboard-navigation logic for the OKF viewer.

Key constants, the focus-region model, and the pure calculations behind the
viewer's keyboard handling: scroll stepping, link/list cycling, and the
focused-link markup rewrite. Lives in ``okf_reader.ui`` beside the viewer but
imports no Kivy, so everything here is unit-testable without a window.

The key codes are the SDL2 values Kivy reports in its window keyboard events.
They mirror the hosting Barks Reader's ``reader_keyboard_nav`` constants, which
this standalone package cannot import.
"""

from __future__ import annotations

import re
from enum import Enum, auto

KEY_TAB = 9
KEY_ENTER = 13
KEY_ESCAPE = 27
KEY_F = ord("f")
KEY_NUMPAD_ENTER = 271
KEY_UP = 273
KEY_DOWN = 274
KEY_RIGHT = 275
KEY_LEFT = 276
KEY_HOME = 278
KEY_END = 279
KEY_PAGE_UP = 280
KEY_PAGE_DOWN = 281

# Focused-link color (the page-heading gold): swapped in for the link blue on
# the focused ref span only — a pure color change cannot reflow the label.
LINK_FOCUS_COLOR = "ffd54a"
# Vertical dp one Up/Down press moves the page (about three body lines).
PAGE_LINE_STEP = 60
# Dp of the previous view kept visible across a PageUp/PageDown step.
PAGE_STEP_OVERLAP = 40


class FocusRegion(Enum):
    """Which pane owns the navigation keys: the page body or the left sidebar."""

    PAGE = auto()
    SIDEBAR = auto()


def scroll_step(scroll_y: float, viewport_h: float, content_h: float, delta_px: float) -> float:
    """Return the new scroll offset after moving the view down the content.

    Args:
        scroll_y: Current normalized offset (1.0 = top, 0.0 = bottom).
        viewport_h: Height of the scroll viewport, in pixels.
        content_h: Height of the scrolled content, in pixels.
        delta_px: Pixels to move down the document (negative moves up).

    Returns:
        The new normalized offset, clamped to [0.0, 1.0] — pinned to 1.0 when
        the content fits the viewport (nothing to scroll).

    """
    scrollable = content_h - viewport_h
    if scrollable <= 0:
        return 1.0
    return max(0.0, min(1.0, scroll_y - delta_px / scrollable))


def advance_index(current: int | None, count: int, delta: int) -> int | None:
    """Return the next index stepping through ``count`` items, stopping at the ends.

    ``None`` means "no focus yet": stepping forward starts at the first item,
    stepping backward at the last. Thereafter the index clamps — no wrap-around,
    so reaching the last item never jumps the view back to the first.

    Args:
        current: The currently focused index, or None for no focus.
        count: Number of items in the list.
        delta: Steps to move (typically +1 or -1).

    Returns:
        The new index, or None when ``count`` is zero.

    """
    if count <= 0:
        return None
    if current is None:
        return 0 if delta > 0 else count - 1
    return step_index(current, count, delta)


def step_index(current: int, count: int, delta: int) -> int:
    """Return the next index stepping through ``count`` items, clamped at both ends."""
    return max(0, min(count - 1, current + delta))


_REF_SPAN_RE = re.compile(r"\[ref=([^\]]*)\].*?\[/ref\]", re.DOTALL)


def enumerate_refs(markup: str) -> list[str]:
    """Return the ``[ref=...]`` values in a Kivy-markup string, in document order."""
    return [m.group(1) for m in _REF_SPAN_RE.finditer(markup)]


def highlight_ref_occurrence(
    markup: str, occurrence: int, link_color: str, focus_color: str
) -> str:
    """Return markup with one ref span's link color swapped to the focus color.

    Only a color swap — the span's text and other tags are untouched, so the
    label cannot reflow when the highlighted markup replaces the original.

    Args:
        markup: A Kivy-markup string as produced by the core renderer.
        occurrence: Zero-based index of the ref span to highlight.
        link_color: The hex color the renderer gave links (no leading '#').
        focus_color: The hex color marking the focused link.

    Returns:
        The rewritten markup; unchanged when ``occurrence`` matches no span.

    """
    for i, match in enumerate(_REF_SPAN_RE.finditer(markup)):
        if i == occurrence:
            span = match.group(0).replace(f"[color={link_color}]", f"[color={focus_color}]", 1)
            return markup[: match.start()] + span + markup[match.end() :]
    return markup
