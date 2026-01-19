# ruff: noqa: SLF001

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from barks_fantagraphics.barks_titles import Titles
from barks_reader.random_title_images import (
    FIT_MODE_CONTAIN,
    FIT_MODE_COVER,
    RandomTitleImages,
)
from barks_reader.reader_file_paths import FileTypes


class TestRandomTitleImages(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_settings = MagicMock()
        self.mock_settings.file_paths = MagicMock()
        self.mock_settings.sys_file_paths = MagicMock()

        # Mock file paths methods
        self.mock_settings.file_paths.get_file_ext.return_value = ".png"
        self.mock_settings.file_paths.get_comic_inset_file.return_value = Path("emergency.png")
        self.mock_settings.file_paths.get_nontitle_files.return_value = [Path("nontitle1.png")]
        self.mock_settings.file_paths.get_edited_version_if_possible.side_effect = lambda p: (
            p,
            False,
        )
        self.mock_settings.file_paths.get_comic_favourite_files_dir.return_value = Path("faves")

        self.mock_settings.sys_file_paths.get_reader_icon_files_dir.return_value = Path("icons")

        # Patch dependencies
        self.patcher_getter = patch("barks_reader.random_title_images.TitleImageFileGetter")
        self.mock_getter_cls = self.patcher_getter.start()
        self.mock_getter = self.mock_getter_cls.return_value
        self.mock_getter.get_all_title_image_files.return_value = {
            FileTypes.COVER: {(Path("cover.png"), False)},
            FileTypes.SPLASH: {(Path("splash.png"), False)},
        }

        self.patcher_utils = patch("barks_reader.random_title_images.get_all_files_in_dir")
        self.mock_get_files = self.patcher_utils.start()
        self.mock_get_files.return_value = [Path("icon1.png"), Path("icon2.png")]

        self.random_images = RandomTitleImages(self.mock_settings)

    def tearDown(self) -> None:
        self.patcher_getter.stop()
        self.patcher_utils.stop()

    def test_init(self) -> None:
        # Access private attributes to verify initialization
        # noinspection PyProtectedMember
        assert self.random_images._all_reader_icon_files
        # noinspection PyProtectedMember
        assert len(self.random_images._CENSORED_IMAGES) > 0

    def test_get_random_reader_app_icon_file(self) -> None:
        # We mocked get_all_files_in_dir to return 2 icons.
        # Since random.shuffle is called in __init__, order is random, but we can check cycling.

        icon1 = self.random_images.get_random_reader_app_icon_file()
        assert isinstance(icon1, Path)

        icon2 = self.random_images.get_random_reader_app_icon_file()
        assert isinstance(icon2, Path)
        assert icon1 != icon2  # Should be different as list has 2 unique items

        icon3 = self.random_images.get_random_reader_app_icon_file()
        assert icon3 == icon1  # Should cycle back to start

    def test_get_random_image_empty_list(self) -> None:
        info = self.random_images.get_random_image([])
        assert info.from_title == Titles.GOOD_NEIGHBORS
        assert info.filename == Path("emergency.png")

    def test_get_random_image_success(self) -> None:
        mock_title_info = MagicMock()
        mock_title_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_title_info.comic_book_info.get_title_str.return_value = "Donald Duck Finds Pirate Gold"

        # Mock random choices to ensure we pick a title and an image
        # noinspection GrazieInspection
        with (
            patch("random.choice") as mock_choice,
            patch("random.randrange") as mock_randrange,
        ):
            mock_choice.side_effect = [
                mock_title_info,  # For title selection
                (Path("splash.png"), FileTypes.SPLASH),  # For image selection
                FIT_MODE_COVER,  # For fit mode (if called)
            ]
            mock_randrange.return_value = 100  # Force title selection (not nontitle)

            info = self.random_images.get_random_image([mock_title_info])

            assert info.from_title == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
            assert info.filename == Path("splash.png")
            # Default fit mode is 'COVER' if use_random_fit_mode is False
            assert info.fit_mode == FIT_MODE_COVER

    def test_get_random_image_for_title(self) -> None:
        title_str = "Some Title"
        # Mock getter to return specific files for this title
        self.mock_getter.get_all_title_image_files.return_value = {
            FileTypes.COVER: {(Path("specific_cover.png"), False)}
        }

        with patch("random.choice") as mock_choice:
            mock_choice.return_value = (Path("specific_cover.png"), FileTypes.COVER)

            path = self.random_images.get_random_image_for_title(title_str, {FileTypes.COVER})

            assert path == Path("specific_cover.png")
            self.mock_getter.get_all_title_image_files.assert_called_with(title_str)

    def test_get_random_image_for_title_no_images(self) -> None:
        title_str = "Empty Title"
        self.mock_getter.get_all_title_image_files.return_value = {}

        path = self.random_images.get_random_image_for_title(title_str, {FileTypes.COVER})

        assert path == Path("emergency.png")

    def test_select_best_candidate_image_mru(self) -> None:
        # Test MRU logic
        possible_files = [
            (Path("img1.png"), FileTypes.COVER),
            (Path("img2.png"), FileTypes.COVER),
        ]

        # Add img1 to MRU
        # noinspection PyProtectedMember
        self.random_images._add_last_image(Path("img1.png"))

        # Should pick img2
        with patch("random.choice") as mock_choice:
            mock_choice.side_effect = lambda x: x[0]  # Pick first available

            # noinspection PyProtectedMember
            result = self.random_images._select_best_candidate_image(possible_files, "Title")
            assert result == (Path("img2.png"), FileTypes.COVER)

    # noinspection GrazieInspection
    def test_get_fit_mode(self) -> None:
        # If use_random_fit_mode is 'False', should return 'COVER'.
        # noinspection PyProtectedMember
        assert self.random_images._get_fit_mode(use_random_fit_mode=False) == FIT_MODE_COVER

        # If True, random
        with patch("random.choice") as mock_choice:
            mock_choice.return_value = FIT_MODE_CONTAIN
            # noinspection PyProtectedMember
            assert self.random_images._get_fit_mode(use_random_fit_mode=True) == FIT_MODE_CONTAIN

    def test_get_better_fitting_image_if_possible(self) -> None:
        # Case 1: Not cover type -> return original
        # noinspection PyProtectedMember
        res = self.random_images._get_better_fitting_image_if_possible(
            Path("img.png"), FIT_MODE_COVER, FileTypes.SPLASH
        )
        assert res == (Path("img.png"), FIT_MODE_COVER)

        # Case 2: Cover type, fit mode cover, edited available
        self.mock_settings.file_paths.get_edited_version_if_possible.side_effect = None
        self.mock_settings.file_paths.get_edited_version_if_possible.return_value = (
            Path("edited.png"),
            True,
        )
        # noinspection PyProtectedMember
        res = self.random_images._get_better_fitting_image_if_possible(
            Path("img.png"), FIT_MODE_COVER, FileTypes.COVER
        )
        assert res == (Path("edited.png"), FIT_MODE_COVER)

        # Case 3: Cover type, fit mode cover, edited NOT available -> switch to contain
        self.mock_settings.file_paths.get_edited_version_if_possible.return_value = (
            Path("img.png"),
            False,
        )
        # noinspection PyProtectedMember
        res = self.random_images._get_better_fitting_image_if_possible(
            Path("img.png"), FIT_MODE_COVER, FileTypes.COVER
        )
        assert res == (Path("img.png"), FIT_MODE_CONTAIN)

    def test_get_random_search_image(self) -> None:
        # Mock _get_random_comic_file to return a path
        with patch.object(RandomTitleImages, "_get_random_comic_file") as mock_get_file:
            mock_get_file.return_value = Path("search.png")

            info = self.random_images.get_random_search_image()

            assert info.filename == Path("search.png")
            assert info.fit_mode == FIT_MODE_COVER
            assert info.from_title is not None

    def test_get_random_censorship_fix_image(self) -> None:
        info = self.random_images.get_random_censorship_fix_image()
        assert info.filename
        assert info.from_title is not None
        assert info.fit_mode == FIT_MODE_COVER
