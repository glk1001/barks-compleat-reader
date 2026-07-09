# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import wiki_reader
from barks_reader.ui.reader_keyboard_nav import (
    KEY_ESCAPE,
    KEY_F,
    KEY_LEFT,
    set_alt_escape_key,
)
from barks_reader.ui.wiki_reader import WikiReaderScreen
from kivy.uix.screenmanager import Screen

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def wiki_screen() -> WikiReaderScreen:
    # Patch Screen.__init__ to avoid Kivy window creation/interaction.
    with patch.object(Screen, "__init__", autospec=True):
        return WikiReaderScreen(
            reader_settings=MagicMock(),
            font_manager=MagicMock(),
            image_selector=MagicMock(),
            app_data_dir=Path("/app-data"),
            on_goto_title=MagicMock(),
            on_close_screen=MagicMock(),
        )


@pytest.fixture(autouse=True)
def mock_window() -> Iterator[MagicMock]:
    # The screen binds/unbinds the window's key handler on open/close; keep the
    # real Window singleton out of the unit tests.
    with patch.object(wiki_reader, "Window") as window:
        yield window


@pytest.fixture(autouse=True)
def mock_clock() -> Iterator[MagicMock]:
    # open_wiki schedules a deferred re-apply of the viewer sizing; keep the real
    # Kivy Clock out of the unit tests (the deferred call is asserted separately).
    with patch.object(wiki_reader, "Clock") as clock:
        yield clock


@pytest.fixture(autouse=True)
def mock_window_manager() -> Iterator[MagicMock]:
    # _apply_viewer_sizing asks WindowManager whether the window is fullscreen;
    # default to windowed so the real Window singleton is never touched. Tests
    # that exercise the fullscreen path flip is_fullscreen_now.return_value.
    with patch.object(wiki_reader, "WindowManager") as wm:
        wm.is_fullscreen_now.return_value = False
        yield wm


class TestWikiReaderScreenOpenWiki:
    BUNDLE = Path("/bundle")
    PAGE = Path("/bundle/concept/stories/donald-duck/lost-in-the-andes.md")

    def test_first_open_builds_viewer_with_start_page(self, wiki_screen: WikiReaderScreen) -> None:
        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_called_once_with(wiki_screen, self.BUNDLE, start_page=self.PAGE)

    def test_existing_viewer_resets_history_to_page(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = self.BUNDLE

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_not_called()
        wiki_screen._viewer.reset_to.assert_called_once_with(self.PAGE)
        wiki_screen._viewer.show_page.assert_not_called()

    def test_existing_viewer_without_page_resets_history(
        self, wiki_screen: WikiReaderScreen
    ) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = self.BUNDLE

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE)

        build_mock.assert_not_called()
        wiki_screen._viewer.reset_to.assert_called_once_with(None)

    def test_bundle_change_rebuilds_viewer_with_start_page(
        self, wiki_screen: WikiReaderScreen
    ) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = Path("/old-bundle")

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_called_once_with(wiki_screen, self.BUNDLE, start_page=self.PAGE)


@pytest.fixture(autouse=True)
def _reset_alt_escape() -> Iterator[None]:
    # is_escape_key reads a module-global alt-Escape key; keep tests isolated.
    yield
    set_alt_escape_key(0)


def _idle_viewer() -> MagicMock:
    """Build a mock viewer with the search field unfocused (normal navigation)."""
    viewer = MagicMock()
    viewer.search_focused = False
    return viewer


