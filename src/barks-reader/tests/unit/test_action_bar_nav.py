# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_UP,
)
from barks_reader.ui import reader_keyboard_nav as nav_module
from barks_reader.ui.reader_keyboard_nav import (
    _FOCUS_BINDING_ATTR,
    ActionBarNavMixin,
    DropdownNavMixin,
    NavExitMixin,
    clear_focus_highlight,
    draw_focus_highlight,
    open_dropdown,
)
from kivy.uix.behaviors import button as behaviors_button
from kivy.uix.button import Button

if TYPE_CHECKING:
    from collections.abc import Iterator


def _make_widget() -> MagicMock:
    """Create a MagicMock widget with the focus binding attribute initialized."""
    widget = MagicMock()
    setattr(widget, _FOCUS_BINDING_ATTR, None)
    return widget


class _StubScreen(ActionBarNavMixin):
    """Minimal concrete subclass for testing."""

    def __init__(
        self, buttons: list, *, action_bar_hidden: bool = False, default_focus_idx: int = 0
    ) -> None:
        self._action_bar_hidden = action_bar_hidden
        for button in buttons:
            button.disabled = False  # a mock's own `disabled` is another mock, and true
        self._setup_action_bar_nav(buttons, default_focus_idx=default_focus_idx)

    def _is_action_bar_hidden(self) -> bool:
        return self._action_bar_hidden

    def _on_action_bar_shown_for_menu(self) -> None:
        self._action_bar_hidden = False


class TestEnterMenuMode:
    def test_focus_drawn_when_action_bar_visible(self) -> None:
        buttons = [MagicMock(), MagicMock()]
        screen = _StubScreen(buttons, action_bar_hidden=False)

        with patch.object(nav_module, "update_focus_in_list") as mock_update:
            screen._enter_menu_mode()

            mock_update.assert_called_once()

    def test_focus_drawn_when_action_bar_was_hidden(self) -> None:
        buttons = [MagicMock(), MagicMock()]
        screen = _StubScreen(buttons, action_bar_hidden=True)

        with patch.object(nav_module, "update_focus_in_list") as mock_update:
            screen._enter_menu_mode()

            # Focus is drawn immediately; the reactive binding handles
            # geometry corrections after layout.
            mock_update.assert_called_once()


class TestDefaultFocusIndex:
    def test_enter_menu_mode_focuses_default_button(self) -> None:
        buttons = [MagicMock() for _ in range(4)]
        screen = _StubScreen(buttons, default_focus_idx=2)

        with patch.object(nav_module, "update_focus_in_list") as mock_update:
            screen._enter_menu_mode()

        assert screen._focused_btn_idx == 2  # noqa: PLR2004
        mock_update.assert_called_once_with(buttons, 2, nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)

    def test_touch_resets_last_used_to_default(self) -> None:
        buttons = [MagicMock() for _ in range(4)]
        screen = _StubScreen(buttons, default_focus_idx=2)

        with (
            patch.object(nav_module, "update_focus_in_list"),
            patch.object(nav_module, "clear_focus_in_list"),
        ):
            screen._enter_menu_mode()
            screen._last_used_btn_idx = 0  # simulate the quit button being used
            screen._enter_menu_mode()
            screen._clear_menu_on_touch()

        assert screen._last_used_btn_idx == 2  # noqa: PLR2004


