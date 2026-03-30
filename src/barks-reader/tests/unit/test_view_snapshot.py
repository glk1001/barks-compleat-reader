from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_CONTAIN, FIT_MODE_COVER, ImageInfo
from barks_reader.core.view_snapshot import (
    FunViewSnapshot,
    ScreenVisibility,
    SearchViewSnapshot,
    TitleViewSnapshot,
    TopViewSnapshot,
    ViewSnapshot,
)
from barks_reader.ui.view_states import ViewStates


class TestTopViewSnapshot:
    def test_construction(self) -> None:
        info = ImageInfo(filename=Path("top.png"), from_title=Titles.ATTIC_ANTICS)
        snap = TopViewSnapshot(image_info=info, image_opacity=0.8, image_color=(1, 1, 1, 1))
        assert snap.image_info is info
        assert snap.image_opacity == 0.8  # noqa: PLR2004
        assert snap.image_color == (1, 1, 1, 1)

    def test_frozen(self) -> None:
        snap = TopViewSnapshot(image_info=ImageInfo(), image_opacity=0.5, image_color=(1, 1, 1, 1))
        with pytest.raises(FrozenInstanceError):
            snap.image_opacity = 0.9  # type: ignore[misc]  # ty: ignore[invalid-assignment]

    def test_equality(self) -> None:
        info = ImageInfo(filename=Path("a.png"))
        a = TopViewSnapshot(image_info=info, image_opacity=0.5, image_color=(1, 0, 0, 1))
        b = TopViewSnapshot(image_info=info, image_opacity=0.5, image_color=(1, 0, 0, 1))
        assert a == b


class TestFunViewSnapshot:
    def test_defaults(self) -> None:
        snap = FunViewSnapshot(is_visible=False)
        assert snap.image_info is None
        assert snap.image_color == (0.0, 0.0, 0.0, 0.0)

    def test_with_image(self) -> None:
        info = ImageInfo(filename=Path("fun.png"), from_title=Titles.GIFT_LION)
        snap = FunViewSnapshot(is_visible=True, image_info=info, image_color=(0, 1, 0, 1))
        assert snap.is_visible is True
        assert snap.image_info is info


class TestTitleViewSnapshot:
    def test_defaults(self) -> None:
        snap = TitleViewSnapshot(is_visible=False)
        assert snap.image_info is None
        assert snap.image_color == (0.0, 0.0, 0.0, 0.0)

    def test_with_image(self) -> None:
        info = ImageInfo(filename=Path("title.png"), fit_mode=FIT_MODE_COVER)
        snap = TitleViewSnapshot(is_visible=True, image_info=info, image_color=(0, 0, 1, 1))
        assert snap.is_visible is True


class TestSearchViewSnapshot:
    def test_defaults(self) -> None:
        snap = SearchViewSnapshot(is_visible=False)
        assert snap.mode == ""
        assert snap.image_info is None

    def test_with_mode(self) -> None:
        info = ImageInfo(filename=Path("search.png"))
        snap = SearchViewSnapshot(is_visible=True, mode="Title", image_info=info)
        assert snap.mode == "Title"


class TestScreenVisibility:
    def test_all_defaults_false(self) -> None:
        vis = ScreenVisibility()
        assert vis.main_index is False
        assert vis.speech_index is False
        assert vis.names_index is False
        assert vis.locations_index is False
        assert vis.statistics is False

    def test_selective(self) -> None:
        vis = ScreenVisibility(main_index=True, statistics=True)
        assert vis.main_index is True
        assert vis.speech_index is False
        assert vis.statistics is True


class TestViewSnapshot:
    def test_full_construction(self) -> None:
        top = TopViewSnapshot(
            image_info=ImageInfo(filename=Path("top.png")),
            image_opacity=1.0,
            image_color=(1, 1, 1, 1),
        )
        fun = FunViewSnapshot(is_visible=False)
        title = TitleViewSnapshot(is_visible=True, image_info=ImageInfo(fit_mode=FIT_MODE_CONTAIN))
        vis = ScreenVisibility(main_index=True)
        search = SearchViewSnapshot(is_visible=False)

        snap = ViewSnapshot(
            view_state=ViewStates.ON_TITLE_NODE,
            top_view=top,
            fun_view=fun,
            title_view=title,
            screen_visibility=vis,
            search_view=search,
        )

        assert snap.view_state == ViewStates.ON_TITLE_NODE
        assert snap.top_view is top
        assert snap.fun_view is fun
        assert snap.title_view is title
        assert snap.screen_visibility is vis
        assert snap.search_view is search

    def test_equality(self) -> None:
        kwargs = {
            "view_state": ViewStates.INITIAL,
            "top_view": TopViewSnapshot(
                image_info=ImageInfo(), image_opacity=0.0, image_color=(0, 0, 0, 0)
            ),
            "fun_view": FunViewSnapshot(is_visible=False),
            "title_view": TitleViewSnapshot(is_visible=False),
            "screen_visibility": ScreenVisibility(),
            "search_view": SearchViewSnapshot(is_visible=False),
        }
        a = ViewSnapshot(**kwargs)
        b = ViewSnapshot(**kwargs)
        assert a == b
