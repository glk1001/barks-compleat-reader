# ruff: noqa: SLF001, PLR2004

import zipfile
from pathlib import Path

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.fanta_comics_info import NUM_VOLUMES
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    FantagraphicsArchive,
    FantagraphicsVolumeArchives,
    MissingArchiveFilesError,
    MissingVolumeError,
    NotEnoughOverrideDirsError,
    PageExtError,
    PageNumError,
    TooManyArchiveFilesError,
    TooManyOverrideDirsError,
)


def _make_volume_zip(path: Path, image_names: list[str], subdir: str = "images") -> Path:
    """Write a minimal cbz at `path` containing `subdir/<name>` for each image."""
    with zipfile.ZipFile(path, "w") as zf:
        for name in image_names:
            zf.writestr(f"{subdir}/{name}", b"\x89PNG\r\n")
    return path


def _make_override_zip(path: Path, image_names: list[str]) -> Path:
    """Write an override cbz: images live at the archive root, no subdir."""
    with zipfile.ZipFile(path, "w") as zf:
        for name in image_names:
            zf.writestr(name, b"\x89PNG\r\n")
    return path


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

    def test_raises_missing_for_empty_list(self, archives: FantagraphicsVolumeArchives) -> None:
        # An empty archive dir must not IndexError; it means every volume is missing.
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers([])
        assert 1 in exc_info.value.missing_file_vols
        assert NUM_VOLUMES in exc_info.value.missing_file_vols


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


class TestExceptionMessages:
    def test_missing_archive_files_error_singular(self) -> None:
        err = MissingArchiveFilesError([7], Path("/archives"))
        assert "volume missing" in str(err)
        assert "'7'" in str(err)

    def test_missing_archive_files_error_plural(self) -> None:
        err = MissingArchiveFilesError([7, 12], Path("/archives"))
        assert "volumes missing" in str(err)
        assert "7, 12" in str(err)

    def test_missing_volume_error_includes_title_and_volume(self) -> None:
        title = Titles.VACATION_TIME
        err = MissingVolumeError(missing_vol=14, title=title)
        msg = str(err)
        assert ENUM_TO_STR_TITLE[title] in msg
        assert "14" in msg
        assert err.missing_vol == 14
        assert err.title is title

    def test_not_enough_override_dirs_error_message(self) -> None:
        root = Path("/over")
        err = NotEnoughOverrideDirsError(
            num_override_dirs=2, num_volumes=29, override_dirs_root=root
        )
        msg = str(err)
        assert "not enough override dirs" in msg
        assert str(root) in msg  # Path separator varies by OS.
        assert "2" in msg
        assert "29" in msg

    def test_too_many_override_dirs_error_message(self) -> None:
        err = TooManyOverrideDirsError(
            num_override_dirs=50, num_volumes=29, override_dirs_root=Path("/over")
        )
        msg = str(err)
        assert "too many override dirs" in msg
        assert "50" in msg


