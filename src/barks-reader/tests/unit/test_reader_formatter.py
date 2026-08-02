from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_reader.core import reader_formatter
from barks_reader.core.reader_formatter import SOFT_HYPHEN


def test_hyphenate_text() -> None:
    text = "hyphenation"
    res = reader_formatter.hyphenate_text(text)
    assert SOFT_HYPHEN in res


def test_hyphenate_text_skips_markup_and_paragraph_tokens() -> None:
    text = "[i]hyphenation[/i] paragraphs\n\nhyphenation &amp; hyphenation"
    res = reader_formatter.hyphenate_text(text)
    assert SOFT_HYPHEN not in res.split(" ")[0]  # markup token untouched
    assert SOFT_HYPHEN not in res.split(" ")[1]  # newline token untouched
    assert SOFT_HYPHEN not in res.split(" ")[2]  # ampersand token untouched
    assert SOFT_HYPHEN in res.split(" ")[3]


# `escape_kivy_markup` is the inlined replacement for `kivy.utils.escape_markup`.
# Pin its behavior so a future "simplification" can't silently break Kivy text
# rendering anywhere the helper is called from.
class TestEscapeEditorialBrackets:
    def test_keeps_real_markup_tags(self) -> None:
        text = "[i]Duck Man[/i] and [b]Scrooge[/b]"
        assert reader_formatter.escape_editorial_brackets(text) == text

    def test_escapes_literal_editorial_brackets(self) -> None:
        text = "using him [actually, the second time] I established"
        assert reader_formatter.escape_editorial_brackets(text) == (
            "using him &bl;actually, the second time&br; I established"
        )

    def test_escapes_around_real_markup(self) -> None:
        text = "[i]note [aside] here[/i]"
        assert reader_formatter.escape_editorial_brackets(text) == "[i]note &bl;aside&br; here[/i]"

    def test_leaves_existing_entities_untouched(self) -> None:
        text = "the &bl;It&br; accidentally"
        assert reader_formatter.escape_editorial_brackets(text) == text


class TestEscapeKivyMarkup:
    def test_escapes_left_bracket(self) -> None:
        assert reader_formatter.escape_kivy_markup("[") == "&bl;"

    def test_escapes_right_bracket(self) -> None:
        assert reader_formatter.escape_kivy_markup("]") == "&br;"

    def test_escapes_ampersand(self) -> None:
        assert reader_formatter.escape_kivy_markup("a & b") == "a &amp; b"

    def test_escapes_ampersand_before_brackets(self) -> None:
        # If `&` weren't escaped first, the `&bl;` from the `[` escape would
        # itself get re-escaped to `&amp;bl;` — catch that ordering bug.
        assert reader_formatter.escape_kivy_markup("&[") == "&amp;&bl;"

    def test_identity_on_plain_text(self) -> None:
        assert reader_formatter.escape_kivy_markup("plain text") == "plain text"


def test_get_bold_markup_text() -> None:
    assert reader_formatter.get_bold_markup_text("foo") == "[b]foo[/b]"


def test_get_markup_text_with_num_titles() -> None:
    res = reader_formatter.get_markup_text_with_num_titles("foo", 5)
    assert res == "[b]foo[/b] [i](5)[/i]"


def test_get_markup_text_with_extra() -> None:
    res = reader_formatter.get_markup_text_with_extra("foo", "bar")
    assert res == "[b]foo[/b] [i](bar)[/i]"


def test_get_clean_text_without_extra() -> None:
    assert reader_formatter.get_clean_text_without_extra("[b]foo[/b]") == "foo"
    assert reader_formatter.get_clean_text_without_extra("foo") == "foo"

    # Test greedy matching behavior
    text = "[b]Title[/b] [i](Info)[/i]"
    assert reader_formatter.get_clean_text_without_extra(text) == "Title"


def test_get_text_with_markup_stripped() -> None:
    text = "[b]Bold[/b] and [i]Italic[/i]"
    assert reader_formatter.get_text_with_markup_stripped(text) == "Bold and Italic"

    # Complex/Nested
    text_complex = "[color=#ff0000]Red[/color] [size=20]Big[/size] [b]Bold[/b]"
    assert reader_formatter.get_text_with_markup_stripped(text_complex) == "Red Big Bold"


