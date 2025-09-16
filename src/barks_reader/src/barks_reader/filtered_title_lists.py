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

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import ComicBookInfo


class FilteredTitleLists:
    def __init__(self) -> None:
        self.chrono_years = range(1942, 1962)
        self.cs_years = range(1942, 1962)
        self.us_years = range(1951, 1962)
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
    def get_cs_year_str(year: int) -> str:
        return f"CS-{year}"

    @staticmethod
    def get_us_year_str(year: int) -> str:
        return f"US-{year}"

    def get_title_lists(self) -> dict[str, list[FantaComicBookInfo]]:
        def create_year_lamba(yr: int) -> Callable[[ComicBookInfo], bool]:
            return lambda info: info.comic_book_info.submitted_year == yr

        def create_series_lamba(series_name: str) -> Callable[[ComicBookInfo], bool]:
            return lambda info: info.series_name == series_name

        def create_cs_year_lamba(yr: int) -> Callable[[ComicBookInfo], bool]:
            return lambda info: (info.series_name == SERIES_CS) and (
                info.comic_book_info.submitted_year == yr
            )

        def create_us_year_lamba(yr: int) -> Callable[[ComicBookInfo], bool]:
            return lambda info: (info.series_name == SERIES_USA) and (
                info.comic_book_info.submitted_year == yr
            )

        def create_category_lamba(cat: TagCategories) -> Callable[[ComicBookInfo], bool]:
            return lambda info: info.comic_book_info.title in BARKS_TAG_CATEGORIES_TITLES[cat]

        filters = {}
        for year in self.chrono_years:
            filters[str(year)] = create_year_lamba(year)
        for name in self.series_names:
            filters[name] = create_series_lamba(name)
        for year in self.cs_years:
            filters[self.get_cs_year_str(year)] = create_cs_year_lamba(year)
        for year in self.us_years:
            filters[self.get_us_year_str(year)] = create_us_year_lamba(year)
        for category in self.categories:
            filters[category.value] = create_category_lamba(category)

        return get_filtered_title_lists(filters)
