"""Read the values the app logged: the fields of a marker's lines, for assertions.

A test waits on a marker to know a transition happened; these read what the
line said, so it can also check the value was right (the page count a document
opened with, the title a goto arrow went to, the letters an index walked).
"""

from __future__ import annotations

import re
import zipfile
from typing import TYPE_CHECKING

from barks_reader.core.log_markers import capture, pattern

if TYPE_CHECKING:
    from pathlib import Path

    import gui_driver as gd


# What the file formatter appends after the message: "  [module:function:line]".
# Stripped before a field is read, or a template's trailing literal (usually a
# full stop) would match inside the suffix and the field swallow the message's end.
_LINE_SUFFIX_RE = re.compile(r"\s+\[[\w.]+:\w+:\d+\]$", re.MULTILINE)


def messages(log_text: str) -> str:
    """Return the log text with every line's trailing location suffix removed."""
    return _LINE_SUFFIX_RE.sub("", log_text)


def fields_of(d: gd.Driver, template: str, field: str, **fields: object) -> list[str]:
    """Return `field` from every line of `template` the app has logged, in order.

    Args:
        d: The driver, for the app log.
        template: A marker from ``barks_reader.core.log_markers``.
        field: The field to read.
        **fields: Values to pin for the other fields, as for ``pattern``.

    """
    regex = re.compile(capture(template, field, **fields))
    text = messages(d.log_path.read_text(errors="replace"))
    return [found[field] for found in regex.finditer(text)]


def last_field(d: gd.Driver, template: str, field: str, **fields: object) -> str:
    """Return `field` from the most recent line of `template` the app logged.

    Raises:
        AssertionError: If the app has not logged that line.

    """
    values = fields_of(d, template, field, **fields)
    assert values, f"the app has not logged /{pattern(template, **fields)}/"
    return values[-1]


def image_exists(path: Path) -> bool:
    """Return whether an image path the app logged names a real image.

    With PNG images on, the path is a file. With them off, the panels come
    from a zip, and the app logs the member as if the zip were a directory:
    ``.../Barks Panels.zip/Favourites/<title>/072-5.jpg``. Then the zip must
    exist and hold that member.

    Args:
        path: The path as the app logged it.

    """
    if path.is_file():
        return True
    for ancestor in path.parents:
        if ancestor.suffix.lower() == ".zip" and ancestor.is_file():
            member = path.relative_to(ancestor).as_posix()
            with zipfile.ZipFile(ancestor) as archive:
                return member in archive.namelist()
    return False
