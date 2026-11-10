"""The request service: a file a GUI test writes to, polled and answered on the clock."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from barks_reader.ui import memory_census as ui_memory_census
from barks_reader.ui import request_service
from barks_reader.ui.request_service import install_request_service
from kivy.clock import Clock

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_ENV_VAR = "BARKS_READER_TEST_REQUEST_FILE"


def test_nothing_is_polled_with_the_variable_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ENV_VAR, raising=False)
    with patch.object(Clock, "schedule_interval") as schedule:
        assert install_request_service(_ENV_VAR, "Test", MagicMock()) is False
    schedule.assert_not_called()


def test_each_request_is_answered_once_with_its_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loguru_sink: list[str]
) -> None:
    request_file = tmp_path / "request"
    monkeypatch.setenv(_ENV_VAR, str(request_file))
    answer = MagicMock()
    with patch.object(Clock, "schedule_interval") as schedule:
        assert install_request_service(_ENV_VAR, "Test", answer) is True
    poll, interval = schedule.call_args.args
    assert interval == request_service.POLL_SECS
    assert f"Test: answering requests in {request_file}." in loguru_sink

    poll(0)  # nothing asked yet
    answer.assert_not_called()

    request_file.write_text("7\n", encoding="utf-8")
    poll(0)
    poll(0)

    answer.assert_called_once_with("7", tmp_path)
    assert not request_file.exists()


def test_the_poll_is_held_for_the_clock_holds_it_only_weakly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(_ENV_VAR, str(tmp_path / "request"))
    with patch.object(Clock, "schedule_interval") as schedule:
        install_request_service(_ENV_VAR, "Test", MagicMock())
    assert schedule.call_args.args[0] in request_service._SERVICES  # noqa: SLF001


def test_a_memory_census_request_is_answered_by_its_id_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request_file = tmp_path / "census-request"
    monkeypatch.setenv(ui_memory_census.MEMORY_CENSUS_FILE_ENV_VAR, str(request_file))
    with patch.object(Clock, "schedule_interval") as schedule:
        assert ui_memory_census.install_memory_census_service() is True

    request_file.write_text("3\n", encoding="utf-8")
    with patch.object(ui_memory_census, "answer") as answer:
        schedule.call_args.args[0](0)

    answer.assert_called_once_with("3")
