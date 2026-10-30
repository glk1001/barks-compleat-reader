# ruff: noqa: SLF001
"""The document reader: page paths, turning, and the log lines that mark each step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.document_links import StoryLink
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.ui import document_reader as document_reader_module
from barks_reader.ui.document_reader import DocumentReaderScreen
from barks_reader.ui.reader_screens import ReaderScreen

if TYPE_CHECKING:
    from collections.abc import Iterator

PAGES = ("01.png", "02.jpg")
TWICE = 2


@pytest.fixture(autouse=True)
def windowed() -> Iterator[MagicMock]:
    """Hold the window windowed, as the real one reads from Kivy's Window."""
    with patch.object(document_reader_module, "WindowManager") as window_manager:
        window_manager.is_fullscreen_now.return_value = False
        yield window_manager


def _bar() -> MagicMock:
    bar = MagicMock()
    bar.disabled = False
    return bar


@pytest.fixture
def screen() -> DocumentReaderScreen:
    with (
        patch.object(ReaderScreen, "__init__", autospec=True) as mock_init,
        patch.object(DocumentReaderScreen, "_setup_action_bar_nav"),
    ):

        def side_effect(instance: DocumentReaderScreen, **_kwargs: object) -> None:
            instance.ids = {
                "doc_action_bar": _bar(),
                "fullscreen_button": MagicMock(),
                "close_button": MagicMock(),
                "goto_story_button": MagicMock(),
            }

        mock_init.side_effect = side_effect
        built = DocumentReaderScreen(
            reader_settings=MagicMock(),
            font_manager=MagicMock(),
            window_manager=MagicMock(),
            on_close_screen=MagicMock(),
            on_goto_story=MagicMock(),
        )
        built._menu_mode = False
        return built


def _figure(title: Titles, page: str, figure: int = 1) -> dict[str, object]:
    return {"figure": figure, "title": title.name, "page": page, "box": [0, 0, 1, 1]}


def _write_links(page: Path, *figures: dict[str, object]) -> None:
    page.with_suffix(".json").write_text(json.dumps({"figures": list(figures)}), encoding="utf-8")


def _open(
    screen: DocumentReaderScreen, doc_dir: Path, title: str = "How To", *, resume: bool = False
) -> None:
    with (
        patch.object(document_reader_module, "Window"),
        patch.object(document_reader_module, "get_action_bar_title", return_value=title),
    ):
        screen.open_document(doc_dir, title, resume=resume)


