from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.reader_file_paths import FileTypes
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver


@pytest.fixture
def mock_file_paths() -> MagicMock:
    fp = MagicMock()
    fp.get_file_ext.return_value = ".png"
    fp.get_nontitle_files.return_value = [Path("nt1.png"), Path("nt2.png")]
    fp.get_comic_inset_file.return_value = Path("inset.png")
    fp.get_edited_version_if_possible.return_value = (Path("edited.png"), True)
    fp.get_comic_favourite_files_dir.return_value = Path("/faves")
    fp.get_comic_search_files.return_value = [Path("search.png")]
    fp.get_file_type_titles.return_value = ["Title A", "Title B"]
    return fp


class TestReaderFilePathsResolver:
    def test_resolve_cover(self, mock_file_paths: MagicMock) -> None:
        cover_path = Path("cover.png")
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {
            FileTypes.COVER: MagicMock(return_value=cover_path)
        }
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.COVER, prefer_edited=False)

        assert result == [(cover_path, False)]

    def test_resolve_cover_not_found(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.COVER: MagicMock(return_value=None)}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.COVER, prefer_edited=False)

        assert result == []

    def test_resolve_list_type(self, mock_file_paths: MagicMock) -> None:
        files = [Path("splash1.png"), Path("splash2.png")]
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.SPLASH: MagicMock(return_value=files)}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.SPLASH, prefer_edited=True)

        assert len(result) == 2  # noqa: PLR2004
        assert all(is_edited for _, is_edited in result)

    def test_resolve_unknown_category(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.SPLASH, prefer_edited=False)

        assert result == []

    def test_get_nontitle_files(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_nontitle_files()

        assert len(result) == 2  # noqa: PLR2004
        assert result[0] == Path("nt1.png")

    def test_get_comic_inset_file(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_comic_inset_file(Titles.GOOD_NEIGHBORS)

        mock_file_paths.get_comic_inset_file.assert_called_with(
            Titles.GOOD_NEIGHBORS,
            False,  # noqa: FBT003
        )
        assert result == Path("inset.png")

    def test_get_edited_version_if_possible(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_edited_version_if_possible(Path("original.png"))

        assert result == (Path("edited.png"), True)

    def test_get_file_type_titles(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_file_type_titles(FileTypes.SPLASH)

        assert result == ["Title A", "Title B"]
