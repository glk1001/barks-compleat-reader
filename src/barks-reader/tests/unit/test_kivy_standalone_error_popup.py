"""The crash popup: what it shows, its details toggle, and its Save, Copy and OK buttons.

The widgets are real, built on the test process's window; the clock never runs
here, so what the popup schedules (the title's reset, the scroll back to the top)
is caught and run by hand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import kivy.clock
import kivy.core.clipboard
import pytest
from barks_reader.core import reader_utils
from barks_reader.ui import kivy_standalone_error_popup, kivy_standalone_show_message
from kivy.config import Config
from kivy.uix.button import Button
from kivy.uix.label import Label

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_DETAILS = "Traceback [b]line 1[/b]\nline 2"


@pytest.fixture
def clock() -> Iterator[MagicMock]:
    with patch.object(kivy.clock, "Clock") as fake_clock:
        yield fake_clock


@pytest.fixture
def clipboard() -> Iterator[MagicMock]:
    with patch.object(kivy.core.clipboard, "Clipboard") as fake_clipboard:
        yield fake_clipboard


def _content(log_path: str = "/logs/app.log", **kwargs: Any) -> Any:  # noqa: ANN401
    return kivy_standalone_error_popup._get_error_content(  # noqa: SLF001
        title="Barks Reader", message="Something [b]broke[/b]", log_path=log_path, **kwargs
    )


def _texts(widget: Any) -> list[str]:  # noqa: ANN401
    return [w.text for w in widget.walk() if isinstance(w, Label)]


def _button(content: Any, text: str) -> Button:  # noqa: ANN401
    return next(w for w in content.walk() if isinstance(w, Button) and w.text == text)


def _logged(sink: list[str], start: str) -> bool:
    """Return whether a line starts so: an exception's line carries its traceback."""
    return any(line.startswith(start) for line in sink)


def _run_last_scheduled(clock: MagicMock) -> None:
    callback = clock.schedule_once.call_args.args[0]
    callback(0)


@pytest.mark.usefixtures("clock", "clipboard")
class TestContent:
    def test_the_banner_names_the_severity(self) -> None:
        texts = _texts(_content(severity="CRITICAL"))
        assert "ꕕ Barks Reader Critical" in texts

    @pytest.mark.parametrize(
        ("severity", "background"),
        [("warning", [0.9, 0.7, 0.2, 1]), ("no-such-level", [0.9, 0.3, 0.3, 1])],
    )
    def test_an_unknown_severity_is_coloured_as_an_error(
        self, severity: str, background: list[float]
    ) -> None:
        content = _content(severity=severity)
        scheme = content.colors.get(content.severity, content.colors["error"])
        assert scheme["bg"] == background

    def test_the_message_and_the_log_path_are_shown(self) -> None:
        texts = _texts(_content())
        assert "Something [b]broke[/b]" in texts
        assert 'Check the log for more info:\n\n[b]"/logs/app.log".[/b]' in texts

    def test_without_a_log_it_says_so(self) -> None:
        assert "No log file available." in _texts(_content(log_path=""))

    def test_the_three_buttons_are_there_and_no_toggle_without_details(self) -> None:
        texts = _texts(_content())
        assert {"Save to File", "Copy to Clipboard", "OK"} <= set(texts)
        assert "▼ Show Details" not in texts

    def test_the_copy_holds_the_message_and_details_without_markup(self) -> None:
        content = _content(details=_DETAILS)
        assert content.full_message == "Something broke\n\nTraceback line 1\nline 2"

    def test_the_background_follows_the_widget(self) -> None:
        content = _content()
        content.pos = (100, 200)
        content.size = (300, 400)
        assert tuple(content.bg_rect.pos) == (100, 200)
        assert tuple(content.shadow_rect.pos) == (105, 195)
        assert tuple(content.shadow_rect.size) == (300, 400)

    def test_the_banner_background_follows_the_banner(self) -> None:
        content = _content()
        banner = content.children[-1]
        banner.pos = (7, 8)
        banner.size = (500, 60)
        assert tuple(content.severity_bgnd.pos) == (7, 8)
        assert tuple(content.severity_bgnd.size) == (500, 60)

    def test_the_message_wraps_to_its_width_and_takes_its_height(self) -> None:
        content = _content()
        content.label_msg.width = 300
        assert tuple(content.label_msg.text_size) == (260, None)
        assert content.label_msg.height == content.label_msg.texture_size[1]


@pytest.mark.usefixtures("clipboard")
class TestDetails:
    def test_details_start_hidden_behind_a_toggle(self, clock: MagicMock) -> None:
        content = _content(details=_DETAILS)
        assert content.btn_toggle.text == "▼ Show Details"
        assert content.label_details.parent is None
        clock.schedule_once.assert_not_called()

    def test_the_toggle_shows_them_under_the_log_and_scrolls_to_the_top(
        self, clock: MagicMock
    ) -> None:
        content = _content(details=_DETAILS)
        content.scroll_view.scroll_y = 0

        _button(content, "▼ Show Details").dispatch("on_press")

        assert content.btn_toggle.text == "▲ Hide Details"
        texts = _texts(content.scroll_content)
        log_at = texts.index('Check the log for more info:\n\n[b]"/logs/app.log".[/b]')
        assert texts[log_at + 1 : log_at + 3] == [
            "[b]Error Details[/b]",
            "Traceback [b]line 1[/b]\nline 2",
        ]
        _run_last_scheduled(clock)
        assert content.scroll_view.scroll_y == 1

    def test_the_toggle_hides_them_again(self) -> None:
        content = _content(details=_DETAILS)
        before = list(content.scroll_content.children)

        content.toggle_details()
        content.toggle_details()

        assert content.btn_toggle.text == "▼ Show Details"
        assert content.label_details.parent is None
        assert content.heading_details.parent is None
        assert list(content.scroll_content.children) == before

    def test_they_can_start_shown(self) -> None:
        content = _content(details=_DETAILS, show_details=True)
        assert content.btn_toggle.text == "▲ Hide Details"
        assert content.label_details.parent is content.scroll_content


