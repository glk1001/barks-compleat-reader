# ruff: noqa: SLF001
"""The document reader: page paths, turning, and the log lines that mark each step."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.document_links import StoryLink
from barks_reader.ui import document_reader as document_reader_module
from barks_reader.ui.document_reader import DocumentReaderScreen
from barks_reader.ui.reader_screens import ReaderScreen

if TYPE_CHECKING:
    from pathlib import Path

PAGES = ("01.png", "02.jpg")
TWICE = 2


@pytest.fixture
def screen() -> DocumentReaderScreen:
    with (
        patch.object(ReaderScreen, "__init__", autospec=True) as mock_init,
        patch.object(DocumentReaderScreen, "_setup_action_bar_nav"),
    ):

        def side_effect(instance: DocumentReaderScreen, **_kwargs: object) -> None:
            instance.ids = {"close_button": MagicMock(), "goto_story_button": MagicMock()}

        mock_init.side_effect = side_effect
        built = DocumentReaderScreen(
            font_manager=MagicMock(), on_close_screen=MagicMock(), on_goto_story=MagicMock()
        )
        built._menu_mode = False
        return built


def _figure(title: Titles, page: str, figure: int = 1) -> dict[str, object]:
    return {"figure": figure, "title": title.name, "page": page, "box": [0, 0, 1, 1]}


def _write_links(page: Path, *figures: dict[str, object]) -> None:
    page.with_suffix(".json").write_text(json.dumps({"figures": list(figures)}), encoding="utf-8")


def _open(screen: DocumentReaderScreen, doc_dir: Path, title: str = "How To") -> None:
    with (
        patch.object(document_reader_module, "Window"),
        patch.object(document_reader_module, "get_action_bar_title", return_value=title),
    ):
        screen.open_document(doc_dir, title)


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
        off_it = MagicMock()
        off_it.collide_point.return_value = False
        screen.ids = {"doc_action_bar": off_it, "doc_page": off_it}
        with (
            patch.object(screen, "_clear_menu_on_touch"),
            patch.object(ReaderScreen, "on_touch_down", return_value=True) as screen_press,
        ):
            assert screen.on_touch_down(MagicMock(pos=(5, 5), x=5)) is True
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
        with patch.object(document_reader_module, "Window"):
            screen._open_goto_story(keyboard_initiated=True)
        screen._on_close_screen.assert_called_once()
        screen._on_goto_story.assert_called_once_with(
            Titles.LOST_IN_THE_ANDES, "7", keyboard_initiated=True
        )
        assert 'Document goto story: "LOST_IN_THE_ANDES", page 7.' in loguru_sink

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
