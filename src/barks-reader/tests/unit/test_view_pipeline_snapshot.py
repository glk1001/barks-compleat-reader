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
from barks_reader.core.ports import PaletteId
from barks_reader.core.reader_file_paths import ALL_TYPES
from barks_reader.core.testing import FakeScheduler, ScriptedColorSource
from barks_reader.core.view_pipeline import ViewPipeline
from barks_reader.core.view_request import ImageThemes, ViewRequest
from barks_reader.core.view_snapshot import (
    FunViewSnapshot,
    ScreenVisibility,
    SearchViewSnapshot,
    TitleViewSnapshot,
    TopViewSnapshot,
    ViewSnapshot,
)


def _selector(pipeline: ViewPipeline) -> MagicMock:
    """Return the pipeline's image_selector as a MagicMock for assertion access."""
    return pipeline.__dict__["_image_selector"]


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
    image_selector.get_random_reading_history_image.return_value = ImageInfo(
        filename=Path("history.png")
    )
    image_selector.get_random_image_for_title.return_value = Path("title.png")
    # Theme expansion iterates this; a MagicMock return value is not iterable.
    reader_settings.file_paths.get_file_type_titles.return_value = []

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


class TestFreshPipelineState:
    """The state a pipeline starts in, before any `render` call.

    Every field is set once in `__init__` and then only ever overwritten by a
    render; a wrong initial value shows up as a one-frame flash of the wrong
    background at startup, which no per-state render test can see.
    """

    def test_initial_snapshot(self) -> None:
        snap = _make_pipeline()._compute_snapshot()  # noqa: SLF001

        assert snap == ViewSnapshot(
            view_state=ViewStates.PRE_INIT,
            top_view=TopViewSnapshot(
                image_info=ImageInfo(),
                image_opacity=0.0,
                image_color=(0, 0, 0, 0),
            ),
            fun_view=FunViewSnapshot(
                is_visible=False,
                image_info=None,
                image_color=(0, 0, 0, 0),
            ),
            title_view=TitleViewSnapshot(
                is_visible=False,
                image_info=ImageInfo(),
                image_color=(0, 0, 0, 0),
            ),
            screen_visibility=ScreenVisibility(),
            search_view=SearchViewSnapshot(is_visible=False, mode="", image_info=None),
        )

    def test_no_navigation_context_is_set(self) -> None:
        pipeline = _make_pipeline()

        assert pipeline._current_year_range == ""  # noqa: SLF001
        assert pipeline._current_cs_year_range == ""  # noqa: SLF001
        assert pipeline._current_us_year_range == ""  # noqa: SLF001
        assert pipeline._current_category == ""  # noqa: SLF001
        assert pipeline._current_bottom_view_title == ""  # noqa: SLF001
        assert pipeline._current_tag is None  # noqa: SLF001
        assert pipeline._current_tag_group is None  # noqa: SLF001

    def test_no_rotation_timers_are_running(self) -> None:
        """Timers are armed by `render`, not by construction."""
        pipeline = _make_pipeline()

        assert pipeline._top_view_change_event is None  # noqa: SLF001
        assert pipeline._bottom_view_change_fun_image_event is None  # noqa: SLF001

    def test_the_fun_title_pool_is_primed_with_no_theme_filter(self) -> None:
        """`__init__` calls `_set_fun_image_themes(None)`, so the pool is ready.

        No theme filter means every title and every image type — so the first fun
        image needs no extra work at startup.
        """
        pipeline = _make_pipeline()

        assert pipeline._fun_image_themes is None  # noqa: SLF001
        cached = pipeline._cached_fun_titles  # noqa: SLF001
        assert cached is not None
        titles, file_types = cached
        assert titles == pipeline._title_lists["All"]  # noqa: SLF001
        assert file_types == ALL_TYPES

    def test_the_search_screen_image_starts_empty(self) -> None:
        """Never visible until a search state renders, so the snapshot cannot see it."""
        pipeline = _make_pipeline()

        assert pipeline.get_search_screen_image_info() == ImageInfo()


# ---------------------------------------------------------------------------
# Screen visibility, opacity, and per-palette colors
# ---------------------------------------------------------------------------


class TestScreenVisibility:
    def test_history_state_shows_the_history_screen(self) -> None:
        """The history flag is the only `ScreenVisibility` field with no other cover."""
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_HISTORY_NODE))

        assert snap.screen_visibility == ScreenVisibility(history=True)
        assert snap.fun_view.is_visible is False

    def test_speech_words_state_shares_the_speech_screen(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INDEX_SPEECH_WORDS_NODE))

        assert snap.screen_visibility == ScreenVisibility(speech_index=True)


class TestViewOpacities:
    """The opacity fields the snapshot only exposes as `is_visible` booleans."""

    def test_pre_init_uses_half_opacity_for_both_views(self) -> None:
        pipeline = _make_pipeline()
        snap = pipeline.render(ViewRequest(view_state=ViewStates.PRE_INIT))

        assert snap.top_view.image_opacity == 0.5  # noqa: PLR2004
        assert pipeline._bottom_view_fun_image_opacity == 0.5  # noqa: PLR2004, SLF001
        assert pipeline._bottom_view_title_opacity == 0.0  # noqa: SLF001

    def test_a_fun_image_state_is_fully_opaque(self) -> None:
        pipeline = _make_pipeline()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        assert pipeline._bottom_view_fun_image_opacity == 1.0  # noqa: SLF001
        assert pipeline._bottom_view_title_opacity == 0.0  # noqa: SLF001

    def test_a_title_state_is_fully_opaque(self) -> None:
        pipeline = _make_pipeline()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_TITLE_NODE, title_str="Some Title"))

        assert pipeline._bottom_view_title_opacity == 1.0  # noqa: SLF001
        assert pipeline._bottom_view_fun_image_opacity == 0.0  # noqa: SLF001


