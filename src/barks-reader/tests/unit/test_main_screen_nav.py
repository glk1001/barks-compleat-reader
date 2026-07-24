# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import main_screen_nav as nav_module
from barks_reader.ui.main_screen_nav import MainScreenNavigation
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
)
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.tree_view_nodes import ButtonTreeViewNode, TitleTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


class FakeTrigger:
    """A restartable one-shot timer that tests fire manually."""

    def __init__(self) -> None:
        self._callback: Callable[[float], None] | None = None
        self.scheduled = False
        self.cancel_count = 0

    def set_callback(self, callback: Callable[[float], None]) -> None:
        self._callback = callback

    def __call__(self) -> None:
        self.scheduled = True

    def cancel(self) -> None:
        self.scheduled = False
        self.cancel_count += 1

    def fire(self) -> None:
        assert self._callback is not None
        self.scheduled = False
        self._callback(0.0)


@pytest.fixture
def fake_trigger() -> FakeTrigger:
    return FakeTrigger()


@pytest.fixture
def fake_time() -> list[float]:
    return [0.0]


@pytest.fixture
def screen_mocks() -> dict[str, MagicMock]:
    return {
        "tree_view": MagicMock(),
        "bottom_title_view": MagicMock(),
        "fun_image_view": MagicMock(),
        "main_index": MagicMock(),
        "speech_index": MagicMock(),
        "names_index": MagicMock(),
        "locations_index": MagicMock(),
        "statistics": MagicMock(),
        "history": MagicMock(),
        "search": MagicMock(),
    }


@pytest.fixture
def screens(screen_mocks: dict[str, MagicMock]) -> ScreenBundle:
    return ScreenBundle(**screen_mocks)


@pytest.fixture
def nav(
    screens: ScreenBundle, fake_trigger: FakeTrigger, fake_time: list[float]
) -> Generator[MainScreenNavigation]:
    enter_menu_mode = MagicMock()
    handle_menu_key = MagicMock(return_value=True)
    is_in_menu_mode = MagicMock(return_value=False)

    def trigger_factory(callback: Callable[[float], None], _timeout: float) -> FakeTrigger:
        fake_trigger.set_callback(callback)
        return fake_trigger

    with (
        patch.object(nav_module, "draw_focus_highlight"),
        patch.object(nav_module, "clear_focus_highlight"),
    ):
        n = MainScreenNavigation(
            screens=screens,
            tree_view_manager=MagicMock(),
            bottom_base_view_screen=MagicMock(),
            enter_menu_mode=enter_menu_mode,
            handle_menu_key=handle_menu_key,
            is_in_menu_mode=is_in_menu_mode,
            trigger_factory=trigger_factory,
            now_fn=lambda: fake_time[0],
        )
        yield n


class TestHandleKey:
    def test_delegates_to_menu_when_in_menu_mode(self, nav: MainScreenNavigation) -> None:
        nav._is_in_menu_mode.return_value = True  # ty: ignore[unresolved-attribute]
        nav._handle_menu_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav.handle_key(KEY_ENTER) is True
        nav._handle_menu_key.assert_called_once_with(KEY_ENTER)  # ty: ignore[unresolved-attribute]

    def test_delegates_to_tree_key_by_default(self, nav: MainScreenNavigation) -> None:
        result = nav.handle_key(KEY_ESCAPE)

        assert result is True
        nav._enter_menu_mode.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_delegates_to_bottom_key_when_in_bottom_focus(self, nav: MainScreenNavigation) -> None:
        # Set up: no visible screens so bottom key falls through to fun/title checks
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        # Escape should exit bottom focus
        result = nav.handle_key(KEY_ESCAPE)
        assert result is True
        assert nav._focus_region.name == "TREE"