def test_text_includes_num_titles() -> None:
    assert reader_formatter.text_includes_num_titles("Something (5)[/i]")
    assert not reader_formatter.text_includes_num_titles("Something")


def test_get_action_bar_title() -> None:
    mock_font_manager: Any = MagicMock()
    mock_font_manager.app_title_font_size = 20.5
    # We check if the string contains expected parts since CARL_BARKS_FONT_FILE is imported
    result = reader_formatter.get_action_bar_title(mock_font_manager, "My Title")
    assert "[font=" in result
    assert "[size=20]My Title" in result


def test_get_formatted_color() -> None:
    # Assuming Color is a tuple/list of floats
    color = (0.1, 0.5, 0.9, 1.0)
    result = reader_formatter.get_formatted_color(color)
    assert result == "(0.10, 0.50, 0.90, 1.00)"


@patch.object(reader_formatter, reader_formatter.get_adjusted_usd.__name__)
@patch.object(reader_formatter, reader_formatter.datetime.__name__)
def test_get_formatted_payment_info(mock_datetime: MagicMock, mock_inflate: MagicMock) -> None:
    # Setup mocks
    mock_now = MagicMock()
    mock_now.year = 2023
    mock_datetime.now.return_value = mock_now

    mock_payment_info = MagicMock()
    mock_payment_info.payment = 100.0
    mock_payment_info.accepted_year = 1950

    # Case 1: Normal inflation
    mock_inflate.return_value = 1000.0
    result = reader_formatter.get_formatted_payment_info(mock_payment_info)
    assert result == "$100 ($1000 in 2023)"
    mock_inflate.assert_called_with(100.0, 1950)


def test_mark_phrase_in_text() -> None:
    target = "Hello Donald Duck world"
    phrase = "Donald Duck"
    res = reader_formatter.mark_phrase_in_text(phrase, target, "<b>", "</b>")
    assert res == "Hello <b>Donald Duck</b> world"

    # Test with newline in target
    target_nl = "Hello Donald\nDuck world"
    res_nl = reader_formatter.mark_phrase_in_text(phrase, target_nl, "<b>", "</b>")
    assert res_nl == "Hello <b>Donald\nDuck</b> world"

    # Test with soft hyphen
    target_sh = "Hello Donald\u00ad\nDuck world"
    res_sh = reader_formatter.mark_phrase_in_text(phrase, target_sh, "<b>", "</b>")
    assert res_sh == "Hello <b>Donald\xad\nDuck</b> world"


def test_mark_phrase_in_text_word_hyphenated_internally() -> None:
    """A single word hyphenated inside itself (soft hyphen) is still matched.

    Regression: the word "Moneytubs" stored with an internal soft hyphen (and an
    optional wrap newline) must still be highlighted.
    """
    func = reader_formatter.mark_phrase_in_text
    shy = SOFT_HYPHEN

    # Soft hyphen with a line break inside the word.
    target_break = f"aboard the S.S. Money{shy}\ntubs!"
    assert (
        func("Moneytubs", target_break, "<b>", "</b>")
        == f"aboard the S.S. <b>Money{shy}\ntubs</b>!"
    )

    # Soft hyphen without a following newline.
    target_no_nl = f"aboard the S.S. Money{shy}tubs!"
    assert (
        func("Moneytubs", target_no_nl, "<b>", "</b>") == f"aboard the S.S. <b>Money{shy}tubs</b>!"
    )

    # Case-insensitive, matching the real speech-bubble usage (upper-case text).
    target_upper = f"ABOARD THE S.S. MONEY{shy}TUBS!"
    assert (
        func("Moneytubs", target_upper, "<b>", "</b>") == f"ABOARD THE S.S. <b>MONEY{shy}TUBS</b>!"
    )


def test_mark_phrase_in_text_does_not_cross_word_boundaries() -> None:
    """Intra-word breaks are soft-hyphen only, so a match can't span a real space/newline.

    "cat one" wrapped at the space (its space became a newline) must not match "atone".
    """
    func = reader_formatter.mark_phrase_in_text
    assert func("atone", "the cat\none day", "<b>", "</b>") == "the cat\none day"


