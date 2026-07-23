from __future__ import annotations

import re
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pyphen
from barks_fantagraphics.barks_covers import COVER_BY_TITLE, get_cover_location
from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS, PaymentInfo
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS, get_one_pager_fanta_page
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_FILE
from barks_fantagraphics.comics_utils import (
    get_formatted_first_published_str,
    get_long_formatted_submitted_date,
    get_short_formatted_first_published_str,
    get_short_submitted_day_and_month,
)
from barks_fantagraphics.fanta_comics_info import FAN, FANTA_SOURCE_COMICS, FantaComicBookInfo
from comic_utils.cpi_calculator import get_adjusted_usd

from .hyphen_break_engine import NO_BREAK_CHARS, SOFT_HYPHEN
from .reader_consts_and_types import CLOSE_TO_ZERO
from .reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from barks_fantagraphics.comic_book_info import ComicBookInfo

    from .reader_colors import Color


def escape_kivy_markup(text: str) -> str:
    """Escape `&`, `[`, `]` for Kivy markup. Matches `kivy.utils.escape_markup`.

    Also byte-identical to ``okf_reader.core.render._esc`` — consumers matching
    okf-escaped text (e.g. the wiki table rewriter) rely on that parity.
    """
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


LONG_TITLE_SPLITS = {
    Titles.DONALD_DUCK_FINDS_PIRATE_GOLD: "Donald Duck\nFinds Pirate Gold",
    Titles.DONALD_DUCK_AND_THE_MUMMYS_RING: "The Mummy's Ring",
    Titles.LOST_CROWN_OF_GENGHIS_KHAN_THE: "The Lost Crown\nof Genghis Khan!",
}

# Pass a concrete dictionary file path rather than lang="en_US". pyphen's lang lookup
# goes through importlib.resources.files(), which under a compiled (Nuitka) build returns
# an unhashable resource object that pyphen then uses as a dict key (TypeError). Building
# the path from pyphen.__file__ yields a real, hashable Path in both dev and the standalone
# build, where pyphen's bundled dictionaries sit alongside the package.
_PYPHEN_DICT_FILE = Path(pyphen.__file__).parent / "dictionaries" / "hyph_en_US.dic"
PYPHEN_DICT = pyphen.Pyphen(filename=str(_PYPHEN_DICT_FILE))
BOLD_TAG_PATTERN = re.compile(r"\[b](.*)\[/b]")
MARKUP_TAG_PATTERN = re.compile(r"\[/?[^]]+]")

# The only real Kivy markup tags in BARKS_EXTRA_INFO; every other square-bracket run
# is literal editorial text (e.g. "[actually, ...]").
_KIVY_MARKUP_TAG = re.compile(r"\[/?[bi]]")


def escape_editorial_brackets(text: str) -> str:
    """Escape literal square brackets that are not Kivy ``[b]``/``[i]`` markup.

    ``BARKS_EXTRA_INFO`` mixes real markup with literal editorial brackets like
    ``[actually, ...]``. Kivy renders an unknown bracket run literally, which is fine
    alone — but the ``[ref]`` tags the hyphenation layer injects (see
    ``barks_reader.ui.hyphen_label``) get swallowed by an unclosed literal bracket
    under Kivy's non-greedy tag parsing. Converting literal brackets to ``&bl;``/``&br;``
    entities keeps them visible while leaving ``[b]``/``[i]``/``[ref]`` intact.
    """
    parts: list[str] = []
    last = 0
    for match in _KIVY_MARKUP_TAG.finditer(text):
        parts.append(text[last : match.start()].replace("[", "&bl;").replace("]", "&br;"))
        parts.append(match.group())
        last = match.end()
    parts.append(text[last:].replace("[", "&bl;").replace("]", "&br;"))
    return "".join(parts)


class FontManagerProtocol(Protocol):
    app_title_font_size: int | float
    title_info_font_size: int | float


def hyphenate_text(text: str) -> str:
    """Mark hyphenation points in text with soft hyphens (U+00AD).

    The markers are invisible break hints only: the UI layer
    (``barks_reader.ui.hyphen_label.HyphenatingLabel``) decides where lines actually
    break and renders a real hyphen at exactly those points. Tokens containing Kivy
    markup characters or newlines are passed through unmarked so a marker can never
    land inside a markup tag or a paragraph break.
    """
    return " ".join(
        word
        if any(c in word for c in NO_BREAK_CHARS)
        else PYPHEN_DICT.inserted(word, hyphen=SOFT_HYPHEN)
        for word in text.split(" ")
    )


def get_bold_markup_text(text: str) -> str:
    return f"[b]{text}[/b]"


def get_markup_text_with_num_titles(text: str, num_titles: int) -> str:
    return get_markup_text_with_extra(text, str(num_titles))


def get_markup_text_with_extra(text: str, extra: str) -> str:
    return f"[b]{text}[/b] [i]({extra})[/i]"


def get_clean_text_without_extra(markup_text: str) -> str:
    match = BOLD_TAG_PATTERN.search(markup_text)
    if match:
        return match.group(1)

    return markup_text


def get_text_with_markup_stripped(text: str) -> str:
    return MARKUP_TAG_PATTERN.sub("", text)


def text_includes_num_titles(text: str) -> bool:
    return text.endswith(")[/i]")


def get_action_bar_title(font_manager: FontManagerProtocol, title: str) -> str:
    return f"[font={CARL_BARKS_FONT_FILE}][size={int(font_manager.app_title_font_size)}]{title}"


def get_formatted_color(color: Color) -> str:
    color_strings = [f"{c:04.2f}" for c in color]
    return f"({', '.join(color_strings)})"


