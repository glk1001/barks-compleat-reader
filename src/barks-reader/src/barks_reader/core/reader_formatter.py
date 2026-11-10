from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import pyphen
from barks_fantagraphics.barks_covers import COVER_BY_TITLE, get_cover_location
from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS, PaymentInfo
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    COVERS_SET,
    ONE_PAGERS,
    get_one_pager_fanta_page,
)
from barks_fantagraphics.comic_issues import ISSUE_NAME, SHORT_ISSUE_NAME, Issues
from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_FILE
from barks_fantagraphics.comics_utils import (
    get_formatted_first_published_str,
    get_long_formatted_submitted_date,
    get_short_formatted_first_published_str,
    get_short_submitted_day_and_month,
)
from barks_fantagraphics.fanta_comics_info import FAN, FANTA_SOURCE_COMICS, FantaComicBookInfo
from barks_fantagraphics.speech_markup import escape_markup, transform_lettering_only
from comic_utils.cpi_calculator import get_adjusted_usd, get_latest_year

from .hyphen_break_engine import HYPHEN_CHARS, NO_BREAK_CHARS, SOFT_HYPHEN
from .reader_consts_and_types import ARTICLE_TITLE_TEXTS, CLOSE_TO_ZERO
from .reader_utils import get_concat_page_nums_str

if TYPE_CHECKING:
    from collections.abc import Iterable

    from barks_fantagraphics.comic_book_info import ComicBookInfo

    from .reader_colors import Color


def escape_kivy_markup(text: str) -> str:
    """Escape `&`, `[`, `]` for Kivy markup. Matches `kivy.utils.escape_markup`.

    The comic text's `escape_markup`, which escapes byte for byte as the OKF renderer
    does (a property test holds the two together), so text matched against
    okf-rendered cells (the wiki table rewriter) is escaped exactly as the cells were.
    """
    return escape_markup(text)


LONG_TITLE_SPLITS = {
    Titles.DONALD_DUCK_FINDS_PIRATE_GOLD: "Donald Duck\nFinds Pirate Gold",
    Titles.DONALD_DUCK_AND_THE_MUMMYS_RING: "The Mummy's Ring",
    Titles.LOST_CROWN_OF_GENGHIS_KHAN_THE: "The Lost Crown of Genghis\nKhan!",
    Titles.TWENTY_FOUR_CARAT_MOON_THE: "The Twenty-four Carat\nMoon",
    Titles.DAY_THE_FARM_STOOD_STILL_THE: "The Day the Farm Stood\nStill",
    Titles.MANY_FACES_OF_MAGICA_DE_SPELL_THE: "The Many Faces of Magica\nDe Spell",
    Titles.CASE_OF_THE_STICKY_MONEY_THE: "The Case of the Sticky\nMoney!",
    Titles.DAY_THE_MOUNTAIN_SHOOK_THE: "The Day the Mountain\nShook",
}

# Pass a concrete dictionary file path rather than lang="en_US". pyphen's lang lookup
# goes through importlib.resources.files(), which under a compiled (Nuitka) build returns
# an unhashable resource object that pyphen then uses as a dict key (TypeError). Building
# the path from pyphen.__file__ yields a real, hashable Path in both dev and the standalone
# build, where pyphen's bundled dictionaries sit alongside the package.
_PYPHEN_DICT_FILE = Path(pyphen.__file__).parent / "dictionaries" / "hyph_en_US.dic"
PYPHEN_DICT = pyphen.Pyphen(filename=str(_PYPHEN_DICT_FILE))
# Non-greedy: the first bold run, not everything from the first [b] to the last [/b].
BOLD_TAG_PATTERN = re.compile(r"\[b](.*?)\[/b]")
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


# Pyphen counts every character as a letter, so its two-letter minimum is miscounted beside
# punctuation or a hyphen ("al-l.", "ful-l-dress"). It sees only a word's letters: an inner
# apostrophe stays with them ("could-n't"), a possessive "'s" does not ("Bark-s's").
_LETTER = r"[^\W\d_]"
_LETTER_RUN = re.compile(rf"{_LETTER}+(?:['\u2019](?!s\b){_LETTER}+)*")

# A word's own hyphen or dash is its natural break, with two letters on each side:
# "full-dress" and "time\u2014so" break there, "e-mail" and "10-page" do not.
_TWO_LETTERS = rf"{_LETTER}['\u2019]?{_LETTER}"
_HYPHEN_CLASS = "".join(re.escape(char) for char in HYPHEN_CHARS)
_OWN_HYPHEN = re.compile(rf"({_TWO_LETTERS}[{_HYPHEN_CLASS}])(?={_TWO_LETTERS})")


