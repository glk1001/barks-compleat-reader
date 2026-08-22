"""Integrity checks for the curated playlist data.

Playlists are hand-written, so the risk is a typo — an empty list, or a title
that is not in the Fanta collection — rather than a logic bug. (A duplicated id
is caught at import time by the assert in `playlists.py`.)
"""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.playlists import (
    PLAYLISTS,
    Playlist,
    get_playlist_title_infos,
)


@pytest.mark.parametrize("playlist", PLAYLISTS, ids=lambda p: p.playlist_id)
def test_playlist_is_fully_populated(playlist: Playlist) -> None:
    assert playlist.playlist_id
    assert playlist.heading
    assert playlist.intro
    assert playlist.titles


@pytest.mark.parametrize("playlist", PLAYLISTS, ids=lambda p: p.playlist_id)
def test_titles_resolve_in_curated_order(playlist: Playlist) -> None:
    title_infos = get_playlist_title_infos(playlist)

    assert [info.comic_book_info.title for info in title_infos] == list(playlist.titles)


def test_unknown_title_fails_loudly() -> None:
    # ATTIC_ANTICS is a real Barks title that the Fantagraphics collection does
    # not carry, so it stands in for a mistyped curated entry.
    bad = Playlist(
        playlist_id="bad",
        heading="Bad",
        intro="Bad.",
        titles=(Titles.ATTIC_ANTICS,),
    )

    with pytest.raises(AssertionError, match="not in the Fanta collection"):
        get_playlist_title_infos(bad)
