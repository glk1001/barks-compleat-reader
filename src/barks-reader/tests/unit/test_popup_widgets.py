"""The confirm popup's keyboard driver, and the log lines that mark its outcome."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.ui import popup_widgets
from barks_reader.ui.popup_widgets import _ConfirmPopupNav
from barks_reader.ui.reader_keyboard_nav import KEY_ENTER, KEY_ESCAPE, KEY_RIGHT


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


def _message_nav(
    ok_text: str, on_ok: MagicMock, on_cancel: MagicMock, title: str = "Volume Missing"
) -> tuple[_ConfirmPopupNav, MagicMock]:
    popup = MagicMock()
    popup.ok_text = ok_text
    popup.cancel_text = "Close" if not ok_text else "Cancel"
    with patch.object(popup_widgets, "Window"):
        nav = _ConfirmPopupNav(
            popup,
            on_ok,
            title,
            on_cancel=on_cancel,
            markers=popup_widgets._MESSAGE_MARKERS,  # noqa: SLF001
        )
    return nav, popup


def _press(nav: _ConfirmPopupNav, key: int) -> bool:
    return nav._on_key_down(None, key, 0, "", [])  # noqa: SLF001


class TestMessagePopupNav:
    """The error popups: a remote had no way out of them before (auto_dismiss is off)."""

    def test_a_close_only_popup_closes_on_enter(self, loguru_sink: list[str]) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        nav, popup = _message_nav("", on_ok, on_cancel)
        assert _press(nav, KEY_ENTER) is True
        popup.dismiss.assert_called_once()
        on_cancel.assert_called_once()
        on_ok.assert_not_called()
        assert 'Message popup "Volume Missing": cancelled.' in loguru_sink

    def test_a_close_only_popup_closes_on_escape_and_ignores_left_right(self) -> None:
        on_cancel = MagicMock()
        nav, popup = _message_nav("", MagicMock(), on_cancel)
        assert _press(nav, KEY_RIGHT) is True  # one button: the ring stays on it
        popup.dismiss.assert_not_called()
        _press(nav, KEY_ESCAPE)
        on_cancel.assert_called_once()

    def test_two_buttons_start_on_the_first_and_enter_presses_it(
        self, loguru_sink: list[str]
    ) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        nav, popup = _message_nav("Settings", on_ok, on_cancel, "Settings Error")
        popup.ok_text = "Settings"
        _press(nav, KEY_ENTER)
        on_ok.assert_called_once()
        on_cancel.assert_not_called()
        assert 'Message popup "Settings Error": Settings pressed.' in loguru_sink

    def test_right_then_enter_is_cancel(self) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        nav, _ = _message_nav("Settings", on_ok, on_cancel)
        _press(nav, KEY_RIGHT)
        _press(nav, KEY_ENTER)
        on_cancel.assert_called_once()
        on_ok.assert_not_called()

    def test_closing_is_logged_as_a_message_popup(self, loguru_sink: list[str]) -> None:
        nav, popup = _message_nav("", MagicMock(), MagicMock())
        nav._on_parent(popup, None)  # noqa: SLF001
        assert 'Message popup "Volume Missing": closed.' in loguru_sink


def test_open_message_popup_opens_next_frame_and_logs(loguru_sink: list[str]) -> None:
    with (
        patch.object(popup_widgets, "MessagePopup") as popup_cls,
        patch.object(popup_widgets, "Window"),
        patch.object(popup_widgets, "Clock") as clock,
        patch.object(popup_widgets, "update_focus_in_list"),
    ):
        popup_cls.return_value.ok_text = ""
        popup_cls.return_value.cancel_text = "Close"
        popup_widgets.open_message_popup(
            title="T", text="x", ok_text="", on_ok=None, cancel_text="Close", on_cancel=None
        )
        popup_cls.return_value.open.assert_not_called()
        clock.schedule_once.call_args.args[0](0)
    popup_cls.return_value.open.assert_called_once()
    assert 'Message popup opened: "T".' in loguru_sink