class TestMenuActionByKeyboardFlag:
    """The keyboard-activation flag must survive the deferred menu-button on_release.

    A menu button's trigger_action fires on_release asynchronously (0.1s press), after
    _exit_menu_mode has cleared _menu_mode — so the handler can't read _menu_mode to tell
    keyboard from mouse. This flag, set at activation time, is that signal.
    """

    def test_flag_starts_false(self) -> None:
        screen = _StubScreen([MagicMock(), MagicMock()])
        assert screen._menu_action_by_keyboard is False

    def test_keyboard_activation_sets_flag_before_menu_mode_torn_down(self) -> None:
        buttons = [MagicMock(), MagicMock()]
        screen = _StubScreen(buttons, default_focus_idx=1)
        with (
            patch.object(nav_module, "update_focus_in_list"),
            patch.object(nav_module, "clear_focus_in_list"),
        ):
            screen._enter_menu_mode()
            screen._activate_focused_button()

        assert screen._menu_action_by_keyboard is True
        assert screen._menu_mode is False  # torn down, but the flag persists
        buttons[1].trigger_action.assert_called_once()

    def test_a_disabled_button_is_not_pressed_and_the_menu_stays(self) -> None:
        """Kivy's trigger_action presses a disabled button: Collapse ran while greyed."""
        buttons = [MagicMock(), MagicMock()]
        screen = _StubScreen(buttons)
        buttons[1].disabled = True
        with (
            patch.object(nav_module, "update_focus_in_list"),
            patch.object(nav_module, "clear_focus_in_list"),
        ):
            screen._enter_menu_mode()
            assert screen._handle_reader_key(KEY_RIGHT) is True
            assert screen._handle_reader_key(KEY_ENTER) is True  # taken, and nothing done

            buttons[1].trigger_action.assert_not_called()
            assert screen._menu_mode is True
            assert screen._menu_action_by_keyboard is False
            assert screen._last_used_btn_idx == 0

            # The ring can still leave it, and the next button is pressed as ever.
            assert screen._handle_reader_key(KEY_LEFT) is True
            assert screen._handle_reader_key(KEY_ENTER) is True
        buttons[0].trigger_action.assert_called_once_with()
        assert screen._menu_mode is False

    def test_touch_clears_flag(self) -> None:
        screen = _StubScreen([MagicMock(), MagicMock()])
        screen._menu_action_by_keyboard = True

        screen._clear_menu_on_touch()

        assert screen._menu_action_by_keyboard is False


class TestATouchOnABarTheMenuShowed:
    """A tap leaves the menu; on the bar it keeps a bar the menu showed, for its buttons."""

    @pytest.mark.parametrize(("on_bar", "hidden"), [(True, False), (False, True)])
    def test_the_bar_stays_only_for_a_tap_on_it(self, *, on_bar: bool, hidden: bool) -> None:
        screen = _StubScreen([MagicMock()], action_bar_hidden=True)
        with (
            patch.object(nav_module, "update_focus_in_list"),
            patch.object(nav_module, "clear_focus_in_list"),
            patch.object(screen, "_on_action_bar_hidden_after_menu") as hide_after_menu,
        ):
            screen._enter_menu_mode()  # shows the hidden bar
            screen._clear_menu_on_touch(on_bar=on_bar)
        assert screen._menu_mode is False
        assert hide_after_menu.called is hidden
        assert screen._showed_action_bar_for_menu is False


class TestFocusHighlightBinding:
    """Verify that draw_focus_highlight installs a pos/size binding and clear removes it."""

    def test_draw_binds_to_pos_and_size(self) -> None:
        widget = _make_widget()

        with patch.object(nav_module, "_draw_highlight"):
            draw_focus_highlight(widget, "test_group")

        widget.bind.assert_called_once()
        bind_kwargs = widget.bind.call_args
        assert "pos" in bind_kwargs.kwargs
        assert "size" in bind_kwargs.kwargs

    def test_clear_unbinds(self) -> None:
        widget = _make_widget()

        with patch.object(nav_module, "_draw_highlight"):
            draw_focus_highlight(widget, "test_group")

        clear_focus_highlight(widget, "test_group")

        widget.unbind.assert_called_once()

    def test_redraw_on_geometry_change(self) -> None:
        widget = _make_widget()

        with patch.object(nav_module, "_draw_highlight") as mock_draw:
            draw_focus_highlight(widget, "test_group")
            assert mock_draw.call_count == 1

            # Capture the bound callback and simulate a geometry change.
            bind_kwargs = widget.bind.call_args.kwargs
            on_change = bind_kwargs["pos"]
            on_change()

            # _draw_highlight called twice: initial draw + redraw.
            assert mock_draw.call_count == 2  # noqa: PLR2004

    def test_successive_draws_unbind_previous(self) -> None:
        widget = _make_widget()

        with patch.object(nav_module, "_draw_highlight"):
            draw_focus_highlight(widget, "group_a")
            draw_focus_highlight(widget, "group_b")

        # First draw binds, second draw unbinds the first then binds again.
        assert widget.unbind.call_count == 1
        assert widget.bind.call_count == 2  # noqa: PLR2004