def _hyphenate_word(word: str) -> str:
    return _LETTER_RUN.sub(
        lambda run: PYPHEN_DICT.inserted(run[0], hyphen=SOFT_HYPHEN),
        _OWN_HYPHEN.sub(rf"\g<1>{SOFT_HYPHEN}", word),
    )


def hyphenate_text(text: str) -> str:
    """Mark hyphenation points in text with soft hyphens (U+00AD).

    The markers are invisible break hints only: the UI layer
    (``barks_reader.ui.hyphen_label.HyphenatingLabel``) decides where lines actually
    break and renders a real hyphen at exactly those points. Tokens containing Kivy
    markup characters or newlines are passed through unmarked so a marker can never
    land inside a markup tag or a paragraph break.
    """
    return " ".join(
        word if any(c in word for c in NO_BREAK_CHARS) else _hyphenate_word(word)
        for word in text.split(" ")
    )


def get_bold_markup_text(text: str) -> str:
    """Return ``text`` in Kivy bold markup."""
    return f"[b]{text}[/b]"


def get_markup_text_with_num_titles(text: str, num_titles: int) -> str:
    """Return ``text`` in bold with its title count after it, in brackets and italics."""
    return get_markup_text_with_extra(text, str(num_titles))


def get_markup_text_with_extra(text: str, extra: str) -> str:
    """Return ``text`` in bold with ``extra`` after it, in brackets and italics."""
    return f"[b]{text}[/b] [i]({extra})[/i]"


def get_clean_text_without_extra(markup_text: str) -> str:
    """Return a node's name: its text's first bold run, or the text when none is bold."""
    match = BOLD_TAG_PATTERN.search(markup_text)
    if match:
        return match.group(1)

    return markup_text


def get_text_with_markup_stripped(text: str) -> str:
    """Return ``text`` without its Kivy markup tags."""
    return MARKUP_TAG_PATTERN.sub("", text)


def get_action_bar_title(font_manager: FontManagerProtocol, title: str, subtitle: str = "") -> str:
    """Return ``title`` as an action bar shows it: in the Carl Barks font, at title size.

    Args:
        font_manager: Where the bar's title size comes from.
        title: The bar's title.
        subtitle: A second line under the title, in the bar's own font and italics:
            the assigned name of a comic that goes by its issue. "" for no second line.

    Returns:
        The title, in Kivy markup.

    """
    bar_title = (
        f"[font={CARL_BARKS_FONT_FILE}][size={int(font_manager.app_title_font_size)}]{title}"
    )
    if not subtitle:
        return bar_title

    return f"{bar_title}[/size][/font]\n[i]{escape_kivy_markup(subtitle)}[/i]"


def get_comic_display_title(comic_book_info: ComicBookInfo) -> str:
    """Return the name a comic goes by, on the reader's bar and the title page alike.

    Args:
        comic_book_info: The comic to name.

    Returns:
        An article's name as on its tree node (an article is a non-Barks title, which the
        issue would otherwise name), a Barks title itself, else the issue's name.

    """
    if (article_text := ARTICLE_TITLE_TEXTS.get(comic_book_info.title)) is not None:
        return article_text
    if comic_book_info.is_barks_title:
        return comic_book_info.get_title_str()
    return comic_book_info.get_title_from_issue_name()


def get_comic_display_subtitle(comic_book_info: ComicBookInfo) -> str:
    """Return the assigned name shown under a comic that goes by its issue, else "".

    Long-time readers know an untitled story by its issue, so the issue stays the
    heading (``get_comic_display_title``); the name later given to it goes under that,
    in parentheses, for everyone who does not.

    Args:
        comic_book_info: The comic to name.

    Returns:
        The parenthesised name of a story Barks left untitled; "" for a title of his
        own, and for a one-pager, a cover and an article, which have headings of
        their own.

    """
    title = comic_book_info.title
    if (
        comic_book_info.is_barks_title
        or title in ONE_PAGERS
        or title in COVERS_SET
        or title in ARTICLE_TITLE_TEXTS
    ):
        return ""
    return comic_book_info.get_display_title()


def get_display_title_str(title: Titles | None) -> str:
    """Return a title as a caption shows it.

    Args:
        title: The title to show, or None for no title.

    Returns:
        A title Barks gave as it is, any other in parentheses, and "" for no title.

    """
    return "" if title is None else BARKS_TITLE_INFO[title].get_display_title()


def get_formatted_color(color: Color) -> str:
    """Return ``color`` as a bracketed list of its channels, two decimals each."""
    color_strings = [f"{c:04.2f}" for c in color]
    return f"({', '.join(color_strings)})"


