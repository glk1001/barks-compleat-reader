# ruff: noqa: SLF001

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import barks_reader.ui.fun_image_view_screen
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core import log_markers
from barks_reader.core.image_selector import FIT_MODE_CONTAIN, FIT_MODE_COVER, ImageInfo
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_SPACE,
    KEY_UP,
)
from barks_reader.core.log_markers import pattern
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.ui.fun_image_view_screen import FunImageViewScreen, _FunFocus
from kivy.uix.boxlayout import BoxLayout

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.widget import Widget


@pytest.fixture
def _no_focus_draw() -> Generator[None]:
    """Neutralize the focus-ring helpers so nav tests assert state, not canvas draws."""
    mod = barks_reader.ui.fun_image_view_screen
    with (
        patch.object(mod, "draw_focus_highlight"),
        patch.object(mod, "clear_focus_highlight"),
        patch.object(mod, "update_focus_in_list"),
        patch.object(mod, "clear_focus_in_list"),
    ):
        yield


@pytest.fixture
def screen_setup() -> Generator[tuple[FunImageViewScreen, Any, MagicMock], Any]:
    """Set up the FunImageViewScreen with mocked dependencies."""
    mock_settings = MagicMock()
    mock_settings.show_fun_view_title_info = True

    # Mock dependencies used in __init__
    with (
        patch.object(barks_reader.ui.fun_image_view_screen, "ReaderNavigation") as mock_nav_cls,
        patch.object(BoxLayout, "__init__", autospec=True) as mock_layout_init,
    ):
        mock_nav_instance = mock_nav_cls.return_value

        # Mock ids for view_options_clear_all_button_pressed
        mock_custom_options_box = MagicMock()
        mock_custom_options_box.children = []

        def side_effect(instance: Widget, **_kwargs) -> None:  # noqa: ANN003
            mock_goto_button = MagicMock()
            mock_goto_button.collide_point.return_value = False
            mock_goto_title_overlay = MagicMock()
            mock_goto_title_overlay.goto_button = mock_goto_button
            mock_lower_goto_button = MagicMock()
            mock_lower_goto_button.collide_point.return_value = False
            mock_lower_goto_title_overlay = MagicMock()
            mock_lower_goto_title_overlay.goto_button = mock_lower_goto_button
            mock_all_checkbox = MagicMock()
            mock_all_checkbox.active = True
            mock_custom_checkbox = MagicMock()
            mock_custom_checkbox.active = False
            instance.ids = {
                "custom_options_box": mock_custom_options_box,
                "goto_title_overlay": mock_goto_title_overlay,
                "lower_goto_title_overlay": mock_lower_goto_title_overlay,
                "fun_options_button": MagicMock(),
                "clear_all_button": MagicMock(),
                "checkbox_all_image_types": mock_all_checkbox,
                "checkbox_custom_image_types": mock_custom_checkbox,
            }
            # Initialize properties that might be set in kv
            instance.x = 0
            instance.y = 0
            instance.width = 100
            instance.height = 100

        mock_layout_init.side_effect = side_effect

        screen = FunImageViewScreen(mock_settings)

        yield screen, mock_nav_instance, mock_settings


