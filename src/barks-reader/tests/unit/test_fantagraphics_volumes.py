# ruff: noqa: SLF001, PLR2004

import zipfile
from pathlib import Path

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    NUM_VOLUMES,
)
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    EmptyArchiveError,
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
        volume_list=list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)),
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

    def test_accepts_a_zero_based_first_page(self, archives: FantagraphicsVolumeArchives) -> None:
        """Page 0 is legal — only a *negative* first page is rejected.

        Volumes whose images start at 000 exist (see `_get_archive_image_page_map`'s
        `page_inc`), so the guard must be `< 0`, not `<= 0`.
        """
        archives._check_image_names(["page0.png", "page1.png"], first=0, last=1, img_ext=".png")


class TestCheckCorrectVolumeNumbers:
    def test_raises_too_many_for_volume_exceeding_max(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        # Create filenames with a volume number > LAST_VOLUME_NUMBER.
        filenames = [
            Path(f"{i}-vol.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        ] + [Path("999-extra.cbz")]
        with pytest.raises(TooManyArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers(filenames)

        # The error reports how many files were actually seen against the expected
        # count, and where — all three are what the user needs to fix it.
        assert exc_info.value.num_archive_files == len(filenames)
        assert exc_info.value.num_volumes == NUM_VOLUMES
        assert exc_info.value.archive_root == archives._archive_root

    def test_last_volume_number_is_accepted(self, archives: FantagraphicsVolumeArchives) -> None:
        """The valid range is inclusive of `LAST_VOLUME_NUMBER`."""
        filenames = [Path(f"{i}-vol.cbz") for i in range(FIRST_VOLUME_NUMBER, NUM_VOLUMES + 1)]
        # No exception expected — and the last volume must not read as "too many".
        archives.check_correct_volume_numbers(filenames)

    def test_raises_duplicate_for_repeated_volumes(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        filenames = [
            Path(f"{i}-vol.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        ]
        filenames.append(Path("5-duplicate.cbz"))
        with pytest.raises(DuplicateArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers(filenames)

        assert exc_info.value.duplicates == [5]
        assert exc_info.value.archive_root == archives._archive_root

    def test_raises_missing_for_gaps(self, archives: FantagraphicsVolumeArchives) -> None:
        # Missing volumes 15 and 20
        filenames = [
            Path(f"{i}-vol.cbz")
            for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
            if i not in (15, 20)
        ]
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers(filenames)
        assert exc_info.value.missing_file_vols == [15, 20]

    def test_passes_for_complete_set(self, archives: FantagraphicsVolumeArchives) -> None:
        filenames = [
            Path(f"{i}-vol.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        ]
        archives.check_correct_volume_numbers(filenames)

    def test_raises_missing_for_empty_list(self, archives: FantagraphicsVolumeArchives) -> None:
        # An empty archive dir must not IndexError; it means every volume is missing.
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers([])

        # Every volume in the valid range, exactly once — not an off-by-one slice.
        assert exc_info.value.missing_file_vols == list(
            range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        )


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

    def test_missing_archive_files_error_keeps_the_volume_list(self) -> None:
        err = MissingArchiveFilesError([7, 12], Path("/archives"))
        assert err.missing_file_vols == [7, 12]

    def test_too_many_archive_files_error(self) -> None:
        root = Path("/archives")
        err = TooManyArchiveFilesError(num_archive_files=31, num_volumes=29, archive_root=root)

        assert str(err) == (
            f'There are too many archive files in "{root}". There are 31 but there should be 29.'
        )
        assert err.num_archive_files == 31
        assert err.num_volumes == 29
        assert err.archive_root == root

    def test_duplicate_archive_files_error(self) -> None:
        root = Path("/archives")
        err = DuplicateArchiveFilesError([7, 12], root)

        assert str(err) == (
            f'There are duplicate volume files in "{root}". The duplicate volumes are 7, 12.'
        )
        assert err.duplicates == [7, 12]
        assert err.archive_root == root

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
        archive_filenames = [
            Path(f"{i}-v.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        ]
        too_many = {i: Path(f"{i}-ov.cbz") for i in range(1, NUM_VOLUMES + 2)}
        with pytest.raises(TooManyOverrideDirsError):
            archives.check_archives_and_overrides(archive_filenames, too_many)

    def test_one_override_per_volume_is_allowed(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        """The limit is `> NUM_VOLUMES`: exactly one override per volume is fine."""
        archive_filenames = [
            Path(f"{i}-v.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        ]
        exactly_enough = {i: Path(f"{i}-ov.cbz") for i in range(1, NUM_VOLUMES + 1)}

        # No exception expected.
        archives.check_archives_and_overrides(archive_filenames, exactly_enough)


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
            volume_list=list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)),
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

    def test_loaded_archive_carries_every_field(self, tmp_path: Path) -> None:
        """The whole `FantagraphicsArchive` for one volume, field by field.

        `load()` threads a dozen values into the dataclass positionally; checking only
        a couple of them leaves the rest free to be wrong (or `None`).
        """
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()

        for vol in range(1, NUM_VOLUMES + 1):
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz",
                image_names=["page001.png", "page002.png", "page003.png"],
            )
        # Volume 2 gets an override zip: one page that shadows an archive page, and one
        # that doesn't exist in the archive at all.
        override = _make_override_zip(
            override_root / "02-override.cbz", image_names=["002.png", "500.png"]
        )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        archives.load()

        entry = archives.get_fantagraphics_archive(2)
        assert entry.fanta_volume == 2
        assert entry.archive_filename == archive_root / "02-vol.cbz"
        assert entry.archive_image_subdir == Path("images")
        assert entry.image_ext == ".png"
        assert entry.first_page == 1
        assert entry.last_page == 3
        assert entry.archive_images_page_map == {
            "001": Path("images/page001.png"),
            "002": Path("images/page002.png"),
            "003": Path("images/page003.png"),
        }
        assert entry.override_images_page_map == {"002": Path("002.png")}
        assert entry.extra_images_page_map == {"500": Path("500.png")}
        assert entry.override_archive_filename == override
        assert entry.is_missing is False
        assert entry.get_num_pages() == 3

        # A volume with no override zip gets empty maps and no override filename.
        plain = archives.get_fantagraphics_archive(1)
        assert plain.override_archive_filename is None
        assert plain.override_images_page_map == {}
        assert plain.extra_images_page_map == {}
        assert plain.has_overrides() is False

    def test_missing_volume_placeholder_carries_every_field(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()

        for vol in range(1, NUM_VOLUMES + 1):
            if vol == 2:
                continue
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz", image_names=["page001.png", "page002.png"]
            )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        with pytest.raises(MissingArchiveFilesError):
            archives.load()

        entry = archives.get_fantagraphics_archive(2)
        assert entry.fanta_volume == 2
        assert entry.archive_filename == Path("2-MISSING.cbz")
        assert entry.archive_image_subdir is None
        assert entry.image_ext == ""
        # The sentinel page range: -1/-1, so `get_num_pages()` reports 1 page.
        assert entry.first_page == -1
        assert entry.last_page == -1
        assert entry.archive_images_page_map == {}
        assert entry.override_images_page_map == {}
        assert entry.override_archive_filename is None
        assert entry.is_missing is True

    def test_archives_are_processed_in_volume_order(self, tmp_path: Path) -> None:
        """Sorted by volume *number*, not by filename.

        Unpadded names sort lexically as 1, 10, 11, ... 2 — so a missing sort key shows
        up as a scrambled processing order.
        """
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()

        for vol in range(1, NUM_VOLUMES + 1):
            _make_volume_zip(
                archive_root / f"{vol}-vol.cbz", image_names=["page001.png", "page002.png"]
            )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        archives.load()

        assert list(archives._fantagraphics_archive_dict) == list(
            range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        )

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


class TestErrorsIdentifyTheArchiveRoot:
    """Every validation error names the directory the user has to go and fix."""

    def test_missing_volumes_error_names_the_root(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        filenames = [
            Path(f"{i}-vol.cbz")
            for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
            if i != 15
        ]
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers(filenames)

        assert str(archives._archive_root) in str(exc_info.value)

    def test_empty_archive_dir_error_names_the_root(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers([])

        assert str(archives._archive_root) in str(exc_info.value)

    def test_too_many_override_dirs_error_names_the_root_and_counts(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        archive_filenames = [
            Path(f"{i}-v.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
        ]
        too_many = {i: Path(f"{i}-ov.cbz") for i in range(1, NUM_VOLUMES + 2)}

        with pytest.raises(TooManyOverrideDirsError) as exc_info:
            archives.check_archives_and_overrides(archive_filenames, too_many)

        msg = str(exc_info.value)
        assert str(archives._archive_root) in msg
        assert f" There are {NUM_VOLUMES + 1} but there should be {NUM_VOLUMES}." in msg


class TestVolumeRangeEdges:
    def test_a_missing_last_volume_is_reported(self, archives: FantagraphicsVolumeArchives) -> None:
        """The full-volume set must run to `LAST_VOLUME_NUMBER` inclusive.

        A short range would silently accept a library missing its final volume.
        """
        filenames = [Path(f"{i}-vol.cbz") for i in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER)]
        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers(filenames)

        assert exc_info.value.missing_file_vols == [LAST_VOLUME_NUMBER]

    def test_an_override_for_the_last_volume_is_accepted(self, tmp_path: Path) -> None:
        override_root = tmp_path / "override"
        override_root.mkdir()
        last = _make_override_zip(
            override_root / f"{LAST_VOLUME_NUMBER}-override.cbz", image_names=["001.png"]
        )

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)),
        )

        assert archives.get_all_volume_override_archives() == {LAST_VOLUME_NUMBER: last}

    def test_a_non_volume_file_is_skipped_without_ending_the_scan(self, tmp_path: Path) -> None:
        """An unparseable name must not hide the override files after it."""
        override_root = tmp_path / "override"
        override_root.mkdir()
        # "README..." sorts before the numbered zips on most filesystems, and has no
        # leading digits, so `_get_fanta_volume` raises ValueError for it.
        (override_root / "README.txt").write_text("not a volume")
        first = _make_override_zip(override_root / "01-override.cbz", image_names=["001.png"])
        second = _make_override_zip(override_root / "02-override.cbz", image_names=["001.png"])

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=[1, 2],
        )

        assert archives.get_all_volume_override_archives() == {1: first, 2: second}


class TestArchiveContentsEdges:
    def test_an_archive_with_no_images_yields_an_empty_relative_subdir(
        self, tmp_path: Path
    ) -> None:
        """The subdir starts as `Path()`, not `None` — callers join onto it."""
        archive = tmp_path / "01-vol.cbz"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("notes.txt", b"no images here")

        subdir, filenames = FantagraphicsVolumeArchives._get_archive_contents(archive)

        assert subdir == Path()
        assert filenames == []


class TestLoadErrorMessages:
    @staticmethod
    def _single_volume_archives(tmp_path: Path, image_names: list[str]):  # noqa: ANN205
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        _make_volume_zip(archive_root / "01-vol.cbz", image_names=image_names)

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root, override_root=override_root, volume_list=[1]
        )
        # Suppress missing-volume validation so the load reaches the per-image checks.
        archives.check_correct_volume_numbers = lambda _filenames: None  # ty: ignore[invalid-assignment]
        return archives

    def test_an_archive_with_no_images_names_the_file(self, tmp_path: Path) -> None:
        """A truncated/partial volume copy must say which file, not raise IndexError.

        This is a real field failure: a volume that copied across to another machine
        as an empty zip surfaced only as "IndexError: list index out of range" from
        the load loop, naming neither the volume nor the cause.
        """
        archives = self._single_volume_archives(tmp_path, [])

        with pytest.raises(EmptyArchiveError) as exc_info:
            archives.load()

        message = str(exc_info.value)
        assert "01-vol.cbz" in message
        assert "contains no page images" in message

    def test_page_ext_error_names_the_offending_first_image(self, tmp_path: Path) -> None:
        archives = self._single_volume_archives(tmp_path, ["page001.PNG", "page002.PNG"])

        with pytest.raises(PageExtError) as exc_info:
            archives.load()

        assert "page001.PNG" in str(exc_info.value)

    def test_the_expected_extension_comes_from_the_first_image(self, tmp_path: Path) -> None:
        """A mixed-extension archive is judged against page 1's extension."""
        archives = self._single_volume_archives(tmp_path, ["page001.png", "page002.jpg"])

        with pytest.raises(RuntimeError) as exc_info:
            archives.load()

        assert 'expecting extension ".png" but got ".jpg"' in str(exc_info.value)


def test_missing_volume_records_its_override_archive(tmp_path: Path) -> None:
    """A missing volume still remembers which bundled override zip serves it."""
    archive_root = tmp_path / "archive"
    override_root = tmp_path / "override"
    archive_root.mkdir()
    override_root.mkdir()
    override = _make_override_zip(override_root / "01-override.cbz", image_names=["258.png"])

    archives = FantagraphicsVolumeArchives(
        archive_root=archive_root,
        override_root=override_root,
        volume_list=list(range(1, NUM_VOLUMES + 1)),
    )
    with pytest.raises(MissingArchiveFilesError):
        archives.load()

    assert archives.get_fantagraphics_archive(1).override_archive_filename == override


def test_an_override_zip_with_a_foreign_image_type_is_rejected(tmp_path: Path) -> None:
    """Override zips may only hold png/jpg pages.

    The check used to sit behind an `assert` over the same two extensions, which made
    it unreachable; it is a live guard now.
    """
    override = tmp_path / "01-override.cbz"
    with zipfile.ZipFile(override, "w") as zf:
        zf.writestr("258.gif", b"GIF89a")

    with pytest.raises(PageExtError, match="expecting extension to be in"):
        FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(override, {})
