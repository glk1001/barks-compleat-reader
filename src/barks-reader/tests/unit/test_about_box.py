"""The About box logs both ends of its life, so a GUI test can wait on its dismissal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from barks_reader.core.popup_frame import PopupSize
from barks_reader.ui import about_box


def test_the_about_box_logs_opening_and_dismissal(loguru_sink: list[str]) -> None:
    with (
        patch.object(about_box, "BoxLayout"),
        patch.object(about_box, "Label"),
        patch.object(about_box, "theme"),
        patch.object(about_box, "show_standalone_popup") as show,
    ):
        about_box.show_about_box(MagicMock(), Path("/art/about.png"))
    assert "About box opened." in loguru_sink

    on_dismiss = show.call_args.kwargs["on_dismiss"]
    on_dismiss()
    assert loguru_sink[-1] == "About box dismissed."


def test_a_dismiss_callback_runs_after_the_dismissal_is_logged(loguru_sink: list[str]) -> None:
    seen: list[str] = []
    with (
        patch.object(about_box, "BoxLayout"),
        patch.object(about_box, "Label"),
        patch.object(about_box, "theme"),
        patch.object(about_box, "show_standalone_popup") as show,
    ):
        about_box.show_about_box(
            MagicMock(),
            Path("/art/about.png"),
            on_dismiss=lambda: seen.append(loguru_sink[-1]),
        )
        show.call_args.kwargs["on_dismiss"]()
    assert seen == ["About box dismissed."]
    # No buttons, so a close X, which Escape lands on first (the frame's rule).
    assert "buttons" not in show.call_args.kwargs
    assert show.call_args.kwargs["size"] is PopupSize.LARGE
    assert show.call_args.kwargs["fit_body_height"] is True  # no gap under its text


def test_its_lines_are_as_tall_as_their_text_and_the_box_as_its_lines() -> None:
    with (
        patch.object(about_box, "theme") as theme,
        patch.object(about_box, "show_standalone_popup") as show,
    ):
        theme.return_value = MagicMock(
            text_display=(1, 1, 0, 1), app_title=(1, 0.8, 0, 1), text_secondary=(1, 1, 1, 1)
        )
        font_manager = MagicMock(
            about_box_title_font_size=30,
            about_box_title_font_name="Roboto",
            about_box_version_font_size=20,
            about_box_fine_print_font_size=14,
        )
        about_box.show_about_box(font_manager, Path("/art/about.png"))
    content = show.call_args.kwargs["content"]
    lines = list(reversed(content.children))
    assert all(line.size_hint_y is None for line in lines)
    lines[-1].texture_size = (400, 321)
    assert lines[-1].height == 321  # noqa: PLR2004
    content.do_layout()
    assert content.minimum_height > 321  # noqa: PLR2004
    assert content.height == content.minimum_height


def _label_texts(label: MagicMock) -> list[str]:
    return [call.kwargs["text"] for call in label.call_args_list]


def test_the_installed_data_pack_is_named_under_the_version() -> None:
    with (
        patch.object(about_box, "BoxLayout"),
        patch.object(about_box, "Label") as label,
        patch.object(about_box, "theme"),
        patch.object(about_box, "show_standalone_popup"),
    ):
        about_box.show_about_box(
            MagicMock(), Path("/art/about.png"), data_pack_text="Data pack 6 (29 Oct 2026)"
        )
    texts = _label_texts(label)
    assert texts[1].startswith("Version ")
    assert texts[2] == "Data pack 6 (29 Oct 2026)"


def test_without_a_data_pack_line_the_box_is_as_it_was() -> None:
    with (
        patch.object(about_box, "BoxLayout"),
        patch.object(about_box, "Label") as label,
        patch.object(about_box, "theme"),
        patch.object(about_box, "show_standalone_popup"),
    ):
        about_box.show_about_box(MagicMock(), Path("/art/about.png"))
    assert not any(text.startswith("Data pack") for text in _label_texts(label))
