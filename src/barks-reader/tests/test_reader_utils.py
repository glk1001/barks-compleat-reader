from __future__ import annotations

import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, mock_open, patch

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.comics_consts import PageType
from barks_reader import reader_utils
from barks_reader.reader_utils import EMPTY_PAGE_KEY


@patch("barks_reader.reader_utils.get_approximate_taskbar_height")
def test_get_best_window_height_fit(mock_taskbar_height: MagicMock) -> None:
    mock_taskbar_height.return_value = 50
    assert reader_utils.get_best_window_height_fit(1000) == 950  # noqa: PLR2004


def test_get_win_width_from_height() -> None:
    height = 1000
    expected = round(height / reader_utils.COMIC_PAGE_ASPECT_RATIO)
    assert reader_utils.get_win_width_from_height(height) == expected


def test_get_title_str_from_reader_icon_file() -> None:
    assert reader_utils.get_title_str_from_reader_icon_file(Path("Title-1-1.png")) == "Title"
    assert reader_utils.get_title_str_from_reader_icon_file(Path("Title.png")) == "Title"
    assert reader_utils.get_title_str_from_reader_icon_file(Path("My-Title-1.png")) == "My-Title"


def test_title_needs_footnote() -> None:
    mock_info = MagicMock()
    mock_info.comic_book_info.is_barks_title = False
    mock_info.comic_book_info.issue_name = Issues.CS

    with patch(
        "barks_reader.reader_utils.US_CENSORED_TITLE_ENUMS",
        [Titles.DONALD_DUCK_FINDS_PIRATE_GOLD],
    ):
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        assert reader_utils.title_needs_footnote(mock_info)

        mock_info.comic_book_info.is_barks_title = True
        assert not reader_utils.title_needs_footnote(mock_info)
        mock_info.comic_book_info.is_barks_title = False

        mock_info.comic_book_info.issue_name = Issues.FC
        assert not reader_utils.title_needs_footnote(mock_info)


@patch("kivy.core.image.Image")
def test_get_image_stream(mock_core_image: MagicMock) -> None:
    # Test with Path
    reader_utils.get_image_stream(Path("test.png"))
    mock_core_image.assert_called_with("test.png")

    # Test with file-like object
    mock_file = MagicMock()
    mock_file.read_bytes.return_value = b"data"
    reader_utils.get_image_stream(mock_file)
    args, kwargs = mock_core_image.call_args
    assert isinstance(args[0], io.BytesIO)
    assert kwargs["ext"] == "png"


@patch("barks_reader.reader_utils.randrange")
def test_prob_rand_less_equal(mock_randrange: MagicMock) -> None:
    mock_randrange.return_value = 50
    assert reader_utils.prob_rand_less_equal(60)
    assert not reader_utils.prob_rand_less_equal(40)


@patch("barks_reader.reader_utils.randrange")
def test_get_rand_int(mock_randrange: MagicMock) -> None:
    mock_randrange.return_value = 5
    assert reader_utils.get_rand_int((1, 10)) == 5  # noqa: PLR2004
    mock_randrange.assert_called_with(1, 11)


def test_is_title_page() -> None:
    mock_page = MagicMock()
    mock_page.page_filename = f"{EMPTY_PAGE_KEY}.png"
    mock_page.page_type = PageType.TITLE
    assert reader_utils.is_title_page(mock_page)

    mock_page.page_type = PageType.BODY
    assert not reader_utils.is_title_page(mock_page)


def test_is_blank_page() -> None:
    assert reader_utils.is_blank_page(f"{EMPTY_PAGE_KEY}.png", PageType.BODY)
    assert not reader_utils.is_blank_page(f"{EMPTY_PAGE_KEY}.png", PageType.TITLE)


def test_get_all_files_in_dir() -> None:
    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "file1.txt").touch()
        subdir = root / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").touch()

        # Non-recursive
        files = reader_utils.get_all_files_in_dir(root, recurse=False)
        assert len(files) == 1
        assert files[0].name == "file1.txt"

        # Recursive
        files_rec = reader_utils.get_all_files_in_dir(root, recurse=True)
        assert len(files_rec) == 2  # noqa: PLR2004
        names = sorted([f.name for f in files_rec])
        assert names == ["file1.txt", "file2.txt"]


