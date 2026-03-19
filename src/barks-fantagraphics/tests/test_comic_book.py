# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# noinspection PyProtectedMember
from barks_fantagraphics.comic_book import (
    ComicBook,
    ComicBookDirs,
    FixesType,
    ModifiedType,
    _get_lookup_title,
    _get_pages_in_order,
    get_abbrev_jpg_page_list,
    get_abbrev_jpg_page_of_type_list,
    get_has_front,
    get_jpg_page_list,
    get_jpg_page_of_type_list,
    get_main_publication_info,
    get_num_splashes,
    get_page_num_str,
    get_page_str,
    get_story_files,
    get_story_files_of_page_type,
    get_total_num_pages,
)
from barks_fantagraphics.comics_consts import (
    BOUNDED_SUBDIR,
    IMAGES_SUBDIR,
    JSON_METADATA_FILENAME,
    PageType,
)
from barks_fantagraphics.fanta_comics_info import FantaBook, FantaComicBookInfo
from barks_fantagraphics.page_classes import OriginalPage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fanta_book(volume: int = 1) -> FantaBook:
    return FantaBook(
        title="Carl Barks Vol 01",
        pub="Fantagraphics",
        volume=volume,
        year=2012,
        num_pages=280,
    )


def _make_comic_book_info(
    *,
    is_barks: bool = True,
    submitted_year: int = 1948,
) -> MagicMock:
    info = MagicMock()
    info.is_barks_title = is_barks
    info.submitted_day = 15
    info.submitted_month = 3
    info.submitted_year = submitted_year
    info.issue_name = 3  # index into ISSUE_NAME list → "Comics and Stories"
    info.issue_number = 91
    info.issue_month = 6
    info.issue_year = submitted_year
    info.get_formatted_title_from_issue_name.return_value = "FC #123"
    info.get_short_issue_title.return_value = "WDCS 91"
    return info


def _make_fanta_info(
    *,
    series_name: str = "WDCS",
    number_in_series: int = 1,
    chrono_number: int = 42,
    is_barks: bool = True,
    submitted_year: int = 1948,
    colorist: str = "Susan Daigle-Leach",
) -> FantaComicBookInfo:
    comic_book_info = _make_comic_book_info(
        is_barks=is_barks,
        submitted_year=submitted_year,
    )
    return FantaComicBookInfo(
        comic_book_info=comic_book_info,
        colorist=colorist,
        series_name=series_name,
        fantagraphics_volume="FANTA_01",
        number_in_series=number_in_series,
        fanta_chronological_number=chrono_number,
    )


def _make_dirs(base: Path = Path("/fake")) -> ComicBookDirs:
    return ComicBookDirs(
        srce_dir=base / "original",
        srce_upscayled_dir=base / "upscayled",
        srce_restored_dir=base / "restored",
        srce_restored_upscayled_dir=base / "restored-upscayled",
        srce_restored_svg_dir=base / "restored-svg",
        srce_restored_ocr_raw_dir=base / "ocr-raw",
        srce_restored_ocr_prelim_dir=base / "ocr-prelim",
        srce_restored_ocr_annotations_dir=base / "ocr-annotations",
        srce_fixes_dir=base / "fixes",
        srce_upscayled_fixes_dir=base / "upscayled-fixes",
        panel_segments_dir=base / "panel-segments",
    )


def _make_pages(*specs: tuple[str, PageType]) -> list[OriginalPage]:
    return [OriginalPage(page_filenames=s, page_type=t) for s, t in specs]


