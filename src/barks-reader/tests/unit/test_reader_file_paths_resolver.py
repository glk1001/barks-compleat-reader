from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

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
        getter = MagicMock(return_value=cover_path)
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.COVER: getter}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.COVER, prefer_edited=False)

        assert result == [(cover_path, False)]
        getter.assert_called_once_with(
            "Title",
            False,  # noqa: FBT003
        )

    def test_resolve_cover_not_found(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.COVER: MagicMock(return_value=None)}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.COVER, prefer_edited=False)

        assert result == []

    def test_resolve_list_type(self, mock_file_paths: MagicMock) -> None:
        files = [Path("splash1.png"), Path("splash2.png")]
        getter = MagicMock(return_value=files)
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.SPLASH: getter}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.SPLASH, prefer_edited=True)

        assert result == [(files[0], True), (files[1], True)]
        getter.assert_called_once_with(
            "Title",
            True,  # noqa: FBT003
        )

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
        mock_file_paths.get_edited_version_if_possible.assert_called_once_with(Path("original.png"))

    def test_get_file_type_titles(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_file_type_titles(FileTypes.SPLASH)

        assert result == ["Title A", "Title B"]
        mock_file_paths.get_file_type_titles.assert_called_once_with(FileTypes.SPLASH, None)

    def test_get_file_type_titles_passes_the_allowed_titles_through(
        self, mock_file_paths: MagicMock
    ) -> None:
        # A non-default 'allowed_titles' is the only way to tell it apart from
        # the parameter being dropped or replaced by its own default.
        mock_file_paths.FILE_TYPE_FILE_GETTERS = {}
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_file_type_titles(FileTypes.SPLASH, {"Title A"})

        assert result == ["Title A", "Title B"]
        mock_file_paths.get_file_type_titles.assert_called_once_with(FileTypes.SPLASH, {"Title A"})

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

        # Each category is asked for the requested title, twice: once preferring
        # edited files and once not. The `prefer_edited=False` pass is invisible in
        # the result (the flag is rewritten to False either way), so the call itself
        # is the only place the argument can be checked.
        assert cover_getter.call_args_list == [
            call("Title X", True),  # noqa: FBT003
            call("Title X", False),  # noqa: FBT003
        ]
        assert splash_getter.call_args_list == [
            call("Title X", True),  # noqa: FBT003
            call("Title X", False),  # noqa: FBT003
        ]

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
