from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DisplayUnit:
    """Represents one reading unit: either a solo page or a left+right page pair."""

    left_page_index: int
    right_page_index: int | None