class TestFunImageViewScreen:
    def test_initialization(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        """Test that the screen initializes with correct default values."""
        screen, _, _ = screen_setup
        assert screen.goto_title_button_active is True
        assert screen.is_visible is False
        assert screen.image_fit_mode == FIT_MODE_CONTAIN
        assert screen.fun_options_enabled is False
        assert screen._history.index == -1
        assert len(screen._history.images) == 0

    def test_set_load_image_func(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        mock_func = MagicMock()
        screen.set_load_image_func(mock_func)
        assert screen._load_image is not None
        assert screen._load_image == mock_func

    def test_set_last_loaded_image_info(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        image_info = ImageInfo(
            filename=Path("test.png"),
            from_title=Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            fit_mode=FIT_MODE_CONTAIN,
        )

        screen.set_last_loaded_image_info(image_info)

        assert len(screen._history.images) == 1
        assert screen._history.images[0] == image_info
        assert screen._history.index == 0
        assert screen.current_title_str != ""

    def test_navigation_previous_next(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        mock_load_func = MagicMock()
        screen.set_load_image_func(mock_load_func)

        # Add two images to history
        info1 = ImageInfo(Path("1.png"), Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, FIT_MODE_CONTAIN)
        info2 = ImageInfo(Path("2.png"), Titles.LAND_OF_THE_TOTEM_POLES, FIT_MODE_CONTAIN)

        screen.set_last_loaded_image_info(info1)
        screen.set_last_loaded_image_info(info2)

        # Current index should be 1 (pointing to info2)
        assert screen._history.index == 1

        # Go back
        screen._goto_previous_image()
        assert screen._history.index == 0
        mock_load_func.assert_called_with(info1)

        # Go back again (should stay at 0)
        screen._goto_previous_image()
        assert screen._history.index == 0

        # Go forward
        screen._goto_next_image()
        assert screen._history.index == 1
        mock_load_func.assert_called_with(info2)

        # Go forward again (should stay at 1)
        screen._goto_next_image()
        assert screen._history.index == 1

    def test_on_touch_down_navigation(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, mock_nav, _ = screen_setup

        # Enable visibility so touch is processed
        screen.is_visible = True
        screen.fun_options_enabled = False

        # Mock touch
        touch = MagicMock()
        touch.x = 100
        touch.y = 100

        # Mock navigation checks
        mock_nav.is_in_left_margin.return_value = True
        mock_nav.is_in_right_margin.return_value = False

        # Mock internal methods to verify calls
        with (
            patch.object(screen, "_goto_previous_image") as mock_prev,
            patch.object(screen, "_goto_next_image") as mock_next,
        ):
            # Test Left Click
            handled = screen.on_touch_down(touch)
            assert handled is True
            mock_prev.assert_called_once()
            mock_next.assert_not_called()

            # Reset
            mock_prev.reset_mock()
            mock_nav.is_in_left_margin.return_value = False
            mock_nav.is_in_right_margin.return_value = True

            # Test Right Click
            handled = screen.on_touch_down(touch)
            assert handled is True
            mock_prev.assert_not_called()
            mock_next.assert_called_once()

    def test_a_press_off_the_view_is_not_a_margin_press(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        """On the spread the tree stands beside the view: its taps are none of the view's."""
        screen, mock_nav, _ = screen_setup
        screen.is_visible = True
        screen.fun_options_enabled = False
        mock_nav.is_in_left_margin.return_value = True  # a negative x passes the check

        touch = MagicMock()
        touch.x, touch.y = -50, 50  # left of the 100 x 100 view at (0, 0)
        with patch.object(screen, "_goto_previous_image") as mock_prev:
            assert screen.on_touch_down(touch) is False
        mock_prev.assert_not_called()
        mock_nav.is_in_left_margin.assert_not_called()

    def test_fun_options_button_pressed(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        assert screen.fun_options_enabled is False
        screen.fun_options_button_pressed()
        assert screen.fun_options_enabled is True
        screen.fun_options_button_pressed()
        assert screen.fun_options_enabled is False

    def test_on_goto_title(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup

        mock_callback = MagicMock()
        screen.on_goto_title_func = mock_callback

        screen.on_goto_title()
        mock_callback.assert_called_once()

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_nav_focus_defaults_to_arrow(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False

        screen.enter_nav_focus(MagicMock())

        assert screen.is_nav_active
        assert screen._nav_focus is _FunFocus.GOTO

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_nav_focus_filter_when_arrow_inactive(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = False
        screen.fun_options_enabled = False

        screen.enter_nav_focus(MagicMock())

        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_up_moves_to_filter_down_back_to_arrow(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())

        assert screen.handle_key(KEY_UP) is True
        assert screen._nav_focus is _FunFocus.FILTER

        assert screen.handle_key(KEY_DOWN) is True
        assert screen._nav_focus is _FunFocus.GOTO

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_on_arrow_calls_goto(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        goto = MagicMock()
        screen.on_goto_title_func = goto
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())

        assert screen.handle_key(KEY_ENTER) is True
        goto.assert_called_once()

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_enter_on_filter_opens_menu(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = False  # focus starts on the filter button
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())
        assert screen._nav_focus is _FunFocus.FILTER

        assert screen.handle_key(KEY_ENTER) is True
        assert screen.fun_options_enabled is True
        assert screen._nav_focus is _FunFocus.MENU

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_escape_on_buttons_exits_to_caller(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        exit_cb = MagicMock()
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(exit_cb)

        assert screen.handle_key(KEY_ESCAPE) is True
        exit_cb.assert_called_once()
        assert not screen.is_nav_active

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_menu_opens_focused_on_all_radio(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.ids["checkbox_custom_image_types"].active = False  # menu = [x, All, Custom]
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())

        assert screen._nav_focus is _FunFocus.MENU
        # Index 0 is the close (x) button; focus lands on the All radio (index 1).
        assert screen._menu_idx == 1

        all_idx = screen._menu_idx
        assert screen.handle_key(KEY_DOWN) is True  # -> Custom
        assert screen._menu_idx == all_idx + 1

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_up_from_all_reaches_close_button(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.ids["checkbox_custom_image_types"].active = False
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())  # idx 1 (All)

        assert screen.handle_key(KEY_UP) is True  # -> close (x) button, index 0
        assert screen._menu_idx == 0

        assert screen.handle_key(KEY_ENTER) is True  # x closes the menu
        assert screen.fun_options_enabled is False
        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_selecting_custom_then_down_reaches_clear_all(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.ids["checkbox_custom_image_types"].active = False
        screen.ids["custom_options_box"].children = []
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())  # idx 1 (All)

        screen.handle_key(KEY_DOWN)  # -> Custom (index 2)
        screen.handle_key(KEY_ENTER)  # select Custom: menu grows with Clear-All
        assert screen.ids["checkbox_custom_image_types"].active is True

        with patch.object(screen, "view_options_clear_all_button_pressed") as mock_clear:
            assert screen.handle_key(KEY_DOWN) is True  # -> Clear-All (index 3)
            assert screen.handle_key(KEY_ENTER) is True

        mock_clear.assert_called_once()

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_menu_space_toggles_theme_row(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        row = MagicMock()
        row.active = False
        screen.ids["custom_options_box"].children = [row]
        screen.ids["checkbox_custom_image_types"].active = True  # menu grows with rows
        screen.fun_options_enabled = True
        # Menu = [x, All, Custom, Clear-All, row]; opens on All (index 1).
        screen.enter_nav_focus(MagicMock())

        screen.handle_key(KEY_DOWN)  # Custom (idx 2)
        screen.handle_key(KEY_DOWN)  # Clear-All (idx 3)
        screen.handle_key(KEY_DOWN)  # theme row (idx 4)
        assert screen.handle_key(KEY_SPACE) is True

        assert row.active is True

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_menu_escape_closes_menu(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())
        assert screen._nav_focus is _FunFocus.MENU

        assert screen.handle_key(KEY_ESCAPE) is True
        assert screen.fun_options_enabled is False
        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_exit_nav_focus_deactivates(
        self, screen_setup: tuple[FunImageViewScreen, MagicMock, MagicMock]
    ) -> None:
        screen, _, _ = screen_setup
        screen.enter_nav_focus(MagicMock())
        assert screen.is_nav_active

        screen.exit_nav_focus()
        assert not screen.is_nav_active


_Setup = tuple[FunImageViewScreen, MagicMock, MagicMock]


class TestTapsAndClicks:
    """Which presses the margins take, and which go on to the widgets under them."""

    def test_the_tap_targets_are_the_two_margins(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = True
        nav.tap_regions.return_value = {
            "left margin": (0, 10, 20, 30),
            "right margin": (80, 10, 20, 30),
            "top margin": (0, 90, 100, 10),
        }
        with patch.object(
            barks_reader.ui.fun_image_view_screen,
            "window_rect",
            side_effect=lambda _widget, *rect: rect,
        ):
            regions = screen.tap_target_regions()

        nav.tap_regions.assert_called_once_with(100, 100)
        assert regions == {"left margin": (0, 10, 20, 30), "right margin": (80, 10, 20, 30)}

    @pytest.mark.parametrize(("visible", "menu_open"), [(False, False), (True, True)])
    def test_hidden_or_under_the_menu_there_is_nothing_to_tap(
        self, screen_setup: _Setup, visible: bool, menu_open: bool
    ) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = visible
        screen.fun_options_enabled = menu_open
        assert screen.tap_target_regions() == {}
        nav.tap_regions.assert_not_called()

    def test_under_the_menu_a_press_goes_to_the_widgets(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = True
        screen.fun_options_enabled = True
        nav.is_in_left_margin.return_value = True
        with (
            patch.object(BoxLayout, "on_touch_down", return_value=True) as widgets_press,
            patch.object(screen, "_goto_previous_image") as previous,
        ):
            assert screen.on_touch_down(MagicMock(x=5, y=5)) is True
        widgets_press.assert_called_once()
        previous.assert_not_called()

    @pytest.mark.parametrize("menu_open", [False, True])
    def test_hidden_the_screen_takes_no_press(self, screen_setup: _Setup, menu_open: bool) -> None:
        # The hidden screen lies full-size under the showing one: its options button
        # took the title view's top-left presses and opened the menu out of sight.
        screen, nav, _ = screen_setup
        screen.is_visible = False
        screen.fun_options_enabled = menu_open
        nav.is_in_left_margin.return_value = True
        with (
            patch.object(BoxLayout, "on_touch_down", return_value=True) as widgets_press,
            patch.object(screen, "_goto_previous_image") as previous,
        ):
            assert screen.on_touch_down(MagicMock(x=5, y=5)) is False
        widgets_press.assert_not_called()
        previous.assert_not_called()

    def test_the_goto_arrow_wins_over_the_margin_under_it(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = True
        screen.ids["goto_title_overlay"].goto_button.collide_point.return_value = True
        nav.is_in_right_margin.return_value = True
        with (
            patch.object(BoxLayout, "on_touch_down", return_value=True) as widgets_press,
            patch.object(screen, "_goto_next_image") as next_image,
        ):
            assert screen.on_touch_down(MagicMock(x=95, y=95)) is True
        widgets_press.assert_called_once()
        next_image.assert_not_called()

    def test_a_press_outside_the_margins_goes_to_the_widgets(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = True
        nav.is_in_left_margin.return_value = False
        nav.is_in_right_margin.return_value = False
        with patch.object(BoxLayout, "on_touch_down", return_value=False) as widgets_press:
            assert screen.on_touch_down(MagicMock(x=50, y=50)) is False
        widgets_press.assert_called_once()

    def test_with_debugging_on_a_press_is_logged(
        self, screen_setup: _Setup, loguru_sink: list[str]
    ) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = True
        nav.is_in_left_margin.return_value = True
        with (
            patch.object(barks_reader.ui.fun_image_view_screen, "_DEBUG", True),  # noqa: FBT003
            patch.object(screen, "_goto_previous_image"),
        ):
            screen.on_touch_down(MagicMock(x=5, y=6))
        assert any(m.startswith("Touch down event: ") for m in loguru_sink)


class TestOptionsMenu:
    def test_clear_all_clears_every_theme_row(
        self, screen_setup: _Setup, loguru_sink: list[str]
    ) -> None:
        screen, _, _ = screen_setup
        rows = [MagicMock(active=True), MagicMock(active=False), MagicMock(active=True)]
        screen.ids["custom_options_box"].children = rows

        screen.view_options_clear_all_button_pressed()

        assert [r.active for r in rows] == [False, False, False]
        assert (
            "Fun view options clear all pressed. Setting all checkboxes to inactive." in loguru_sink
        )


@pytest.mark.usefixtures("_no_focus_draw")
class TestKeysLeftAlone:
    """Keys the fun view does not use are handed back, and dead ends do nothing."""

    def test_without_focus_no_key_is_taken(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        assert not screen.is_nav_active
        assert screen.handle_key(KEY_ENTER) is False

    def test_an_unused_key_on_the_buttons_is_handed_back(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        screen.enter_nav_focus(MagicMock())
        assert screen.handle_key(ord("a")) is False

    def test_an_unused_key_in_the_menu_is_handed_back(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())
        assert screen.handle_key(ord("a")) is False
        assert screen._nav_focus is _FunFocus.MENU

    def test_left_and_right_in_the_menu_do_not_change_the_image(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())
        with (
            patch.object(screen, "prev_image") as prev_image,
            patch.object(screen, "next_image") as next_image,
        ):
            assert screen.handle_key(KEY_LEFT) is True
            assert screen.handle_key(KEY_RIGHT) is True
        prev_image.assert_not_called()
        next_image.assert_not_called()

    def test_enter_on_an_arrow_that_went_inactive_does_nothing(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        goto = MagicMock()
        screen.on_goto_title_func = goto
        screen.enter_nav_focus(MagicMock())  # on the arrow
        screen.goto_title_button_active = False

        assert screen.handle_key(KEY_ENTER) is True

        goto.assert_not_called()
        assert screen._nav_focus is _FunFocus.GOTO

    def test_escape_in_a_menu_already_closed_still_returns_to_the_filter(
        self, screen_setup: _Setup
    ) -> None:
        """The menu can be shut by a click while keyboard focus is in it."""
        screen, _, _ = screen_setup
        screen.fun_options_enabled = True
        screen.enter_nav_focus(MagicMock())
        screen.fun_options_enabled = False

        assert screen.handle_key(KEY_ESCAPE) is True

        assert screen.fun_options_enabled is False  # not toggled back open
        assert screen._nav_focus is _FunFocus.FILTER

    def test_escape_with_no_one_to_return_focus_to_just_leaves(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        screen.enter_nav_focus(MagicMock())
        screen._nav_on_exit_request = None

        assert screen.handle_key(KEY_ESCAPE) is True
        assert not screen.is_nav_active


def test_an_inactive_goto_button_is_given_no_focus_ring(
    screen_setup: _Setup,
) -> None:
    screen, _, _ = screen_setup
    mod = barks_reader.ui.fun_image_view_screen
    screen._nav_focus = _FunFocus.GOTO
    screen.goto_title_button_active = False
    with (
        patch.object(mod, "draw_focus_highlight") as draw,
        patch.object(mod, "clear_focus_highlight") as clear,
    ):
        screen._draw_nav_focus()
    draw.assert_not_called()
    assert clear.call_count == 3  # the two goto buttons and the filter  # noqa: PLR2004


def _info(name: str, title: Titles = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD) -> ImageInfo:
    return ImageInfo(Path(name), title, FIT_MODE_COVER)


def _texture(width: int, height: int) -> MagicMock:
    return MagicMock(width=width, height=height)


def _stack_the_tiers(screen: FunImageViewScreen, nav: MagicMock | None = None) -> None:
    """Two story images on the spread: the tiers stack.

    With `nav`, the view is visible and its margins' band is all but the top and
    bottom slivers of its 100 x 100, so a press can be placed by its thirds.
    """
    screen.layout_mode = MainLayoutMode.SPREAD.value
    loader = MagicMock()
    screen.set_load_texture_func(loader)
    screen.set_load_image_func(MagicMock())
    screen.set_last_loaded_image_info(_info("a.png", Titles.GIFT_LION))
    screen.set_last_loaded_image_info(_info("b.png", Titles.LOST_IN_THE_ANDES))
    (_, apply_texture), _ = loader.call_args
    apply_texture(_texture(400, 300))  # the lower tier's title and texture
    screen.image_texture = _texture(400, 300)
    screen._update_stacked()  # the fixture skips the on_<property> bindings
    if nav is not None:
        screen.is_visible = True
        nav.y_bottom_margin = 2
        nav.y_top_margin = 96


class TestTheSpreadsTwoTiers:
    """On the two-page spread the view stacks the image on show over the one before it."""

    @staticmethod
    def _on_the_spread(screen: FunImageViewScreen) -> MagicMock:
        # The fixture skips Widget.__init__, which binds the on_<property> handlers,
        # so the layout mode's handler runs by hand where a test needs it.
        screen.layout_mode = MainLayoutMode.SPREAD.value
        loader = MagicMock()
        screen.set_load_texture_func(loader)
        screen.set_load_image_func(MagicMock())
        return loader

    def test_on_a_single_page_the_lower_tier_stays_empty(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        loader = MagicMock()
        screen.set_load_texture_func(loader)
        screen.set_last_loaded_image_info(_info("a.png"))
        screen.set_last_loaded_image_info(_info("b.png"))
        loader.assert_not_called()
        assert screen.previous_image_texture is None

    def test_the_lower_tier_shows_the_image_before_the_one_on_show(
        self, screen_setup: _Setup, loguru_sink: list[str]
    ) -> None:
        screen, _, _ = screen_setup
        loader = self._on_the_spread(screen)
        screen.set_last_loaded_image_info(_info("a.png"))
        loader.assert_not_called()  # Nothing before the first.
        assert any(log_markers.FUN_VIEW_LOWER_TIER_EMPTY in line for line in loguru_sink)

        screen.set_last_loaded_image_info(_info("b.png", Titles.GIFT_LION))
        (previous, apply_texture), _ = loader.call_args
        assert previous == _info("a.png")
        texture = _texture(400, 300)
        apply_texture(texture)
        assert screen.previous_image_texture is texture
        assert screen.previous_image_fit_mode == FIT_MODE_COVER
        assert screen.previous_title_str == "Donald Duck Finds Pirate Gold"
        marker = pattern(
            log_markers.FUN_VIEW_LOWER_TIER,
            filename="a.png",
            title="Donald Duck Finds Pirate Gold",
        )
        assert any(re.search(marker, line) for line in loguru_sink)

    def test_a_texture_that_arrives_after_another_step_is_dropped(
        self, screen_setup: _Setup
    ) -> None:
        screen, _, _ = screen_setup
        loader = self._on_the_spread(screen)
        screen.set_last_loaded_image_info(_info("a.png"))
        screen.set_last_loaded_image_info(_info("b.png"))
        screen.set_last_loaded_image_info(_info("c.png"))
        (_, apply_a), _ = loader.call_args_list[0]
        (wanted, apply_b), _ = loader.call_args_list[1]
        assert wanted == _info("b.png")
        late, timely = _texture(4, 3), _texture(4, 3)
        apply_a(late)
        assert screen.previous_image_texture is None
        apply_b(timely)
        assert screen.previous_image_texture is timely

    def test_stepping_back_moves_the_lower_tier_with_it(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        loader = self._on_the_spread(screen)
        for name in ("a.png", "b.png", "c.png"):
            screen.set_last_loaded_image_info(_info(name))
        loader.reset_mock()
        screen.prev_image()  # c -> b on show; a before it.
        (previous, _), _ = loader.call_args
        assert previous == _info("a.png")
        loader.reset_mock()
        screen.prev_image()  # a on show; nothing before it.
        loader.assert_not_called()
        assert screen.previous_image_texture is None

    @pytest.mark.parametrize(
        ("layout", "with_previous", "size", "expected"),
        [
            (MainLayoutMode.SPREAD, True, (400, 300), True),
            (MainLayoutMode.SPREAD, True, (300, 300), True),
            (MainLayoutMode.SPREAD, True, (300, 400), True),  # A tall image stacks too.
            (MainLayoutMode.SPREAD, False, (400, 300), False),
            (MainLayoutMode.SINGLE, True, (400, 300), False),
        ],
    )
    def test_stacked_on_the_spread_with_an_image_of_any_shape_over_a_previous_one(
        self,
        screen_setup: _Setup,
        layout: MainLayoutMode,
        with_previous: bool,
        size: tuple[int, int],
        expected: bool,
    ) -> None:
        screen, _, _ = screen_setup
        screen.layout_mode = layout.value
        screen.image_texture = _texture(*size)
        screen.previous_image_texture = _texture(4, 3) if with_previous else None
        screen.on_image_texture(screen, screen.image_texture)
        assert screen.stacked is expected

    def test_on_the_spread_the_outer_thirds_step_and_the_middle_zooms(
        self, screen_setup: _Setup, loguru_sink: list[str]
    ) -> None:
        """Both tiers move with the history on an outer third; the middle third zooms."""
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        with (
            patch.object(screen, "_goto_previous_image") as back,
            patch.object(screen, "_goto_next_image") as forward,
        ):
            assert screen.on_touch_down(MagicMock(x=10, y=20)) is True  # Left, lower tier.
            assert screen.on_touch_down(MagicMock(x=20, y=80)) is True  # Left, upper tier.
            assert back.call_count == 2  # noqa: PLR2004
            assert screen.on_touch_down(MagicMock(x=90, y=20)) is True  # Right, lower tier.
            forward.assert_called_once()
            assert not screen.zoomed

        assert screen.on_touch_down(MagicMock(x=50, y=20)) is True  # Middle, lower tier.
        assert screen.zoomed == "lower"
        assert not screen.tiered
        assert log_markers.MIDDLE_PRESSED.format(x=50, y=20, tier="lower") in loguru_sink
        assert log_markers.FUN_VIEW_ZOOM.format(tier="lower") in loguru_sink
        assert screen._history.index == 1  # The history stays put.

        assert screen.on_touch_down(MagicMock(x=50, y=80)) is True  # Middle, zoomed: out.
        assert not screen.zoomed
        assert screen.tiered
        assert log_markers.FUN_VIEW_ZOOM.format(tier="off") in loguru_sink

        assert screen.on_touch_down(MagicMock(x=50, y=80)) is True  # Middle, upper tier.
        assert screen.zoomed == "upper"

    def test_a_press_above_or_below_the_margins_band_is_not_a_step(
        self, screen_setup: _Setup
    ) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        with patch.object(BoxLayout, "on_touch_down", return_value=False):
            assert screen.on_touch_down(MagicMock(x=10, y=98)) is False
            assert screen.on_touch_down(MagicMock(x=50, y=1)) is False
        assert not screen.zoomed

    def test_a_lone_image_has_nothing_to_zoom(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        screen.previous_image_texture = None
        screen._update_stacked()
        assert not screen.stacked
        with patch.object(BoxLayout, "on_touch_down", return_value=False):
            assert screen.on_touch_down(MagicMock(x=50, y=20)) is False
        assert not screen.zoomed

    def test_zoomed_in_on_the_lower_tier_the_goto_button_is_that_images(
        self, screen_setup: _Setup
    ) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        goto = MagicMock()
        screen.on_goto_title_func = goto
        screen.on_touch_down(MagicMock(x=50, y=20))
        assert screen.goto_title_button_active
        assert not screen.lower_goto_title_button_active
        screen.on_goto_title()
        goto.assert_called_once_with(
            from_keyboard=False, image_info=_info("a.png", Titles.GIFT_LION)
        )

        screen.previous_title_str = ""
        screen._update_tiered()
        assert not screen.goto_title_button_active

        goto.reset_mock()
        screen.on_touch_down(MagicMock(x=50, y=20))  # Out, then in on the upper tier.
        screen.on_touch_down(MagicMock(x=50, y=80))
        assert screen.zoomed == "upper"
        screen.on_goto_title()
        goto.assert_called_once_with(from_keyboard=False)

    @pytest.mark.parametrize("step", ["back", "forward", "new image", "layout"])
    def test_a_step_ends_the_zoom(self, screen_setup: _Setup, step: str) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        screen.on_touch_down(MagicMock(x=50, y=20))
        assert screen.zoomed
        if step == "back":
            screen.prev_image()
        elif step == "forward":
            screen._history.back()
            screen.next_image()
        elif step == "new image":
            screen.set_last_loaded_image_info(_info("c.png"))
        else:
            screen.layout_mode = MainLayoutMode.SINGLE.value
            screen.on_layout_mode(screen, screen.layout_mode)
        assert not screen.zoomed

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_a_zoom_moves_the_keyboard_focus_off_the_lower_button(
        self, screen_setup: _Setup
    ) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())
        screen.handle_key(KEY_DOWN)
        assert screen._nav_focus is _FunFocus.LOWER_GOTO
        screen.on_touch_down(MagicMock(x=50, y=20))
        assert screen._nav_focus is _FunFocus.GOTO

    @pytest.mark.parametrize(
        ("zoom", "expected_middle"),
        [
            ("", {"upper middle": (33, 50, 33, 46), "lower middle": (33, 2, 33, 48)}),
            ("lower", {"middle": (33, 2, 33, 94)}),
        ],
    )
    def test_on_the_spread_the_tap_targets_are_thirds(
        self, screen_setup: _Setup, zoom: str, expected_middle: dict[str, tuple[int, ...]]
    ) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        screen._set_zoom(zoom)
        nav.tap_regions.return_value = {
            "left margin": (0, 2, 50, 94),
            "right margin": (50, 2, 50, 94),
            "top margin": (0, 96, 100, 4),
        }
        with patch.object(
            barks_reader.ui.fun_image_view_screen,
            "window_rect",
            side_effect=lambda _widget, *rect: rect,
        ):
            regions = screen.tap_target_regions()
        assert regions == {
            "left margin": (0, 2, 33, 94),
            "right margin": (66, 2, 34, 94),
            **expected_middle,
        }

    def test_a_lone_image_has_no_middle_target(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        screen.previous_image_texture = None
        screen._update_stacked()
        nav.tap_regions.return_value = {"left margin": (0, 2, 50, 94)}
        with patch.object(
            barks_reader.ui.fun_image_view_screen,
            "window_rect",
            side_effect=lambda _widget, *rect: rect,
        ):
            regions = screen.tap_target_regions()
        assert set(regions) == {"left margin", "right margin"}

    def test_a_second_image_is_wanted_on_the_spread_with_one_shown(
        self, screen_setup: _Setup
    ) -> None:
        screen, _, _ = screen_setup
        self._on_the_spread(screen)
        assert not screen._needs_a_second_image()
        screen.set_last_loaded_image_info(_info("a.png"))
        assert screen._needs_a_second_image()
        screen.set_last_loaded_image_info(_info("b.png"))
        assert not screen._needs_a_second_image()
        screen.layout_mode = MainLayoutMode.SINGLE.value
        screen._history.back()
        assert not screen._needs_a_second_image()

    def test_a_second_image_is_wanted_at_the_oldest_image(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        self._on_the_spread(screen)
        screen.set_last_loaded_image_info(_info("a.png"))
        screen.set_last_loaded_image_info(_info("b.png"))
        assert not screen._needs_a_second_image()
        screen._history.back()
        assert screen._needs_a_second_image()

    def test_the_first_image_on_the_spread_is_given_one_behind_it(
        self, screen_setup: _Setup, loguru_sink: list[str]
    ) -> None:
        """The lower tier is fed at boot, and on a switch to the spread (`on_layout_mode`)."""
        screen, _, _ = screen_setup
        loader = self._on_the_spread(screen)
        picker = MagicMock(return_value=_info("seed.png", Titles.GIFT_LION))
        screen.set_pick_image_func(picker)
        screen.set_last_loaded_image_info(_info("a.png"))

        picker.assert_called_once_with()
        assert [info.filename.name for info in screen._history.images] == ["seed.png", "a.png"]
        assert screen._history.index == 1
        (previous, _), _ = loader.call_args
        assert previous == _info("seed.png", Titles.GIFT_LION)
        marker = pattern(log_markers.FUN_VIEW_SEEDED, filename="seed.png", title="Gift Lion")
        assert any(re.search(marker, line) for line in loguru_sink)

    def test_a_step_back_to_the_oldest_image_puts_one_more_behind_it(
        self, screen_setup: _Setup
    ) -> None:
        """A tap on the lower tier at boot collapsed the tiers: the oldest had none below."""
        screen, _, _ = screen_setup
        loader = self._on_the_spread(screen)
        picker = MagicMock(side_effect=[_info("seed.png"), _info("older.png")])
        screen.set_pick_image_func(picker)
        screen.set_last_loaded_image_info(_info("a.png"))  # Fed: the seed goes behind.
        screen.set_last_loaded_image_info(_info("b.png"))

        screen._goto_previous_image()  # Onto "a": the seed below it, nothing picked.
        assert picker.call_count == 1
        screen._goto_previous_image()  # Onto the seed: one more picked and put behind.

        assert picker.call_count == 2  # noqa: PLR2004
        assert [info.filename.name for info in screen._history.images] == [
            "older.png",
            "seed.png",
            "a.png",
            "b.png",
        ]
        assert screen._history.index == 1
        (previous, _), _ = loader.call_args  # the lower tier, loaded with the new pick
        assert previous == _info("older.png")

    def test_a_step_back_with_more_behind_picks_nothing_more(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        self._on_the_spread(screen)
        picker = MagicMock(return_value=_info("seed.png"))
        screen.set_pick_image_func(picker)
        for name in ("a.png", "b.png", "c.png"):
            screen.set_last_loaded_image_info(_info(name))
        screen._goto_previous_image()
        picker.assert_called_once_with()  # At the first image only.

    def test_on_a_single_page_a_step_back_picks_nothing(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        screen.set_load_texture_func(MagicMock())
        screen.set_load_image_func(MagicMock())
        picker = MagicMock()
        screen.set_pick_image_func(picker)
        screen.set_last_loaded_image_info(_info("a.png"))
        screen.set_last_loaded_image_info(_info("b.png"))
        screen._goto_previous_image()
        picker.assert_not_called()
        assert screen._history.index == 0

    def test_a_switch_to_the_spread_feeds_the_lower_tier(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        loader = MagicMock()
        screen.set_load_texture_func(loader)
        screen.set_load_image_func(MagicMock())
        picker = MagicMock(return_value=_info("seed.png"))
        screen.set_pick_image_func(picker)
        screen.set_last_loaded_image_info(_info("a.png"))  # On the single page: unfed.
        picker.assert_not_called()

        screen.layout_mode = MainLayoutMode.SPREAD.value
        screen.on_layout_mode(screen, screen.layout_mode)
        picker.assert_called_once_with()
        (previous, _), _ = loader.call_args
        assert previous == _info("seed.png")

    def test_the_tap_margins_come_from_the_views_own_size(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        screen.on_size(screen, (300.0, 200.0))
        nav.update_regions.assert_called_once_with(300, 200, 0, 0)


class TestTheLowerTiersGotoButton:
    """Stacked, the lower tier carries its own goto button: a tap target and a key stop."""

    @staticmethod
    def _stack(screen: FunImageViewScreen) -> None:
        _stack_the_tiers(screen)

    def test_stacking_is_logged_and_arms_the_lower_button(
        self, screen_setup: _Setup, loguru_sink: list[str]
    ) -> None:
        screen, _, _ = screen_setup
        self._stack(screen)
        assert screen.stacked
        assert screen.lower_goto_title_button_active
        assert log_markers.FUN_VIEW_STACKED.format(state=True) in loguru_sink

        screen.layout_mode = MainLayoutMode.SINGLE.value
        screen._update_stacked()
        assert not screen.stacked
        assert not screen.lower_goto_title_button_active
        assert log_markers.FUN_VIEW_STACKED.format(state=False) in loguru_sink

    def test_a_stock_image_in_the_lower_tier_gets_no_button(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        self._stack(screen)
        screen.previous_title_str = ""
        screen._update_stacked()
        assert screen.stacked
        assert not screen.lower_goto_title_button_active

    def test_the_lower_button_wins_over_the_lower_tier_under_it(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        _stack_the_tiers(screen, nav)
        screen.ids["lower_goto_title_overlay"].goto_button.collide_point.return_value = True
        with (
            patch.object(BoxLayout, "on_touch_down", return_value=True) as widgets_press,
            patch.object(screen, "_goto_next_image") as forward,
        ):
            assert screen.on_touch_down(MagicMock(x=90, y=40)) is True
        widgets_press.assert_called_once()
        forward.assert_not_called()

    def test_unstacked_the_lower_button_takes_no_press(self, screen_setup: _Setup) -> None:
        screen, nav, _ = screen_setup
        screen.is_visible = True
        screen.ids["lower_goto_title_overlay"].goto_button.collide_point.return_value = True
        nav.is_in_left_margin.return_value = True
        with patch.object(screen, "_goto_previous_image") as back:
            assert screen.on_touch_down(MagicMock(x=5, y=40)) is True
        back.assert_called_once_with()

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_down_reaches_the_lower_button_and_enter_goes_to_its_story(
        self, screen_setup: _Setup
    ) -> None:
        screen, _, _ = screen_setup
        self._stack(screen)
        goto = MagicMock()
        screen.on_goto_title_func = goto
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())
        assert screen._nav_focus is _FunFocus.GOTO

        assert screen.handle_key(KEY_DOWN) is True
        assert screen._nav_focus is _FunFocus.LOWER_GOTO
        assert screen.handle_key(KEY_ENTER) is True
        goto.assert_called_once_with(
            from_keyboard=True, image_info=_info("a.png", Titles.GIFT_LION)
        )

        assert screen.handle_key(KEY_UP) is True
        assert screen._nav_focus is _FunFocus.GOTO
        assert screen.handle_key(KEY_UP) is True
        assert screen._nav_focus is _FunFocus.FILTER

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_unstacked_down_stays_on_the_goto_button(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        screen.goto_title_button_active = True
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())
        assert screen.handle_key(KEY_DOWN) is True
        assert screen._nav_focus is _FunFocus.GOTO

    @pytest.mark.usefixtures("_no_focus_draw")
    def test_a_step_that_unstacks_moves_focus_off_the_lower_button(
        self, screen_setup: _Setup
    ) -> None:
        screen, _, _ = screen_setup
        self._stack(screen)
        screen.fun_options_enabled = False
        screen.enter_nav_focus(MagicMock())
        screen.handle_key(KEY_DOWN)
        assert screen._nav_focus is _FunFocus.LOWER_GOTO
        screen.lower_goto_title_button_active = False
        screen._reconcile_button_focus()
        assert screen._nav_focus is _FunFocus.GOTO

    def test_a_lower_button_press_names_the_lower_image(self, screen_setup: _Setup) -> None:
        screen, _, _ = screen_setup
        self._stack(screen)
        goto = MagicMock()
        screen.on_goto_title_func = goto
        screen.on_goto_lower_title()
        goto.assert_called_once_with(
            from_keyboard=False, image_info=_info("a.png", Titles.GIFT_LION)
        )

    def test_while_a_steps_lower_texture_loads_the_lower_button_is_off(
        self, screen_setup: _Setup
    ) -> None:
        """The tier shows the old image until the new one comes: no goto to either."""
        screen, _, _ = screen_setup
        self._stack(screen)
        loader = screen._load_texture
        assert isinstance(loader, MagicMock)
        goto = MagicMock()
        screen.on_goto_title_func = goto

        # The image on show (stock, no title) becomes the one before the next.
        screen.set_last_loaded_image_info(_info("c.png"))
        assert screen.stacked  # the old lower texture still shows
        assert not screen.lower_goto_title_button_active
        screen.on_goto_lower_title()
        goto.assert_not_called()

        (wanted, apply_texture), _ = loader.call_args
        assert wanted == _info("b.png", Titles.LOST_IN_THE_ANDES)
        apply_texture(_texture(400, 300))
        assert screen.lower_goto_title_button_active
        screen.on_goto_lower_title()
        goto.assert_called_once_with(from_keyboard=False, image_info=wanted)
