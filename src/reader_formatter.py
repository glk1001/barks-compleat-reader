import re

from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_fantagraphics.comics_utils import (
    get_formatted_first_published_str,
    get_long_formatted_submitted_date,
)
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo, FANTA_SOURCE_COMICS, FAN
from reader_utils import get_formatted_payment_info

LONG_TITLE_SPLITS = {
    Titles.LOST_CROWN_OF_GENGHIS_KHAN_THE: "The Lost Crown\nof Genghis Khan!",
}


def get_bold_markup_text(text: str) -> str:
    return f"[b]{text}[/b]"


def get_markup_text_with_num_titles(text: str, num_titles: int) -> str:
    return get_markup_text_with_extra(text, str(num_titles))


def get_markup_text_with_extra(text: str, extra: str) -> str:
    return f"[b]{text}[/b] [i]({extra})[/i]"


def get_clean_text_without_extra(markup_text: str) -> str:
    match = re.search(r"\[b](.*)\[/b]", markup_text)
    if match:
        return match.group(1)

    return markup_text


def text_includes_num_titles(text: str) -> bool:
    return text.endswith(")[/i]")


class ReaderFormatter:
    def __init__(self):
        # Use a custom issue_name here to display slightly shorter names.
        self._title_info_issue_name = ISSUE_NAME.copy()
        self._title_info_issue_name[Issues.CS] = "Comics & Stories"
        self._title_info_issue_name[Issues.MC] = "March of Comics"
        self._title_info_issue_name[Issues.USGTD] = "US Goes to Disneyland"

    def get_title_info(self, fanta_info: FantaComicBookInfo, max_len_before_shorten: int) -> str:
        # TODO: Clean this up.
        issue_info = get_formatted_first_published_str(
            fanta_info.comic_book_info, self._title_info_issue_name, max_len_before_shorten
        )
        payment_info = get_formatted_payment_info(BARKS_PAYMENTS[fanta_info.comic_book_info.title])
        submitted_info = get_long_formatted_submitted_date(fanta_info.comic_book_info)
        fanta_book = FANTA_SOURCE_COMICS[fanta_info.fantagraphics_volume]
        source = f"{FAN} CBDL, Vol {fanta_book.volume}, {fanta_book.year}"

        return (
            f"[i]1st Issue:[/i]   [b]{issue_info}[/b]\n"
            f"[i]Submitted:[/i] [b]{submitted_info}[/b]\n"
            f"[i]Payslip:[/i]      [b]{payment_info}[/b]\n"
            f"[i]Source:[/i]       [b]{source}[/b]"
        )

    @staticmethod
    def get_title_extra_info(fanta_info: FantaComicBookInfo) -> str:
        title = fanta_info.comic_book_info.title
        if title not in BARKS_EXTRA_INFO:
            return ""

        return f"{BARKS_EXTRA_INFO[title]}"
