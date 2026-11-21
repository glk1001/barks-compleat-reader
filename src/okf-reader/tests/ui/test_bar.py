# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The top bar through a real viewer: its buttons, the page's action, and the keys on it."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.image import Image
from okf_reader.core.actions import PageAction
from okf_reader.core.theme import ViewerThemeSpec
from okf_reader.core.top_bar import TopBarSpec
from okf_reader.ui import viewer as viewer_module
from okf_reader.ui.keynav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_F,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
)
from okf_reader.ui.viewer import (
    FocusRegion,
    OKFViewer,
)
from PIL import Image as PilImage
from viewer_test_helpers import (
    NEEDS_A_WINDOW,
    page_of,
    remove_popups_left_open,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from kivy.uix.widget import Widget

pytestmark = NEEDS_A_WINDOW

TINT = (0.9, 0.8, 0.5, 1.0)


class TestBarKeys:
    def test_with_no_bar_buttons_escape_stays_where_it_is(self, viewer: OKFViewer) -> None:
        with patch.object(viewer._bar, "nav_buttons", return_value=[]):
            viewer.handle_key(KEY_ESCAPE)
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_buttons_gone_under_the_ring_drop_the_focus_out(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        with patch.object(viewer._bar, "nav_buttons", return_value=[]):
            assert viewer.handle_key(KEY_RIGHT) is True
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_a_ringed_button_gone_re_seeds_on_the_first(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        first = viewer._bar.nav_buttons()[0]
        viewer._bar.focused = Button()  # no longer one of the bar's buttons
        viewer.handle_key(KEY_RIGHT)
        assert viewer._bar.focused is first

    def test_enter_on_a_ringed_button_gone_does_nothing(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        viewer._bar.focused = Button()
        assert viewer.handle_key(KEY_ENTER) is True
        assert viewer._focus_region is FocusRegion.TOP_BAR

    def test_tab_leaves_the_bar_for_where_it_came_from(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)
        assert viewer.handle_key(KEY_TAB) is True
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_tab_switches_between_the_sidebar_and_the_page(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_TAB)
        assert viewer._focus_region is FocusRegion.PAGE
        viewer.handle_key(KEY_TAB)
        assert viewer._focus_region is FocusRegion.SIDEBAR


class TestPageAction:
    def test_an_action_without_an_icon_is_a_text_button(self, viewer: OKFViewer) -> None:
        run = MagicMock()
        viewer._bar.set_page_action(PageAction(label="Read Comic", run=run))
        assert viewer.action_btn is not None
        assert viewer.action_btn.text == "Read Comic"

        viewer.action_btn.dispatch("on_release")

        run.assert_called_once_with()

    def test_replacing_the_ringed_action_drops_the_ring(self, viewer: OKFViewer) -> None:
        viewer._bar.set_page_action(PageAction(label="Read Comic", run=MagicMock()))
        assert viewer.action_btn is not None
        viewer._bar.set_focus(viewer.action_btn)

        viewer._bar.set_page_action(None)

        assert viewer._bar.focused is None
        assert viewer.action_btn is None

    def test_with_no_action_running_one_does_nothing(self, viewer: OKFViewer) -> None:
        viewer._bar.set_page_action(None)
        with patch.object(viewer_module.trace, "page_action") as logged:
            viewer._bar.run_page_action()
        logged.assert_not_called()


class TestAnIconBar:
    """A host's bar: icon buttons tinted to its theme, and its icon as the way home."""

    @pytest.fixture
    def icons(self, tmp_path: Path) -> dict[str, Path]:
        paths = {}
        for name in ("home", "back", "on", "off", "close", "action"):
            paths[name] = tmp_path / f"{name}.png"
            PilImage.new("RGBA", (8, 8), (255, 255, 255, 255)).save(paths[name])
        return paths

    @pytest.fixture
    def themed(self, bundle: Path, icons: dict[str, Path]) -> Iterator[OKFViewer]:
        self.on_close = MagicMock()
        spec = TopBarSpec(
            icon_path=icons["home"],
            back_icon_path=icons["back"],
            contrast_on_icon_path=icons["on"],
            contrast_off_icon_path=icons["off"],
            close_icon_path=icons["close"],
            on_close=self.on_close,
        )
        okf_viewer = OKFViewer(bundle, top_bar=spec, theme=ViewerThemeSpec(icon_tint=TINT))
        yield okf_viewer
        remove_popups_left_open()

    @staticmethod
    def _overlay(button: Widget) -> Image:
        return next(w for w in button.children if isinstance(w, Image) and w.color == list(TINT))

    def test_each_button_wears_its_icon(self, themed: OKFViewer, icons: dict[str, Path]) -> None:
        assert themed.back_btn.icon == str(icons["back"])
        assert themed.contrast_btn.icon == str(icons["on"])
        assert themed._bar.quit_btn.icon == str(icons["close"])

    def test_the_contrast_icon_shows_what_pressing_will_do(
        self, themed: OKFViewer, icons: dict[str, Path]
    ) -> None:
        themed.contrast_btn.state = "down"
        assert themed.contrast_btn.icon == str(icons["off"])
        themed.contrast_btn.state = "normal"
        assert themed.contrast_btn.icon == str(icons["on"])

    def test_a_tinted_copy_lies_over_each_glyph_inside_its_inset(self, themed: OKFViewer) -> None:
        for button in (themed.back_btn, themed.contrast_btn, themed._bar.quit_btn):
            button.pos, button.size = (200, 10), (48, 40)
            overlay = self._overlay(button)
            assert overlay.source == button.icon
            assert tuple(overlay.pos) == (200 + dp(4), 10 + dp(4))
            assert tuple(overlay.size) == (48 - dp(8), 40 - dp(8))

    def test_the_tinted_copy_follows_the_contrast_icons_swap(
        self, themed: OKFViewer, icons: dict[str, Path]
    ) -> None:
        themed.contrast_btn.state = "down"
        assert self._overlay(themed.contrast_btn).source == str(icons["off"])

    def test_the_quit_button_does_what_the_host_asked(self, themed: OKFViewer) -> None:
        themed._bar.quit_btn.dispatch("on_release")
        self.on_close.assert_called_once_with()

    def test_the_bars_icon_dims_while_pressed_and_goes_home(self, themed: OKFViewer) -> None:
        home = themed._bar.home_btn
        assert home is not None
        icon = next(w for w in home.parent.children if isinstance(w, Image))
        home.parent.size = (70, 40)
        assert tuple(icon.size) == (70 - dp(8), 40 - dp(8))
        themed.show_page(themed.bundle / "concept" / "a.md")

        home.state = "down"
        assert icon.opacity == 0.5  # noqa: PLR2004
        home.state = "normal"
        assert icon.opacity == 1.0
        home.dispatch("on_release")

        assert page_of(themed) == "index.md"
        assert home in themed._bar.nav_buttons()

    def test_a_page_action_with_an_icon_is_a_tinted_icon_button(
        self, themed: OKFViewer, icons: dict[str, Path]
    ) -> None:
        run = MagicMock()
        themed._bar.set_page_action(
            PageAction(label="Read Comic", run=run, icon_path=icons["action"])
        )
        assert themed.action_btn is not None
        assert themed.action_btn.icon == str(icons["action"])
        assert self._overlay(themed.action_btn).source == str(icons["action"])

        themed.action_btn.dispatch("on_release")

        run.assert_called_once_with()


class TestTheRemoteOnTheBar:
    @pytest.fixture
    def on_bar(self, viewer: OKFViewer) -> OKFViewer:
        viewer.handle_key(KEY_ESCAPE)
        return viewer

    def test_right_and_left_walk_the_buttons_and_wrap(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")  # Back comes alive: three buttons
        viewer.handle_key(KEY_ESCAPE)
        back, contrast, close = viewer._bar.nav_buttons()
        assert viewer._bar.focused is back

        viewer.handle_key(KEY_RIGHT)
        assert viewer._bar.focused is contrast
        viewer.handle_key(KEY_LEFT)
        viewer.handle_key(KEY_LEFT)
        assert viewer._bar.focused is close
        viewer.handle_key(KEY_RIGHT)
        assert viewer._bar.focused is back

    def test_it_starts_on_back_when_there_is_a_page_to_go_back_to(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        viewer.handle_key(KEY_ESCAPE)
        assert viewer._bar.focused is viewer.back_btn

    def test_enter_presses_the_ringed_button_and_leaves_the_bar(self, on_bar: OKFViewer) -> None:
        assert on_bar._bar.focused is on_bar.contrast_btn

        assert on_bar.handle_key(KEY_ENTER) is True

        assert on_bar.contrast_btn.state == "down"
        assert on_bar._focus_region is FocusRegion.SIDEBAR

    def test_down_drops_out_and_up_is_held(self, on_bar: OKFViewer) -> None:
        assert on_bar.handle_key(KEY_UP) is True
        assert on_bar._focus_region is FocusRegion.TOP_BAR
        assert on_bar.handle_key(KEY_DOWN) is True
        assert on_bar._focus_region is FocusRegion.SIDEBAR

    def test_an_unmapped_key_is_left_to_the_host(self, on_bar: OKFViewer) -> None:
        assert on_bar.handle_key(KEY_F) is False
