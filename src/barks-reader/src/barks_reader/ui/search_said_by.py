"""The word search's speaker filter: one chip, and the list of who says it.

`SaidByFilter` is a part of the search screen with its own state: the speaker the
word results are narrowed to, the chip that names them, and the list the chip opens,
each speaker with the stories they say the search in. The screen owns one, hands it
the screen's `SearchFocus`, and tells it how to read what is searched and how to find
its stories; the filter tells the screen when a speaker is picked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from barks_kivy_ui.scrolling import ReaderDropDown
from kivy.metrics import dp
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.search_chip_row import ChipRow
from barks_reader.core.search_focus import FocusArea
from barks_reader.core.search_state import (
    ALL_SPEAKERS,
    offered_speakers,
    speaker_story_counts,
    stories_said_by,
)

from .reader_keyboard_nav import DropdownNavMixin, open_dropdown
from .search_widgets import _SAID_BY, _make_said_by_chip, _SaidByItem, _speaker_label

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from barks_fantagraphics.search_filters import SearchFilter
    from barks_fantagraphics.whoosh_search_engine import TitleInfo
    from kivy.uix.button import Button
    from kivy.uix.widget import Widget

    from barks_reader.core.search_focus import SearchFocus

    # What is searched: the typed query, the picked word (one of them empty, or both
    # while nothing is searched), and the era and scope the stories are listed under.
    Searched = tuple[str, str, SearchFilter | None]

SAID_BY_LIST_WIDTH = dp(220)


class SaidByFilter(DropdownNavMixin):
    """The speaker the word results are narrowed to, its chip and its list.

    Attributes:
        speaker: The speaker picked; `ALL_SPEAKERS` for anyone.
        row: The chip's row, in the results panel. Empty while no chip shows.
        dropdown: The list the chip opens.

    """

    _dropdown_wraps: bool = False  # a list: it stops at its ends

    def __init__(
        self,
        layout: Widget,
        focus: SearchFocus,
        *,
        indexed_speakers: Callable[[], Collection[str]],
        searched: Callable[[], Searched],
        find_stories: Callable[[str | None], dict[str, TitleInfo]],
        on_picked: Callable[[], None],
    ) -> None:
        """Make the filter over its chip's layout, on anyone.

        Args:
            layout: Where the chip goes.
            focus: Where the keyboard is on the screen; the filter moves it between
                its chip and its list.
            indexed_speakers: Reads the index's speakers; called once, when first needed.
            searched: Returns what is searched now.
            find_stories: Returns the stories a speaker (None for anyone) says it in.
            on_picked: Called once a speaker is picked from the list, to list again.

        """
        self._focus = focus
        self._indexed_speakers = indexed_speakers
        self._searched = searched
        self._find_stories = find_stories
        self._on_picked = on_picked
        self.speaker: str = ALL_SPEAKERS
        self.row = ChipRow(layout, _make_said_by_chip, self._on_chip_pressed)
        # The speakers the filter offers (the index's roster ones); None until read.
        self._offered: list[str] | None = None
        # The list's counts, with the search they were counted for: reopening the list
        # (to change the speaker picked) does not search again. None until counted.
        self._counted: tuple[Searched, dict[str | None, int]] | None = None
        self.dropdown = ReaderDropDown(auto_width=False, width=SAID_BY_LIST_WIDTH)
        self.dropdown.bind(on_select=self._on_item_selected, on_dismiss=self._on_dropdown_dismissed)
        self._setup_dropdown_nav()

    def offered(self) -> list[str]:
        """Return the speakers the filter offers: the index's roster ones, in its order.

        Read once, from the index's speaker sidecar. An index without one (built
        before speakers existed) offers none, and no chip shows. The roster's named
        characters and the narrator are offered; ``other:`` speakers are a long tail
        and are not.
        """
        if self._offered is None:
            self._offered = offered_speakers(self._indexed_speakers())
            if not self._offered:
                logger.debug(log_markers.SPEAKER_FILTER_NO_SPEAKERS)
        return self._offered

    def show(self) -> None:
        """Show the chip, naming the speaker, while a word search's stories are listed.

        None while nothing is searched, or the index has no speakers. Filled while a
        speaker is picked. The keyboard stays on it as its text changes.
        """
        query, word, _filter = self._searched()
        if not (query or word) or not self.offered():
            self.row.set_options([])
            return
        focused = self.row.focused
        self.row.set_options([(_SAID_BY, f"Said by: {_speaker_label(self.speaker)}")])
        self.row.set_selected(_SAID_BY if self.speaker else "")
        if focused is not None:
            self.row.enter_focus(0)

    def lift(self, searched: str) -> None:
        """Go back to anyone: the picked speaker says none of a new search, which others say."""
        logger.info(log_markers.SPEAKER_FILTER_LIFTED.format(speaker=self.speaker, text=searched))
        self.speaker = ALL_SPEAKERS

    def story_counts(self) -> list[tuple[str, int]]:
        """Return anyone's stories, then each speaker's who says what was searched, most first.

        Each count is the search run again under that speaker: the filter wants
        every bubble a typed query finds to be the speaker's, so counting everyone's
        bubbles could give too many. The picked speaker stays listed at none, so
        the filter can be lifted from the list.
        """
        counts = self._stories_by_speaker()
        return speaker_story_counts(counts.__getitem__, self.offered(), self.speaker)

    def _stories_by_speaker(self) -> dict[str | None, int]:
        """Return the listed search's count of stories for anyone (None) and each speaker.

        Counted once for each search, era and scope. A picked word's from its one
        search (`stories_said_by`); a typed query run again under each speaker, as
        its parts need not share a bubble. The list ran a search for each speaker
        every time it opened, on the UI thread.
        """
        searched = self._searched()
        if self._counted is not None and self._counted[0] == searched:
            return self._counted[1]
        offered = self.offered()
        anyone = self._find_stories(None)
        if searched[0]:  # a typed query
            each = {speaker: len(self._find_stories(speaker)) for speaker in offered}
        else:
            each = stories_said_by(anyone, offered)
        counts: dict[str | None, int] = {None: len(anyone), **each}
        self._counted = (searched, counts)
        return counts

    def _on_chip_pressed(self, _value: str) -> None:
        """Open the list of who says what was searched, each with their stories."""
        self.row.set_selected(_SAID_BY if self.speaker else "")  # opening picks none
        counts = self.story_counts()
        dropdown = self.dropdown
        dropdown.clear_widgets()
        for i, (speaker, count) in enumerate(counts):
            item = _SaidByItem(
                text=_speaker_label(speaker),
                value=speaker,
                count_text=str(count),
                row_index=i,
                selected=speaker == self.speaker,
            )
            item.bind(on_release=lambda _b, v=speaker: dropdown.select(v))
            dropdown.add_widget(item)
        chip = cast("Widget", self.row.chips[0])
        if not open_dropdown(dropdown, chip):
            return
        logger.info(log_markers.SPEAKER_LIST_OPENED.format(count=len(counts) - 1))
        if self._focus.area == FocusArea.SPEAKERS and self.row.focused is not None:
            self.take_keys_onto_list()  # by the remote: it walks the list

    def _on_item_selected(self, _dropdown: Widget, speaker: str) -> None:
        """Narrow the word results to the speaker picked from the list, or lift the filter."""
        self.speaker = speaker
        logger.info(log_markers.SPEAKER_FILTER_SET.format(speaker=speaker or "All"))
        self._on_picked()
        # Named anew here too, though listing the stories again shows the chip: the
        # filter's chip does not wait on what its screen does with a pick.
        self.show()

    def _after_dropdown_nav_closed(self) -> None:
        """Give the keyboard back to the chip: the list has closed under it."""
        self._focus.area = FocusArea.SPEAKERS
        self.row.enter_focus(0)

    def handle_list_key(self, key: int) -> bool:
        """Keys while the list is open: Up, Down, Enter, Escape; the rest wait."""
        self._handle_dropdown_key(key)
        return True

    def list_open_without_the_keys(self) -> bool:
        """Return whether the list is open on screen and not the keys'."""
        return self.dropdown.parent is not None and not self._dropdown_nav_mode

    def close_list(self) -> None:
        """Close the list, the keys off it at once.

        Kivy closes a list a moment after it is asked to, and says so only then: the
        keys still on the list at that point went to the chip, on a screen that had
        since given them up. Whoever closes the list this way says where they go.
        """
        if self._dropdown_nav_mode:
            self._exit_dropdown_nav()
        self.dropdown.dismiss()

    def take_keys_onto_list(self) -> None:
        """Take the keys onto the open list, the ring on the speaker picked now.

        The picked speaker is listed only while offered: else the ring is on anyone's row.
        """
        self.row.clear_focus()
        self._focus.area = FocusArea.SAID_BY_LIST
        rows = self._get_dropdown_buttons()
        here = next((i for i, row in enumerate(rows) if row.value == self.speaker), 0)
        self._enter_dropdown_nav(here)

    # --- DropdownNavMixin hooks ---

    def _get_dropdown_buttons(self) -> list[Button]:
        """Return the list's rows, top to bottom."""
        return list(reversed(self.dropdown.container.children))

    def _dismiss_dropdown(self) -> None:
        self.dropdown.dismiss()

    def _scroll_to_dropdown_button(self, btn: object) -> None:
        # A window too short for the whole list cuts it short, and it scrolls: the
        # ring must not walk out of sight.
        self.dropdown.scroll_into_view(cast("Widget", btn))

    def _activate_dropdown_item(self) -> None:
        # At once, as Enter presses everything on this screen: the list closes on it.
        self._dropdown_buttons_cache[self._dropdown_focused_idx].trigger_action(duration=0)
