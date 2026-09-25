"""The About box logs both ends of its life, so a GUI test can wait on its dismissal."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
