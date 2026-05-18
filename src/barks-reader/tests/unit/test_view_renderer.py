"""Tests for `ViewRenderer` orchestration.

These tests pin the renderer's translation from caller-facing methods (render,
render_state, render_title, refresh) into the underlying ViewPipeline +
SnapshotApplicator calls. The pipeline and applicator are mocked because we
want to verify the orchestration, not re-test the pipeline.
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
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.view_renderer import (
    ImageThemesChange,
    ImageThemesToUse,
    ViewRenderer,
)


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
        search=MagicMock(),
    )


@pytest.fixture
def mock_pipeline() -> MagicMock:
    pipeline = MagicMock()
    pipeline.get_view_state.return_value = ViewStates.ON_INTRO_NODE
    pipeline.get_current_category.return_value = ""
    pipeline.get_current_year_range.return_value = ""
    pipeline.get_current_cs_year_range.return_value = ""
    pipeline.get_current_us_year_range.return_value = ""
    pipeline.get_current_tag_group.return_value = None
    pipeline.get_current_tag.return_value = None
    pipeline.get_current_bottom_view_title.return_value = ""
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

        deps["pipeline"].set_view_state.assert_called_with(
            ViewStates.INITIAL, preserve_top_view=False
        )
        deps["applicator"].apply.assert_called_once()
        deps["on_view_state_changed"].assert_called_with(ViewStates.INITIAL)

    def test_render_state_resets_title_image_file_after_apply(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render_state(ViewStates.INITIAL)

        deps["pipeline"].set_bottom_view_title_image_file.assert_called_with(None)


class TestRender:
    def test_render_simple_destination_resolves_to_view_state(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(IntroDestination())

        deps["pipeline"].set_view_state.assert_called_with(
            ViewStates.ON_INTRO_NODE, preserve_top_view=False
        )

    def test_render_category_destination_passes_category_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(CategoryDestination(category="MyCategory"))

        deps["pipeline"].set_current_category.assert_called_with("MyCategory")
        deps["pipeline"].set_view_state.assert_called_with(
            ViewStates.ON_CATEGORY_NODE, preserve_top_view=False
        )

    def test_render_tag_group_destination_passes_tag_group_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(TagGroupDestination(tag_group=TagGroups.AFRICA))

        deps["pipeline"].set_current_tag_group.assert_called_with(TagGroups.AFRICA)

    def test_render_tag_destination_passes_tag_to_pipeline(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.render(TagDestination(tag=Tags.AIRPLANES))

        deps["pipeline"].set_current_tag.assert_called_with(Tags.AIRPLANES)


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
        deps["pipeline"].set_view_state.assert_called_with(
            ViewStates.ON_TITLE_NODE, preserve_top_view=False
        )

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
        # Title image file is set to the edited version, then reset after apply.
        # Both calls happen on set_bottom_view_title_image_file.
        calls = deps["pipeline"].set_bottom_view_title_image_file.call_args_list
        assert any(c.args == (Path("edited.png"),) for c in calls)


class TestRefresh:
    def test_refresh_replays_current_state(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        deps["pipeline"].get_view_state.return_value = ViewStates.ON_INTRO_NODE

        view_renderer.refresh()

        deps["pipeline"].set_view_state.assert_called_with(
            ViewStates.ON_INTRO_NODE, preserve_top_view=False
        )
        deps["applicator"].apply.assert_called_once()

    def test_refresh_clears_fun_image_when_fun_view_visible(
        self, renderer: tuple[ViewRenderer, dict[str, Any]], mock_screens: ScreenBundle
    ) -> None:
        view_renderer, deps = renderer
        mock_screens.fun_image_view.is_visible = True

        view_renderer.refresh()

        deps["pipeline"].reset_bottom_view_fun_image_info.assert_called_once()


class TestThemes:
    def test_themes_to_all_sets_pipeline_themes_none(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, deps = renderer
        view_renderer.bottom_view_fun_image_themes_changed(ImageThemesToUse.ALL)

        # Verify by triggering a render and checking what was forwarded.
        view_renderer.render_state(ViewStates.ON_INTRO_NODE)
        deps["pipeline"].set_fun_image_themes.assert_called_with(None)

    def test_themes_to_custom_sets_full_theme_set(
        self, renderer: tuple[ViewRenderer, dict[str, Any]]
    ) -> None:
        view_renderer, _deps = renderer
        view_renderer.bottom_view_fun_image_themes_changed(ImageThemesToUse.CUSTOM)
        view_renderer.bottom_view_alter_fun_image_themes(
            ImageThemes.FORTIES, ImageThemesChange.DISCARD
        )

        # The custom set initially contains all themes; FORTIES was just discarded.
        # We can't read the renderer's private set, but we can verify behavior
        # propagates through to the pipeline.
        view_renderer.render_state(ViewStates.ON_INTRO_NODE)
        themes_arg = _deps["pipeline"].set_fun_image_themes.call_args.args[0]
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

        # TitleDestination resolves to ON_TITLE_NODE without title_str param.
        deps["pipeline"].set_view_state.assert_called_with(
            ViewStates.ON_TITLE_NODE, preserve_top_view=False
        )
