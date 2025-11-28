from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Timing:
    _start_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def restart(self) -> None:
        self._start_time = datetime.now(UTC)

    def get_start_time(self) -> datetime:
        return self._start_time

    def get_elapsed_time_in_seconds(self) -> int:
        assert self._start_time is not None

        end_time = datetime.now(UTC)

        elapsed_time = end_time - self._start_time
        return int(round(elapsed_time.total_seconds(), 1))

    def get_elapsed_time_in_microseconds(self) -> int:
        assert self._start_time is not None

        end_time = datetime.now(UTC)

        elapsed_time = end_time - self._start_time
        return int(round(elapsed_time.microseconds, 1))

    def get_elapsed_time_with_unit(self) -> str:
        assert self._start_time is not None

        end_time = datetime.now(UTC)

        elapsed_time = end_time - self._start_time

        elapsed_time_in_seconds = elapsed_time.total_seconds()
        if elapsed_time_in_seconds > 0.09:  # noqa: PLR2004
            return f"{elapsed_time_in_seconds:.1f}s"

        elapsed_time_in_milliseconds = int(round(elapsed_time.microseconds / 1000.0, 1))
        return f"{elapsed_time_in_milliseconds}ms"
