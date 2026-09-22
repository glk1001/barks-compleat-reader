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

    def test_closing_is_logged_when_the_popup_leaves_the_window(
        self, loguru_sink: list[str]
    ) -> None:
        """A driver waits on this line before its next key.

        The main screen ignores keys while a modal is still on the window, and
        Kivy keeps a dismissed popup there through its fade-out, so the
        dismissal itself is too early to log it.
        """
        nav, popup = _nav(MagicMock(), "Clear Reading History")
        closed = 'Confirm popup "Clear Reading History": closed.'
        with patch.object(popup_widgets, "Window"):
            nav._unbind_window()  # noqa: SLF001
        assert closed not in loguru_sink
        nav._on_parent(popup, object())  # noqa: SLF001  (added to the window)
        assert closed not in loguru_sink
        nav._on_parent(popup, None)  # noqa: SLF001  (removed after the fade)
        assert closed in loguru_sink

    def test_the_window_binding_goes_with_the_dismissal(self) -> None:
        nav, popup = _nav(MagicMock())
        popup.bind.assert_called_once()
        assert set(popup.bind.call_args.kwargs) == {"on_dismiss", "parent"}
        with patch.object(popup_widgets, "Window") as window:
            nav._unbind_window()  # noqa: SLF001
        window.unbind.assert_called_once_with(on_key_down=nav._on_key_down)  # noqa: SLF001