class TestNavFocusLog:
    """Every focus ring drawn logs where it landed; the GUI path tests wait on that line."""

    def test_draw_logs_the_widget_and_its_text(self, loguru_sink: list[str]) -> None:
        widget = _make_widget()
        widget.text = "Titles"
        with patch.object(nav_module, "_draw_highlight"):
            draw_focus_highlight(widget, "test_group")
        assert 'Nav focus on MagicMock "Titles".' in loguru_sink

    def test_a_widget_without_text_logs_its_class_alone(self, loguru_sink: list[str]) -> None:
        widget = _make_widget()  # its .text is a MagicMock, not a str
        with patch.object(nav_module, "_draw_highlight"):
            draw_focus_highlight(widget, "test_group")
        assert "Nav focus on MagicMock." in loguru_sink


class _StubDropdownScreen(DropdownNavMixin, ActionBarNavMixin):
    def __init__(self) -> None:
        self._setup_action_bar_nav([MagicMock(disabled=False)])
        self._setup_dropdown_nav()
        self._items = [MagicMock(), MagicMock()]

    def _get_dropdown_buttons(self) -> list:
        return self._items


class TestDropdownDismissedLog:
    """A dismissed dropdown logs it, whether or not keyboard nav was inside it."""

    def test_logged_outside_dropdown_nav(self, loguru_sink: list[str]) -> None:
        _StubDropdownScreen()._on_dropdown_dismissed(MagicMock())
        assert "Dropdown dismissed." in loguru_sink

    def test_logged_from_inside_dropdown_nav(self, loguru_sink: list[str]) -> None:
        screen = _StubDropdownScreen()
        with patch.object(nav_module, "draw_focus_highlight"):
            screen._enter_dropdown_nav()
        with patch.object(nav_module, "clear_focus_highlight"):
            screen._on_dropdown_dismissed(MagicMock())
        assert "Dropdown dismissed." in loguru_sink
        assert screen._dropdown_nav_mode is False


class TestOpenDropdown:
    """A dropdown asked for off screen says so; the soak's crash was its raising instead."""

    def test_off_screen_it_logs_and_does_not_open(self, loguru_sink: list[str]) -> None:
        dropdown = MagicMock()
        dropdown.open_if_shown.return_value = False
        widget = _make_widget()
        widget.text = "Goto Page"
        assert open_dropdown(dropdown, widget) is False
        assert 'Dropdown not opened: MagicMock "Goto Page" is not on screen.' in loguru_sink

    def test_on_screen_it_opens_quietly(self, loguru_sink: list[str]) -> None:
        dropdown = MagicMock()
        dropdown.open_if_shown.return_value = True
        assert open_dropdown(dropdown, _make_widget()) is True
        assert not any("Dropdown not opened" in line for line in loguru_sink)


