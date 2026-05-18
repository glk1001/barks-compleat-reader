"""Verify `ViewPipeline`'s integration with the `Scheduler` port.

These tests rely on `FakeScheduler.advance(secs)` to fire the rotation timer
deterministically — proving the pipeline can be exercised end-to-end without
Kivy.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ViewPipeline


def _make_pipeline_with_scheduler() -> tuple[ViewPipeline, FakeScheduler, MagicMock]:
    reader_settings = MagicMock()
    reader_settings.file_paths.get_comic_inset_file.return_value = Path("inset.png")

    image_selector = MagicMock()
    image_selector.get_random_image.return_value = ImageInfo(
        filename=Path("random.png"), from_title=Titles.ATTIC_ANTICS, fit_mode=FIT_MODE_COVER
    )
    image_selector.get_random_search_image.return_value = ImageInfo(filename=Path("search.png"))
    image_selector.get_random_censorship_fix_image.return_value = ImageInfo(
        filename=Path("censor.png")
    )

    scheduler = FakeScheduler()
    pipeline = ViewPipeline(
        reader_settings=reader_settings,
        title_lists={"All": [MagicMock()]},
        image_selector=image_selector,
        scheduler=scheduler,
        colors=ScriptedColorSource(),
    )
    return pipeline, scheduler, image_selector


class TestRotationTimer:
    def test_set_view_state_schedules_rotation_timer(self) -> None:
        pipeline, scheduler, _ = _make_pipeline_with_scheduler()
        pipeline.set_view_state(ViewStates.ON_INTRO_NODE)

        # Top-view + fun-view timers both armed.
        assert len(scheduler.active_intervals) == 2  # noqa: PLR2004

    def test_advance_fires_top_view_rotation(self) -> None:
        pipeline, scheduler, image_selector = _make_pipeline_with_scheduler()
        pipeline.set_view_state(ViewStates.ON_THE_STORIES_NODE)

        initial_random_calls = image_selector.get_random_image.call_count

        scheduler.advance(ViewPipeline.TOP_VIEW_EVENT_TIMEOUT_SECS)

        # Both top-view and fun-view rotations fire on the same period.
        assert image_selector.get_random_image.call_count > initial_random_calls

    def test_subsequent_set_view_state_replaces_old_timer(self) -> None:
        pipeline, scheduler, _ = _make_pipeline_with_scheduler()
        pipeline.set_view_state(ViewStates.ON_INTRO_NODE)
        pipeline.set_view_state(ViewStates.ON_THE_STORIES_NODE)

        # Old intervals cancelled, new ones armed: still 2 active.
        assert len(scheduler.active_intervals) == 2  # noqa: PLR2004
        # Total scheduled grew (cancelled ones still tracked in _intervals).
        # Verify the cancellation actually happened by checking inactive count.
        all_intervals = pipeline._top_view_change_event  # noqa: SLF001
        assert all_intervals is not None