def test_read_text_paragraphs() -> None:
    data = "A\nB\nC\\\nD\n\nE"
    with patch("pathlib.Path.open", mock_open(read_data=data)):
        text = reader_utils.read_text_paragraphs(Path("dummy"))
        assert text == "A B C\nD \n\nE"


def test_read_title_list() -> None:
    data = "Donald Duck Finds Pirate Gold\nThe Victory Garden"
    with patch("pathlib.Path.open", mock_open(read_data=data)):
        titles = reader_utils.read_title_list(Path("dummy"))
        assert titles == [Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, Titles.VICTORY_GARDEN_THE]


def test_unique_extend() -> None:
    l1 = [Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, Titles.BACK_TO_LONG_AGO]
    l2 = [Titles.BACK_TO_LONG_AGO, Titles.GOOD_NEIGHBORS]
    reader_utils.unique_extend(l1, l2)
    assert l1 == [
        Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
        Titles.BACK_TO_LONG_AGO,
        Titles.GOOD_NEIGHBORS,
    ]


def test_get_paths_from_directory() -> None:
    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "file1.txt").touch()
        (root / "subdir").mkdir()
        (root / "subdir" / "file2.jpg").touch()

        paths = reader_utils.get_paths_from_directory(root)
        # Paths are relative and without extension
        assert "file1" in paths
        # On Windows separators might differ, but the function normalizes to "/"
        assert "subdir/file2" in paths


@patch("zipfile.ZipFile")
def test_get_paths_from_zip(mock_zipfile: MagicMock) -> None:
    mock_zip = MagicMock()
    mock_zip.namelist.return_value = ["file1.txt", "subdir/", "subdir/file2.jpg"]
    mock_zipfile.return_value.__enter__.return_value = mock_zip

    mock_path = MagicMock(spec=Path)
    mock_path.is_file.return_value = True

    paths = reader_utils.get_paths_from_zip(mock_path)
    assert "file1" in paths
    assert "subdir/file2" in paths
    assert "subdir" not in paths


def test_get_concat_page_nums_str() -> None:
    assert reader_utils.get_concat_page_nums_str(["1", "2", "3", "5"]) == "1-3,5"

    with patch("barks_reader.reader_utils.ROMAN_NUMERALS_SET", {"i", "ii"}):
        assert reader_utils.get_concat_page_nums_str(["i", "ii"]) == "i,ii"
        assert reader_utils.get_concat_page_nums_str(["i", "1", "2"]) == "i,1-2"


def test_join_with_and() -> None:
    assert reader_utils.join_with_and([]) == ""
    assert reader_utils.join_with_and(["A"]) == "A"
    assert reader_utils.join_with_and(["A", "B"]) == "A and B"
    assert reader_utils.join_with_and(["A", "B", "C"]) == "A, B, and C"

    assert reader_utils.quote_and_join_with_and(["A", "B"]) == '"A" and "B"'


@patch("screeninfo.get_monitors")
def test_get_centred_position_on_primary_monitor(mock_get_monitors: MagicMock) -> None:
    mock_monitor = MagicMock()
    mock_monitor.is_primary = True
    mock_monitor.x = 0
    mock_monitor.y = 0
    mock_monitor.width = 1920
    mock_monitor.height = 1080
    mock_get_monitors.return_value = [mock_monitor]

    pos = reader_utils.get_centred_position_on_primary_monitor(100, 100)
    assert pos == (910, 490)


@patch("subprocess.run")
def test_safe_import_check(mock_run: MagicMock) -> None:
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = '{"ok": true}'
    mock_run.return_value = mock_proc
    assert reader_utils.safe_import_check("module")

    mock_proc.stdout = '{"ok": false}'
    assert not reader_utils.safe_import_check("module")
