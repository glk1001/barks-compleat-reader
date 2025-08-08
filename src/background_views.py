# ruff: noqa: ERA001

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS_TITLES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import BARKS_TITLES, VACATION_TIME, Titles
from barks_fantagraphics.comics_utils import get_abbrev_path
from barks_fantagraphics.fanta_comics_info import (
    ALL_LISTS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_USA,
    SERIES_USS,
    FantaComicBookInfo,
    FantaComicBookInfoDict,
)
from kivy.clock import Clock

from src.filtered_title_lists import FilteredTitleLists
from src.random_title_images import FIT_MODE_COVER, FileTypes, ImageInfo, RandomTitleImages
from src.reader_colors import RandomColorTint
from src.reader_formatter import get_formatted_color

if TYPE_CHECKING:
    from pathlib import Path

    from src.reader_colors import Color
    from src.reader_settings import ReaderSettings

TOP_VIEW_IMAGE_TYPES = {
    t for t in FileTypes if t not in [FileTypes.NONTITLE, FileTypes.ORIGINAL_ART]
}

DEBUG_FUN_IMAGE_TITLES = None
# DEBUG_FUN_IMAGE_TITLES = [Titles.LOST_IN_THE_ANDES]


class ViewStates(Enum):
    PRE_INIT = auto()
    INITIAL = auto()
    ON_INTRO_NODE = auto()
    ON_INTRO_COMPLEAT_BARKS_READER_NODE = auto()
    ON_INTRO_DON_AULT_FANTA_INTRO_NODE = auto()
    ON_THE_STORIES_NODE = auto()
    ON_SEARCH_NODE = auto()
    ON_APPENDIX_NODE = auto()
    ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE = auto()
    ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE = auto()
    ON_APPENDIX_CENSORSHIP_FIXES_NODE = auto()
    ON_INDEX_NODE = auto()
    ON_CHRONO_BY_YEAR_NODE = auto()
    ON_YEAR_RANGE_NODE = auto()
    ON_SERIES_NODE = auto()
    ON_CS_NODE = auto()
    ON_CS_YEAR_RANGE_NODE = auto()
    ON_DD_NODE = auto()
    ON_US_NODE = auto()
    ON_US_YEAR_RANGE_NODE = auto()
    ON_DDS_NODE = auto()
    ON_USS_NODE = auto()
    ON_GG_NODE = auto()
    ON_MISC_NODE = auto()
    ON_CATEGORIES_NODE = auto()
    ON_CATEGORY_NODE = auto()
    ON_TAG_GROUP_NODE = auto()
    ON_TAG_NODE = auto()
    ON_TITLE_NODE = auto()
    ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET = auto()
    ON_TITLE_SEARCH_BOX_NODE = auto()
    ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET = auto()
    ON_TAG_SEARCH_BOX_NODE = auto()