class TestPerPaletteColors:
    """Each view must draw its tint from its own palette, not a shared one."""

    def test_each_view_takes_its_color_from_its_own_palette(self) -> None:
        top = (0.1, 0.1, 0.1, 1.0)
        fun = (0.2, 0.2, 0.2, 1.0)
        title = (0.3, 0.3, 0.3, 1.0)
        pipeline = _make_pipeline()
        pipeline._colors = ScriptedColorSource(  # noqa: SLF001
            palettes={PaletteId.TOP_VIEW: [top], PaletteId.FUN: [fun], PaletteId.TITLE: [title]},
            default=(9.0, 9.0, 9.0, 9.0),
        )

        snap = pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        assert snap.top_view.image_color == top
        assert snap.fun_view.image_color == fun
        assert snap.title_view.image_color == title


# ---------------------------------------------------------------------------
# `render`'s two flags
# ---------------------------------------------------------------------------


class TestRenderFlags:
    def test_initial_state_keeps_its_fun_image_across_renders(self) -> None:
        """Re-entering INITIAL must not re-roll the startup fun image."""
        pipeline = _make_pipeline()
        picks = iter([ImageInfo(filename=Path(f"fun{n}.png")) for n in range(1, 5)])
        _selector(pipeline).get_random_image.side_effect = lambda *_args, **_kw: next(picks)

        first = pipeline.render(ViewRequest(view_state=ViewStates.INITIAL))
        second = pipeline.render(ViewRequest(view_state=ViewStates.INITIAL))

        # A fun image *is* picked the first time...
        assert first.fun_view.image_info == ImageInfo(filename=Path("fun1.png"))
        # ...and kept the second, because `render` does not force a fresh one.
        assert second.fun_view.image_info == ImageInfo(filename=Path("fun1.png"))

    def test_non_initial_states_re_roll_the_fun_image_every_render(self) -> None:
        pipeline = _make_pipeline()
        picks = iter([ImageInfo(filename=Path(f"fun{n}.png")) for n in range(1, 5)])
        _selector(pipeline).get_random_image.side_effect = lambda *_args, **_kw: next(picks)

        first = pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))
        second = pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        assert first.fun_view.image_info == ImageInfo(filename=Path("fun1.png"))
        assert second.fun_view.image_info == ImageInfo(filename=Path("fun2.png"))

    def test_force_fresh_fun_image_clears_the_image_in_a_no_fun_state(self) -> None:
        """The cleared field must end up as `None`, not some other falsy value.

        `ON_TITLE_NODE` never picks a fun image, so whatever `force_fresh` left
        behind is exactly what the snapshot carries.
        """
        pipeline = _make_pipeline()
        pipeline.render(ViewRequest(view_state=ViewStates.ON_INTRO_NODE))

        snap = pipeline.render(
            ViewRequest(view_state=ViewStates.ON_TITLE_NODE, title_str="Some Title"),
            force_fresh_fun_image=True,
        )

        assert snap.fun_view.image_info is None

    def test_preserve_top_view_keeps_the_current_top_image(self) -> None:
        pipeline = _make_pipeline()
        picks = iter([ImageInfo(filename=Path(f"top{n}.png")) for n in range(1, 5)])
        _selector(pipeline).get_random_image.side_effect = lambda *_args, **_kw: next(picks)

        first = pipeline.render(ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE))
        second = pipeline.render(
            ViewRequest(view_state=ViewStates.ON_THE_STORIES_NODE, preserve_top_view=True)
        )

        assert first.top_view.image_info == ImageInfo(filename=Path("top1.png"))
        assert second.top_view.image_info == ImageInfo(filename=Path("top1.png"))

    def test_update_views_picks_a_new_top_image_by_default(self) -> None:
        """The `preserve_top_view` default is off — a plain refresh re-rolls the top."""
        pipeline = _make_pipeline()
        pipeline._view_state = ViewStates.ON_THE_STORIES_NODE  # noqa: SLF001
        pipeline._top_view_image_info = ImageInfo()  # noqa: SLF001

        pipeline._update_views()  # noqa: SLF001

        assert pipeline._top_view_image_info.filename == Path("random.png")  # noqa: SLF001

    def test_render_keeps_the_provided_title_image_file(self) -> None:
        pipeline = _make_pipeline()
        provided = Path("provided.png")

        snap = pipeline.render(
            ViewRequest(
                view_state=ViewStates.ON_TITLE_NODE,
                title_str="Lost in the Andes!",
                title_image_file=provided,
            )
        )

        assert snap.title_view.image_info is not None
        assert snap.title_view.image_info.filename == provided
        _selector(pipeline).get_random_image_for_title.assert_not_called()

    def test_render_stores_the_requested_fun_image_themes(self) -> None:
        pipeline = _make_pipeline()

        pipeline.render(
            ViewRequest(
                view_state=ViewStates.ON_INTRO_NODE,
                fun_image_themes={ImageThemes.SPLASHES},
            )
        )

        assert pipeline._fun_image_themes == {ImageThemes.SPLASHES}  # noqa: SLF001
        assert pipeline.current_request().fun_image_themes == {ImageThemes.SPLASHES}