class TestAccessors:
    def test_get_volume_list_returns_configured_list(self) -> None:
        archives = FantagraphicsVolumeArchives(
            archive_root=Path("/a"),
            override_root=Path("/o"),
            volume_list=[3, 5, 7],
        )
        assert archives.get_volume_list() == [3, 5, 7]

    def test_get_fantagraphics_archive_returns_loaded_entry(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        sentinel = FantagraphicsArchive(
            fanta_volume=4,
            archive_filename=Path("4.cbz"),
            archive_image_subdir=Path("imgs"),
            image_ext=".png",
            first_page=1,
            last_page=2,
            archive_images_page_map={},
            override_images_page_map={},
            extra_images_page_map={},
            override_archive_filename=None,
        )
        archives._fantagraphics_archive_dict[4] = sentinel
        assert archives.get_fantagraphics_archive(4) is sentinel


class TestCheckArchivesAndOverrides:
    def test_raises_too_many_override_dirs(self, archives: FantagraphicsVolumeArchives) -> None:
        archive_filenames = [Path(f"{i}-v.cbz") for i in range(1, 30)]
        too_many = {i: Path(f"{i}-ov.cbz") for i in range(1, NUM_VOLUMES + 2)}
        with pytest.raises(TooManyOverrideDirsError):
            archives.check_archives_and_overrides(archive_filenames, too_many)


class TestDirectoryScanning:
    def test_get_all_volume_filenames_filters_extensions_and_volume_list(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "01-a.cbz").touch()
        (tmp_path / "02-b.zip").touch()
        (tmp_path / "notvol.cbz").touch()  # ValueError on _get_fanta_volume → skipped
        (tmp_path / "99-out-of-list.cbz").touch()  # outside volume_list → skipped
        (tmp_path / "readme.txt").touch()  # wrong extension → skipped

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path,
            override_root=tmp_path,
            volume_list=[1, 2],
        )
        found = sorted(archives.get_all_volume_filenames(), key=lambda p: p.name)

        assert found == [tmp_path / "01-a.cbz", tmp_path / "02-b.zip"]

    def test_get_all_volume_filenames_returns_empty_for_missing_root(self) -> None:
        # An unset/vanished library dir must not raise; it scans as empty.
        archives = FantagraphicsVolumeArchives(
            archive_root=Path("/nonexistent/library/root"),
            override_root=Path("/fake/overrides"),
            volume_list=list(range(1, 30)),
        )
        assert archives.get_all_volume_filenames() == []

    def test_get_all_volume_override_archives_returns_map(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        (override_root / "01-x.cbz").touch()
        (override_root / "02-y.cbz").touch()

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=[1, 2, 3],
        )
        result = archives.get_all_volume_override_archives()

        assert set(result.keys()) == {1, 2}
        assert result[1] == override_root / "01-x.cbz"
        assert result[2] == override_root / "02-y.cbz"

    def test_get_all_volume_override_archives_raises_on_directory_entry(
        self, tmp_path: Path
    ) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        (override_root / "unexpected_subdir").mkdir()

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=[1],
        )
        with pytest.raises(FileExistsError, match="Unexpected override archive directory"):
            archives.get_all_volume_override_archives()


class TestGetArchiveContents:
    def test_extracts_subdir_and_image_list_sorted(self, tmp_path: Path) -> None:
        zip_path = _make_volume_zip(
            tmp_path / "01-vol.cbz",
            image_names=["page002.png", "page001.png", "page003.png"],
        )

        subdir, image_filenames = FantagraphicsVolumeArchives._get_archive_contents(zip_path)

        assert subdir == Path("images")
        assert image_filenames == ["page001.png", "page002.png", "page003.png"]

    def test_excludes_non_image_entries(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "01-vol.cbz"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("images/page001.png", b"\x89PNG\r\n")
            zf.writestr("images/page002.png", b"\x89PNG\r\n")
            zf.writestr("images/metadata.xml", b"<root/>")
            zf.writestr("images/notes.txt", b"hello")

        _subdir, image_filenames = FantagraphicsVolumeArchives._get_archive_contents(zip_path)

        assert image_filenames == ["page001.png", "page002.png"]


class TestGetFirstAndLastPageNums:
    def test_first_and_last_extracted_from_filenames(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        first, last = archives._get_first_and_last_page_nums(
            ["page001.png", "page002.png", "page005.png"]
        )
        assert (first, last) == (1, 5)


class TestOverrideAndExtraMap:
    def test_returns_empty_when_no_override_archive(self) -> None:
        overrides, extras = FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
            override_archive_filename=None,
            archive_page_map={"003": Path("images/page003.png")},
        )
        assert overrides == {}
        assert extras == {}

    def test_classifies_overrides_vs_extras(self, tmp_path: Path) -> None:
        override_zip = _make_override_zip(
            tmp_path / "01-ov.cbz",
            image_names=["003.png", "099.png"],
        )
        archive_page_map = {"003": Path("images/page003.png")}

        overrides, extras = FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
            override_archive_filename=override_zip,
            archive_page_map=archive_page_map,
        )

        assert overrides == {"003": Path("003.png")}
        assert extras == {"099": Path("099.png")}

    def test_raises_on_duplicate_override_page(self, tmp_path: Path) -> None:
        override_zip = _make_override_zip(
            tmp_path / "01-ov.cbz",
            image_names=["003.png", "003.jpg"],
        )
        with pytest.raises(RuntimeError, match="Cannot have jpg and png override"):
            FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
                override_archive_filename=override_zip,
                archive_page_map={"003": Path("images/page003.png")},
            )

    def test_raises_on_duplicate_extra_page(self, tmp_path: Path) -> None:
        override_zip = _make_override_zip(
            tmp_path / "01-ov.cbz",
            image_names=["099.png", "099.jpg"],
        )
        with pytest.raises(RuntimeError, match="Cannot have jpg and png override"):
            FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
                override_archive_filename=override_zip,
                archive_page_map={"003": Path("images/page003.png")},
            )


