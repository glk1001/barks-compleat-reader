"""When the title view's story picture says "Read this story".

The picture is the button that opens the comic, and nothing else on it says so. A
first-time user gets "READ ME!" across it, until the first comic it opens; this
caption follows for the next few, then goes, unless the setting keeps it or turns it
off. An install that was past its first use before the caption existed has no count
saved, so it shows nothing new.
"""

from typing import Final

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
