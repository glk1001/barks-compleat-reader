from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import BARKS_TAG_CATEGORIES_TITLES, TagCategories
from barks_fantagraphics.fanta_comics_info import (
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_USA,
    SERIES_USS,
    FantaComicBookInfo,
    get_filtered_title_lists,
)

from barks_reader.core.reader_consts_and_types import (
    CHRONO_YEAR_RANGES,
    CS_YEAR_RANGES,
    US_YEAR_RANGES,
)

if TYPE_CHECKING:
    from collections.abc import Callable

CHRONO_YEARS_KEY_PREFIX = ""
CS_YEARS_KEY_PREFIX = "CS-"
US_YEARS_KEY_PREFIX = "US-"


class FilteredTitleLists:
    def __init__(self) -> None:
        self.chrono_years = range(CHRONO_YEAR_RANGES[0][0], CHRONO_YEAR_RANGES[-1][1] + 1)
        self.cs_years = range(CS_YEAR_RANGES[0][0], CS_YEAR_RANGES[-1][1] + 1)
        self.us_years = range(US_YEAR_RANGES[0][0], US_YEAR_RANGES[-1][1] + 1)
        self.series_names = [
            SERIES_CS,
            SERIES_DDA,
            SERIES_DDS,
            SERIES_GG,
            SERIES_MISC,
            SERIES_USA,
            SERIES_USS,
        ]
        self.categories = list(TagCategories)

    @staticmethod
    def get_range_str(year_range: tuple[int, int]) -> str:
        return f"{year_range[0]}-{year_range[1]}"

    @staticmethod
    def get_cs_year_key_from_year(year: int) -> str:
        return f"{CS_YEARS_KEY_PREFIX}{year}"

    @staticmethod
    def get_cs_year_range_key_from_range(year_range_str: str) -> str:
        return f"{CS_YEARS_KEY_PREFIX}{year_range_str}"

    @staticmethod
    def get_us_year_key_from_year(year: int) -> str:
        return f"{US_YEARS_KEY_PREFIX}{year}"

    @staticmethod
    def get_us_year_range_key_from_range(year_range_str: str) -> str:
        return f"{US_YEARS_KEY_PREFIX}{year_range_str}"

    def get_title_lists(self) -> dict[str, list[FantaComicBookInfo]]:
        filters: dict[str, Callable[[FantaComicBookInfo], bool]] = {}

        for year in self.chrono_years:
            filters[str(year)] = lambda info, y=year: info.comic_book_info.submitted_year == y

        for name in self.series_names:
            filters[name] = lambda info, n=name: info.series_name == n

        for year in self.cs_years:
            filters[self.get_cs_year_key_from_year(year)] = lambda info, y=year: (
                (info.series_name == SERIES_CS) and (info.comic_book_info.submitted_year == y)
            )

        for year in self.us_years:
            filters[self.get_us_year_key_from_year(year)] = lambda info, y=year: (
                (info.series_name == SERIES_USA) and (info.comic_book_info.submitted_year == y)
            )

        for category in self.categories:
            filters[category.value] = lambda info, c=category: (
                info.comic_book_info.title in BARKS_TAG_CATEGORIES_TITLES[c]
            )

        title_lists = get_filtered_title_lists(filters)

        self.add_year_ranges(CHRONO_YEARS_KEY_PREFIX, CHRONO_YEAR_RANGES, title_lists)
        self.add_year_ranges(CS_YEARS_KEY_PREFIX, CS_YEAR_RANGES, title_lists)
        self.add_year_ranges(US_YEARS_KEY_PREFIX, US_YEAR_RANGES, title_lists)

        return title_lists

    def add_year_ranges(
        self,
        key_prefix: str,
        year_ranges: list[tuple[int, int]],
        title_lists: dict[str, list[FantaComicBookInfo]],
    ) -> None:
        for year_range in year_ranges:
            year_range_key = f"{key_prefix}{self.get_range_str(year_range)}"
            title_lists[year_range_key] = []
            for year in range(year_range[0], year_range[1] + 1):
                year_key = f"{key_prefix}{year}"
                title_lists[year_range_key].extend(title_lists[year_key])
