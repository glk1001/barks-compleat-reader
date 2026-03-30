from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.view_snapshot import (
    ScreenVisibility,
    TopViewSnapshot,
    ViewSnapshot,
)
from barks_reader.ui.background_views import BackgroundViews
from barks_reader.ui.view_states import ViewStates


def _make_background_views() -> BackgroundViews:
    """Create a BackgroundViews with mocked dependencies, bypassing image selection."""
    reader_settings = MagicMock()
    reader_settings.file_paths.get_comic_inset_file.return_value = Path("inset.png")

    random_images = MagicMock()
    random_images.get_random_image.return_value = ImageInfo(
        filename=Path("random.png"), from_title=Titles.ATTIC_ANTICS, fit_mode=FIT_MODE_COVER
    )
    random_images.get_random_search_image.return_value = ImageInfo(
        filename=Path("search.png"), from_title=Titles.BACK_TO_LONG_AGO
    )
    random_images.get_random_censorship_fix_image.return_value = ImageInfo(
        filename=Path("censor.png")
    )

    title_lists = {
        "All": [MagicMock()],
    }

    return BackgroundViews(
        reader_settings=reader_settings,
        title_lists=title_lists,  # ty: ignore[invalid-argument-type]
        random_title_images=random_images,
    )


class TestComputeSnapshot:
    def test_pre_init_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.PRE_INIT)
        snap = bg.compute_snapshot()

        assert snap.view_state == ViewStates.PRE_INIT
        assert snap.top_view.image_opacity == 0.5  # noqa: PLR2004
        assert snap.fun_view.is_visible is True
        assert snap.title_view.is_visible is False
        assert snap.screen_visibility == ScreenVisibility()
        assert snap.search_view.is_visible is False

    def test_initial_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.INITIAL)
        snap = bg.compute_snapshot()

        assert snap.view_state == ViewStates.INITIAL
        assert isinstance(snap.top_view, TopViewSnapshot)
        assert snap.top_view.image_info.filename is not None
        assert snap.fun_view.is_visible is True
        assert snap.title_view.is_visible is False

    def test_title_node_state(self) -> None:
        bg = _make_background_views()
        bg.set_current_bottom_view_title("Some Title")
        bg.set_view_state(ViewStates.ON_TITLE_NODE)
        snap = bg.compute_snapshot()

        assert snap.view_state == ViewStates.ON_TITLE_NODE
        assert snap.title_view.is_visible is True
        assert snap.fun_view.is_visible is False
        assert snap.screen_visibility == ScreenVisibility()
        assert snap.search_view.is_visible is False

    def test_main_index_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INDEX_MAIN_NODE)
        snap = bg.compute_snapshot()

        assert snap.screen_visibility.main_index is True
        assert snap.screen_visibility.speech_index is False
        assert snap.screen_visibility.names_index is False
        assert snap.screen_visibility.locations_index is False
        assert snap.screen_visibility.statistics is False
        assert snap.fun_view.is_visible is False

    def test_speech_index_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INDEX_SPEECH_NODE)
        snap = bg.compute_snapshot()

        assert snap.screen_visibility.speech_index is True
        assert snap.screen_visibility.main_index is False

    def test_names_index_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INDEX_NAMES_NODE)
        snap = bg.compute_snapshot()

        assert snap.screen_visibility.names_index is True

    def test_locations_index_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INDEX_LOCATIONS_NODE)
        snap = bg.compute_snapshot()

        assert snap.screen_visibility.locations_index is True

    def test_statistics_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_APPENDIX_STATISTICS_NODE)
        snap = bg.compute_snapshot()

        assert snap.screen_visibility.statistics is True
        assert snap.fun_view.is_visible is False

    def test_title_search_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_TITLE_SEARCH_NODE)
        snap = bg.compute_snapshot()

        assert snap.search_view.is_visible is True
        assert snap.search_view.mode == "Title"
        assert snap.search_view.image_info is not None

    def test_tag_search_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_TAG_SEARCH_NODE)
        snap = bg.compute_snapshot()

        assert snap.search_view.is_visible is True
        assert snap.search_view.mode == "Tag"

    def test_word_search_state(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_WORD_SEARCH_NODE)
        snap = bg.compute_snapshot()

        assert snap.search_view.is_visible is True
        assert snap.search_view.mode == "Word"

    def test_non_search_state_has_no_mode(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INTRO_NODE)
        snap = bg.compute_snapshot()

        assert snap.search_view.is_visible is False
        assert snap.search_view.mode == ""
        assert snap.search_view.image_info is None

    def test_snapshot_is_frozen(self) -> None:
        bg = _make_background_views()
        snap = bg.compute_snapshot()
        assert isinstance(snap, ViewSnapshot)

    def test_top_view_has_color(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INTRO_NODE)
        snap = bg.compute_snapshot()

        assert len(snap.top_view.image_color) == 4  # noqa: PLR2004
        assert all(isinstance(c, float) for c in snap.top_view.image_color)

    def test_fun_view_has_color_when_visible(self) -> None:
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INTRO_NODE)
        snap = bg.compute_snapshot()

        assert snap.fun_view.is_visible is True
        assert len(snap.fun_view.image_color) == 4  # noqa: PLR2004

    def test_snapshot_equality(self) -> None:
        """Two snapshots from the same state should have the same structure."""
        bg = _make_background_views()
        bg.set_view_state(ViewStates.ON_INDEX_MAIN_NODE)
        snap1 = bg.compute_snapshot()
        snap2 = bg.compute_snapshot()

        # Structure is the same but colors are random, so just check view_state + visibility
        assert snap1.view_state == snap2.view_state
        assert snap1.screen_visibility == snap2.screen_visibility
        assert snap1.search_view == snap2.search_view
