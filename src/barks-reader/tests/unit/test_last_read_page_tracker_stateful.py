"""The last-read-page tracker under any sequence of comics opened and closed: a state machine.

The second stateful pilot of docs/BACKLOG.md, after the reading history's. Hypothesis
draws a sequence of the rules below (a comic opened on a drawn layout with saving on
or off, the reader closed on a drawn page in single- or double-page mode, or with no
valid page) and checks after each step that the page the tracker saved is one of the
layout's pages and in the unit shown ("current page always in bounds"), that the page
it returns and the page it offers on the next open are that page normalised to the
comic's beginning when it is not inside the body, and that the settings file on disk
reads back as the model.

Run from a module-level function, not the class-scoped ``TestCase`` Hypothesis
generates: mutmut runs pytest many times in one process (docs/mutation-testing.md).
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.comic_book_page_info import ComicLayout, PageInfo
from barks_reader.core.json_settings_manager import SettingsManager
from barks_reader.core.last_read_page_tracker import LastReadPageTracker
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE, FIRST_BODY_PAGE
from barks_reader.core.saved_page_info import SavedPageInfo
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)
from strategies import page_maps

if TYPE_CHECKING:
    from collections import OrderedDict

_TITLES = ["Lost in the Andes!", "Vacation Time", "Trick or Treat"]


def _inside_body(page: PageInfo | SavedPageInfo, last_body_page: str) -> bool:
    """Say whether a page is inside the body: a body page, neither the first nor the last.

    The model's own rule, not `SavedPageInfo.is_inside_body`: an oracle shared with the
    code under test would change with it and let its bugs through.
    """
    return page.page_type == PageType.BODY and page.display_page_num not in (
        FIRST_BODY_PAGE,
        last_body_page,
    )


def _normalised(saved: SavedPageInfo) -> SavedPageInfo:
    """Return the page as the tracker hands it out: a finished comic goes back to the beginning."""
    if _inside_body(saved, saved.last_body_page):
        return replace(saved)
    return replace(saved, display_page_num=COMIC_BEGIN_PAGE)


class LastReadPageMachine(RuleBasedStateMachine):
    """A tracker over the real settings file, beside a model of the pages it should have saved."""

    def __init__(self) -> None:
        super().__init__()
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "settings.json"
        self.tracker = LastReadPageTracker(SettingsManager(self.path))
        # The model: the page saved for each title, as it is on disk (not normalised);
        # and the comic opened last, with its layout and whether its progress is saved.
        self.saved: dict[str, SavedPageInfo] = {}
        self.session: tuple[str, ComicLayout, bool] | None = None

    def teardown(self) -> None:
        self._dir.cleanup()

    # --- rules ---

    @rule(
        title=st.sampled_from(_TITLES), page_map=page_maps(max_pages=12), save_enabled=st.booleans()
    )
    def begin(self, title: str, page_map: OrderedDict[str, PageInfo], save_enabled: bool) -> None:
        layout = ComicLayout(page_map, last_body_page=next(reversed(page_map)))
        self.tracker.begin(title, layout, save_enabled=save_enabled)
        self.session = (title, layout, save_enabled)

    @precondition(lambda self: self.session is None)
    @rule()
    def end_before_any_begin(self) -> None:
        reader = MagicMock()
        reader.get_last_read_page.return_value = FIRST_BODY_PAGE
        assert self.tracker.end(reader) is None

    @precondition(lambda self: self.session is not None)
    @rule(data=st.data(), double_page_mode=st.booleans(), no_page=st.booleans())
    def end(self, data: st.DataObject, double_page_mode: bool, no_page: bool) -> None:
        assert self.session is not None
        title, layout, save_enabled = self.session
        page_map = layout.page_map
        current = "" if no_page else data.draw(st.sampled_from(list(page_map)))
        page = page_map.get(current)
        unit = None
        if page is not None:
            unit_idx = layout.unit_idx_for(page.page_index)
            assert unit_idx is not None
            unit = data.draw(st.none() | st.just(layout.display_units[unit_idx]))

        reader = MagicMock()
        reader.double_page_mode = double_page_mode
        reader.get_last_read_page.return_value = current
        reader.get_current_display_unit.return_value = unit

        result = self.tracker.end(reader)

        if not save_enabled or page is None:
            assert result is None
            return
        assert result is not None

        # In bounds: one of the layout's pages, and in double-page mode one of the pair shown.
        shown = page_map[str(result.page_index + 1)]
        assert shown.page_index == result.page_index
        assert result.page_type == shown.page_type
        assert result.last_body_page == layout.last_body_page
        if double_page_mode and unit is not None:
            assert result.page_index in (unit.left_page_index, unit.right_page_index)
        else:
            assert result.page_index == page.page_index

        # The page saved: the right page of a full pair, unless the left is an edge page.
        chosen = page
        if double_page_mode and unit is not None and unit.right_page_index is not None:
            left = page_map[str(unit.left_page_index + 1)]
            right = page_map[str(unit.right_page_index + 1)]
            chosen = left if not _inside_body(left, layout.last_body_page) else right
        expected = SavedPageInfo(
            chosen.page_index, chosen.display_page_num, chosen.page_type, layout.last_body_page
        )
        assert result == _normalised(expected)
        self.saved[title] = expected

    # --- invariants ---

    @invariant()
    def the_page_offered_on_the_next_open_is_the_page_saved_normalised(self) -> None:
        for title in _TITLES:
            offered = self.tracker.get_last_read_page(title)
            if title not in self.saved:
                assert offered is None
            else:
                assert offered == _normalised(self.saved[title])
                assert offered.display_page_num == COMIC_BEGIN_PAGE or _inside_body(
                    offered, offered.last_body_page
                )

    @invariant()
    def the_settings_file_reads_back_as_the_page_saved_not_normalised(self) -> None:
        on_disk = SettingsManager(self.path)
        for title in _TITLES:
            assert on_disk.get_last_read_page(title) == self.saved.get(title)

    @invariant()
    def the_tracker_hands_out_copies_so_a_caller_cannot_change_the_file(self) -> None:
        for title in self.saved:
            offered = self.tracker.get_last_read_page(title)
            assert offered is not None
            offered.display_page_num = "changed"
            assert self.tracker.get_last_read_page(title) == _normalised(self.saved[title])


def test_the_tracker_saves_a_page_in_bounds_and_offers_it_back_under_any_reads() -> None:
    run_state_machine_as_test(
        LastReadPageMachine, settings=settings(stateful_step_count=30, deadline=None)
    )
