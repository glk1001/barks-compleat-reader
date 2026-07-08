# ruff: noqa: PLR2004

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comic_book import ModifiedType
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import (
    CleanPage,
    ComicDimensions,
    OriginalPage,
    RequiredDimensions,
    SrceAndDestPages,
)
from barks_fantagraphics.pages import (
    EMPTY_FILENAME,
    EMPTY_IMAGE_FILEPATH,
    TITLE_EMPTY_FILENAME,
    TITLE_EMPTY_IMAGE_FILEPATH,
    FinalStoryFileResolver,
    SrceDependency,
    SrceStoryFileNotFoundError,
    SrceStoryFileResolver,
    SvgPngStoryFileResolver,
    _get_srce_and_dest_pages_in_order,
    get_full_srce_filepath,
    get_page_mod_type,
    get_page_number_str,
    get_relative_srce_filepath,
    get_required_pages_in_order,
    get_srce_dest_map,
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

    def test_custom_resolver_overrides_default(self) -> None:
        comic = MagicMock()
        page = CleanPage("001", PageType.BODY)
        expected = Path("/custom/001.png")

        resolver = MagicMock(spec=SrceStoryFileResolver)
        resolver.get_story_file.return_value = expected

        result = get_full_srce_filepath(comic, page, resolver)

        resolver.get_story_file.assert_called_once_with(comic, page)
        comic.get_final_srce_story_file.assert_not_called()
        assert result == expected

    def test_custom_resolver_ignored_for_empty_filenames(self) -> None:
        resolver = MagicMock(spec=SrceStoryFileResolver)
        title_page = CleanPage(TITLE_EMPTY_FILENAME, PageType.TITLE)
        blank_page = CleanPage(EMPTY_FILENAME, PageType.BLANK_PAGE)

        title_result = get_full_srce_filepath(MagicMock(), title_page, resolver)
        blank_result = get_full_srce_filepath(MagicMock(), blank_page, resolver)
        assert title_result == TITLE_EMPTY_IMAGE_FILEPATH
        assert blank_result == EMPTY_IMAGE_FILEPATH
        resolver.get_story_file.assert_not_called()


# ---------------------------------------------------------------------------
# SrceStoryFileResolver and concrete subclasses
# ---------------------------------------------------------------------------


class TestSrceStoryFileResolver:
    def test_abstract_base_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            SrceStoryFileResolver()  # type: ignore[abstract]


class TestFinalStoryFileResolver:
    def test_returns_final_srce_story_file_as_path(self) -> None:
        comic = MagicMock()
        expected = Path("/some/dir/001.jpg")
        comic.get_final_srce_story_file.return_value = (str(expected), ModifiedType.ORIGINAL)
        page = CleanPage("001", PageType.BODY)

        result = FinalStoryFileResolver().get_story_file(comic, page)

        comic.get_final_srce_story_file.assert_called_once_with("001", PageType.BODY)
        assert result == expected

    def test_wraps_non_str_return_value_in_path(self) -> None:
        comic = MagicMock()
        comic.get_final_srce_story_file.return_value = (Path("/p/2.jpg"), ModifiedType.MODIFIED)
        page = CleanPage("002", PageType.BODY)

        result = FinalStoryFileResolver().get_story_file(comic, page)

        assert isinstance(result, Path)
        assert result == Path("/p/2.jpg")


class TestSvgPngStoryFileResolver:
    def test_returns_png_when_file_exists(self) -> None:
        comic = MagicMock()
        png_path = MagicMock(spec=Path)
        png_path.is_file.return_value = True
        comic.get_srce_restored_svg_png_story_file.return_value = png_path
        page = CleanPage("003", PageType.BODY)

        result = SvgPngStoryFileResolver().get_story_file(comic, page)

        comic.get_srce_restored_svg_png_story_file.assert_called_once_with("003")
        assert result is png_path

    def test_raises_when_missing_and_no_fallback(self) -> None:
        comic = MagicMock()
        png_path = MagicMock(spec=Path)
        png_path.is_file.return_value = False
        comic.get_srce_restored_svg_png_story_file.return_value = png_path
        page = CleanPage("004", PageType.BODY)

        with pytest.raises(SrceStoryFileNotFoundError):
            SvgPngStoryFileResolver().get_story_file(comic, page)

    def test_missing_error_is_file_not_found_error(self) -> None:
        # Callers may catch the broader stdlib type — keep the inheritance contract.
        assert issubclass(SrceStoryFileNotFoundError, FileNotFoundError)

    def test_delegates_to_fallback_when_png_missing(self) -> None:
        comic = MagicMock()
        png_path = MagicMock(spec=Path)
        png_path.is_file.return_value = False
        comic.get_srce_restored_svg_png_story_file.return_value = png_path
        page = CleanPage("005", PageType.BODY)

        fallback = MagicMock(spec=SrceStoryFileResolver)
        fallback_path = Path("/fallback/005.jpg")
        fallback.get_story_file.return_value = fallback_path

        result = SvgPngStoryFileResolver(fallback=fallback).get_story_file(comic, page)

        fallback.get_story_file.assert_called_once_with(comic, page)
        assert result == fallback_path

    def test_fallback_not_called_when_png_exists(self) -> None:
        comic = MagicMock()
        png_path = MagicMock(spec=Path)
        png_path.is_file.return_value = True
        comic.get_srce_restored_svg_png_story_file.return_value = png_path
        page = CleanPage("006", PageType.BODY)

        fallback = MagicMock(spec=SrceStoryFileResolver)

        result = SvgPngStoryFileResolver(fallback=fallback).get_story_file(comic, page)

        fallback.get_story_file.assert_not_called()
        assert result is png_path


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
        page = CleanPage("001.jpg", PageType.BODY, 1)

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
        page = CleanPage("001.jpg", PageType.BODY, 1)

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
        page = CleanPage("001.jpg", PageType.BODY, 1)

        result = get_page_mod_type(comic, page)

        comic.get_final_srce_original_story_file.assert_called_once_with("001", PageType.BODY)
        assert result == ModifiedType.ORIGINAL

    def test_uses_page_num_not_filename_stem_for_multi_extension_paths(self) -> None:
        comic = MagicMock()
        comic.get_final_srce_story_file.return_value = (
            Path("/some/199.svg.png"),
            ModifiedType.MODIFIED,
        )
        page = CleanPage("/some/dir/199.svg.png", PageType.BODY, 199)

        result = get_page_mod_type(comic, page)

        assert result == ModifiedType.MODIFIED
        comic.get_final_srce_story_file.assert_called_once_with("199", PageType.BODY)


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


# ---------------------------------------------------------------------------
# _get_srce_and_dest_pages_in_order (front/body/back-matter section machine)
# ---------------------------------------------------------------------------


def _comic_with_pages(pages: list[OriginalPage]) -> MagicMock:
    comic = MagicMock()
    comic.page_images_in_order = pages
    return comic


class TestGetSrceAndDestPagesInOrder:
    def test_section_and_page_numbering_across_matter_transitions(self) -> None:
        """Front->body->back transitions each open a new dest file section.

        Dest filenames are ``<section>-<page-in-section>``: front matter is
        section 1, the first body page resets numbering into section 2, and the
        first back-matter page opens section 3. Body page numbers restart at 1.
        """
        comic = _comic_with_pages(
            [
                OriginalPage("100", PageType.FRONT),
                OriginalPage(TITLE_EMPTY_FILENAME, PageType.TITLE),
                OriginalPage("101", PageType.BODY),
                OriginalPage("102", PageType.BODY),
                OriginalPage("103", PageType.BACK_MATTER),
            ],
        )

        pages = _get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

        dest = pages.dest_pages
        assert [p.page_filename for p in dest] == [
            "1-00.jpg",
            "1-01.jpg",
            "2-01.jpg",
            "2-02.jpg",
            "3-01.jpg",
        ]
        # Front page is number 0; body restarts at 1; back matter continues (+1).
        assert [p.page_num for p in dest] == [0, 1, 1, 2, 3]
        assert [p.page_type for p in dest] == [
            PageType.FRONT,
            PageType.TITLE,
            PageType.BODY,
            PageType.BODY,
            PageType.BACK_MATTER,
        ]

    def test_srce_pages_keep_original_filenames_and_numbers(self) -> None:
        """Source pages carry the original relative filename and original page num."""
        comic = _comic_with_pages(
            [
                OriginalPage("100", PageType.FRONT),
                OriginalPage("101", PageType.BODY),
            ],
        )

        pages = _get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

        assert [p.page_filename for p in pages.srce_pages] == ["100.jpg", "101.jpg"]
        assert [p.page_num for p in pages.srce_pages] == [100, 101]

    def test_wrong_front_matter_page_type_raises(self) -> None:
        """A back-matter page seen while still in front matter is rejected."""
        comic = _comic_with_pages(
            [
                OriginalPage("100", PageType.FRONT),
                OriginalPage("101", PageType.BACK_MATTER),
            ],
        )

        with pytest.raises(ValueError, match="front matter but page type is incorrect"):
            _get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

    def test_wrong_back_matter_page_type_raises(self) -> None:
        """A front-matter page seen after the back matter has started is rejected."""
        comic = _comic_with_pages(
            [
                OriginalPage("100", PageType.FRONT),
                OriginalPage("101", PageType.BODY),
                OriginalPage("102", PageType.BACK_MATTER),
                OriginalPage(TITLE_EMPTY_FILENAME, PageType.TITLE),
            ],
        )

        with pytest.raises(ValueError, match="back matter but page type is incorrect"):
            _get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

    def test_full_paths_use_resolver_and_dest_image_dir(self) -> None:
        """With full paths, srce comes from the resolver and dest from the dest dir."""
        comic = _comic_with_pages(
            [
                OriginalPage("100", PageType.FRONT),
                OriginalPage("101", PageType.BODY),
            ],
        )
        comic.get_dest_image_dir.return_value = Path("/dest")
        resolver = MagicMock(spec=SrceStoryFileResolver)
        resolver.get_story_file.return_value = Path("/srce/restored.jpg")

        pages = _get_srce_and_dest_pages_in_order(
            comic, get_full_paths=True, srce_story_file_resolver=resolver
        )

        expected_srce = str(Path("/srce/restored.jpg"))
        assert [p.page_filename for p in pages.srce_pages] == [expected_srce, expected_srce]
        assert pages.dest_pages[0].page_filename == str(Path("/dest") / "1-00.jpg")
        assert pages.dest_pages[1].page_filename == str(Path("/dest") / "2-01.jpg")


# ---------------------------------------------------------------------------
# get_srce_dest_map
# ---------------------------------------------------------------------------


class TestGetSrceDestMap:
    def test_builds_dimension_and_page_map(self) -> None:
        """The map carries dir names, bbox dimensions, and a dest->srce page map."""
        comic = MagicMock()
        comic.dirs.srce_dir = "/root/my-srce-dir"
        comic.get_dest_rel_dirname.return_value = "dest-rel"
        srce_dim = ComicDimensions(
            min_panels_bbox_width=10,
            max_panels_bbox_width=20,
            min_panels_bbox_height=30,
            max_panels_bbox_height=40,
        )
        required_dim = RequiredDimensions(panels_bbox_width=100, panels_bbox_height=200)
        pages = SrceAndDestPages(
            srce_pages=[CleanPage("/a/101.jpg", PageType.BODY, 101)],
            dest_pages=[CleanPage("/b/2-01.jpg", PageType.BODY, 1)],
        )

        result = get_srce_dest_map(comic, srce_dim, required_dim, pages)

        assert result["srce_dirname"] == "my-srce-dir"
        assert result["dest_dirname"] == "dest-rel"
        assert result["srce_min_panels_bbox_width"] == 10
        assert result["dest_required_bbox_width"] == 100
        assert result["dest_required_bbox_height"] == 200
        assert result["pages"] == {"2-01.jpg": {"file": "101.jpg", "type": "BODY"}}
