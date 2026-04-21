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

    def test_resolve_list_type_empty(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.SPLASH: MagicMock(return_value=[])}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.SPLASH, prefer_edited=False)

        assert result == []

    def test_get_file_ext(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        assert resolver.get_file_ext() == ".png"

    def test_get_comic_favourite_files_dir(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        assert resolver.get_comic_favourite_files_dir() == Path("/faves")

    def test_get_comic_search_files(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_comic_search_files("Title", prefer_edited=True)

        mock_file_paths.get_comic_search_files.assert_called_once_with(
            "Title",
            True,  # noqa: FBT003
        )
        assert result == [Path("search.png")]


class TestResolveAllTitleImageFiles:
    def test_merges_edited_and_standard_files_across_categories(self) -> None:
        fp = MagicMock()
        # Cover: edited variant differs from the standard variant.
        cover_edited = Path("cover-edited.png")
        cover_std = Path("cover.png")
        # Splash: edited variant is the same as one of the standard list entries.
        splash_shared = Path("splash-edited.png")
        splash_plain = Path("splash.png")

        cover_getter = MagicMock(
            side_effect=lambda _title, prefer_edited: cover_edited if prefer_edited else cover_std
        )
        splash_getter = MagicMock(
            side_effect=lambda _title, prefer_edited: (
                [splash_shared] if prefer_edited else [splash_shared, splash_plain]
            )
        )

        # Only include COVER and SPLASH; other types return empty.
        empty_getter = MagicMock(return_value=[])
        fp.FILE_TYPE_FILE_GETTERS = {
            ft: empty_getter for ft in FileTypes if ft != FileTypes.NONTITLE
        }
        fp.FILE_TYPE_FILE_GETTERS[FileTypes.COVER] = cover_getter
        fp.FILE_TYPE_FILE_GETTERS[FileTypes.SPLASH] = splash_getter

        resolver = ReaderFilePathsResolver(fp)

        result = resolver.resolve_all_title_image_files("Title X")

        # NONTITLE is skipped entirely.
        assert FileTypes.NONTITLE not in result

        # Cover: the edited and the standard paths both appear,
        # the edited one flagged True and the standard one flagged False.
        assert result[FileTypes.COVER] == {(cover_edited, True), (cover_std, False)}

        # Splash: the shared path is flagged True (from the edited list) and
        # must NOT appear again with False; splash_plain appears with False.
        assert result[FileTypes.SPLASH] == {(splash_shared, True), (splash_plain, False)}

    def test_skips_categories_with_no_files(self) -> None:
        fp = MagicMock()
        fp.FILE_TYPE_FILE_GETTERS = {
            ft: MagicMock(return_value=[]) for ft in FileTypes if ft != FileTypes.NONTITLE
        }
        # COVER getter returns None for both prefer_edited values.
        fp.FILE_TYPE_FILE_GETTERS[FileTypes.COVER] = MagicMock(return_value=None)

        resolver = ReaderFilePathsResolver(fp)

        result = resolver.resolve_all_title_image_files("Title Y")

        assert result == {}
