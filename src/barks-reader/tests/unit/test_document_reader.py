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
