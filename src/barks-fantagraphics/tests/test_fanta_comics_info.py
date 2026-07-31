from collections import Counter

from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    SERIES_COVERS,
    SERIES_CS,
    SERIES_ONE_PAGERS,
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