def _make_comic(
    *,
    title: str = "Test Title",
    issue_title: str = "",
    volume: int = 1,
    series_name: str = "WDCS",
    number_in_series: int = 1,
    chrono_number: int = 42,
    is_barks: bool = True,
    pages: list[OriginalPage] | None = None,
    base_dir: Path = Path("/fake"),
) -> ComicBook:
    if pages is None:
        pages = _make_pages(
            ("001", PageType.COVER),
            ("002", PageType.BODY),
            ("003", PageType.BODY),
        )
    fanta_info = _make_fanta_info(
        series_name=series_name,
        number_in_series=number_in_series,
        chrono_number=chrono_number,
        is_barks=is_barks,
    )
    return ComicBook(
        ini_file=Path(f"/ini/{title}.ini"),
        title=title,
        title_font_file=Path("/fonts/test.ttf"),
        title_font_size=155,
        issue_title=issue_title,
        author_font_size=90,
        srce_dir_num_page_files=len(pages),
        dirs=_make_dirs(base_dir),
        intro_inset_file=Path("/insets/test.png"),
        config_page_images=pages,
        page_images_in_order=_get_pages_in_order(pages),
        publication_date="June 1948",
        submitted_date="March 15, 1948",
        publication_text="Published in WDCS 91",
        fanta_book=_make_fanta_book(volume),
        fanta_info=fanta_info,
        solo_page_keys=frozenset(),
    )


# ---------------------------------------------------------------------------
# ComicBook properties
# ---------------------------------------------------------------------------


class TestComicBookProperties:
    def test_chronological_number(self) -> None:
        comic = _make_comic(chrono_number=99)
        assert comic.chronological_number == 99

    def test_submitted_year(self) -> None:
        comic = _make_comic()
        assert comic.submitted_year == 1948

    def test_series_name(self) -> None:
        comic = _make_comic(series_name="FC")
        assert comic.series_name == "FC"

    def test_number_in_series(self) -> None:
        comic = _make_comic(number_in_series=7)
        assert comic.number_in_series == 7

    def test_is_barks_title(self) -> None:
        comic = _make_comic(is_barks=True)
        assert comic.is_barks_title()

    def test_get_fanta_volume(self) -> None:
        comic = _make_comic(volume=5)
        assert comic.get_fanta_volume() == 5

    def test_get_ini_title(self) -> None:
        comic = _make_comic(title="The Victory Garden")
        assert comic.get_ini_title() == "The Victory Garden"

    def test_get_series_comic_title(self) -> None:
        comic = _make_comic(series_name="FC", number_in_series=12)
        assert comic.get_series_comic_title() == "FC 12"


class TestComicBookPostInit:
    def test_rejects_empty_series_name(self) -> None:
        with pytest.raises(AssertionError):
            _make_comic(series_name="")

    def test_rejects_zero_number_in_series(self) -> None:
        with pytest.raises(AssertionError):
            _make_comic(number_in_series=0)

    def test_rejects_barks_title_without_title(self) -> None:
        with pytest.raises(AssertionError):
            _make_comic(title="", is_barks=True)

    def test_non_barks_title_can_have_empty_title(self) -> None:
        comic = _make_comic(title="", is_barks=False, issue_title="FC #495")
        assert comic.title == ""


# ---------------------------------------------------------------------------
# Image directory methods
# ---------------------------------------------------------------------------


class TestImageDirMethods:
    def test_get_srce_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        assert comic.get_srce_image_dir() == Path("/root/original") / IMAGES_SUBDIR

    def test_get_srce_upscayled_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        assert comic.get_srce_upscayled_image_dir() == Path("/root/upscayled") / IMAGES_SUBDIR

    def test_get_srce_restored_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        assert comic.get_srce_restored_image_dir() == Path("/root/restored") / IMAGES_SUBDIR

    def test_get_srce_restored_upscayled_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        expected = Path("/root/restored-upscayled") / IMAGES_SUBDIR
        assert comic.get_srce_restored_upscayled_image_dir() == expected

    def test_get_srce_restored_svg_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        assert comic.get_srce_restored_svg_image_dir() == Path("/root/restored-svg") / IMAGES_SUBDIR

    def test_get_srce_original_fixes_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        assert comic.get_srce_original_fixes_image_dir() == Path("/root/fixes") / IMAGES_SUBDIR

    def test_get_srce_upscayled_fixes_image_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        expected = Path("/root/upscayled-fixes") / IMAGES_SUBDIR
        assert comic.get_srce_upscayled_fixes_image_dir() == expected

    def test_get_srce_original_fixes_bounded_dir(self) -> None:
        comic = _make_comic(base_dir=Path("/root"))
        expected = Path("/root/fixes") / IMAGES_SUBDIR / BOUNDED_SUBDIR
        assert comic.get_srce_original_fixes_bounded_dir() == expected


