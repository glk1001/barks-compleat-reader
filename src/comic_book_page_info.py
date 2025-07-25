import os.path
from collections import OrderedDict
from dataclasses import dataclass

from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_consts import PageType, JSON_FILE_EXT
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.page_classes import CleanPage, RequiredDimensions
from barks_fantagraphics.pages import (
    FRONT_MATTER_PAGES,
    ROMAN_NUMERALS,
    get_sorted_srce_and_dest_pages_with_dimensions,
)
from reader_settings import ReaderSettings


@dataclass
class PageInfo:
    page_index: int
    display_page_num: str
    page_type: PageType
    srce_page: CleanPage
    dest_page: CleanPage


@dataclass
class ComicBookPageInfo:
    # 'page_map' maps the comic book page numbers, starting with the roman numeral 'i',
    # to the three digit comic archive page number. For example:
    #     'i':  '210'   front matter
    #     'ii': '211'   front matter
    #     '1':  '220'   '1' is the first body page
    #     '2':  '221'   '2' is the second body page
    #     '3':  '222'   '3' is the last body page
    #     '4':  '250'   '4' is a back matter page and the last page
    page_map: OrderedDict[str, PageInfo]
    last_body_page: str
    last_page: str
    required_dim: RequiredDimensions


class ComicBookPageInfoManager:
    def __init__(self, comics_database: ComicsDatabase, reader_settings: ReaderSettings):
        self._comics_database = comics_database
        self._sys_file_paths = reader_settings.sys_file_paths

    def get_comic_page_info(self, comic: ComicBook) -> ComicBookPageInfo:
        panel_segments_root_dir = (
            self._sys_file_paths.get_barks_reader_fantagraphics_panel_segments_root_dir()
        )
        vol_title = self._comics_database.get_fantagraphics_volume_title(comic.get_fanta_volume())
        panel_segments_dir = os.path.join(panel_segments_root_dir, vol_title)

        def get_srce_panel_segments_file(page_num: str) -> str:
            return os.path.join(panel_segments_dir, page_num + JSON_FILE_EXT)

        # TODO: Don't need dimensions if using prebuilt comics.
        srce_and_dest_pages, _srce_dim, required_dim = (
            get_sorted_srce_and_dest_pages_with_dimensions(
                comic,
                get_srce_panel_segments_file=get_srce_panel_segments_file,
                get_full_paths=False,
                check_srce_page_timestamps=False,
            )
        )

        page_map = OrderedDict()
        last_body_page = ""
        last_page = ""
        body_start_page_num = -1
        orig_page_num = 0

        for srce_page, dest_page in zip(
            srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages
        ):
            orig_page_num += 1

            # if is_title_page(srce_page):
            #     srce_page.page_filename = title_str + JPG_FILE_EXT

            if dest_page.page_type not in FRONT_MATTER_PAGES and body_start_page_num == -1:
                body_start_page_num = orig_page_num

            if body_start_page_num == -1:
                display_page_num = ROMAN_NUMERALS[orig_page_num]
            else:
                display_page_num = str(orig_page_num - body_start_page_num + 1)
                if dest_page.page_type == PageType.BODY:
                    last_body_page = display_page_num

            page_map[display_page_num] = PageInfo(
                orig_page_num - 1,
                display_page_num,
                dest_page.page_type,
                srce_page,
                dest_page,
            )

        return ComicBookPageInfo(page_map, last_body_page, last_page, required_dim)
