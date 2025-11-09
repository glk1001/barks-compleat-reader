from dataclasses import dataclass
from datetime import datetime


@dataclass
class Timing:
    start_time: datetime | None = None
    end_time: datetime | None = None

    def get_elapsed_time_in_seconds(self) -> int:
        assert self.start_time is not None
        assert self.end_time is not None

        elapsed_time = self.end_time - self.start_time
        return int(round(elapsed_time.total_seconds(), 1))

    def get_elapsed_time_in_microseconds(self) -> int:
        assert self.start_time is not None
        assert self.end_time is not None

        elapsed_time = self.end_time - self.start_time
        return int(round(elapsed_time.microseconds, 1))

    def get_elapsed_time_with_unit(self) -> str:
        assert self.start_time is not None
        assert self.end_time is not None

        elapsed_time = self.end_time - self.start_time

        elapsed_time_in_seconds = int(round(elapsed_time.total_seconds(), 1))
        if elapsed_time_in_seconds > 0:
            return f"{elapsed_time_in_seconds}s"

        elapsed_time_in_milliseconds = int(round(elapsed_time.microseconds / 1000.0, 1))
        return f"{elapsed_time_in_milliseconds}ms"