def test_mark_phrase_in_text_highlights_inside_emphasis() -> None:
    """A word that is bold in the art still gets highlighted, tags kept around it."""
    func = reader_formatter.mark_phrase_in_text
    assert func("sharp", "REALLY [b]SHARP[/b]", "<m>", "</m>") == "REALLY [b]<m>SHARP</m>[/b]"


def test_mark_phrase_in_text_never_marks_inside_markup() -> None:
    """The search must not reach into a tag or an escape sequence.

    Wrapping the "b" of "[b]" or the "amp" of "&amp;" produces a tag Kivy cannot
    parse, so the reader would show broken text instead of the line. Both are
    search terms a user could plausibly type.
    """
    func = reader_formatter.mark_phrase_in_text
    assert func("b", "REALLY [b]SHARP[/b]", "<m>", "</m>") == "REALLY [b]SHARP[/b]"
    assert func("amp", "GOLDSTEIN &amp; CO.", "<m>", "</m>") == "GOLDSTEIN &amp; CO."
    assert func("bl", "&bl;Chinese Characters&br;", "<m>", "</m>") == "&bl;Chinese Characters&br;"


def test_mark_phrase_in_text_phrase_does_not_span_a_tag() -> None:
    """The accepted cost of confining the match to lettering: a missed highlight.

    Highlighting "really sharp" across the tag would mean mapping offsets over
    the markup, which is exactly what inline markup was adopted to avoid. A
    missing highlight is visible and harmless; a mangled tag is neither.
    """
    func = reader_formatter.mark_phrase_in_text
    assert func("really sharp", "REALLY [b]SHARP[/b]", "<m>", "</m>") == "REALLY [b]SHARP[/b]"


def test_get_fitted_title_with_page_nums() -> None:
    func = reader_formatter.get_fitted_title_with_page_nums

    # Case 1: Short title, fits
    title = "Short Title"
    page_nums = ["1", "2", "3", "4", "5"]
    max_len = 100

    first_page, res_str = func(title, page_nums, max_len)
    assert first_page == "1"
    assert res_str == "Short Title, 1-5"

    # Case 2: Needs shortening by removing "A "
    # "A Title, 1-5" (len 12) vs max_len 10. Excess 2.
    title = "A Title"
    max_len = 10

    _, res_str = func(title, page_nums, max_len)
    assert res_str == "Title, 1-5"

    # Case 3: Needs shortening by removing "The "
    # "The Title, 1-5" (len 14) vs max_len 10. Excess 4.
    title = "The Title"
    max_len = 10

    _, res_str = func(title, page_nums, max_len)
    assert res_str == "Title, 1-5"

    # Case 4: Truncate title
    title = "Very Long Title Indeed"
    max_len = 10
    # Should shorten title.
    # max_title_len = 10 - 1 - 2 = 7
    # textwrap.shorten("Very Long Title Indeed", width=7, placeholder="...")  # noqa: ERA001

    _, res_str = func(title, ["1"], max_len)
    # Depending on textwrap implementation, it might return "Very..." or similar
    assert len(res_str) <= max_len
    assert res_str.endswith(", 1")

    # Case 5: Known issue
    title = "Donald Duck and the Mummy's Ring"
    max_len = 34 + 8
    page_nums = ["1", "5", "10", "32"]
    _, res_str = func(title, page_nums, max_len)
    assert len(res_str) <= max_len
    assert res_str == f"{title}, 1,..."

    # Case 6: Page num shortening triggered
    title = "My Title"
    page_nums = ["1", "2", "9", "10"]
    # "My Title, 1, 2, 3, 4" -> 8 + 2 + 10 = 20 chars.
    max_len = 15
    # Should shorten page nums to "1,..." (5 chars)
    # Combined: 8 + 2 + 5 = 15. Fits exactly.
    _, res = func(title, page_nums, max_len)
    assert res == "My Title, 1,..."

    # Case 7: Title shortening after page num shortening
    title = "Very Long Title Here"  # 20 chars
    page_nums = ["1", "2", "8", "9"]
    max_len = 15
    # Page nums shortened -> "1,..." (5).
    # Length now: 20 + 2 + 5 = 27 > 15.
    # Title shortened to fit 8 chars: "Very..."
    _, res = func(title, page_nums, max_len)
    assert res == "Very..., 1,..."


