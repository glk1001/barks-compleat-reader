# ruff: noqa: ERA001

from __future__ import annotations

from enum import Enum, IntEnum, auto
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import (
    BARKS_TAG_GROUPS_TITLES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comics_utils import get_abbrev_path
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    ALL_LISTS,
    SERIES_CS,
    SERIES_DDA,
    SERIES_DDS,
    SERIES_GG,
    SERIES_MISC,
    SERIES_USA,
    SERIES_USS,
    FantaComicBookInfo,
)
from kivy.clock import Clock
from loguru import logger

from barks_reader.random_title_images import FIT_MODE_COVER, ImageInfo, RandomTitleImages
from barks_reader.reader_colors import RandomColorTint
from barks_reader.reader_file_paths import ALL_TYPES, FileTypes
from barks_reader.reader_formatter import get_formatted_color
from barks_reader.reader_utils import get_cs_range_str_from_str, get_us_range_str_from_str

if TYPE_CHECKING:
    from comic_utils.comic_consts import PanelPath

    from barks_reader.reader_colors import Color
    from barks_reader.reader_settings import ReaderSettings

TOP_VIEW_IMAGE_TYPES = {
    t for t in FileTypes if t not in [FileTypes.NONTITLE, FileTypes.ORIGINAL_ART]
}
TITLE_VIEW_IMAGE_TYPES = {
    t for t in FileTypes if t not in [FileTypes.INSET, FileTypes.ORIGINAL_ART]
}

DEBUG_FUN_IMAGE_TITLES = None
# DEBUG_FUN_IMAGE_TITLES = [Titles.LOST_IN_THE_ANDES]


class ImageThemes(Enum):
    AI = auto()
    BLACK_AND_WHITE = auto()
    CENSORSHIP = auto()
    CLASSICS = auto()
    FAVOURITES = auto()
    INSETS = auto()
    SILHOUETTES = auto()
    SPLASHES = auto()
    FORTIES = auto()
    FIFTIES = auto()
    SIXTIES = auto()


IMAGE_THEME_TO_FILE_TYPE_MAP = {
    ImageThemes.AI: FileTypes.AI,
    ImageThemes.BLACK_AND_WHITE: FileTypes.BLACK_AND_WHITE,
    ImageThemes.CENSORSHIP: FileTypes.CENSORSHIP,
    ImageThemes.FAVOURITES: FileTypes.FAVOURITE,
    ImageThemes.INSETS: FileTypes.INSET,
    ImageThemes.SILHOUETTES: FileTypes.SILHOUETTE,
    ImageThemes.SPLASHES: FileTypes.SPLASH,
}
IMAGE_THEMES_WITH_NO_FILES = {
    ImageThemes.CLASSICS,
    ImageThemes.FORTIES,
    ImageThemes.FIFTIES,
    ImageThemes.SIXTIES,
}
assert len(ImageThemes) == (len(IMAGE_THEME_TO_FILE_TYPE_MAP) + len(IMAGE_THEMES_WITH_NO_FILES))


class ViewStates(IntEnum):
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
    ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE = auto()
    ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE = auto()
    ON_APPENDIX_CENSORSHIP_FIXES_NODE = auto()
    ON_INDEX_NODE = auto()
    ON_INDEX_MAIN_NODE = auto()
    ON_INDEX_SPEECH_NODE = auto()
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


BOTTOM_VIEW_MAIN_INDEX_OPACITY_1_STATES = {
    ViewStates.ON_INDEX_MAIN_NODE,
}
BOTTOM_VIEW_SPEECH_INDEX_OPACITY_1_STATES = {
    ViewStates.ON_INDEX_SPEECH_NODE,
}
BOTTOM_VIEW_TITLE_OPACITY_1_STATES = {
    ViewStates.ON_TITLE_NODE,
    ViewStates.ON_TITLE_SEARCH_BOX_NODE,
    ViewStates.ON_TAG_SEARCH_BOX_NODE,
}
BOTTOM_VIEW_FUN_IMAGE_OPACITY_1_STATES = (
    set(ViewStates) - BOTTOM_VIEW_TITLE_OPACITY_1_STATES
) - BOTTOM_VIEW_MAIN_INDEX_OPACITY_1_STATES


