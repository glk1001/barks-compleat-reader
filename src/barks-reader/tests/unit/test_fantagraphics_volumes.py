# ruff: noqa: SLF001, PLR2004

from pathlib import Path

import pytest
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    FantagraphicsArchive,
    FantagraphicsVolumeArchives,
    MissingArchiveFilesError,
    PageNumError,
    TooManyArchiveFilesError,
)


@pytest.fixture
def archives() -> FantagraphicsVolumeArchives:
    return FantagraphicsVolumeArchives(
        archive_root=Path("/fake/archives"),
        override_root=Path("/fake/overrides"),
        volume_list=list(range(1, 30)),
    )


class TestGetFantaVolume:
    def test_extracts_volume_from_filename(self) -> None:
        assert FantagraphicsVolumeArchives._get_fanta_volume(Path("07 - Volume Seven.cbz")) == 7

    def test_extracts_multi_digit_volume(self) -> None:
        assert FantagraphicsVolumeArchives._get_fanta_volume(Path("25-volume.cbz")) == 25

    def test_raises_for_no_leading_digits(self) -> None:
        with pytest.raises(ValueError, match="Could not find"):
            FantagraphicsVolumeArchives._get_fanta_volume(Path("volume-seven.cbz"))


class TestExtractImageInt:
    def test_extracts_trailing_integer(self) -> None:
        assert FantagraphicsVolumeArchives._extract_image_int("page042") == 42

    def test_extracts_from_numeric_only(self) -> None:
        assert FantagraphicsVolumeArchives._extract_image_int("123") == 123

    def test_raises_for_no_trailing_integer(self) -> None:
        with pytest.raises(ValueError, match="does not have an integer suffix"):
            FantagraphicsVolumeArchives._extract_image_int("no_number_here")


class TestCheckImageNames:
    def test_raises_when_first_is_negative(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(ValueError, match="First page should be >= 0"):
            archives._check_image_names(["page-1.png"], first=-1, last=5, img_ext=".png")

    def test_raises_when_first_equals_last(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(ValueError, match=r"First page .* should be <"):
            archives._check_image_names(["page5.png"], first=5, last=5, img_ext=".png")

    def test_raises_when_first_greater_than_last(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        with pytest.raises(ValueError, match=r"First page .* should be <"):
            archives._check_image_names(["page10.png"], first=10, last=5, img_ext=".png")

    def test_raises_on_page_number_mismatch(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(PageNumError, match="Expecting page 1 but got 2"):
            archives._check_image_names(["page2.png", "page3.png"], first=1, last=2, img_ext=".png")

    def test_raises_on_extension_mismatch(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(RuntimeError, match=r'expecting extension "\.png" but got "\.jpg"'):
            archives._check_image_names(["page1.jpg", "page2.jpg"], first=1, last=2, img_ext=".png")

    def test_passes_for_valid_images(self, archives: FantagraphicsVolumeArchives) -> None:
        archives._check_image_names(
            ["page1.png", "page2.png", "page3.png"], first=1, last=3, img_ext=".png"
        )


class TestCheckCorrectVolumeNumbers:
    def test_raises_too_many_for_volume_exceeding_max(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        # Create filenames with a volume number > LAST_VOLUME_NUMBER (29)
        filenames = [Path(f"{i}-vol.cbz") for i in range(1, 30)] + [Path("999-extra.cbz")]
        with pytest.raises(TooManyArchiveFilesError):
            archives.check_correct_volume_numbers(filenames)

    def test_raises_duplicate_for_repeated_volumes(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        filenames = [Path(f"{i}-vol.cbz") for i in range(1, 30)]
        filenames.append(Path("5-duplicate.cbz"))
        with pytest.raises(DuplicateArchiveFilesError):
            archives.check_correct_volume_numbers(filenames)

    def test_raises_missing_for_gaps(self, archives: FantagraphicsVolumeArchives) -> None:
        # Missing volumes 15 and 20
        filenames = [Path(f"{i}-vol.cbz") for i in range(1, 30) if i not in (15, 20)]
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers(filenames)
        assert 15 in exc_info.value.missing_file_vols
        assert 20 in exc_info.value.missing_file_vols

    def test_passes_for_complete_set(self, archives: FantagraphicsVolumeArchives) -> None:
        filenames = [Path(f"{i}-vol.cbz") for i in range(1, 30)]
        archives.check_correct_volume_numbers(filenames)


class TestFantagraphicsArchive:
    def test_get_num_pages(self) -> None:
        archive = FantagraphicsArchive(
            fanta_volume=1,
            archive_filename=Path("1-vol.cbz"),
            archive_image_subdir=Path("images"),
            image_ext=".png",
            first_page=3,
            last_page=10,
            archive_images_page_map={},
            override_images_page_map={},
            extra_images_page_map={},
            override_archive_filename=None,
        )
        assert archive.get_num_pages() == 8

    def test_has_overrides_true_with_override_map(self) -> None:
        archive = FantagraphicsArchive(
            fanta_volume=1,
            archive_filename=Path("1-vol.cbz"),
            archive_image_subdir=Path("images"),
            image_ext=".png",
            first_page=1,
            last_page=5,
            archive_images_page_map={},
            override_images_page_map={"003": Path("003.png")},
            extra_images_page_map={},
            override_archive_filename=None,
        )
        assert archive.has_overrides() is True

    def test_has_overrides_true_with_extra_map(self) -> None:
        archive = FantagraphicsArchive(
            fanta_volume=1,
            archive_filename=Path("1-vol.cbz"),
            archive_image_subdir=Path("images"),
            image_ext=".png",
            first_page=1,
            last_page=5,
            archive_images_page_map={},
            override_images_page_map={},
            extra_images_page_map={"099": Path("099.png")},
            override_archive_filename=None,
        )
        assert archive.has_overrides() is True

    def test_has_overrides_false_when_empty(self) -> None:
        archive = FantagraphicsArchive(
            fanta_volume=1,
            archive_filename=Path("1-vol.cbz"),
            archive_image_subdir=Path("images"),
            image_ext=".png",
            first_page=1,
            last_page=5,
            archive_images_page_map={},
            override_images_page_map={},
            extra_images_page_map={},
            override_archive_filename=None,
        )
        assert archive.has_overrides() is False


class TestGetArchiveImagePageMap:
    def test_page_map_first_is_one(self) -> None:
        result = FantagraphicsVolumeArchives._get_archive_image_page_map(
            image_subdir=Path("imgs"),
            img_filenames=["page1.png", "page2.png", "page3.png"],
            first=1,
            last=3,
        )
        # When first == 1, page_inc == 0, so keys are 001, 002, 003
        assert "001" in result
        assert "002" in result
        assert "003" in result
        assert result["001"] == Path("imgs/page1.png")

    def test_page_map_first_is_zero(self) -> None:
        result = FantagraphicsVolumeArchives._get_archive_image_page_map(
            image_subdir=Path("imgs"),
            img_filenames=["page0.png", "page1.png", "page2.png"],
            first=0,
            last=2,
        )
        # When first == 0, page_inc == 1, so keys are 001, 002, 003
        assert "001" in result
        assert "002" in result
        assert "003" in result
        assert result["001"] == Path("imgs/page0.png")