# ---------------------------------------------------------------------------
# Story file path methods
# ---------------------------------------------------------------------------


class TestStoryFilePaths:
    def test_get_srce_original_story_file(self) -> None:
        comic = _make_comic()
        result = comic.get_srce_original_story_file("042")
        assert result == comic.get_srce_image_dir() / "042.jpg"

    def test_get_srce_upscayled_story_file(self) -> None:
        comic = _make_comic()
        result = comic.get_srce_upscayled_story_file("042")
        assert result == comic.get_srce_upscayled_image_dir() / "042.png"

    def test_get_srce_restored_upscayled_story_file(self) -> None:
        comic = _make_comic()
        result = comic.get_srce_restored_upscayled_story_file("042")
        assert result == comic.get_srce_restored_upscayled_image_dir() / "042.png"

    def test_get_srce_restored_svg_story_file(self) -> None:
        comic = _make_comic()
        result = comic.get_srce_restored_svg_story_file("042")
        assert result == comic.get_srce_restored_svg_image_dir() / "042.svg"

    def test_get_srce_upscayled_fixes_story_file(self) -> None:
        comic = _make_comic()
        result = comic.get_srce_upscayled_fixes_story_file("042")
        assert result == comic.get_srce_upscayled_fixes_image_dir() / "042.png"

    def test_get_srce_panel_segments_file(self) -> None:
        comic = _make_comic()
        result = comic.get_srce_panel_segments_file("042")
        assert result == comic.dirs.panel_segments_dir / "042.json"

    def test_get_srce_restored_ocr_raw_story_file(self) -> None:
        comic = _make_comic()
        easy, paddle = comic._get_srce_restored_ocr_raw_story_file("042")
        assert easy == comic.dirs.srce_restored_ocr_raw_dir / "042.easyocr.json"
        assert paddle == comic.dirs.srce_restored_ocr_raw_dir / "042.paddleocr.json"


# ---------------------------------------------------------------------------
# Story file list methods
# ---------------------------------------------------------------------------


class TestStoryFileLists:
    def test_get_srce_original_story_files_filters_by_page_type(self) -> None:
        comic = _make_comic()
        files = comic.get_srce_original_story_files([PageType.COVER])
        assert len(files) == 1
        assert files[0].name == "001.jpg"

    def test_get_srce_original_story_files_body_pages(self) -> None:
        comic = _make_comic()
        files = comic.get_srce_original_story_files([PageType.BODY])
        assert len(files) == 2

    def test_get_srce_upscayled_story_files(self) -> None:
        comic = _make_comic()
        files = comic.get_srce_upscayled_story_files([PageType.BODY])
        assert all(f.suffix == ".png" for f in files)

    def test_get_srce_panel_segments_files(self) -> None:
        comic = _make_comic()
        files = comic.get_srce_panel_segments_files([PageType.COVER, PageType.BODY])
        assert len(files) == 3
        assert all(f.suffix == ".json" for f in files)


# ---------------------------------------------------------------------------
# Original fixes story file (filesystem-dependent)
# ---------------------------------------------------------------------------


