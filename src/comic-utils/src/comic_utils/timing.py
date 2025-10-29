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
