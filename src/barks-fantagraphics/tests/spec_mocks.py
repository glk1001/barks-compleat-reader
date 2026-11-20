"""Stand-ins for the database and a comic book that hold a test to the real signatures.

A bare ``MagicMock()`` takes any method name and any arguments, so a test built on one
goes on passing after the method it calls is renamed or its parameters reordered. These
take their spec from the classes: a name the class lacks raises, and so does a call the real
method would refuse. The sibling repositories call the same methods.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_database import ComicsDatabase


def mock_comics_database() -> MagicMock:
    """Return a mock that has `ComicsDatabase`'s methods, with their signatures."""
    return create_autospec(ComicsDatabase, instance=True)


def mock_comic_book() -> MagicMock:
    """Return a mock that has `ComicBook`'s fields and methods, with their signatures."""
    return create_autospec(ComicBook, instance=True)
