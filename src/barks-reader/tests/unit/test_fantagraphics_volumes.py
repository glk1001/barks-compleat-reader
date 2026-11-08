# ruff: noqa: SLF001, PLR2004

import zipfile
from pathlib import Path

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import (
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    NUM_VOLUMES,
)
from barks_fantagraphics.page_classes import CleanPage
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.fantagraphics_volumes import (
    ZERO_BASED_VOLUMES,
    DuplicateArchiveFilesError,
    EmptyArchiveError,
    FantagraphicsArchive,
    FantagraphicsVolumeArchives,
    MissingArchiveFilesError,
    MissingVolumeError,
    MixedImageFoldersError,
    PageExtError,
    PageNumError,
    PageSource,
    PageSourceKind,
    has_archive_extension,
)
from barks_reader.core.log_markers import EMPTY_PAGE_IMAGE

_ARCHIVE = Path("03 - Volume.cbz")


def _make_volume_zip(path: Path, image_names: list[str], subdir: str = "images") -> Path:
    """Write a minimal cbz at `path` containing `subdir/<name>` for each image."""
    with zipfile.ZipFile(path, "w") as zf:
        for name in image_names:
            zf.writestr(f"{subdir}/{name}", b"\x89PNG\r\n")
    return path


def _volume_pages(vol: int, count: int, ext: str = ".png") -> list[str]:
    """`count` page names numbered as the volume's are: from 000 or from 001."""
    first = 0 if vol in ZERO_BASED_VOLUMES else 1
    return [f"page{page:03d}{ext}" for page in range(first, first + count)]


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
            archives._check_image_names(_ARCHIVE, ["page-1.png"], first=-1, last=5, img_ext=".png")

    def test_raises_when_first_equals_last(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(ValueError, match=r"First page .* should be <"):
            archives._check_image_names(_ARCHIVE, ["page5.png"], first=5, last=5, img_ext=".png")

    def test_raises_when_first_greater_than_last(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        with pytest.raises(ValueError, match=r"First page .* should be <"):
            archives._check_image_names(_ARCHIVE, ["page10.png"], first=10, last=5, img_ext=".png")

    def test_raises_on_page_number_mismatch(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(PageNumError) as exc_info:
            archives._check_image_names(
                _ARCHIVE, ["page2.png", "page3.png"], first=1, last=2, img_ext=".png"
            )

        message = str(exc_info.value)
        assert f'"{_ARCHIVE}"' in message
        assert 'expecting page 1 but image "page2.png" is numbered 2' in message

    def test_raises_when_the_numbering_resets_partway(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        """Pages 1-3 then a second run 1-2: the last image says 2, so only two were checked."""
        images = ["page1.png", "page2.png", "page3.png", "scan1.png", "scan2.png"]

        with pytest.raises(PageNumError) as exc_info:
            archives._check_image_names(_ARCHIVE, images, first=1, last=2, img_ext=".png")

        assert str(exc_info.value) == (
            f'Fantagraphics archive "{_ARCHIVE}": its pages are numbered 1 to 2, but it holds'
            ' 5 page images, the first one past page 2 being "page3.png". Replace it from the'
            " library and retry."
        )

    def test_a_missing_page_is_named_not_counted(
        self, archives: FantagraphicsVolumeArchives
    ) -> None:
        """A short volume fails at the page that is missing, the more useful message."""
        with pytest.raises(PageNumError, match=r'expecting page 2 but image "page3\.png"'):
            archives._check_image_names(
                _ARCHIVE, ["page1.png", "page3.png"], first=1, last=3, img_ext=".png"
            )

    def test_raises_on_extension_mismatch(self, archives: FantagraphicsVolumeArchives) -> None:
        with pytest.raises(RuntimeError, match=r'expecting extension "\.png" but got "\.jpg"'):
            archives._check_image_names(
                _ARCHIVE, ["page1.jpg", "page2.jpg"], first=1, last=2, img_ext=".png"
            )

    def test_passes_for_valid_images(self, archives: FantagraphicsVolumeArchives) -> None:
        archives._check_image_names(
            _ARCHIVE, ["page1.png", "page2.png", "page3.png"], first=1, last=3, img_ext=".png"
        )

    def test_accepts_a_zero_based_first_page(self, archives: FantagraphicsVolumeArchives) -> None:
        """Page 0 is legal — only a *negative* first page is rejected.

        Volumes whose images start at 000 exist (see `_get_archive_image_page_map`'s
        `page_inc`), so the guard must be `< 0`, not `<= 0`.
        """
        archives._check_image_names(
            _ARCHIVE, ["page0.png", "page1.png"], first=0, last=1, img_ext=".png"
        )

    def test_an_upper_case_extension_matches(self, archives: FantagraphicsVolumeArchives) -> None:
        """`_get_archive_contents` picks pages out whatever their case, so this check must too."""
        archives._check_image_names(
            _ARCHIVE, ["page1.JPG", "page2.jpg"], first=1, last=2, img_ext=".jpg"
        )


class TestCheckFirstPage:
    @pytest.mark.parametrize(
        ("vol", "first_page"), [(1, 0), (19, 0), (29, 0), (2, 1), (18, 1), (30, 1)]
    )
    def test_a_volume_numbered_as_fantagraphics_numbers_it_passes(
        self, vol: int, first_page: int
    ) -> None:
        FantagraphicsVolumeArchives._check_first_page(
            _ARCHIVE, vol, first_page, f"page{first_page:03d}.jpg"
        )

    def test_a_zero_based_volume_that_lost_its_000_is_refused(self) -> None:
        """It would pass every other check, and be read one page off throughout."""
        with pytest.raises(PageNumError) as exc_info:
            FantagraphicsVolumeArchives._check_first_page(_ARCHIVE, 1, 1, "page001.jpg")

        assert str(exc_info.value) == (
            f'Fantagraphics archive "{_ARCHIVE}": volume 1 numbers its pages from 0, but its'
            ' first image, "page001.jpg", is numbered 1. Replace it from the library and retry.'
        )

    @pytest.mark.parametrize(
        ("vol", "first_page"),
        [
            pytest.param(2, 2, id="a one-based volume that lost its 001"),
            pytest.param(19, 2, id="a zero-based volume that lost two pages"),
            pytest.param(2, 0, id="a one-based volume numbered from 000"),
        ],
    )
    def test_a_volume_starting_elsewhere_is_refused(self, vol: int, first_page: int) -> None:
        with pytest.raises(PageNumError, match=f"volume {vol} numbers its pages from"):
            FantagraphicsVolumeArchives._check_first_page(
                _ARCHIVE, vol, first_page, f"page{first_page:03d}.jpg"
            )


class TestCheckCorrectVolumeNumbers:
    @staticmethod
    def _for_volumes(volume_list: list[int]) -> FantagraphicsVolumeArchives:
        return FantagraphicsVolumeArchives(
            archive_root=Path("/fake/archives"),
            override_root=Path("/fake/overrides"),
            volume_list=volume_list,
        )

    def test_a_few_volumes_with_their_files_are_not_missing_the_rest(self) -> None:
        archives = self._for_volumes([3, 5, 7])
        archives.check_correct_volume_numbers([Path(f"{i}-vol.cbz") for i in (3, 5, 7)])

    def test_a_few_volumes_report_only_their_own_gaps(self) -> None:
        archives = self._for_volumes([7, 3, 5])

        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers([Path("3-vol.cbz"), Path("7-vol.cbz")])

        assert exc_info.value.missing_file_vols == [5]

    def test_a_few_volumes_with_no_files_report_just_those(self) -> None:
        archives = self._for_volumes([7, 3, 5])

        with pytest.raises(MissingArchiveFilesError) as exc_info:
            archives.check_correct_volume_numbers([])

        assert exc_info.value.missing_file_vols == [3, 5, 7]

    def test_last_volume_number_is_accepted(self, archives: FantagraphicsVolumeArchives) -> None:
        """The valid range is inclusive of `LAST_VOLUME_NUMBER`."""
        filenames = [Path(f"{i}-vol.cbz") for i in range(FIRST_VOLUME_NUMBER, NUM_VOLUMES + 1)]
        # No exception expected.
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

    def test_duplicate_archive_files_error(self) -> None:
        root = Path("/archives")
        err = DuplicateArchiveFilesError([7, 12], root)

        assert str(err) == (
            f'There are duplicate volume files in "{root}". The duplicate volumes are 7, 12.'
        )
        assert err.duplicates == [7, 12]
        assert err.archive_root == root


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

    def test_stray_override_entries_are_skipped_and_logged(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        """A bad data pack must not stop the app: strays are warned about, not raised."""
        override_root = tmp_path / "override"
        override_root.mkdir()
        (override_root / "__MACOSX").mkdir()
        (override_root / "00-notes.txt").touch()  # volume 0 is out of range
        (override_root / f"{LAST_VOLUME_NUMBER + 1}-extra.cbz").touch()
        good = override_root / "01-x.cbz"
        good.touch()

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=[1],
        )

        assert archives.get_all_volume_override_archives() == {1: good}
        warnings = [line for line in loguru_sink if "unexpected entry" in line]
        assert len(warnings) == 3
        assert any("__MACOSX" in line for line in warnings)

    def test_scan_reports_each_stray_in_name_order(self, tmp_path: Path) -> None:
        override_root = tmp_path / "override"
        override_root.mkdir()
        first = override_root / "02-a.cbz"
        first.touch()
        (override_root / "02-b.cbz").touch()  # a second file for volume 2
        (override_root / "README").touch()  # no volume number
        (override_root / "sub").mkdir()

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=[2],
        )

        found, strays = archives.scan_override_root()

        assert found == {2: first}
        assert strays == [
            override_root / "02-b.cbz",
            override_root / "README",
            override_root / "sub",
        ]

    def test_an_override_file_without_an_extension_is_used_but_warned_about(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        """data-v8 ships volume 18's override with no ".cbz": a bad name, but still the archive."""
        override_root = tmp_path / "override"
        override_root.mkdir()
        bare = override_root / "18 - Donald Duck - The Lost Peg Leg Mine"
        bare.touch()

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=[18],
        )

        assert archives.scan_override_root() == ({18: bare}, [])
        assert archives.get_all_volume_override_archives() == {18: bare}
        assert any(
            f'"{bare}" has no ".cbz" or ".zip" extension; using it anyway' in line
            for line in loguru_sink
        )

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("01 - a.cbz", True),
            ("01 - a.ZIP", True),
            ("01 - a", False),
            ("05 - Mr. X", False),  # a dot in the title is not an extension
            ("01 - a.cbr", False),
        ],
    )
    def test_has_archive_extension(self, name: str, *, expected: bool) -> None:
        assert has_archive_extension(Path(name)) is expected

    def test_a_volume_outside_the_list_is_not_a_stray(self, tmp_path: Path) -> None:
        override_root = tmp_path / "override"
        override_root.mkdir()
        (override_root / "05-x.cbz").touch()

        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=[1],
        )

        assert archives.scan_override_root() == ({}, [])

    def test_a_missing_overrides_folder_is_reported_not_raised(self, tmp_path: Path) -> None:
        override_root = tmp_path / "gone"
        archives = FantagraphicsVolumeArchives(
            archive_root=tmp_path / "archive",
            override_root=override_root,
            volume_list=[1],
        )

        assert archives.scan_override_root() == ({}, [override_root])
        assert archives.get_all_volume_override_archives() == {}


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

    def test_skips_the_junk_finder_compress_adds(self, tmp_path: Path) -> None:
        """A volume zipped with Finder holds `__MACOSX/` and `._` copies of every image."""
        zip_path = tmp_path / "01-vol.cbz"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for name in ["page001.png", "page002.png"]:
                zf.writestr(f"images/{name}", b"\x89PNG\r\n")
                zf.writestr(f"__MACOSX/images/._{name}", b"junk")
                zf.writestr(f"images/._{name}", b"junk")

        subdir, image_filenames = FantagraphicsVolumeArchives._get_archive_contents(zip_path)

        assert subdir == Path("images")
        assert image_filenames == ["page001.png", "page002.png"]

    def test_images_in_two_folders_are_an_error_naming_both(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "01-vol.cbz"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("images/page001.png", b"\x89PNG\r\n")
            zf.writestr("extra/page002.png", b"\x89PNG\r\n")

        with pytest.raises(MixedImageFoldersError) as exc_info:
            FantagraphicsVolumeArchives._get_archive_contents(zip_path)

        assert exc_info.value.image_subdirs == [Path("extra"), Path("images")]
        msg = str(exc_info.value)
        assert '"extra", "images"' in msg
        assert str(zip_path) in msg

    def test_images_at_the_archive_root_have_an_empty_subdir(self, tmp_path: Path) -> None:
        zip_path = _make_override_zip(tmp_path / "01-vol.cbz", ["page001.png"])

        subdir, image_filenames = FantagraphicsVolumeArchives._get_archive_contents(zip_path)

        assert subdir == Path()
        assert image_filenames == ["page001.png"]


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

    def test_skips_folder_entries_and_the_junk_finder_compress_adds(self, tmp_path: Path) -> None:
        override_zip = tmp_path / "01-ov.cbz"
        with zipfile.ZipFile(override_zip, "w") as zf:
            zf.writestr("overrides/", b"")
            zf.writestr("overrides/003.png", b"\x89PNG\r\n")
            zf.writestr("__MACOSX/", b"")
            zf.writestr("__MACOSX/overrides/._003.png", b"junk")
            zf.writestr("overrides/._099.png", b"junk")

        overrides, extras = FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
            override_archive_filename=override_zip,
            archive_page_map={"003": Path("images/page003.png")},
        )

        assert overrides == {"003": Path("overrides/003.png")}
        assert extras == {}

    def test_accepts_an_upper_case_extension(self, tmp_path: Path) -> None:
        override_zip = _make_override_zip(tmp_path / "01-ov.cbz", image_names=["003.PNG"])

        overrides, _extras = FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
            override_archive_filename=override_zip,
            archive_page_map={"003": Path("images/page003.png")},
        )

        assert overrides == {"003": Path("003.PNG")}

    def test_still_rejects_a_file_that_is_not_an_image(self, tmp_path: Path) -> None:
        override_zip = _make_override_zip(tmp_path / "01-ov.cbz", image_names=["notes.txt"])

        with pytest.raises(PageExtError, match=r"notes\.txt"):
            FantagraphicsVolumeArchives._get_override_and_extra_images_page_maps(
                override_archive_filename=override_zip,
                archive_page_map={"003": Path("images/page003.png")},
            )


