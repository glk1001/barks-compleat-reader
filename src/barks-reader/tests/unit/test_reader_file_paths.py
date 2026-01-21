# ruff: noqa: SLF001

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.reader_file_paths import (
    EDITED_SUBDIR,
    BarksPanelsExtType,
    FileTypes,
    PanelDirNames,
    ReaderFilePaths,
)

if TYPE_CHECKING:
    from pathlib import Path


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
        # noinspection PyProtectedMember
        assert reader_file_paths._barks_panels_zip is None
        # noinspection PyProtectedMember
        assert reader_file_paths._panels_ext_type == BarksPanelsExtType.MOSTLY_PNG

        # Check a specific dir
        # noinspection PyProtectedMember
        assert reader_file_paths._panel_dirs[PanelDirNames.COVERS] == panels_dir / "Covers"

    def test_set_barks_panels_source_zip(
        self, reader_file_paths: ReaderFilePaths, panels_zip: Path
    ) -> None:
        with patch("os.path.expandvars", return_value=str(panels_zip)):
            reader_file_paths.set_barks_panels_source(panels_zip, BarksPanelsExtType.JPG)

        assert reader_file_paths.barks_panels_are_encrypted is True
        # noinspection PyProtectedMember
        assert reader_file_paths._barks_panels_zip is not None
        # noinspection PyProtectedMember
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