class TestGetFittedTitleWithPageNumsBoundaries:
    """The exact thresholds of the three-stage shortening, one case per boundary.

    Stages, in order: drop a leading "A "/"The " when that alone is enough, abbreviate
    a long page list to "<first>,...", then truncate the title with an ellipsis.
    """

    @staticmethod
    def _fit(title: str, page_nums: list[str], max_len: int) -> str:
        return reader_formatter.get_fitted_title_with_page_nums(title, page_nums, max_len)[1]

    def test_exact_fit_keeps_the_leading_article(self) -> None:
        """At exactly max_len nothing is over-long, so "A " must survive."""
        assert self._fit("A Title", ["1", "2", "3", "4", "5"], 12) == "A Title, 1-5"

    def test_article_trim_only_when_it_alone_would_fit(self) -> None:
        """An excess of 3 is more than "A " (2 chars) can recover, so it is not dropped."""
        assert self._fit("A Title", ["7"], 7) == "A..., 7"

    def test_the_trim_only_when_it_alone_would_fit(self) -> None:
        """Likewise an excess of 5 is more than "The " (4 chars) can recover."""
        assert self._fit("The Very Long Title", ["7"], 17) == "The Very..., 7"

    def test_three_page_nums_are_not_abbreviated(self) -> None:
        """The page list is only collapsed past three entries; three stay in full."""
        assert self._fit("Long Title Here", ["1", "5", "9"], 18) == "Long..., 1,5,9"

    def test_title_truncation_uses_the_abbreviated_page_length(self) -> None:
        """After collapsing the page list the combined length is recomputed from it."""
        assert (
            self._fit("Very Long Title Here", ["1", "2", "9", "10"], 25)
            == "Very Long Title..., 1,..."
        )

    def test_no_room_left_for_the_title_leaves_it_untruncated(self) -> None:
        """With zero chars to spare the title is returned whole rather than truncated."""
        assert self._fit("My Title", ["7"], 3) == "My Title, 7"

    def test_room_for_less_than_the_ellipsis_is_rejected(self) -> None:
        """Pins a rough edge: 1-2 spare chars can't hold "..." and textwrap raises.

        Callers size max_title_with_pages_len from window geometry, so this is not
        reachable in practice - but the boundary is exactly one char away from the
        untruncated case above, so it is worth having nailed down.
        """
        with pytest.raises(ValueError, match="placeholder too large"):
            self._fit("My Title", ["7"], 4)


