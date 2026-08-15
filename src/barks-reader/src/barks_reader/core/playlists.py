"""Curated reading playlists — the data behind the 'Playlists' tree section.

A playlist is a hand-picked set of stories tied together by an idea, introduced by a
short piece of prose. Unlike the 'Choose for me' nodes (a fresh random sample, sorted
chronologically) a playlist is fixed and is always shown in the order written here.

The intro text is stored as plain prose; the navigation tree spec hyphenates it for
display, the same way `ReaderFormatter.get_title_extra_info` does for the bottom
title view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import get_fanta_info

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


@dataclass(frozen=True, slots=True)
class Playlist:
    """One curated reading list.

    Attributes:
        playlist_id: Stable key carried by `PlaylistDestination`. Never displayed,
            so it can stay fixed while the heading is reworded.
        heading: The tree-node text.
        intro: Plain, un-hyphenated introductory prose.
        titles: The stories, in the order they should be displayed.

    """

    playlist_id: str
    heading: str
    intro: str
    titles: tuple[Titles, ...]


BRAVERY_PLAYLIST_ID = "bravery"

PLAYLISTS: tuple[Playlist, ...] = (
    Playlist(
        playlist_id=BRAVERY_PLAYLIST_ID,
        heading="The Bravery Stories",
        intro=(
            "[i]The stories where bravery is a key plot element."
            " It might be real bravery, accidental bravery or the opposite of bravery.[/i]"
        ),
        titles=(
            Titles.CHRISTMAS_ON_BEAR_MOUNTAIN,
            Titles.KNIGHT_IN_SHINING_ARMOR,
            Titles.SHERIFF_OF_BULLET_VALLEY,
            Titles.VACATION_TIME,
            Titles.DONALD_DUCKS_WORST_NIGHTMARE,
            Titles.BACK_TO_THE_KLONDIKE,
            Titles.ROSCOE_THE_ROBOT,
        ),
    ),
)

PLAYLISTS_BY_ID: dict[str, Playlist] = {playlist.playlist_id: playlist for playlist in PLAYLISTS}

# A duplicate id would make one playlist unreachable from its destination.
assert len(PLAYLISTS_BY_ID) == len(PLAYLISTS), "playlist ids must be unique"


def get_playlist_title_infos(playlist: Playlist) -> list[FantaComicBookInfo]:
    """Resolve a playlist's titles to their Fanta info, preserving the curated order.

    Args:
        playlist: The playlist to resolve.

    Returns:
        One `FantaComicBookInfo` per title, in playlist order.

    Raises:
        AssertionError: If a title is not in the Fanta collection. Unlike the tag
            lists — which legitimately name titles outside the collection and are
            filtered — a playlist is hand-written here, so a miss is a typo and
            should fail loudly rather than silently drop a row.

    """
    title_infos = []
    for title in playlist.titles:
        title_info = get_fanta_info(title)
        assert title_info is not None, (
            f"playlist '{playlist.playlist_id}' names '{title.name}',"
            f" which is not in the Fanta collection"
        )
        title_infos.append(title_info)

    return title_infos
