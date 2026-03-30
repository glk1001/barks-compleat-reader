from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import ANY, MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import (
    ALL_LISTS,
    SERIES_CS,
    SERIES_USA,
)
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.ui import background_views as background_views_module
from barks_reader.ui.background_views import BackgroundViews, ImageThemes
from barks_reader.ui.view_states import ViewStates

if TYPE_CHECKING:
    from collections.abc import Generator


class TestBackgroundViews:
    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None]:
        self.mock_settings = MagicMock()
        self.mock_random_images = MagicMock()
        self.title_lists = defaultdict(list)
        self.title_lists.update(
            {
                ALL_LISTS: [MagicMock(name="All1"), MagicMock(name="All2")],
                SERIES_CS: [MagicMock(name="CS1")],
                SERIES_USA: [MagicMock(name="US1")],
                "1942": [MagicMock(name="1942_1")],
                "1950": [MagicMock(name="1950_1")],
                "CS-1942-1946": [MagicMock(name="CS_Range")],
                "US-1951-1954": [MagicMock(name="US_Range")],
                "MyCategory": [MagicMock(name="Cat1")],
            }
        )

        # Mock RandomTitleImages methods to return a dummy ImageInfo
        self.dummy_image_info = ImageInfo(
            filename=Path("dummy.png"),
            from_title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            fit_mode=FIT_MODE_COVER,
        )
        self.mock_random_images.get_random_image.return_value = self.dummy_image_info
        self.mock_random_images.get_random_search_image.return_value = self.dummy_image_info
        self.mock_random_images.get_random_censorship_fix_image.return_value = self.dummy_image_info
        self.mock_random_images.get_random_image_for_title.return_value = "random_title.png"

        # Patch Clock to avoid scheduling
        self.clock_patcher = patch.object(background_views_module, "Clock")
        self.mock_clock = self.clock_patcher.start()

        self.bg_views = BackgroundViews(
            self.mock_settings, self.title_lists, self.mock_random_images
        )

        yield

        self.clock_patcher.stop()

    def test_initialization(self) -> None:
        assert self.bg_views.get_view_state() == ViewStates.PRE_INIT

    def test_set_view_state_pre_init(self) -> None:
        self.bg_views.set_view_state(ViewStates.PRE_INIT)
        snap = self.bg_views.compute_snapshot()
        assert snap.top_view.image_opacity == 0.5  # noqa: PLR2004
        assert snap.fun_view.is_visible is True
        assert snap.title_view.is_visible is False

    # noinspection GrazieInspection
    def test_set_view_state_series(self) -> None:
        self.bg_views.set_view_state(ViewStates.ON_CS_NODE)

        self.mock_random_images.get_random_image.assert_any_call(
            self.title_lists[SERIES_CS], file_types=ANY, use_only_edited_if_possible=True
        )
        snap = self.bg_views.compute_snapshot()
        assert snap.top_view.image_info == self.dummy_image_info

    def test_set_view_state_intro(self) -> None:
        self.mock_settings.file_paths.get_comic_inset_file.return_value = "intro.png"

        self.bg_views.set_view_state(ViewStates.ON_INTRO_NODE)

        snap = self.bg_views.compute_snapshot()
        assert snap.top_view.image_info.filename == "intro.png"
        assert snap.top_view.image_info.from_title == Titles.ADVENTURE_DOWN_UNDER

    def test_set_view_state_stories(self) -> None:
        self.bg_views.set_view_state(ViewStates.ON_THE_STORIES_NODE)

        self.mock_random_images.get_random_image.assert_any_call(
            self.title_lists[ALL_LISTS], file_types=ANY, use_only_edited_if_possible=True
        )

    def test_set_view_state_cs_year_range(self) -> None:
        self.bg_views.set_current_cs_year_range("1942-1946")

        self.bg_views.set_view_state(ViewStates.ON_CS_YEAR_RANGE_NODE)

        self.mock_random_images.get_random_image.assert_any_call(
            self.title_lists["CS-1942-1946"], file_types=ANY, use_only_edited_if_possible=True
        )

    def test_set_view_state_category(self) -> None:
        self.bg_views.set_current_category("MyCategory")

        self.bg_views.set_view_state(ViewStates.ON_CATEGORY_NODE)

        self.mock_random_images.get_random_image.assert_any_call(
            self.title_lists["MyCategory"], file_types=ANY, use_only_edited_if_possible=True
        )

    def test_set_view_state_search(self) -> None:
        self.bg_views.set_view_state(ViewStates.ON_SEARCH_NODE)
        self.mock_random_images.get_random_search_image.assert_called_once()

    def test_set_view_state_appendix(self) -> None:
        self.mock_settings.file_paths.get_comic_inset_file.return_value = "appendix.png"
        self.bg_views.set_view_state(ViewStates.ON_APPENDIX_NODE)

        snap = self.bg_views.compute_snapshot()
        assert snap.top_view.image_info.filename == "appendix.png"
        assert snap.top_view.image_info.from_title == Titles.FABULOUS_PHILOSOPHERS_STONE_THE

    def test_set_view_state_index(self) -> None:
        self.mock_settings.file_paths.get_comic_inset_file.return_value = "index.png"
        self.bg_views.set_view_state(ViewStates.ON_INDEX_NODE)

        snap = self.bg_views.compute_snapshot()
        assert snap.top_view.image_info.filename == "index.png"
        assert snap.top_view.image_info.from_title == Titles.TRUANT_OFFICER_DONALD

    def test_opacities(self) -> None:
        # ON_TITLE_NODE: Title visible, Fun not visible
        self.bg_views.set_view_state(ViewStates.ON_TITLE_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.title_view.is_visible is True
        assert snap.fun_view.is_visible is False

        # ON_INTRO_NODE: Title not visible, Fun visible
        self.bg_views.set_view_state(ViewStates.ON_INTRO_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.title_view.is_visible is False
        assert snap.fun_view.is_visible is True

    def test_set_fun_image_themes(self) -> None:
        self.mock_settings.file_paths.get_file_type_titles.return_value = set()

        mock_info_1942 = MagicMock()
        mock_info_1942.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        self.title_lists["1942"] = [mock_info_1942]

        with patch.object(background_views_module, "ALL_FANTA_COMIC_BOOK_INFO") as mock_all_info:
            mock_all_info.__getitem__.return_value = mock_info_1942

            self.bg_views.set_fun_image_themes({ImageThemes.FORTIES})
            self.bg_views.set_view_state(ViewStates.ON_INTRO_NODE)

            args, _ = self.mock_random_images.get_random_image.call_args
            passed_list = args[0]
            assert mock_info_1942 in passed_list

    def test_set_bottom_view_title_image(self) -> None:
        # Case 1: Explicit file provided
        self.bg_views.set_bottom_view_title_image_file(Path("explicit.png"))
        self.bg_views.set_view_state(ViewStates.ON_TITLE_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.title_view.image_info is not None
        assert snap.title_view.image_info.filename == Path("explicit.png")

        # Case 2: Random based on current title
        self.bg_views.set_bottom_view_title_image_file(None)  # Reset
        self.bg_views.set_current_bottom_view_title("My Title")
        self.mock_random_images.get_random_image_for_title.return_value = Path("random.png")

        self.bg_views.set_next_bottom_view_title_image()
        self.bg_views.set_view_state(ViewStates.ON_TITLE_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.title_view.image_info is not None
        assert snap.title_view.image_info.filename == Path("random.png")

    def test_index_view_opacities(self) -> None:
        # Main Index
        self.bg_views.set_view_state(ViewStates.ON_INDEX_MAIN_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.screen_visibility.main_index is True
        assert snap.screen_visibility.speech_index is False

        # Speech Index
        self.bg_views.set_view_state(ViewStates.ON_INDEX_SPEECH_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.screen_visibility.main_index is False
        assert snap.screen_visibility.speech_index is True

        # Other
        self.bg_views.set_view_state(ViewStates.ON_INTRO_NODE)
        snap = self.bg_views.compute_snapshot()
        assert snap.screen_visibility.main_index is False
        assert snap.screen_visibility.speech_index is False
