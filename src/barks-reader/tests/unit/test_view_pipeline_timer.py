"""Verify `ViewPipeline`'s integration with the `Scheduler` port.

These tests rely on `FakeScheduler.advance(secs)` to fire the rotation timer
deterministically — proving the pipeline can be exercised end-to-end without
Kivy.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_COVER, ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ViewPipeline
from barks_reader.core.view_request import ViewRequest

if TYPE_CHECKING:
    from barks_reader.core.view_snapshot import FunViewSnapshot, TopViewSnapshot


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
    def test_render_schedules_rotation_timer(self) -> None:
        pipeline, scheduler, _ = _make_pipeline_with_scheduler()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        # Top-view + fun-view timers both armed.
        assert len(scheduler.active_intervals) == 2  # noqa: PLR2004

    def test_advance_fires_top_view_rotation(self) -> None:
        pipeline, scheduler, image_selector = _make_pipeline_with_scheduler()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))

        initial_random_calls = image_selector.get_random_image.call_count

        scheduler.advance(ViewPipeline.TOP_VIEW_EVENT_TIMEOUT_SECS)

        # Both top-view and fun-view rotations fire on the same period.
        assert image_selector.get_random_image.call_count > initial_random_calls

    def test_subsequent_render_replaces_old_timer(self) -> None:
        pipeline, scheduler, _ = _make_pipeline_with_scheduler()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))
        first = scheduler.active_intervals

        pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))

        assert len(scheduler.active_intervals) == 2  # noqa: PLR2004
        assert all(interval.cancelled for interval in first)


def _pick_a_new_image_each_time(image_selector: MagicMock) -> None:
    count = itertools.count()
    image_selector.get_random_image.side_effect = lambda *_args, **_kwargs: ImageInfo(
        filename=Path(f"random-{next(count)}.png"),
        from_title=Titles.ATTIC_ANTICS,
        fit_mode=FIT_MODE_COVER,
    )


def _listen(pipeline: ViewPipeline) -> tuple[list[TopViewSnapshot], list[FunViewSnapshot]]:
    top_views: list[TopViewSnapshot] = []
    fun_views: list[FunViewSnapshot] = []
    pipeline.set_rotation_listeners(on_top_view=top_views.append, on_fun_view=fun_views.append)
    return top_views, fun_views


class TestRotationReachesTheScreen:
    """A timer's new image goes to the listeners: a render is not what shows it."""

    def test_a_tick_sends_each_view_its_new_image(self) -> None:
        pipeline, scheduler, image_selector = _make_pipeline_with_scheduler()
        _pick_a_new_image_each_time(image_selector)
        top_views, fun_views = _listen(pipeline)
        rendered = pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))

        scheduler.advance(ViewPipeline.TOP_VIEW_EVENT_TIMEOUT_SECS)

        assert len(top_views) == 1
        assert top_views[0].image_info != rendered.top_view.image_info
        assert top_views[0].image_opacity == rendered.top_view.image_opacity
        assert len(fun_views) == 1
        assert fun_views[0].is_visible is True
        assert fun_views[0].image_info != rendered.fun_view.image_info

    def test_a_render_sends_nothing_to_the_listeners(self) -> None:
        pipeline, _, image_selector = _make_pipeline_with_scheduler()
        _pick_a_new_image_each_time(image_selector)
        top_views, fun_views = _listen(pipeline)

        pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))

        assert (top_views, fun_views) == ([], [])

    def test_a_state_with_no_fun_view_sends_no_fun_image(self) -> None:
        pipeline, scheduler, image_selector = _make_pipeline_with_scheduler()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))
        _pick_a_new_image_each_time(image_selector)
        _, fun_views = _listen(pipeline)
        # The fun timer armed on the stories node keeps running on the statistics one.
        pipeline.render(ViewRequest(view_state=ViewStates.ON_APPENDIX_STATISTICS_NODE))

        scheduler.advance(ViewPipeline.BOTTOM_VIEW_EVENT_TIMEOUT_SECS)

        assert fun_views == []

    def test_the_same_image_picked_again_is_not_sent(self) -> None:
        pipeline, scheduler, _ = _make_pipeline_with_scheduler()  # always the same image
        top_views, fun_views = _listen(pipeline)
        pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))

        scheduler.advance(ViewPipeline.TOP_VIEW_EVENT_TIMEOUT_SECS)

        assert (top_views, fun_views) == ([], [])
