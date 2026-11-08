from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core import reader_utils as utils_module
from barks_reader.core.main_layout import SPREAD_WIDTH_IN_PAGES
from barks_reader.core.reader_file_paths import ReaderFilePaths
from barks_reader.core.reader_utils import (
    COMIC_PAGE_ASPECT_RATIO,
    EMPTY_PAGE_KEY,
    expand_path_vars,
    get_all_files_in_dir,
    get_centred_position_on_primary_monitor,
    get_concat_page_nums_str,
    get_page_run_end,
    get_page_run_starts,
    get_page_sort_key,
    get_paths_from_directory,
    get_paths_from_zip,
    get_quoted_items,
    get_tagged_pages,
    get_title_str_from_reader_icon_file,
    get_win_dimensions,
    get_win_width_from_height,
    is_blank_page,
    is_title_page,
    join_with_and,
    quote_and_join_with_and,
    read_title_list,
    safe_import_check,
    title_needs_footnote,
)
from intspan import intspan

if TYPE_CHECKING:
    from typing import IO, Any


class TestReaderUtils:
    def test_get_win_width_from_height(self) -> None:
        """Test aspect ratio calculation."""
        height = 1000
        expected = round(1000 / COMIC_PAGE_ASPECT_RATIO)
        assert get_win_width_from_height(height) == expected

    def test_get_win_dimensions_height_limited(self) -> None:
        """When derived width fits within max_width, return it unchanged."""
        content_h = 1000
        max_w = 2000
        width, result_h = get_win_dimensions(content_h, max_w)
        assert width == get_win_width_from_height(content_h)
        assert result_h == content_h

    def test_get_win_dimensions_width_limited(self) -> None:
        """When derived width exceeds max_width, clamp to max_width and reduce height."""
        content_h = 1000
        max_w = 400  # Much smaller than derived width (~662)
        width, result_h = get_win_dimensions(content_h, max_w)
        assert width == max_w
        assert result_h == round(max_w * COMIC_PAGE_ASPECT_RATIO)
        assert result_h < content_h

    def test_get_win_dimensions_at_exactly_max_width(self) -> None:
        """A derived width of exactly max_width still counts as fitting (<=, not <)."""
        content_h = 1000
        exact_w = get_win_width_from_height(content_h)
        width, result_h = get_win_dimensions(content_h, exact_w)
        assert width == exact_w
        assert result_h == content_h

    def test_get_win_dimensions_take_the_spreads_shape(self) -> None:
        """The main window in the two-page spread: wider at the same height."""
        spread = COMIC_PAGE_ASPECT_RATIO / SPREAD_WIDTH_IN_PAGES
        assert get_win_width_from_height(1000, spread) == round(1000 / spread)
        assert get_win_dimensions(1000, 10_000, spread) == (round(1000 / spread), 1000)
        # Width-limited at the spread's shape: the height follows the same shape.
        assert get_win_dimensions(1000, 1000, spread) == (1000, round(1000 * spread))

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

    def test_get_title_str_from_reader_icon_file_strips_flipped_suffix(self) -> None:
        """A "-flipped" variant resolves to the same title as its unflipped twin."""
        assert get_title_str_from_reader_icon_file(Path("My-Title-1-1-flipped.png")) == "My-Title"
        # Only a *trailing* "-flipped" is a variant marker; elsewhere it is part of the title.
        assert (
            get_title_str_from_reader_icon_file(Path("-flipped-Title-2-1.png")) == "-flipped-Title"
        )

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

    def test_get_all_files_in_dir_recurses_at_every_depth(self, tmp_path: Path) -> None:
        """Two levels down: one level would pass with the flag dropped on the way down."""
        d = tmp_path / "subdir"
        (d / "a" / "b" / "c").mkdir(parents=True)
        (d / "f1.txt").touch()
        (d / "a" / "f2.txt").touch()
        (d / "a" / "b" / "f3.txt").touch()
        (d / "a" / "b" / "c" / "f4.txt").touch()

        names = sorted(p.name for p in get_all_files_in_dir(d, recurse=True))

        assert names == ["f1.txt", "f2.txt", "f3.txt", "f4.txt"]

    def test_get_all_files_in_dir_recurses_in_a_zip(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "panels.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Top/f1.jpg", "")
            zf.writestr("Top/a/f2.jpg", "")
            zf.writestr("Top/a/b/f3.jpg", "")

        with zipfile.ZipFile(zip_path) as zf:
            top = zipfile.Path(zf) / "Top/"
            names = sorted(p.name for p in get_all_files_in_dir(top, recurse=True))

        assert names == ["f1.jpg", "f2.jpg", "f3.jpg"]

    def test_get_all_files_in_dir_does_not_recurse_by_default(self, tmp_path: Path) -> None:
        """Omitting `recurse` must behave like recurse=False, not silently walk the tree."""
        d = tmp_path / "subdir"
        d.mkdir()
        (d / "f1.txt").touch()
        (d / "sub_sub").mkdir()
        (d / "sub_sub" / "f2.txt").touch()

        assert [p.name for p in get_all_files_in_dir(d)] == ["f1.txt"]

    def test_read_title_list(self, tmp_path: Path) -> None:
        """Test reading title list from file."""
        f = tmp_path / "titles.txt"
        f.write_text("Title One\nTitle Two\n", encoding="utf-8")

        mock_dict = {
            "Title One": Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            "Title Two": Titles.DONALD_DUCK_AND_THE_MUMMYS_RING,
        }

        # Patch STR_TITLE_TO_ENUM to use our dummy map
        with patch.object(utils_module, "STR_TITLE_TO_ENUM", mock_dict):
            titles = read_title_list(f)
            # Should be sorted by enum value.
            assert len(titles) == 2  # noqa: PLR2004
            assert Titles.DONALD_DUCK_FINDS_PIRATE_GOLD in titles
            assert Titles.DONALD_DUCK_AND_THE_MUMMYS_RING in titles

    def test_read_title_list_skips_blank_lines(self, tmp_path: Path) -> None:
        """A blank line (an editor's extra newline) is not an unknown title."""
        f = tmp_path / "titles.txt"
        f.write_text("\nLost in the Andes!\n\n   \nVacation Time\n\n", encoding="utf-8")

        titles = read_title_list(f)

        assert titles == sorted([Titles.LOST_IN_THE_ANDES, Titles.VACATION_TIME])

    def test_read_title_list_drops_a_byte_order_mark(self, tmp_path: Path) -> None:
        f = tmp_path / "titles.txt"
        f.write_text("Lost in the Andes!\n", encoding="utf-8-sig")

        assert read_title_list(f) == [Titles.LOST_IN_THE_ANDES]

    def test_read_title_list_reads_utf8_whatever_the_locale(self, tmp_path: Path) -> None:
        """Windows' default codec (cp1252) would misread a UTF-8 title."""
        f = tmp_path / "titles.txt"
        f.write_bytes("Caf\u00e9 Title\n".encode())

        with patch.object(utils_module, "STR_TITLE_TO_ENUM", {"Caf\u00e9 Title": Titles.CUBE_THE}):
            real_open = Path.open

            def open_with_cp1252_default(
                path: Path, mode: str = "r", encoding: str = "cp1252"
            ) -> IO[Any]:
                return real_open(path, mode, encoding=encoding)

            with patch.object(Path, Path.open.__name__, open_with_cp1252_default):
                assert read_title_list(f) == [Titles.CUBE_THE]

    def test_read_title_list_names_an_unknown_title(self, tmp_path: Path) -> None:
        f = tmp_path / "titles.txt"
        f.write_text("Not A Barks Title\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match='Unknown title "Not A Barks Title"'):
            read_title_list(f)

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
        # Exact set: the "folder/" directory entry must be skipped, not listed as "folder".
        assert paths == {"folder/file", "root"}

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

    @pytest.mark.parametrize(
        ("pages", "starts"),
        [
            (["7"], ["7"]),
            (["4", "5", "6", "7"], ["4"]),
            (["7", "13", "16", "17", "18", "19", "20", "21", "22", "23"], ["7", "13", "16"]),
            (["24", "19", "20", "31", "21"], ["19", "24", "31"]),
            ([], []),
        ],
    )
    def test_get_page_run_starts(self, pages: list[str], starts: list[str]) -> None:
        assert get_page_run_starts(pages) == starts

    @pytest.mark.parametrize(
        ("page", "pages", "end"),
        [
            ("1", ["1", "2", "3"], "3"),
            ("16", ["7", "13", "16", "17", "18", "19", "20", "21", "22", "23"], "23"),
            ("13", ["7", "13", "16", "17"], ""),  # a lone page
            ("17", ["16", "17", "18"], ""),  # inside a run, not its start
            ("5", ["1", "2", "3"], ""),  # not among them
            ("19", ["24", "19", "20", "31", "21"], "21"),  # any order
            ("ii", ["i", "ii", "iii"], ""),  # front matter has no runs
            ("", ["1", "2"], ""),
        ],
    )
    def test_get_page_run_end(self, page: str, pages: list[str], end: str) -> None:
        assert get_page_run_end(page, pages) == end

    def test_get_page_run_starts_puts_each_front_matter_page_first_in_page_order(self) -> None:
        # Sorted as strings, "ix" would come before "v", and "iv" before both.
        pages = ["2", "v", "1", "ix", "5", "iv"]
        assert get_page_run_starts(pages) == ["iv", "v", "ix", "1", "5"]

    def test_tagged_pages_are_joined_across_the_tags_and_sorted(self) -> None:
        andes = Titles.LOST_IN_THE_ANDES
        with patch.object(
            utils_module,
            "BARKS_TAGGED_PAGES",
            {(Tags.AWFULTONIANS, andes): ["19", "26"], (Tags.SPLASH, andes): ["iv", "17", "26"]},
        ):
            assert get_tagged_pages((Tags.AWFULTONIANS, Tags.SPLASH), andes) == [
                "iv",
                "17",
                "19",
                "26",
            ]
            assert get_tagged_pages((Tags.AWFULTONIANS,), Titles.BACK_TO_THE_KLONDIKE) == []
            assert get_tagged_pages((), andes) == []

    def test_get_page_sort_key_puts_front_matter_first_then_numbers(self) -> None:
        pages = ["9", "x", "14", "1", "iv", "ii"]
        assert sorted(pages, key=get_page_sort_key) == ["ii", "iv", "x", "1", "9", "14"]

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

    def test_read_title_list_raises_on_unknown_title(self, tmp_path: Path) -> None:
        """Unknown title in the favourites file should raise RuntimeError."""
        f = tmp_path / "titles.txt"
        f.write_text("Known Title\nUnknown Title\n", encoding="utf-8")

        mock_dict = {"Known Title": Titles.DONALD_DUCK_FINDS_PIRATE_GOLD}

        with (
            patch.object(utils_module, "STR_TITLE_TO_ENUM", mock_dict),
            pytest.raises(RuntimeError, match='Unknown title "Unknown Title"'),
        ):
            read_title_list(f)

    def test_get_paths_from_directory_returns_empty_when_not_dir(self, tmp_path: Path) -> None:
        """Non-existent directory should yield an empty set, not raise."""
        missing = tmp_path / "does_not_exist"
        assert get_paths_from_directory(missing) == set()

    def test_get_paths_from_zip_returns_empty_when_not_file(self, tmp_path: Path) -> None:
        """Non-existent zip path should yield an empty set, not raise."""
        missing = tmp_path / "does_not_exist.zip"
        assert get_paths_from_zip(missing) == set()

    def test_get_concat_page_nums_str_raises_on_non_int(self) -> None:
        """Non-roman, non-int input should raise ValueError from inner converter."""
        with (
            patch.object(utils_module, "ROMAN_NUMERALS_SET", set()),
            pytest.raises(ValueError, match="Could not convert page nums list"),
        ):
            get_concat_page_nums_str(["abc", "1"])

    def test_get_concat_page_nums_str_roman_only(self) -> None:
        """When input is only roman numerals, no trailing comma+arabic is appended."""
        with patch.object(utils_module, "ROMAN_NUMERALS_SET", {"i", "ii"}):
            assert get_concat_page_nums_str(["ii", "i"]) == "i,ii"

    @pytest.mark.parametrize(
        ("pages", "expected"),
        [
            # As strings, "ix" < "v" < "viii": the pages must go in numeral order.
            (["viii", "ix", "v", "1", "2"], "v,viii,ix,1-2"),
            (["ix", "vi", "x"], "vi,ix,x"),
        ],
    )
    def test_get_concat_page_nums_str_orders_the_real_numerals_by_value(
        self, pages: list[str], expected: str
    ) -> None:
        """Unpatched: the real numerals, up to x, where string order goes wrong."""
        assert get_concat_page_nums_str(pages) == expected

    def test_get_concat_page_nums_str_multiple_romans_then_arabic(self) -> None:
        """Several roman pages are comma-joined among themselves before the arabic run."""
        with (
            patch.object(utils_module, intspan.__name__) as mock_intspan,
            patch.object(utils_module, "ROMAN_NUMERALS_SET", {"i", "ii", "iii"}),
        ):
            mock_intspan.return_value = "1-3"
            assert get_concat_page_nums_str(["iii", "i", "ii", "1", "2", "3"]) == "i,ii,iii,1-3"

    def test_safe_import_check_handles_malformed_json(self) -> None:
        """Subprocess returning success but malformed stdout falls back to False."""
        with patch.object(utils_module.subprocess, subprocess.run.__name__) as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "not json at all"
            mock_run.return_value = mock_proc

            assert safe_import_check("anything") is False

    def test_safe_import_check_json_without_ok_key_is_false(self) -> None:
        """Well-formed JSON that omits "ok" must not be read as success."""
        with patch.object(utils_module.subprocess, subprocess.run.__name__) as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = '{"err": "boom"}'
            mock_run.return_value = mock_proc

            assert safe_import_check("anything") is False

    def test_safe_import_check_sandbox_subprocess_contract(self) -> None:
        """Pin how the sandbox subprocess is spawned - each kwarg here carries weight.

        A crashing import (e.g. a segfaulting extension module) must not take down the
        caller, so the check runs out-of-process: `check=False` keeps a non-zero exit
        from raising, `capture_output`/`text` are what make stdout parseable, and the
        timeout stops a hung import blocking startup forever.
        """
        with patch.object(utils_module.subprocess, subprocess.run.__name__) as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = '{"ok": true}'
            mock_run.return_value = mock_proc

            assert safe_import_check("some_module") is True

        args, kwargs = mock_run.call_args
        assert args[0][:2] == [sys.executable, "-c"]
        assert "some_module" in args[0][2]
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 5.0,
        }

    def test_safe_import_check_timeout_is_false_not_a_raise(self) -> None:
        """A slow first import (a cold Windows VM) must not kill the first-run installer."""
        with patch.object(
            utils_module.subprocess,
            subprocess.run.__name__,
            side_effect=subprocess.TimeoutExpired(cmd="python", timeout=5.0),
        ):
            assert safe_import_check("slow_module") is False

    def test_safe_import_check_when_compiled_imports_in_process(self) -> None:
        """In a Nuitka build sys.executable is the app binary, so import directly."""
        with (
            patch.object(utils_module, "IS_COMPILED", True),  # noqa: FBT003
            patch.object(utils_module.subprocess, subprocess.run.__name__) as mock_run,
        ):
            assert safe_import_check("json") is True
            assert safe_import_check("no_such_module_anywhere_xyz") is False
            mock_run.assert_not_called()


