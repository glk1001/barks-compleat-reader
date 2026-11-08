from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.reader_file_paths import FileTypes, PanelDirNames
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver


@pytest.fixture
def mock_file_paths() -> MagicMock:
    fp = MagicMock()
    fp.get_file_ext.return_value = ".png"
    fp.get_nontitle_files.return_value = [Path("nt1.png"), Path("nt2.png")]
    fp.get_comic_inset_file.return_value = Path("inset.png")
    fp.get_edited_version_if_possible.return_value = (Path("edited.png"), True)
    fp.get_panel_dir.side_effect = lambda d: (
        Path("/faves") if d == PanelDirNames.FAVOURITES else None
    )
    fp.get_comic_search_files.return_value = [Path("search.png")]
    fp.get_file_type_titles.return_value = ["Title A", "Title B"]
    return fp


class TestReaderFilePathsResolver:
    def test_resolve_flags_each_file_edited_or_not(self, mock_file_paths: MagicMock) -> None:
        """The flag is whether each file is an edited copy, not which pass asked."""
        files = [Path("Splash/edited/splash1.png"), Path("Splash/splash2.png")]
        mock_file_paths.get_title_files.return_value = files
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.resolve("Title", FileTypes.SPLASH, prefer_edited=True)

        assert result == [(files[0], True), (files[1], False)]
        mock_file_paths.get_title_files.assert_called_once_with(
            FileTypes.SPLASH,
            "Title",
            True,  # noqa: FBT003
        )

    def test_an_edited_cover_is_flagged_edited_whichever_pass_found_it(
        self, mock_file_paths: MagicMock
    ) -> None:
        edited_cover = Path("Covers/edited/cover.png")
        mock_file_paths.get_title_files.return_value = [edited_cover]
        resolver = ReaderFilePathsResolver(mock_file_paths)

        assert resolver.resolve("Title", FileTypes.COVER, prefer_edited=False) == [
            (edited_cover, True)
        ]
        mock_file_paths.get_title_files.assert_called_once_with(
            FileTypes.COVER,
            "Title",
            False,  # noqa: FBT003
        )

    def test_resolve_no_files(self, mock_file_paths: MagicMock) -> None:
        mock_file_paths.get_title_files.return_value = []
        resolver = ReaderFilePathsResolver(mock_file_paths)

        assert resolver.resolve("Title", FileTypes.SPLASH, prefer_edited=False) == []

    def test_get_nontitle_files(self, mock_file_paths: MagicMock) -> None:
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_nontitle_files()

        assert len(result) == 2  # noqa: PLR2004
        assert result[0] == Path("nt1.png")

    def test_get_comic_inset_file(self, mock_file_paths: MagicMock) -> None:
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_comic_inset_file(Titles.GOOD_NEIGHBORS)

        mock_file_paths.get_comic_inset_file.assert_called_with(
            Titles.GOOD_NEIGHBORS,
            False,  # noqa: FBT003
        )
        assert result == Path("inset.png")

    def test_get_edited_version_if_possible(self, mock_file_paths: MagicMock) -> None:
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_edited_version_if_possible(Path("original.png"))

        assert result == (Path("edited.png"), True)
        mock_file_paths.get_edited_version_if_possible.assert_called_once_with(Path("original.png"))

    def test_get_file_type_titles(self, mock_file_paths: MagicMock) -> None:
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_file_type_titles(FileTypes.SPLASH)

        assert result == ["Title A", "Title B"]
        mock_file_paths.get_file_type_titles.assert_called_once_with(FileTypes.SPLASH, None)

    def test_get_file_type_titles_passes_the_allowed_titles_through(
        self, mock_file_paths: MagicMock
    ) -> None:
        # A non-default 'allowed_titles' is the only way to tell it apart from
        # the parameter being dropped or replaced by its own default.
        resolver = ReaderFilePathsResolver(mock_file_paths)

        result = resolver.get_file_type_titles(FileTypes.SPLASH, {"Title A"})

        assert result == ["Title A", "Title B"]
        mock_file_paths.get_file_type_titles.assert_called_once_with(FileTypes.SPLASH, {"Title A"})

    def test_get_file_ext(self, mock_file_paths: MagicMock) -> None:
        resolver = ReaderFilePathsResolver(mock_file_paths)

        assert resolver.get_file_ext() == ".png"

    def test_get_comic_favourite_files_dir(self, mock_file_paths: MagicMock) -> None:
        resolver = ReaderFilePathsResolver(mock_file_paths)

        assert resolver.get_comic_favourite_files_dir() == Path("/faves")

    def test_get_comic_search_files(self, mock_file_paths: MagicMock) -> None:
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
        cover_edited = Path("Covers/edited/cover.png")
        cover_std = Path("Covers/cover.png")
        # Splash: edited variant is the same as one of the standard list entries.
        splash_shared = Path("Splash/edited/splash.png")
        splash_plain = Path("Splash/splash.png")

        def get_title_files(file_type: FileTypes, _title: str, prefer_edited: bool) -> list[Path]:
            # Only COVER and SPLASH have files; the other types have none.
            if file_type == FileTypes.COVER:
                return [cover_edited if prefer_edited else cover_std]
            if file_type == FileTypes.SPLASH:
                return [splash_shared] if prefer_edited else [splash_shared, splash_plain]
            return []

        fp.get_title_files.side_effect = get_title_files

        resolver = ReaderFilePathsResolver(fp)

        result = resolver.resolve_all_title_image_files("Title X")

        # A type with no files is left out.
        assert set(result) == {FileTypes.COVER, FileTypes.SPLASH}

        # Cover: the edited and the standard paths both appear,
        # the edited one flagged True and the standard one flagged False.
        assert result[FileTypes.COVER] == {(cover_edited, True), (cover_std, False)}

        # Splash: the shared path is flagged True and must NOT appear again with
        # False; splash_plain appears with False.
        assert result[FileTypes.SPLASH] == {(splash_shared, True), (splash_plain, False)}

        # Each category is asked for the requested title, twice: once preferring
        # edited files and once not. The `prefer_edited=False` pass is invisible in
        # the result, so the call itself is the only place the argument can be checked.
        cover_calls = [c for c in fp.get_title_files.call_args_list if c[0][0] == FileTypes.COVER]
        assert cover_calls == [
            call(FileTypes.COVER, "Title X", True),  # noqa: FBT003
            call(FileTypes.COVER, "Title X", False),  # noqa: FBT003
        ]

    def test_skips_categories_with_no_files(self) -> None:
        fp = MagicMock()
        fp.get_title_files.return_value = []

        resolver = ReaderFilePathsResolver(fp)

        assert resolver.resolve_all_title_image_files("Title Y") == {}
