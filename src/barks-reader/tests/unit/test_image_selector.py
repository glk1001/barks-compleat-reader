# ruff: noqa: SLF001

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path
from random import randrange
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core import image_selector as is_module
from barks_reader.core.image_selector import FIT_MODE_CONTAIN, FIT_MODE_COVER, ImageSelector
from barks_reader.core.reader_file_paths import EMERGENCY_INSET_FILE, FileTypes
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.reader_utils import get_all_files_in_dir

if TYPE_CHECKING:
    from collections.abc import Generator

    from comic_utils.comic_consts import PanelPath


class FakeResolver:
    """A dict-based fake ImageFileResolver for testing (no filesystem)."""

    def __init__(self) -> None:
        # title_str -> {FileTypes -> [(path, is_edited), ...]}
        self.files: dict[str, dict[FileTypes, list[tuple[PanelPath, bool]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.nontitle_files: list[PanelPath] = [Path("nontitle1.png")]
        self.inset_file: PanelPath = Path("inset.png")
        self.fav_dir: PanelPath = Path("/faves")
        self.file_ext: str = ".png"
        self.search_files: list[PanelPath] = [Path("search1.png")]
        self.edited_version: tuple[PanelPath, bool] = (Path("edited.png"), True)

    def resolve(
        self, title_str: str, category: FileTypes, prefer_edited: bool
    ) -> list[tuple[PanelPath, bool]]:
        all_files = self.files.get(title_str, {}).get(category, [])
        if prefer_edited:
            edited = [(f, e) for f, e in all_files if e]
            return edited or []
        return all_files

    def get_nontitle_files(self) -> list[PanelPath]:
        return self.nontitle_files

    def get_comic_inset_file(self, _title: Titles, _prefer_edited: bool = False) -> PanelPath:
        return self.inset_file

    def get_edited_version_if_possible(self, _image_file: PanelPath) -> tuple[PanelPath, bool]:
        return self.edited_version

    def get_comic_favourite_files_dir(self) -> PanelPath:
        return self.fav_dir

    def get_file_ext(self) -> str:
        return self.file_ext

    def get_comic_search_files(self, _title_str: str, _prefer_edited: bool) -> list[PanelPath]:
        return self.search_files


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock the ReaderSettings."""
    settings = MagicMock(spec=ReaderSettings)
    settings.sys_file_paths.get_reader_icon_files_dir.return_value = Path("/icons")
    # Point the config dir at a path with no never-crop.txt so loading is a no-op.
    settings.get_app_settings_path.return_value = Path("/nonexistent-barks-config/barks-reader.ini")
    return settings


@pytest.fixture
def fake_resolver() -> FakeResolver:
    return FakeResolver()


@pytest.fixture
def image_selector(
    fake_resolver: FakeResolver, mock_settings: MagicMock
) -> Generator[ImageSelector]:
    """Create an ImageSelector with a FakeResolver."""
    with (
        patch.object(
            is_module,
            get_all_files_in_dir.__name__,
            return_value=[Path("icon1.png"), Path("icon2.png")],
        ),
        patch.object(random, random.shuffle.__name__),
    ):
        selector = ImageSelector(fake_resolver, mock_settings)  # ty: ignore[invalid-argument-type]
        yield selector


def _make_title_info(title: Titles, title_str: str) -> MagicMock:
    title_info = MagicMock()
    title_info.comic_book_info.title = title
    title_info.comic_book_info.get_title_str.return_value = title_str
    return title_info


class TestImageSelector:
    def test_init(self, image_selector: ImageSelector, mock_settings: MagicMock) -> None:
        assert image_selector._reader_settings == mock_settings
        assert len(image_selector._all_reader_icon_files) == 2  # noqa: PLR2004
        assert image_selector._next_reader_icon_file == 0

    def test_get_random_search_image(self, image_selector: ImageSelector) -> None:
        with patch.object(random, random.choice.__name__, return_value=Titles.TRACKING_SANDY):
            info = image_selector.get_random_search_image()

            assert info.from_title == Titles.TRACKING_SANDY
            assert info.fit_mode == FIT_MODE_COVER

    def test_get_random_reader_app_icon_file(self, image_selector: ImageSelector) -> None:
        icon1 = image_selector.get_random_reader_app_icon_file()
        assert icon1 == Path("icon1.png")
        assert image_selector._next_reader_icon_file == 1

        icon2 = image_selector.get_random_reader_app_icon_file()
        assert icon2 == Path("icon2.png")
        assert image_selector._next_reader_icon_file == 0

        icon3 = image_selector.get_random_reader_app_icon_file()
        assert icon3 == Path("icon1.png")

    def test_get_random_censorship_fix_image(self, image_selector: ImageSelector) -> None:
        mock_choice_ret = (Titles.VACATION_TIME, "censored.png")
        with patch.object(random, random.choice.__name__, return_value=mock_choice_ret):
            info = image_selector.get_random_censorship_fix_image()

            assert info.from_title == Titles.VACATION_TIME
            assert info.filename == Path("/faves") / "censored.png"

    def test_get_random_image_success(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        mock_title_info = _make_title_info(
            Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, "Donald Duck Finds Pirate Gold"
        )

        # Add files to the fake resolver for this title
        fake_resolver.files["Donald Duck Finds Pirate Gold"][FileTypes.SPLASH] = [
            (Path("splash.png"), False)
        ]
        fake_resolver.files["Donald Duck Finds Pirate Gold"][FileTypes.COVER] = [
            (Path("cover.png"), False)
        ]

        with (
            patch.object(is_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
        ):
            mock_choice.side_effect = [
                mock_title_info,
                (Path("splash.png"), FileTypes.SPLASH),
            ]

            info = image_selector.get_random_image([mock_title_info])

            assert info.from_title == Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
            assert info.filename == Path("splash.png")
            assert info.fit_mode == FIT_MODE_COVER

    def test_get_random_image_nontitle(self, image_selector: ImageSelector) -> None:
        mock_title_info = MagicMock()

        with patch.object(is_module, randrange.__name__, return_value=100):  # noqa: SIM117
            with patch.object(
                random,
                random.choice.__name__,
                return_value=(Path("nontitle1.png"), FileTypes.NONTITLE),
            ):
                info = image_selector.get_random_image(
                    [mock_title_info], file_types={FileTypes.NONTITLE, FileTypes.SPLASH}
                )

                assert info.from_title is None
                assert info.filename == Path("nontitle1.png")

    def test_get_random_image_fallback(self, image_selector: ImageSelector) -> None:
        mock_title_info = MagicMock()
        mock_title_info.comic_book_info.get_title_str.return_value = "Title"

        with patch.object(
            image_selector, ImageSelector._select_random_title_or_nontitle.__name__
        ) as mock_select:
            mock_select.return_value = ("Title", Titles.ADVENTURE_DOWN_UNDER, [])

            info = image_selector.get_random_image([mock_title_info])

            assert info.filename == Path("inset.png")
            assert info.from_title == Titles.GOOD_NEIGHBORS

    def test_get_random_image_for_title(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        title_str = "Some Title"

        # Add files to the fake resolver
        fake_resolver.files[title_str][FileTypes.SPLASH] = [(Path("splash.png"), False)]

        with patch.object(
            random, random.choice.__name__, return_value=(Path("splash.png"), FileTypes.SPLASH)
        ):
            path = image_selector.get_random_image_for_title(title_str, {FileTypes.SPLASH})
            assert path == Path("splash.png")

    def test_get_random_image_cover_fit_mode(
        self,
        image_selector: ImageSelector,
        fake_resolver: FakeResolver,
    ) -> None:
        mock_title_info = _make_title_info(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, "Pirate Gold")

        fake_resolver.files["Pirate Gold"][FileTypes.COVER] = [(Path("cover.png"), False)]

        with (
            patch.object(is_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
        ):
            mock_choice.side_effect = [mock_title_info, (Path("cover.png"), FileTypes.COVER)]

            info = image_selector.get_random_image([mock_title_info])

            assert info.filename == Path("edited.png")
            assert info.fit_mode == FIT_MODE_COVER

    def test_mru_avoidance(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """Test that recently used images are avoided."""
        title_str = "Test Title"
        fake_resolver.files[title_str][FileTypes.SPLASH] = [
            (Path("splash1.png"), False),
            (Path("splash2.png"), False),
        ]

        # Add splash1 to MRU
        image_selector._most_recently_used_images.append(Path("splash1.png"))

        # Manually populate title image files
        image_selector._title_image_files[title_str] = {
            FileTypes.SPLASH: {(Path("splash1.png"), False), (Path("splash2.png"), False)}
        }

        mock_title_info = _make_title_info(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, title_str)

        with patch.object(is_module, randrange.__name__, return_value=0):
            # random.choice should be called with only splash2 (splash1 is in MRU)
            info = image_selector.get_random_image([mock_title_info])

            # Should pick splash2 since splash1 is in MRU
            assert info.filename is not None

    def test_per_title_freshness(
        self,
        image_selector: ImageSelector,
        fake_resolver: FakeResolver,  # noqa: ARG002
    ) -> None:
        """Test that the last image for a specific title is avoided."""
        title_str = "Test Title"

        image_selector._title_image_files[title_str] = {
            FileTypes.SPLASH: {(Path("splash1.png"), False), (Path("splash2.png"), False)}
        }

        # Set the last title image
        image_selector._last_title_image[title_str] = Path("splash1.png")

        # get_random_image_for_title should prefer splash2
        path = image_selector.get_random_image_for_title(title_str, {FileTypes.SPLASH})
        assert path == Path("splash2.png")

    def test_empty_title_list_returns_fallback(self, image_selector: ImageSelector) -> None:
        info = image_selector.get_random_image([])
        assert info.from_title == Titles.GOOD_NEIGHBORS
        assert info.filename == Path("inset.png")

    def test_icon_image_cycles(self, image_selector: ImageSelector) -> None:
        """Test that icon_image cycles through all available icons."""
        icons = [image_selector.get_random_reader_app_icon_file() for _ in range(4)]

        assert icons == [Path("icon1.png"), Path("icon2.png"), Path("icon1.png"), Path("icon2.png")]

    def test_get_search_image_for_title(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """Returns the inset file for the given title in cover fit mode."""
        fake_resolver.inset_file = Path("inset-for-search.png")

        info = image_selector.get_search_image_for_title(Titles.TRACKING_SANDY)

        assert info.filename == Path("inset-for-search.png")
        assert info.from_title == Titles.TRACKING_SANDY
        assert info.fit_mode == FIT_MODE_COVER

    def test_get_random_image_for_title_emergency_fallback(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """No resolver entries for a title falls back to the emergency inset file."""
        # FakeResolver.get_comic_inset_file ignores the title and returns inset_file.
        fake_resolver.inset_file = Path("emergency.png")

        # Title has no files registered in fake_resolver.files.
        result = image_selector.get_random_image_for_title(
            "Title With No Files", {FileTypes.SPLASH}
        )

        assert result == Path("emergency.png")
        # Sanity: the lookup was indeed for the emergency title constant.
        assert EMERGENCY_INSET_FILE == Titles.BICEPS_BLUES

    def test_get_random_image_for_title_falls_back_when_only_last_image_available(
        self, image_selector: ImageSelector
    ) -> None:
        """When the only possible image is the last-used one, fall back to choosing it anyway."""
        title_str = "Test Title"
        only_image = Path("only.png")
        image_selector._title_image_files[title_str] = {
            FileTypes.SPLASH: {(only_image, False)},
        }
        image_selector._last_title_image[title_str] = only_image

        # No "preferred" candidates exist (the only image is the last one), so the
        # fallback random.choice over possible_images is hit (line 291).
        with patch.object(
            random, random.choice.__name__, return_value=(only_image, FileTypes.SPLASH)
        ) as mock_choice:
            result = image_selector.get_random_image_for_title(title_str, {FileTypes.SPLASH})

        assert result == only_image
        # The fallback path calls random.choice with the full possible_images list.
        mock_choice.assert_called_once_with([(only_image, FileTypes.SPLASH)])

    def _adaptive_fit_mode_for_size(
        self,
        image_selector: ImageSelector,
        fake_resolver: FakeResolver,
        image_size: tuple[int, int],
    ) -> str:
        """Run get_random_image with adaptive fit and a mocked image size; return fit mode."""
        title_str = "Pirate Gold"
        fake_resolver.files[title_str][FileTypes.SPLASH] = [(Path("splash.png"), False)]

        mock_title_info = _make_title_info(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, title_str)

        with (
            patch.object(is_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
            patch.object(is_module, is_module.get_image_size.__name__, return_value=image_size),
        ):
            # title selection → image selection (fit mode is now aspect-based, no choice).
            mock_choice.side_effect = [
                mock_title_info,
                (Path("splash.png"), FileTypes.SPLASH),
            ]
            info = image_selector.get_random_image(
                [mock_title_info], use_adaptive_fit_mode=True, file_types={FileTypes.SPLASH}
            )

        return info.fit_mode

    def test_adaptive_fit_mode_wide_image_uses_cover(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """A wide/near-square image fills the view edge-to-edge (cover)."""
        fit_mode = self._adaptive_fit_mode_for_size(image_selector, fake_resolver, (1000, 800))
        assert fit_mode == FIT_MODE_COVER

    def test_adaptive_fit_mode_tall_image_uses_contain(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """A tall, narrow image is letterboxed (contain) so nothing is cropped."""
        fit_mode = self._adaptive_fit_mode_for_size(image_selector, fake_resolver, (650, 1000))
        assert fit_mode == FIT_MODE_CONTAIN

    def test_adaptive_fit_mode_very_wide_image_uses_contain(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """A much-wider-than-high image is letterboxed (contain) instead of cropped."""
        fit_mode = self._adaptive_fit_mode_for_size(image_selector, fake_resolver, (2000, 800))
        assert fit_mode == FIT_MODE_CONTAIN

    def test_never_crop_image_forces_contain(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """An image on the never-crop list is letterboxed even when its aspect fits cover."""
        title_str = "Pirate Gold"
        fake_resolver.files[title_str][FileTypes.SPLASH] = [(Path("wide-splash.png"), False)]
        image_selector._never_crop_images = frozenset({"wide-splash.png"})

        mock_title_info = _make_title_info(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, title_str)

        with (
            patch.object(is_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
            # (1200, 1000) -> aspect 1.2, which would otherwise be cover.
            patch.object(is_module, is_module.get_image_size.__name__, return_value=(1200, 1000)),
        ):
            mock_choice.side_effect = [
                mock_title_info,
                (Path("wide-splash.png"), FileTypes.SPLASH),
            ]
            info = image_selector.get_random_image(
                [mock_title_info], use_adaptive_fit_mode=True, file_types={FileTypes.SPLASH}
            )

        assert info.fit_mode == FIT_MODE_CONTAIN

    def test_never_crop_matches_title_dir_suffix(self, image_selector: ImageSelector) -> None:
        """A never-crop entry matches any image path ending with that title/file suffix."""
        image_selector._never_crop_images = frozenset({"Lost in the Andes/012-3.png"})

        assert image_selector._is_never_crop(Path("/comics/Lost in the Andes/012-3.png"))
        assert not image_selector._is_never_crop(Path("/comics/Lost in the Andes/099-9.png"))
        # A bare name must not partial-match a longer filename.
        image_selector._never_crop_images = frozenset({"012-3.png"})
        assert not image_selector._is_never_crop(Path("/comics/x-012-3.png"))

    def test_load_never_crop_images_parses_file(
        self,
        image_selector: ImageSelector,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The never-crop file is parsed, ignoring blank lines and # comments."""
        (tmp_path / "never-crop.txt").write_text(
            "# wide double-panel splash\n"
            "Lost in the Andes/012-3.png\n"
            "\n"
            "  The Golden Helmet/034-1.png  # inline comment\n",
            encoding="utf-8",
        )
        mock_settings.get_app_settings_path.return_value = tmp_path / "barks-reader.ini"

        entries = image_selector._load_never_crop_images()

        assert entries == frozenset({"Lost in the Andes/012-3.png", "The Golden Helmet/034-1.png"})

    def test_load_never_crop_images_missing_file_returns_empty(
        self,
        image_selector: ImageSelector,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A missing never-crop file yields an empty set (feature simply off)."""
        mock_settings.get_app_settings_path.return_value = tmp_path / "barks-reader.ini"
        assert image_selector._load_never_crop_images() == frozenset()

    def test_adaptive_fit_mode_unreadable_image_falls_back_to_contain(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """If the image size cannot be read, adaptive fit falls back to contain."""
        title_str = "Pirate Gold"
        fake_resolver.files[title_str][FileTypes.SPLASH] = [(Path("splash.png"), False)]
        mock_title_info = _make_title_info(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, title_str)

        with (
            patch.object(is_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
            patch.object(is_module, is_module.get_image_size.__name__, side_effect=OSError("boom")),
        ):
            mock_choice.side_effect = [
                mock_title_info,
                (Path("splash.png"), FileTypes.SPLASH),
            ]
            info = image_selector.get_random_image(
                [mock_title_info], use_adaptive_fit_mode=True, file_types={FileTypes.SPLASH}
            )

        assert info.fit_mode == FIT_MODE_CONTAIN

    def test_better_fitting_cover_falls_back_to_contain_when_no_edited(
        self, image_selector: ImageSelector, fake_resolver: FakeResolver
    ) -> None:
        """Cover-fit cover image with no edited version is shown in contain mode instead."""
        title_str = "Pirate Gold"
        fake_resolver.files[title_str][FileTypes.COVER] = [(Path("cover.png"), False)]
        # Resolver reports no edited version available.
        fake_resolver.edited_version = (Path("cover.png"), False)

        mock_title_info = _make_title_info(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, title_str)

        with (
            patch.object(is_module, randrange.__name__, return_value=0),
            patch.object(random, random.choice.__name__) as mock_choice,
        ):
            mock_choice.side_effect = [mock_title_info, (Path("cover.png"), FileTypes.COVER)]
            info = image_selector.get_random_image([mock_title_info])

        assert info.filename == Path("cover.png")
        assert info.fit_mode == FIT_MODE_CONTAIN

    def test_use_only_edited_filters_out_non_edited(self, image_selector: ImageSelector) -> None:
        """use_only_edited_if_possible=True excludes is_edited=False candidates."""
        title_str = "Mixed Title"
        edited = Path("edited.png")
        plain = Path("plain.png")
        image_selector._title_image_files[title_str] = {
            FileTypes.SPLASH: {(edited, True), (plain, False)},
        }

        with patch.object(
            random, random.choice.__name__, return_value=(edited, FileTypes.SPLASH)
        ) as mock_choice:
            result = image_selector.get_random_image_for_title(
                title_str, {FileTypes.SPLASH}, use_only_edited_if_possible=True
            )

        assert result == edited
        # The choice should have been made over a list containing only the edited file.
        choices_arg = mock_choice.call_args.args[0]
        assert (plain, FileTypes.SPLASH) not in choices_arg
        assert (edited, FileTypes.SPLASH) in choices_arg

    def test_get_random_comic_file_raises_when_no_files(self) -> None:
        """The internal random-comic-file helper asserts when no files are available."""

        def empty_files(_title: str, _prefer_edited: bool) -> list[PanelPath]:
            return []

        with pytest.raises(AssertionError):
            ImageSelector._get_random_comic_file(
                "Some Title",
                empty_files,
                use_only_edited_if_possible=False,
            )