def get_formatted_payment_info(payment_info: PaymentInfo) -> str:
    current_year = datetime.now(UTC).year
    cpi_adjusted_payment = get_adjusted_usd(payment_info.payment, payment_info.accepted_year)

    return f"${payment_info.payment:.0f} (${cpi_adjusted_payment:.0f} in {current_year})"


class ReaderFormatter:
    def __init__(self, font_manager: FontManagerProtocol) -> None:
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
        submitted_date = ReaderFormatter.get_formatted_submitted_str(
            fanta_info.comic_book_info, color
        )

        issue_info = first_published + submitted_date

        if not add_footnote:
            return f"[i]{issue_info}[/i]"

        return f"[i]{issue_info}[size={sup_font_size}][sup]*[/sup][/i]"

    @staticmethod
    def get_formatted_submitted_str(comic_book_info: ComicBookInfo, color: str) -> str:
        if comic_book_info.submitted_month == -1:
            # No recorded submitted date (e.g. some covers) - omit the bracket.
            return ""

        left_sq_bracket = escape_kivy_markup("[")
        right_sq_bracket = escape_kivy_markup("]")

        # The year is not bolded: the story title is the row's emphasis, not the date.
        return (
            f" {left_sq_bracket}"
            f"{get_short_submitted_day_and_month(comic_book_info)}"
            f" [color={color}]"
            f"{comic_book_info.submitted_year}"
            f"[/color]"
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
        title = fanta_info.comic_book_info.title
        source = f"{FAN} CBDL, Vol {fanta_book.volume}, {fanta_book.year}"
        fanta_page = get_one_pager_fanta_page(title) if title in ONE_PAGERS else None
        if fanta_page is None and title in COVERS_SET:
            cover_location = get_cover_location(COVER_BY_TITLE[title])
            fanta_page = None if cover_location is None else cover_location[1]
        if fanta_page is not None:
            # One-pagers and covers also show the page within the Fantagraphics volume.
            source += f", p. {fanta_page}"
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

        return hyphenate_text(escape_editorial_brackets(BARKS_EXTRA_INFO[title]))


def mark_phrase_in_text(phrase: str, target_text: str, start_tag: str, end_tag: str) -> str:
    r"""Find and tag a phrase in a target string.

    The target text is hyphenated for display, so the phrase may be broken in two ways:
    spaces between words may become newlines (\n) or soft hyphen + newline (\u00AD\n), and
    a single word may be hyphenated *internally* at a soft hyphen, optionally followed by a
    newline (e.g. "Moneytubs" stored as "Money\u00ADtubs" / "Money\u00AD\ntubs"). This
    function tolerates both and wraps the found phrase in start...end tags.
    """
    # 1. Split the original phrase into a list of words
    #    (split() handles multiple spaces automatically)
    words = phrase.split()

    # 2. Within a word, a hyphenation break may sit between any two characters: a soft
    #    hyphen (\xad == \u00AD), optionally followed by a newline where the line wrapped.
    #    Only soft-hyphen breaks are allowed inside a word (never a bare space/newline), so
    #    a match can't span a real word boundary. Each character is escaped so regex
    #    metacharacters ('?', '.', '(', ...) are matched literally.
    intra_word_break = r"(?:\xad\n?)?"
    word_patterns = [intra_word_break.join(re.escape(ch) for ch in word) for word in words]

    # 3. Create a regex pattern for the between-word separator.
    #    It matches: A literal space OR a newline OR a soft hyphen followed by newline.
    #    (?: ...) is a non-capturing group.
    separator_pattern = r"(?: |\n|\xad\n)"

    # 4. Join the per-word patterns with the flexible separator
    full_pattern = separator_pattern.join(word_patterns)

    # 5. Perform the substitution.
    #    We wrap full_pattern in parentheses (...) to create a capturing group.
    #    We replace it with 'start_tag\1end_tag', where \1 puts back exactly what was found.
    result = re.sub(
        f"({full_pattern})", rf"{start_tag}\1{end_tag}", target_text, flags=re.IGNORECASE
    )

    return result  # noqa: RET504


TITLE_PAGE_NUM_SEPARATOR_STR = ", "
LEN_PAGE_NUM_SEPARATOR_STR = len(TITLE_PAGE_NUM_SEPARATOR_STR)


def get_fitted_title_with_page_nums(
    title_str: str, page_nums: list[str], max_title_with_pages_len: int
) -> tuple[str, str]:
    page_nums_str = get_concat_page_nums_str(page_nums)
    len_combined = len(title_str) + len(page_nums_str) + LEN_PAGE_NUM_SEPARATOR_STR

    # Shorten the title plus page number list if it's too long.
    # Start with easy title shortening.
    if len_combined > max_title_with_pages_len:
        excess_len = len_combined - max_title_with_pages_len
        if (excess_len <= 2) and title_str.startswith("A "):  # noqa: PLR2004
            title_str = title_str[2:]
            len_combined -= 2
        elif (excess_len <= 4) and title_str.startswith("The "):  # noqa: PLR2004
            title_str = title_str[4:]
            len_combined -= 4

    # Try shortening page num string.
    if (len_combined > max_title_with_pages_len) and (len(page_nums) > 3):  # noqa: PLR2004
        page_nums_str = page_nums[0] + ",..."
        len_combined = len(title_str) + len(page_nums_str) + LEN_PAGE_NUM_SEPARATOR_STR

    if len_combined > max_title_with_pages_len:
        # Shorten the title.
        max_title_len = max_title_with_pages_len - len(page_nums_str) - LEN_PAGE_NUM_SEPARATOR_STR
        if max_title_len > 0:
            title_str = textwrap.shorten(title_str, width=max_title_len, placeholder="...")

    return page_nums[0], title_str + TITLE_PAGE_NUM_SEPARATOR_STR + page_nums_str
