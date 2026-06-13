"""Snapshot-emission tests for `ViewPipeline`.

Drives the pipeline through every navigable view state and asserts on the
resulting `ViewSnapshot`. Uses `core.testing.fakes` to avoid Kivy, disk, and
the global `random` module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ViewPipeline
from barks_reader.core.view_request import ViewRequest
from barks_reader.core.view_snapshot import (
    ScreenVisibility,
    TopViewSnapshot,
    ViewSnapshot,
)


def _make_pipeline() -> ViewPipeline:
    """Create a ViewPipeline with mocked image selection + fake scheduler/colors."""
    reader_settings = MagicMock()
    reader_settings.file_paths.get_comic_inset_file.return_value = Path("inset.png")

    image_selector = MagicMock()
    image_selector.get_random_image.return_value = ImageInfo(
        filename=Path("random.png"), from_title=Titles.ATTIC_ANTICS, fit_mode=FIT_MODE_COVER
    )
    image_selector.get_random_search_image.return_value = ImageInfo(
        filename=Path("search.png"), from_title=Titles.BACK_TO_LONG_AGO
    )
    image_selector.get_random_censorship_fix_image.return_value = ImageInfo(
        filename=Path("censor.png")
    )

    title_lists = {
        "All": [MagicMock()],
    }

    return ViewPipeline(
        reader_settings=reader_settings,
        title_lists=title_lists,  # ty: ignore[invalid-argument-type]
        image_selector=image_selector,
        scheduler=FakeScheduler(),
        colors=ScriptedColorSource(),
    )


class TestRenderSnapshot:
    def test_pre_init_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.PRE_INIT))

        assert snap.view_state == ViewStates.PRE_INIT
        assert snap.top_view.image_opacity == 0.5  # noqa: PLR2004
        assert snap.fun_view.is_visible is True
        assert snap.title_view.is_visible is False
        assert snap.screen_visibility == ScreenVisibility()
        assert snap.search_view.is_visible is False

    def test_initial_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.INITIAL))

        assert snap.view_state == ViewStates.INITIAL
        assert isinstance(snap.top_view, TopViewSnapshot)
        assert snap.top_view.image_info.filename is not None
        assert snap.fun_view.is_visible is True
        assert snap.title_view.is_visible is False

    def test_title_node_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(
            ViewRequest(view_state=ViewStates.ON_TITLE_NODE, title_str="Some Title")
        )

        assert snap.view_state == ViewStates.ON_TITLE_NODE
        assert snap.title_view.is_visible is True
        assert snap.fun_view.is_visible is False
        assert snap.screen_visibility == ScreenVisibility()
        assert snap.search_view.is_visible is False

    def test_main_index_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_MAIN_NODE))

        assert snap.screen_visibility.main_index is True
        assert snap.screen_visibility.speech_index is False
        assert snap.screen_visibility.names_index is False
        assert snap.screen_visibility.locations_index is False
        assert snap.screen_visibility.statistics is False
        assert snap.fun_view.is_visible is False

    def test_speech_index_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_SPEECH_NODE))

        assert snap.screen_visibility.speech_index is True
        assert snap.screen_visibility.main_index is False

    def test_names_index_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_NAMES_NODE))

        assert snap.screen_visibility.names_index is True

    def test_locations_index_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_LOCATIONS_NODE))

        assert snap.screen_visibility.locations_index is True

    def test_statistics_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_APPENDIX_STATISTICS_NODE))

        assert snap.screen_visibility.statistics is True
        assert snap.fun_view.is_visible is False

    def test_title_search_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_TITLE_SEARCH_NODE))

        assert snap.search_view.is_visible is True
        assert snap.search_view.mode == "Title"
        assert snap.search_view.image_info is not None

    def test_tag_search_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_TAG_SEARCH_NODE))

        assert snap.search_view.is_visible is True
        assert snap.search_view.mode == "Tag"

    def test_word_search_state(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_WORD_SEARCH_NODE))

        assert snap.search_view.is_visible is True
        assert snap.search_view.mode == "Word"

    def test_non_search_state_has_no_mode(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        assert snap.search_view.is_visible is False
        assert snap.search_view.mode == ""
        assert snap.search_view.image_info is None

    def test_snapshot_is_frozen(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.PRE_INIT))
        assert isinstance(snap, ViewSnapshot)

    def test_top_view_has_color(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        assert len(snap.top_view.image_color) == 4  # noqa: PLR2004
        assert all(isinstance(c, float) for c in snap.top_view.image_color)

    def test_fun_view_has_color_when_visible(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        assert snap.fun_view.is_visible is True
        assert len(snap.fun_view.image_color) == 4  # noqa: PLR2004

    def test_snapshot_equality(self) -> None:
        """Two snapshots from the same state should have the same structure."""
        pipeline = _make_pipeline()
        snap1 = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_MAIN_NODE))
        snap2 = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_MAIN_NODE))

        assert snap1.view_state == snap2.view_state
        assert snap1.screen_visibility == snap2.screen_visibility
        assert snap1.search_view == snap2.search_view

    def test_current_request_round_trips_nav_context(self) -> None:
        """`current_request()` reflects the last rendered navigation context."""
        pipeline = _make_pipeline()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_TITLE_NODE, title_str="Some Title"))

        request = pipeline.current_request()
        assert request.view_state == ViewStates.ON_TITLE_NODE
        assert request.title_str == "Some Title"
        # The one-shot title image file is never carried back out.
        assert request.title_image_file is None
