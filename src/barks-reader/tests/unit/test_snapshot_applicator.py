from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import barks_reader.ui.snapshot_applicator
import pytest
from barks_reader.core import log_markers
from barks_reader.core.log_markers import pattern
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from barks_reader.ui.screen_bundle import ScreenBundle
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.image_selector import FIT_MODE_CONTAIN, FIT_MODE_COVER, ImageInfo
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.view_snapshot import (
    FunViewSnapshot,
    ScreenVisibility,
    SearchViewSnapshot,
    TitleViewSnapshot,
    TopViewSnapshot,
    ViewSnapshot,
)
from barks_reader.ui.snapshot_applicator import SnapshotApplicator


@pytest.fixture
def applicator(screens: ScreenBundle) -> Generator[SnapshotApplicator]:
    with patch.object(barks_reader.ui.snapshot_applicator, "PanelTextureLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value

        def side_effect(_filename, callback):  # noqa: ANN001, ANN202
            callback(MagicMock(), None)

        mock_loader.load_texture.side_effect = side_effect

        yield SnapshotApplicator(screens=screens)


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


class TestImageLoadTiming:
    def test_a_loaded_image_logs_its_name_and_how_long_it_took(
        self, loguru_sink: list[str]
    ) -> None:
        """The GUI suite holds this duration to a budget (IMAGE_LOADED)."""
        loader = MagicMock()
        loader.load_texture.side_effect = lambda _filename, callback: callback(MagicMock(), None)
        image_info = MagicMock(filename=Path("Barks Panels Pngs/Insets/Too Fit to Fit.png"))
        applied: list[object] = []

        SnapshotApplicator._load_texture(loader, image_info, applied.append)  # noqa: SLF001

        assert len(applied) == 1
        wanted = pattern(log_markers.IMAGE_LOADED, filename="Too Fit to Fit.png")
        assert any(re.search(wanted, m) for m in loguru_sink)


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

    def test_apply_fun_view_skips_the_image_already_shown(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot(fun_visible=True)
        applicator.apply(snap)

        # Reset the mock call count
        screen_mocks["fun_image_view"].set_last_loaded_image_info.reset_mock()

        # Apply same snapshot again: skipped, as its image is the one shown
        applicator.apply(snap)
        screen_mocks["fun_image_view"].set_last_loaded_image_info.assert_not_called()

    def test_another_image_of_the_same_title_is_applied(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        """A rotation picked another panel of the shown story: it was dropped as a repeat."""
        snap = _make_snapshot(fun_visible=True)
        applicator.apply(snap)
        assert snap.fun_view.image_info is not None
        other = replace(snap.fun_view.image_info, filename=Path("another_fun.png"))

        applicator.apply_fun_view_rotation(replace(snap.fun_view, image_info=other))

        screen_mocks["fun_image_view"].set_last_loaded_image_info.assert_called_with(other)
        assert applicator.get_prev_fun_view_image_info() == other

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


class TestRotation:
    """A rotation timer's image goes to its own view; the rest of the screen is left alone."""

    def test_a_rotated_top_view_is_applied_alone(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        top = _make_snapshot(top_filename="rotated.png").top_view

        applicator.apply_top_view_rotation(top)

        assert screen_mocks["tree_view"].top_view_image_texture is not None
        assert applicator.get_prev_top_view_image_info() == top.image_info
        assert screen_mocks["search"].method_calls == []
        assert screen_mocks["bottom_title_view"].method_calls == []
        assert screen_mocks["fun_image_view"].method_calls == []

    def test_a_rotated_fun_view_is_applied_with_its_goto_title_button(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        fun_view = screen_mocks["fun_image_view"]
        fun_view.fun_view_from_title = Titles.GIFT_LION
        screen_mocks["bottom_title_view"].is_visible = False
        fun = _make_snapshot(fun_visible=True).fun_view

        applicator.apply_fun_view_rotation(fun)

        assert fun_view.image_texture is not None
        fun_view.set_last_loaded_image_info.assert_called_once_with(fun.image_info)
        assert fun_view.goto_title_button_active is True
        assert screen_mocks["search"].method_calls == []
        assert screen_mocks["tree_view"].method_calls == []


class TestWhatIsLeftAlone:
    """A snapshot with nothing to show for a view leaves that view's widgets as they are."""

    def test_a_top_view_with_no_image_loads_nothing(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot()
        snap = replace(snap, top_view=replace(snap.top_view, image_info=ImageInfo()))
        tree = screen_mocks["tree_view"]
        texture_before = tree.top_view_image_texture

        applicator.apply(snap)

        assert tree.top_view_image_texture is texture_before
        tree.set_title.assert_not_called()
        assert applicator.get_prev_top_view_image_info() == ImageInfo()

    def test_a_top_image_from_no_title_sets_no_title(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = _make_snapshot()
        no_title = ImageInfo(filename=Path("emblem.png"))
        snap = replace(snap, top_view=replace(snap.top_view, image_info=no_title))

        applicator.apply(snap)

        assert screen_mocks["tree_view"].top_view_image_texture is not None
        screen_mocks["tree_view"].set_title.assert_not_called()

    def test_a_visible_fun_view_with_no_image_is_left_as_it_is(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = replace(_make_snapshot(), fun_view=FunViewSnapshot(is_visible=True))
        fun = screen_mocks["fun_image_view"]
        texture_before = fun.image_texture

        applicator.apply(snap)

        assert fun.is_visible is True
        assert fun.image_texture is texture_before
        fun.set_last_loaded_image_info.assert_not_called()

    def test_a_fun_image_with_no_file_clears_the_fun_view(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        info = ImageInfo(from_title=Titles.GIFT_LION)
        snap = replace(_make_snapshot(), fun_view=FunViewSnapshot(is_visible=True, image_info=info))

        applicator.apply(snap)

        fun = screen_mocks["fun_image_view"]
        assert fun.image_texture is None
        fun.set_last_loaded_image_info.assert_not_called()
        assert applicator.get_prev_fun_view_image_info() is info

    def test_a_search_with_no_mode_keeps_the_mode_it_has(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        applicator.apply(_make_snapshot(search_visible=True, search_mode=""))

        search = screen_mocks["search"]
        search.set_mode.assert_not_called()
        search.set_background_image.assert_called_once()

    def test_a_search_with_no_background_image_loads_none(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        snap = replace(_make_snapshot(), search_view=SearchViewSnapshot(is_visible=True))

        applicator.apply(snap)

        search = screen_mocks["search"]
        assert search.is_visible is True
        search.set_background_image.assert_not_called()


class _HeldLoader:
    """A texture loader whose load finishes only when told, and which cancel drops."""

    def __init__(self) -> None:
        self._pending: list[Callable[[object, Exception | None], None]] = []

    def load_texture(
        self, _filename: Path, callback: Callable[[object, Exception | None], None]
    ) -> None:
        self._pending = [callback]  # one load in flight, as PanelImageLoader keeps

    def cancel(self) -> None:
        self._pending = []

    def finish(self) -> None:
        for callback in self._pending:
            callback(MagicMock(), None)
        self._pending = []


class TestAClearedViewStaysCleared:
    """A view cleared while its image is still loading is not given that image after all."""

    @pytest.fixture
    def held_applicator(self, screens: ScreenBundle) -> Generator[SnapshotApplicator]:
        with patch.object(
            barks_reader.ui.snapshot_applicator, "PanelTextureLoader", side_effect=_HeldLoader
        ):
            yield SnapshotApplicator(screens=screens)

    def test_the_title_view(
        self, held_applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        held_applicator.apply(_make_snapshot(title_visible=True))
        held_applicator.apply(_make_snapshot(title_visible=False))
        held_applicator._bottom_title_view_texture_loader.finish()  # noqa: SLF001  # ty:ignore[missing-attribute]

        assert screen_mocks["bottom_title_view"].title_image_texture is None

    def test_the_fun_view(
        self, held_applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        held_applicator.apply(_make_snapshot(fun_visible=True))
        no_file = ImageInfo(from_title=Titles.ATTIC_ANTICS)  # another image, so not skipped
        held_applicator.apply(
            replace(_make_snapshot(), fun_view=FunViewSnapshot(is_visible=True, image_info=no_file))
        )
        held_applicator._fun_view_texture_loader.finish()  # noqa: SLF001  # ty:ignore[missing-attribute]

        assert screen_mocks["fun_image_view"].image_texture is None


def test_a_texture_that_failed_to_load_is_logged_as_an_error_and_nothing_is_applied() -> None:
    """Raised on the Kivy clock, one bad panel file would end the app."""
    loader = MagicMock()
    loader.load_texture.side_effect = lambda _filename, callback: callback(None, OSError("bad png"))
    applied: list[object] = []
    lines: list[str] = []
    handle = logger.add(lambda m: lines.append(str(m).rstrip("\n")), format="{level}|{message}")
    try:
        SnapshotApplicator._load_texture(  # noqa: SLF001
            loader, ImageInfo(filename=Path("broken.png")), applied.append
        )
    finally:
        logger.remove(handle)

    assert applied == []
    failed = log_markers.IMAGE_LOAD_FAILED.format(filename="broken.png", error="bad png")
    assert f"ERROR|{failed}" in lines
    assert not any("Time taken to load image" in line for line in lines)


class TestLoadFunViewTexture:
    def test_the_texture_goes_to_the_caller_and_the_fun_view_is_left_alone(
        self, applicator: SnapshotApplicator, screen_mocks: dict[str, MagicMock]
    ) -> None:
        before = applicator.get_prev_fun_view_image_info()
        info = ImageInfo(filename=Path("lower_tier.png"), from_title=Titles.GIFT_LION)
        apply_texture = MagicMock()
        applicator.load_fun_view_texture(info, apply_texture)
        apply_texture.assert_called_once()
        assert applicator.get_prev_fun_view_image_info() == before
        assert screen_mocks["fun_image_view"].set_last_loaded_image_info.call_count == 0
