"""The confirm and message popups on the shared frame, and the log lines that mark them."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.keys import KEY_ENTER, KEY_ESCAPE, KEY_RIGHT
from barks_reader.core.popup_frame import PopupSize
from barks_reader.ui import popup_frame, popup_widgets
from barks_reader.ui.popup_frame import PopupFrame
from kivy.uix.label import Label

if TYPE_CHECKING:
    from collections.abc import Iterator

FONT_SIZE = 20


@pytest.fixture(autouse=True)
def _app_fonts() -> Iterator[None]:
    fm = MagicMock(
        error_popup_font_size=FONT_SIZE, message_title_size=18, error_popup_button_font_size=16
    )
    with (
        patch.object(popup_widgets, "_font_manager", return_value=fm),
        patch.object(popup_frame, "Window") as window,
        patch.object(PopupFrame, "open"),
        patch.object(PopupFrame, "dismiss"),
    ):
        window.width, window.height = 1760, 1300
        yield


def _confirm(on_ok: MagicMock, on_cancel: MagicMock | None = None) -> PopupFrame:
    return popup_widgets.open_confirm_popup(
        title="Quit",
        text="Quit the Barks Reader?",
        ok_text="Quit",
        cancel_text="Stay",
        on_ok=on_ok,
        bg_image="art.png",
        on_cancel=on_cancel,
    )


def _message(
    ok_text: str,
    on_ok: MagicMock | None,
    on_cancel: MagicMock | None,
    title: str = "Volume Missing",
    **kwargs: bool,
) -> PopupFrame:
    with patch.object(popup_widgets, "Clock"):
        return popup_widgets.open_message_popup(
            title=title,
            text="A message.",
            ok_text=ok_text,
            on_ok=on_ok,
            cancel_text="Cancel" if ok_text else "Close",
            on_cancel=on_cancel,
            **kwargs,
        )


def _press(frame: PopupFrame, key: int) -> bool:
    return frame._on_key_down(None, key, 0, "", [])  # noqa: SLF001


def _body(frame: PopupFrame) -> Label:
    bodies = ("Quit the Barks Reader?", "A message.")
    return next(w for w in frame.walk() if isinstance(w, Label) and w.text in bodies)


class TestConfirmPopup:
    """A confirm closes and runs its callback; a cancel closes and runs its own. Both logged."""

    def test_it_opens_at_once_and_logs(self, loguru_sink: list[str]) -> None:
        frame = _confirm(MagicMock())
        frame.open.assert_called_once_with()  # ty: ignore[unresolved-attribute]
        assert 'Confirm popup opened: "Quit".' in loguru_sink

    def test_a_question_is_small_centred_large_text_over_its_art(self) -> None:
        frame = _confirm(MagicMock())
        assert frame.size_class is PopupSize.SMALL
        assert _body(frame).halign == "center"
        assert _body(frame).font_size == pytest.approx(
            popup_widgets.QUESTION_FONT_SCALE * FONT_SIZE
        )
        assert any(getattr(w, "source", "") == "art.png" for w in frame.walk())
        assert [b.text for b in frame.button_widgets] == ["Quit", "Stay"]

    def test_enter_confirms_logs_and_runs_on_ok(self, loguru_sink: list[str]) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        frame = _confirm(on_ok, on_cancel)
        assert _press(frame, KEY_ENTER) is True
        frame.dismiss.assert_called_once_with()  # ty: ignore[unresolved-attribute]
        on_ok.assert_called_once_with()
        on_cancel.assert_not_called()
        assert 'Confirm popup "Quit": confirmed.' in loguru_sink

    def test_escape_cancels_logs_and_leaves_on_ok_alone(self, loguru_sink: list[str]) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        _press(_confirm(on_ok, on_cancel), KEY_ESCAPE)
        on_cancel.assert_called_once_with()
        on_ok.assert_not_called()
        assert 'Confirm popup "Quit": cancelled.' in loguru_sink

    def test_a_cancel_with_nothing_to_run_only_closes(self, loguru_sink: list[str]) -> None:
        _press(_confirm(MagicMock()), KEY_ESCAPE)
        assert 'Confirm popup "Quit": cancelled.' in loguru_sink

    def test_closing_is_logged_when_the_popup_leaves_the_window(
        self, loguru_sink: list[str]
    ) -> None:
        """A driver waits on this line before its next key.

        The main screen ignores keys while a modal is still on the window, and
        Kivy keeps a dismissed popup there through its fade-out, so the
        dismissal itself is too early to log it.
        """
        frame = _confirm(MagicMock())
        _press(frame, KEY_ESCAPE)
        assert 'Confirm popup "Quit": closed.' not in loguru_sink
        frame._on_parent(frame, None)  # noqa: SLF001  (removed after the fade)
        assert 'Confirm popup "Quit": closed.' in loguru_sink


class TestMessagePopup:
    """The error popups: a remote had no way out of them before (auto_dismiss is off)."""

    def test_it_opens_next_frame_and_logs(self, loguru_sink: list[str]) -> None:
        with patch.object(popup_widgets, "Clock") as clock:
            frame = popup_widgets.open_message_popup(
                title="T", text="x", ok_text="", on_ok=None, cancel_text="Close", on_cancel=None
            )
            frame.open.assert_not_called()  # ty: ignore[unresolved-attribute]
            clock.schedule_once.call_args.args[0](0)
        frame.open.assert_called_once_with()  # ty: ignore[unresolved-attribute]
        assert 'Message popup opened: "T".' in loguru_sink

    def test_a_message_is_medium_and_left_aligned_unless_asked_otherwise(self) -> None:
        # Justified, a message's lines stretched into wide gaps in the popup's narrow column.
        frame = _message("", None, None)
        assert frame.size_class is PopupSize.MEDIUM
        assert _body(frame).halign == "left"
        assert _body(frame).font_size == FONT_SIZE
        assert _body(_message("", None, None, centred=True)).halign == "center"

    def test_a_close_only_popup_closes_on_enter(self, loguru_sink: list[str]) -> None:
        on_cancel = MagicMock()
        frame = _message("", None, on_cancel)
        assert [b.text for b in frame.button_widgets] == ["Close"]
        assert _press(frame, KEY_ENTER) is True
        frame.dismiss.assert_called_once_with()  # ty: ignore[unresolved-attribute]
        on_cancel.assert_called_once_with()
        assert 'Message popup "Volume Missing": cancelled.' in loguru_sink

    def test_a_close_only_popup_closes_on_escape_and_ignores_left_right(self) -> None:
        on_cancel = MagicMock()
        frame = _message("", None, on_cancel)
        assert _press(frame, KEY_RIGHT) is True  # one button: the ring stays on it
        frame.dismiss.assert_not_called()  # ty: ignore[unresolved-attribute]
        _press(frame, KEY_ESCAPE)
        on_cancel.assert_called_once_with()

    def test_two_buttons_start_on_the_first_and_enter_presses_it(
        self, loguru_sink: list[str]
    ) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        frame = _message("Settings", on_ok, on_cancel, "Settings Error")
        _press(frame, KEY_ENTER)
        on_ok.assert_called_once_with()
        on_cancel.assert_not_called()
        assert 'Message popup "Settings Error": Settings pressed.' in loguru_sink

    def test_right_then_enter_is_cancel(self) -> None:
        on_ok, on_cancel = MagicMock(), MagicMock()
        frame = _message("Settings", on_ok, on_cancel)
        with patch.object(popup_frame, "update_focus_in_list"):
            _press(frame, KEY_RIGHT)
        _press(frame, KEY_ENTER)
        on_cancel.assert_called_once_with()
        on_ok.assert_not_called()

    def test_closing_is_logged_as_a_message_popup(self, loguru_sink: list[str]) -> None:
        frame = _message("", None, None)
        frame._on_parent(frame, None)  # noqa: SLF001
        assert 'Message popup "Volume Missing": closed.' in loguru_sink
