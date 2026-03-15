# ruff: noqa: SLF001, PLR2004

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from comic_utils.timing import Timing


class TestTiming:
    def test_restart_resets_start_time(self) -> None:
        t = Timing()
        original_start = t.get_start_time()
        t.restart()
        assert t.get_start_time() >= original_start

    def test_elapsed_time_in_seconds(self) -> None:
        t = Timing()
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        t._start_time = start
        end = start + timedelta(seconds=3)
        with patch("comic_utils.timing.datetime") as mock_dt:
            mock_dt.now.return_value = end
            mock_dt.side_effect = datetime
            result = t.get_elapsed_time_in_seconds()
        assert result == 3

    def test_elapsed_time_with_unit_seconds(self) -> None:
        t = Timing()
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        t._start_time = start
        end = start + timedelta(seconds=1.5)
        with patch("comic_utils.timing.datetime") as mock_dt:
            mock_dt.now.return_value = end
            mock_dt.side_effect = datetime
            result = t.get_elapsed_time_with_unit()
        assert result == "1.5s"

    def test_elapsed_time_with_unit_milliseconds(self) -> None:
        t = Timing()
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        t._start_time = start
        end = start + timedelta(milliseconds=50)
        with patch("comic_utils.timing.datetime") as mock_dt:
            mock_dt.now.return_value = end
            mock_dt.side_effect = datetime
            result = t.get_elapsed_time_with_unit()
        assert result == "50ms"