# TODO: Consolidate views and currents into classes.
class BackgroundViews:
    TOP_VIEW_EVENT_TIMEOUT_SECS = 1000.0
    BOTTOM_VIEW_EVENT_TIMEOUT_SECS = 1000.0

    def __init__(
        self,
        reader_settings: ReaderSettings,
        title_lists: dict[str, list[FantaComicBookInfo]],
        random_title_images: RandomTitleImages,
    ) -> None:
        self._reader_settings = reader_settings
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
        self._bottom_view_fun_image_info: ImageInfo | None = None
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
        self._current_bottom_view_title = ""

        self._fun_image_themes: set[ImageThemes] | None = None
        self._cached_fun_titles: tuple[list[FantaComicBookInfo], set[FileTypes]] | None = None

        self._view_state = ViewStates.PRE_INIT

    def set_fun_image_themes(self, image_themes: set[ImageThemes] | None) -> None:
        logger.debug(f"Set self._fun_image_themes = {image_themes}.")
        self._fun_image_themes = image_themes
        self._cached_fun_titles = self._get_fun_image_titles()

    @staticmethod
    def _get_fanta_info(title: Titles) -> None | FantaComicBookInfo:
        # TODO: Very roundabout way to get fanta info
        # TODO: And duplicated in main_screen
        title_str = BARKS_TITLES[title]
        if title_str not in ALL_FANTA_COMIC_BOOK_INFO:
            return None
        return ALL_FANTA_COMIC_BOOK_INFO[title_str]

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
        assert self._bottom_view_fun_image_info is not None
        return self._bottom_view_fun_image_info

    def reset_bottom_view_fun_image_info(self) -> None:
        self._bottom_view_fun_image_info = None

    def get_bottom_view_title_image_color(self) -> Color:
        return self._bottom_view_title_image_color

    def get_bottom_view_title_image_info(self) -> ImageInfo:
        return self._bottom_view_title_image_info

    def get_main_index_view_opacity(self) -> float:
        return 1.0 if (self._view_state in BOTTOM_VIEW_MAIN_INDEX_OPACITY_1_STATES) else 0.0

    def get_speech_index_view_opacity(self) -> float:
        return 1.0 if (self._view_state in BOTTOM_VIEW_SPEECH_INDEX_OPACITY_1_STATES) else 0.0

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

    def get_current_bottom_view_title(self) -> str:
        return self._current_bottom_view_title

    def set_current_bottom_view_title(self, title: str) -> None:
        self._current_bottom_view_title = title

    def set_view_state(self, view_state: ViewStates) -> None:
        logger.info(f"Updating background view state to {view_state.name}.")
        self._view_state = view_state
        self._update_views()

    def _update_views(self) -> None:
        if self._view_state == ViewStates.PRE_INIT:
            self._top_view_image_opacity = 0.5
            self._set_next_top_view_image()
            self._bottom_view_fun_image_opacity = 0.5
            self._set_next_bottom_view_fun_image()
            self._bottom_view_title_opacity = 0.0
            return

        self._bottom_view_fun_image_opacity = (
            1.0 if self._view_state in BOTTOM_VIEW_FUN_IMAGE_OPACITY_1_STATES else 0.0
        )
        self._bottom_view_title_opacity = (
            1.0 if self._view_state in BOTTOM_VIEW_TITLE_OPACITY_1_STATES else 0.0
        )

        self._set_next_top_view_image()
        self._set_next_bottom_view_fun_image()
        self.set_next_bottom_view_title_image()
        self._set_bottom_view_title_image_color()

    def _set_next_top_view_image(self) -> None:  # noqa: PLR0915
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
            case ViewStates.ON_APPENDIX_RICH_TOMASSO_ON_COLORING_BARKS_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_DON_AULT_LIFE_AMONG_DUCKS_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_MAGGIE_THOMPSON_COMICS_READERS_FIND_COMIC_BOOK_GOLD_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_GEORGE_LUCAS_AN_APPRECIATION_NODE:
                # TODO: Fix this
                self._set_top_view_image_for_appendix()
            case ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE:
                self._set_top_view_image_for_appendix_censorship_fixes()
            case ViewStates.ON_INDEX_NODE:
                self._set_top_view_image_for_index()
            case ViewStates.ON_INDEX_MAIN_NODE:
                self._set_top_view_image_for_index()
            case ViewStates.ON_INDEX_SPEECH_NODE:
                self._set_top_view_image_for_index()
            case _:
                # noinspection PyUnreachableCode
                # Reason: inspection seems broken here.
                raise AssertionError

        self._set_top_view_image_color()
        self._schedule_top_view_event()

        assert self._top_view_image_info.filename

        logger.debug(
            f"Top view image:"
            f" State: {self._view_state.name},"
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
        logger.debug(f"Current category: '{self._current_category}'.")
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
        logger.debug(f"Current tag_group: '{self._current_tag_group}'.")
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
        logger.debug(f"Current tag: '{self._current_tag}'.")
        if not self._current_tag:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            fanta_title_list = self._get_fanta_title_list(BARKS_TAGGED_TITLES[self._current_tag])
            self._top_view_image_info = self._get_top_view_random_image(fanta_title_list)

    def _set_top_view_image_for_year_range(self) -> None:
        logger.debug(f"Year range: '{self._current_year_range}'.")
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
        logger.debug(f"CS Year range: '{self._current_cs_year_range}'.")
        if not self._current_cs_year_range:
            title = Titles.GOOD_NEIGHBORS
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            cs_range = get_cs_range_str_from_str(self._current_cs_year_range)
            logger.debug(f"CS Year range key: '{cs_range}'.")
            self._top_view_image_info = self._get_top_view_random_image(self._title_lists[cs_range])

    def _set_top_view_image_for_us_year_range(self) -> None:
        logger.debug(f"US Year range: '{self._current_us_year_range}'.")
        if not self._current_us_year_range:
            title = Titles.BACK_TO_THE_KLONDIKE
            self._top_view_image_info = ImageInfo(
                self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
            )
        else:
            us_range = get_us_range_str_from_str(self._current_us_year_range)
            logger.debug(f"US Year range key: '{us_range}'.")
            self._top_view_image_info = self._get_top_view_random_image(self._title_lists[us_range])

    def _get_top_view_random_image(self, title_list: list[FantaComicBookInfo]) -> ImageInfo:
        return self._random_title_images.get_random_image(
            title_list, file_types=TOP_VIEW_IMAGE_TYPES, use_only_edited_if_possible=True
        )

    def _set_top_view_image_for_search(self) -> None:
        self._top_view_image_info = self._random_title_images.get_random_search_image()

    def _set_top_view_image_for_appendix(self) -> None:
        title = Titles.FABULOUS_PHILOSOPHERS_STONE_THE
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_for_appendix_censorship_fixes(self) -> None:
        self._top_view_image_info = self._random_title_images.get_random_censorship_fix_image()

    def _set_top_view_image_for_index(self) -> None:
        title = Titles.TRUANT_OFFICER_DONALD
        self._top_view_image_info = ImageInfo(
            self._reader_settings.file_paths.get_comic_inset_file(title), title, FIT_MODE_COVER
        )

    def _set_top_view_image_color(self) -> None:
        self._top_view_image_color = self._top_view_image_random_color_tint.get_random_color()

    def set_bottom_view_fun_image(self, image_info: ImageInfo) -> None:
        self._bottom_view_fun_image_info = image_info

    def _set_next_bottom_view_fun_image(self) -> None:
        if self._view_state in [
            ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET,
            ViewStates.ON_TITLE_SEARCH_BOX_NODE,
            ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET,
            ViewStates.ON_TAG_SEARCH_BOX_NODE,
            ViewStates.ON_TITLE_NODE,
            ViewStates.ON_INDEX_MAIN_NODE,
            ViewStates.ON_INDEX_SPEECH_NODE,
        ]:
            return

        if (self._view_state == ViewStates.INITIAL) and self._bottom_view_fun_image_info:
            return

        self._bottom_view_fun_image_info = self._get_next_fun_view_image_info()
        self._set_bottom_view_fun_image_color()
        self._schedule_bottom_view_fun_image_event()

        assert self._bottom_view_fun_image_info.filename

        logger.debug(
            f"Bottom view fun image:"
            f" State: {self._view_state.name},"
            f" Image: '{get_abbrev_path(self._bottom_view_fun_image_info.filename)}',"
            f" FitMode: '{self._bottom_view_fun_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._bottom_view_fun_image_color)},"
            f" Opacity: {self._bottom_view_fun_image_opacity}."
        )

    def _get_next_fun_view_image_info(self) -> ImageInfo:
        if self._view_state == ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE:
            fanta_title_list = self._get_fanta_title_list(
                BARKS_TAGGED_TITLES[Tags.CENSORED_STORIES_BUT_FIXED]
            )
            return self._random_title_images.get_random_image(
                fanta_title_list, use_random_fit_mode=True
            )

        assert self._cached_fun_titles
        titles, file_types = self._cached_fun_titles

        return self._random_title_images.get_random_image(
            titles,
            file_types=file_types,
            use_random_fit_mode=True,
        )

    def _get_fun_image_titles(self) -> tuple[list[FantaComicBookInfo], set[FileTypes]]:
        if DEBUG_FUN_IMAGE_TITLES:
            return [
                t
                for t in self._title_lists[ALL_LISTS]
                if t.comic_book_info.title in DEBUG_FUN_IMAGE_TITLES
            ], self._get_file_types_to_use()

        if not self._fun_image_themes:
            return self._title_lists[ALL_LISTS], self._get_file_types_to_use()

        return self._get_themed_fun_image_titles()

    def _get_themed_fun_image_titles(self) -> tuple[list[FantaComicBookInfo], set[FileTypes]]:
        file_types = self._get_file_types_to_use()

        theme_titles: set[str] = set()

        assert self._fun_image_themes

        if ImageThemes.FORTIES in self._fun_image_themes:
            self._update_titles(theme_titles, (1942, 1949))
        if ImageThemes.FIFTIES in self._fun_image_themes:
            self._update_titles(theme_titles, (1950, 1959))
        if ImageThemes.SIXTIES in self._fun_image_themes:
            self._update_titles(theme_titles, (1960, 1961))
        if ImageThemes.CLASSICS in self._fun_image_themes:
            theme_titles.update(
                [BARKS_TITLES[title] for title in BARKS_TAGGED_TITLES[Tags.CLASSICS]]
            )

        for file_type in file_types:
            theme_titles.update(
                self._reader_settings.file_paths.get_file_type_titles(file_type, theme_titles)
            )

        return [ALL_FANTA_COMIC_BOOK_INFO[title_str] for title_str in theme_titles], file_types

    def _update_titles(self, title_set: set[str], year_range: tuple[int, int]) -> None:
        for year in range(year_range[0], year_range[1] + 1):
            title_set.update(
                BARKS_TITLES[info.comic_book_info.title] for info in self._title_lists[str(year)]
            )

    def _get_file_types_to_use(self) -> set[FileTypes]:
        if self._fun_image_themes is None:
            return ALL_TYPES

        file_types_to_use = set()

        for theme in self._fun_image_themes:
            if theme not in IMAGE_THEME_TO_FILE_TYPE_MAP:
                continue
            file_types_to_use.add(IMAGE_THEME_TO_FILE_TYPE_MAP[theme])

        if len(file_types_to_use) == 0:
            file_types_to_use = ALL_TYPES.copy()
            file_types_to_use.discard(FileTypes.NONTITLE)

        logger.debug(f"file_types_to_use = {file_types_to_use}")

        return file_types_to_use

    # TODO: Rationalize image color setters - make more responsive to individual images
    #       have fun images weighted to larger opacity and full color
    def _set_bottom_view_fun_image_color(self) -> None:
        self._bottom_view_fun_image_color = (
            self._bottom_view_fun_image_random_color_tint.get_random_color()
        )

    def set_next_bottom_view_title_image(self) -> None:
        if self._bottom_view_title_image_info.filename:
            logger.debug(
                f'Using provided title image file "{self._bottom_view_title_image_info.filename}".'
            )
        else:
            if not self._current_bottom_view_title:
                logger.debug("No bottom view title set. Nothing to do.")
                return

            image_file = self._random_title_images.get_random_image_for_title(
                self._current_bottom_view_title,
                TITLE_VIEW_IMAGE_TYPES,
                use_only_edited_if_possible=True,
            )
            logger.debug(f'Using random title image file "{image_file}".')
            self.set_bottom_view_title_image_file(image_file)

    def set_bottom_view_title_image_file(self, image_file: PanelPath | None) -> None:
        self._bottom_view_title_image_info.filename = image_file
        self._log_bottom_view_title_state()

    def _set_bottom_view_title_image_color(self) -> None:
        self._bottom_view_title_image_color = (
            self._bottom_view_title_image_random_color_tint.get_random_color()
        )

        self._log_bottom_view_title_state()

    def _log_bottom_view_title_state(self) -> None:
        logger.debug(
            f"Bottom view title image:"
            f" State: {self._view_state.name},"
            f" Image: '{self._bottom_view_title_image_info.filename}',"
            f" FitMode: '{self._bottom_view_title_image_info.fit_mode}',"
            f" Color: {get_formatted_color(self._bottom_view_title_image_color)},"
            f" Opacity: {self._bottom_view_title_opacity}."
        )

    def _schedule_top_view_event(self) -> None:
        if self._top_view_change_event:
            self._top_view_change_event.cancel()

        self._top_view_change_event = Clock.schedule_interval(
            lambda _dt: self._set_next_top_view_image(), self.TOP_VIEW_EVENT_TIMEOUT_SECS
        )

    def _schedule_bottom_view_fun_image_event(self) -> None:
        if self._bottom_view_change_fun_image_event:
            self._bottom_view_change_fun_image_event.cancel()

        self._bottom_view_change_fun_image_event = Clock.schedule_interval(
            lambda _dt: self._set_next_bottom_view_fun_image(), self.BOTTOM_VIEW_EVENT_TIMEOUT_SECS
        )
