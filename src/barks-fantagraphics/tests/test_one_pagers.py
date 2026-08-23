"""Tests for the one-pager integration (ONE_PAGER_LOCATIONS and the collection)."""

import pytest
from barks_fantagraphics import comic_book_info as cbi
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
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


def _submitted_key(title: Titles) -> tuple[int, int, int]:
    info = BARKS_TITLE_INFO[title]
    return (
        info.submitted_year if info.submitted_year != -1 else 9999,
        info.submitted_month if info.submitted_month != -1 else 99,
        info.submitted_day if info.submitted_day != -1 else 99,
    )


def _inversions(titles: list[Titles]) -> list[tuple[Titles, Titles]]:
    """Adjacent ``(earlier_entry, later_entry)`` pairs whose submitted dates go backwards."""
    return [
        (titles[i - 1], titles[i])
        for i in range(1, len(titles))
        if _submitted_key(titles[i]) < _submitted_key(titles[i - 1])
    ]


def _describe(pair: tuple[Titles, Titles]) -> str:
    prev, title = pair
    return (
        f"{ENUM_TO_STR_TITLE[title]!r} {_submitted_key(title)}"
        f" placed after {ENUM_TO_STR_TITLE[prev]!r} {_submitted_key(prev)}"
    )


# Cap on how many drifted entries a failure message lists before summarising.
_MAX_LISTED_DRIFT = 5

_REORDER_HINT = (
    " Move the entry to its chronological slot in ONE_PAGERS (comic_book_info.py) - the"
    " one-pager subsequence of BARKS_TITLE_INFO is the reference order, and"
    " experiments/one_pagers/reorder_one_pagers.py rewrites the list to it. Then re-run"
    " barks-stage-one-pagers: the collection's pre-baked page numbering follows this list,"
    " so moving an entry leaves the staged scans on the wrong pages."
)


class TestOnePagerOrdering:
    """`ONE_PAGERS` list order is the "All One-Pagers" collection's page order.

    It is a *separate hand-maintained list*, not a slice of `BARKS_TITLE_INFO`, so
    `check_story_submitted_order` cannot see it and the two can drift apart - which they
    did, until the list was reordered to match. These two assertions are what keep them
    together: without them a stray entry surfaces only as an opaque page-number mismatch
    in the reader's collection tests, or not at all when it stays inside a year-range group.
    """

    def test_one_pagers_are_in_submitted_date_order(self) -> None:
        inverted = _inversions(ONE_PAGERS)
        assert not inverted, (
            "ONE_PAGERS is not in submitted-date order: "
            + "; ".join(_describe(pair) for pair in inverted)
            + "."
            + _REORDER_HINT
        )

    def test_one_pagers_match_the_barks_title_info_order(self) -> None:
        # BARKS_TITLE_INFO is chronological and gated by check_story_submitted_order, so it
        # is the reference *order*. It is not a reference for *membership*: ONE_PAGERS is
        # itself the definition of which titles are one-pagers, so the reference is filtered
        # by it and the two sets are equal by construction - a set assertion here would be
        # vacuous, never able to fail. Membership is covered instead by the NUM_ONE_PAGERS
        # count assert in comic_book_info.py and by test_locations_keys_are_one_pagers.
        reference = [info.title for info in BARKS_TITLE_INFO if info.title in set(ONE_PAGERS)]
        drift = [
            f"{ENUM_TO_STR_TITLE[a]!r} at index {i} where {ENUM_TO_STR_TITLE[b]!r} is expected"
            for i, (a, b) in enumerate(zip(ONE_PAGERS, reference, strict=True))
            if a != b
        ]
        assert not drift, (
            "ONE_PAGERS is out of step with BARKS_TITLE_INFO: "
            + "; ".join(drift[:_MAX_LISTED_DRIFT])
            + (
                f" (+{len(drift) - _MAX_LISTED_DRIFT} more)"
                if len(drift) > _MAX_LISTED_DRIFT
                else ""
            )
            + "."
            + _REORDER_HINT
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
