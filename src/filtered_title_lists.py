from typing import Tuple, List, Dict, Union

from barks_fantagraphics.barks_tags import TagCategories, BARKS_TAG_CATEGORIES_TITLES
from barks_fantagraphics.fanta_comics_info import (
    get_filtered_title_lists,
    FantaComicBookInfo,
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_USA,
    SERIES_USS,
)


class FilteredTitleLists:
    def __init__(self):
        self.chrono_year_ranges = [
            (1942, 1946),
            (1947, 1950),
            (1951, 1954),
            (1955, 1957),
            (1958, 1961),
        ]
        self.cs_year_ranges = [
            (1942, 1946),
            (1947, 1950),
            (1951, 1954),
            (1955, 1957),
            (1958, 1961),
        ]
        self.us_year_ranges = [
            (1951, 1954),
            (1955, 1957),
            (1958, 1961),
        ]
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
    def get_range_str(year_range: Tuple[int, int]) -> str:
        return f"{year_range[0]}-{year_range[1]}"

    def get_cs_range_str(self, year_range: Tuple[int, int]) -> str:
        return self.get_cs_range_str_from_str(self.get_range_str(year_range))

    @staticmethod
    def get_cs_range_str_from_str(year_range_str: str) -> str:
        return f"CS-{year_range_str}"

    def get_us_range_str(self, year_range: Tuple[int, int]) -> str:
        return self.get_us_range_str_from_str(self.get_range_str(year_range))

    @staticmethod
    def get_us_range_str_from_str(year_range_str: str) -> str:
        return f"US-{year_range_str}"

    def get_year_range_from_info(
        self, fanta_info: FantaComicBookInfo
    ) -> Union[None, Tuple[int, int]]:
        sub_year = fanta_info.comic_book_info.submitted_year

        for year_range in self.chrono_year_ranges:
            if year_range[0] <= sub_year <= year_range[1]:
                return year_range

        return None

    def get_title_lists(self) -> Dict[str, List[FantaComicBookInfo]]:

        def create_range_lamba(yr_range: Tuple[int, int]):
            return lambda info: yr_range[0] <= info.comic_book_info.submitted_year <= yr_range[1]

        def create_series_lamba(series_name: str):
            return lambda info: info.series_name == series_name

        def create_cs_range_lamba(yr_range: Tuple[int, int]):
            return (
                lambda info: info.series_name == SERIES_CS
                and yr_range[0] <= info.comic_book_info.submitted_year <= yr_range[1]
            )

        def create_us_range_lamba(yr_range: Tuple[int, int]):
            return (
                lambda info: info.series_name == SERIES_USA
                and yr_range[0] <= info.comic_book_info.submitted_year <= yr_range[1]
            )

        def create_category_lamba(cat: TagCategories):
            return lambda info: info.comic_book_info.title in BARKS_TAG_CATEGORIES_TITLES[cat]

        filters = {}
        for year_range in self.chrono_year_ranges:
            filters[self.get_range_str(year_range)] = create_range_lamba(year_range)
        for name in self.series_names:
            filters[name] = create_series_lamba(name)
        for year_range in self.cs_year_ranges:
            filters[self.get_cs_range_str(year_range)] = create_cs_range_lamba(year_range)
        for year_range in self.us_year_ranges:
            filters[self.get_us_range_str(year_range)] = create_us_range_lamba(year_range)
        for category in self.categories:
            filters[category.value] = create_category_lamba(category)

        return get_filtered_title_lists(filters)