# TODO: Consolidate views and currents into classes.
class BackgroundViews:
    TOP_VIEW_EVENT_TIMEOUT_SECS = 1000.0
    BOTTOM_VIEW_EVENT_TIMEOUT_SECS = 1000.0

    def __init__(
        self,
        reader_settings: ReaderSettings,
        all_fanta_titles: FantaComicBookInfoDict,
        title_lists: dict[str, list[FantaComicBookInfo]],
        random_title_images: RandomTitleImages,
    ) -> None:
        self._reader_settings = reader_settings
        self._all_fanta_titles = all_fanta_titles
        self._title_lists = title_lists
        self._random_title_images = random_title_images

        self._top_view_image_random_color_tint = RandomColorTint(30, 50)
        self._bottom_view_fun_image_random_color_tint = RandomColorTint(80, 50)
        self._bottom_view_title_image_random_color_tint = RandomColorTint(30, 70)
        self._bottom_view_title_image_random_color_tint.set_full_color_alpha_range(100, 150)
        self._bottom_view_title_image_random_color_tint.set_alpha_range(150, 200)

        self._top_view_image_opacity = 0.0
        self._top_view_image_info: ImageInfo = ImageInfo()
        self._top_view_image_color: Color = (0, 0, 0, 0)
        self._top_view_change_event = None

        self._bottom_view_title_opacity = 0.0

        self._bottom_view_fun_image_opacity = 0.0
        self._bottom_view_fun_image_info: ImageInfo = ImageInfo()
        self._bottom_view_fun_image_color: Color = (0, 0, 0, 0)
        self._bottom_view_change_fun_image_event = None

        self._bottom_view_title_image_info: ImageInfo = ImageInfo()
        self._bottom_view_title_image_color: Color = (0, 0, 0, 0)

        self._current_year_range = ""
        self._current_cs_year_range = ""
        self._current_us_year_range = ""
        self._current_category = ""
        self._current_tag_group = None
        self._current_tag = None

        self._view_state = ViewStates.PRE_INIT

    def _get_fanta_info(self, title: Titles) -> None | FantaComicBookInfo:
        # TODO: Very roundabout way to get fanta info
        # TODO: And duplicated in main_screen
        title_str = BARKS_TITLES[title]
        if title_str not in self._all_fanta_titles:
            return None
        return self._all_fanta_titles[title_str]

    def _get_fanta_title_list(self, titles: list[Titles]) -> list[FantaComicBookInfo]:
        fanta_title_list = [self._get_fanta_info(title) for title in titles]
        return [title for title in fanta_title_list if title]

    def get_view_state(self) -> ViewStates:
        return self._view_state

    def get_top_view_image_opacity(self) -> float:
        return self._top_view_image_opacity

    def get_top_view_image_color(self) -> Color:
        return self._top_view_image_color

    def get_top_view_image_info(self) -> ImageInfo:
        return self._top_view_image_info

    def get_bottom_view_title_opacity(self) -> float:
        return self._bottom_view_title_opacity

    def get_bottom_view_fun_image_opacity(self) -> float:
        return self._bottom_view_fun_image_opacity

    def get_bottom_view_fun_image_color(self) -> Color:
        return self._bottom_view_fun_image_color

    def get_bottom_view_fun_image_info(self) -> ImageInfo:
        return self._bottom_view_fun_image_info

    def get_bottom_view_title_image_color(self) -> Color:
        return self._bottom_view_title_image_color

    def get_bottom_view_title_image_info(self) -> ImageInfo:
        return self._bottom_view_title_image_info

    def get_current_category(self) -> str:
        return self._current_category

    def set_current_category(self, cat: str) -> None:
        self._current_category = cat

    def get_current_tag_group(self) -> None | TagGroups:
        return self._current_tag_group

    def set_current_tag_group(self, tag_group: None | TagGroups) -> None:
        self._current_tag_group = tag_group

    def get_current_tag(self) -> None | Tags:
        return self._current_tag

    def set_current_tag(self, tag: None | Tags) -> None:
        self._current_tag = tag

    def get_current_year_range(self) -> str:
        return self._current_year_range

    def set_current_year_range(self, year_range: str) -> None:
        self._current_year_range = year_range

    def get_current_cs_year_range(self) -> str:
        return self._current_cs_year_range

    def set_current_cs_year_range(self, year_range: str) -> None:
        self._current_cs_year_range = year_range

    def get_current_us_year_range(self) -> str:
        return self._current_us_year_range

    def set_current_us_year_range(self, year_range: str) -> None:
        self._current_us_year_range = year_range

    def set_view_state(self, view_state: ViewStates) -> None:
        self._view_state = view_state
        self._update_views()

    def _update_views(self) -> None:
        if self._view_state == ViewStates.PRE_INIT:
            self._top_view_image_opacity = 0.5
            self._set_top_view_image()
            self._bottom_view_fun_image_opacity = 0.5
            self._set_bottom_view_fun_image()
            self._bottom_view_title_opacity = 0.0
            return

        if self._view_state in [
            ViewStates.ON_TITLE_SEARCH_BOX_NODE,
            ViewStates.ON_TITLE_NODE,
            ViewStates.ON_TAG_SEARCH_BOX_NODE,
        ]:
            self._bottom_view_fun_image_opacity = 0.0
            self._bottom_view_title_opacity = 1.0
        else:
            self._bottom_view_fun_image_opacity = 1.0
            self._bottom_view_title_opacity = 0.0

        self._set_top_view_image()
        self._set_bottom_view_fun_image()
        self._set_bottom_view_title_image_color()

    def _set_top_view_image(self) -> None:  # noqa: PLR0915
        # noinspection PyUnreachableCode
        match self._view_state:
            case ViewStates.PRE_INIT | ViewStates.INITIAL:
                self._set_initial_top_view_image()
            case ViewStates.ON_INTRO_NODE:
                self._set_top_view_image_for_intro()
            case ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_intro()
            case ViewStates.ON_INTRO_DON_AULT_FANTA_INTRO_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_intro()
            case (
                ViewStates.ON_THE_STORIES_NODE
                | ViewStates.ON_CHRONO_BY_YEAR_NODE
                | ViewStates.ON_SERIES_NODE
                | ViewStates.ON_CATEGORIES_NODE
                # TODO: Save parent node as the state to use??
                | ViewStates.ON_TITLE_NODE
            ):
                self._set_top_view_image_for_stories()
            case ViewStates.ON_CS_NODE:
                self._set_top_view_image_for_cs()
            case ViewStates.ON_CS_YEAR_RANGE_NODE:
                self._set_top_view_image_for_cs_year_range()
            case ViewStates.ON_DD_NODE:
                self._set_top_view_image_for_dd()
            case ViewStates.ON_US_NODE:
                self._set_top_view_image_for_us()
            case ViewStates.ON_US_YEAR_RANGE_NODE:
                self._set_top_view_image_for_us_year_range()
            case ViewStates.ON_DDS_NODE:
                self._set_top_view_image_for_dds()
            case ViewStates.ON_USS_NODE:
                self._set_top_view_image_for_uss()
            case ViewStates.ON_GG_NODE:
                self._set_top_view_image_for_gg()
            case ViewStates.ON_MISC_NODE:
                self._set_top_view_image_for_misc()
            case ViewStates.ON_YEAR_RANGE_NODE:
                self._set_top_view_image_for_year_range()
            case ViewStates.ON_CATEGORY_NODE:
                self._set_top_view_image_for_category()
            case ViewStates.ON_TAG_GROUP_NODE:
                self._set_top_view_image_for_tag_group()
            case ViewStates.ON_TAG_NODE:
                self._set_top_view_image_for_tag()
            case (
                ViewStates.ON_SEARCH_NODE
                | ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
                | ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
                | ViewStates.ON_TITLE_SEARCH_BOX_NODE
                | ViewStates.ON_TAG_SEARCH_BOX_NODE
            ):
                self._set_top_view_image_for_search()
            case ViewStates.ON_APPENDIX_NODE:
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix_censorship_fixes()
            case ViewStates.ON_INDEX_NODE:
                self._set_top_view_image_for_index()
            case _:
                raise AssertionError

        self._set_top_view_image_color()
        self._schedule_top_view_event()

        logging.debug(
            f"Top view image:"
            f" State: {self._view_state},"
            f" Image: '{get_abbrev_path(self._top_view_image_info.filename)}',"
            f" FitMode: '{self._top_view_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._top_view_image_color)},"
            f" Opacity: {self._top_view_image_opacity}."
        )

    def _set_initial_top_view_image(self) -> None:
        title = Titles.COLD_BARGAIN_A
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_for_intro(self) -> None:
        title = Titles.ADVENTURE_DOWN_UNDER
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_for_stories(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[ALL_LISTS])

    def _set_top_view_image_for_cs(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_CS])

    def _set_top_view_image_for_dd(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_DDA])

    def _set_top_view_image_for_us(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_USA])

    def _set_top_view_image_for_dds(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_DDS])

    def _set_top_view_image_for_uss(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_USS])

    def _set_top_view_image_for_gg(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_GG])

    def _set_top_view_image_for_misc(self) -> None:
        self._top_view_image_info = self._get_top_view_random_image(self._title_lists[SERIES_MISC])

    def _set_top_view_image_for_category(self) -> None:
        logging.debug(f"Current category: '{self._current_category}'.")
        if not self._current_category:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            self._top_view_image_info = self._get_top_view_random_image(
                self._title_lists[self._current_category]
            )

    def _set_top_view_image_for_tag_group(self) -> None:
        logging.debug(f"Current tag_group: '{self._current_tag_group}'.")
        if not self._current_tag_group:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            fanta_title_list = self._get_fanta_title_list(
                BARKS_TAG_GROUPS_TITLES[self._current_tag_group]
            )
            self._top_view_image_info = self._get_top_view_random_image(fanta_title_list)

    def _set_top_view_image_for_tag(self) -> None:
        logging.debug(f"Current tag: '{self._current_tag}'.")
        if not self._current_tag:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            fanta_title_list = self._get_fanta_title_list(BARKS_TAGGED_TITLES[self._current_tag])
            self._top_view_image_info = self._get_top_view_random_image(fanta_title_list)

    def _set_top_view_image_for_year_range(self) -> None:
        logging.debug(f"Year range: '{self._current_year_range}'.")
        if not self._current_year_range:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            self._top_view_image_info = self._get_top_view_random_image(
                self._title_lists[self._current_year_range]
            )

    def _set_top_view_image_for_cs_year_range(self) -> None:
        logging.debug(f"CS Year range: '{self._current_cs_year_range}'.")
        if not self._current_cs_year_range:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            cs_range = FilteredTitleLists.get_cs_range_str_from_str(self._current_cs_year_range)
            logging.debug(f"CS Year range key: '{cs_range}'.")
            self._top_view_image_info = self._get_top_view_random_image(self._title_lists[cs_range])

    def _set_top_view_image_for_us_year_range(self) -> None:
        logging.debug(f"US Year range: '{self._current_us_year_range}'.")
        if not self._current_us_year_range:
            title = Titles.BACK_TO_THE_KLONDIKE
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            us_range = FilteredTitleLists.get_us_range_str_from_str(self._current_us_year_range)
            logging.debug(f"US Year range key: '{us_range}'.")
            self._top_view_image_info = self._get_top_view_random_image(self._title_lists[us_range])

    def _get_top_view_random_image(self, title_list: list[FantaComicBookInfo]) -> ImageInfo:
        return self._random_title_images.get_random_image(
            title_list, file_types=TOP_VIEW_IMAGE_TYPES, use_edited_only=True
        )

    def _set_top_view_image_for_search(self) -> None:
        self._top_view_image_info = self._random_title_images.get_random_search_image()

    def _set_top_view_image_for_appendix(self) -> None:
        title = Titles.FABULOUS_PHILOSOPHERS_STONE_THE
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_for_appendix_censorship_fixes(self) -> None:
        title = Titles.VACATION_TIME
        file1 = (
            self._reader_settings.file_paths.get_comic_favourite_files_dir()
            / VACATION_TIME
            / "076-8-flipped.png"
        )
        self._top_view_image_info = ImageInfo(file1, title, FIT_MODE_COVER)

    def _set_top_view_image_for_index(self) -> None:
        title = Titles.TRUANT_OFFICER_DONALD
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_color(self) -> None:
        self._top_view_image_color = self._top_view_image_random_color_tint.get_random_color()

    def _set_bottom_view_fun_image(self) -> None:
        if self._view_state in [
            ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET,
            ViewStates.ON_TITLE_SEARCH_BOX_NODE,
            ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET,
            ViewStates.ON_TAG_SEARCH_BOX_NODE,
            ViewStates.ON_TITLE_NODE,
        ]:
            return

        if self._view_state == ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE:
            fanta_title_list = self._get_fanta_title_list(
                BARKS_TAGGED_TITLES[Tags.CENSORED_STORIES_BUT_FIXED]
            )
            self._bottom_view_fun_image_info = self._random_title_images.get_random_image(
                fanta_title_list, use_random_fit_mode=True
            )
        else:
            self._bottom_view_fun_image_info = self._random_title_images.get_random_image(
                self._get_fun_image_titles(), use_random_fit_mode=True
            )
        self._set_bottom_view_fun_image_color()
        self._schedule_bottom_view_fun_image_event()

        logging.debug(
            f"Bottom view fun image:"
            f" State: {self._view_state},"
            f" Image: '{get_abbrev_path(self._bottom_view_fun_image_info.filename)}',"
            f" FitMode: '{self._bottom_view_fun_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._bottom_view_fun_image_color)},"
            f" Opacity: {self._bottom_view_fun_image_opacity}."
        )

    def _get_fun_image_titles(self) -> list[FantaComicBookInfo]:
        if not DEBUG_FUN_IMAGE_TITLES:
            return self._title_lists[ALL_LISTS]

        return [
            t
            for t in self._title_lists[ALL_LISTS]
            if t.comic_book_info.title in DEBUG_FUN_IMAGE_TITLES
        ]

    # TODO: Rationalize image color setters - make more responsive to individual images
    #       have fun images weighted to larger opacity and full color
    def _set_bottom_view_fun_image_color(self) -> None:
        self._bottom_view_fun_image_color = (
            self._bottom_view_fun_image_random_color_tint.get_random_color()
        )

    def set_bottom_view_title_image_file(self, image_file: Path) -> None:
        self._bottom_view_title_image_info.filename = image_file
        self._log_bottom_view_title_state()

    def _set_bottom_view_title_image_color(self) -> None:
        self._bottom_view_title_image_color = (
            self._bottom_view_title_image_random_color_tint.get_random_color()
        )

        self._log_bottom_view_title_state()

    def _log_bottom_view_title_state(self) -> None:
        logging.debug(
            f"Bottom view title image:"
            f" State: {self._view_state},"
            f" Image: '{self._bottom_view_title_image_info.filename}',"
            f" FitMode: '{self._bottom_view_title_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._bottom_view_title_image_color)},"
            f" Opacity: {self._bottom_view_title_opacity}."
        )

    def _schedule_top_view_event(self) -> None:
        if self._top_view_change_event:
            self._top_view_change_event.cancel()

        self._top_view_change_event = Clock.schedule_interval(
            lambda _dt: self._set_top_view_image(), self.TOP_VIEW_EVENT_TIMEOUT_SECS
        )

    def _schedule_bottom_view_fun_image_event(self) -> None:
        if self._bottom_view_change_fun_image_event:
            self._bottom_view_change_fun_image_event.cancel()

        self._bottom_view_change_fun_image_event = Clock.schedule_interval(
            lambda _dt: self._set_bottom_view_fun_image(), self.BOTTOM_VIEW_EVENT_TIMEOUT_SECS
        )
