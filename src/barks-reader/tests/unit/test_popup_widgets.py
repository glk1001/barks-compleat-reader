"""The confirm popup's keyboard driver, and the log lines that mark its outcome."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.ui import popup_widgets
from barks_reader.ui.popup_widgets import _ConfirmPopupNav


def _nav(on_ok: MagicMock, title: str = "Quit") -> tuple[_ConfirmPopupNav, MagicMock]:
    popup = MagicMock()
    with patch.object(popup_widgets, "Window"):
        return _ConfirmPopupNav(popup, on_ok, title), popup


class TestConfirmPopupNav:
    """A confirm dismisses and runs the callback; a cancel only dismisses. Both are logged."""

    def test_confirm_logs_and_runs_on_ok(self, loguru_sink: list[str]) -> None:
        on_ok = MagicMock()
        nav, popup = _nav(on_ok)
        nav.confirm()
        assert 'Confirm popup "Quit": confirmed.' in loguru_sink
        popup.dismiss.assert_called_once()
        on_ok.assert_called_once()

    def test_cancel_logs_and_leaves_on_ok_alone(self, loguru_sink: list[str]) -> None:
        on_ok = MagicMock()
        nav, popup = _nav(on_ok, "Clear Reading History")
        nav.cancel()
        assert 'Confirm popup "Clear Reading History": cancelled.' in loguru_sink
        popup.dismiss.assert_called_once()
        on_ok.assert_not_called()