class TestEscapeOnAShownBar:
    """Escape dismisses a bar a tap showed, when the screen says so; else it opens the menu."""

    def test_escape_opens_the_menu_by_default(self) -> None:
        screen = _StubScreen([MagicMock()])
        with patch.object(nav_module, "update_focus_in_list"):
            assert screen._handle_reader_key(KEY_ESCAPE)
        assert screen._menu_mode is True

    def test_escape_on_a_bar_the_screen_dismisses_does_not_open_the_menu(self) -> None:
        screen = _StubScreen([MagicMock()])
        with patch.object(screen, "_dismiss_shown_bar_on_escape", return_value=True) as dismiss:
            assert screen._handle_reader_key(KEY_ESCAPE)
        dismiss.assert_called_once_with()
        assert screen._menu_mode is False

    def test_up_opens_the_menu_on_a_bar_escape_would_dismiss(self) -> None:
        screen = _StubScreen([MagicMock()])
        with (
            patch.object(screen, "_dismiss_shown_bar_on_escape", return_value=True) as dismiss,
            patch.object(nav_module, "update_focus_in_list"),
        ):
            assert screen._handle_reader_key(KEY_UP)
        dismiss.assert_not_called()
        assert screen._menu_mode is True


class TestPageTurnHooks:
    """A screen that turns pages by keyboard must supply its own page turns."""

    def test_right_without_an_override_raises(self) -> None:
        screen = _StubScreen([MagicMock()])
        with pytest.raises(NotImplementedError):
            screen._handle_reader_key(KEY_RIGHT)

    def test_left_without_an_override_raises(self) -> None:
        screen = _StubScreen([MagicMock()])
        with pytest.raises(NotImplementedError):
            screen._handle_reader_key(KEY_LEFT)


def test_a_bar_with_no_buttons_has_nowhere_to_move_the_focus_and_says_nothing() -> None:
    """The step round the bar divided by its count of buttons."""
    screen = _StubScreen([])
    screen._move_menu_focus(1)
    assert screen._focused_btn_idx == 0


class _BareDropdownScreen(DropdownNavMixin, ActionBarNavMixin):
    """Overrides none of the dropdown hooks."""

    def __init__(self) -> None:
        self._setup_action_bar_nav([MagicMock(disabled=False)])
        self._setup_dropdown_nav()


class TestDropdownHookDefaults:
    def test_a_screen_naming_no_buttons_offers_none(self) -> None:
        assert _BareDropdownScreen()._get_dropdown_buttons() == []


class _PagedDropdownScreen(_StubDropdownScreen):
    _dropdown_page_step = 3

    def __init__(self, count: int) -> None:
        super().__init__()
        self._items = [MagicMock() for _ in range(count)]


