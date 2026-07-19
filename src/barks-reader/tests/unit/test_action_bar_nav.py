# ruff: noqa: SLF001

from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.ui import reader_keyboard_nav as nav_module
from barks_reader.ui.reader_keyboard_nav import (
    _FOCUS_BINDING_ATTR,
    ActionBarNavMixin,
    clear_focus_highlight,
    draw_focus_highlight,
)


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

    def test_touch_clears_flag(self) -> None:
        screen = _StubScreen([MagicMock(), MagicMock()])
        screen._menu_action_by_keyboard = True

        screen._clear_menu_on_touch()

        assert screen._menu_action_by_keyboard is False


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
