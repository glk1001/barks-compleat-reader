"""The popup gallery's names and requests, free of Kivy for ``scripts/popup_gallery.py``.

The gallery (``barks_reader.ui.popup_gallery``) opens the popups; this module says
which there are, in the gallery's order, and how a request to open one is written,
so the script can ask for each without importing the UI.
"""

from __future__ import annotations

from .user_error_types import ErrorTypes

# Set to `LIVE_MODE`, or to the file the app answers requests from.
POPUP_GALLERY_ENV_VAR = "BARKS_READER_POPUP_GALLERY"
LIVE_MODE = "live"


def error_popup_name(error_type: ErrorTypes) -> str:
    """Return the gallery's name for a user error's popup: ``error-missing-archive-volumes``.

    Args:
        error_type: The user error.

    Returns:
        Its kebab-case name, after ``error-``.

    """
    name = error_type.name
    return "error-" + "".join(f"-{c.lower()}" if c.isupper() else c for c in name).lstrip("-")


# The shared frame's samples (``ui.popup_frame``), one per size class, shown until the
# real popups are moved onto it.
FRAME_SAMPLE_NAMES: tuple[str, ...] = ("frame-small", "frame-medium", "frame-large")

# The gallery's order: the confirms, the messages, the user errors, the rest, then the
# frame's samples.
POPUP_NAMES: tuple[str, ...] = (
    "quit",
    "delete-reading",
    "delete-title-readings",
    "clear-history",
    "data-pack-offer",
    "data-pack-no-update",
    "small-screen",
    *(error_popup_name(error_type) for error_type in ErrorTypes),
    "about",
    "speech-bubbles",
    "folder-chooser",
    "alt-escape-key",
    *FRAME_SAMPLE_NAMES,
)


def request_text(request: str, name: str) -> str:
    """Return the request to open popup `name`, as its file holds it.

    Args:
        request: An id for the request, unique within the app's run, with no spaces.
        name: A name in `POPUP_NAMES`.

    Returns:
        The request's text.

    """
    return f"{request} {name}\n"


def parse_request(text: str) -> tuple[str, str] | None:
    """Split a request ``<id> <name>``, or return None for one that is not.

    Args:
        text: The request file's contents.

    Returns:
        The request id and the popup's name.

    """
    parts = text.split()
    if len(parts) != 2:  # noqa: PLR2004
        return None
    return parts[0], parts[1]
