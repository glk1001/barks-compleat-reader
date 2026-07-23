"""Tests for the synthetic "All Covers" collection (Titles.ALL_COVERS)."""

import pytest
from barks_fantagraphics import barks_covers as bc
from barks_fantagraphics.barks_covers import (
    BARKS_COVERS,
    COVER_BY_TITLE,
    BarksCover,
    CoverKind,
    get_cover_collection_page_num,
    get_cover_collection_pages,
    get_cover_display_title,
    get_cover_title,
    get_cover_title_str,
    get_located_covers,
)
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    COVERS,
    COVERS_SET,
    SYNTHETIC_TITLES,
    is_covers_collection,
)
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    SERIES_COVERS,
    SERIES_EXTRAS,
    get_fanta_info,
)


def _make_cover(**overrides: object) -> BarksCover:
    fields = {
        "issue_name": Issues.US,
        "series_name": "UNCLE SCROOGE",
        "issue_number": 7,
        "issue_month": 9,
        "issue_year": 1954,
        "kind": CoverKind.FRONT,
        "seq": 0,
        "qualifier": None,
        "description": "",
        "submitted_day": -1,
        "submitted_month": -1,
        "submitted_year": -1,
        "illustrates": None,
    }
    fields.update(overrides)
    return BarksCover(**fields)


class TestCoverTitles:
    def test_every_cover_has_a_unique_title(self) -> None:
        titles = [get_cover_title(cover) for cover in BARKS_COVERS]
        assert len(set(titles)) == len(BARKS_COVERS)
        assert set(titles) == COVERS_SET

    def test_cover_title_round_trips(self) -> None:
        for cover in BARKS_COVERS:
            title = get_cover_title(cover)
            assert ENUM_TO_STR_TITLE[title] == get_cover_title_str(cover)
            assert COVER_BY_TITLE[title] is cover

    def test_cover_titles_are_assigned_titles(self) -> None:
        """Cover titles are assigned (not Barks's own), so they display parenthesised."""
        by_title = {info.title: info for info in BARKS_TITLE_INFO}
        for title in COVERS:
            assert by_title[title].is_barks_title is False

    def test_every_cover_has_a_placeholder_payment(self) -> None:
        for title in COVERS:
            payment = BARKS_PAYMENTS[title]
            assert payment.num_pages == 1
            assert payment.payment == -1.0

    def test_collection_page_num(self) -> None:
        located = get_located_covers()
        assert get_cover_collection_page_num(get_cover_title(located[0])) == 1
        assert get_cover_collection_page_num(get_cover_title(located[-1])) == len(located)
        # An unlocated cover has no collection page.
        unlocated = next(c for c in BARKS_COVERS if c not in located)
        assert get_cover_collection_page_num(get_cover_title(unlocated)) is None


class TestCoversCollection:
    def test_collection_is_in_extras_series(self) -> None:
        # The collection itself is an "Extra" in FANTA_02 (like "All One-Pagers" in
        # FANTA_01); its constituent covers are in the "Covers" series.
        info = get_fanta_info(Titles.ALL_COVERS)
        assert info is not None
        assert info.series_name == SERIES_EXTRAS
        assert info.fantagraphics_volume == "FANTA_02"

    def test_located_covers_are_in_covers_series(self) -> None:
        located = get_located_covers()
        assert located, "No located covers to check."
        for cover in located:
            info = get_fanta_info(get_cover_title(cover))
            assert info is not None, f"No fanta info for located cover: {cover.key}."
            assert info.series_name == SERIES_COVERS

    def test_unlocated_covers_are_not_in_series(self) -> None:
        located = set(get_located_covers())
        for cover in BARKS_COVERS:
            if cover not in located:
                assert get_fanta_info(get_cover_title(cover)) is None

    def test_is_covers_collection(self) -> None:
        assert is_covers_collection(Titles.ALL_COVERS)
        assert not is_covers_collection(Titles.ALL_ONE_PAGERS)

    def test_collection_is_synthetic(self) -> None:
        assert Titles.ALL_COVERS in SYNTHETIC_TITLES

    def test_collection_present_in_all_fanta_info(self) -> None:
        """The collection is registered in ALL_FANTA_COMIC_BOOK_INFO at import time."""
        assert Titles.ALL_COVERS in ALL_FANTA_COMIC_BOOK_INFO

    def test_collection_pages_are_sequential_base_pages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Collection pages are sequential FANTA_02 'extra' pages from the base number."""
        fake = {BARKS_COVERS[0].key: (6, 209), BARKS_COVERS[1].key: (6, 219)}
        monkeypatch.setattr(bc, "COVER_LOCATIONS", fake)

        base = bc.COVER_COLLECTION_PAGE_BASE
        pages = get_cover_collection_pages()
        # Covers are full-page images, so they use COVER (never cropped to panels).
        assert [(p.page_filenames, p.page_type) for p in pages] == [
            (f"{base:03d}", PageType.COVER),
            (f"{base + 1:03d}", PageType.COVER),
        ]

    def test_collection_pages_cover_all_located_covers(self) -> None:
        assert len(get_cover_collection_pages()) == len(get_located_covers())

    def test_comics_database_builds_collection_with_derived_pages(self) -> None:
        """The ini's empty [pages] section is overridden by COVER_LOCATIONS."""
        comic = ComicsDatabase(for_building_comics=False).get_comic_book("All Covers")
        assert comic.config_page_images == get_cover_collection_pages()

    def test_collection_allows_added_cover_pages(self) -> None:
        """The collection's COVER pages may be ADDED fixes (staged FANTA_02 extras)."""
        comic = ComicsDatabase(for_building_comics=False).get_comic_book("All Covers")
        assert comic._is_added_fixes_special_case("500", PageType.COVER) is True  # noqa: SLF001


class TestCoverDisplayTitle:
    def test_issue_backed_cover(self) -> None:
        cover = _make_cover()
        assert get_cover_display_title(cover) == "Uncle Scrooge #7 (Sep 1954)"

    def test_series_with_no_issues_member_uses_series_name(self) -> None:
        cover = _make_cover(
            issue_name=None,
            series_name="DAISY AND DONALD",
            issue_number=25,
            issue_month=8,
            issue_year=1977,
        )
        assert get_cover_display_title(cover) == "Daisy And Donald #25 (Aug 1977)"

    def test_unnumbered_issue_omits_number(self) -> None:
        cover = _make_cover(issue_number=-1)
        assert get_cover_display_title(cover) == "Uncle Scrooge (Sep 1954)"

    def test_unknown_month_uses_year_only(self) -> None:
        cover = _make_cover(issue_month=-1)
        assert get_cover_display_title(cover) == "Uncle Scrooge #7 (1954)"

    def test_non_front_cover_appends_kind(self) -> None:
        cover = _make_cover(issue_number=16, issue_month=12, issue_year=1957, kind=CoverKind.BACK)
        assert get_cover_display_title(cover) == "Uncle Scrooge #16 (Dec 1957), back"