class TestReaderFormatterClass:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.mock_font_manager: Any = MagicMock()
        self.mock_font_manager.title_info_font_size = 10
        self.formatter = reader_formatter.ReaderFormatter(self.mock_font_manager)

    def test_init(self) -> None:
        # Check if issue names are updated in the instance
        assert "Comics & Stories" in self.formatter._title_info_issue_name  # noqa: SLF001

    def test_init_overrides_exactly_the_four_long_issue_names(self) -> None:
        """The title-info panel is narrow, so four issue names get shorter labels.

        Pinning both the replacements and the fact that nothing else moves - the copy
        must stay aligned with ISSUE_NAME, which is indexed by the Issues enum value.
        """
        names = self.formatter._title_info_issue_name  # noqa: SLF001
        assert names[Issues.CS] == "Comics & Stories"
        assert names[Issues.MC] == "March of Comics"
        assert names[Issues.USGTD] == "US Goes to Disneyland"
        assert names[Issues.HDL] == "HDL Junior Woodchucks"

        overridden = {
            issue
            for issue, (original, shortened) in enumerate(zip(ISSUE_NAME, names, strict=True))
            if original != shortened
        }
        assert overridden == {Issues.CS, Issues.MC, Issues.USGTD, Issues.HDL}

    def test_init_does_not_mutate_the_shared_issue_name_list(self) -> None:
        """ISSUE_NAME is module-global; the formatter must work on its own copy."""
        assert ISSUE_NAME[Issues.CS] == "Comics and Stories"

    def test_get_main_title(self) -> None:
        assert (
            reader_formatter.ReaderFormatter.get_main_title("Title", add_footnote=False) == "Title"
        )
        assert (
            reader_formatter.ReaderFormatter.get_main_title("Title", add_footnote=True)
            == "Title[sup]*[/sup]"
        )

    @patch.object(reader_formatter, "escape_kivy_markup")
    @patch.object(
        reader_formatter, reader_formatter.get_short_formatted_first_published_str.__name__
    )
    @patch.object(reader_formatter, reader_formatter.get_short_submitted_day_and_month.__name__)
    def test_get_issue_info(
        self,
        mock_short_sub: MagicMock,
        mock_short_pub: MagicMock,
        mock_escape: MagicMock,
    ) -> None:
        mock_short_pub.return_value = "PubDate"
        mock_short_sub.return_value = "SubDate"
        mock_escape.side_effect = lambda x: f"ESC_{x}"

        fanta_info = MagicMock()
        fanta_info.comic_book_info.submitted_year = "1950"

        # Test without footnote
        res = reader_formatter.ReaderFormatter.get_issue_info(
            fanta_info, add_footnote=False, sup_font_size=12, color="red"
        )
        # Expect structure: [i]PubDate {formatted_submitted}[/i]
        # formatted_submitted: ESC_[SubDate [color=red]1950[/color]ESC_]

        assert res == "[i]PubDate ESC_[SubDate [color=red]1950[/color]ESC_][/i]"
        # Both date helpers read the ComicBookInfo, not the FantaComicBookInfo wrapper.
        mock_short_pub.assert_called_once_with(fanta_info.comic_book_info)

        # Test with footnote
        res_foot = reader_formatter.ReaderFormatter.get_issue_info(
            fanta_info, add_footnote=True, sup_font_size=12, color="red"
        )
        assert res_foot == (
            "[i]PubDate ESC_[SubDate [color=red]1950[/color]ESC_][size=12][sup]*[/sup][/i]"
        )

    @patch.object(reader_formatter, "escape_kivy_markup")
    @patch.object(reader_formatter, reader_formatter.get_short_submitted_day_and_month.__name__)
    def test_get_formatted_submitted_str(
        self, mock_short_sub: MagicMock, mock_escape: MagicMock
    ) -> None:
        mock_short_sub.return_value = "01 Jan"
        mock_escape.side_effect = lambda x: f"E{x}"

        info = MagicMock()
        info.submitted_year = 2000

        res = reader_formatter.ReaderFormatter.get_formatted_submitted_str(info, "blue")
        assert res == " E[01 Jan [color=blue]2000[/color]E]"
        mock_short_sub.assert_called_once_with(info)

    def test_get_formatted_submitted_str_unknown_date_is_empty(self) -> None:
        """A wholly unrecorded submitted date (e.g. some covers) omits the bracket."""
        info = MagicMock()
        info.submitted_month = -1

        res = reader_formatter.ReaderFormatter.get_formatted_submitted_str(info, "blue")
        assert res == ""

    @patch.object(reader_formatter, "FAN", "FAN_ICON")
    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    @patch.object(reader_formatter, reader_formatter.get_formatted_payment_info.__name__)
    def test_get_title_info(
        self,
        mock_get_payment: MagicMock,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
    ) -> None:
        # Setup
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = "MyTitle"
        fanta_info.fantagraphics_volume = 1

        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"

        mock_vol = MagicMock()
        mock_vol.volume = "V1"
        mock_vol.year = "2000"
        mock_fanta_source.__getitem__.return_value = mock_vol

        # Case 1: No payment info
        mock_barks_payments.get.return_value = None

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=False)
        assert "1st Issue:" in res
        assert "IssueInfo" in res
        assert "Source:" in res
        assert "FAN_ICON CBDL, Vol V1, 2000" in res
        assert "Payslip:" not in res

        # Case 2: With payment info
        mock_payment = MagicMock()
        mock_payment.payment = 100.0
        mock_barks_payments.get.return_value = mock_payment
        mock_get_payment.return_value = "$100"

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=False)
        assert "Payslip:" in res
        assert "$100" in res

        # Case 3: With footnote
        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=True)
        assert "[sup]*[/sup]" in res

    @patch.object(reader_formatter, "get_one_pager_fanta_page")
    @patch.object(reader_formatter, "FAN", "FAN_ICON")
    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    def test_get_title_info_one_pager_includes_fanta_page(
        self,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
        mock_fanta_page: MagicMock,
    ) -> None:
        """A one-pager's Source line also carries its Fantagraphics page number."""
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = Titles.IF_THE_HAT_FITS  # a one-pager
        fanta_info.fantagraphics_volume = 5

        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"
        mock_vol = MagicMock()
        mock_vol.volume = 5
        mock_vol.year = 2013
        mock_fanta_source.__getitem__.return_value = mock_vol
        mock_barks_payments.get.return_value = None
        mock_fanta_page.return_value = 123

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=False)
        assert "FAN_ICON CBDL, Vol 5, 2013, p. 123" in res
        mock_fanta_page.assert_called_once_with(Titles.IF_THE_HAT_FITS)

    @patch.object(reader_formatter, "FAN", "FAN_ICON")
    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    @patch.object(reader_formatter, reader_formatter.get_formatted_payment_info.__name__)
    def test_get_title_info_exact_layout_and_delegation(
        self,
        mock_get_payment: MagicMock,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
    ) -> None:
        """Pin the whole three-line block, plus what each collaborator is asked for.

        Every part of this string is a mocked collaborator's return value, so the
        assertions split in two: the literal layout (labels, spacing, markup, line
        order) is pinned by comparing the whole result, and the *inputs* handed to
        each collaborator are pinned by the call assertions - a membership check on
        the output can't see either.
        """
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = "MyTitle"
        fanta_info.fantagraphics_volume = 1

        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"
        mock_vol = MagicMock()
        mock_vol.volume = "V1"
        mock_vol.year = "2000"
        mock_fanta_source.__getitem__.return_value = mock_vol
        mock_barks_payments.get.return_value = None

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=False)

        assert res == (
            "[i]1st Issue:[/i]   [b]IssueInfo[/b]\n"
            "[i]Submitted:[/i] [b]SubmittedInfo[/b]\n"
            "[i]Source:[/i]       [b]FAN_ICON CBDL, Vol V1, 2000[/b]"
        )
        mock_fmt_pub.assert_called_once_with(
            fanta_info.comic_book_info,
            self.formatter._title_info_issue_name,  # noqa: SLF001
            50,
        )
        mock_long_sub.assert_called_once_with(fanta_info.comic_book_info)
        mock_fanta_source.__getitem__.assert_called_once_with(1)
        mock_barks_payments.get.assert_called_once_with(fanta_info.comic_book_info.title, None)
        mock_get_payment.assert_not_called()

    @patch.object(reader_formatter, "FAN", "FAN_ICON")
    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    @patch.object(reader_formatter, reader_formatter.get_formatted_payment_info.__name__)
    def test_get_title_info_payslip_line_and_footnote(
        self,
        mock_get_payment: MagicMock,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
    ) -> None:
        """A paid title gains a fourth line, and the footnote marker sizes off the font."""
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = "MyTitle"
        fanta_info.fantagraphics_volume = 1

        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"
        mock_vol = MagicMock()
        mock_vol.volume = "V1"
        mock_vol.year = "2000"
        mock_fanta_source.__getitem__.return_value = mock_vol

        payment = MagicMock()
        payment.payment = 100.0
        mock_barks_payments.get.return_value = payment
        mock_get_payment.return_value = "$100"

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=True)

        # title_info_font_size is 10 (see setup), so the marker is round(1.5 * 10) = 15,
        # and it is *appended* to the issue info rather than replacing it.
        assert res == (
            "[i]1st Issue:[/i]   [b]IssueInfo[size=15][sup]*[/sup][/size][/b]\n"
            "[i]Submitted:[/i] [b]SubmittedInfo[/b]\n"
            "[i]Payslip:[/i]      [b]$100[/b]\n"
            "[i]Source:[/i]       [b]FAN_ICON CBDL, Vol V1, 2000[/b]"
        )
        mock_get_payment.assert_called_once_with(payment)

    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    @patch.object(reader_formatter, reader_formatter.get_formatted_payment_info.__name__)
    def test_get_title_info_zero_payment_still_shows_a_payslip(
        self,
        mock_get_payment: MagicMock,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
    ) -> None:
        """The suppression threshold is strict: a payment *at* CLOSE_TO_ZERO still shows.

        Only a recorded payment strictly below it (i.e. effectively nothing) drops the
        line, so this pins which side of the boundary is "paid".
        """
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = "MyTitle"
        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"
        mock_get_payment.return_value = "$0"
        mock_fanta_source.__getitem__.return_value = MagicMock(volume="V1", year="2000")

        payment = MagicMock()
        payment.payment = reader_formatter.CLOSE_TO_ZERO
        mock_barks_payments.get.return_value = payment
        assert "Payslip:" in self.formatter.get_title_info(fanta_info, 50, add_footnote=False)

        payment.payment = reader_formatter.CLOSE_TO_ZERO / 2
        mock_barks_payments.get.return_value = payment
        assert "Payslip:" not in self.formatter.get_title_info(fanta_info, 50, add_footnote=False)

    @patch.object(reader_formatter, "FAN", "FAN_ICON")
    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    @patch.object(reader_formatter, reader_formatter.get_cover_location.__name__)
    def test_get_title_info_cover_source_carries_its_volume_page(
        self,
        mock_cover_location: MagicMock,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
    ) -> None:
        """Covers take the same ", p. N" suffix as one-pagers, via get_cover_location."""
        cover_title = next(iter(reader_formatter.COVERS_SET))
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = cover_title
        fanta_info.fantagraphics_volume = 6

        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"
        mock_vol = MagicMock()
        mock_vol.volume = 6
        mock_vol.year = 2014
        mock_fanta_source.__getitem__.return_value = mock_vol
        mock_barks_payments.get.return_value = None
        mock_cover_location.return_value = (6, 209)

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=False)

        assert res.endswith("[i]Source:[/i]       [b]FAN_ICON CBDL, Vol 6, 2014, p. 209[/b]")
        mock_cover_location.assert_called_once_with(reader_formatter.COVER_BY_TITLE[cover_title])

    @patch.object(reader_formatter, "FAN", "FAN_ICON")
    @patch.object(reader_formatter, "BARKS_PAYMENTS")
    @patch.object(reader_formatter, "FANTA_SOURCE_COMICS")
    @patch.object(reader_formatter, reader_formatter.get_formatted_first_published_str.__name__)
    @patch.object(reader_formatter, reader_formatter.get_long_formatted_submitted_date.__name__)
    @patch.object(reader_formatter, reader_formatter.get_cover_location.__name__)
    def test_get_title_info_cover_with_unknown_location_omits_the_page(
        self,
        mock_cover_location: MagicMock,
        mock_long_sub: MagicMock,
        mock_fmt_pub: MagicMock,
        mock_fanta_source: MagicMock,
        mock_barks_payments: MagicMock,
    ) -> None:
        """An unlocated cover degrades to a plain Source line rather than "p. None"."""
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = next(iter(reader_formatter.COVERS_SET))
        fanta_info.fantagraphics_volume = 6

        mock_fmt_pub.return_value = "IssueInfo"
        mock_long_sub.return_value = "SubmittedInfo"
        mock_vol = MagicMock()
        mock_vol.volume = 6
        mock_vol.year = 2014
        mock_fanta_source.__getitem__.return_value = mock_vol
        mock_barks_payments.get.return_value = None
        mock_cover_location.return_value = None

        res = self.formatter.get_title_info(fanta_info, 50, add_footnote=False)

        assert res.endswith("[i]Source:[/i]       [b]FAN_ICON CBDL, Vol 6, 2014[/b]")

    # A real dict, not a MagicMock: a mock's __contains__/__getitem__ answer the same
    # for any key, so it can't tell "looked the title up" from "looked anything up".
    @patch.object(reader_formatter, "BARKS_EXTRA_INFO", {"KnownTitle": "Extra Info"})
    def test_get_title_extra_info(self) -> None:
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = "KnownTitle"

        res = reader_formatter.ReaderFormatter.get_title_extra_info(fanta_info)
        assert res == f"Ex{SOFT_HYPHEN}tra In{SOFT_HYPHEN}fo"

        # Unknown title
        fanta_info.comic_book_info.title = "Unknown"

        res = reader_formatter.ReaderFormatter.get_title_extra_info(fanta_info)
        assert res == ""