class TestDropdownPageKeys:
    """Page Up and Down jump a page step through a long dropdown, clamped at its ends."""

    def test_page_down_jumps_a_step_and_stops_at_the_last_item(self) -> None:
        screen = _PagedDropdownScreen(8)
        with (
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            screen._enter_dropdown_nav()
            visited = []
            for _ in range(3):
                assert screen._handle_menu_key(KEY_PAGE_DOWN) is True
                visited.append(screen._dropdown_focused_idx)
        assert visited == [3, 6, 7]

    def test_page_up_jumps_a_step_and_stops_at_the_first_item(self) -> None:
        screen = _PagedDropdownScreen(8)
        with (
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            screen._enter_dropdown_nav(initial_idx=7)
            visited = []
            for _ in range(3):
                assert screen._handle_menu_key(KEY_PAGE_UP) is True
                visited.append(screen._dropdown_focused_idx)
        assert visited == [4, 1, 0]

    def test_the_focus_ring_follows_a_page_jump(self) -> None:
        screen = _PagedDropdownScreen(8)
        with (
            patch.object(nav_module, "draw_focus_highlight") as mock_draw,
            patch.object(nav_module, "clear_focus_highlight") as mock_clear,
        ):
            screen._enter_dropdown_nav()
            screen._handle_menu_key(KEY_PAGE_DOWN)
        mock_clear.assert_called_once_with(screen._items[0], nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)
        mock_draw.assert_called_with(screen._items[3], nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)

    def test_a_start_past_the_end_of_the_list_is_its_last_row(self) -> None:
        """A start worked out before the list was rebuilt raised IndexError on opening."""
        screen = _PagedDropdownScreen(3)
        with (
            patch.object(nav_module, "draw_focus_highlight") as mock_draw,
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            screen._enter_dropdown_nav(initial_idx=7)
        assert screen._dropdown_focused_idx == 2  # noqa: PLR2004
        mock_draw.assert_called_once_with(screen._items[2], nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)

    def test_an_empty_list_opens_with_no_ring_and_its_keys_pass_by(self) -> None:
        screen = _PagedDropdownScreen(0)
        with patch.object(nav_module, "draw_focus_highlight") as mock_draw:
            screen._enter_dropdown_nav()
        mock_draw.assert_not_called()
        assert screen._dropdown_nav_mode is True
        assert screen._handle_menu_key(KEY_PAGE_DOWN) is False

    def test_escape_closes_an_empty_list(self) -> None:
        """Its keys gave up on the empty list before Escape was asked: it stayed open."""
        screen = _PagedDropdownScreen(0)
        screen._enter_dropdown_nav()
        with patch.object(screen, "_dismiss_dropdown") as dismiss:
            assert screen._handle_menu_key(KEY_ESCAPE) is True
        dismiss.assert_called_once_with()

    def test_return_twice_before_the_release_chooses_the_row_once(self) -> None:
        """Kivy releases a keyed press a tenth of a second on: a bouncing Return chose twice."""
        screen = _PagedDropdownScreen(2)
        screen._items = [Button(), Button()]
        chosen = MagicMock()
        screen._items[1].bind(on_release=chosen)
        with (
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight"),
            patch.object(behaviors_button, "Clock") as clock,
        ):
            screen._enter_dropdown_nav(initial_idx=1)
            assert screen._handle_menu_key(KEY_ENTER) is True
            assert screen._handle_menu_key(KEY_ENTER) is True
            for release in [c.args[0] for c in clock.schedule_once.call_args_list]:
                release(0)

            assert chosen.call_count == 1
            # Released, it can be chosen again: a list that stays open is not stuck.
            screen._handle_menu_key(KEY_ENTER)
            clock.schedule_once.call_args.args[0](0)
        assert chosen.call_count == 2  # noqa: PLR2004

    def test_page_keys_are_not_consumed_without_a_page_step(self) -> None:
        screen = _StubDropdownScreen()
        with patch.object(nav_module, "draw_focus_highlight"):
            screen._enter_dropdown_nav()
        assert screen._handle_menu_key(KEY_PAGE_DOWN) is False
        assert screen._handle_menu_key(KEY_PAGE_UP) is False
        assert screen._dropdown_focused_idx == 0


def _bar_buttons(screen: ActionBarNavMixin) -> list[MagicMock]:
    """Return the screen's bar buttons as the stand-ins the test gave it."""
    return cast("list[MagicMock]", screen._menu_buttons)


class _PageTurningScreen(_StubScreen):
    """A reader: its bar's buttons, and page turns it only counts."""

    def __init__(self, buttons: list) -> None:
        super().__init__(buttons)
        self.turns: list[str] = []

    def _reading_next_page(self) -> None:
        self.turns.append("next")

    def _reading_prev_page(self) -> None:
        self.turns.append("prev")


class TestTheMenuKeys:
    """In the menu the remote's keys walk the bar, press its button and leave it."""

    @pytest.fixture
    def screen(self) -> Iterator[_PageTurningScreen]:
        with (
            patch.object(nav_module, "update_focus_in_list") as self.focus,
            patch.object(nav_module, "clear_focus_in_list") as self.clear,
        ):
            screen = _PageTurningScreen([MagicMock(name=f"button {i}") for i in range(3)])
            screen._enter_menu_mode()
            self.focus.reset_mock()
            yield screen

    def _focused(self) -> int:
        buttons, index, group = self.focus.call_args.args
        assert group == nav_module.MENU_FOCUS_HIGHLIGHT_GROUP
        assert len(buttons) == 3  # noqa: PLR2004
        return index

    def test_right_goes_to_the_next_button_and_round_from_the_last(
        self, screen: _PageTurningScreen
    ) -> None:
        visited = []
        for _ in range(3):
            assert screen._handle_reader_key(KEY_RIGHT) is True
            visited.append(self._focused())
        assert visited == [1, 2, 0]
        assert screen.turns == []  # the menu has the keys: no page turns under it

    def test_left_goes_to_the_button_before_and_round_from_the_first(
        self, screen: _PageTurningScreen
    ) -> None:
        visited = []
        for _ in range(2):
            assert screen._handle_reader_key(KEY_LEFT) is True
            visited.append(self._focused())
        assert visited == [2, 1]
        assert screen.turns == []

    @pytest.mark.parametrize("enter", [KEY_ENTER, KEY_NUMPAD_ENTER])
    def test_enter_presses_the_focused_button_and_leaves_the_menu(
        self, screen: _PageTurningScreen, enter: int
    ) -> None:
        screen._handle_reader_key(KEY_RIGHT)

        assert screen._handle_reader_key(enter) is True

        first, second, third = _bar_buttons(screen)
        second.trigger_action.assert_called_once_with()
        first.trigger_action.assert_not_called()
        third.trigger_action.assert_not_called()
        assert screen._menu_mode is False
        assert screen._menu_action_by_keyboard is True
        assert screen._last_used_btn_idx == 1  # where the menu opens next time

    def test_escape_leaves_the_menu_pressing_nothing(self, screen: _PageTurningScreen) -> None:
        assert screen._handle_reader_key(KEY_ESCAPE) is True

        assert screen._menu_mode is False
        self.clear.assert_called_once_with(
            screen._menu_buttons, nav_module.MENU_FOCUS_HIGHLIGHT_GROUP
        )
        for button in _bar_buttons(screen):
            button.trigger_action.assert_not_called()

    @pytest.mark.parametrize("key", [KEY_UP, KEY_DOWN, KEY_PAGE_DOWN])
    def test_any_other_key_is_not_the_menu_s(self, screen: _PageTurningScreen, key: int) -> None:
        assert screen._handle_reader_key(key) is False
        assert screen._menu_mode is True
        self.focus.assert_not_called()

    def test_out_of_the_menu_the_same_keys_turn_pages(self, screen: _PageTurningScreen) -> None:
        screen._handle_reader_key(KEY_ESCAPE)

        assert screen._handle_reader_key(KEY_RIGHT) is True
        assert screen._handle_reader_key(KEY_LEFT) is True
        assert screen.turns == ["next", "prev"]

    def test_a_key_reading_has_no_use_for_is_passed_by(self, screen: _PageTurningScreen) -> None:
        screen._handle_reader_key(KEY_ESCAPE)

        assert screen._handle_reader_key(KEY_DOWN) is False
        assert screen._menu_mode is False

    def test_a_bar_with_no_lists_never_has_one_open(self, screen: _PageTurningScreen) -> None:
        assert screen._has_list_open() is False


class TestTheMenuKeysUnderADropdown:
    """A screen with a dropdown gives the keys to its open list, else to the bar."""

    def test_with_no_list_open_the_bar_has_the_keys(self) -> None:
        screen = _StubDropdownScreen()
        with (
            patch.object(nav_module, "update_focus_in_list"),
            patch.object(nav_module, "clear_focus_in_list"),
        ):
            screen._enter_menu_mode()
            assert screen._has_list_open() is False
            assert screen._handle_menu_key(KEY_ENTER) is True
        _bar_buttons(screen)[0].trigger_action.assert_called_once_with()

    def test_an_open_list_has_them(self) -> None:
        screen = _StubDropdownScreen()
        with (
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            screen._enter_dropdown_nav()
            assert screen._has_list_open() is True
            assert screen._handle_menu_key(KEY_DOWN) is True
            assert screen._handle_menu_key(KEY_ENTER) is True
        first, second = screen._items
        second.trigger_action.assert_called_once_with()
        first.trigger_action.assert_not_called()
        _bar_buttons(screen)[0].trigger_action.assert_not_called()

    def test_a_list_that_does_not_wrap_stops_at_its_ends(self) -> None:
        screen = _PagedDropdownScreen(2)
        screen._dropdown_wraps = False
        with (
            patch.object(nav_module, "draw_focus_highlight") as draw,
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            screen._enter_dropdown_nav()
            draw.reset_mock()
            assert screen._handle_menu_key(KEY_UP) is True  # taken, though nothing moves
            assert screen._dropdown_focused_idx == 0
            draw.assert_not_called()
            screen._handle_menu_key(KEY_DOWN)
            assert screen._handle_menu_key(KEY_DOWN) is True
            assert screen._dropdown_focused_idx == 1

    def test_a_list_that_wraps_goes_round(self) -> None:
        screen = _StubDropdownScreen()
        with (
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight"),
        ):
            screen._enter_dropdown_nav()
            screen._handle_menu_key(KEY_UP)
            assert screen._dropdown_focused_idx == 1
            screen._handle_menu_key(KEY_DOWN)
            assert screen._dropdown_focused_idx == 0


class TestNavExit:
    def test_a_screen_must_clear_its_own_focus(self) -> None:
        with pytest.raises(NotImplementedError):
            NavExitMixin().exit_nav_focus()


class TestSetMenuButtons:
    """A bar whose buttons change with the layout keeps each index on its button."""

    @staticmethod
    def _screen() -> tuple[_StubScreen, list[MagicMock]]:
        icon, back, collapse, pics, quit_ = (MagicMock() for _ in range(5))
        buttons = [icon, back, collapse, pics, quit_]
        return _StubScreen(buttons, default_focus_idx=1), buttons

    def test_an_added_button_shifts_the_indexes_after_it(self) -> None:
        screen, (icon, back, collapse, pics, quit_) = self._screen()
        search = MagicMock()
        screen._last_used_btn_idx = 3  # pics
        screen._set_menu_buttons([icon, back, collapse, search, pics, quit_])
        assert screen._menu_buttons[screen._default_btn_idx] is back
        assert screen._menu_buttons[screen._last_used_btn_idx] is pics

    def test_an_index_on_a_removed_button_falls_back_to_the_default(self) -> None:
        screen, (icon, back, collapse, pics, quit_) = self._screen()
        search = MagicMock()
        screen._set_menu_buttons([icon, back, collapse, search, pics, quit_])
        screen._last_used_btn_idx = screen._focused_btn_idx = 3  # search
        screen._set_menu_buttons([icon, back, collapse, pics, quit_])
        assert screen._last_used_btn_idx == screen._focused_btn_idx == 1  # back

    def test_in_the_menu_the_ring_is_redrawn_on_its_button(self) -> None:
        screen, (icon, back, collapse, pics, quit_) = self._screen()
        search = MagicMock()
        with (
            patch.object(nav_module, "update_focus_in_list") as update,
            patch.object(nav_module, "clear_focus_in_list") as clear,
        ):
            screen._enter_menu_mode()
            screen._focused_btn_idx = 3  # pics
            update.reset_mock()
            new_buttons = [icon, back, collapse, search, pics, quit_]
            screen._set_menu_buttons(new_buttons)
        clear.assert_called_once()
        update.assert_called_once_with(new_buttons, 4, nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)

    def test_out_of_the_menu_no_ring_is_drawn(self) -> None:
        screen, buttons = self._screen()
        with (
            patch.object(nav_module, "update_focus_in_list") as update,
            patch.object(nav_module, "clear_focus_in_list") as clear,
        ):
            screen._set_menu_buttons([*buttons, MagicMock()])
        update.assert_not_called()
        clear.assert_not_called()