class TestDocumentReaderMarkers:
    def test_open_logs_the_title_and_page_count(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        for name in PAGES:
            (tmp_path / name).write_bytes(b"")
        (tmp_path / "notes.txt").write_text("not a page")
        _open(screen, tmp_path)
        assert f'Document reader opened "How To" with {len(PAGES)} pages.' in loguru_sink
        assert f'Document page 1/{len(PAGES)}: "01.png".' in loguru_sink

    def test_turning_pages_logs_each_one(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        for name in PAGES:
            (tmp_path / name).write_bytes(b"")
        _open(screen, tmp_path)
        screen.next_page()
        assert f'Document page 2/{len(PAGES)}: "02.jpg".' in loguru_sink
        screen.next_page()  # already on the last page: nothing new
        assert loguru_sink.count(f'Document page 2/{len(PAGES)}: "02.jpg".') == 1
        screen.prev_page()
        assert loguru_sink.count(f'Document page 1/{len(PAGES)}: "01.png".') == TWICE

    def test_close_logs(self, screen: DocumentReaderScreen, loguru_sink: list[str]) -> None:
        with patch.object(document_reader_module, "Window"):
            screen.close()
        assert "Document reader closing." in loguru_sink


class TestEdges:
    def test_a_document_with_no_pages_shows_none(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        (tmp_path / "notes.txt").write_text("not a page")
        _open(screen, tmp_path)
        assert screen.page_source == ""
        assert 'Document reader opened "How To" with 0 pages.' in loguru_sink

    def test_a_touch_off_the_bar_and_the_page_goes_on_to_the_screen(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        for name in PAGES:
            (tmp_path / name).write_bytes(b"")
        _open(screen, tmp_path)
        off_it = _bar()
        off_it.collide_point.return_value = False
        screen.ids = {"doc_action_bar": off_it, "doc_page": off_it}
        with (
            patch.object(screen, "_clear_menu_on_touch"),
            patch.object(ReaderScreen, "on_touch_down", return_value=True) as screen_press,
        ):
            assert screen.on_touch_down(MagicMock(pos=(5, 5), x=5, y=5)) is True
        screen_press.assert_called_once()
        assert screen._current_page_index == 0


TWO_LINKS = (
    StoryLink(Titles.LOST_IN_THE_ANDES, "7", "Fig. 1"),
    StoryLink(Titles.VOODOO_HOODOO, "2", "Fig. 2"),
)


class TestGotoStory:
    def test_a_page_with_links_shows_the_button_and_one_without_greys_it(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        for name in ("page-001.png", "page-002.png"):
            (tmp_path / name).write_bytes(b"")
        _write_links(tmp_path / "page-001.png", _figure(Titles.LOST_IN_THE_ANDES, "7"))
        _write_links(tmp_path / "page-002.png")
        _open(screen, tmp_path)
        assert screen.has_story_links is True
        screen.next_page()
        assert screen.has_story_links is False

    def test_one_story_goes_straight_to_it_and_closes_the_document(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _write_links(tmp_path / "page-001.png", _figure(Titles.LOST_IN_THE_ANDES, "7"))
        _open(screen, tmp_path)
        order = MagicMock()
        order.attach_mock(screen._on_close_screen, "close")
        order.attach_mock(screen._on_goto_story, "goto")
        with patch.object(document_reader_module, "Window"):
            screen._open_goto_story(keyboard_initiated=True)
        # The document goes first, then the main screen navigates.
        assert order.mock_calls == [
            call.close(),
            call.goto(Titles.LOST_IN_THE_ANDES, "7", keyboard_initiated=True),
        ]
        assert 'Document goto story: "LOST_IN_THE_ANDES", page 7.' in loguru_sink

    def test_from_a_changed_mode_the_story_waits_for_the_document_to_go(
        self, screen: DocumentReaderScreen, tmp_path: Path, windowed: MagicMock
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _write_links(tmp_path / "page-001.png", _figure(Titles.LOST_IN_THE_ANDES, "7"))
        _open(screen, tmp_path)  # windowed on entry
        windowed.is_fullscreen_now.return_value = True  # the bar's Fullscreen since
        screen._mode = MagicMock()
        order = MagicMock()
        order.attach_mock(screen._on_close_screen, "close")
        order.attach_mock(screen._on_goto_story, "goto")
        with patch.object(document_reader_module, "Window"):
            screen._open_goto_story(keyboard_initiated=False)
        screen._mode.goto_windowed.assert_called_once()
        assert order.mock_calls == []  # nothing until the window is back

        windowed.is_fullscreen_now.return_value = False
        with (
            patch.object(document_reader_module, "log_window_geometry"),
            patch.object(screen, "_fills_window", return_value=True),
            patch.object(document_reader_module, "Clock") as clock,
        ):
            screen._on_finished_goto_windowed_mode()
            clock.schedule_once.call_args[0][0](0)
        assert order.mock_calls == [
            call.close(),
            call.goto(Titles.LOST_IN_THE_ANDES, "7", keyboard_initiated=False),
        ]
        # Done with: a later close does not navigate again.
        screen._on_goto_story.reset_mock()
        _open(screen, tmp_path)
        with patch.object(document_reader_module, "Window"):
            screen.close()
        screen._on_goto_story.assert_not_called()

    def test_no_story_does_nothing(self, screen: DocumentReaderScreen, tmp_path: Path) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _open(screen, tmp_path)
        screen._open_goto_story(keyboard_initiated=False)
        screen._on_goto_story.assert_not_called()
        screen._on_close_screen.assert_not_called()

    def test_several_stories_open_a_list_in_keyboard_nav(
        self, screen: DocumentReaderScreen
    ) -> None:
        screen._story_links = list(TWO_LINKS)
        with (
            patch.object(screen, "_clear_menu_focus"),
            patch.object(screen, "_open_story_dropdown", return_value=True),
            patch.object(screen, "_enter_dropdown_nav") as enter_nav,
        ):
            screen._open_goto_story(keyboard_initiated=True)
        enter_nav.assert_called_once_with(initial_idx=0)
        screen._on_goto_story.assert_not_called()

    def test_a_keyboard_pick_from_the_list_is_passed_on_as_one(
        self, screen: DocumentReaderScreen
    ) -> None:
        screen._story_links = list(TWO_LINKS)
        screen._story_buttons = [MagicMock(), MagicMock()]
        screen._dropdown_buttons_cache = screen._story_buttons
        screen._dropdown_focused_idx = 1
        screen._activate_dropdown_item()
        with patch.object(document_reader_module, "Clock") as clock:
            screen._on_story_selected(MagicMock(), 1)
        go = clock.schedule_once.call_args.args[0]
        with patch.object(document_reader_module, "Window"):
            go(0)
        screen._on_goto_story.assert_called_once_with(
            Titles.VOODOO_HOODOO, "2", keyboard_initiated=True
        )
        assert screen._story_picked_by_keyboard is False

    def test_a_list_left_without_a_pick_forgets_the_keyboard(
        self, screen: DocumentReaderScreen
    ) -> None:
        """Else the next pick by mouse would be passed on as a keyboard one."""
        screen._story_buttons = [MagicMock(), MagicMock()]
        screen._dropdown_buttons_cache = screen._story_buttons
        screen._dropdown_focused_idx = 0
        screen._activate_dropdown_item()  # Return, but the press never reached the list
        assert screen._story_picked_by_keyboard is True
        screen._on_story_list_dismissed(MagicMock())
        assert screen._story_picked_by_keyboard is False

    # --- Go to Story pressed on the bar ---

    @staticmethod
    def _on_the_bar(screen: DocumentReaderScreen) -> None:
        """Give the screen the bar the fixture's mocked nav setup left out."""
        screen._menu_buttons = [screen.ids.goto_story_button, screen.ids.close_button]
        screen._focused_btn_idx = screen._last_used_btn_idx = 1

    def test_from_the_bar_a_list_opens_in_keyboard_nav_in_the_menu(
        self, screen: DocumentReaderScreen
    ) -> None:
        self._on_the_bar(screen)
        screen._story_links = list(TWO_LINKS)
        with (
            patch.object(
                screen, "_enter_menu_mode", side_effect=lambda: setattr(screen, "_menu_mode", True)
            ) as enter_menu,
            patch.object(screen, "_exit_menu_mode") as exit_menu,
            patch.object(screen, "_clear_menu_focus"),
            patch.object(screen, "_open_story_dropdown", return_value=True),
            patch.object(
                screen,
                "_enter_dropdown_nav",
                side_effect=lambda **_kw: setattr(screen, "_dropdown_nav_mode", True),
            ) as enter_nav,
        ):
            screen.open_goto_story_from_bar()
        enter_menu.assert_called_once_with()
        enter_nav.assert_called_once_with(initial_idx=0)
        exit_menu.assert_not_called()
        assert (screen._focused_btn_idx, screen._last_used_btn_idx) == (0, 0)

    def test_from_the_bar_the_one_story_is_a_mouse_pick_and_leaves_the_menu_once(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _write_links(tmp_path / "page-001.png", _figure(Titles.LOST_IN_THE_ANDES, "7"))
        _open(screen, tmp_path)
        self._on_the_bar(screen)
        with (
            patch.object(document_reader_module, "Window"),
            patch.object(
                screen, "_enter_menu_mode", side_effect=lambda: setattr(screen, "_menu_mode", True)
            ),
            patch.object(
                screen, "_exit_menu_mode", side_effect=lambda: setattr(screen, "_menu_mode", False)
            ) as exit_menu,
        ):
            screen.open_goto_story_from_bar()
        screen._on_goto_story.assert_called_once_with(
            Titles.LOST_IN_THE_ANDES, "7", keyboard_initiated=False
        )
        exit_menu.assert_called_once_with()  # closing the document left it; not again after

    def test_from_the_bar_with_no_story_the_menu_is_left_again(
        self, screen: DocumentReaderScreen
    ) -> None:
        self._on_the_bar(screen)
        screen._story_links = []
        with (
            patch.object(
                screen, "_enter_menu_mode", side_effect=lambda: setattr(screen, "_menu_mode", True)
            ),
            patch.object(screen, "_exit_menu_mode") as exit_menu,
        ):
            screen.open_goto_story_from_bar()
        exit_menu.assert_called_once_with()


def _pages(doc_dir: Path, count: int) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    for number in range(1, count + 1):
        (doc_dir / f"page-{number:03d}.png").write_bytes(b"")


class TestResume:
    """A document opened to resume comes back at the page it was left on, this session."""

    def test_a_resumed_document_opens_at_the_page_it_was_left_on(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        _pages(tmp_path, 4)
        _open(screen, tmp_path, resume=True)
        screen.next_page()
        screen.next_page()
        _open(screen, tmp_path, resume=True)
        assert screen.page_source.endswith("page-003.png")

    def test_a_document_not_resumed_opens_at_its_first_page(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        _pages(tmp_path, 4)
        _open(screen, tmp_path)
        screen.next_page()
        _open(screen, tmp_path)
        assert screen.page_source.endswith("page-001.png")

    def test_each_document_keeps_its_own_page(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        first, second = tmp_path / "first", tmp_path / "second"
        _pages(first, 3)
        _pages(second, 3)
        _open(screen, first, resume=True)
        screen.next_page()
        _open(screen, second, resume=True)
        assert screen.page_source.endswith("page-001.png")
        _open(screen, first, resume=True)
        assert screen.page_source == str(first / "page-002.png")

    def test_a_document_that_lost_pages_resumes_at_its_last_one(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        _pages(tmp_path, 3)
        _open(screen, tmp_path, resume=True)
        screen.next_page()
        screen.next_page()
        (tmp_path / "page-003.png").unlink()
        _open(screen, tmp_path, resume=True)
        assert screen.page_source.endswith("page-002.png")


SEVEN_PAGES = tuple(f"page-{n:03d}.png" for n in range(1, 8))


def _spread(screen: DocumentReaderScreen) -> None:
    """Put the screen on the two-page spread (the fixture's init skips Kivy's auto-bind)."""
    screen.layout_mode = MainLayoutMode.SPREAD.value
    screen.on_layout_mode(screen, screen.layout_mode)


def _shown(screen: DocumentReaderScreen) -> tuple[str, str]:
    return Path(screen.page_source).name, Path(screen.right_page_source).name


class TestTheSpread:
    """Pages come in pairs on the spread, from the first; a turn moves a pair."""

    def test_the_document_opens_on_its_first_pair_and_right_turns_a_pair(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        for name in SEVEN_PAGES:
            (tmp_path / name).write_bytes(b"")
        _spread(screen)
        _open(screen, tmp_path)
        assert _shown(screen) == ("page-001.png", "page-002.png")
        assert 'Document page 1/7: "page-001.png".' in loguru_sink
        assert 'Document right page 2/7: "page-002.png".' in loguru_sink
        screen.next_page()
        assert _shown(screen) == ("page-003.png", "page-004.png")
        screen.next_page()
        assert _shown(screen) == ("page-005.png", "page-006.png")
        screen.next_page()
        assert _shown(screen) == ("page-007.png", "")
        screen.next_page()  # the last page: nothing new
        assert _shown(screen) == ("page-007.png", "")
        screen.prev_page()
        assert _shown(screen) == ("page-005.png", "page-006.png")
        screen.prev_page()
        screen.prev_page()
        assert _shown(screen) == ("page-001.png", "page-002.png")

    def test_an_odd_last_page_stands_alone(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        for name in SEVEN_PAGES[:5]:
            (tmp_path / name).write_bytes(b"")
        _spread(screen)
        _open(screen, tmp_path)
        screen.next_page()
        screen.next_page()
        assert _shown(screen) == ("page-005.png", "")

    def test_a_single_page_shows_one_at_a_time_as_before(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        for name in SEVEN_PAGES:
            (tmp_path / name).write_bytes(b"")
        _open(screen, tmp_path)
        screen.next_page()
        assert _shown(screen) == ("page-002.png", "")
        assert not [line for line in loguru_sink if "Document right page" in line]

    def test_a_layout_change_under_an_open_document_pairs_the_current_page(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        for name in SEVEN_PAGES:
            (tmp_path / name).write_bytes(b"")
        _open(screen, tmp_path)
        screen.next_page()
        screen.next_page()
        screen.next_page()  # page 4, a pair's right page on the spread
        _spread(screen)
        assert _shown(screen) == ("page-003.png", "page-004.png")
        screen.layout_mode = MainLayoutMode.SINGLE.value
        screen.on_layout_mode(screen, screen.layout_mode)
        assert _shown(screen) == ("page-003.png", "")

    def test_a_layout_change_under_a_closed_document_leaves_its_resume_page(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        """A closed reader is not laid out again: that moved the page it resumes at."""
        for name in SEVEN_PAGES:
            (tmp_path / name).write_bytes(b"")
        _open(screen, tmp_path)
        screen.next_page()
        screen.next_page()
        screen.next_page()  # page 4, a pair's right page on the spread
        with patch.object(document_reader_module, "Window"):
            screen.close()
        pages_shown = len([line for line in loguru_sink if "Document page" in line])

        _spread(screen)
        screen.layout_mode = MainLayoutMode.SINGLE.value
        screen.on_layout_mode(screen, screen.layout_mode)

        assert len([line for line in loguru_sink if "Document page" in line]) == pages_shown
        _open(screen, tmp_path, resume=True)
        assert _shown(screen) == ("page-004.png", "")

    def test_go_to_story_offers_both_pages_stories(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        for name in SEVEN_PAGES[:3]:
            (tmp_path / name).write_bytes(b"")
        _write_links(tmp_path / "page-001.png", _figure(Titles.LOST_IN_THE_ANDES, "7"))
        _write_links(tmp_path / "page-002.png", _figure(Titles.VOODOO_HOODOO, "2", figure=2))
        _spread(screen)
        _open(screen, tmp_path)
        assert [link.title for link in screen._story_links] == [
            Titles.LOST_IN_THE_ANDES,
            Titles.VOODOO_HOODOO,
        ]
        assert screen.has_story_links is True
        screen.next_page()
        assert screen.has_story_links is False

    def test_a_resumed_document_comes_back_at_its_pair(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        for name in SEVEN_PAGES:
            (tmp_path / name).write_bytes(b"")
        _spread(screen)
        _open(screen, tmp_path)
        screen.next_page()
        screen.next_page()
        _open(screen, tmp_path, resume=True)
        assert _shown(screen) == ("page-005.png", "page-006.png")


class TestFullscreen:
    """The bar's Fullscreen, as the comic reader's: the bar hides, and a close comes back."""

    def test_the_toggle_asks_the_window_for_the_other_mode(
        self, screen: DocumentReaderScreen
    ) -> None:
        screen._mode = MagicMock()
        screen.toggle_screen_mode()
        screen._mode.toggle.assert_called_once()

    def test_fullscreen_hides_the_bar_and_offers_windowed(
        self, screen: DocumentReaderScreen, windowed: MagicMock, loguru_sink: list[str]
    ) -> None:
        windowed.is_fullscreen_now.return_value = True
        with patch.object(document_reader_module, "log_window_geometry"):
            screen._on_finished_goto_fullscreen_mode()
        assert screen.is_fullscreen is True
        assert screen.ids["doc_action_bar"].disabled is True
        assert screen.ids["doc_action_bar"].height == 0
        assert screen.ids["fullscreen_button"].text == "Windowed"
        assert "Entered fullscreen mode on DocumentReaderScreen." in loguru_sink

    def test_windowed_shows_the_bar_and_offers_fullscreen(
        self, screen: DocumentReaderScreen, loguru_sink: list[str]
    ) -> None:
        screen.is_fullscreen = True
        screen._update_widget_states()
        with patch.object(document_reader_module, "log_window_geometry"):
            screen._on_finished_goto_windowed_mode()
        assert screen.is_fullscreen is False
        assert screen.ids["doc_action_bar"].disabled is False
        assert screen.ids["fullscreen_button"].text == "Fullscreen"
        assert "Entered windowed mode on DocumentReaderScreen." in loguru_sink

    def test_a_document_opens_in_the_window_mode_it_finds(
        self, screen: DocumentReaderScreen, tmp_path: Path, windowed: MagicMock
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        windowed.is_fullscreen_now.return_value = True
        _open(screen, tmp_path)
        assert screen.is_fullscreen is True
        assert screen.ids["doc_action_bar"].disabled is True
        assert screen._was_fullscreen_on_entry is True

    def test_a_tap_on_the_top_margin_brings_a_hidden_bar_back(
        self, screen: DocumentReaderScreen, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _open(screen, tmp_path)
        screen.is_fullscreen = True
        screen._update_widget_states()
        bar = screen.ids["doc_action_bar"]
        bar.collide_point.return_value = False
        page = MagicMock()
        page.collide_point.return_value = True
        screen.ids["doc_page"] = page
        screen.size = (800, 600)
        with patch.object(screen, "_clear_menu_on_touch"):
            assert screen.on_touch_down(MagicMock(pos=(400, 590), x=400, y=590)) is True
        assert bar.disabled is False
        assert "Showing action bar on top margin press." in loguru_sink
        assert screen._current_page_index == 0  # not a page turn

    def test_a_close_in_the_entry_mode_leaves_at_once(
        self, screen: DocumentReaderScreen, tmp_path: Path
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _open(screen, tmp_path)
        with patch.object(document_reader_module, "Window"):
            screen.close()
        screen._on_close_screen.assert_called_once()
        assert screen._is_closing is False

    def test_a_close_from_a_changed_mode_waits_for_the_window_to_come_back(
        self, screen: DocumentReaderScreen, tmp_path: Path, windowed: MagicMock
    ) -> None:
        (tmp_path / "page-001.png").write_bytes(b"")
        _open(screen, tmp_path)  # windowed on entry
        windowed.is_fullscreen_now.return_value = True  # fullscreen since
        screen._mode = MagicMock()
        with patch.object(document_reader_module, "Window"):
            screen.close()
        screen._mode.goto_windowed.assert_called_once()
        screen._on_close_screen.assert_not_called()
        assert screen._is_closing is True
        # Keys and taps have nothing left to act on.
        assert screen._on_key_down(None, 0, 0, "", []) is True
        assert screen.on_touch_down(MagicMock(pos=(5, 5), x=5, y=5)) is True
        # Then the window lands, and the screen leaves once laid out for it.
        windowed.is_fullscreen_now.return_value = False
        with (
            patch.object(document_reader_module, "log_window_geometry"),
            patch.object(screen, "_fills_window", return_value=True),
            patch.object(document_reader_module, "Clock") as clock,
        ):
            screen._on_finished_goto_windowed_mode()
            clock.schedule_once.assert_called_once()
            clock.schedule_once.call_args[0][0](0)
        screen._on_close_screen.assert_called_once()
        assert screen._is_closing is False

    def test_a_close_never_waits_past_the_frame_budget(self, screen: DocumentReaderScreen) -> None:
        screen._is_closing = True
        with (
            patch.object(screen, "_fills_window", return_value=False),
            patch.object(document_reader_module, "Clock") as clock,
        ):
            screen._finish_closing_once_laid_out()
            frames = 0
            while clock.schedule_once.call_count > frames:
                frames += 1
                clock.schedule_once.call_args_list[frames - 1][0][0](0)
        assert frames == DocumentReaderScreen._CLOSE_LAYOUT_MAX_FRAMES
        screen._on_close_screen.assert_called_once()
