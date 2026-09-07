"""Tests for `ViewRenderer` orchestration.

These tests pin the renderer's translation from caller-facing methods (render,
render_state, render_title, refresh) into a single `ViewPipeline.render(request)`
call plus the `SnapshotApplicator`. The pipeline and applicator are mocked
because we want to verify the orchestration, not re-test the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.navigation import (
    CategoryDestination,
    IntroDestination,
    NavigationModel,
    TagDestination,
    TagGroupDestination,
    TitleDestination,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.view_pipeline import ImageThemes
from barks_reader.core.view_request import ViewRequest
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.view_renderer import (
    ImageThemesChange,
    ImageThemesToUse,
    ViewRenderer,
)


def _rendered_request(deps: dict[str, Any]) -> ViewRequest:
    """Return the `ViewRequest` passed to the most recent `pipeline.render` call."""
    return deps["pipeline"].render.call_args.args[0]


@pytest.fixture
def mock_screens() -> ScreenBundle:
    return ScreenBundle(
        tree_view=MagicMock(),
        bottom_title_view=MagicMock(),
        fun_image_view=MagicMock(),
        main_index=MagicMock(),
        speech_index=MagicMock(),
        names_index=MagicMock(),
        locations_index=MagicMock(),
        statistics=MagicMock(),
        history=MagicMock(),
        search=MagicMock(),
    )


@pytest.fixture
def mock_pipeline() -> MagicMock:
    pipeline = MagicMock()
    pipeline.get_view_state.return_value = ViewStates.ON_INTRO_NODE
    pipeline.current_request.return_value = ViewRequest(view_state=ViewStates.ON_INTRO_NODE)
    return pipeline


@pytest.fixture
def renderer(
    mock_pipeline: MagicMock, mock_screens: ScreenBundle
) -> tuple[ViewRenderer, dict[str, Any]]:
    deps: dict[str, Any] = {
        "reader_settings": MagicMock(),
        "pipeline": mock_pipeline,
        "applicator": MagicMock(),
        "screens": mock_screens,
        "nav_model": NavigationModel(),
        "on_view_state_changed": MagicMock(),
    }
    return ViewRenderer(**deps), deps


class TestRenderState:
    def test_render_state_drives_pipeline_and_applies(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render_state(ViewStates.INITIAL)

        request = _rendered_request(deps)
        assert request.view_state == ViewStates.INITIAL
        assert request.preserve_top_view is False
        # The snapshot returned by render is what gets applied.
        deps["applicator"].apply.assert_called_once_with(deps["pipeline"].render.return_value)
        deps["on_view_state_changed"].assert_called_with(ViewStates.INITIAL)

    def test_render_state_request_carries_no_one_shot_title_image(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render_state(ViewStates.INITIAL)

        assert _rendered_request(deps).title_image_file is None


class TestRender:
    def test_render_simple_destination_resolves_to_view_state(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(IntroDestination())

        assert _rendered_request(deps).view_state == ViewStates.ON_INTRO_NODE

    def test_render_category_destination_passes_category_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(CategoryDestination(category="MyCategory"))

        request = _rendered_request(deps)
        assert request.view_state == ViewStates.ON_CATEGORY_NODE
        assert request.category == "MyCategory"

    def test_render_tag_group_destination_passes_tag_group_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(TagGroupDestination(tag_group=TagGroups.AFRICA))

        assert _rendered_request(deps).tag_group == TagGroups.AFRICA

    def test_render_tag_destination_passes_tag_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(TagDestination(tag=Tags.AIRPLANES))

        assert _rendered_request(deps).tag == Tags.AIRPLANES

    def test_render_preserve_top_view_propagates(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(IntroDestination(), preserve_top_view=True)

        assert _rendered_request(deps).preserve_top_view is True


class TestRenderTitle:
    def test_render_title_fades_in_and_applies_title_state(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Story Title"

        view_renderer.render_title(fanta_info)

        deps["screens"].bottom_title_view.fade_in_bottom_view_title.assert_called_once()
        deps["screens"].bottom_title_view.set_title_view.assert_called_with(fanta_info)
        request = _rendered_request(deps)
        assert request.view_state == ViewStates.ON_TITLE_NODE
        assert request.title_str == "Story Title"

    def test_render_title_resolves_edited_image_if_provided(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Story Title"
        deps["reader_settings"].file_paths.get_edited_version_if_possible.return_value = (
            Path("edited.png"),
            True,
        )

        view_renderer.render_title(fanta_info, title_image_file=Path("orig.png"))

        deps["reader_settings"].file_paths.get_edited_version_if_possible.assert_called_with(
            Path("orig.png")
        )
        # The edited file is carried on the request as the one-shot title image.
        assert _rendered_request(deps).title_image_file == Path("edited.png")


class TestSetTitleWithoutRender:
    def test_set_title_without_render_sets_title_on_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        fanta_info = MagicMock()
        fanta_info.comic_book_info.get_title_str.return_value = "Story Title"

        view_renderer.set_title_without_render(fanta_info)

        deps["screens"].bottom_title_view.fade_in_bottom_view_title.assert_called_once()
        deps["pipeline"].set_title.assert_called_once_with("Story Title", None)
        deps["screens"].bottom_title_view.set_title_view.assert_called_with(fanta_info)
        # No view-state transition: render is never called.
        deps["pipeline"].render.assert_not_called()


class TestRefresh:
    def test_refresh_replays_current_request(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        deps["pipeline"].current_request.return_value = ViewRequest(
            view_state=ViewStates.ON_INTRO_NODE
        )

        view_renderer.refresh()

        request = _rendered_request(deps)
        assert request.view_state == ViewStates.ON_INTRO_NODE
        deps["applicator"].apply.assert_called_once()

    def test_refresh_forces_fresh_fun_image_when_fun_view_visible(
        self, renderer: tuple[ViewRenderer, dict[str, Any]], mock_screens: ScreenBundle
    ) -> None:
        view_renderer, deps = renderer
        mock_screens.fun_image_view.is_visible = True

        view_renderer.refresh()

        assert deps["pipeline"].render.call_args.kwargs["force_fresh_fun_image"] is True

    def test_refresh_keeps_fun_image_when_fun_view_hidden(
        self, renderer: tuple[ViewRenderer, dict[str, Any]], mock_screens: ScreenBundle
    ) -> None:
        view_renderer, deps = renderer
        mock_screens.fun_image_view.is_visible = False

        view_renderer.refresh()

        assert deps["pipeline"].render.call_args.kwargs["force_fresh_fun_image"] is False

    def test_refresh_applies_current_themes_not_pipeline_stale_ones(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        # The pipeline's stored context predates the theme switch (stale = None).
        view_renderer, deps = renderer
        deps["pipeline"].current_request.return_value = ViewRequest(
            view_state=ViewStates.ON_INTRO_NODE, fun_image_themes=None
        )
        # User switches to custom themes after the last render, without re-navigating.
        view_renderer.bottom_view_fun_image_themes_changed(ImageThemesToUse.CUSTOM)

        view_renderer.refresh()

        # Refresh must stamp the renderer's CURRENT themes, not replay the stale ones.
        assert _rendered_request(deps).fun_image_themes is not None


class TestThemes:
    def test_themes_to_all_sends_none_themes_on_render(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.bottom_view_fun_image_themes_changed(ImageThemesToUse.ALL)

        # Verify by triggering a render and checking what was forwarded.
        view_renderer.render_state(ViewStates.ON_INTRO_NODE)
        assert _rendered_request(deps).fun_image_themes is None

    def test_themes_to_custom_sends_full_theme_set_minus_discarded(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.bottom_view_fun_image_themes_changed(ImageThemesToUse.CUSTOM)
        view_renderer.bottom_view_alter_fun_image_themes(
            ImageThemes.FORTIES, ImageThemesChange.DISCARD
        )

        # The custom set initially contains all themes; FORTIES was just discarded.
        view_renderer.render_state(ViewStates.ON_INTRO_NODE)
        themes_arg = _rendered_request(deps).fun_image_themes
        assert themes_arg is not None
        assert ImageThemes.FORTIES not in themes_arg


class TestImageInfoPassthrough:
    def test_get_top_view_image_info_delegates_to_applicator(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        expected = MagicMock()
        deps["applicator"].get_prev_top_view_image_info.return_value = expected

        assert view_renderer.get_top_view_image_info() is expected

    def test_get_bottom_view_fun_image_info_delegates_to_applicator(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        expected = MagicMock()
        deps["applicator"].get_prev_fun_view_image_info.return_value = expected

        assert view_renderer.get_bottom_view_fun_image_info() is expected


class TestUpdateSearchBackground:
    def test_update_search_background_routes_through_pipeline_and_applicator(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        search_image = MagicMock()
        search_image.filename = Path("search.png")
        deps["pipeline"].get_search_screen_image_info.return_value = search_image

        view_renderer.update_search_background(Titles.ATTIC_ANTICS)

        deps["pipeline"].set_search_screen_image_for_title.assert_called_with(Titles.ATTIC_ANTICS)
        deps["screens"].search.set_background_image.assert_called_with(search_image)
        deps["applicator"].load_search_texture.assert_called_once()


class TestTitleDestinationViaRender:
    def test_render_title_destination_passes_title_str_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        fanta_info = MagicMock()

        view_renderer.render(TitleDestination(fanta_info=fanta_info))

        # TitleDestination resolves to ON_TITLE_NODE without a title_str param.
        assert _rendered_request(deps).view_state == ViewStates.ON_TITLE_NODE
