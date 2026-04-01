from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.snapshot_applicator
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
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
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.snapshot_applicator import SnapshotApplicator
from barks_reader.ui.view_states import ViewStates


def _make_screen_mocks() -> dict[str, MagicMock]:
    return {
        "tree_view": MagicMock(),
        "bottom_title_view": MagicMock(),
        "fun_image_view": MagicMock(),
        "main_index": MagicMock(),
        "speech_index": MagicMock(),
        "names_index": MagicMock(),
        "locations_index": MagicMock(),
        "statistics": MagicMock(),
        "search": MagicMock(),
    }


@pytest.fixture
def screen_mocks() -> dict[str, MagicMock]:
    return _make_screen_mocks()


@pytest.fixture
def screens(screen_mocks: dict[str, MagicMock]) -> ScreenBundle:
    return ScreenBundle(**screen_mocks)


@pytest.fixture
def applicator(screens: ScreenBundle) -> Generator[SnapshotApplicator]:
    with patch.object(barks_reader.ui.snapshot_applicator, "PanelTextureLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value

        def side_effect(_filename, callback):  # noqa: ANN001, ANN202
            callback(MagicMock(), None)

        mock_loader.load_texture.side_effect = side_effect

        yield SnapshotApplicator(screens=screens, panels_are_encrypted=False)


def _make_snapshot(
    view_state: ViewStates = ViewStates.INITIAL,
    top_filename: str = "top.png",
    fun_visible: bool = False,
    title_visible: bool = False,
    search_visible: bool = False,
    search_mode: str = "",
) -> ViewSnapshot:
    top_info = ImageInfo(filename=Path(top_filename), from_title=Titles.ATTIC_ANTICS)
    return ViewSnapshot(
        view_state=view_state,
        top_view=TopViewSnapshot(
            image_info=top_info,
            image_opacity=0.8,
            image_color=(1, 1, 1, 1),
        ),
        fun_view=FunViewSnapshot(
            is_visible=fun_visible,
            image_info=ImageInfo(
                filename=Path("fun.png"), from_title=Titles.GIFT_LION, fit_mode=FIT_MODE_COVER
            )
            if fun_visible
            else None,
            image_color=(0, 1, 0, 1) if fun_visible else (0, 0, 0, 0),
        ),
        title_view=TitleViewSnapshot(
            is_visible=title_visible,
            image_info=ImageInfo(filename=Path("title.png"), fit_mode=FIT_MODE_CONTAIN)
            if title_visible
            else None,
            image_color=(0, 0, 1, 1) if title_visible else (0, 0, 0, 0),
        ),
        screen_visibility=ScreenVisibility(),
        search_view=SearchViewSnapshot(
            is_visible=search_visible,
            mode=search_mode,
            image_info=ImageInfo(filename=Path("search.png")) if search_visible else None,
        ),
    )


class TestSnapshotApplicator:
    def test_apply_top_view(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot()
        applicator.apply(snap)

        tree = screen_mocks["tree_view"]
        assert tree.top_view_image_opacity == 0.8  # noqa: PLR2004
        assert tree.top_view_image_fit_mode == FIT_MODE_COVER
        assert tree.top_view_image_color == (1, 1, 1, 1)
        assert tree.top_view_image_texture is not None
        tree.set_title.assert_called_with(Titles.ATTIC_ANTICS)

    def test_apply_fun_view_visible(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(fun_visible=True)
        applicator.apply(snap)

        fun = screen_mocks["fun_image_view"]
        assert fun.is_visible is True
        assert fun.image_fit_mode == FIT_MODE_COVER
        assert fun.image_color == (0, 1, 0, 1)
        assert fun.image_texture is not None
        fun.set_last_loaded_image_info.assert_called_once()

    def test_apply_fun_view_not_visible(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(fun_visible=False)
        applicator.apply(snap)

        fun = screen_mocks["fun_image_view"]
        assert fun.is_visible is False

    def test_apply_fun_view_skips_same_title(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(fun_visible=True)
        applicator.apply(snap)

        # Reset the mock call count
        screen_mocks["fun_image_view"].set_last_loaded_image_info.reset_mock()

        # Apply same snapshot again — should skip because from_title hasn't changed
        applicator.apply(snap)
        screen_mocks["fun_image_view"].set_last_loaded_image_info.assert_not_called()

    def test_apply_title_view_visible(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(title_visible=True)
        applicator.apply(snap)

        bottom = screen_mocks["bottom_title_view"]
        assert bottom.is_visible is True
        assert bottom.title_image_fit_mode == FIT_MODE_CONTAIN
        assert bottom.title_image_color == (0, 0, 1, 1)
        assert bottom.title_image_texture is not None

    def test_apply_title_view_not_visible(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(title_visible=False)
        applicator.apply(snap)

        bottom = screen_mocks["bottom_title_view"]
        assert bottom.is_visible is False
        assert bottom.title_image_texture is None

    def test_apply_screen_visibility(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = ViewSnapshot(
            view_state=ViewStates.ON_INDEX_MAIN_NODE,
            top_view=TopViewSnapshot(
                image_info=ImageInfo(filename=Path("t.png"), from_title=Titles.ATTIC_ANTICS),
                image_opacity=1.0,
                image_color=(1, 1, 1, 1),
            ),
            fun_view=FunViewSnapshot(is_visible=False),
            title_view=TitleViewSnapshot(is_visible=False),
            screen_visibility=ScreenVisibility(main_index=True, statistics=True),
            search_view=SearchViewSnapshot(is_visible=False),
        )
        applicator.apply(snap)

        assert screen_mocks["main_index"].is_visible is True
        assert screen_mocks["speech_index"].is_visible is False
        assert screen_mocks["names_index"].is_visible is False
        assert screen_mocks["locations_index"].is_visible is False
        assert screen_mocks["statistics"].is_visible is True

    def test_apply_search_view(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(search_visible=True, search_mode="Title")
        applicator.apply(snap)

        search = screen_mocks["search"]
        assert search.is_visible is True
        search.set_mode.assert_called_with("Title")
        search.set_background_image.assert_called_once()
        assert search.image_texture is not None

    def test_apply_search_view_not_visible(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(search_visible=False)
        applicator.apply(snap)

        search = screen_mocks["search"]
        assert search.is_visible is False
        search.set_mode.assert_not_called()

    def test_load_new_fun_view_image(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        info = ImageInfo(filename=Path("new_fun.png"), from_title=Titles.GIFT_LION)
        applicator.load_new_fun_view_image(info)

        fun = screen_mocks["fun_image_view"]
        assert fun.image_texture is not None
        assert applicator.get_prev_fun_view_image_info() == info

    def test_goto_title_button_active(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        screen_mocks["fun_image_view"].fun_view_from_title = Titles.GIFT_LION
        snap = _make_snapshot(fun_visible=True, title_visible=False)
        applicator.apply(snap)

        assert screen_mocks["fun_image_view"].goto_title_button_active is not None