def get_formatted_payment_info(payment_info: PaymentInfo) -> str:
    """Return a payment and its worth in the CPI table's latest year, e.g. "$100 ($1300 in 2026)".

    The year shown is the year the amount is converted to, not today's: the table lags
    the calendar until it is next updated.
    """
    to_year = get_latest_year()
    cpi_adjusted_payment = get_adjusted_usd(
        payment_info.payment, payment_info.accepted_year, to_year
    )

    return f"${payment_info.payment:.0f} (${cpi_adjusted_payment:.0f} in {to_year})"


class ReaderFormatter:
    def __init__(self, font_manager: FontManagerProtocol) -> None:
        self._font_manager = font_manager

        # Use a custom issue_name here to display slightly shorter names.
        self._title_info_issue_name = ISSUE_NAME.copy()
        self._title_info_issue_name[Issues.CS] = "Comics & Stories"
        self._title_info_issue_name[Issues.MC] = "March of Comics"
        self._title_info_issue_name[Issues.USGTD] = (
            f"{SHORT_ISSUE_NAME[Issues.US]} Goes to Disneyland"
        )
        self._title_info_issue_name[Issues.HDL] = (
            f"{SHORT_ISSUE_NAME[Issues.HDL]} Junior Woodchucks"
        )

    @staticmethod
    def get_main_title(title_str: str, add_footnote: bool) -> str:
        """Return the bottom title view's title, with a footnote star if asked for."""
        if not add_footnote:
            return title_str

        return title_str + "[sup]*[/sup]"

    @staticmethod
    def get_issue_info(
        fanta_info: FantaComicBookInfo, add_footnote: bool, sup_font_size: int, color: str
    ) -> str:
        """Return a tree node's issue line: first issue and submitted date, in italics.

        Args:
            fanta_info: The title.
            add_footnote: End the line with a footnote star.
            sup_font_size: The footnote star's font size.
            color: The submitted year's colour, as Kivy markup takes it.

        Returns:
            The line, in Kivy markup.

        """
        first_published = get_short_formatted_first_published_str(fanta_info.comic_book_info)
        submitted_date = ReaderFormatter.get_formatted_submitted_str(
            fanta_info.comic_book_info, color
        )

        issue_info = first_published + submitted_date

        if not add_footnote:
            return f"[i]{issue_info}[/i]"

        return f"[i]{issue_info}[size={sup_font_size}][sup]*[/sup][/size][/i]"

    @staticmethod
    def get_formatted_submitted_str(comic_book_info: ComicBookInfo, color: str) -> str:
        """Return " [day month year]" with the year in ``color``, or "" with no submitted date."""
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
        """Return the title info box's lines: first issue, submitted, payslip and source.

        Args:
            fanta_info: The title.
            max_len_before_shorten: The first-issue text's length past which its month
                is abbreviated; 0 never abbreviates it.
            add_footnote: End the first-issue text with a footnote star.

        Returns:
            The lines, in Kivy markup; the payslip line only when Barks was paid for it.

        """
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

        # The spaces after each label line the values up in the info box's font.
        lines = [
            f"[i]1st Issue:[/i]   [b]{issue_info}[/b]",
            f"[i]Submitted:[/i] [b]{submitted_info}[/b]",
        ]
        if payment_info and payment_info.payment >= CLOSE_TO_ZERO:
            lines.append(f"[i]Payslip:[/i]      [b]{get_formatted_payment_info(payment_info)}[/b]")
        lines.append(f"[i]Source:[/i]       [b]{source}[/b]")
        return "\n".join(lines)

    @staticmethod
    def get_title_extra_info(fanta_info: FantaComicBookInfo) -> str:
        """Return the title's extra-info note, hyphenated for display, or "" with none."""
        title = fanta_info.comic_book_info.title
        if title not in BARKS_EXTRA_INFO:
            return ""

        return hyphenate_text(escape_editorial_brackets(BARKS_EXTRA_INFO[title]))


# A highlight is a whole word: not preceded or followed by a letter or digit, by a soft
# hyphen (one word hyphenated for display), or by an apostrophe or hyphen that joins
# another word to it (DUCK'S, SUPER-DUCK), as the index keeps those as one word.
_WORD_START = r"(?<![\w\xad])(?<!\w['\u2019-])"
_WORD_END = r"(?![\w\xad])(?!['\u2019-]\w)"