class TestLoadEndToEnd:
    def test_populates_archive_dict_for_complete_volume_set(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()

        for vol in range(1, NUM_VOLUMES + 1):
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz",
                image_names=["page001.png", "page002.png"],
            )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        archives.load()

        for vol in range(1, NUM_VOLUMES + 1):
            entry = archives.get_fantagraphics_archive(vol)
            assert entry.is_missing is False
            assert entry.fanta_volume == vol
            assert entry.first_page == 1
            assert entry.last_page == 2

    def test_marks_missing_volumes_and_then_raises(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()

        # Write all volumes except #2.
        for vol in range(1, NUM_VOLUMES + 1):
            if vol == 2:
                continue
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz",
                image_names=["page001.png", "page002.png"],
            )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.load()

        assert 2 in exc_info.value.missing_file_vols
        # The placeholder entry for the missing volume was registered before raising.
        missing_entry = archives.get_fantagraphics_archive(2)
        assert missing_entry.is_missing is True
        assert missing_entry.fanta_volume == 2

    def test_missing_volumes_still_expose_bundled_extra_pages(self, tmp_path: Path) -> None:
        # An existing-but-empty library dir plus bundled override zips: every volume is
        # missing, but each override zip's pages are still mapped as "extra" pages, so
        # fully-bundled stories (the restored censored ones) remain readable.
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()  # exists but holds no library volumes
        override_root.mkdir()

        _make_override_zip(
            override_root / "01-override.cbz",
            image_names=["258.png", "259.png", "267.png"],
        )
        _make_override_zip(override_root / "03-override.cbz", image_names=["250.png", "260.png"])

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        with pytest.raises(MissingArchiveFilesError):
            archives.load()

        vol1 = archives.get_fantagraphics_archive(1)
        assert vol1.is_missing is True
        assert set(vol1.extra_images_page_map) == {"258", "259", "267"}
        assert vol1.needs_real_archive_for("258") is False
        assert vol1.needs_real_archive_for("999") is True

        vol3 = archives.get_fantagraphics_archive(3)
        assert set(vol3.extra_images_page_map) == {"250", "260"}

        # A missing volume with no bundled override has no extra pages.
        vol2 = archives.get_fantagraphics_archive(2)
        assert vol2.extra_images_page_map == {}
        assert vol2.needs_real_archive_for("258") is True

    def test_raises_page_ext_error_for_uppercase_extension(self, tmp_path: Path) -> None:
        """`_get_archive_contents` accepts case-insensitively; `load()` then rejects non-canonical exts."""  # noqa: E501
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        # .PNG passes the case-insensitive endswith filter but Path.suffix preserves case,
        # so the resulting ".PNG" is not in _VALID_IMAGE_EXTENSION = [".png", ".jpg"].
        _make_volume_zip(
            archive_root / "01-vol.cbz",
            image_names=["page001.PNG", "page002.PNG"],
        )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=[1],
        )
        # Suppress missing-volume validation so the load reaches the extension check.
        archives.check_correct_volume_numbers = lambda _filenames: None  # ty: ignore[invalid-assignment]

        with pytest.raises(PageExtError, match="expecting extension to be in"):
            archives.load()
