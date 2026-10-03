"""The installer's success screen: where things went, what to do next, and its start button."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from barks_reader import first_run_installer_show_message
from kivy.config import Config
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget

_FANTA = Path("/books/Fantagraphics Carl Barks Library")
_ZIPS = [Path("barks-reader-data-1.barkspack"), Path("barks-reader-data-2.barkspack")]
_CONFIG = Path("/home/u/.config/barks-reader")
_LOG = Path("/home/u/.config/barks-reader/kivy/logs/barks-reader.log")


def _content(
    fanta_dir: Path | None = _FANTA,
    zips: list[Path] | None = _ZIPS,
    config_dir: Path | None = _CONFIG,
    log_path: Path | None = _LOG,
) -> Any:  # noqa: ANN401
    return first_run_installer_show_message._get_installer_success_content(  # noqa: SLF001
        fanta_dir,
        zips,  # ty: ignore[invalid-argument-type]
        config_dir,  # ty: ignore[invalid-argument-type]
        log_path,  # ty: ignore[invalid-argument-type]
    )


def _texts(widget: Widget) -> list[str]:
    return [w.text for w in widget.walk() if isinstance(w, Label)]


def test_it_says_where_everything_went() -> None:
    texts = _texts(_content())

    assert texts[0] == "✅  Installation Completed Successfully"
    assert f'"{_FANTA}"' in texts
    assert f'"{_CONFIG}"' in texts
    assert f'"{_LOG}"' in texts
    assert '"barks-reader-data-1.barkspack" and "barks-reader-data-2.barkspack"' in texts
    assert texts.index("Fantagraphics Library Location") < texts.index("Next Steps")


def test_a_library_not_found_is_a_warning_with_what_to_do() -> None:
    texts = _texts(_content(fanta_dir=None))

    assert "⚠ Your Fantagraphics Carl Barks Library was NOT found." in texts
    assert "You'll need to configure the library location when the app starts." in texts


def test_what_was_not_given_is_not_listed() -> None:
    texts = _texts(_content(zips=None, config_dir=None, log_path=None))

    assert "Default configuration files were written to:" not in texts
    assert "App logging will go to:" not in texts
    assert not any("barkspack" in text for text in texts)


def test_the_text_wraps_to_its_width() -> None:
    content = _content(fanta_dir=None)
    content.size = (600, 900)
    for label in (w for w in content.walk() if isinstance(w, Label)):
        label.size = (500, 30)

    wrapped = [w for w in content.walk() if isinstance(w, Label) and w.text_size[0] is not None]
    assert wrapped
    assert tuple(content._bg.size) == (600, 900)  # noqa: SLF001


def test_start_closes_the_popup_around_it() -> None:
    class _Popup(Widget):
        dismiss = MagicMock()

    content = _content()
    popup = _Popup()
    middle = Widget()
    popup.add_widget(middle)
    middle.add_widget(content)
    start = next(w for w in content.walk() if isinstance(w, Button))
    assert start.text == "🚀  Start Barks Reader"

    start.dispatch("on_press")

    popup.dismiss.assert_called_once_with()


def test_start_outside_a_popup_does_nothing() -> None:
    start = next(w for w in _content().walk() if isinstance(w, Button))
    start.dispatch("on_press")


def test_show_installer_message_places_the_window_and_shows_the_screen(tmp_path: Path) -> None:
    background = tmp_path / "success.png"
    with (
        patch.object(
            first_run_installer_show_message,
            "get_centred_position_on_primary_monitor",
            return_value=(30, 40),
        ),
        patch.object(Config, "set") as config_set,
        patch.object(first_run_installer_show_message, "show_standalone_popup") as show,
    ):
        first_run_installer_show_message.show_installer_message(
            "Installation Complete",
            _FANTA,
            _ZIPS,
            _CONFIG,
            _LOG,
            size=(800, 950),
            background_image_file=background,
        )

    assert [c.args[1:] for c in config_set.call_args_list] == [
        ("left", 30),
        ("top", 40),
        ("width", 800),
        ("height", 950),
    ]
    title, content = show.call_args.args
    assert title == "Installation Complete"
    assert f'"{_FANTA}"' in _texts(content)
    assert show.call_args.kwargs == {
        "size_hint": (0.90, 0.85),
        "add_close_button": False,
        "background_image_file": background,
    }
