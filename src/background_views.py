import logging
from enum import Enum, auto
from typing import Dict, List, Union

from kivy.clock import Clock

from barks_fantagraphics.barks_tags import Tags, BARKS_TAGGED_TITLES
from barks_fantagraphics.barks_titles import Titles, BARKS_TITLES
from barks_fantagraphics.comics_utils import get_abbrev_path
from barks_fantagraphics.fanta_comics_info import (
    FantaComicBookInfo,
    FantaComicBookInfoDict,
    ALL_LISTS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_USA,
    SERIES_DDS,
    SERIES_USS,
    SERIES_GG,
    SERIES_MISC,
)
from file_paths import get_comic_inset_file
from filtered_title_lists import FilteredTitleLists
from random_title_images import RandomTitleImages, ImageInfo, FIT_MODE_COVER
from reader_colors import RandomColorTint
from reader_consts_and_types import Color
from reader_utils import get_formatted_color


class ViewStates(Enum):
    PRE_INIT = auto()
    INITIAL = auto()
    ON_INTRO_NODE = auto()
    ON_THE_STORIES_NODE = auto()
    ON_SEARCH_NODE = auto()
    ON_APPENDIX_NODE = auto()
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
    ON_TAG_NODE = auto()
    ON_TITLE_NODE = auto()
    ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET = auto()
    ON_TITLE_SEARCH_BOX_NODE = auto()
    ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET = auto()
    ON_TAG_SEARCH_BOX_NODE = auto()


