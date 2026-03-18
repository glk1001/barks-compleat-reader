# ruff: noqa: PLR2004

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.comic_book import ModifiedType
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import CleanPage, OriginalPage
from barks_fantagraphics.pages import (
    EMPTY_FILENAME,
    EMPTY_IMAGE_FILEPATH,
    TITLE_EMPTY_FILENAME,
    TITLE_EMPTY_IMAGE_FILEPATH,
    SrceDependency,
    get_full_srce_filepath,
    get_page_mod_type,
    get_page_number_str,
    get_relative_srce_filepath,
    get_required_pages_in_order,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _page(page_type: PageType, page_num: int = 1) -> CleanPage:
    return CleanPage("001", page_type, page_num)


# ---------------------------------------------------------------------------
# get_page_number_str
# ---------------------------------------------------------------------------


class TestGetPageNumberStr:
    def test_painting_no_border_returns_empty(self) -> None:
        assert get_page_number_str(_page(PageType.PAINTING_NO_BORDER), 1) == ""

    def test_back_painting_no_border_returns_empty(self) -> None:
        assert get_page_number_str(_page(PageType.BACK_PAINTING_NO_BORDER), 1) == ""

    def test_front_page_returns_empty(self) -> None:
        assert get_page_number_str(_page(PageType.FRONT, 0), 0) == ""

    def test_body_page_returns_number_str(self) -> None:
        assert get_page_number_str(_page(PageType.BODY), 5) == "5"

    def test_back_matter_returns_number_str(self) -> None:
        assert get_page_number_str(_page(PageType.BACK_MATTER), 12) == "12"

    def test_back_no_panels_returns_number_str(self) -> None:
        assert get_page_number_str(_page(PageType.BACK_NO_PANELS), 7) == "7"

    def test_front_matter_returns_roman_numeral(self) -> None:
        assert get_page_number_str(_page(PageType.FRONT_MATTER), 1) == "i"
        assert get_page_number_str(_page(PageType.FRONT_MATTER), 3) == "iii"
        assert get_page_number_str(_page(PageType.FRONT_MATTER), 10) == "x"

    def test_cover_returns_roman_numeral(self) -> None:
        assert get_page_number_str(_page(PageType.COVER), 2) == "ii"

    def test_title_page_returns_roman_numeral(self) -> None:
        assert get_page_number_str(_page(PageType.TITLE), 4) == "iv"

    def test_page_number_zero_returns_zero_str_for_body(self) -> None:
        # BODY is not in FRONT_MATTER_PAGES
        assert get_page_number_str(_page(PageType.BODY), 0) == "0"


# ---------------------------------------------------------------------------
# get_required_pages_in_order
# ---------------------------------------------------------------------------


class TestGetRequiredPagesInOrder:
    def test_title_empty_filename(self) -> None:
        pages = [OriginalPage(TITLE_EMPTY_FILENAME, PageType.TITLE)]
        result = get_required_pages_in_order(pages)
        assert len(result) == 1
        assert result[0].page_filename == TITLE_EMPTY_FILENAME
        assert result[0].page_type == PageType.TITLE
        assert result[0].page_num == -1

    def test_empty_filename(self) -> None:
        pages = [OriginalPage(EMPTY_FILENAME, PageType.BLANK_PAGE)]
        result = get_required_pages_in_order(pages)
        assert len(result) == 1
        assert result[0].page_filename == EMPTY_FILENAME
        assert result[0].page_type == PageType.BLANK_PAGE
        assert result[0].page_num == -1

    def test_numeric_filename_sets_page_num(self) -> None:
        pages = [OriginalPage("042", PageType.BODY)]
        result = get_required_pages_in_order(pages)
        assert result[0].page_num == 42

    def test_multiple_pages_in_order(self) -> None:
        pages = [
            OriginalPage("001", PageType.BODY),
            OriginalPage("002", PageType.BODY),
            OriginalPage(EMPTY_FILENAME, PageType.BLANK_PAGE),
        ]
        result = get_required_pages_in_order(pages)
        assert len(result) == 3
        assert result[0].page_num == 1
        assert result[1].page_num == 2
        assert result[2].page_num == -1

    def test_empty_input(self) -> None:
        assert get_required_pages_in_order([]) == []


# ---------------------------------------------------------------------------
# get_full_srce_filepath
# ---------------------------------------------------------------------------


class TestGetFullSrceFilepath:
    def test_title_empty_returns_title_empty_path(self) -> None:
        page = CleanPage(TITLE_EMPTY_FILENAME, PageType.TITLE)
        result = get_full_srce_filepath(MagicMock(), page)
        assert result == TITLE_EMPTY_IMAGE_FILEPATH

    def test_empty_returns_empty_path(self) -> None:
        page = CleanPage(EMPTY_FILENAME, PageType.BLANK_PAGE)
        result = get_full_srce_filepath(MagicMock(), page)
        assert result == EMPTY_IMAGE_FILEPATH

    def test_normal_page_calls_get_final_srce_story_file(self) -> None:
        comic = MagicMock()
        expected = Path("/some/dir/001.jpg")
        comic.get_final_srce_story_file.return_value = (str(expected), ModifiedType.ORIGINAL)
        page = CleanPage("001", PageType.BODY)

        result = get_full_srce_filepath(comic, page)

        comic.get_final_srce_story_file.assert_called_once_with("001", PageType.BODY)
        assert result == expected


# ---------------------------------------------------------------------------
# get_relative_srce_filepath
# ---------------------------------------------------------------------------


class TestGetRelativeSrceFilepath:
    def test_title_empty_returns_image_filename(self) -> None:
        page = CleanPage(TITLE_EMPTY_FILENAME, PageType.TITLE)
        result = get_relative_srce_filepath(page)
        assert result == TITLE_EMPTY_IMAGE_FILEPATH.name

    def test_empty_returns_image_filename(self) -> None:
        page = CleanPage(EMPTY_FILENAME, PageType.BLANK_PAGE)
        result = get_relative_srce_filepath(page)
        assert result == EMPTY_IMAGE_FILEPATH.name

    def test_normal_page_returns_filename_with_jpg_ext(self) -> None:
        page = CleanPage("042", PageType.BODY)
        result = get_relative_srce_filepath(page)
        assert result == "042.jpg"


# ---------------------------------------------------------------------------
# get_page_mod_type
# ---------------------------------------------------------------------------


class TestGetPageModType:
    def test_title_empty_returns_original(self) -> None:
        page = CleanPage(TITLE_EMPTY_FILENAME, PageType.TITLE)
        result = get_page_mod_type(MagicMock(), page)
        assert result == ModifiedType.ORIGINAL

    def test_empty_returns_original(self) -> None:
        page = CleanPage(EMPTY_FILENAME, PageType.BLANK_PAGE)
        result = get_page_mod_type(MagicMock(), page)
        assert result == ModifiedType.ORIGINAL

    def test_uses_story_file_mod_type_when_not_original(self) -> None:
        comic = MagicMock()
        comic.get_final_srce_story_file.return_value = (
            Path("/some/001.jpg"),
            ModifiedType.MODIFIED,
        )
        page = CleanPage("001.jpg", PageType.BODY)

        result = get_page_mod_type(comic, page)

        assert result == ModifiedType.MODIFIED
        comic.get_final_srce_story_file.assert_called_once_with("001", PageType.BODY)

    def test_falls_through_to_upscayled_when_original(self) -> None:
        comic = MagicMock()
        comic.get_final_srce_story_file.return_value = (Path("/x.jpg"), ModifiedType.ORIGINAL)
        comic.get_final_srce_upscayled_story_file.return_value = (
            Path("/x.jpg"),
            ModifiedType.ADDED,
        )
        page = CleanPage("001.jpg", PageType.BODY)

        result = get_page_mod_type(comic, page)

        assert result == ModifiedType.ADDED

    def test_falls_through_to_original_file_when_all_original(self) -> None:
        comic = MagicMock()
        comic.get_final_srce_story_file.return_value = (Path("/x.jpg"), ModifiedType.ORIGINAL)
        comic.get_final_srce_upscayled_story_file.return_value = (
            Path("/x.jpg"),
            ModifiedType.ORIGINAL,
        )
        comic.get_final_srce_original_story_file.return_value = (
            Path("/x.jpg"),
            ModifiedType.ORIGINAL,
        )
        page = CleanPage("001.jpg", PageType.BODY)

        result = get_page_mod_type(comic, page)

        comic.get_final_srce_original_story_file.assert_called_once_with("001", PageType.BODY)
        assert result == ModifiedType.ORIGINAL


# ---------------------------------------------------------------------------
# SrceDependency
# ---------------------------------------------------------------------------


class TestSrceDependency:
    def test_default_mod_type_is_original(self) -> None:
        sd = SrceDependency(file=Path("/x"), timestamp=1.0, independent=True)
        assert sd.mod_type == ModifiedType.ORIGINAL

    def test_stores_fields(self) -> None:
        sd = SrceDependency(
            file=Path("/some/file.jpg"),
            timestamp=42.5,
            independent=False,
            mod_type=ModifiedType.MODIFIED,
        )
        assert sd.file == Path("/some/file.jpg")
        assert sd.timestamp == 42.5
        assert sd.independent is False
        assert sd.mod_type == ModifiedType.MODIFIED