class TestLoadEndToEnd:
    @staticmethod
    def _every_volume(
        tmp_path: Path, pages_for: dict[int, list[str]]
    ) -> FantagraphicsVolumeArchives:
        """Every volume numbered as Fantagraphics numbers it, but those in `pages_for`."""
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        for vol in range(1, NUM_VOLUMES + 1):
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz",
                image_names=pages_for.get(vol, _volume_pages(vol, 2)),
            )
        return FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )

    def test_a_zero_based_volume_s_000_is_its_page_001(self, tmp_path: Path) -> None:
        archives = self._every_volume(tmp_path, {})
        archives.load()

        assert archives.get_fantagraphics_archive(1).archive_images_page_map == {
            "001": Path("images/page000.png"),
            "002": Path("images/page001.png"),
        }

    def test_a_zero_based_volume_that_lost_its_000_is_refused(self, tmp_path: Path) -> None:
        archives = self._every_volume(tmp_path, {1: ["page001.png", "page002.png"]})

        with pytest.raises(PageNumError) as exc_info:
            archives.load()

        message = str(exc_info.value)
        assert "01-vol.cbz" in message
        assert 'volume 1 numbers its pages from 0, but its first image, "page001.png"' in message

    def test_archives_made_for_one_volume_load_just_that_one(self, tmp_path: Path) -> None:
        """The other 29 are neither scanned nor reported missing."""
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        for vol in (2, 3):
            _make_volume_zip(archive_root / f"{vol:02d}-vol.cbz", image_names=_volume_pages(vol, 2))

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root, override_root=override_root, volume_list=[2]
        )
        archives.load()

        assert list(archives._fantagraphics_archive_dict) == [2]
        assert archives.get_fantagraphics_archive(2).is_missing is False

    def test_loads_a_volume_whose_pages_have_upper_case_extensions(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()
        for vol in range(1, NUM_VOLUMES + 1):
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz", image_names=_volume_pages(vol, 2, ".JPG")
            )

        archives = FantagraphicsVolumeArchives(
            archive_root=archive_root,
            override_root=override_root,
            volume_list=list(range(1, NUM_VOLUMES + 1)),
        )
        archives.load()

        entry = archives.get_fantagraphics_archive(2)
        assert entry.image_ext == ".jpg"
        # The page map keeps the names as the zip has them: they are what is read.
        assert entry.archive_images_page_map == {
            "001": Path("images/page001.JPG"),
            "002": Path("images/page002.JPG"),
        }

    def test_populates_archive_dict_for_complete_volume_set(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "archive"
        override_root = tmp_path / "override"
        archive_root.mkdir()
        override_root.mkdir()

        for vol in range(1, NUM_VOLUMES + 1):
            _make_volume_zip(
                archive_root / f"{vol:02d}-vol.cbz",
                image_names=_volume_pages(vol, 2),
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
            first_page = 0 if vol in ZERO_BASED_VOLUMES else 1
            assert entry.first_page == first_page
            assert entry.last_page == first_page + 1

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
                image_names=_volume_pages(vol, 3),
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
            _make_volume_zip(archive_root / f"{vol:02d}-vol.cbz", image_names=_volume_pages(vol, 2))

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
            _make_volume_zip(archive_root / f"{vol}-vol.cbz", image_names=_volume_pages(vol, 2))

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
                image_names=_volume_pages(vol, 2),
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
        assert (vol1.page_source("258", use_overrides=True).kind is PageSourceKind.ARCHIVE) is False
        assert (vol1.page_source("999", use_overrides=True).kind is PageSourceKind.ARCHIVE) is True

        vol3 = archives.get_fantagraphics_archive(3)
        assert set(vol3.extra_images_page_map) == {"250", "260"}

        # A missing volume with no bundled override has no extra pages.
        vol2 = archives.get_fantagraphics_archive(2)
        assert vol2.extra_images_page_map == {}
        assert (vol2.page_source("258", use_overrides=True).kind is PageSourceKind.ARCHIVE) is True

    def test_an_override_page_needs_the_archive_once_overrides_are_off(self) -> None:
        """What the image source does: extras always bundled, overrides only when in use.

        With overrides off the user asked for the original page, which only the
        library archive has; saying "bundled" here let a missing volume through to a
        KeyError in the loader thread instead of the missing-volume dialog.
        """
        archive = FantagraphicsArchive(
            fanta_volume=7,
            archive_filename=Path("07-MISSING.cbz"),
            archive_image_subdir=None,
            image_ext=".png",
            first_page=1,
            last_page=2,
            archive_images_page_map={},
            override_images_page_map={"258": Path("258.png")},
            extra_images_page_map={"300": Path("300.png")},
            override_archive_filename=None,
            is_missing=True,
        )

        assert (
            archive.page_source("258", use_overrides=True).kind is PageSourceKind.ARCHIVE
        ) is False
        assert (
            archive.page_source("258", use_overrides=False).kind is PageSourceKind.ARCHIVE
        ) is True
        # An extra page is bundled whatever the overrides setting.
        assert (
            archive.page_source("300", use_overrides=False).kind is PageSourceKind.ARCHIVE
        ) is False
        assert (
            archive.page_source("999", use_overrides=True).kind is PageSourceKind.ARCHIVE
        ) is True


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
        _make_volume_zip(archive_root / "02-vol.cbz", image_names=image_names)

        # Made for volume 2 alone, which is not then missing the other 29.
        return FantagraphicsVolumeArchives(
            archive_root=archive_root, override_root=override_root, volume_list=[2]
        )

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
        assert "02-vol.cbz" in message
        assert "contains no page images" in message

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


def _page(filename: str, page_type: PageType = PageType.BODY) -> PageInfo:
    page = CleanPage(filename, page_type)
    return PageInfo(
        page_index=0, display_page_num="1", page_type=page_type, srce_page=page, dest_page=page
    )


class TestPageSourceFor:
    """The one rule for where a comic's page comes from: the reader and the gate share it."""

    @staticmethod
    def _archive() -> FantagraphicsArchive:
        return FantagraphicsArchive(
            fanta_volume=7,
            archive_filename=Path("07.cbz"),
            archive_image_subdir=None,
            image_ext=".jpg",
            first_page=1,
            last_page=400,
            archive_images_page_map={"100": Path("arch/100.jpg"), "258": Path("arch/258.jpg")},
            override_images_page_map={"258": Path("over/258.png"), "300": Path("over/300.png")},
            extra_images_page_map={"300": Path("extra/300.png")},
            override_archive_filename=None,
        )

    @pytest.mark.parametrize(
        ("page", "use_overrides", "kind", "path"),
        [
            (_page("empty_page.jpg", PageType.TITLE), True, PageSourceKind.PLACEHOLDER, None),
            (_page("empty_page.jpg", PageType.BLANK_PAGE), True, PageSourceKind.PLACEHOLDER, None),
            (_page("empty_page.jpg", PageType.BODY), True, PageSourceKind.PLACEHOLDER, None),
            (_page("100.jpg"), True, PageSourceKind.ARCHIVE, "arch/100.jpg"),
            (_page("258.jpg"), True, PageSourceKind.OVERRIDE, "over/258.png"),
            (_page("258.jpg"), False, PageSourceKind.ARCHIVE, "arch/258.jpg"),
            (_page("300.jpg"), True, PageSourceKind.EXTRA, "extra/300.png"),
            (_page("300.jpg"), False, PageSourceKind.EXTRA, "extra/300.png"),
            (_page("999.jpg"), True, PageSourceKind.ARCHIVE, None),
        ],
        ids=[
            "title",
            "blank",
            "empty-body",
            "archive",
            "override",
            "override-off",
            "extra-beats-override",
            "extra-with-overrides-off",
            "in-no-map",
        ],
    )
    def test_the_source_of_a_page(
        self, page: PageInfo, use_overrides: bool, kind: PageSourceKind, path: str | None
    ) -> None:
        source = self._archive().page_source_for(page, use_overrides=use_overrides)

        assert source.kind is kind
        if kind is PageSourceKind.PLACEHOLDER:
            assert source.path == Path(EMPTY_PAGE_IMAGE)
        else:
            assert source.path == (None if path is None else Path(path))

    def test_a_title_typed_page_whose_scan_is_not_title_typed_is_looked_up(self) -> None:
        """`is_title_page` reads the scan's own type: only the page type says blank here."""
        page = _page("empty_page.jpg", PageType.TITLE)
        page = PageInfo(
            page_index=0,
            display_page_num="1",
            page_type=PageType.TITLE,
            srce_page=CleanPage("empty_page.jpg", PageType.BODY),
            dest_page=page.dest_page,
        )

        source = self._archive().page_source_for(page, use_overrides=True)

        assert source == PageSource(PageSourceKind.ARCHIVE, None)
