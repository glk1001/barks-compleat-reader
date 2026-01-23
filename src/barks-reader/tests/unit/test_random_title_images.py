# ruff: noqa: SLF001

from __future__ import annotations

import random
from pathlib import Path
from random import randrange
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core import random_title_images as rti_module
from barks_reader.core.image_file_getter import TitleImageFileGetter
from barks_reader.core.random_title_images import FIT_MODE_COVER, RandomTitleImages
from barks_reader.core.reader_file_paths import FileTypes
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.reader_utils import get_all_files_in_dir

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock the ReaderSettings and its file path helpers."""
    settings = MagicMock(spec=ReaderSettings)
    settings.sys_file_paths.get_reader_icon_files_dir.return_value = Path("/icons")
    settings.file_paths.get_file_ext.return_value = ".png"
    settings.file_paths.get_comic_inset_file.return_value = Path("inset.png")
    settings.file_paths.get_comic_favourite_files_dir.return_value = Path("/faves")
    settings.file_paths.get_nontitle_files.return_value = [Path("nontitle1.png")]
    settings.file_paths.get_comic_search_files.return_value = [Path("search1.png")]
    # Default behavior for edited version check: return edited version exists
    settings.file_paths.get_edited_version_if_possible.return_value = (Path("edited.png"), True)
    return settings


@pytest.fixture
def mock_file_getter() -> MagicMock:
    """Mock the TitleImageFileGetter."""
    mock = MagicMock()
    # Default: return some files for any title query
    mock.get_all_title_image_files.return_value = {
        FileTypes.SPLASH: {(Path("splash.png"), False)},
        FileTypes.COVER: {(Path("cover.png"), False)},
    }
    return mock


@pytest.fixture
def random_images(
    mock_settings: MagicMock, mock_file_getter: MagicMock
) -> Generator[RandomTitleImages]:
    """Create a RandomTitleImages instance with mocked dependencies."""
    # Patch dependencies used in __init__
    with (
        patch.object(rti_module, TitleImageFileGetter.__name__, return_value=mock_file_getter),
        patch.object(
            rti_module,
            get_all_files_in_dir.__name__,
            return_value=[Path("icon1.png"), Path("icon2.png")],
        ),
        patch.object(random, random.shuffle.__name__),
    ):
        ri = RandomTitleImages(mock_settings)
        yield ri


class TestRandomTitleImages:
    def test_init(self, random_images: RandomTitleImages, mock_settings: MagicMock) -> None:
        """Test initialization of RandomTitleImages."""
        assert random_images._reader_settings == mock_settings
        assert len(random_images._all_reader_icon_files) == 2  # noqa: PLR2004
        assert random_images._next_reader_icon_file == 0

    def test_get_random_search_image(
        self, random_images: RandomTitleImages, mock_settings: MagicMock
    ) -> None:
        """Test getting a random search image."""
        # Mock random.choice to return a specific title
        with patch.object(random, random.choice.__name__, return_value=Titles.TRACKING_SANDY):
            info = random_images.get_random_search_image()

            assert info.from_title == Titles.TRACKING_SANDY
            assert info.fit_mode == FIT_MODE_COVER
            # Verify it called get_comic_search_files
            mock_settings.file_paths.get_comic_search_files.assert_called()

    def test_get_random_reader_app_icon_file(self, random_images: RandomTitleImages) -> None:
        """Test cycling through reader app icons."""
        # Initial state is 0
        icon1 = random_images.get_random_reader_app_icon_file()
        assert icon1 == Path("icon1.png")
        assert random_images._next_reader_icon_file == 1

        icon2 = random_images.get_random_reader_app_icon_file()
        assert icon2 == Path("icon2.png")
        assert random_images._next_reader_icon_file == 0

        icon3 = random_images.get_random_reader_app_icon_file()
        assert icon3 == Path("icon1.png")

    def test_get_random_censorship_fix_image(self, random_images: RandomTitleImages) -> None:
        """Test getting a random censorship fix image."""
        mock_choice_ret = (Titles.VACATION_TIME, "censored.png")
        with patch.object(random, random.choice.__name__, return_value=mock_choice_ret):
            info = random_images.get_random_censorship_fix_image()

            assert info.from_title == Titles.VACATION_TIME
            assert info.filename == Path("/faves") / "censored.png"

    def test_get_random_image_success(self, random_images: RandomTitleImages) -> None:
        """Test successfully getting a random image for a title."""
        mock_title_info = MagicMock()
        mock_title_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_title_info.comic_book_info.get_title_str.return_value = "Donald Duck Finds Pirate Gold"

        # We need to mock:
        # 1. randrange (to avoid nontitle selection)
        # 2. random.choice (to pick title)
        # 3. random.choice (to pick image from candidates)

        with (
            patch.object(rti_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
        ):
            mock_choice.side_effect = [
                mock_title_info,  # Select title
                (Path("splash.png"), FileTypes.SPLASH),  # Select image
            ]

            info = random_images.get_random_image([mock_title_info])

            assert info.from_title == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
            assert info.filename == Path("splash.png")
            assert info.fit_mode == FIT_MODE_COVER

    def test_get_random_image_nontitle(self, random_images: RandomTitleImages) -> None:
        """Test getting a nontitle image when randrange triggers it."""
        mock_title_info = MagicMock()

        # Force nontitle selection: randrange >= num_titles (1)
        with patch.object(rti_module, randrange.__name__, return_value=100):  # noqa: SIM117
            # random.choice for image selection (nontitle list)
            with patch.object(
                random,
                random.choice.__name__,
                return_value=(Path("nontitle1.png"), FileTypes.NONTITLE),
            ):
                # Must pass FileTypes.NONTITLE in the set, or it won't check
                info = random_images.get_random_image(
                    [mock_title_info], file_types={FileTypes.NONTITLE, FileTypes.SPLASH}
                )

                assert info.from_title is None
                assert info.filename == Path("nontitle1.png")

    def test_get_random_image_fallback(self, random_images: RandomTitleImages) -> None:
        """Test fallback when no suitable image is found after retries."""
        mock_title_info = MagicMock()
        mock_title_info.comic_book_info.get_title_str.return_value = "Title"

        # Simulate failure to find candidates by returning empty list from title selection
        with patch.object(
            random_images, RandomTitleImages._select_random_title_or_nontitle.__name__
        ) as mock_select:
            mock_select.return_value = ("Title", Titles.ADVENTURE_DOWN_UNDER, [])

            info = random_images.get_random_image([mock_title_info])

            # Should return fallback
            assert info.filename == Path("inset.png")
            assert info.from_title == Titles.GOOD_NEIGHBORS

    def test_get_random_image_for_title(self, random_images: RandomTitleImages) -> None:
        """Test getting a random image for a specific title string."""
        title_str = "Some Title"

        # Manually populate the cache to avoid file getter logic
        random_images._title_image_files[title_str] = {
            FileTypes.SPLASH: {(Path("splash.png"), False)}
        }

        with patch.object(
            random, random.choice.__name__, return_value=(Path("splash.png"), FileTypes.SPLASH)
        ):
            path = random_images.get_random_image_for_title(title_str, {FileTypes.SPLASH})
            assert path == Path("splash.png")

    def test_get_random_image_cover_fit_mode(
        self,
        random_images: RandomTitleImages,
        mock_settings: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that cover images check for edited versions and adjust fit mode."""
        mock_title_info = MagicMock()
        mock_title_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_title_info.comic_book_info.get_title_str.return_value = "Pirate Gold"

        # Case: Edited version exists (mock_settings default)
        with (
            patch.object(rti_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
        ):
            mock_choice.side_effect = [mock_title_info, (Path("cover.png"), FileTypes.COVER)]

            info = random_images.get_random_image([mock_title_info])

            # Should use edited version and cover fit mode
            assert info.filename == Path("edited.png")
            assert info.fit_mode == FIT_MODE_COVER
