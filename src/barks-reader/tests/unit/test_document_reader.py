# ruff: noqa: SLF001
"""The document reader: page paths, turning, and the log lines that mark each step."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
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
            instance.ids = {"close_button": MagicMock()}

        mock_init.side_effect = side_effect
        built = DocumentReaderScreen(font_manager=MagicMock(), on_close_screen=MagicMock())
        built._menu_mode = False
        return built


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
