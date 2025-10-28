from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_reader.random_title_images import (
    FIT_MODE_CONTAIN,
    FIT_MODE_COVER,
    ImageInfo,
    RandomTitleImages,
)
from barks_reader.reader_file_paths import FileTypes

if TYPE_CHECKING:
    from barks_reader.reader_settings import ReaderSettings
    from pytest_mock import MockerFixture


@pytest.fixture
def mock_reader_settings(tmp_path: Path) -> MagicMock:
    """Create a mock ReaderSettings object with temporary paths."""
    # Create a mock that simulates the necessary attributes and methods
    settings = MagicMock()

    # Mock file paths
    nontitle_dir = tmp_path / "nontitle"
    nontitle_dir.mkdir()
    (nontitle_dir / "nontitle1.jpg").touch()
    (nontitle_dir / "nontitle2.jpg").touch()

    inset_dir = tmp_path / "insets"
    inset_dir.mkdir()
    (inset_dir / "emergency.jpg").touch()

    # Set up the mock to return these paths
    settings.file_paths.get_nontitle_files.return_value = list(nontitle_dir.glob("*.jpg"))
    settings.file_paths.get_comic_inset_file.return_value = inset_dir / "emergency.jpg"
    # Provide a default mock for get_edited_version_if_possible to prevent ValueErrors.
    # This simulates the behavior of not finding an edited version.
    settings.file_paths.get_edited_version_if_possible.side_effect = lambda filename: (
        filename,
        False,
    )

    return settings


@pytest.fixture
def mock_title_list() -> list[FantaComicBookInfo]:
    """Create a mock list of FantaComicBookInfo objects."""
    # We need to explicitly create the nested mock objects because using `spec`
    # on a dataclass doesn't always allow attribute access as expected.

    # Mock for the first title
    mock_comic_info1 = MagicMock()
    mock_comic_info1.get_title_str.return_value = "title1"
    mock_comic_info1.title = Titles.STATUESQUE_SPENDTHRIFTS
    info1 = MagicMock(spec=FantaComicBookInfo)
    info1.comic_book_info = mock_comic_info1

    # Mock for the second title
    mock_comic_info2 = MagicMock()
    mock_comic_info2.get_title_str.return_value = "title2"
    mock_comic_info2.title = Titles.MAHARAJAH_DONALD
    info2 = MagicMock(spec=FantaComicBookInfo)
    info2.comic_book_info = mock_comic_info2

    return [info1, info2]


@pytest.fixture
def random_image_selector(
    mock_reader_settings: ReaderSettings, mocker: MockerFixture
) -> RandomTitleImages:
    """Fixture to create a RandomTitleImages instance with mocked dependencies."""
    # Mock the TitleImageFileGetter to return predictable file lists
    mocker.patch(
        "barks_reader.random_title_images.TitleImageFileGetter.get_all_title_image_files",
        return_value={
            FileTypes.COVER: {
                (Path("/fake/path/title1/cover.jpg"), False),
                (Path("/fake/path/title1/cover_edited.jpg"), True),
            },
            FileTypes.INSET: {(Path("/fake/path/title1/inset.jpg"), False)},
            FileTypes.SPLASH: {(Path("/fake/path/title2/splash.jpg"), False)},
        },
    )
    return RandomTitleImages(mock_reader_settings)


def test_get_random_image_returns_valid_image_info(
    random_image_selector: RandomTitleImages, mock_title_list: list[FantaComicBookInfo]
) -> None:
    """Test that get_random_image returns a valid ImageInfo object."""
    result = random_image_selector.get_random_image(mock_title_list)
    assert isinstance(result, ImageInfo)
    assert result.filename is not None
    # We don't assert .exists() here because the file path is from a mock
    # and is not expected to exist on the filesystem for this test.
    # Other tests (like test_nontitle_bias) use real temp files where .exists() is appropriate.
    assert result.from_title is not None
    assert result.fit_mode in [FIT_MODE_CONTAIN, FIT_MODE_COVER]


def test_mru_list_is_updated(
    random_image_selector: RandomTitleImages, mock_title_list: list[FantaComicBookInfo]
) -> None:
    """Test that the most-recently-used list is populated."""
    assert len(random_image_selector._most_recently_used_images) == 0  # noqa: SLF001
    random_image_selector.get_random_image(mock_title_list)
    assert len(random_image_selector._most_recently_used_images) == 1  # noqa: SLF001


def test_nontitle_bias(
    random_image_selector: RandomTitleImages,
    mock_title_list: list[FantaComicBookInfo],
    mocker: MockerFixture,
) -> None:
    """Test that a 'nontitle' image can be selected based on the bias."""
    # Mock the higher-level selection method to directly return the "nontitle" files.
    # This is more robust than mocking the low-level `randrange` function.
    mocker.patch.object(
        random_image_selector,
        "_select_random_title_or_nontitle",
        return_value=(None, None, random_image_selector._nontitle_files),  # noqa: SLF001
    )

    result = random_image_selector.get_random_image(
        mock_title_list, file_types={FileTypes.NONTITLE}
    )

    # A nontitle image has no 'from_title'
    assert result.from_title is None
    assert result.filename
    assert "nontitle" in result.filename.name


def test_use_edited_only_filters_files(
    random_image_selector: RandomTitleImages, mock_title_list: list[FantaComicBookInfo]
) -> None:
    """Test that `use_edited_only=True` correctly filters for edited files."""
    # Run it multiple times to ensure we consistently get the edited file.
    for _ in range(10):
        result = random_image_selector.get_random_image(
            mock_title_list,
            file_types={FileTypes.COVER},
            use_only_edited_if_possible=True,
        )
        # The mock is set up so only title1 has an edited cover
        if result.from_title == Titles.STATUESQUE_SPENDTHRIFTS:
            assert result.filename
            assert "edited" in result.filename.name


def test_empty_title_list_returns_emergency_image(
    random_image_selector: RandomTitleImages,
) -> None:
    """Test that an empty title list returns the emergency fallback image."""
    result = random_image_selector.get_random_image([])
    assert result.filename
    assert "emergency" in result.filename.name


def test_candidate_selection_prefers_not_mru(random_image_selector: RandomTitleImages) -> None:
    """Test that the candidate selection logic prefers images not in the MRU list."""
    possible_files = [
        (Path("/fake/path/img1.jpg"), FileTypes.COVER),
        (Path("/fake/path/img2.jpg"), FileTypes.COVER),
        (Path("/fake/path/img3.jpg"), FileTypes.COVER),
    ]
    # Add img1 and img2 to the MRU list
    random_image_selector._most_recently_used_images.append(Path("/fake/path/img1.jpg"))  # noqa: SLF001
    random_image_selector._most_recently_used_images.append(Path("/fake/path/img2.jpg"))  # noqa: SLF001

    # The selection logic should now always pick img3.jpg
    # TODO: ty issue does not make sense. 'random_image_selector._select_best_candidate_image' is
    #       not an iterable.
    selected_file, _ = random_image_selector._select_best_candidate_image(  # noqa: SLF001 # ty: ignore[not-iterable]
        possible_files, "any_title"
    )

    assert selected_file.name == "img3.jpg"
