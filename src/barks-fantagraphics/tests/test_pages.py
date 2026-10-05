# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics import pages as pages_module
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
    get_full_srce_filepath,
    get_max_timestamp,
    get_page_mod_type,
    get_page_number_str,
    get_relative_srce_filepath,
    get_required_pages_in_order,
    get_restored_srce_dependencies,
    get_sorted_srce_and_dest_pages,
    get_sorted_srce_and_dest_pages_with_dimensions,
    get_srce_and_dest_pages_in_order,
    get_srce_dest_map,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

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
# get_srce_and_dest_pages_in_order (front/body/back-matter section machine)
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

        pages = get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

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

        pages = get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

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
            get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

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
            get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

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

        pages = get_srce_and_dest_pages_in_order(
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


# ---------------------------------------------------------------------------
# get_restored_srce_dependencies: the chain the integrity checker grades
# ---------------------------------------------------------------------------


class TestGetRestoredSrceDependencies:
    """What a restored page is built from, in chain order, with each file's timestamp."""

    FILES = ("segments", "bounds", "restored", "upscayled", "svg", "upscayl", "original")

    @pytest.fixture
    def comic(self, tmp_path: Path) -> MagicMock:
        """Fake a comic whose every source file exists, each a second newer than the last."""
        files = {name: tmp_path / f"{name}.file" for name in (*self.FILES, "ini", "inset")}
        for mtime, file in enumerate(files.values(), start=1_000):
            file.write_text("x")
            os.utime(file, (mtime, mtime))
        comic = MagicMock()
        comic.files = files
        comic.ini_file = files["ini"]
        comic.intro_inset_file = files["inset"]
        comic.get_srce_panel_segments_file.return_value = files["segments"]
        comic.get_final_fixes_panel_bounds_file.return_value = files["bounds"]
        comic.get_final_srce_story_file.return_value = (files["restored"], ModifiedType.MODIFIED)
        comic.get_srce_restored_upscayled_story_file.return_value = files["upscayled"]
        comic.get_srce_restored_svg_story_file.return_value = files["svg"]
        comic.get_final_srce_upscayled_story_file.return_value = (
            files["upscayl"],
            ModifiedType.ORIGINAL,
        )
        comic.get_final_srce_original_story_file.return_value = (
            files["original"],
            ModifiedType.ADDED,
        )
        comic._is_added_fixes_special_case.return_value = False
        return comic

    @staticmethod
    def _deps(comic: MagicMock, page_type: PageType) -> list[SrceDependency]:
        return get_restored_srce_dependencies(comic, CleanPage("012.jpg", page_type, page_num=12))

    def test_a_blank_page_depends_on_nothing(self, comic: MagicMock) -> None:
        assert self._deps(comic, PageType.BLANK_PAGE) == []

    def test_a_title_page_depends_on_its_ini_and_inset(self, comic: MagicMock) -> None:
        deps = self._deps(comic, PageType.TITLE)
        assert [(d.file, d.independent) for d in deps] == [
            (comic.ini_file, True),
            (comic.intro_inset_file, True),
        ]
        assert deps[1].timestamp == comic.intro_inset_file.stat().st_mtime

    def test_a_title_page_with_no_inset_yet_is_not_an_error(self, comic: MagicMock) -> None:
        comic.intro_inset_file.unlink()
        assert self._deps(comic, PageType.TITLE)[1].timestamp == -1

    def test_a_body_page_is_the_whole_chain_in_order(self, comic: MagicMock) -> None:
        deps = self._deps(comic, PageType.BODY)
        assert [d.file for d in deps] == [comic.files[name] for name in self.FILES]
        # The bounds override is off the chain: segments come from it *and* the page.
        assert [d.independent for d in deps] == [False, True, False, False, False, False, False]
        assert [d.timestamp for d in deps] == [
            comic.files[name].stat().st_mtime for name in self.FILES
        ]
        assert (deps[2].mod_type, deps[5].mod_type, deps[6].mod_type) == (
            ModifiedType.MODIFIED,
            ModifiedType.ORIGINAL,
            ModifiedType.ADDED,
        )
        comic.get_srce_panel_segments_file.assert_called_once_with("012")

    def test_files_not_made_yet_have_the_not_on_disk_timestamp(self, comic: MagicMock) -> None:
        for name in ("segments", "upscayled", "svg", "upscayl", "original"):
            comic.files[name].unlink()
        deps = {d.file: d.timestamp for d in self._deps(comic, PageType.BODY)}
        assert [deps[comic.files[name]] for name in ("segments", "upscayled", "svg")] == [-1] * 3
        assert deps[comic.files["upscayl"]] == deps[comic.files["original"]] == -1

    def test_no_bounds_override_leaves_it_out(self, comic: MagicMock) -> None:
        comic.get_final_fixes_panel_bounds_file.return_value = None
        files = [d.file for d in self._deps(comic, PageType.BODY)]
        assert comic.files["bounds"] not in files
        assert len(files) == len(self.FILES) - 1

    def test_an_added_fixes_page_stops_at_the_restored_file(self, comic: MagicMock) -> None:
        """A page added in the fixes has no upscayled or original source behind it."""
        comic._is_added_fixes_special_case.return_value = True
        assert [d.file for d in self._deps(comic, PageType.BODY)] == [
            comic.files[name] for name in ("segments", "bounds", "restored")
        ]

    def test_a_page_that_is_not_restored_has_only_its_final_file(self, comic: MagicMock) -> None:
        assert [d.file for d in self._deps(comic, PageType.COVER)] == [comic.files["restored"]]


# ---------------------------------------------------------------------------
# Front matter numbered as an ordinary book, page times, and the sorted-pages wrappers
# ---------------------------------------------------------------------------


class TestArabicFrontMatter:
    def test_a_synthetic_collections_front_matter_is_numbered_in_arabic(self) -> None:
        """Its front matter runs to hundreds of pages; roman numerals stop at "x"."""
        page = CleanPage("001", PageType.FRONT_MATTER, 1, use_arabic_page_num=True)
        assert get_page_number_str(page, 214) == "214"


class TestGetMaxTimestamp:
    def test_it_is_the_newest_pages_file_time(self, tmp_path: Path) -> None:
        pages = []
        for name, mtime in (("001.jpg", 3_000), ("002.jpg", 5_000), ("003.jpg", 4_000)):
            file = tmp_path / name
            file.write_text("x")
            os.utime(file, (mtime, mtime))
            pages.append(CleanPage(str(file), PageType.BODY, 1))
        assert get_max_timestamp(pages) == 5_000


class TestSortedPagesWrappers:
    def test_the_sorted_pages_are_the_pages_in_order(self) -> None:
        comic, resolver = MagicMock(), MagicMock()
        with patch.object(pages_module, "get_srce_and_dest_pages_in_order") as in_order:
            result = get_sorted_srce_and_dest_pages(
                comic, get_full_paths=True, srce_story_file_resolver=resolver
            )
        assert in_order.call_args.args == (comic, True, resolver)
        assert result is in_order.return_value

    @pytest.fixture
    def geometry(self) -> Iterator[tuple[CleanPage, MagicMock]]:
        srce_page = CleanPage("005", PageType.BODY, 5)
        with (
            patch.object(
                pages_module,
                "get_srce_and_dest_pages_in_order",
                return_value=SrceAndDestPages([srce_page], []),
            ),
            patch.object(pages_module, "set_srce_panel_bounding_boxes") as set_srce_boxes,
            patch.object(
                pages_module,
                "get_required_panels_bbox_width_height",
                return_value=("srce dim", "required dim"),
            ),
            patch.object(pages_module, "set_dest_panel_bounding_boxes"),
        ):
            yield srce_page, set_srce_boxes

    def test_without_a_segments_file_getter_the_comics_own_is_used(
        self, geometry: tuple[CleanPage, MagicMock]
    ) -> None:
        srce_page, set_srce_boxes = geometry
        comic = MagicMock()

        _, srce_dim, required_dim = get_sorted_srce_and_dest_pages_with_dimensions(
            comic, get_full_paths=False
        )

        comic.get_srce_panel_segments_file.assert_called_once_with(pages_module.get_page_str(5))
        assert set_srce_boxes.call_args.args == (
            [srce_page],
            [comic.get_srce_panel_segments_file.return_value],
            True,
        )
        assert (srce_dim, required_dim) == ("srce dim", "required dim")

    def test_a_getter_given_is_used_instead(self, geometry: tuple[CleanPage, MagicMock]) -> None:
        _, set_srce_boxes = geometry
        comic = MagicMock()
        getter = MagicMock(return_value=Path("segments.json"))

        get_sorted_srce_and_dest_pages_with_dimensions(
            comic,
            get_full_paths=False,
            get_srce_panel_segments_file=getter,
            check_srce_page_timestamps=False,
        )

        comic.get_srce_panel_segments_file.assert_not_called()
        assert set_srce_boxes.call_args.args[1:] == ([Path("segments.json")], False)