class BackgroundViews:
    TOP_VIEW_EVENT_TIMEOUT_SECS = 1000.0
    BOTTOM_VIEW_EVENT_TIMEOUT_SECS = 1000.0

    def __init__(
        self,
        all_fanta_titles: FantaComicBookInfoDict,
        title_lists: Dict[str, List[FantaComicBookInfo]],
        random_title_images: RandomTitleImages,
    ):
        self.all_fanta_titles = all_fanta_titles
        self.title_lists = title_lists
        self.random_title_images = random_title_images

        self.__top_view_image_random_color_tint = RandomColorTint(30, 50)
        self.__bottom_view_fun_image_random_color_tint = RandomColorTint(80, 50)
        self.__bottom_view_title_image_random_color_tint = RandomColorTint(30, 70)
        self.__bottom_view_title_image_random_color_tint.set_full_color_alpha_range(100, 150)
        self.__bottom_view_title_image_random_color_tint.set_alpha_range(150, 200)

        self.__top_view_image_opacity = 0.0
        self.__top_view_image_info: ImageInfo = ImageInfo()
        self.__top_view_image_color: Color = (0, 0, 0, 0)
        self.__top_view_change_event = None

        self.__bottom_view_title_opacity = 0.0

        self.__bottom_view_fun_image_opacity = 0.0
        self.__bottom_view_fun_image_info: ImageInfo = ImageInfo()
        self.__bottom_view_fun_image_color: Color = (0, 0, 0, 0)
        self.__bottom_view_change_fun_image_event = None

        self.__bottom_view_title_image_info: ImageInfo = ImageInfo()
        self.__bottom_view_title_image_color: Color = (0, 0, 0, 0)

        self.__current_year_range = ""
        self.__current_cs_year_range = ""
        self.__current_us_year_range = ""
        self.__current_category = ""
        self.__current_tag = None

        self.__view_state = ViewStates.PRE_INIT

    def __get_fanta_info(self, title: Titles) -> Union[None, FantaComicBookInfo]:
        # TODO: Very roundabout way to get fanta info
        # TODO: And duplicated in main_screen
        title_str = BARKS_TITLES[title]
        if title_str not in self.all_fanta_titles:
            return None
        return self.all_fanta_titles[title_str]

    def __get_fanta_title_list(self, titles: List[Titles]) -> List[FantaComicBookInfo]:
        fanta_title_list = [self.__get_fanta_info(title) for title in titles]
        return [title for title in fanta_title_list if title]

    def get_view_state(self) -> ViewStates:
        return self.__view_state

    def get_top_view_image_opacity(self) -> float:
        return self.__top_view_image_opacity

    def get_top_view_image_color(self) -> Color:
        return self.__top_view_image_color

    def get_top_view_image_info(self) -> ImageInfo:
        return self.__top_view_image_info

    def get_bottom_view_title_opacity(self) -> float:
        return self.__bottom_view_title_opacity

    def get_bottom_view_fun_image_opacity(self) -> float:
        return self.__bottom_view_fun_image_opacity

    def get_bottom_view_fun_image_color(self) -> Color:
        return self.__bottom_view_fun_image_color

    def get_bottom_view_fun_image_info(self) -> ImageInfo:
        return self.__bottom_view_fun_image_info

    def get_bottom_view_title_image_color(self) -> Color:
        return self.__bottom_view_title_image_color

    def get_bottom_view_title_image_info(self) -> ImageInfo:
        return self.__bottom_view_title_image_info

    def get_current_category(self) -> str:
        return self.__current_category

    def set_current_category(self, cat: str) -> None:
        self.__current_category = cat

    def get_current_tag(self) -> Union[None, Tags]:
        return self.__current_tag

    def set_current_tag(self, tag: Union[None, Tags]) -> None:
        self.__current_tag = tag

    def get_current_year_range(self) -> str:
        return self.__current_year_range

    def set_current_year_range(self, year_range: str) -> None:
        self.__current_year_range = year_range

    def get_current_cs_year_range(self) -> str:
        return self.__current_cs_year_range

    def set_current_cs_year_range(self, year_range: str) -> None:
        self.__current_cs_year_range = year_range

    def get_current_us_year_range(self) -> str:
        return self.__current_us_year_range

    def set_current_us_year_range(self, year_range: str) -> None:
        self.__current_us_year_range = year_range

    def set_view_state(self, view_state: ViewStates) -> None:
        self.__view_state = view_state
        self.__update_views()

    def __update_views(self):
        if self.__view_state == ViewStates.PRE_INIT:
            self.__top_view_image_opacity = 0.5
            self.__set_top_view_image()
            self.__bottom_view_fun_image_opacity = 0.5
            self.__set_bottom_view_fun_image()
            self.__bottom_view_title_opacity = 0.0
            return

        if self.__view_state == ViewStates.ON_INTRO_NODE:
            self.__set_top_view_image()
            self.__bottom_view_fun_image_opacity = 0.0
            self.__bottom_view_title_opacity = 0.0
            return

        if self.__view_state in [
            ViewStates.ON_TITLE_SEARCH_BOX_NODE,
            ViewStates.ON_TITLE_NODE,
            ViewStates.ON_TAG_SEARCH_BOX_NODE,
        ]:
            self.__bottom_view_fun_image_opacity = 0.0
            self.__bottom_view_title_opacity = 1.0
        else:
            self.__bottom_view_fun_image_opacity = 1.0
            self.__bottom_view_title_opacity = 0.0

        self.__set_top_view_image()
        self.__set_bottom_view_fun_image()
        self.__set_bottom_view_title_image_color()

    def __set_top_view_image(self) -> None:
        # noinspection PyUnreachableCode
        match self.__view_state:
            case ViewStates.PRE_INIT | ViewStates.INITIAL:
                self.__set_initial_top_view_image()
            case ViewStates.ON_INTRO_NODE:
                self.__set_top_view_image_for_intro()
            case (
                ViewStates.ON_THE_STORIES_NODE
                | ViewStates.ON_CHRONO_BY_YEAR_NODE
                | ViewStates.ON_SERIES_NODE
                | ViewStates.ON_CATEGORIES_NODE
                # TODO: Save parent node as the state to use??
                | ViewStates.ON_TITLE_NODE
            ):
                self.__set_top_view_image_for_stories()
            case ViewStates.ON_CS_NODE:
                self.__set_top_view_image_for_cs()
            case ViewStates.ON_CS_YEAR_RANGE_NODE:
                self.__set_top_view_image_for_cs_year_range()
            case ViewStates.ON_DD_NODE:
                self.__set_top_view_image_for_dd()
            case ViewStates.ON_US_NODE:
                self.__set_top_view_image_for_us()
            case ViewStates.ON_US_YEAR_RANGE_NODE:
                self.__set_top_view_image_for_us_year_range()
            case ViewStates.ON_DDS_NODE:
                self.__set_top_view_image_for_dds()
            case ViewStates.ON_USS_NODE:
                self.__set_top_view_image_for_uss()
            case ViewStates.ON_GG_NODE:
                self.__set_top_view_image_for_gg()
            case ViewStates.ON_MISC_NODE:
                self.__set_top_view_image_for_misc()
            case ViewStates.ON_YEAR_RANGE_NODE:
                self.__set_top_view_image_for_year_range()
            case ViewStates.ON_CATEGORY_NODE:
                self.__set_top_view_image_for_category()
            case ViewStates.ON_TAG_NODE:
                self.__set_top_view_image_for_tag()
            case (
                ViewStates.ON_SEARCH_NODE
                | ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
                | ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
                | ViewStates.ON_TITLE_SEARCH_BOX_NODE
                | ViewStates.ON_TAG_SEARCH_BOX_NODE
            ):
                self.__set_top_view_image_for_search()
            case ViewStates.ON_APPENDIX_NODE:
                self.__set_top_view_image_for_appendix()
            case ViewStates.ON_INDEX_NODE:
                self.__set_top_view_image_for_index()
            case _:
                assert False

        self.__set_top_view_image_color()
        self.__schedule_top_view_event()

        logging.debug(
            f"Top view image:"
            f" State: {self.__view_state},"
            f" Image: '{get_abbrev_path(self.__top_view_image_info.filename)}',"
            f" FitMode: '{self.__top_view_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self.__top_view_image_color)},"
            f" Opacity: {self.__top_view_image_opacity}."
        )

    def __set_initial_top_view_image(self):
        title = Titles.COLD_BARGAIN_A
        self.__top_view_image_info = ImageInfo(get_comic_inset_file(title), title, FIT_MODE_COVER)

    def __set_top_view_image_for_intro(self):
        title = Titles.ADVENTURE_DOWN_UNDER
        self.__top_view_image_info = ImageInfo(get_comic_inset_file(title), title, FIT_MODE_COVER)

    def __set_top_view_image_for_stories(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[ALL_LISTS], use_edited_only=True
        )

    def __set_top_view_image_for_cs(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_CS], use_edited_only=True
        )

    def __set_top_view_image_for_dd(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_DDA], use_edited_only=True
        )

    def __set_top_view_image_for_us(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_USA], use_edited_only=True
        )

    def __set_top_view_image_for_dds(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_DDS], use_edited_only=True
        )

    def __set_top_view_image_for_uss(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_USS], use_edited_only=True
        )

    def __set_top_view_image_for_gg(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_GG], use_edited_only=True
        )

    def __set_top_view_image_for_misc(self):
        self.__top_view_image_info = self.random_title_images.get_random_image(
            self.title_lists[SERIES_MISC], use_edited_only=True
        )

    def __set_top_view_image_for_category(self):
        logging.debug(f"Current category: '{self.__current_category}'.")
        if not self.__current_category:
            title = Titles.GOOD_NEIGHBORS
            self.__top_view_image_info = ImageInfo(
                get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            self.__top_view_image_info = self.random_title_images.get_random_image(
                self.title_lists[self.__current_category], use_edited_only=True
            )

    def __set_top_view_image_for_tag(self):
        logging.debug(f"Current tag: '{self.__current_tag}'.")
        if not self.__current_tag:
            title = Titles.GOOD_NEIGHBORS
            self.__top_view_image_info = ImageInfo(
                get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            fanta_title_list = self.__get_fanta_title_list(BARKS_TAGGED_TITLES[self.__current_tag])
            self.__top_view_image_info = self.random_title_images.get_random_image(
                fanta_title_list, use_edited_only=True
            )

    def __set_top_view_image_for_year_range(self):
        logging.debug(f"Year range: '{self.__current_year_range}'.")
        if not self.__current_year_range:
            title = Titles.GOOD_NEIGHBORS
            self.__top_view_image_info = ImageInfo(
                get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            self.__top_view_image_info = self.random_title_images.get_random_image(
                self.title_lists[self.__current_year_range], use_edited_only=True
            )

    def __set_top_view_image_for_cs_year_range(self):
        logging.debug(f"CS Year range: '{self.__current_cs_year_range}'.")
        if not self.__current_cs_year_range:
            title = Titles.GOOD_NEIGHBORS
            self.__top_view_image_info = ImageInfo(
                get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            cs_range = FilteredTitleLists.get_cs_range_str_from_str(self.__current_cs_year_range)
            logging.debug(f"CS Year range key: '{cs_range}'.")
            self.__top_view_image_info = self.random_title_images.get_random_image(
                self.title_lists[cs_range], use_edited_only=True
            )

    def __set_top_view_image_for_us_year_range(self):
        logging.debug(f"US Year range: '{self.__current_us_year_range}'.")
        if not self.__current_us_year_range:
            title = Titles.BACK_TO_THE_KLONDIKE
            self.__top_view_image_info = ImageInfo(
                get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            us_range = FilteredTitleLists.get_us_range_str_from_str(self.__current_us_year_range)
            logging.debug(f"US Year range key: '{us_range}'.")
            self.__top_view_image_info = self.random_title_images.get_random_image(
                self.title_lists[us_range], use_edited_only=True
            )

    def __set_top_view_image_for_search(self):
        self.__top_view_image_info = self.random_title_images.get_random_search_image()

    def __set_top_view_image_for_appendix(self):
        title = Titles.FABULOUS_PHILOSOPHERS_STONE_THE
        self.__top_view_image_info = ImageInfo(get_comic_inset_file(title), title, FIT_MODE_COVER)

    def __set_top_view_image_for_index(self):
        title = Titles.TRUANT_OFFICER_DONALD
        self.__top_view_image_info = ImageInfo(get_comic_inset_file(title), title, FIT_MODE_COVER)

    def __set_top_view_image_color(self):
        self.__top_view_image_color = self.__top_view_image_random_color_tint.get_random_color()

    def __set_bottom_view_fun_image(self) -> None:
        if self.__view_state in [
            ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET,
            ViewStates.ON_TITLE_SEARCH_BOX_NODE,
            ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET,
            ViewStates.ON_TAG_SEARCH_BOX_NODE,
            ViewStates.ON_TITLE_NODE,
        ]:
            return

        self.__bottom_view_fun_image_info = self.random_title_images.get_random_image(
            self.title_lists[ALL_LISTS], use_random_fit_mode=True
        )
        self.__set_bottom_view_fun_image_color()
        self.__schedule_bottom_view_fun_image_event()

        logging.debug(
            f"Bottom view fun image:"
            f" State: {self.__view_state},"
            f" Image: '{get_abbrev_path(self.__bottom_view_fun_image_info.filename)}',"
            f" FitMode: '{self.__bottom_view_fun_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self.__bottom_view_fun_image_color)},"
            f" Opacity: {self.__bottom_view_fun_image_opacity}."
        )

    # TODO: Rationalize image color setters - make more responsive to individual images
    #       have fun images weighted to larger opacity and full color
    def __set_bottom_view_fun_image_color(self):
        self.__bottom_view_fun_image_color = (
            self.__bottom_view_fun_image_random_color_tint.get_random_color()
        )

    def set_bottom_view_title_image_file(self, image_file: str) -> None:
        self.__bottom_view_title_image_info.filename = image_file
        self.__log_bottom_view_title_state()

    def __set_bottom_view_title_image_color(self):
        self.__bottom_view_title_image_color = (
            self.__bottom_view_title_image_random_color_tint.get_random_color()
        )

        self.__log_bottom_view_title_state()

    def __log_bottom_view_title_state(self):
        logging.debug(
            f"Bottom view title image:"
            f" State: {self.__view_state},"
            f" Image: '{self.__bottom_view_title_image_info.filename}',"
            f" FitMode: '{self.__bottom_view_title_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self.__bottom_view_title_image_color)},"
            f" Opacity: {self.__bottom_view_title_opacity}."
        )

    def __schedule_top_view_event(self):
        if self.__top_view_change_event:
            self.__top_view_change_event.cancel()

        self.__top_view_change_event = Clock.schedule_interval(
            lambda dt: self.__set_top_view_image(), self.TOP_VIEW_EVENT_TIMEOUT_SECS
        )

    def __schedule_bottom_view_fun_image_event(self):
        if self.__bottom_view_change_fun_image_event:
            self.__bottom_view_change_fun_image_event.cancel()

        self.__bottom_view_change_fun_image_event = Clock.schedule_interval(
            lambda dt: self.__set_bottom_view_fun_image(), self.BOTTOM_VIEW_EVENT_TIMEOUT_SECS
        )
