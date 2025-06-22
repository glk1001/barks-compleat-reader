from collections import OrderedDict
from dataclasses import dataclass

from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_consts import JPG_FILE_EXT, PageType
from barks_fantagraphics.pages import (
    get_srce_and_dest_pages_in_order,
    FRONT_MATTER_PAGES,
    ROMAN_NUMERALS,
)
from reader_utils import is_title_page


@dataclass
class PageInfo:
    page_index: int
    display_page_num: str
    page_type: PageType
    srce_image_filename: str
    dest_image_filename: str


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


def get_comic_page_info(comic: ComicBook) -> ComicBookPageInfo:
    title_str = comic.get_ini_title()
    srce_and_dest_pages = get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

    page_map = OrderedDict()
    last_body_page = ""
    last_page = ""
    body_start_page_num = -1
    orig_page_num = 0

    for srce_page, dest_page in zip(srce_and_dest_pages.srce_pages, srce_and_dest_pages.dest_pages):
        orig_page_num += 1

        dest_page_filename = dest_page.page_filename

        if is_title_page(srce_page):
            srce_page_filename = title_str + JPG_FILE_EXT
        else:
            srce_page_filename = srce_page.page_filename

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
            srce_page_filename,
            dest_page_filename,
        )

    return ComicBookPageInfo(page_map, last_body_page, last_page)
