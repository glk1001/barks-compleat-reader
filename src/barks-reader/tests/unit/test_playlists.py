"""Integrity checks for the curated playlist data.

Playlists are hand-written, so the risk is a typo — a duplicated id, an empty
list, or a title that is not in the Fanta collection — rather than a logic bug.
"""

from __future__ import annotations

import dataclasses

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.playlists import (
    PLAYLISTS,
    PLAYLISTS_BY_ID,
    Playlist,
    get_playlist_title_infos,
)


@pytest.mark.parametrize("playlist", PLAYLISTS, ids=lambda p: p.playlist_id)
def test_playlist_is_fully_populated(playlist: Playlist) -> None:
    assert playlist.playlist_id
    assert playlist.heading
    assert playlist.intro
    assert playlist.titles


def test_playlist_ids_are_unique() -> None:
    assert len(PLAYLISTS_BY_ID) == len(PLAYLISTS)
    for playlist_id, playlist in PLAYLISTS_BY_ID.items():
        assert playlist.playlist_id == playlist_id


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


def test_the_bravery_stories_playlist() -> None:
    bravery = PLAYLISTS_BY_ID["bravery"]

    assert bravery.heading == "The Bravery Stories"
    assert bravery.titles == (
        Titles.SWIMMING_SWINDLERS,
        Titles.SHERIFF_OF_BULLET_VALLEY,
        Titles.VACATION_TIME,
        Titles.KNIGHT_IN_SHINING_ARMOR,
        Titles.CHRISTMAS_ON_BEAR_MOUNTAIN,
        Titles.DONALD_DUCKS_WORST_NIGHTMARE,
        Titles.BACK_TO_THE_KLONDIKE,
        Titles.ROSCOE_THE_ROBOT,
    )


def test_playlists_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        PLAYLISTS[0].heading = "nope"  # ty: ignore[invalid-assignment]
