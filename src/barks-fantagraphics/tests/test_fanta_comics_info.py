from collections import Counter

from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
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

    def test_all_series_info_titles_in_fanta_info(self) -> None:
        """Tests that every SERIES_INFO entry made it into ALL_FANTA_COMIC_BOOK_INFO."""
        assert len(ALL_FANTA_COMIC_BOOK_INFO) == len(SERIES_INFO)

    def test_chronological_numbers_are_contiguous(self) -> None:
        """Tests that the two chronological sequences are gap-free and start at 1.

        Non one-pager titles and one-pager titles are numbered independently; each
        sequence must be exactly 1..N with no gaps or duplicates.
        """
        main_numbers = sorted(
            info.fanta_chronological_number
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
            if info.series_name != SERIES_ONE_PAGERS
        )
        assert main_numbers == list(range(1, len(main_numbers) + 1))

        one_pager_numbers = sorted(
            info.fanta_chronological_number
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
            if info.series_name == SERIES_ONE_PAGERS
        )
        assert one_pager_numbers == list(range(1, len(one_pager_numbers) + 1))
