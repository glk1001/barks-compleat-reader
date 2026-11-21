"""The links on the page showing: the one the keyboard is on, and the pointer over them.

The viewer builds a page's labels and tells this which of them hold links; from there
Up and Down walk the links in view and scroll through the stretches with none, Enter
follows the one in focus, and the cursor turns to a hand over any of them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kivy.metrics import dp

from okf_reader.ui import trace

from .keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_HOME,
    KEY_NUMPAD_ENTER,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_UP,
    LINK_FOCUS_COLOR,
    PAGE_LINE_STEP,
    PAGE_STEP_OVERLAP,
    enumerate_refs,
    highlight_ref_occurrence,
    hybrid_link_step,
    scroll_step,
)
from .widgets import ref_under

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from .widgets import PageLabel


class PageLinks:
    """A page's links, their keyboard focus and the hand cursor over them."""

    def __init__(
        self,
        body: Widget,
        body_scroll: ScrollView,
        link_hex: str,
        on_follow: Callable[[PageLabel, str], None],
    ) -> None:
        """Watch the pointer over the links of the page laid out in `body`.

        Args:
            body: The column the page's blocks are laid out in.
            body_scroll: The scroll view that column sits in: the page's viewport.
            link_hex: The color the page's links are rendered in, to recolor one from.
            on_follow: Called with a link's label and its ref when the link is followed.

        """
        self._body = body
        self._body_scroll = body_scroll
        self._link_hex = link_hex
        self._on_follow = on_follow
        # The page's labels that hold links: what the pointer is tested against.
        self.labels: list[PageLabel] = []
        # The page's links in document order: (label, ref, occurrence-in-label).
        self.links: list[tuple[PageLabel, str, int]] = []
        self.focused: int | None = None
        self.popup_label: Label | None = None  # an open footnote popup's label
        self.hand_cursor = False
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        Window.bind(mouse_pos=self.on_mouse_pos)

    def start_page(self) -> None:
        """Forget the last page's links: its labels are gone, so nothing is restored."""
        self.labels.clear()
        self.focused = None

    def page_built(self) -> None:
        """List the new page's links, now every label of it has been added to `labels`."""
        self.links = [
            (lbl, ref, i) for lbl in self.labels for i, ref in enumerate(enumerate_refs(lbl.text))
        ]

    def handle_key(self, key: int) -> bool:
        """Walk the links with Up/Down, scroll with the desktop's keys, follow with Enter."""
        if key in (KEY_UP, KEY_DOWN):
            self.line_step(1 if key == KEY_DOWN else -1)
            return True
        if self._handle_scroll_key(key):
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            return self.follow_focused()
        return False

    def _handle_scroll_key(self, key: int) -> bool:
        """Handle the desktop page-scrolling extras (PageUp/PageDown/Home/End)."""
        if key in (KEY_PAGE_UP, KEY_PAGE_DOWN):
            step = self._body_scroll.height - dp(PAGE_STEP_OVERLAP)
            self.scroll_by(step if key == KEY_PAGE_DOWN else -step)
        elif key == KEY_HOME:
            self._body_scroll.scroll_y = 1.0
        elif key == KEY_END:
            fits = self._body.height <= self._body_scroll.height
            self._body_scroll.scroll_y = 1.0 if fits else 0.0
        else:
            return False
        self.prune_offscreen_focus()
        return True

    def line_step(self, delta: int) -> None:
        """One Up/Down press: focus the next/previous nearby link, else scroll a step."""
        step_px = dp(PAGE_LINE_STEP)
        action, idx = hybrid_link_step(
            self.geometry(),
            self.focused,
            self._body_scroll.height,
            step_px,
            delta,
        )
        if action == "focus":
            assert idx is not None
            self.set_focus(idx)
        else:
            self.scroll_by(step_px * delta)
            self.prune_offscreen_focus()

    def geometry(self) -> list[tuple[float, float]]:
        """Each page link's label (top, bottom) in viewport-relative pixels.

        Viewport-relative: y grows downward from the viewport's top edge, so a
        label spanning the top of the view has top ~0 (see `hybrid_link_step`).
        Occurrences within one label share its geometry.
        """
        viewport_top = self._body_scroll.to_window(self._body_scroll.x, self._body_scroll.top)[1]
        geometry = []
        for lbl, _ref, _occurrence in self.links:
            label_top = viewport_top - lbl.to_window(lbl.x, lbl.top)[1]
            geometry.append((label_top, label_top + lbl.height))
        return geometry

    def prune_offscreen_focus(self) -> None:
        """Drop link focus once its label has scrolled fully out of the viewport.

        This is what lets Up/Down re-acquire the first *visible* link after any
        scrolling — focus can never sit on (and Enter can never follow) a link
        the reader cannot see.
        """
        if self.focused is None:
            return
        lbl, _ref, _occurrence = self.links[self.focused]
        viewport_top = self._body_scroll.to_window(self._body_scroll.x, self._body_scroll.top)[1]
        label_top = viewport_top - lbl.to_window(lbl.x, lbl.top)[1]
        if label_top + lbl.height <= 0 or label_top >= self._body_scroll.height:
            self.clear_focus()

    def scroll_by(self, delta_px: float) -> None:
        self._body_scroll.scroll_y = scroll_step(
            self._body_scroll.scroll_y, self._body_scroll.height, self._body.height, delta_px
        )

    def set_focus(self, idx: int | None) -> None:
        """Move the gold link highlight to ``idx``, scrolling its label into view."""
        self._restore_markup()
        self.focused = idx
        if idx is None:
            return
        lbl, ref, occurrence = self.links[idx]
        lbl.orig_markup = lbl.text
        # The colour the page's links were rendered in: a host may have themed it.
        lbl.text = highlight_ref_occurrence(lbl.text, occurrence, self._link_hex, LINK_FOCUS_COLOR)
        if self._body.height > self._body_scroll.height:
            self._body_scroll.scroll_to(lbl, padding=24)  # scroll_to applies dp() itself
        trace.link_focus(ref)

    def _restore_markup(self) -> None:
        """Put the focused link's label text back to its unhighlighted markup."""
        if self.focused is None:
            return
        lbl, _ref, _occurrence = self.links[self.focused]
        if lbl.orig_markup is not None:
            lbl.text = lbl.orig_markup
            lbl.orig_markup = None

    def clear_focus(self) -> None:
        self._restore_markup()
        self.focused = None

    def follow_focused(self) -> bool:
        """Activate the focused link exactly as a tap would; False with no focus."""
        if self.focused is None:
            return False
        lbl, ref, _occurrence = self.links[self.focused]
        self._on_follow(lbl, ref)
        return True

    def on_mouse_pos(self, _window: Any, pos: tuple[float, float]) -> None:  # noqa: ANN401
        self.set_hand_cursor(self.over_link(pos))

    def over_link(self, pos: tuple[float, float]) -> bool:
        """Return whether the window point ``pos`` is over a page link."""
        if self._body_scroll.get_root_window() is None:  # viewer not on screen (e.g. wiki closed)
            return False
        if self.popup_label is not None:  # a modal popup: only its label counts
            return ref_under(self.popup_label, *pos) is not None
        # Fast reject: outside the page pane's viewport nothing can be a link —
        # this also blocks labels scrolled out of view, whose content-space boxes
        # would otherwise still collide. collide_point wants parent-space coords;
        # the scroll view's own to_widget would apply the scroll transform.
        if not self._body_scroll.collide_point(*self._body_scroll.parent.to_widget(*pos)):
            return False
        return any(ref_under(lbl, *pos) is not None for lbl in self.labels)

    def set_hand_cursor(self, over: bool) -> None:
        """Flip the system cursor between hand and arrow, only on a state change.

        Change-only so this never fights other cursor owners (e.g. the Barks
        Reader's busy cursor) while the mouse just moves about.
        """
        if over == self.hand_cursor:
            return
        self.hand_cursor = over
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        Window.set_system_cursor("hand" if over else "arrow")

    def refresh_cursor(self) -> None:
        """Re-evaluate the cursor against the current mouse position (no move needed)."""
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        self.set_hand_cursor(self.over_link(Window.mouse_pos))
