from collections import Counter

from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    ALL_LISTS,
    FANTA_OVERRIDE_ZIPS,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    SERIES_COVERS,
    SERIES_CS,
    SERIES_ONE_PAGERS,
    get_filtered_title_lists,
    get_num_comic_book_titles,
)
from barks_fantagraphics.fanta_series_data import SERIES_INFO


class TestSeriesInfo:
    def test_no_duplicate_titles(self) -> None:
        """Tests that no title appears more than once in SERIES_INFO.

        A duplicate silently consumes a chronological number and a number-in-series
        (the duplicate overwrites the first entry in ALL_FANTA_COMIC_BOOK_INFO),
        shifting the numbering of every later title.
        """
        title_counts = Counter(series_info.title for series_info in SERIES_INFO)
        duplicates = [title.name for title, count in title_counts.items() if count > 1]
        assert not duplicates, f"Duplicate titles in SERIES_INFO: {duplicates}"

    def test_comics_and_stories_series_is_all_wdcs(self) -> None:
        """Tests that every Comics and Stories title ran in a numbered WDCS issue.

        The series label in the reader's tree reads 'WDCS <first>-<last>', built from
        the issue numbers of the titles in each year range. Unlike the Uncle Scrooge
        series, which also holds Dell Giants that carry their own issue #1, this series
        admits no other issue -- a title from one would make the label a lie.
        """
        strays = [
            (info.comic_book_info.get_title_str(), info.comic_book_info.issue_name.name)
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
            if info.series_name == SERIES_CS and info.comic_book_info.issue_name is not Issues.CS
        ]
        assert not strays, (
            f"Non-WDCS titles in the {SERIES_CS} series: {strays}. Either the series is"
            f" wrong in SERIES_INFO, or _get_cs_year_range_extra_text in the reader's"
            f" tree_spec needs to learn how to label this issue."
        )

    def test_all_series_info_titles_in_fanta_info(self) -> None:
        """Tests that every SERIES_INFO entry made it into ALL_FANTA_COMIC_BOOK_INFO."""
        assert len(ALL_FANTA_COMIC_BOOK_INFO) == len(SERIES_INFO)

    def test_chronological_numbers_are_contiguous(self) -> None:
        """Tests that the three chronological sequences are gap-free and start at 1.

        Regular titles, one-pagers, and covers are numbered independently; each
        sequence must be exactly 1..N with no gaps or duplicates.
        """
        own_sequence_series = (SERIES_ONE_PAGERS, SERIES_COVERS)
        main_numbers = sorted(
            info.fanta_chronological_number
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
            if info.series_name not in own_sequence_series
        )
        assert main_numbers == list(range(1, len(main_numbers) + 1))

        for series_name in own_sequence_series:
            series_numbers = sorted(
                info.fanta_chronological_number
                for info in ALL_FANTA_COMIC_BOOK_INFO.values()
                if info.series_name == series_name
            )
            assert series_numbers == list(range(1, len(series_numbers) + 1))


class TestOverrideZipNames:
    """The overrides script writes each volume's archive under its name here."""

    def test_every_volume_has_one(self) -> None:
        assert sorted(FANTA_OVERRIDE_ZIPS) == list(
            range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        )

    def test_each_is_a_cbz_named_for_its_volume(self) -> None:
        """Volume 18's once lacked ".cbz", and data-v8 shipped it that way."""
        misnamed = {
            volume: name
            for volume, name in FANTA_OVERRIDE_ZIPS.items()
            if not (name.startswith(f"{volume:02d} - ") and name.endswith(".cbz"))
        }
        assert misnamed == {}


class TestFilteredTitleLists:
    def test_every_title_is_in_the_all_list_and_in_each_list_whose_filter_takes_it(self) -> None:
        lists = get_filtered_title_lists(
            {
                "covers": lambda info: info.series_name == SERIES_COVERS,
                "none": lambda _info: False,
            }
        )
        assert lists[ALL_LISTS] == list(ALL_FANTA_COMIC_BOOK_INFO.values())
        assert lists["covers"]
        assert all(info.series_name == SERIES_COVERS for info in lists["covers"])
        assert len(lists["covers"]) == sum(
            info.series_name == SERIES_COVERS for info in ALL_FANTA_COMIC_BOOK_INFO.values()
        )
        assert "none" not in lists


class TestNumComicBookTitles:
    @staticmethod
    def _count(series: set[str], first: int, last: int) -> int:
        return sum(
            first <= info.comic_book_info.submitted_year <= last and info.series_name in series
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
        )

    def test_covers_are_never_counted_and_one_pagers_only_when_asked(self) -> None:
        years = (1942, 1966)
        all_series = {info.series_name for info in ALL_FANTA_COMIC_BOOK_INFO.values()}
        stories = all_series - {SERIES_COVERS, SERIES_ONE_PAGERS}
        one_pagers = self._count({SERIES_ONE_PAGERS}, *years)
        assert one_pagers
        assert self._count({SERIES_COVERS}, *years)

        assert get_num_comic_book_titles(years) == self._count(stories, *years)
        assert get_num_comic_book_titles(years, include_one_pagers=True) == (
            self._count(stories, *years) + one_pagers
        )

    def test_both_ends_of_the_year_range_are_included(self) -> None:
        both = get_num_comic_book_titles((1950, 1951), include_one_pagers=True)
        first = get_num_comic_book_titles((1950, 1950), include_one_pagers=True)
        second = get_num_comic_book_titles((1951, 1951), include_one_pagers=True)
        assert first
        assert second
        assert both == first + second
