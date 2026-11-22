"""When the title view's story picture says "Read this story".

The picture is the button that opens the comic, and nothing else on it says so. A
first-time user gets "READ ME!" across it, until the first comic it opens; this
caption follows for the next few, then goes, unless the setting keeps it or turns it
off. An install that was past its first use before the caption existed has no count
saved, so it shows nothing new.
"""

from typing import Final, Protocol

READ_CUE_FIRST_FEW: Final = "For the first few stories"
READ_CUE_ALWAYS: Final = "Always"
READ_CUE_NEVER: Final = "Never"
READ_CUE_OPTIONS: Final = (READ_CUE_FIRST_FEW, READ_CUE_ALWAYS, READ_CUE_NEVER)

# How many comics opened from the picture the caption stays for, after the first.
READ_CUE_OPENS: Final = 3


def is_read_cue_shown(setting: str, opens_left: int) -> bool:
    """Return whether the story picture carries its caption.

    Args:
        setting: One of `READ_CUE_OPTIONS`; anything else is read as the first.
        opens_left: How many more comics opened from the picture the caption stays for.

    Returns:
        Whether to show the caption.

    """
    if setting == READ_CUE_ALWAYS:
        return True
    if setting == READ_CUE_NEVER:
        return False
    return opens_left > 0


class ReadCueStore(Protocol):
    """Where the count of comics the caption stays for is kept (the JSON settings)."""

    def get_read_cue_opens_left(self) -> int:
        """Return how many more comics opened from the picture the caption stays for."""
        ...

    def save_read_cue_opens_left(self, opens_left: int) -> None:
        """Save how many more comics opened from the picture the caption stays for."""
        ...


def count_comic_opened(store: ReadCueStore, *, first_use: bool) -> None:
    """Count a comic opened from the story picture against the caption's stay.

    The first comic ever opened ends "READ ME!" and starts the count; each one after
    takes one off it, until none is left. With none left nothing is saved: an install
    past its first use before the caption existed has no count, and gets none.

    Args:
        store: Where the count is kept.
        first_use: Whether this is the first comic the reader has opened.

    """
    if first_use:
        store.save_read_cue_opens_left(READ_CUE_OPENS)
        return
    opens_left = store.get_read_cue_opens_left()
    if opens_left > 0:
        store.save_read_cue_opens_left(opens_left - 1)