@pytest.mark.usefixtures("clipboard")
class TestSave:
    def test_it_saves_a_report_beside_the_log(
        self, tmp_path: Path, clock: MagicMock, loguru_sink: list[str]
    ) -> None:
        content = _content(log_path=str(tmp_path / "app.log"), details=_DETAILS)
        content.popup_ref = MagicMock()

        _button(content, "Save to File").dispatch("on_press")

        (report,) = tmp_path.glob("barks-reader-error-details-*.txt")
        text = report.read_text(encoding="utf-8")
        assert text.startswith("Barks Reader Error Report\n")
        assert "Severity: ERROR\n" in text
        assert text.endswith("Something broke\n\nTraceback line 1\nline 2")
        assert f'Error saved to "{report}".' in loguru_sink
        assert content.popup_ref.title == f'Error Information: Saved to "{report}"'
        _run_last_scheduled(clock)
        assert content.popup_ref.title == ""

    def test_without_a_log_it_saves_in_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        content = _content(log_path="")

        content.save_to_file()

        assert len(list(tmp_path.glob("barks-reader-error-details-*.txt"))) == 1

    def test_a_failed_save_is_logged_and_shown(
        self, tmp_path: Path, clock: MagicMock, loguru_sink: list[str]
    ) -> None:
        content = _content(log_path=str(tmp_path / "no-such-dir" / "app.log"))
        content.popup_ref = MagicMock()

        content.save_to_file()

        assert _logged(loguru_sink, "Failed to save error to file:")
        assert content.popup_ref.title == "Error Information (Save Failed!)"
        _run_last_scheduled(clock)
        assert content.popup_ref.title == ""

    @pytest.mark.usefixtures("clock")
    def test_without_a_popup_nothing_is_retitled(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        _content(log_path=str(tmp_path / "app.log")).save_to_file()
        _content(log_path=str(tmp_path / "no-such-dir" / "app.log")).save_to_file()

        assert _logged(loguru_sink, "Failed to save error to file:")


class TestCopyAndOk:
    def test_copy_puts_the_plain_text_on_the_clipboard(
        self, clock: MagicMock, clipboard: MagicMock, loguru_sink: list[str]
    ) -> None:
        content = _content(details=_DETAILS)
        content.popup_ref = MagicMock()

        _button(content, "Copy to Clipboard").dispatch("on_press")

        clipboard.copy.assert_called_once_with("Something broke\n\nTraceback line 1\nline 2")
        assert "Error message copied to clipboard" in loguru_sink
        assert content.popup_ref.title == "Error Information: Copied to clipboard"
        _run_last_scheduled(clock)
        assert content.popup_ref.title == ""

    @pytest.mark.usefixtures("clock")
    def test_a_copy_without_a_popup_is_only_logged(
        self, clipboard: MagicMock, loguru_sink: list[str]
    ) -> None:
        _content().copy_to_clipboard()

        clipboard.copy.assert_called_once_with("Something broke")
        assert "Error message copied to clipboard" in loguru_sink

    @pytest.mark.usefixtures("clock")
    def test_a_failed_copy_is_logged(self, clipboard: MagicMock, loguru_sink: list[str]) -> None:
        clipboard.copy.side_effect = RuntimeError("no clipboard")
        content = _content()

        content.copy_to_clipboard()

        assert _logged(loguru_sink, "Failed to copy to clipboard:")

    @pytest.mark.usefixtures("clock", "clipboard")
    def test_ok_closes_the_popup(self) -> None:
        content = _content()
        content.popup_ref = MagicMock()

        _button(content, "OK").dispatch("on_press")

        content.popup_ref.dismiss.assert_called_once_with()

    @pytest.mark.usefixtures("clock", "clipboard")
    def test_ok_before_the_popup_exists_does_nothing(self) -> None:
        _content().dismiss_popup()


@pytest.mark.usefixtures("clock", "clipboard")
def test_show_error_popup_places_the_window_and_shows_the_content(tmp_path: Path) -> None:
    background = tmp_path / "error-background.png"
    with (
        patch.object(
            reader_utils, "get_centred_position_on_primary_monitor", return_value=(10, 20)
        ) as centred,
        patch.object(Config, "set") as config_set,
        patch.object(kivy_standalone_show_message, "show_standalone_popup") as show,
    ):
        kivy_standalone_error_popup.show_error_popup(
            title_bar_text="Installer",
            title="Barks Reader Installation",
            message="Could not find the data pack",
            log_path="/logs/installer.log",
            severity="critical",
            details=_DETAILS,
            show_details=True,
            size=(640, 480),
            background_image_file=background,
        )

    centred.assert_called_once_with(640, 480)
    assert [c.args for c in config_set.call_args_list] == [
        ("graphics", "left", 10),
        ("graphics", "top", 20),
        ("graphics", "width", 640),
        ("graphics", "height", 480),
    ]
    kwargs = show.call_args.kwargs
    assert kwargs["title"] == "Installer Critical"
    assert kwargs["timeout"] == 0
    assert kwargs["auto_dismiss"] is False
    assert kwargs["background_image_file"] == background
    content = kwargs["content"]
    assert content.message == "Could not find the data pack"
    assert content.log_path == "/logs/installer.log"
    assert content.details_visible
