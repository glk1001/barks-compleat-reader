# ruff: noqa: SLF001

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_ESCAPE, KEY_NUMPAD_ENTER, KEY_UP
from barks_reader.ui import settings_keyboard_nav as nav_module
from barks_reader.ui.settings_keyboard_nav import SettingsKeyboardNav

_IDX_2 = 2


def _make_item() -> MagicMock:
    """Return a mock SettingItem; isinstance checks are patched at the call site."""
    item = MagicMock()
    item.parent = None
    return item


def _make_nav(items: list[MagicMock]) -> SettingsKeyboardNav:
    panel = MagicMock()
    # Kivy stores children last-added-first, so reverse the display order.
    panel.children = list(reversed(items))
    settings = MagicMock()
    settings.interface.content.current_panel = panel
    return SettingsKeyboardNav(settings)


def _patch_settingitem(items: list[MagicMock]):  # noqa: ANN202
    """Patch isinstance(..., SettingItem) to treat our mocks as SettingItems."""
    real_isinstance = isinstance

    def fake_isinstance(obj: object, cls: type) -> bool:
        if cls is nav_module.SettingItem and obj in items:
            return True
        return real_isinstance(obj, cls)

    return patch.object(nav_module, "isinstance", fake_isinstance, create=True)


class TestHandleKey:
    def test_down_moves_focus_forward_and_stops_at_the_last_item(self) -> None:
        """A list stops at its ends: wrapped, Down past the last item lost the place."""
        items = [_make_item(), _make_item(), _make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            assert nav.handle_key(KEY_DOWN) is True
            assert nav._focused_idx == 1
            assert nav.handle_key(KEY_DOWN) is True
            assert nav._focused_idx == _IDX_2
            assert nav.handle_key(KEY_DOWN) is True
            assert nav._focused_idx == _IDX_2

    def test_up_moves_focus_backward_and_stops_at_the_first_item(self) -> None:
        items = [_make_item(), _make_item(), _make_item()]
        nav = _make_nav(items)
        nav._focused_idx = _IDX_2

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            assert nav.handle_key(KEY_UP) is True
            assert nav._focused_idx == 1
            assert nav.handle_key(KEY_UP) is True
            assert nav._focused_idx == 0
            assert nav.handle_key(KEY_UP) is True
            assert nav._focused_idx == 0

    def test_enter_dispatches_on_release(self) -> None:
        items = [_make_item(), _make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            nav.handle_key(KEY_DOWN)  # focus idx 1
            assert nav.handle_key(KEY_ENTER) is True

        items[1].dispatch.assert_called_once_with("on_release")

    def test_numpad_enter_also_activates(self) -> None:
        items = [_make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items):
            assert nav.handle_key(KEY_NUMPAD_ENTER) is True

        items[0].dispatch.assert_called_once_with("on_release")

    def test_escape_returns_false(self) -> None:
        items = [_make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items):
            assert nav.handle_key(KEY_ESCAPE) is False

    def test_unknown_key_returns_false(self) -> None:
        items = [_make_item()]
        nav = _make_nav(items)

        with _patch_settingitem(items):
            assert nav.handle_key(999) is False

    def test_empty_panel_returns_false(self) -> None:
        nav = _make_nav([])
        assert nav.handle_key(KEY_DOWN) is False
        assert nav.handle_key(KEY_ENTER) is False


class TestReset:
    def test_reset_clears_focus_and_resets_index(self) -> None:
        items = [_make_item(), _make_item()]
        nav = _make_nav(items)

        with (
            _patch_settingitem(items),
            patch.object(nav_module, "draw_focus_highlight"),
            patch.object(nav_module, "clear_focus_highlight") as mock_clear,
        ):
            nav.handle_key(KEY_DOWN)  # focus idx 1
            nav.reset()

        mock_clear.assert_called_once()
        assert nav._focused_idx == 0
        assert nav._last_focused_item is None


class TestBooleanToggle:
    def test_enter_on_boolean_flips_value(self) -> None:
        bool_item = MagicMock()
        bool_item.values = ["0", "1"]
        bool_item.value = "0"
        bool_item.parent = None
        nav = _make_nav([bool_item])

        # Treat the mock as both SettingItem and SettingBoolean.
        real_isinstance = isinstance

        def fake_isinstance(obj: object, cls: type) -> bool:
            if obj is bool_item and cls in (nav_module.SettingItem, nav_module.SettingBoolean):
                return True
            return real_isinstance(obj, cls)

        with (
            patch.object(nav_module, "isinstance", fake_isinstance, create=True),
            patch.object(nav_module, "draw_focus_highlight"),
        ):
            assert nav.handle_key(KEY_ENTER) is True
            assert bool_item.value == "1"
            assert nav.handle_key(KEY_ENTER) is True
            assert bool_item.value == "0"

        # Should not have dispatched on_release for booleans.
        bool_item.dispatch.assert_not_called()


class TestOpeningAPopup:
    def test_enter_opens_an_item_s_popup_and_leaves_its_keys_to_it(self) -> None:
        """The popup is on the shared frame and takes its own keys: the list holds no state."""
        item = _make_item()
        nav = _make_nav([item])

        with _patch_settingitem([item]), patch.object(nav_module, "draw_focus_highlight"):
            assert nav.handle_key(KEY_ENTER) is True

        item.dispatch.assert_called_once_with("on_release")


def _settings_with_content(content: SimpleNamespace) -> MagicMock:
    settings = MagicMock()
    settings.interface.content = content
    return settings


class TestFindCurrentPanel:
    def test_settings_with_no_interface_consume_no_keys(self) -> None:
        nav = SettingsKeyboardNav(MagicMock(spec=[]))
        assert nav.handle_key(KEY_DOWN) is False
        assert nav.handle_key(KEY_ENTER) is False

    def test_without_a_current_panel_the_child_holding_items_is_used(self) -> None:
        items = [_make_item(), _make_item()]
        empty_child = SimpleNamespace(children=[MagicMock()])
        panel = SimpleNamespace(children=list(reversed(items)))
        content = SimpleNamespace(current_panel=None, children=[empty_child, panel])
        nav = SettingsKeyboardNav(_settings_with_content(content))

        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight") as draw:
            assert nav.handle_key(KEY_DOWN) is True

        draw.assert_called_once_with(items[1], nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)

    def test_without_a_current_panel_or_any_items_no_keys_are_consumed(self) -> None:
        content = SimpleNamespace(
            current_panel=None, children=[SimpleNamespace(children=[MagicMock()])]
        )
        nav = SettingsKeyboardNav(_settings_with_content(content))

        assert nav.handle_key(KEY_DOWN) is False


class TestBooleanToggleEdges:
    def test_a_boolean_with_fewer_than_two_values_is_left_alone(self) -> None:
        item = MagicMock(values=["1"], value="1")
        nav_module._toggle_boolean(item)
        assert item.value == "1"


class TestBlurAndRefocus:
    """The X takes the ring and gives it back; the item focused stays the same."""

    def test_blur_clears_the_ring_and_refocus_redraws_the_same_item(self) -> None:
        items = [_make_item(), _make_item()]
        nav = _make_nav(items)
        with (
            _patch_settingitem(items),
            patch.object(nav_module, "draw_focus_highlight") as draw,
            patch.object(nav_module, "clear_focus_highlight") as clear,
        ):
            nav.handle_key(KEY_DOWN)  # the second item
            nav.blur()
            clear.assert_called_with(items[1], nav_module.MENU_FOCUS_HIGHLIGHT_GROUP)
            nav.refocus()
            assert draw.call_args.args[0] is items[1]
            assert nav._focused_idx == 1


class TestFocusFirst:
    def test_the_first_item_is_shown_focused_and_down_reaches_the_second(self) -> None:
        items = [_make_item(), _make_item(), _make_item()]
        nav = _make_nav(items)
        with (
            _patch_settingitem(items),
            patch.object(nav_module, "draw_focus_highlight") as draw,
        ):
            nav.focus_first()
            assert draw.call_args.args[0] is items[0]
            nav.handle_key(KEY_DOWN)
            assert draw.call_args.args[0] is items[1]

    def test_the_panel_opens_from_its_top_title_row_and_all(self) -> None:
        """The panel keeps its scroll between openings.

        A scroll to the first item alone left the title row above the view, and the
        close X over the first item.
        """
        items = [_make_item(), _make_item()]
        scroll = MagicMock(spec=nav_module.ScrollView)
        scroll.scroll_y = 0.3
        panel = MagicMock()  # the item's layout, inside the scroll view
        panel.parent = scroll  # (not Mock's `parent=` kwarg, which is its mock parent)
        items[0].parent = panel
        nav = _make_nav(items)
        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            nav.focus_first()
        assert scroll.scroll_y == 1.0
        scroll.scroll_to.assert_not_called()  # its animation would write over the top

    def test_up_back_onto_the_first_item_shows_the_panel_s_top_too(self) -> None:
        """Walked to the bottom and back, the title row was left above the view."""
        items = [_make_item(), _make_item()]
        scroll = MagicMock(spec=nav_module.ScrollView)
        for item in items:
            panel = MagicMock()
            panel.parent = scroll
            item.parent = panel
        nav = _make_nav(items)
        with _patch_settingitem(items), patch.object(nav_module, "draw_focus_highlight"):
            nav.handle_key(KEY_DOWN)
            scroll.scroll_to.assert_called_once_with(items[1])
            scroll.scroll_y = 0.3
            nav.handle_key(KEY_UP)
        assert scroll.scroll_y == 1.0
        scroll.scroll_to.assert_called_once()  # no scroll to the first item

    def test_an_empty_panel_has_nothing_to_focus(self) -> None:
        nav = _make_nav([])
        with patch.object(nav_module, "draw_focus_highlight") as draw:
            nav.focus_first()
        draw.assert_not_called()
