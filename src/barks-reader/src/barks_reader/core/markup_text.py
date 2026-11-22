"""Kivy markup as the plain text it shows.

A module of its own, with nothing of the app's data behind it: the fatal-error path
uses it, and must load whatever else failed to.
"""

from __future__ import annotations

import re

from barks_fantagraphics.speech_markup import unescape_markup

# A tag as Kivy knows one: a lowercase name, perhaps with a value. Any other run in
# square brackets ("[Cover]", an OSError's "[Errno 2]") is text, and Kivy draws it.
_MARKUP_TAG = re.compile(r"\[/?[a-z_]+(?:=[^\]]*)?\]")


def plain_text(markup: str) -> str:
    """Return Kivy markup as plain text: its tags gone, its escapes undone.

    Args:
        markup: Kivy markup, a bracket that is text either escaped (``escape_markup``)
            or in a run that is no tag.

    Returns:
        The text as the label shows it, for a log, a saved report, the clipboard or
        a GUI test's name for a widget.

    """
    return unescape_markup(_MARKUP_TAG.sub("", markup))
