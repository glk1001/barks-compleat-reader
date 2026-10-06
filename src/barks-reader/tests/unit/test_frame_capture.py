"""The app's answer to a frame request: its window drawn again off screen, saved as a PNG."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from barks_reader.core import log_markers
from barks_reader.ui import frame_capture
from barks_reader.ui.frame_capture import FRAME_CAPTURE_FILE_ENV_VAR
from kivy.clock import Clock
from kivy.core.window import Window
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_the_window_is_drawn_to_a_png_its_size(tmp_path: Path) -> None:
    out = tmp_path / "frame.png"

    width, height = frame_capture.capture_window(out)

    assert (width, height) == tuple(round(side) for side in Window.size)
    with Image.open(out) as image:
        assert image.size == (width, height)


def test_a_request_is_answered_with_the_png_beside_its_file(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    with patch.object(frame_capture, "capture_window", return_value=(782, 1225)) as capture:
        frame_capture.answer("final", tmp_path)

    capture.assert_called_once_with(tmp_path / "frame-final.png")
    expected = log_markers.FRAME_CAPTURED.format(
        request="final", width=782, height=1225, path=tmp_path / "frame-final.png"
    )
    assert expected in loguru_sink


class TestService:
    def test_nothing_runs_without_the_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(FRAME_CAPTURE_FILE_ENV_VAR, raising=False)
        assert frame_capture.install_frame_capture_service() is False

    def test_a_request_written_to_the_file_is_answered_once(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        request_file = tmp_path / "frame-request"
        monkeypatch.setenv(FRAME_CAPTURE_FILE_ENV_VAR, str(request_file))
        with patch.object(Clock, "schedule_interval") as schedule:
            assert frame_capture.install_frame_capture_service() is True
        poll = schedule.call_args.args[0]
        assert schedule.call_args.args[1] == frame_capture.POLL_SECS

        request_file.write_text("7\n", encoding="utf-8")
        with patch.object(frame_capture, "answer") as answer:
            poll(0)
            poll(0)

        answer.assert_called_once_with("7", tmp_path)
        assert not request_file.exists()