class TestWikiReaderScreenKeyboard:
    def test_escape_routes_to_go_back_and_consumes(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = _idle_viewer()
        wiki_screen._viewer.escape_search.return_value = False  # search idle

        consumed = wiki_screen._on_key_down(None, KEY_ESCAPE, 0, "", [])

        assert consumed is True
        wiki_screen._viewer.go_back.assert_called_once_with()

    def test_escape_backs_out_of_active_search_before_go_back(
        self, wiki_screen: WikiReaderScreen
    ) -> None:
        wiki_screen._viewer = _idle_viewer()
        wiki_screen._viewer.escape_search.return_value = True  # an active search consumes Escape

        consumed = wiki_screen._on_key_down(None, KEY_ESCAPE, 0, "", [])

        assert consumed is True
        wiki_screen._viewer.go_back.assert_not_called()

    def test_ctrl_f_focuses_search_and_consumes(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = _idle_viewer()

        consumed = wiki_screen._on_key_down(None, KEY_F, 0, "", ["ctrl"])

        assert consumed is True
        wiki_screen._viewer.focus_search.assert_called_once_with()
        wiki_screen._viewer.go_back.assert_not_called()

    def test_f_without_ctrl_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = _idle_viewer()

        consumed = wiki_screen._on_key_down(None, KEY_F, 0, "f", [])

        assert consumed is False
        wiki_screen._viewer.focus_search.assert_not_called()

    def test_alt_left_routes_to_go_back_and_consumes(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = _idle_viewer()

        consumed = wiki_screen._on_key_down(None, KEY_LEFT, 0, "", ["alt"])

        assert consumed is True
        wiki_screen._viewer.go_back.assert_called_once_with()

    def test_left_without_alt_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = _idle_viewer()

        consumed = wiki_screen._on_key_down(None, KEY_LEFT, 0, "", [])

        assert consumed is False
        wiki_screen._viewer.go_back.assert_not_called()

    def test_other_key_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = _idle_viewer()

        consumed = wiki_screen._on_key_down(None, ord("a"), 0, "a", [])

        assert consumed is False
        wiki_screen._viewer.go_back.assert_not_called()

    def test_alt_escape_navigates_when_search_idle(self, wiki_screen: WikiReaderScreen) -> None:
        """With the field unfocused, a configured alt-Escape letter backs out."""
        set_alt_escape_key(ord("r"))
        wiki_screen._viewer = _idle_viewer()
        wiki_screen._viewer.escape_search.return_value = False

        consumed = wiki_screen._on_key_down(None, ord("r"), 0, "r", [])

        assert consumed is True
        wiki_screen._viewer.go_back.assert_called_once_with()

    def test_no_viewer_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = None

        assert wiki_screen._on_key_down(None, KEY_ESCAPE, 0, "", []) is False


class TestWikiReaderScreenKeyboardWhileTyping:
    """While the search field owns the keyboard, keystrokes must reach it."""

    def test_alt_escape_letter_passes_through(self, wiki_screen: WikiReaderScreen) -> None:
        """The configured alt-Escape letter (e.g. 'r') types instead of navigating."""
        set_alt_escape_key(ord("r"))
        wiki_screen._viewer = MagicMock()
        wiki_screen._viewer.search_focused = True

        consumed = wiki_screen._on_key_down(None, ord("r"), 0, "r", [])

        assert consumed is False
        wiki_screen._viewer.escape_search.assert_not_called()
        wiki_screen._viewer.go_back.assert_not_called()

    def test_plain_letter_passes_through(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._viewer.search_focused = True

        consumed = wiki_screen._on_key_down(None, ord("a"), 0, "a", [])

        assert consumed is False
        wiki_screen._viewer.go_back.assert_not_called()

    def test_alt_left_passes_through_while_typing(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._viewer.search_focused = True

        consumed = wiki_screen._on_key_down(None, KEY_LEFT, 0, "", ["alt"])

        assert consumed is False
        wiki_screen._viewer.go_back.assert_not_called()

    def test_real_escape_backs_out_of_search(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._viewer.search_focused = True

        consumed = wiki_screen._on_key_down(None, KEY_ESCAPE, 0, "", [])

        assert consumed is True
        wiki_screen._viewer.escape_search.assert_called_once_with()
        wiki_screen._viewer.go_back.assert_not_called()

    def test_ctrl_f_still_focuses_while_typing(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._viewer.search_focused = True

        consumed = wiki_screen._on_key_down(None, KEY_F, 0, "", ["ctrl"])

        assert consumed is True
        wiki_screen._viewer.focus_search.assert_called_once_with()


class TestWikiReaderScreenKeyBinding:
    BUNDLE = Path("/bundle")

    def test_open_binds_handlers(
        self, wiki_screen: WikiReaderScreen, mock_window: MagicMock
    ) -> None:
        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True):
            wiki_screen.open_wiki(self.BUNDLE)

        mock_window.bind.assert_called_once_with(
            on_key_down=wiki_screen._on_key_down, on_resize=wiki_screen._apply_viewer_sizing
        )
        # Unbind first, so a re-open without an intervening close can't double-bind.
        mock_window.unbind.assert_called_once_with(
            on_key_down=wiki_screen._on_key_down, on_resize=wiki_screen._apply_viewer_sizing
        )

    def test_open_applies_viewer_sizing_immediately(
        self, wiki_screen: WikiReaderScreen, mock_clock: MagicMock
    ) -> None:
        with (
            patch.object(WikiReaderScreen, "_build_viewer", autospec=True),
            patch.object(WikiReaderScreen, "_apply_viewer_sizing", autospec=True) as apply_mock,
        ):
            wiki_screen.open_wiki(self.BUNDLE)

        # Applied immediately (no flash of an unsized viewer), and a deferred
        # re-apply is scheduled for after the layout settles.
        apply_mock.assert_called_once_with(wiki_screen)
        assert mock_clock.schedule_once.call_count == 1

    def test_open_defers_a_re_apply(
        self, wiki_screen: WikiReaderScreen, mock_clock: MagicMock
    ) -> None:
        # Not patching _apply_viewer_sizing here, so the real bound method is what
        # gets scheduled — re-pinning the strip against settled fullscreen geometry
        # when the open-time layout was still transient.
        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True):
            wiki_screen.open_wiki(self.BUNDLE)

        mock_clock.schedule_once.assert_called_once_with(wiki_screen._apply_viewer_sizing)

    def test_close_unbinds_handlers(
        self, wiki_screen: WikiReaderScreen, mock_window: MagicMock
    ) -> None:
        wiki_screen.close()

        mock_window.unbind.assert_called_once_with(
            on_key_down=wiki_screen._on_key_down, on_resize=wiki_screen._apply_viewer_sizing
        )
        wiki_screen._on_close_screen.assert_called_once_with()

    def test_close_does_not_change_window_mode(
        self, wiki_screen: WikiReaderScreen, mock_window_manager: MagicMock
    ) -> None:
        # Decision: the wiki inherits the caller's window mode and never toggles
        # it — close only unbinds handlers and saves the session.
        wiki_screen.close()

        mock_window_manager.goto_fullscreen_mode.assert_not_called()
        mock_window_manager.goto_windowed_mode.assert_not_called()


class TestWikiReaderScreenBuildViewer:
    BUNDLE = Path("/bundle")

    def test_build_viewer_passes_close_as_on_exit(self, wiki_screen: WikiReaderScreen) -> None:
        with (
            patch.object(wiki_reader, "OKFViewer") as viewer_cls,
            patch.object(wiki_reader, "wiki_top_bar_spec"),
            patch.object(wiki_reader, "wiki_session_path"),
            patch.object(wiki_reader, "BarksPanelsImageProvider"),
            patch.object(wiki_reader, "BarksTableRewriter"),
            patch.object(wiki_screen, "add_widget"),
        ):
            wiki_screen._build_viewer(self.BUNDLE)

        assert viewer_cls.call_args.kwargs["on_exit"] == wiki_screen.close


class TestWikiFullscreenViewerSize:
    """The pure fullscreen-strip math (comic aspect, width from height)."""

    def test_height_limited(self) -> None:
        # 1080 tall, 45 top bar -> 1035 content; width = round(1035 / 1.50943) = 686.
        assert wiki_reader.wiki_fullscreen_viewer_size(1080, 5000, 45) == (686, 1080)

    def test_ignores_oversized_multi_monitor_width(self) -> None:
        # A fullscreen Window.width that overshoots the visible monitor (spanning
        # two screens) must not widen the strip: width stays height-derived.
        width, _height = wiki_reader.wiki_fullscreen_viewer_size(1080, 99999, 45)
        assert width == 686
        assert width < 99999

    def test_width_limited(self) -> None:
        # A narrow ceiling caps the width and shrinks the content height to keep
        # the comic aspect: 100 wide -> content height round(100 * 1.50943) = 151.
        assert wiki_reader.wiki_fullscreen_viewer_size(2000, 100, 45) == (100, 196)


class TestApplyViewerSizing:
    def test_no_viewer_is_noop(
        self, wiki_screen: WikiReaderScreen, mock_window_manager: MagicMock
    ) -> None:
        wiki_screen._viewer = None

        wiki_screen._apply_viewer_sizing()

        mock_window_manager.is_fullscreen_now.assert_not_called()

    def test_fullscreen_shapes_screen_to_centred_strip(
        self,
        wiki_screen: WikiReaderScreen,
        mock_window: MagicMock,
        mock_window_manager: MagicMock,
    ) -> None:
        wiki_screen._viewer = MagicMock()
        mock_window_manager.is_fullscreen_now.return_value = True
        mock_window.height = 1080
        mock_window.width = 3840

        with patch.object(
            wiki_reader, "wiki_fullscreen_viewer_size", return_value=(686, 1080)
        ) as size_mock:
            wiki_screen._apply_viewer_sizing()

        # The SCREEN itself becomes the centred strip (mirroring <MainScreen>)...
        assert tuple(wiki_screen.size_hint) == (None, None)
        assert wiki_screen.pos_hint == {"center_x": 0.5, "center_y": 0.5}
        assert tuple(wiki_screen.size) == (686, 1080)
        size_mock.assert_called_once_with(1080, 3840, wiki_reader.ACTION_BAR_SIZE_Y)
        # ...and the viewer just fills the screen (no independent sizing to race).
        assert wiki_screen._viewer.size_hint == (1, 1)
        assert wiki_screen._viewer.pos_hint == {}

    def test_windowed_fills_manager(
        self, wiki_screen: WikiReaderScreen, mock_window_manager: MagicMock
    ) -> None:
        wiki_screen._viewer = MagicMock()
        mock_window_manager.is_fullscreen_now.return_value = False

        wiki_screen._apply_viewer_sizing()

        assert tuple(wiki_screen.size_hint) == (1, 1)
        assert wiki_screen.pos_hint == {}
        assert wiki_screen._viewer.size_hint == (1, 1)
        assert wiki_screen._viewer.pos_hint == {}