def _term_pattern(term: str) -> str:
    r"""Return the regex matching one term, a word or several, as the lettering breaks it.

    The target text is hyphenated for display, so a term may be broken in three ways:
    spaces between words may become newlines (\n) or soft hyphen + newline (­\n); a
    single word may be hyphenated *internally* at a soft hyphen, optionally followed by a
    newline (e.g. "Moneytubs" stored as "Money­tubs" / "Money­\ntubs"); and a
    compound with a real hyphen may be broken at that hyphen ("never-never" lettered as
    "NEVER-\nNEVER").
    """
    # Within a word, a hyphenation break may sit between any two characters: a soft
    # hyphen (\xad == ­), optionally followed by a newline where the line wrapped.
    # Only soft-hyphen breaks are allowed inside a word (never a bare space/newline), so
    # a match can't span a real word boundary. Each character is escaped so regex
    # metacharacters ('?', '.', '(', ...) are matched literally.
    intra_word_break = r"(?:\xad\n?)?"
    # A real hyphen in the term may be where the letterer broke the line.
    word_patterns = [
        intra_word_break.join(re.escape(ch) + (r"\n?" if ch == "-" else "") for ch in word)
        for word in term.split()
    ]
    # Between words: a space, a newline, or a soft hyphen followed by a newline.
    separator_pattern = r"(?: |\n|\xad\n)"
    return separator_pattern.join(word_patterns)


def mark_terms_in_text(terms: Iterable[str], target_text: str, start_tag: str, end_tag: str) -> str:
    """Wrap every whole-word occurrence of any of `terms` in start...end tags.

    One pass, the longest term tried first, so "ducking" is marked whole rather
    than its "duck", "gold mine" rather than its "gold", and no mark ever sits
    inside another. Case is ignored, and a term matches however the lettering is
    hyphenated or wrapped (see `_term_pattern`).

    Only the comic's own lettering is searched. The target may carry emphasis
    markup ("[b]SHARP[/b]") and escape sequences ("&amp;"), and substituting over
    the whole string reaches inside them: searching for "b" would wrap the b in
    "[b]", and "amp" the amp in "&amp;", each producing a tag Kivy cannot parse --
    so the reader would show broken text instead of the line. The cost is that a
    term cannot match across a tag, so "really sharp" against "REALLY [b]SHARP[/b]"
    is simply not highlighted. A missed highlight is visible and harmless; a
    mangled tag is neither.

    Args:
        terms: The words or phrases to mark.
        target_text: A bubble's lettering, possibly with markup.
        start_tag: Put before each occurrence.
        end_tag: Put after each occurrence.

    Returns:
        The text with each occurrence marked; unchanged when `terms` has no words.

    """
    unique = dict.fromkeys(" ".join(t.split()).lower() for t in terms if t.split())
    if not unique:
        return target_text
    patterns = [_term_pattern(t) for t in sorted(unique, key=len, reverse=True)]
    regex = re.compile(f"{_WORD_START}(?:{'|'.join(patterns)}){_WORD_END}", re.IGNORECASE)
    return transform_lettering_only(
        target_text,
        lambda segment: regex.sub(lambda m: f"{start_tag}{m.group(0)}{end_tag}", segment),
    )


TITLE_PAGE_NUM_SEPARATOR_STR = ", "
LEN_PAGE_NUM_SEPARATOR_STR = len(TITLE_PAGE_NUM_SEPARATOR_STR)


def get_fitted_title_with_page_nums(
    title_str: str, page_nums: list[str], max_title_with_pages_len: int
) -> tuple[str, str]:
    """Return a story's first page and its row, "Title, 3,5-7", fitted to a length.

    The row is shortened in steps: a leading "A" or "The" dropped when that is enough,
    then a long page list cut to its first page, then the title shortened.

    Args:
        title_str: The story's title.
        page_nums: The pages, as the comic numbers them.
        max_title_with_pages_len: The longest the row may be.

    Returns:
        The first page ("" when there are none) and the row (the title alone then).

    """
    if not page_nums:
        return "", _shortened_title(title_str, max_title_with_pages_len)

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
            title_str = _shortened_title(title_str, max_title_len)

    return page_nums[0], title_str + TITLE_PAGE_NUM_SEPARATOR_STR + page_nums_str


_TITLE_SHORTENED_PLACEHOLDER = "..."


def _shortened_title(title_str: str, max_len: int) -> str:
    if len(title_str) <= max_len:
        return title_str
    # textwrap.shorten refuses a width narrower than its placeholder: cut it bare.
    if max_len < len(_TITLE_SHORTENED_PLACEHOLDER):
        return title_str[: max(max_len, 0)]
    return textwrap.shorten(title_str, width=max_len, placeholder=_TITLE_SHORTENED_PLACEHOLDER)
