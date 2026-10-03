"""The collapse bar over the tree: when it shows, and what tapping it does.

It shows once an expanded parent's top has scrolled above the tree's view, and
a tap collapses that parent. The node and the scroll view are stand-ins that
report where they sit in the window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import collapse_parent_overlay
from barks_reader.ui.collapse_parent_overlay import CollapseParentOverlay
from barks_reader.ui.tree_view_nodes import ButtonTreeViewNode
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.properties import ColorProperty  # ty: ignore[unresolved-import]
from kivy.uix.label import Label

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class _BgColorLabel(Label):
    """Stand in for the app's BgColorLabel, defined in main_screen.kv, which is not loaded here."""

    background_color = ColorProperty((0, 0, 0, 0))


_SCROLL_VIEW_TOP = 500


@pytest.fixture(autouse=True)
def _bg_color_label() -> Iterator[None]:
    if "BgColorLabel" in Factory.classes:
        yield
        return
    Factory.register("BgColorLabel", cls=_BgColorLabel)
    yield
    Factory.unregister("BgColorLabel")


@pytest.fixture
def icon(tmp_path: Path) -> Path:
    return tmp_path / "collapse.png"


@pytest.fixture
def overlay(icon: Path) -> Iterator[CollapseParentOverlay]:
    app = MagicMock()
    app.reader_settings.sys_file_paths.get_barks_reader_collapse_icon_file.return_value = icon
    with (
        patch.object(collapse_parent_overlay.App, "get_running_app", return_value=app),
        patch.object(collapse_parent_overlay, "Clock") as clock,
    ):
        widget = CollapseParentOverlay(pos=(0, 0), size=(400, 600))
        widget.clock = clock
        yield widget


@pytest.fixture
def scroll_view() -> MagicMock:
    view = MagicMock()
    view.to_window.side_effect = lambda _x, _y: (0, _SCROLL_VIEW_TOP)
    return view


def _node(name: str = "Donald Duck", top: float = 450) -> MagicMock:
    """Return a tree node, open, whose top edge is at ``top`` in the window."""
    node = MagicMock(spec=ButtonTreeViewNode)
    node.get_name.return_value = name
    node.is_open = True
    node.to_window.side_effect = lambda _x, _y: (0, node.window_top)
    node.window_top = top
    return node


def _tracking(overlay: CollapseParentOverlay, scroll_view: MagicMock, node: MagicMock) -> None:
    """Track a node with its layout settled, as the tree's scroll pinner leaves it."""
    overlay.setup(scroll_view)
    overlay.track_node(node)
    overlay.end_suppression()


def _scroll(scroll_view: MagicMock) -> None:
    """Move the tree, as the user's scrolling does: the overlay rechecks."""
    on_scroll = scroll_view.bind.call_args.kwargs["scroll_y"]
    on_scroll(scroll_view, 0.5)


def _bar(overlay: CollapseParentOverlay) -> collapse_parent_overlay._CollapseBar:
    return overlay._bar_widget  # noqa: SLF001


def _touch_at(x: float, y: float) -> MagicMock:
    touch = MagicMock()
    touch.pos = (x, y)
    return touch