class TestExpandPathVars:
    FAKE_HOME = Path("/fake/home")

    @pytest.mark.parametrize("home_var", ["${HOME}", "$HOME"])
    def test_home_is_the_users_home_when_the_environment_has_no_home(
        self, monkeypatch: pytest.MonkeyPatch, home_var: str
    ) -> None:
        """Windows sets no HOME: started from Explorer or PowerShell, the app has none."""
        monkeypatch.delenv("HOME", raising=False)
        with patch.object(Path, Path.home.__name__, return_value=self.FAKE_HOME):
            assert expand_path_vars(f"{home_var}/Books") == f"{self.FAKE_HOME}/Books"

    def test_a_set_home_is_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/set/home")
        with patch.object(Path, Path.home.__name__, return_value=self.FAKE_HOME):
            assert expand_path_vars("${HOME}/Books") == "/set/home/Books"

    def test_a_longer_name_starting_with_home_is_not_home(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HOME", raising=False)
        monkeypatch.setenv("HOMEPATH", "/home/path")
        with patch.object(Path, Path.home.__name__, return_value=self.FAKE_HOME):
            assert expand_path_vars("$HOMEPATH/Books") == "/home/path/Books"

    def test_other_variables_are_still_expanded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HOME", raising=False)
        monkeypatch.setenv("BARKS_TEST_DIR", "/barks/test")
        with patch.object(Path, Path.home.__name__, return_value=self.FAKE_HOME):
            # As paths: on Windows the expansion keeps the variable's "/" beside a "\".
            assert Path(expand_path_vars(Path("${BARKS_TEST_DIR}/x"))) == Path("/barks/test/x")

    def test_the_default_prebuilt_dir_is_under_the_home_when_the_environment_has_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """win_lg's overnight validate looked for a folder named "${HOME}" (2026-10-11)."""
        monkeypatch.delenv("HOME", raising=False)
        with patch.object(Path, Path.home.__name__, return_value=self.FAKE_HOME):
            prebuilt_dir = ReaderFilePaths.get_default_prebuilt_comic_zips_dir()

        assert prebuilt_dir.is_relative_to(self.FAKE_HOME)
