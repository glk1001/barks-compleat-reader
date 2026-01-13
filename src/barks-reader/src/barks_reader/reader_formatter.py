# ruff: noqa: ERA001
from __future__ import annotations

import re
import textwrap
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS, PaymentInfo
from barks_fantagraphics.barks_titles import ComicBookInfo, Titles
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_FILE
from barks_fantagraphics.comics_utils import (
    get_formatted_first_published_str,
    get_long_formatted_submitted_date,
    get_short_formatted_first_published_str,
    get_short_submitted_day_and_month,
)
from barks_fantagraphics.fanta_comics_info import FAN, FANTA_SOURCE_COMICS, FantaComicBookInfo
from comic_utils.cpi_wrapper import inflate
from kivy.utils import escape_markup

from barks_reader.reader_consts_and_types import CLOSE_TO_ZERO
from barks_reader.reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from barks_reader.font_manager import FontManager
    from barks_reader.reader_colors import Color

LONG_TITLE_SPLITS = {
    Titles.DONALD_DUCK_FINDS_PIRATE_GOLD: "Donald Duck\nFinds Pirate Gold",
    Titles.DONALD_DUCK_AND_THE_MUMMYS_RING: "The Mummy's Ring",
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


def get_text_with_markup_stripped(text: str) -> str:
    return text.replace("[b]", "").replace("[/b]", "").replace("[i]", "").replace("[/i]", "")


def text_includes_num_titles(text: str) -> bool:
    return text.endswith(")[/i]")


def get_action_bar_title(font_manager: FontManager, title: str) -> str:
    return f"[font={CARL_BARKS_FONT_FILE}][size={int(font_manager.app_title_font_size)}]{title}"


def get_formatted_color(color: Color) -> str:
    color_strings = [f"{c:04.2f}" for c in color]
    return f"({', '.join(color_strings)})"


def get_formatted_payment_info(payment_info: PaymentInfo) -> str:
    current_year = datetime.now(UTC).year
    cpi_adjusted_payment = inflate(payment_info.payment, payment_info.accepted_year)
    if cpi_adjusted_payment < 0:
        return "CPI calculator is not available"

    return (
        f"${payment_info.payment:.0f} (${cpi_adjusted_payment:.0f} in {current_year})"
        #        f" ({get_formatted_day(payment_info.accepted_day)}"
        #        f" {MONTH_AS_SHORT_STR[payment_info.accepted_month]}"
        #        f" {payment_info.accepted_year})"
    )


class ReaderFormatter:
    def __init__(self, font_manager: FontManager) -> None:
        self._font_manager = font_manager

        # Use a custom issue_name here to display slightly shorter names.
        self._title_info_issue_name = ISSUE_NAME.copy()
        self._title_info_issue_name[Issues.CS] = "Comics & Stories"
        self._title_info_issue_name[Issues.MC] = "March of Comics"
        self._title_info_issue_name[Issues.USGTD] = "US Goes to Disneyland"
        self._title_info_issue_name[Issues.HDL] = "HDL Junior Woodchucks"

    @staticmethod
    def get_main_title(title_str: str, add_footnote: bool) -> str:
        if not add_footnote:
            return title_str

        return title_str + "[sup]*[/sup]"

    @staticmethod
    def get_issue_info(
        fanta_info: FantaComicBookInfo, add_footnote: bool, sup_font_size: int, color: str
    ) -> str:
        first_published = get_short_formatted_first_published_str(fanta_info.comic_book_info)
        # noinspection LongLine,PyUnresolvedReferences
        submitted_date = __class__.get_formatted_submitted_str(fanta_info.comic_book_info, color)  # ty: ignore[unresolved-reference]

        issue_info = first_published + submitted_date

        if not add_footnote:
            return f"[i]{issue_info}[/i]"

        return f"[i]{issue_info}[size={sup_font_size}][sup]*[/sup][/i]"

    @staticmethod
    def get_formatted_submitted_str(comic_book_info: ComicBookInfo, color: str) -> str:
        left_sq_bracket = escape_markup("[")
        right_sq_bracket = escape_markup("]")

        return (
            f" {left_sq_bracket}"
            f"{get_short_submitted_day_and_month(comic_book_info)}"
            f" [b][color={color}]"
            f"{comic_book_info.submitted_year}"
            f"[/color][/b]"
            f"{right_sq_bracket}"
        )

    def get_title_info(
        self, fanta_info: FantaComicBookInfo, max_len_before_shorten: int, add_footnote: bool
    ) -> str:
        # TODO: Clean this up.
        issue_info = get_formatted_first_published_str(
            fanta_info.comic_book_info, self._title_info_issue_name, max_len_before_shorten
        )
        if add_footnote:
            sup_font_size = round(1.5 * self._font_manager.title_info_font_size)
            issue_info += f"[size={sup_font_size}][sup]*[/sup][/size]"

        submitted_info = get_long_formatted_submitted_date(fanta_info.comic_book_info)
        fanta_book = FANTA_SOURCE_COMICS[fanta_info.fantagraphics_volume]
        source = f"{FAN} CBDL, Vol {fanta_book.volume}, {fanta_book.year}"
        payment_info = BARKS_PAYMENTS.get(fanta_info.comic_book_info.title, None)

        if (not payment_info) or (payment_info.payment < CLOSE_TO_ZERO):
            return (
                f"[i]1st Issue:[/i]   [b]{issue_info}[/b]\n"
                f"[i]Submitted:[/i] [b]{submitted_info}[/b]\n"
                f"[i]Source:[/i]       [b]{source}[/b]"
            )

        return (
            f"[i]1st Issue:[/i]   [b]{issue_info}[/b]\n"
            f"[i]Submitted:[/i] [b]{submitted_info}[/b]\n"
            f"[i]Payslip:[/i]      [b]{get_formatted_payment_info(payment_info)}[/b]\n"
            f"[i]Source:[/i]       [b]{source}[/b]"
        )

    @staticmethod
    def get_title_extra_info(fanta_info: FantaComicBookInfo) -> str:
        title = fanta_info.comic_book_info.title
        if title not in BARKS_EXTRA_INFO:
            return ""

        return f"{BARKS_EXTRA_INFO[title]}"


def mark_phrase_in_text(phrase: str, target_text: str, start_tag: str, end_tag: str) -> str:
    r"""Find and tag a phrase in a target string.

    Spaces in the phrase might be replaced by newlines (\n) or soft hyphens + newlines
    (\u00ad\n) and this function will wrap the found phrase in start...end tags.
    """
    # 1. Split the original phrase into a list of words
    #    (split() handles multiple spaces automatically)
    words = phrase.split()

    # 2. Escape words to ensure characters like '?', '.', or '(' don't break the regex
    escaped_words = [re.escape(w) for w in words]

    # 3. Create a regex pattern for the separator.
    #    It matches: A literal space OR a newline OR a soft hyphen followed by newline.
    #    (?: ...) is a non-capturing group.
    #    \xad is the hexadecimal representation of \u00AD.
    separator_pattern = r"(?: |\n|\xad\n)"

    # 4. Join the words with the flexible separator
    full_pattern = separator_pattern.join(escaped_words)

    # 5. Perform the substitution.
    #    We wrap full_pattern in parentheses (...) to create a capturing group.
    #    We replace it with 'start_tag\1end_tag', where \1 puts back exactly what was found.
    result = re.sub(
        f"({full_pattern})", rf"{start_tag}\1{end_tag}", target_text, flags=re.IGNORECASE
    )

    return result  # noqa: RET504


TITLE_PAGE_NUM_SEPERATOR_STR = ", "
LEN_PAGE_NUM_SEPERATOR_STR = len(TITLE_PAGE_NUM_SEPERATOR_STR)


def get_fitted_title_with_page_nums(
    title_str: str, page_nums: list[str], max_title_with_pages_len: int
) -> tuple[str, str]:
    len_title = len(title_str)

    page_nums_str = get_concat_page_nums_str(page_nums)
    len_page_nums = len(page_nums_str)

    len_title_and_page_nums = len_title + len_page_nums + LEN_PAGE_NUM_SEPERATOR_STR

    # Shorten the title plus page number list if it's too long.
    # Start with easy title shortening.
    excess_len = max_title_with_pages_len - len_title_and_page_nums
    if excess_len < 0:
        excess_len = -excess_len
        if (excess_len <= 2) and title_str.startswith("A "):  # noqa: PLR2004
            title_str = title_str[2:]
        elif (excess_len <= 4) and title_str.startswith("The "):  # noqa: PLR2004
            title_str = title_str[4:]

    page_nums_str = get_concat_page_nums_str(page_nums)

    len_title = len(title_str)
    len_title_and_page_nums = len_title + len(page_nums_str) + LEN_PAGE_NUM_SEPERATOR_STR

    # Try shortening page num string.
    # noinspection LongLine
    if (len_title_and_page_nums > max_title_with_pages_len) and (len(page_nums) > 3):  # noqa: PLR2004
        page_nums_str = page_nums[0] + ",..."
        len_title_and_page_nums = len_title + len(page_nums_str) + LEN_PAGE_NUM_SEPERATOR_STR

    if len_title_and_page_nums > max_title_with_pages_len:
        # Shorten the title.
        max_title_len = max_title_with_pages_len - len(page_nums_str)
        title_str = textwrap.shorten(title_str, width=max_title_len, placeholder="...")

    return page_nums[0], title_str + TITLE_PAGE_NUM_SEPERATOR_STR + page_nums_str
