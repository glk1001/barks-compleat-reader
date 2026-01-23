from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path
from random import randrange
from unittest.mock import MagicMock, patch

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core import reader_utils as utils_module
from barks_reader.core.reader_utils import (
    COMIC_PAGE_ASPECT_RATIO,
    EMPTY_PAGE_KEY,
    get_all_files_in_dir,
    get_centred_position_on_primary_monitor,
    get_concat_page_nums_str,
    get_paths_from_directory,
    get_paths_from_zip,
    get_quoted_items,
    get_rand_int,
    get_title_str_from_reader_icon_file,
    get_win_width_from_height,
    is_blank_page,
    is_title_page,
    join_with_and,
    prob_rand_less_equal,
    quote_and_join_with_and,
    read_text_paragraphs,
    read_title_list,
    safe_import_check,
    title_needs_footnote,
    unique_extend,
)
from intspan import intspan


class TestReaderUtils:
    def test_get_win_width_from_height(self) -> None:
        """Test aspect ratio calculation."""
        height = 1000
        expected = round(1000 / COMIC_PAGE_ASPECT_RATIO)
        assert get_win_width_from_height(height) == expected

    def test_get_title_str_from_reader_icon_file(self) -> None:
        """Test extracting title from icon filename."""
        # Case 1: Standard format
        p1 = Path("path/to/My-Comic-Title-1-1.png")
        assert get_title_str_from_reader_icon_file(p1) == "My-Comic-Title"

        # Case 2: Title with hyphens
        p2 = Path("Title-With-Hyphens-2-3.png")
        assert get_title_str_from_reader_icon_file(p2) == "Title-With-Hyphens"

        # Case 3: No suffix (edge case, though regex expects digits at end)
        # The regex is r'(-\d+)+$'. If not found, split returns [original_string]
        p3 = Path("JustTitle.png")
        assert get_title_str_from_reader_icon_file(p3) == "JustTitle"

    def test_title_needs_footnote(self) -> None:
        """Test footnote requirement logic."""
        fanta_info = MagicMock()
        fanta_info.comic_book_info.is_barks_title = False
        fanta_info.comic_book_info.issue_name = Issues.CS

        # Mock the title to be one that needs censorship footnote
        # We need to patch US_CENSORED_TITLE_ENUMS
        dummy_title = MagicMock()
        fanta_info.comic_book_info.title = dummy_title

        with patch.object(utils_module, "US_CENSORED_TITLE_ENUMS", [dummy_title]):
            assert title_needs_footnote(fanta_info) is True

        # Case 1: is_barks_title is True
        fanta_info.comic_book_info.is_barks_title = True
        with patch.object(utils_module, "US_CENSORED_TITLE_ENUMS", [dummy_title]):
            assert title_needs_footnote(fanta_info) is False

    def test_prob_rand_less_equal(self) -> None:
        """Test probability check."""
        with patch.object(utils_module, randrange.__name__) as mock_rand:
            mock_rand.return_value = 50
            # 50 < 60 -> True
            assert prob_rand_less_equal(60) is True
            # 50 < 40 -> False
            assert prob_rand_less_equal(40) is False

    def test_get_rand_int(self) -> None:
        """Test random integer generation."""
        with patch.object(utils_module, randrange.__name__) as mock_rand:
            mock_rand.return_value = 5
            assert get_rand_int((1, 10)) == 5  # noqa: PLR2004
            mock_rand.assert_called_with(1, 11)

    def test_is_title_page(self) -> None:
        """Test title page detection."""
        page = MagicMock()
        page.page_filename = f"{EMPTY_PAGE_KEY}.png"
        page.page_type = PageType.TITLE
        assert is_title_page(page) is True

        page.page_type = PageType.BODY
        assert is_title_page(page) is False

        page.page_filename = "other.png"
        page.page_type = PageType.TITLE
        assert is_title_page(page) is False

    def test_is_blank_page(self) -> None:
        """Test blank page detection."""
        assert is_blank_page(f"{EMPTY_PAGE_KEY}.png", PageType.BLANK_PAGE) is True
        assert is_blank_page(f"{EMPTY_PAGE_KEY}.png", PageType.TITLE) is False
        assert is_blank_page("other.png", PageType.BLANK_PAGE) is False

    def test_get_all_files_in_dir(self, tmp_path: Path) -> None:
        """Test recursive and non-recursive file listing."""
        d = tmp_path / "subdir"
        d.mkdir()
        (d / "f1.txt").touch()
        (d / "f2.txt").touch()
        (d / "sub_sub").mkdir()
        (d / "sub_sub" / "f3.txt").touch()

        files = get_all_files_in_dir(d, recurse=False)
        assert len(files) == 2  # noqa: PLR2004

        files_rec = get_all_files_in_dir(d, recurse=True)
        assert len(files_rec) == 3  # noqa: PLR2004

    def test_read_text_paragraphs(self, tmp_path: Path) -> None:
        """Test reading and formatting text paragraphs."""
        f = tmp_path / "test.txt"
        # "Line 1\n" -> "Line 1 "
        # "Line 2\n" -> "Line 2 "
        # "\n" -> "\n\n"
        # "Line 3" -> "Line 3"
        content = "Line 1\nLine 2\n\nLine 3"
        f.write_text(content, encoding="utf-8")

        res = read_text_paragraphs(f)
        assert "Line 1 Line 2" in res
        assert "\n\n" in res
        assert res.endswith("Line 3")

    def test_read_title_list(self, tmp_path: Path) -> None:
        """Test reading title list from file."""
        f = tmp_path / "titles.txt"
        f.write_text("Title One\nTitle Two\n", encoding="utf-8")

        mock_dict = {
            "Title One": Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            "Title Two": Titles.DONALD_DUCK_AND_THE_MUMMYS_RING,
        }

        # Patch BARKS_TITLE_DICT to use our dummy map
        with patch.object(utils_module, "BARKS_TITLE_DICT", mock_dict):
            titles = read_title_list(f)
            # Should be sorted by enum value.
            assert len(titles) == 2  # noqa: PLR2004
            assert Titles.DONALD_DUCK_FINDS_PIRATE_GOLD in titles
            assert Titles.DONALD_DUCK_AND_THE_MUMMYS_RING in titles

    def test_unique_extend(self) -> None:
        """Test extending list with unique items."""
        l1 = [Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, Titles.DONALD_DUCK_AND_THE_MUMMYS_RING]
        l2 = [Titles.DONALD_DUCK_AND_THE_MUMMYS_RING, Titles.ADVENTURE_DOWN_UNDER, Titles.CUBE_THE]
        unique_extend(l1, l2)
        assert l1 == [
            Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            Titles.DONALD_DUCK_AND_THE_MUMMYS_RING,
            Titles.ADVENTURE_DOWN_UNDER,
            Titles.CUBE_THE,
        ]

    def test_get_paths_from_directory(self, tmp_path: Path) -> None:
        """Test getting relative paths from directory."""
        (tmp_path / "a.txt").touch()
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.png").touch()

        paths = get_paths_from_directory(tmp_path)
        assert "a" in paths
        assert "sub/b" in paths

    def test_get_paths_from_zip(self, tmp_path: Path) -> None:
        """Test getting paths from zip file."""
        z_path = tmp_path / "test.zip"
        with zipfile.ZipFile(z_path, "w") as zf:
            zf.writestr("folder/", "")
            zf.writestr("folder/file.txt", "content")
            zf.writestr("root.png", "content")

        paths = get_paths_from_zip(z_path)
        assert "folder/file" in paths
        assert "root" in paths

    def test_get_concat_page_nums_str(self) -> None:
        """Test page number concatenation string generation."""
        # Mock intspan
        with patch.object(utils_module, intspan.__name__) as mock_intspan:
            mock_intspan.return_value = "1-3"

            # Case 1: Integers only
            res = get_concat_page_nums_str(["1", "2", "3"])
            assert res == "1-3"

            # Case 2: Roman + Int
            # Patch ROMAN_NUMERALS_SET to include 'i'
            with patch.object(utils_module, "ROMAN_NUMERALS_SET", {"i", "ii"}):
                res = get_concat_page_nums_str(["i", "1", "2", "3"])
                assert res == "i,1-3"

    def test_join_with_and(self) -> None:
        """Test joining list with 'and'."""
        assert join_with_and([]) == ""
        assert join_with_and(["a"]) == "a"
        assert join_with_and(["a", "b"]) == "a and b"
        assert join_with_and(["a", "b", "c"]) == "a, b, and c"

    def test_quote_and_join_with_and(self) -> None:
        """Test quoting and joining."""
        assert quote_and_join_with_and(["a", "b"]) == '"a" and "b"'
        assert get_quoted_items(["a"]) == ['"a"']

    def test_get_centred_position_on_primary_monitor(self) -> None:
        """Test window centering logic."""
        mock_monitor = MagicMock()
        mock_monitor.is_primary = True
        mock_monitor.x = 0
        mock_monitor.y = 0
        mock_monitor.width = 1920
        mock_monitor.height = 1080

        mock_screeninfo = MagicMock()
        mock_screeninfo.get_monitors.return_value = [mock_monitor]

        # Patch sys.modules to inject mock screeninfo
        with patch.dict(sys.modules, {"screeninfo": mock_screeninfo}):
            # Win size 800x600
            # x = 0 + (1920 - 800) / 2 = 560
            # y = 0 + (1080 - 600) / 2 = 240
            pos = get_centred_position_on_primary_monitor(800, 600)
            assert pos == (560, 240)

        # Test exception/fallback
        mock_screeninfo.get_monitors.side_effect = Exception("No screens")
        with patch.dict(sys.modules, {"screeninfo": mock_screeninfo}):
            assert get_centred_position_on_primary_monitor(800, 600) == (100, 100)

    def test_safe_import_check(self) -> None:
        """Test safe import check via subprocess."""
        with patch.object(utils_module.subprocess, subprocess.run.__name__) as mock_run:
            # Success case
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = '{"ok": true}'
            mock_run.return_value = mock_proc

            assert safe_import_check("os") is True

            # Failure case
            mock_proc.stdout = '{"ok": false}'
            assert safe_import_check("fake_module") is False

            # Exception/Crash case
            mock_proc.returncode = 1
            assert safe_import_check("crash") is False
