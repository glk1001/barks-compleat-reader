# ruff: noqa: SLF001

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.reader_file_paths import (
    EDITED_SUBDIR,
    BarksPanelsExtType,
    FileTypes,
    PanelDirNames,
    ReaderFilePaths,
)


@pytest.fixture
def reader_file_paths() -> ReaderFilePaths:
    return ReaderFilePaths()


@pytest.fixture
def panels_dir(tmp_path: Path) -> Path:
    """Create a temporary directory structure for panels."""
    root = tmp_path / "Barks Panels"
    root.mkdir()

    for dir_enum in PanelDirNames:
        (root / dir_enum.value).mkdir()

    # Create edited dir for insets as it is checked in _check_panels_dirs
    (root / PanelDirNames.INSETS.value / EDITED_SUBDIR).mkdir()

    return root


@pytest.fixture
def panels_zip(tmp_path: Path) -> Path:
    """Create a temporary zip file structure for panels."""
    zip_path = tmp_path / "Barks Panels.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for dir_enum in PanelDirNames:
            zf.writestr(f"{dir_enum.value}/placeholder.txt", "")

        # Create edited dir entry
        zf.writestr(f"{PanelDirNames.INSETS.value}/{EDITED_SUBDIR}/placeholder.txt", "")

    return zip_path


class TestReaderFilePaths:
    def test_set_barks_panels_source_dir(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)

        assert reader_file_paths.barks_panels_are_encrypted is False
        assert reader_file_paths._barks_panels_zip is None
        assert reader_file_paths._panels_ext_type == BarksPanelsExtType.MOSTLY_PNG

        # Check a specific dir
        assert reader_file_paths._panel_dirs[PanelDirNames.COVERS] == panels_dir / "Covers"

    def test_set_barks_panels_source_zip(
        self, reader_file_paths: ReaderFilePaths, panels_zip: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_zip)):
            reader_file_paths.set_barks_panels_source(panels_zip, BarksPanelsExtType.JPG)

        assert reader_file_paths.barks_panels_are_encrypted is True
        assert reader_file_paths._barks_panels_zip is not None
        assert reader_file_paths._panels_ext_type == BarksPanelsExtType.JPG

    def test_set_barks_panels_source_missing_dir(
        self, reader_file_paths: ReaderFilePaths, tmp_path: Path
    ) -> None:
        # Empty dir, missing sub dirs
        with patch("os.path.expandvars", return_value=str(tmp_path)):  # noqa: SIM117
            with pytest.raises(FileNotFoundError):
                reader_file_paths.set_barks_panels_source(tmp_path, BarksPanelsExtType.MOSTLY_PNG)

    def test_get_comic_cover_file(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.JPG)

        title = "Donald Duck Finds Pirate Gold"
        cover_file = panels_dir / "Covers" / f"{title}.jpg"
        cover_file.touch()

        # Test normal retrieval
        result = reader_file_paths.get_comic_cover_file(title)
        assert result == cover_file

        # Test missing file
        assert reader_file_paths.get_comic_cover_file("Missing Title") is None

        # Test edited version
        edited_dir = panels_dir / "Covers" / EDITED_SUBDIR
        edited_dir.mkdir()
        edited_cover = edited_dir / f"{title}.jpg"
        edited_cover.touch()

        result_edited = reader_file_paths.get_comic_cover_file(
            title, use_only_edited_if_possible=True
        )
        assert result_edited == edited_cover

    def test_get_comic_inset_file(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)

        title_enum = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        title_str = "Donald Duck Finds Pirate Gold"

        inset_file = panels_dir / "Insets" / f"{title_str}.png"
        inset_file.touch()

        # Test normal
        result = reader_file_paths.get_comic_inset_file(title_enum)
        assert result == inset_file

        # Test emergency fallback
        # Remove file
        inset_file.unlink()

        # Create emergency file
        emergency_title = "Biceps Blues"
        emergency_file = panels_dir / "Insets" / f"{emergency_title}.png"
        emergency_file.touch()

        result_fallback = reader_file_paths.get_comic_inset_file(title_enum)
        assert result_fallback == emergency_file

    def test_get_comic_bw_files(self, reader_file_paths: ReaderFilePaths, panels_dir: Path) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)

        title = "Some Title"
        bw_dir = panels_dir / "BW" / title
        bw_dir.mkdir()
        (bw_dir / "page1.png").touch()
        (bw_dir / "page2.png").touch()

        files = reader_file_paths.get_comic_bw_files(title)
        assert len(files) == 2  # noqa: PLR2004

        # Test edited
        edited_dir = bw_dir / EDITED_SUBDIR
        edited_dir.mkdir()
        (edited_dir / "page1.png").touch()

        files_edited = reader_file_paths.get_comic_bw_files(title, use_only_edited_if_possible=True)
        assert len(files_edited) == 1
        assert files_edited[0].parent.name == EDITED_SUBDIR  # ty:ignore[unresolved-attribute]

    def test_get_file_type_titles(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)

        # Setup some covers
        (panels_dir / "Covers" / "Title1.png").touch()
        (panels_dir / "Covers" / "Title2.png").touch()
        (panels_dir / "Covers" / "Title3-no-overrides.png").touch()  # Should be ignored
        (panels_dir / "Covers" / "SubDir").mkdir()  # Should be ignored

        # Let's test Covers (files)
        titles = reader_file_paths.get_file_type_titles(FileTypes.COVER)
        assert "Title1" in titles
        assert "Title2" in titles
        assert "Title3-no-overrides" not in titles


