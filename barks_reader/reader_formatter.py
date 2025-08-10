# ruff: noqa: ERA001

import re
from datetime import UTC, datetime

from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS, PaymentInfo
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_NAME
from barks_fantagraphics.comics_utils import (
    get_formatted_first_published_str,
    get_long_formatted_submitted_date,
)
from barks_fantagraphics.fanta_comics_info import FAN, FANTA_SOURCE_COMICS, FantaComicBookInfo
from cpi import inflate

from barks_reader.font_manager import FontManager
from barks_reader.reader_colors import Color

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


def get_action_bar_title(font_manager: FontManager, title: str) -> str:
    return f"[font={CARL_BARKS_FONT_NAME}][size={int(font_manager.app_title_font_size)}]{title}"


def get_formatted_color(color: Color) -> str:
    color_strings = [f"{c:04.2f}" for c in color]
    return f"({', '.join(color_strings)})"


def get_formatted_payment_info(payment_info: PaymentInfo) -> str:
    current_year = datetime.now(UTC).year
    cpi_adjusted_payment = inflate(payment_info.payment, payment_info.accepted_year)

    return (
        f"${payment_info.payment:.0f} (${cpi_adjusted_payment:.0f} in {current_year})"
        #        f" ({get_formatted_day(payment_info.accepted_day)}"
        #        f" {MONTH_AS_SHORT_STR[payment_info.accepted_month]}"
        #        f" {payment_info.accepted_year})"
    )


class ReaderFormatter:
    def __init__(self) -> None:
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
