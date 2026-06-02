"""Tests for the one-pager integration (ONE_PAGER_LOCATIONS and the collection)."""

import pytest
from barks_fantagraphics import comic_book_info as cbi
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    ONE_PAGER_LOCATIONS,
    ONE_PAGERS,
    get_located_one_pagers,
    get_one_pager_collection_page_num,
    get_one_pager_collection_pages,
    get_one_pager_display_title,
    get_one_pager_issue_page,
    is_one_pager_collection,
    is_one_pager_located,
)
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    SERIES_EXTRAS,
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
            volume, page, _issue_page = ONE_PAGER_LOCATIONS[title]
            assert volume > 0
            assert page > 0
        # Located list is a subset of ONE_PAGERS, in chronological (ONE_PAGERS) order.
        assert located == [t for t in ONE_PAGERS if t in located]

    def test_todo_sentinel_is_not_located(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A `_TODO` (0, 0, 0) entry counts as unlocated and is skipped."""
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (0, 0, 0)})
        assert not is_one_pager_located(Titles.IF_THE_HAT_FITS)
        assert get_located_one_pagers() == []

    def test_issue_page_returned_only_when_recorded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        issue_page = 7
        monkeypatch.setattr(
            cbi,
            "ONE_PAGER_LOCATIONS",
            {
                Titles.IF_THE_HAT_FITS: (5, 123, issue_page),
                Titles.FASHION_IN_FLIGHT: (5, 26, 0),
            },
        )
        assert get_one_pager_issue_page(Titles.IF_THE_HAT_FITS) == issue_page
        # 0 means "not recorded yet".
        assert get_one_pager_issue_page(Titles.FASHION_IN_FLIGHT) is None
        # Absent from the table.
        assert get_one_pager_issue_page(Titles.BIRD_WATCHING) is None

    def test_display_title_includes_issue_page(self, monkeypatch: pytest.MonkeyPatch) -> None:
        issue_page = 2
        monkeypatch.setattr(
            cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (5, 123, issue_page)}
        )
        issue = BARKS_TITLE_INFO[Titles.IF_THE_HAT_FITS].get_title_from_issue_name()
        assert get_one_pager_display_title(Titles.IF_THE_HAT_FITS) == f"{issue}, p. {issue_page}"

    def test_display_title_falls_back_to_issue_when_page_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (5, 123, 0)})
        issue = BARKS_TITLE_INFO[Titles.IF_THE_HAT_FITS].get_title_from_issue_name()
        assert get_one_pager_display_title(Titles.IF_THE_HAT_FITS) == issue


class TestOnePagerCollection:
    def test_collection_is_in_extras_series(self) -> None:
        # The collection itself is an "Extra" in FANTA_01 (alongside the introductions
        # and appreciations); its constituent one-pagers stay in the "One Pagers" series.
        info = get_fanta_info(Titles.ALL_ONE_PAGERS)
        assert info is not None
        assert info.series_name == SERIES_EXTRAS
        assert info.fantagraphics_volume == "FANTA_01"

    def test_located_one_pagers_are_in_one_pagers_series(self) -> None:
        located = get_located_one_pagers()
        assert located, "No located one-pagers to check."
        for title in located:
            info = get_fanta_info(title)
            assert info is not None, f"No fanta info for located one-pager: {title}."
            assert info.series_name == SERIES_ONE_PAGERS

    def test_is_one_pager_collection(self) -> None:
        assert is_one_pager_collection(Titles.ALL_ONE_PAGERS)
        assert not is_one_pager_collection(Titles.IF_THE_HAT_FITS)

    def test_collection_pages_are_sequential_base_pages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Collection pages are sequential FANTA_01 'extra' pages from the base number."""
        fake = {Titles.IF_THE_HAT_FITS: (10, 123, 0), Titles.FASHION_IN_FLIGHT: (11, 45, 0)}
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", fake)

        base = cbi.ONE_PAGER_COLLECTION_PAGE_BASE
        pages = get_one_pager_collection_pages()
        assert [(p.page_filenames, p.page_type) for p in pages] == [
            (f"{base:03d}", PageType.BODY),
            (f"{base + 1:03d}", PageType.BODY),
        ]
        # Deep-link page numbers are the 1-based display position within the collection.
        assert [
            get_one_pager_collection_page_num(Titles.IF_THE_HAT_FITS),
            get_one_pager_collection_page_num(Titles.FASHION_IN_FLIGHT),
        ] == [1, 2]

    def test_unlocated_one_pager_has_no_collection_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {Titles.IF_THE_HAT_FITS: (10, 123, 0)})
        assert get_one_pager_collection_page_num(Titles.FASHION_IN_FLIGHT) is None

    def test_collection_present_in_all_fanta_info(self) -> None:
        """The collection is registered in ALL_FANTA_COMIC_BOOK_INFO at import time."""
        assert Titles.ALL_ONE_PAGERS in ALL_FANTA_COMIC_BOOK_INFO


class TestOnePagerCollectionBuild:
    def test_collection_allows_added_body_pages(self) -> None:
        """The collection's BODY pages may be ADDED fixes (staged FANTA_01 extras).

        This lets upscayl/restore build one-pagers not already part of another comic;
        a normal title rejects an ADDED BODY page.
        """
        comic = ComicsDatabase(for_building_comics=False).get_comic_book("All One-Pagers")
        assert comic._is_added_fixes_special_case("500", PageType.BODY) is True  # noqa: SLF001

    def test_regular_comic_disallows_added_body_pages(self) -> None:
        comic = ComicsDatabase(for_building_comics=False).get_comic_book("Sheriff of Bullet Valley")
        assert comic._is_added_fixes_special_case("999", PageType.BODY) is False  # noqa: SLF001