class TestShowing:
    def test_a_node_still_in_view_shows_no_bar(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        _tracking(overlay, scroll_view, _node(top=_SCROLL_VIEW_TOP - 50))
        _scroll(scroll_view)
        assert not overlay.is_visible
        assert _bar(overlay).opacity == 0
        assert _bar(overlay).disabled

    def test_a_node_scrolled_above_the_view_shows_the_bar_with_its_name(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        node = _node("Uncle Scrooge")
        _tracking(overlay, scroll_view, node)

        node.window_top = _SCROLL_VIEW_TOP + 50
        _scroll(scroll_view)

        assert overlay.is_visible
        assert _bar(overlay).opacity == 1
        assert not _bar(overlay).disabled
        label = _bar(overlay).children[-1]
        assert label.text == "[i]Uncle Scrooge[/i]"

    def test_nothing_shows_while_the_tree_is_still_settling(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        overlay.setup(scroll_view)
        overlay.track_node(_node(top=_SCROLL_VIEW_TOP + 50))

        _scroll(scroll_view)
        assert not overlay.is_visible

        overlay.end_suppression()
        assert not overlay.is_visible
        overlay.clock.schedule_once.call_args.args[0](0)
        assert overlay.is_visible

    def test_a_parent_collapsed_some_other_way_stops_being_tracked(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        node = _node(top=_SCROLL_VIEW_TOP + 50)
        _tracking(overlay, scroll_view, node)

        node.is_open = False
        overlay.recheck_visibility()

        assert not overlay.is_visible
        assert overlay.parent_name == ""

    def test_without_a_tracked_node_or_scroll_view_it_stays_hidden(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        overlay.recheck_visibility()
        assert not overlay.is_visible

        overlay.setup(scroll_view)
        overlay.clear_tracking()
        _scroll(scroll_view)
        assert not overlay.is_visible

    def test_only_a_tree_node_is_tracked(self, overlay: CollapseParentOverlay) -> None:
        overlay.track_node(MagicMock())
        assert overlay.parent_name == ""
        assert _bar(overlay) is None


class TestTheBar:
    def test_it_is_built_once_with_the_apps_icon(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock, icon: Path
    ) -> None:
        _tracking(overlay, scroll_view, _node("One"))
        bar = _bar(overlay)
        _tracking(overlay, scroll_view, _node("Two"))

        assert _bar(overlay) is bar
        assert bar.icon_source == str(icon)
        assert overlay.parent_name == "Two"

    def test_it_sits_along_the_top_and_follows_the_overlay(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        _tracking(overlay, scroll_view, _node())

        overlay.pos = (10, 20)
        overlay.size = (300, 400)

        bar = _bar(overlay)
        assert (bar.x, bar.width) == (10, 300)
        assert bar.y == 20 + 400 - dp(28) - dp(5)

    def test_before_it_is_built_moving_the_overlay_does_nothing(
        self, overlay: CollapseParentOverlay
    ) -> None:
        overlay._update_bar_pos()  # noqa: SLF001
        overlay._update_bar_visibility()  # noqa: SLF001
        assert _bar(overlay) is None


class TestTapping:
    def _shown(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock, node: MagicMock
    ) -> collapse_parent_overlay._CollapseBar:
        _tracking(overlay, scroll_view, node)
        node.window_top = _SCROLL_VIEW_TOP + 50
        _scroll(scroll_view)
        return _bar(overlay)

    def test_a_tap_collapses_the_parent_and_hides_the_bar(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock, loguru_sink: list[str]
    ) -> None:
        node = _node("Gyro Gearloose")
        on_collapse = MagicMock()
        overlay.on_collapse_request = on_collapse
        bar = self._shown(overlay, scroll_view, node)

        assert bar.on_touch_down(_touch_at(bar.x + 50, bar.y + 10))

        on_collapse.assert_called_once_with(node)
        assert "Collapse overlay tapped: collapsing 'Gyro Gearloose'." in loguru_sink
        assert not overlay.is_visible
        assert overlay.parent_name == ""

    def test_a_tap_with_no_one_listening_still_hides_it(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        bar = self._shown(overlay, scroll_view, _node())

        assert bar.on_touch_down(_touch_at(bar.x + 50, bar.y + 10))

        assert not overlay.is_visible

    def test_a_touch_elsewhere_is_left_to_the_tree(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        on_collapse = MagicMock()
        overlay.on_collapse_request = on_collapse
        bar = self._shown(overlay, scroll_view, _node())

        assert not bar.on_touch_down(_touch_at(bar.x + 50, bar.y - 100))

        on_collapse.assert_not_called()
        assert overlay.is_visible

    def test_a_hidden_bar_takes_no_touch(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        on_collapse = MagicMock()
        overlay.on_collapse_request = on_collapse
        _tracking(overlay, scroll_view, _node(top=_SCROLL_VIEW_TOP - 50))
        bar = _bar(overlay)

        assert not bar.on_touch_down(_touch_at(bar.x + 50, bar.y + 10))

        on_collapse.assert_not_called()

    def test_a_press_after_tracking_ended_does_nothing(
        self, overlay: CollapseParentOverlay, scroll_view: MagicMock
    ) -> None:
        on_collapse = MagicMock()
        overlay.on_collapse_request = on_collapse
        self._shown(overlay, scroll_view, _node())
        overlay.clear_tracking()

        overlay._on_bar_pressed()  # noqa: SLF001

        on_collapse.assert_not_called()
