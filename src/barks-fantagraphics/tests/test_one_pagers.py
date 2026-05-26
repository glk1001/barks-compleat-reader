"""Tests for the one-pager integration (ONE_PAGER_LOCATIONS and the collection)."""

import pytest
from barks_fantagraphics import comic_book_info as cbi
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import (
    ONE_PAGER_LOCATIONS,
    ONE_PAGERS,
    get_located_one_pagers,
    get_one_pager_collection_page_num,
    get_one_pager_collection_pages,
    is_one_pager_collection,
    is_one_pager_located,
)
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    SERIES_ONE_PAGERS,
    get_fanta_info,
)


class TestOnePagerLocations:
    def test_locations_keys_are_one_pagers(self) -> None:
        """Every key in the location table must be a known one-pager."""
        assert set(ONE_PAGER_LOCATIONS) <= set(ONE_PAGERS)

    def test_located_means_positive_volume_and_page(self) -> None:
        located = get_located_one_pagers()
        for title in located:
            volume, page = ONE_PAGER_LOCATIONS[title]
            assert volume > 0
            assert page > 0
        # Located list is a subset of ONE_PAGERS, in chronological (ONE_PAGERS) order.
        assert located == [t for t in ONE_PAGERS if t in located]

    def test_todo_sentinel_is_not_located(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A `_TODO` (0, 0) entry counts as unlocated and is skipped."""
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (0, 0)})
        assert not is_one_pager_located(Titles.IF_THE_HAT_FITS)
        assert get_located_one_pagers() == []


class TestOnePagerCollection:
    def test_collection_is_in_one_pagers_series(self) -> None:
        info = get_fanta_info(Titles.ALL_ONE_PAGERS)
        assert info is not None
        assert info.series_name == SERIES_ONE_PAGERS
        assert info.fantagraphics_volume == "FANTA_01"

    def test_is_one_pager_collection(self) -> None:
        assert is_one_pager_collection(Titles.ALL_ONE_PAGERS)
        assert not is_one_pager_collection(Titles.IF_THE_HAT_FITS)

    def test_collection_pages_built_from_locations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The collection's pages are gathered across volumes from the table."""
        fake = {Titles.IF_THE_HAT_FITS: (10, 123), Titles.FASHION_IN_FLIGHT: (11, 45)}
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", fake)

        pages = get_one_pager_collection_pages()
        assert [(p.page_filenames, p.page_type, p.fanta_volume) for p in pages] == [
            ("123", PageType.BODY, 10),
            ("045", PageType.BODY, 11),
        ]
        # Deep-link page numbers are the 1-based position within the collection.
        assert [
            get_one_pager_collection_page_num(Titles.IF_THE_HAT_FITS),
            get_one_pager_collection_page_num(Titles.FASHION_IN_FLIGHT),
        ] == [1, 2]

    def test_unlocated_one_pager_has_no_collection_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (10, 123)})
        assert get_one_pager_collection_page_num(Titles.FASHION_IN_FLIGHT) is None

    def test_collection_present_in_all_fanta_info(self) -> None:
        """The collection is registered in ALL_FANTA_COMIC_BOOK_INFO at import time."""
        assert "All One-Pagers" in ALL_FANTA_COMIC_BOOK_INFO
