from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from barks_reader import reader_formatter
from barks_reader.reader_formatter import INVISIBLE_BREAK


class TestReaderFormatterFunctions(unittest.TestCase):
    def test_hyphenate_text(self) -> None:
        text = "hyphenation"
        res = reader_formatter.hyphenate_text(text)
        assert reader_formatter.INVISIBLE_BREAK in res

    def test_get_bold_markup_text(self) -> None:
        assert reader_formatter.get_bold_markup_text("foo") == "[b]foo[/b]"

    def test_get_markup_text_with_num_titles(self) -> None:
        res = reader_formatter.get_markup_text_with_num_titles("foo", 5)
        assert res == "[b]foo[/b] [i](5)[/i]"

    def test_get_markup_text_with_extra(self) -> None:
        res = reader_formatter.get_markup_text_with_extra("foo", "bar")
        assert res == "[b]foo[/b] [i](bar)[/i]"

    def test_get_clean_text_without_extra(self) -> None:
        assert reader_formatter.get_clean_text_without_extra("[b]foo[/b]") == "foo"
        assert reader_formatter.get_clean_text_without_extra("foo") == "foo"

        # Test greedy matching behavior
        text = "[b]Title[/b] [i](Info)[/i]"
        assert reader_formatter.get_clean_text_without_extra(text) == "Title"

    def test_get_text_with_markup_stripped(self) -> None:
        text = "[b]Bold[/b] and [i]Italic[/i]"
        assert reader_formatter.get_text_with_markup_stripped(text) == "Bold and Italic"

        # Complex/Nested
        text_complex = "[color=#ff0000]Red[/color] [size=20]Big[/size] [b]Bold[/b]"
        assert reader_formatter.get_text_with_markup_stripped(text_complex) == "Red Big Bold"

    def test_text_includes_num_titles(self) -> None:
        assert reader_formatter.text_includes_num_titles("Something (5)[/i]")
        assert not reader_formatter.text_includes_num_titles("Something")

    def test_get_action_bar_title(self) -> None:
        mock_font_manager = MagicMock()
        mock_font_manager.app_title_font_size = 20.5
        # We check if the string contains expected parts since CARL_BARKS_FONT_FILE is imported
        result = reader_formatter.get_action_bar_title(mock_font_manager, "My Title")
        assert "[font=" in result
        assert "[size=20]My Title" in result

    def test_get_formatted_color(self) -> None:
        # Assuming Color is a tuple/list of floats
        color = (0.1, 0.5, 0.9, 1.0)
        result = reader_formatter.get_formatted_color(color)
        assert result == "(0.10, 0.50, 0.90, 1.00)"

    @patch("barks_reader.reader_formatter.inflate")
    @patch("barks_reader.reader_formatter.datetime")
    def test_get_formatted_payment_info(
        self, mock_datetime: MagicMock, mock_inflate: MagicMock
    ) -> None:
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

        # Case 2: CPI not available (inflate returns < 0)
        mock_inflate.return_value = -1.0
        result = reader_formatter.get_formatted_payment_info(mock_payment_info)
        assert result == "CPI calculator is not available"

    def test_mark_phrase_in_text(self) -> None:
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

    def test_get_fitted_title_with_page_nums(self) -> None:
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


class TestReaderFormatterClass(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_font_manager = MagicMock()
        self.mock_font_manager.title_info_font_size = 10
        self.formatter = reader_formatter.ReaderFormatter(self.mock_font_manager)

    def test_init(self) -> None:
        # Check if issue names are updated in the instance
        assert "Comics & Stories" in self.formatter._title_info_issue_name  # noqa: SLF001

    def test_get_main_title(self) -> None:
        assert (
            reader_formatter.ReaderFormatter.get_main_title("Title", add_footnote=False) == "Title"
        )
        assert (
            reader_formatter.ReaderFormatter.get_main_title("Title", add_footnote=True)
            == "Title[sup]*[/sup]"
        )

    @patch("barks_reader.reader_formatter.escape_markup")
    @patch("barks_reader.reader_formatter.get_short_formatted_first_published_str")
    @patch("barks_reader.reader_formatter.get_short_submitted_day_and_month")
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
        # formatted_submitted: ESC_[SubDate [b][color=red]1950[/color][/b]ESC_]

        assert "PubDate" in res
        assert "SubDate" in res
        assert "1950" in res
        assert "[color=red]" in res
        assert "[sup]*[/sup]" not in res

        # Test with footnote
        res_foot = reader_formatter.ReaderFormatter.get_issue_info(
            fanta_info, add_footnote=True, sup_font_size=12, color="red"
        )
        assert "[sup]*[/sup]" in res_foot

    @patch("barks_reader.reader_formatter.escape_markup")
    @patch("barks_reader.reader_formatter.get_short_submitted_day_and_month")
    def test_get_formatted_submitted_str(
        self, mock_short_sub: MagicMock, mock_escape: MagicMock
    ) -> None:
        mock_short_sub.return_value = "01 Jan"
        mock_escape.side_effect = lambda x: f"E{x}"

        info = MagicMock()
        info.submitted_year = 2000

        res = reader_formatter.ReaderFormatter.get_formatted_submitted_str(info, "blue")
        assert res == " E[01 Jan [b][color=blue]2000[/color][/b]E]"

    @patch("barks_reader.reader_formatter.FAN", "FAN_ICON")
    @patch("barks_reader.reader_formatter.BARKS_PAYMENTS")
    @patch("barks_reader.reader_formatter.FANTA_SOURCE_COMICS")
    @patch("barks_reader.reader_formatter.get_formatted_first_published_str")
    @patch("barks_reader.reader_formatter.get_long_formatted_submitted_date")
    @patch("barks_reader.reader_formatter.get_formatted_payment_info")
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

    @patch("barks_reader.reader_formatter.BARKS_EXTRA_INFO")
    def test_get_title_extra_info(self, mock_extra_info: MagicMock) -> None:
        fanta_info = MagicMock()
        fanta_info.comic_book_info.title = "KnownTitle"

        mock_extra_info.__contains__.return_value = True
        mock_extra_info.__getitem__.return_value = "Extra Info"

        res = reader_formatter.ReaderFormatter.get_title_extra_info(fanta_info)
        assert res == f"Ex{INVISIBLE_BREAK}tra In{INVISIBLE_BREAK}fo"

        # Unknown title
        fanta_info.comic_book_info.title = "Unknown"
        mock_extra_info.__contains__.side_effect = lambda k: k == "KnownTitle"

        res = reader_formatter.ReaderFormatter.get_title_extra_info(fanta_info)
        assert res == ""