class TestPanelsSourceSetup:
    def test_the_source_path_is_expanded_before_use(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        """`${HOME}`-style defaults only work if the raw path reaches `expandvars`."""
        with patch("os.path.expandvars", return_value=str(panels_dir)) as mock_expand:
            reader_file_paths.set_barks_panels_source(
                Path("${HOME}/panels"), BarksPanelsExtType.MOSTLY_PNG
            )

        mock_expand.assert_called_once_with(Path("${HOME}/panels"))

    def test_a_directory_source_is_not_encrypted(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)

        assert reader_file_paths.barks_panels_are_encrypted is False

    def test_a_zip_source_is_encrypted(
        self, reader_file_paths: ReaderFilePaths, panels_zip: Path
    ) -> None:
        """Only the bundled zip is encrypted; a loose directory is plain files."""
        with patch("os.path.expandvars", return_value=str(panels_zip)):
            reader_file_paths.set_barks_panels_source(panels_zip, BarksPanelsExtType.JPG)

        assert reader_file_paths.barks_panels_are_encrypted is True

    @pytest.mark.parametrize(
        ("ext_type", "expected_ext"),
        [
            pytest.param(BarksPanelsExtType.JPG, ".jpg", id="jpg"),
            pytest.param(BarksPanelsExtType.MOSTLY_PNG, ".png", id="mostly_png"),
        ],
    )
    def test_the_panel_extension_follows_the_source_type(
        self,
        reader_file_paths: ReaderFilePaths,
        panels_dir: Path,
        ext_type: BarksPanelsExtType,
        expected_ext: str,
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, ext_type)

        assert reader_file_paths._inset_files_ext == expected_ext
        assert reader_file_paths._edited_files_ext == expected_ext


class TestInsetFileLookup:
    @pytest.fixture
    def paths(self, reader_file_paths: ReaderFilePaths, panels_dir: Path) -> ReaderFilePaths:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)
        return reader_file_paths

    def test_edited_insets_are_ignored_unless_asked_for(
        self, paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        """The default is the plain inset — edited ones are opt-in."""
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        main = panels_dir / "Insets" / "Donald Duck Finds Pirate Gold.png"
        edited = panels_dir / "Insets" / EDITED_SUBDIR / "Donald Duck Finds Pirate Gold.png"
        main.touch()
        edited.touch()

        assert paths.get_comic_inset_file(title) == main
        assert paths.get_comic_inset_file(title, use_only_edited_if_possible=True) == edited

    def test_a_missing_edited_inset_falls_back_to_the_plain_one(
        self, paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        main = panels_dir / "Insets" / "Donald Duck Finds Pirate Gold.png"
        main.touch()

        assert paths.get_comic_inset_file(title, use_only_edited_if_possible=True) == main

    def test_the_inset_filename_uses_the_titles_own_name_and_extension(
        self, paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        """Wrong title or wrong extension resolves to a file that isn't there.

        That falls through to the emergency inset rather than raising, so the exact
        constructed name is what has to be checked.
        """
        title = Titles.GOLDEN_HELMET_THE
        expected = panels_dir / "Insets" / "The Golden Helmet.png"
        expected.touch()

        assert paths.get_comic_inset_file(title) == expected


class TestFileTypeTitles:
    @pytest.fixture
    def paths_with_covers(
        self, reader_file_paths: ReaderFilePaths, panels_dir: Path
    ) -> ReaderFilePaths:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)

        covers = panels_dir / "Covers"
        (covers / "Title1.png").touch()
        (covers / "Title2.png").touch()
        (covers / "Title3-no-overrides.png").touch()
        (covers / EDITED_SUBDIR).mkdir()
        (covers / "Title4").mkdir()
        return reader_file_paths

    def test_all_titles_are_returned_when_nothing_is_allowed_listed(
        self, paths_with_covers: ReaderFilePaths
    ) -> None:
        """Sub-directories count as titles, except the shared `edited` one."""
        titles = paths_with_covers.get_file_type_titles(FileTypes.COVER)

        assert sorted(titles) == ["Title1", "Title2", "Title4"]

    def test_an_allowed_list_keeps_only_its_members(
        self, paths_with_covers: ReaderFilePaths
    ) -> None:
        titles = paths_with_covers.get_file_type_titles(
            FileTypes.COVER, allowed_titles={"Title2", "Not Present"}
        )

        assert titles == ["Title2"]

    def test_an_empty_allowed_list_is_treated_as_no_filter(
        self, paths_with_covers: ReaderFilePaths
    ) -> None:
        """`set()` means "nothing specified", not "allow nothing"."""
        titles = paths_with_covers.get_file_type_titles(FileTypes.COVER, allowed_titles=set())

        assert sorted(titles) == ["Title1", "Title2", "Title4"]

    def test_the_directory_is_scanned_once_and_then_cached(
        self, paths_with_covers: ReaderFilePaths, panels_dir: Path
    ) -> None:
        first = paths_with_covers.get_file_type_titles(FileTypes.COVER)

        # A title added after the first scan must not appear: the listing is cached.
        (panels_dir / "Covers" / "Title5.png").touch()
        second = paths_with_covers.get_file_type_titles(FileTypes.COVER)

        assert second == first
        assert "Title5" not in second

    def test_the_cache_is_per_file_type(
        self, paths_with_covers: ReaderFilePaths, panels_dir: Path
    ) -> None:
        paths_with_covers.get_file_type_titles(FileTypes.COVER)
        (panels_dir / "Splash" / "SplashTitle.png").touch()

        assert paths_with_covers.get_file_type_titles(FileTypes.SPLASH) == ["SplashTitle"]


class TestEditedFilesAreOptIn:
    """`use_only_edited_if_possible` defaults to False across the file getters.

    A default of True would silently hide every unedited panel from the reader.
    """

    @pytest.fixture
    def paths(self, reader_file_paths: ReaderFilePaths, panels_dir: Path) -> ReaderFilePaths:
        with patch("os.path.expandvars", return_value=str(panels_dir)):
            reader_file_paths.set_barks_panels_source(panels_dir, BarksPanelsExtType.MOSTLY_PNG)
        return reader_file_paths

    def test_cover_lookup_defaults_to_the_plain_file(
        self, paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        """Covers are always jpg; only the *edited* copy follows the configured ext."""
        title = "Some Title"
        main = panels_dir / "Covers" / f"{title}.jpg"
        edited_dir = panels_dir / "Covers" / EDITED_SUBDIR
        edited_dir.mkdir()
        main.touch()
        edited = edited_dir / f"{title}.png"
        edited.touch()

        assert paths.get_comic_cover_file(title) == main
        assert paths.get_comic_cover_file(title, use_only_edited_if_possible=True) == edited

    def test_bw_lookup_defaults_to_every_file(
        self, paths: ReaderFilePaths, panels_dir: Path
    ) -> None:
        title = "Some Title"
        bw_dir = panels_dir / "BW" / title
        bw_dir.mkdir()
        (bw_dir / "page1.png").touch()
        (bw_dir / "page2.png").touch()
        edited = bw_dir / EDITED_SUBDIR
        edited.mkdir()
        (edited / "page1.png").touch()

        # Every page is offered, edited and unedited alike.
        assert len(paths.get_comic_bw_files(title)) == 3  # noqa: PLR2004
        # Opting in narrows it to the edited copies only.
        assert paths.get_comic_bw_files(title, use_only_edited_if_possible=True) == [
            edited / "page1.png"
        ]