class TestGetSrceOriginalFixesStoryFile:
    def test_returns_png_when_no_jpg(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        # Neither file exists — returns png path by default
        result = comic.get_srce_original_fixes_story_file("042")
        assert result.suffix == ".png"

    def test_returns_jpg_when_it_exists(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        jpg_path = comic.get_srce_original_fixes_image_dir() / "042.jpg"
        jpg_path.parent.mkdir(parents=True, exist_ok=True)
        jpg_path.touch()
        result = comic.get_srce_original_fixes_story_file("042")
        assert result == jpg_path

    def test_raises_when_both_jpg_and_png_exist(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        img_dir = comic.get_srce_original_fixes_image_dir()
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / "042.jpg").touch()
        (img_dir / "042.png").touch()
        with pytest.raises(RuntimeError, match="Cannot have both"):
            comic.get_srce_original_fixes_story_file("042")


# ---------------------------------------------------------------------------
# _get_final_story_file
# ---------------------------------------------------------------------------


class TestGetFinalStoryFile:
    def test_returns_primary_when_fixes_not_found(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        primary = tmp_path / "primary.jpg"
        fixes = tmp_path / "fixes.png"
        # Neither exists — fixes_file.is_file() is False
        result, mod = comic._get_final_story_file(
            FixesType.ORIGINAL, "042", PageType.BODY, primary, fixes
        )
        assert result == primary
        assert mod == ModifiedType.ORIGINAL

    def test_returns_modified_when_both_exist_and_story_type(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        primary = tmp_path / "primary.jpg"
        fixes = tmp_path / "fixes.png"
        primary.touch()
        fixes.touch()
        result, mod = comic._get_final_story_file(
            FixesType.ORIGINAL, "042", PageType.BODY, primary, fixes
        )
        assert result == fixes
        assert mod == ModifiedType.MODIFIED

    def test_raises_when_edited_non_story_type(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        primary = tmp_path / "primary.jpg"
        fixes = tmp_path / "fixes.png"
        primary.touch()
        fixes.touch()
        with pytest.raises(RuntimeError, match="EDITED"):
            comic._get_final_story_file(FixesType.ORIGINAL, "042", PageType.SPLASH, primary, fixes)

    def test_returns_added_when_primary_missing_and_non_story_type(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        primary = tmp_path / "primary.jpg"
        fixes = tmp_path / "fixes.png"
        fixes.touch()
        # primary does NOT exist, non-story page type
        result, mod = comic._get_final_story_file(
            FixesType.ORIGINAL, "042", PageType.SPLASH, primary, fixes
        )
        assert result == fixes
        assert mod == ModifiedType.ADDED

    def test_raises_when_added_file_has_story_type(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        primary = tmp_path / "primary.jpg"
        fixes = tmp_path / "fixes.png"
        fixes.touch()
        with pytest.raises(RuntimeError, match="ADDED"):
            comic._get_final_story_file(FixesType.ORIGINAL, "042", PageType.BODY, primary, fixes)


# ---------------------------------------------------------------------------
# get_final_srce_story_file
# ---------------------------------------------------------------------------


class TestGetFinalSrceStoryFile:
    def test_title_page_returns_placeholder(self) -> None:
        comic = _make_comic()
        path, mod = comic.get_final_srce_story_file("001", PageType.TITLE)
        assert path == Path("TITLE PAGE")
        assert mod == ModifiedType.ORIGINAL

    def test_blank_page_returns_placeholder(self) -> None:
        comic = _make_comic()
        path, mod = comic.get_final_srce_story_file("001", PageType.BLANK_PAGE)
        assert path == Path("EMPTY PAGE")
        assert mod == ModifiedType.ORIGINAL

    def test_restorable_page_uses_restored_file(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        restored_file = comic._get_srce_restored_story_file("002")
        restored_file.parent.mkdir(parents=True, exist_ok=True)
        restored_file.touch()

        with patch.object(
            type(comic),
            "get_ini_title",
            return_value="Some Non-Hand-Restored Title",
        ):
            path, mod = comic.get_final_srce_story_file("002", PageType.BODY)
        assert path == restored_file
        assert mod == ModifiedType.ORIGINAL

    def test_restorable_page_raises_when_restored_missing(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        with (
            patch.object(
                type(comic),
                "get_ini_title",
                return_value="Some Non-Hand-Restored Title",
            ),
            pytest.raises(FileNotFoundError, match="Could not find restored"),
        ):
            comic.get_final_srce_story_file("002", PageType.BODY)

    def test_restorable_page_raises_when_jpg_found(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        jpg_file = comic.get_srce_restored_image_dir() / "002.jpg"
        jpg_file.parent.mkdir(parents=True, exist_ok=True)
        jpg_file.touch()

        with (
            patch.object(
                type(comic),
                "get_ini_title",
                return_value="Some Non-Hand-Restored Title",
            ),
            pytest.raises(RuntimeError, match="should be png not jpg"),
        ):
            comic.get_final_srce_story_file("002", PageType.BODY)


# ---------------------------------------------------------------------------
# is_fixes_special_case / is_fixes_special_case_added
# ---------------------------------------------------------------------------


class TestFixesSpecialCases:
    def test_vol16_page_209_is_special(self) -> None:
        assert ComicBook.is_fixes_special_case(16, "209")

    def test_vol4_page_227_is_special(self) -> None:
        assert ComicBook.is_fixes_special_case(4, "227")

    def test_normal_case_not_special(self) -> None:
        assert not ComicBook.is_fixes_special_case(1, "001")

    def test_added_vol7_page_240(self) -> None:
        assert ComicBook.is_fixes_special_case_added(7, "240")

    def test_added_vol7_page_241(self) -> None:
        assert ComicBook.is_fixes_special_case_added(7, "241")

    def test_added_vol16_page_235(self) -> None:
        assert ComicBook.is_fixes_special_case_added(16, "235")

    def test_added_vol1_page_268(self) -> None:
        assert ComicBook.is_fixes_special_case_added(1, "268")

    def test_added_vol2_range_252_to_261(self) -> None:
        for page in range(252, 262):
            assert ComicBook.is_fixes_special_case_added(2, str(page))

    def test_added_vol7_range_260_to_266(self) -> None:
        for page in range(260, 267):
            assert ComicBook.is_fixes_special_case_added(7, str(page))

    def test_added_normal_case(self) -> None:
        assert not ComicBook.is_fixes_special_case_added(1, "001")


class TestIsEditedFixesSpecialCase:
    def test_vol16_page_209(self) -> None:
        comic = _make_comic(volume=16)
        assert comic._is_edited_fixes_special_case("209")

    def test_not_special(self) -> None:
        comic = _make_comic(volume=1)
        assert not comic._is_edited_fixes_special_case("001")


class TestIsAddedFixesSpecialCase:
    def test_delegates_to_static(self) -> None:
        comic = _make_comic(volume=7)
        assert comic._is_added_fixes_special_case("240", PageType.BODY)

    def test_censored_title_body_page(self) -> None:
        comic = _make_comic()
        with patch.object(
            type(comic),
            "get_ini_title",
            return_value="Good Deeds",
        ):
            assert comic._is_added_fixes_special_case("999", PageType.BODY)

    def test_censored_title_non_body_page(self) -> None:
        comic = _make_comic()
        with patch.object(
            type(comic),
            "get_ini_title",
            return_value="Good Deeds",
        ):
            assert not comic._is_added_fixes_special_case("999", PageType.COVER)


# ---------------------------------------------------------------------------
# get_comic_title / get_comic_issue_title / get_title_with_issue_num
# ---------------------------------------------------------------------------


class TestTitleMethods:
    def test_get_comic_title_uses_title_when_set(self) -> None:
        comic = _make_comic(title="Lost in the Andes")
        assert comic.get_comic_title() == "Lost in the Andes"

    def test_get_comic_title_falls_back_to_issue_title(self) -> None:
        comic = _make_comic(title="", issue_title="FC #495", is_barks=False)
        assert comic.get_comic_title() == "FC #495"

    def test_get_comic_title_falls_back_to_formatted(self) -> None:
        comic = _make_comic(title="", issue_title="", is_barks=False)
        assert comic.get_comic_title() == "FC #123"

    def test_get_comic_issue_title(self) -> None:
        comic = _make_comic()
        # get_short_issue_title delegates to comic_book_info mock
        assert comic.get_comic_issue_title() == "WDCS 91"


# ---------------------------------------------------------------------------
# Destination path methods
# ---------------------------------------------------------------------------


class TestDestPaths:
    def test_get_dest_image_dir(self) -> None:
        comic = _make_comic()
        result = comic.get_dest_image_dir()
        assert result.name == IMAGES_SUBDIR

    def test_get_metadata_filepath(self) -> None:
        comic = _make_comic()
        result = comic.get_metadata_filepath()
        assert result.name == JSON_METADATA_FILENAME

    def test_get_dest_comic_zip_filename(self) -> None:
        comic = _make_comic(title="Test")
        result = comic.get_dest_comic_zip_filename()
        assert result.endswith(".cbz")


# ---------------------------------------------------------------------------
# Module-level functions
# ---------------------------------------------------------------------------


class TestGetLookupTitle:
    def test_uses_title_when_non_empty(self) -> None:
        result = _get_lookup_title("Lost in the Andes", "file_title")
        assert "Lost" in result

    def test_uses_file_title_when_title_empty(self) -> None:
        result = _get_lookup_title("", "file_title")
        assert result == "file_title"

    def test_asserts_on_both_empty(self) -> None:
        with pytest.raises(AssertionError):
            _get_lookup_title("", "")


class TestGetPagesInOrder:
    def test_single_page(self) -> None:
        pages = _make_pages(("042", PageType.BODY))
        result = _get_pages_in_order(pages)
        assert len(result) == 1
        assert result[0].page_filenames == "042"

    def test_range_expansion(self) -> None:
        pages = _make_pages(("10-13", PageType.BODY))
        result = _get_pages_in_order(pages)
        assert len(result) == 4
        assert [p.page_filenames for p in result] == ["010", "011", "012", "013"]
        assert all(p.page_type == PageType.BODY for p in result)

    def test_mixed_single_and_range(self) -> None:
        pages = _make_pages(
            ("001", PageType.COVER),
            ("2-4", PageType.BODY),
            ("005", PageType.BACK_MATTER),
        )
        result = _get_pages_in_order(pages)
        assert len(result) == 5


class TestGetPageStr:
    def test_zero_pads_to_three(self) -> None:
        assert get_page_str(1) == "001"
        assert get_page_str(42) == "042"
        assert get_page_str(999) == "999"

    def test_four_digits(self) -> None:
        assert get_page_str(1000) == "1000"


class TestGetPageNumStr:
    def test_returns_stem(self) -> None:
        assert get_page_num_str(Path("042.jpg")) == "042"
        assert get_page_num_str(Path("/some/dir/page.png")) == "page"


class TestGetStoryFiles:
    def test_returns_correct_paths(self) -> None:
        comic = _make_comic()
        image_dir = Path("/out")
        files = get_story_files(image_dir, comic, ".png")
        # COVER + 2 BODY = 3 story pages
        assert len(files) == 3
        assert files[0] == Path("/out/001.png")


class TestGetStoryFilesOfPageType:
    def test_filters_by_type(self) -> None:
        comic = _make_comic()
        files = get_story_files_of_page_type(Path("/out"), comic, ".png", [PageType.COVER])
        assert len(files) == 1


class TestPageListFunctions:
    def test_get_abbrev_jpg_page_list(self) -> None:
        comic = _make_comic()
        result = get_abbrev_jpg_page_list(comic)
        assert result == ["001", "002", "003"]

    def test_get_abbrev_jpg_page_of_type_list(self) -> None:
        comic = _make_comic()
        result = get_abbrev_jpg_page_of_type_list(comic, [PageType.COVER])
        assert result == ["001"]

    def test_get_jpg_page_list(self) -> None:
        comic = _make_comic()
        result = get_jpg_page_list(comic)
        assert result == ["001", "002", "003"]

    def test_get_jpg_page_of_type_list(self) -> None:
        comic = _make_comic()
        result = get_jpg_page_of_type_list(comic, [PageType.BODY])
        assert result == ["002", "003"]


class TestGetHasFront:
    def test_true_when_first_page_is_front(self) -> None:
        pages = _make_pages(
            ("001", PageType.FRONT),
            ("002", PageType.BODY),
        )
        comic = _make_comic(pages=pages)
        assert get_has_front(comic)

    def test_false_when_first_page_is_not_front(self) -> None:
        comic = _make_comic()
        assert not get_has_front(comic)


class TestGetNumSplashes:
    def test_counts_splash_pages(self) -> None:
        pages = _make_pages(
            ("001", PageType.SPLASH),
            ("002", PageType.SPLASH),
            ("003", PageType.BODY),
        )
        comic = _make_comic(pages=pages)
        assert get_num_splashes(comic) == 2

    def test_zero_splashes(self) -> None:
        comic = _make_comic()
        assert get_num_splashes(comic) == 0


class TestGetTotalNumPages:
    def test_counts_all_pages(self) -> None:
        comic = _make_comic()
        assert get_total_num_pages(comic) == 3


# ---------------------------------------------------------------------------
# get_main_publication_info
# ---------------------------------------------------------------------------


class TestGetMainPublicationInfo:
    @staticmethod
    def _make_info_mocks(
        file_title: str = "Regular Title",
    ) -> tuple[str, FantaComicBookInfo, FantaBook]:
        fanta_info = _make_fanta_info()
        fanta_book = _make_fanta_book()
        return file_title, fanta_info, fanta_book

    def test_regular_title_includes_first_published(self) -> None:
        file_title, fanta_info, fanta_book = self._make_info_mocks()
        result = get_main_publication_info(file_title, fanta_info, fanta_book)
        assert "First published in" in result
        assert "Submitted to Western Publishing" in result
        assert "Fantagraphics" in result

    def test_silent_night_special_text(self) -> None:
        file_title, fanta_info, fanta_book = self._make_info_mocks("Silent Night")
        result = get_main_publication_info(file_title, fanta_info, fanta_book)
        assert "Rejected by Western editors in 1945" in result

    def test_milkman_special_text(self) -> None:
        file_title, fanta_info, fanta_book = self._make_info_mocks("The Milkman")
        result = get_main_publication_info(file_title, fanta_info, fanta_book)
        assert "Rejected by Western editors in 1957" in result
        assert "Color restoration by" in result

    def test_good_deeds_no_fanta_pub_info(self) -> None:
        file_title, fanta_info, fanta_book = self._make_info_mocks("Good Deeds")
        result = get_main_publication_info(file_title, fanta_info, fanta_book)
        assert "First published in" in result
        assert "Fantagraphics" not in result


# ---------------------------------------------------------------------------
# get_final_fixes_panel_bounds_file
# ---------------------------------------------------------------------------


class TestGetFinalFixesPanelBoundsFile:
    def test_returns_none_when_missing(self) -> None:
        comic = _make_comic()
        assert comic.get_final_fixes_panel_bounds_file(42) is None

    def test_returns_path_when_exists(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        bounds_dir = comic.get_srce_original_fixes_bounded_dir()
        bounds_dir.mkdir(parents=True, exist_ok=True)
        bounds_file = bounds_dir / "042.jpg"
        bounds_file.touch()
        result = comic.get_final_fixes_panel_bounds_file(42)
        assert result == bounds_file


# ---------------------------------------------------------------------------
# get_story_file_sources
# ---------------------------------------------------------------------------


class TestGetStoryFileSources:
    def test_empty_when_no_files_exist(self) -> None:
        comic = _make_comic()
        sources = comic.get_story_file_sources("042")
        assert sources == []

    def test_includes_restored_when_exists(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        restored = comic._get_srce_restored_story_file("042")
        restored.parent.mkdir(parents=True, exist_ok=True)
        restored.touch()
        sources = comic.get_story_file_sources("042")
        assert restored in sources

    def test_includes_original_when_exists(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        original = comic.get_srce_original_story_file("042")
        original.parent.mkdir(parents=True, exist_ok=True)
        original.touch()
        sources = comic.get_story_file_sources("042")
        assert original in sources

    def test_prefers_fixes_over_original(self, tmp_path: Path) -> None:
        comic = _make_comic(base_dir=tmp_path)
        original = comic.get_srce_original_story_file("042")
        original.parent.mkdir(parents=True, exist_ok=True)
        original.touch()
        # Create a png fixes file
        fixes_dir = comic.get_srce_original_fixes_image_dir()
        fixes_dir.mkdir(parents=True, exist_ok=True)
        fixes_file = fixes_dir / "042.png"
        fixes_file.touch()
        sources = comic.get_story_file_sources("042")
        assert fixes_file in sources
        assert original not in sources