class TestHandleTreeKey:
    def test_escape_enters_menu_mode(self, nav: MainScreenNavigation) -> None:
        assert nav._handle_tree_key(KEY_ESCAPE) is True
        nav._enter_menu_mode.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_alt_escape_enters_menu_mode(self, nav: MainScreenNavigation) -> None:
        from barks_reader.ui.reader_keyboard_nav import set_alt_escape_key  # noqa: PLC0415

        backspace = 8
        set_alt_escape_key(backspace)
        try:
            assert nav._handle_tree_key(backspace) is True
            nav._enter_menu_mode.assert_called_once()  # ty: ignore[unresolved-attribute]
        finally:
            set_alt_escape_key(0)

    def test_tab_is_unhandled(self, nav: MainScreenNavigation) -> None:
        # Tab handling was removed; Enter enters the bottom zone instead.
        assert nav._handle_tree_key(KEY_TAB) is False

    def test_up_moves_tree(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_visible_nodes.return_value = [MagicMock(), MagicMock()]  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        assert nav._handle_tree_key(KEY_UP) is True
        nav._tree_view_screen.select_node.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_down_moves_tree(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_visible_nodes.return_value = [MagicMock(), MagicMock()]  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        assert nav._handle_tree_key(KEY_DOWN) is True
        nav._tree_view_screen.select_node.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_left_collapses(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        assert nav._handle_tree_key(KEY_LEFT) is True

    def test_enter_activates(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        assert nav._handle_tree_key(KEY_ENTER) is True

    def test_numpad_enter_activates(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        assert nav._handle_tree_key(KEY_NUMPAD_ENTER) is True

    def test_right_enters_bottom_focus_when_title_visible(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._handle_tree_key(KEY_RIGHT) is True

        assert nav.is_in_bottom_focus
        nav._bottom_title_view_screen.enter_nav_focus.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_right_with_no_bottom_screen_stays_in_tree(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._handle_tree_key(KEY_RIGHT) is True

        assert not nav.is_in_bottom_focus

    def test_unhandled_key_returns_false(self, nav: MainScreenNavigation) -> None:
        assert nav._handle_tree_key(999) is False


class TestHandleBottomKey:
    def test_tab_no_longer_exits_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM
        # No active nav screen
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False

        # Tab is inert now; only Escape backs out of the bottom zone.
        assert nav._handle_bottom_key(KEY_TAB) is False
        assert nav.is_in_bottom_focus

    def test_escape_exits_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_ESCAPE) is True
        assert not nav.is_in_bottom_focus

    def test_delegates_to_nav_screen(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = True
        nav._main_index_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._handle_bottom_key(KEY_DOWN) is True
        nav._main_index_screen.handle_key.assert_called_once_with(KEY_DOWN)  # ty: ignore[unresolved-attribute]

    def test_tab_on_nav_screen_is_delegated(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)
        nav._main_index_screen.is_visible = True
        nav._main_index_screen.handle_key.return_value = False  # ty: ignore[unresolved-attribute]
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        # Tab is passed to the active screen like any other key, not intercepted.
        assert nav._handle_bottom_key(KEY_TAB) is False
        nav._main_index_screen.handle_key.assert_called_once_with(KEY_TAB)  # ty: ignore[unresolved-attribute]
        nav._main_index_screen.exit_nav_focus.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_fun_view_keys_delegate_to_screen(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False
        nav._fun_image_view_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav._handle_bottom_key(KEY_LEFT) is True
        nav._fun_image_view_screen.handle_key.assert_called_once_with(KEY_LEFT)  # ty: ignore[unresolved-attribute]

    def test_title_view_keys_delegate_to_screen(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav._handle_bottom_key(KEY_ENTER) is True
        nav._bottom_title_view_screen.handle_key.assert_called_once_with(KEY_ENTER)  # ty: ignore[unresolved-attribute]

    def test_title_view_escape_is_delegated_not_intercepted(
        self, nav: MainScreenNavigation
    ) -> None:
        """Escape goes to the title screen (which exits via its exit-request callback)."""
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav._handle_bottom_key(KEY_ESCAPE) is True
        nav._bottom_title_view_screen.handle_key.assert_called_once_with(KEY_ESCAPE)  # ty: ignore[unresolved-attribute]

    def test_title_view_lazily_enters_nav_focus(self, nav: MainScreenNavigation) -> None:
        """The fun view's goto-title lands here with BOTTOM focus but no nav entry yet."""
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = False  # ty: ignore[invalid-assignment]
        nav._bottom_title_view_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav._handle_bottom_key(KEY_DOWN) is True
        nav._bottom_title_view_screen.enter_nav_focus.assert_called_once_with(  # ty: ignore[unresolved-attribute]
            nav.exit_bottom_focus
        )
        nav._bottom_title_view_screen.handle_key.assert_called_once_with(KEY_DOWN)  # ty: ignore[unresolved-attribute]

    def test_title_view_not_reentered_when_nav_active(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = True  # ty: ignore[invalid-assignment]

        nav._handle_bottom_key(KEY_DOWN)

        nav._bottom_title_view_screen.enter_nav_focus.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_fun_view_takes_precedence_over_title_view(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = True
        nav._fun_image_view_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav._handle_bottom_key(KEY_LEFT) is True
        nav._fun_image_view_screen.handle_key.assert_called_once_with(KEY_LEFT)  # ty: ignore[unresolved-attribute]
        nav._bottom_title_view_screen.handle_key.assert_not_called()  # ty: ignore[unresolved-attribute]


class TestTreeNavMove:
    def test_no_visible_nodes(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_visible_nodes.return_value = []  # ty: ignore[unresolved-attribute]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_no_selection_delta_positive(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[0])  # ty: ignore[unresolved-attribute]

    def test_no_selection_delta_negative(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        nav._tree_nav_move(-1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[2])  # ty: ignore[unresolved-attribute]

    def test_move_down_from_middle(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = nodes[1]  # ty: ignore[unresolved-attribute]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[2])  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.scroll_to_node.assert_called_with(nodes[2])  # ty: ignore[unresolved-attribute]

    def test_clamps_at_end(self, nav: MainScreenNavigation) -> None:
        nodes = [MagicMock(), MagicMock()]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = nodes[1]  # ty: ignore[unresolved-attribute]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(nodes[1])  # ty: ignore[unresolved-attribute]

    def test_renders_title_node_immediately_on_discrete_press(
        self, nav: MainScreenNavigation, fake_trigger: FakeTrigger
    ) -> None:
        title_node = MagicMock(spec=TitleTreeViewNode)
        nav._tree_view_screen.get_visible_nodes.return_value = [title_node]  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        nav._tree_nav_move(1)

        nav._tree_view_screen.select_node.assert_called_with(title_node)  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.scroll_to_node.assert_called_with(title_node)  # ty: ignore[unresolved-attribute]
        nav._tree_view_manager.render_title_node.assert_called_once_with(title_node)  # ty: ignore[unresolved-attribute]
        assert not fake_trigger.scheduled


class TestTitleRenderDebounce:
    @staticmethod
    def _setup_title_nodes(nav: MainScreenNavigation, count: int) -> list[MagicMock]:
        """Set up title nodes with selection tracked through select_node calls."""
        nodes = [MagicMock(spec=TitleTreeViewNode) for _ in range(count)]
        nav._tree_view_screen.get_visible_nodes.return_value = nodes  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        def track_selection(node: MagicMock) -> None:
            nav._tree_view_screen.get_selected_node.return_value = node  # ty: ignore[unresolved-attribute]

        nav._tree_view_screen.select_node.side_effect = track_selection  # ty: ignore[unresolved-attribute]
        return nodes

    def test_rapid_press_defers_render(
        self, nav: MainScreenNavigation, fake_trigger: FakeTrigger, fake_time: list[float]
    ) -> None:
        nodes = self._setup_title_nodes(nav, 3)

        nav._tree_nav_move(1)  # Leading edge: renders nodes[0] immediately.
        fake_time[0] = 0.05
        nav._tree_nav_move(1)  # Rapid: render deferred.

        nav._tree_view_manager.render_title_node.assert_called_once_with(nodes[0])  # ty: ignore[unresolved-attribute]
        assert fake_trigger.scheduled
        assert nav._pending_title_node is nodes[1]

    def test_each_rapid_press_restarts_trigger(
        self, nav: MainScreenNavigation, fake_trigger: FakeTrigger, fake_time: list[float]
    ) -> None:
        self._setup_title_nodes(nav, 4)

        nav._tree_nav_move(1)
        for i in range(3):
            fake_time[0] += 0.05
            nav._tree_nav_move(1)
            assert fake_trigger.cancel_count == i + 1
            assert fake_trigger.scheduled

    def test_trigger_fire_renders_pending_node(
        self, nav: MainScreenNavigation, fake_trigger: FakeTrigger, fake_time: list[float]
    ) -> None:
        nodes = self._setup_title_nodes(nav, 3)

        nav._tree_nav_move(1)
        fake_time[0] = 0.05
        nav._tree_nav_move(1)
        fake_trigger.fire()

        nav._tree_view_manager.render_title_node.assert_called_with(nodes[1])  # ty: ignore[unresolved-attribute]
        assert nav._pending_title_node is None

    def test_trigger_fire_skips_stale_selection(
        self, nav: MainScreenNavigation, fake_trigger: FakeTrigger, fake_time: list[float]
    ) -> None:
        nodes = self._setup_title_nodes(nav, 3)

        nav._tree_nav_move(1)
        fake_time[0] = 0.05
        nav._tree_nav_move(1)
        # Selection moved elsewhere (e.g. mouse click) before the trigger fired.
        nav._tree_view_screen.get_selected_node.return_value = MagicMock()  # ty: ignore[unresolved-attribute]
        fake_trigger.fire()

        nav._tree_view_manager.render_title_node.assert_called_once_with(nodes[0])  # ty: ignore[unresolved-attribute]
        assert nav._pending_title_node is None

    def test_enter_cancels_pending_render(
        self, nav: MainScreenNavigation, fake_trigger: FakeTrigger, fake_time: list[float]
    ) -> None:
        nodes = self._setup_title_nodes(nav, 3)

        nav._tree_nav_move(1)
        fake_time[0] = 0.05
        nav._tree_nav_move(1)
        nav._tree_nav_activate()

        assert nav._pending_title_node is None
        assert not fake_trigger.scheduled
        # The bottom view was behind (a debounced render was pending), so Enter
        # renders the pending node synchronously rather than leaving it stale.
        nav._tree_view_manager.render_title_node.assert_called_with(nodes[1], scroll_to=True)  # ty: ignore[unresolved-attribute]
        nav._tree_view_manager.activate_node.assert_not_called()  # ty: ignore[unresolved-attribute]


class TestTreeNavActivate:
    def test_no_selection_does_nothing(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        nav._tree_nav_activate()

        nav._tree_view_manager.activate_node.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_title_node_enters_panel_focus_at_portal(self, nav: MainScreenNavigation) -> None:
        selected = MagicMock(spec=TitleTreeViewNode)
        nav._tree_view_screen.get_selected_node.return_value = selected  # ty: ignore[unresolved-attribute]
        nav._bottom_title_view_screen.is_visible = True

        with patch.object(nav_module, "Clock") as mock_clock:
            nav._tree_nav_activate()
            # Focus entry is deferred a frame; run the scheduled callback.
            mock_clock.schedule_once.call_args[0][0](0)

        # The bottom title view already shows this title (no pending render), so Enter
        # does not re-render it — that avoided the jarring top-view re-roll flash.
        nav._tree_view_manager.render_title_node.assert_not_called()  # ty: ignore[unresolved-attribute]
        nav._tree_view_manager.activate_node.assert_not_called()  # ty: ignore[unresolved-attribute]
        # Enter lands on the portal (read action) rather than launching the reader.
        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_called_once()  # ty: ignore[unresolved-attribute]
        assert nav.is_in_bottom_focus

    def test_index_node_enters_bottom_focus(self, nav: MainScreenNavigation) -> None:
        node = MagicMock()
        nav._main_index_screen.treeview_index_node = node
        nav._speech_index_screen.treeview_index_node = MagicMock()
        nav._names_index_screen.treeview_index_node = MagicMock()
        nav._locations_index_screen.treeview_index_node = MagicMock()
        # noinspection PyPropertyAccess
        nav._tree_view_manager.speech_words_node = MagicMock()  # ty: ignore[invalid-assignment]
        # noinspection PyPropertyAccess
        nav._tree_view_manager.statistics_node = MagicMock()  # ty: ignore[invalid-assignment]
        nav._tree_view_screen.get_selected_node.return_value = node  # ty: ignore[unresolved-attribute]
        nav._main_index_screen.is_visible = True

        with patch.object(nav_module, "Clock"):
            nav._tree_nav_activate()

        # Should have entered bottom focus since screen is visible
        assert nav.is_in_bottom_focus

    def test_history_node_enters_bottom_focus_when_visible(self, nav: MainScreenNavigation) -> None:
        history_node = MagicMock()
        nav._main_index_screen.treeview_index_node = MagicMock()
        nav._speech_index_screen.treeview_index_node = MagicMock()
        nav._names_index_screen.treeview_index_node = MagicMock()
        nav._locations_index_screen.treeview_index_node = MagicMock()
        # noinspection PyPropertyAccess
        nav._tree_view_manager.speech_words_node = MagicMock()  # ty: ignore[invalid-assignment]
        # noinspection PyPropertyAccess
        nav._tree_view_manager.statistics_node = MagicMock()  # ty: ignore[invalid-assignment]
        # noinspection PyPropertyAccess
        nav._tree_view_manager.history_node = history_node  # ty: ignore[invalid-assignment]
        nav._tree_view_screen.get_selected_node.return_value = history_node  # ty: ignore[unresolved-attribute]
        nav._history_screen.is_visible = True

        with patch.object(nav_module, "Clock"):
            nav._tree_nav_activate()

        assert nav.is_in_bottom_focus

    def test_history_node_activates_then_enters_bottom_focus_when_hidden(
        self, nav: MainScreenNavigation
    ) -> None:
        history_node = MagicMock()
        nav._main_index_screen.treeview_index_node = MagicMock()
        nav._speech_index_screen.treeview_index_node = MagicMock()
        nav._names_index_screen.treeview_index_node = MagicMock()
        nav._locations_index_screen.treeview_index_node = MagicMock()
        # noinspection PyPropertyAccess
        nav._tree_view_manager.speech_words_node = MagicMock()  # ty: ignore[invalid-assignment]
        # noinspection PyPropertyAccess
        nav._tree_view_manager.statistics_node = MagicMock()  # ty: ignore[invalid-assignment]
        # noinspection PyPropertyAccess
        nav._tree_view_manager.history_node = history_node  # ty: ignore[invalid-assignment]
        nav._tree_view_screen.get_selected_node.return_value = history_node  # ty: ignore[unresolved-attribute]
        nav._history_screen.is_visible = False

        with patch.object(nav_module, "Clock") as mock_clock:
            nav._tree_nav_activate()

        nav._tree_view_manager.activate_node.assert_called_with(history_node)  # ty: ignore[unresolved-attribute]
        mock_clock.schedule_once.assert_called_once()

    def test_button_node_toggles_in_place(self, nav: MainScreenNavigation) -> None:
        """Enter on a closed parent opens it but keeps selection on it (mouse parity)."""
        selected = MagicMock(spec=ButtonTreeViewNode)
        selected.is_open = False
        selected.nodes = [MagicMock()]
        nav._tree_view_screen.get_selected_node.return_value = selected  # ty: ignore[unresolved-attribute]
        nav._main_index_screen.treeview_index_node = MagicMock()
        nav._speech_index_screen.treeview_index_node = MagicMock()
        nav._names_index_screen.treeview_index_node = MagicMock()
        nav._locations_index_screen.treeview_index_node = MagicMock()
        # noinspection PyPropertyAccess
        nav._tree_view_manager.speech_words_node = MagicMock()  # ty: ignore[invalid-assignment]
        # noinspection PyPropertyAccess
        nav._tree_view_manager.statistics_node = MagicMock()  # ty: ignore[invalid-assignment]
        nav._search_screen.is_visible = False

        with patch.object(nav_module, "Clock") as mock_clock:
            nav._tree_nav_activate()

        nav._tree_view_manager.activate_node.assert_called_with(selected)  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.select_node.assert_not_called()  # ty: ignore[unresolved-attribute]
        mock_clock.schedule_once.assert_not_called()


class TestTreeNavCollapseToParent:
    def test_no_selection(self, nav: MainScreenNavigation) -> None:
        nav._tree_view_screen.get_selected_node.return_value = None  # ty: ignore[unresolved-attribute]

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_manager.activate_node.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_open_button_node_collapses(self, nav: MainScreenNavigation) -> None:
        selected = MagicMock(spec=ButtonTreeViewNode)
        selected.is_open = True
        selected.nodes = [MagicMock()]
        nav._tree_view_screen.get_selected_node.return_value = selected  # ty: ignore[unresolved-attribute]

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_manager.activate_node.assert_called_with(selected)  # ty: ignore[unresolved-attribute]

    def test_child_node_selects_parent(self, nav: MainScreenNavigation) -> None:
        parent = MagicMock(spec=ButtonTreeViewNode)
        parent.is_open = True
        selected = MagicMock()
        selected.parent_node = parent
        nav._tree_view_screen.get_selected_node.return_value = selected  # ty: ignore[unresolved-attribute]

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_manager.activate_node.assert_called_with(parent)  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.scroll_to_node.assert_called_with(parent)  # ty: ignore[unresolved-attribute]

    def test_child_with_closed_parent_selects_without_activating(
        self, nav: MainScreenNavigation
    ) -> None:
        parent = MagicMock(spec=ButtonTreeViewNode)
        parent.is_open = False
        selected = MagicMock()
        selected.parent_node = parent
        nav._tree_view_screen.get_selected_node.return_value = selected  # ty: ignore[unresolved-attribute]

        nav._tree_nav_collapse_to_parent()

        nav._tree_view_screen.select_node.assert_called_with(parent)  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.scroll_to_node.assert_called_with(parent)  # ty: ignore[unresolved-attribute]


class TestFocusSaveRestore:
    def test_save_and_restore_tree(self, nav: MainScreenNavigation) -> None:
        nav.save_focus_before_reader()
        nav.restore_focus_after_reader()

        assert not nav.is_in_bottom_focus
        assert nav._focus_region_before_reader is None

    def test_save_and_restore_bottom(self, nav: MainScreenNavigation) -> None:
        # Enter bottom focus
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav.enter_bottom_focus()

        nav.save_focus_before_reader()
        # Simulate leaving bottom during comic
        nav.exit_bottom_focus()

        nav.restore_focus_after_reader()
        assert nav.is_in_bottom_focus


class TestEnterBottomFocus:
    def test_nothing_visible_stays_in_tree(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.enter_bottom_focus()

        assert not nav.is_in_bottom_focus

    def test_nav_screen_gets_enter_nav_focus(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._main_index_screen.is_visible = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.enter_bottom_focus()

        nav._main_index_screen.enter_nav_focus.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_title_view_gets_enter_nav_focus(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.enter_bottom_focus()

        nav._bottom_title_view_screen.enter_nav_focus.assert_called_once_with(  # ty: ignore[unresolved-attribute]
            nav.exit_bottom_focus
        )

    def test_title_view_not_focused_when_fun_view_visible(self, nav: MainScreenNavigation) -> None:
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = True
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.enter_bottom_focus()

        nav._bottom_title_view_screen.enter_nav_focus.assert_not_called()  # ty: ignore[unresolved-attribute]


class TestExitBottomFocus:
    def test_exits_title_view_nav_focus(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        nav.exit_bottom_focus()

        nav._bottom_title_view_screen.exit_nav_focus.assert_called_once()  # ty: ignore[unresolved-attribute]


class TestGetActiveNavScreen:
    def test_returns_none_when_nothing_visible(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._get_active_nav_screen() is None

    def test_returns_first_visible(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = True
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        assert nav._get_active_nav_screen() is nav._speech_index_screen


class TestEnterBottomFocusIfIndexVisible:
    def test_search_screen_visible(self, nav: MainScreenNavigation) -> None:
        nav._search_screen.is_visible = True
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible()

        assert nav.is_in_bottom_focus
        nav._search_screen.enter_nav_focus_at_last_result.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_index_screen_visible(self, nav: MainScreenNavigation) -> None:
        nav._search_screen.is_visible = False
        nav._main_index_screen.is_visible = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._statistics_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible()

        assert nav.is_in_bottom_focus

    def test_nothing_visible_does_nothing(self, nav: MainScreenNavigation) -> None:
        nav._search_screen.is_visible = False
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible()

        assert not nav.is_in_bottom_focus

    def test_enters_focus_when_index_visible_regardless_of_prior_focus(
        self, nav: MainScreenNavigation
    ) -> None:
        """Keyboard Go Back always restores bottom focus when an index screen is visible."""
        nav._main_index_screen.is_visible = True
        nav._search_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False

        assert not nav.is_in_bottom_focus

        nav.enter_bottom_focus_if_index_visible()

        assert nav.is_in_bottom_focus

    def test_mouse_initiated_does_not_restore_search_focus(self, nav: MainScreenNavigation) -> None:
        """A mouse-driven Go Back reveals the search screen without a keyboard focus ring."""
        nav._search_screen.is_visible = True
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible(keyboard_initiated=False)

        assert not nav.is_in_bottom_focus
        nav._search_screen.enter_nav_focus_at_last_result.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_mouse_initiated_does_not_restore_index_focus(self, nav: MainScreenNavigation) -> None:
        """A mouse-driven Go Back reveals an index screen without a keyboard focus ring."""
        nav._search_screen.is_visible = False
        nav._main_index_screen.is_visible = True
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._statistics_screen.is_visible = False

        nav.enter_bottom_focus_if_index_visible(keyboard_initiated=False)

        assert not nav.is_in_bottom_focus


class TestOnBottomScreenVisibilityChanged:
    def test_exits_bottom_focus_when_no_screen_visible(self, nav: MainScreenNavigation) -> None:
        # Enter bottom focus with a visible screen.
        nav._main_index_screen.is_visible = True
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav.enter_bottom_focus()
        assert nav.is_in_bottom_focus

        # Hide all screens, then notify.
        nav._main_index_screen.is_visible = False
        nav.on_bottom_screen_visibility_changed()

        assert not nav.is_in_bottom_focus
        assert nav.was_bottom_focus_auto_exited

    def test_noop_when_in_tree_focus(self, nav: MainScreenNavigation) -> None:
        assert not nav.is_in_bottom_focus

        nav.on_bottom_screen_visibility_changed()

        assert not nav.is_in_bottom_focus
        assert not nav.was_bottom_focus_auto_exited

    def test_noop_when_screen_still_visible(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = True
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav.enter_bottom_focus()

        nav.on_bottom_screen_visibility_changed()

        assert nav.is_in_bottom_focus
        assert not nav.was_bottom_focus_auto_exited

    def test_auto_exit_flag_cleared_on_enter_bottom_focus(self, nav: MainScreenNavigation) -> None:
        # Simulate auto-exit.
        nav._main_index_screen.is_visible = True
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav.enter_bottom_focus()
        nav._main_index_screen.is_visible = False
        nav.on_bottom_screen_visibility_changed()
        assert nav.was_bottom_focus_auto_exited

        # Re-enter bottom focus — flag should clear.
        nav._main_index_screen.is_visible = True
        nav.enter_bottom_focus()

        assert nav.is_in_bottom_focus
        assert not nav.was_bottom_focus_auto_exited

    def test_auto_exit_flag_cleared_on_explicit_exit(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = True
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False
        nav.enter_bottom_focus()

        nav.exit_bottom_focus()

        assert not nav.was_bottom_focus_auto_exited


class TestTitleViewFocusHandoff:
    """Hand keyboard focus to the title portal after a nav screen goes to a title.

    Covers the index/history/search result activation and fun-view goto paths: once
    the title view replaces the nav screen, focus lands on the portal (read action).
    """

    @staticmethod
    def _in_bottom_focus(nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM

    def test_hands_off_to_portal_when_title_view_replaces_nav_screen(
        self, nav: MainScreenNavigation
    ) -> None:
        self._in_bottom_focus(nav)
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = False  # ty: ignore[invalid-assignment]
        prev = MagicMock()

        nav._handoff_focus_to_title_view(prev)

        # The old nav screen's ring is cleared; focus lands on the portal.
        prev.exit_nav_focus.assert_called_once_with()
        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_called_once()  # ty: ignore[unresolved-attribute]
        assert nav.is_in_bottom_focus

    def test_no_handoff_when_title_view_not_visible(self, nav: MainScreenNavigation) -> None:
        # Ordinary in-screen navigation: no goto happened, title view stays hidden.
        self._in_bottom_focus(nav)
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = False
        prev = MagicMock()

        nav._handoff_focus_to_title_view(prev)

        prev.exit_nav_focus.assert_not_called()
        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_no_handoff_while_fun_view_co_visible(self, nav: MainScreenNavigation) -> None:
        # The fun view keeps key precedence while co-visible with the title view.
        self._in_bottom_focus(nav)
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = False  # ty: ignore[invalid-assignment]

        nav._handoff_focus_to_title_view(None)

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_no_double_handoff_when_already_nav_active(self, nav: MainScreenNavigation) -> None:
        # A burst of keys can schedule several hand-offs; only the first takes effect.
        self._in_bottom_focus(nav)
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = True  # ty: ignore[invalid-assignment]

        nav._handoff_focus_to_title_view(MagicMock())

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_no_handoff_outside_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(1)  # TREE
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = False  # ty: ignore[invalid-assignment]

        nav._handoff_focus_to_title_view(MagicMock())

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_fun_view_path_hands_off_without_clearing_a_nav_screen(
        self, nav: MainScreenNavigation
    ) -> None:
        # The fun view has no nav-screen ring to clear, so prev is None.
        self._in_bottom_focus(nav)
        nav._fun_image_view_screen.is_visible = False
        nav._bottom_title_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_nav_active = False  # ty: ignore[invalid-assignment]

        nav._handoff_focus_to_title_view(None)

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_nav_screen_key_schedules_handoff(self, nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = True
        nav._main_index_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

        with patch.object(nav_module, "Clock") as mock_clock:
            assert nav._handle_bottom_key(KEY_ENTER) is True
            # Run the deferred hand-off as if a title goto swapped the index out.
            nav._main_index_screen.is_visible = False
            nav._bottom_title_view_screen.is_visible = True
            nav._bottom_title_view_screen.is_nav_active = False  # ty: ignore[invalid-assignment]
            nav._fun_image_view_screen.is_visible = False
            self._in_bottom_focus(nav)
            mock_clock.schedule_once.call_args[0][0](0)

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_called_once()  # ty: ignore[unresolved-attribute]


class TestWikiGotoTitleFocus:
    """The wiki's "Goto Title" button lands focus on the portal, when in bottom focus.

    A plain wiki close restores bottom focus onto the "Goto wiki page" button before
    this runs; choosing a comic overrides that to the portal, but only in a keyboard
    (bottom-focus) context.
    """

    def test_forces_portal_when_in_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM (restored by close)
        nav._bottom_title_view_screen.is_visible = True

        with patch.object(nav_module, "Clock") as mock_clock:
            nav.focus_title_view_portal_after_wiki_goto()
            # The portal focus is deferred a frame so the title render settles first.
            mock_clock.schedule_once.call_args[0][0](0)

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_no_op_outside_bottom_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(1)  # TREE (mouse/tree context)

        with patch.object(nav_module, "Clock") as mock_clock:
            nav.focus_title_view_portal_after_wiki_goto()

        mock_clock.schedule_once.assert_not_called()
        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_not_called()  # ty: ignore[unresolved-attribute]


class TestIconGotoTitleFocus:
    """The action-bar app icon deliberately navigates, so it always focuses the portal.

    Unlike the passive wiki/popup hand-offs (gated on prior bottom focus), pressing the
    icon forces keyboard focus onto the portal whatever the previous focus region.
    """

    def test_forces_portal_from_tree_focus(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(1)  # TREE (mouse context)
        nav._bottom_title_view_screen.is_visible = True

        with patch.object(nav_module, "Clock") as mock_clock:
            nav.focus_title_portal_after_icon_goto()
            # The portal focus is deferred a frame so the title render settles first.
            mock_clock.schedule_once.call_args[0][0](0)

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_called_once()  # ty: ignore[unresolved-attribute]

    def test_no_op_when_title_view_not_visible(self, nav: MainScreenNavigation) -> None:
        nav._bottom_title_view_screen.is_visible = False

        with patch.object(nav_module, "Clock") as mock_clock:
            nav.focus_title_portal_after_icon_goto()
            mock_clock.schedule_once.call_args[0][0](0)

        nav._bottom_title_view_screen.enter_nav_focus_at_portal.assert_not_called()  # ty: ignore[unresolved-attribute]


class TestTopGotoFocus:
    """The top-view goto arrow is a keyboard focus sub-stop of the TREE region."""

    def test_up_on_first_node_with_title_enters_top_goto(self, nav: MainScreenNavigation) -> None:
        first, second = MagicMock(), MagicMock()
        nav._tree_view_screen.get_visible_nodes.return_value = [first, second]  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = first  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.is_top_goto_active = True  # ty: ignore[invalid-assignment]

        assert nav._handle_tree_key(KEY_UP) is True

        assert nav._top_goto_focused is True
        nav._tree_view_screen.enter_top_goto_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.select_node.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_up_on_first_node_without_title_stays_in_tree(self, nav: MainScreenNavigation) -> None:
        first, second = MagicMock(), MagicMock()
        nav._tree_view_screen.get_visible_nodes.return_value = [first, second]  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = first  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.is_top_goto_active = False  # ty: ignore[invalid-assignment]

        assert nav._handle_tree_key(KEY_UP) is True

        assert nav._top_goto_focused is False
        nav._tree_view_screen.enter_top_goto_focus.assert_not_called()  # ty: ignore[unresolved-attribute]
        # The normal (clamped) move keeps the selection on the first node.
        nav._tree_view_screen.select_node.assert_called_once_with(first)  # ty: ignore[unresolved-attribute]

    def test_up_on_non_first_node_moves_tree(self, nav: MainScreenNavigation) -> None:
        first, second = MagicMock(), MagicMock()
        nav._tree_view_screen.get_visible_nodes.return_value = [first, second]  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.get_selected_node.return_value = second  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.is_top_goto_active = True  # ty: ignore[invalid-assignment]

        assert nav._handle_tree_key(KEY_UP) is True

        assert nav._top_goto_focused is False
        nav._tree_view_screen.enter_top_goto_focus.assert_not_called()  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.select_node.assert_called_once_with(first)  # ty: ignore[unresolved-attribute]

    def test_enter_on_arrow_activates_and_exits(self, nav: MainScreenNavigation) -> None:
        nav._top_goto_focused = True

        assert nav._handle_tree_key(KEY_ENTER) is True

        nav._tree_view_screen.activate_top_goto.assert_called_once()  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.exit_top_goto_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
        assert nav._top_goto_focused is False

    def test_down_on_arrow_returns_to_tree(self, nav: MainScreenNavigation) -> None:
        nav._top_goto_focused = True

        assert nav._handle_tree_key(KEY_DOWN) is True

        nav._tree_view_screen.exit_top_goto_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.activate_top_goto.assert_not_called()  # ty: ignore[unresolved-attribute]
        assert nav._top_goto_focused is False

    def test_escape_on_arrow_returns_to_tree_not_menu(self, nav: MainScreenNavigation) -> None:
        nav._top_goto_focused = True

        assert nav._handle_tree_key(KEY_ESCAPE) is True

        nav._tree_view_screen.exit_top_goto_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
        nav._enter_menu_mode.assert_not_called()  # ty: ignore[unresolved-attribute]
        assert nav._top_goto_focused is False

    def test_sideways_keys_on_arrow_are_swallowed(self, nav: MainScreenNavigation) -> None:
        nav._top_goto_focused = True

        for key in (KEY_UP, KEY_LEFT, KEY_RIGHT):
            assert nav._handle_tree_key(key) is True

        nav._tree_view_screen.activate_top_goto.assert_not_called()  # ty: ignore[unresolved-attribute]
        nav._tree_view_screen.exit_top_goto_focus.assert_not_called()  # ty: ignore[unresolved-attribute]
        assert nav._top_goto_focused is True

    def test_save_focus_before_reader_clears_arrow(self, nav: MainScreenNavigation) -> None:
        nav._top_goto_focused = True

        nav.save_focus_before_reader()

        nav._tree_view_screen.exit_top_goto_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
        assert nav._top_goto_focused is False


class TestFunViewBottomFocus:
    """The fun view owns its keyboard nav; the nav layer just enters/exits/delegates."""

    @staticmethod
    def _hide_nav_screens(nav: MainScreenNavigation) -> None:
        nav._main_index_screen.is_visible = False
        nav._speech_index_screen.is_visible = False
        nav._names_index_screen.is_visible = False
        nav._locations_index_screen.is_visible = False
        nav._statistics_screen.is_visible = False
        nav._history_screen.is_visible = False
        nav._search_screen.is_visible = False

    def test_enter_bottom_focus_enters_fun_nav(self, nav: MainScreenNavigation) -> None:
        self._hide_nav_screens(nav)
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False

        nav.enter_bottom_focus()

        assert nav.is_in_bottom_focus
        nav._fun_image_view_screen.enter_nav_focus.assert_called_once_with(  # ty: ignore[unresolved-attribute]
            nav.exit_bottom_focus
        )

    def test_fun_nav_takes_precedence_over_title_view(self, nav: MainScreenNavigation) -> None:
        self._hide_nav_screens(nav)
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = True

        nav.enter_bottom_focus()

        nav._fun_image_view_screen.enter_nav_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
        nav._bottom_title_view_screen.enter_nav_focus.assert_not_called()  # ty: ignore[unresolved-attribute]

    def test_bottom_key_delegates_to_fun_handle_key(self, nav: MainScreenNavigation) -> None:
        nav._focus_region = nav._focus_region.__class__(2)  # BOTTOM
        self._hide_nav_screens(nav)
        nav._fun_image_view_screen.is_visible = True
        nav._bottom_title_view_screen.is_visible = False
        nav._fun_image_view_screen.handle_key.return_value = True  # ty: ignore[unresolved-attribute]

        assert nav._handle_bottom_key(KEY_UP) is True
        nav._fun_image_view_screen.handle_key.assert_called_once_with(KEY_UP)  # ty: ignore[unresolved-attribute]

    def test_exit_bottom_focus_exits_fun_nav(self, nav: MainScreenNavigation) -> None:
        self._hide_nav_screens(nav)

        nav.exit_bottom_focus()

        nav._fun_image_view_screen.exit_nav_focus.assert_called_once()  # ty: ignore[unresolved-attribute]
