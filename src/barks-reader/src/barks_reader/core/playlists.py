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
BRITTLE_MASTERY_PLAYLIST_ID = "brittle_mastery"
PERSISTENCE_PLAYLIST_ID = "persistence"
PARENTING_PLAYLIST_ID = "parenting"
PETS_PLAYLIST_ID = "pets"
TECHNOLOGY_PLAYLIST_ID = "technology"
WESTERNS_PLAYLIST_ID = "westerns"
CAMPING_PLAYLIST_ID = "camping and hiking"
DETECTIVE_PLAYLIST_ID = "detective"

PLAYLISTS: tuple[Playlist, ...] = (
    Playlist(
        playlist_id=BRAVERY_PLAYLIST_ID,
        heading="The Bravery Stories",
        intro=(
            "[i]The stories where bravery is a key plot element."
            " It might be real bravery, accidental bravery or the opposite of bravery.[/i]"
        ),
        titles=(
            Titles.SWIMMING_SWINDLERS,
            Titles.SHERIFF_OF_BULLET_VALLEY,
            Titles.VACATION_TIME,
            Titles.KNIGHT_IN_SHINING_ARMOR,
            Titles.CHRISTMAS_ON_BEAR_MOUNTAIN,
            Titles.DONALD_DUCKS_WORST_NIGHTMARE,
            Titles.BACK_TO_THE_KLONDIKE,
            Titles.ROSCOE_THE_ROBOT,
        ),
    ),
    Playlist(
        playlist_id=BRITTLE_MASTERY_PLAYLIST_ID,
        heading="The Brittle Mastery Stories",
        intro=(
            "[i]Stories where Donald is an unbelievably brilliant master craftsman. But"
            "\u2014arrogance\u2014or jealousy bring him crashing down. The first four titles are"
            " not the true 'Brittle Mastery' stories but rather stories where Donald is very, very"
            " good at something. The final five titles are truly brittle mastery.[/i]"
        ),
        titles=(
            Titles.MASTER_ICE_FISHER,
            Titles.NO_SUCH_VARMINT,
            Titles.SMOKE_WRITER_IN_THE_SKY,
            Titles.PERSISTENT_POSTMAN_THE,
            Titles.MASTER_RAINMAKER_THE,
            Titles.MASTER_GLASSER_THE,
            Titles.MASTER_MOVER_THE,
            Titles.MASTER_WRECKER,
            Titles.SPARE_THAT_HAIR,
            # Titles.BEAUTY_BUSINESS_THE,
        ),
    ),
    Playlist(
        playlist_id=PERSISTENCE_PLAYLIST_ID,
        heading="The Persistence Stories",
        intro=("[i]Stories where Donald will not give up. Mostly with good results.[/i]"),
        titles=(
            Titles.SILENT_NIGHT,
            Titles.TEN_DOLLAR_DITHER,
            Titles.OLYMPIC_HOPEFUL_THE,
            Titles.HYPNO_GUN_THE,
            Titles.BIG_TOP_BEDLAM,
            Titles.THREE_UN_DUCKS,
        ),
    ),
    Playlist(
        playlist_id=PARENTING_PLAYLIST_ID,
        heading="The Parenting Stories",
        intro=("\u201c[i]Ah! We parents! ... What [b]rich[/b] rewards we reap![/i]\u201d"),
        titles=(
            Titles.BEE_BUMBLES,
            Titles.TAMING_THE_RAPIDS,
            Titles.WATCHFUL_PARENTS_THE,
            Titles.THREE_UN_DUCKS,
            Titles.MASTERS_OF_MELODY_THE,
            Titles.SPOIL_THE_ROD,
            Titles.HOUSEBOAT_HOLIDAY,
            Titles.CAMPING_CONFUSION,
        ),
    ),
    Playlist(
        playlist_id=PETS_PLAYLIST_ID,
        heading="The Pets Stories",
        intro=("[i]Stories where pets are involved. Usually with a happy ending![/i]"),
        titles=(
            Titles.TOO_MANY_PETS,
            Titles.FARRAGUT_THE_FALCON,
            Titles.SINGAPORE_JOE,
            Titles.SMUGSNORKLE_SQUATTIE_THE,
            Titles.TURKEY_RAFFLE,
            Titles.CANTANKEROUS_CAT_THE,
            Titles.GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE,
            Titles.PLENTY_OF_PETS,
            Titles.PIXILATED_PARROT_THE,
            Titles.OPERATION_ST_BERNARD,
            Titles.TALKING_DOG_THE,
            Titles.HAMMY_CAMEL_THE,
            Titles.CHELTENHAMS_CHOICE,
            Titles.DONALDS_PET_SERVICE,
            Titles.CODE_OF_DUCKBURG_THE,
            Titles.OLD_FROGGIE_CATAPULT,
            Titles.LITTLEST_CHICKEN_THIEF_THE,
            Titles.DOG_SITTER_THE,
            Titles.FRAIDY_FALCON_THE,
            # Titles.DUCKBURG_PET_PARADE_THE,
        ),
    ),
    Playlist(
        playlist_id=TECHNOLOGY_PLAYLIST_ID,
        heading="The Technology Stories",
        intro=(
            "[i]Stories where technology drives the plot. Chemistry, physics,"
            " electronics, engineering, and some (but not all) of Gyro's inventions.[/i]"
        ),
        titles=(
            Titles.MAD_CHEMIST_THE,
            Titles.EYES_IN_THE_DARK,
            Titles.JET_RESCUE,
            Titles.GOLD_FINDER_THE,
            Titles.DONALD_DUCKS_ATOM_BOMB,
            Titles.ROCKET_RACE_TO_THE_MOON,
            Titles.SUNKEN_YACHT_THE,
            Titles.SUPER_SNOOPER,
            Titles.HYPNO_GUN_THE,
            Titles.CAMPING_CONFUSION,
            Titles.DESCENT_INTERVAL_A,
            Titles.ROCKET_ROASTED_CHRISTMAS_TURKEY,
            Titles.THINK_BOX_BOLLIX_THE,
            Titles.TALKING_DOG_THE,
            Titles.GYROS_IMAGINATION_INVENTION,
            Titles.STRANGER_THAN_FICTION,
            Titles.CAT_BOX_THE,
            Titles.FORECASTING_FOLLIES,
            Titles.ROCKS_TO_RICHES,
            Titles.SHERIFF_OF_BULLET_VALLEY,
            Titles.IN_ANCIENT_PERSIA,
            Titles.MYSTERIOUS_STONE_RAY_THE,
            Titles.BILLIONS_IN_THE_HOLE,
            Titles.UNSAFE_SAFE_THE,
            Titles.TWENTY_FOUR_CARAT_MOON_THE,
            Titles.TITANIC_ANTS_THE,
            Titles.PAUL_BUNYAN_MACHINE_THE,
            Titles.THRIFTY_SPENDTHRIFT_THE,
            # Titles.SWAMP_OF_NO_RETURN_THE,
            # Titles.GIANT_ROBOT_ROBBERS_THE,
        ),
    ),
    Playlist(
        playlist_id=WESTERNS_PLAYLIST_ID,
        heading="The Old West Stories",
        intro=("[i]Stories with an western theme.[/i]"),
        titles=(
            Titles.SHERIFF_OF_BULLET_VALLEY,
            Titles.LIMBER_W_GUEST_RANCH_THE,
            Titles.WEBFOOTED_WRANGLER,
            Titles.DAYS_AT_THE_LAZY_K,
            Titles.PIZEN_SPRING_DUDE_RANCH,
            Titles.IN_OLD_CALIFORNIA,
            Titles.GHOST_SHERIFF_OF_LAST_GASP_THE,
            Titles.LOST_PEG_LEG_MINE_THE,
            Titles.RETURN_TO_PIZEN_BLUFF,
            Titles.TENDERFOOT_TRAP_THE,
            Titles.FABULOUS_TYCOON_THE,
            Titles.RIDING_THE_PONY_EXPRESS,
            # Titles.MYSTERY_OF_THE_GHOST_TOWN_RAILROAD,
            # Titles.CATTLE_KING_THE,
        ),
    ),
    Playlist(
        playlist_id=CAMPING_PLAYLIST_ID,
        heading="Camping, Hiking, or Woods Stories",
        intro=("[i]Stories where Donald and the boys go camping, hiking, or out in the woods.[/i]"),
        titles=(
            Titles.VACATION_TIME,
            Titles.GOLDILOCKS_GAMBIT_THE,
            Titles.CAMP_COUNSELOR,
            Titles.CAMPING_CONFUSION,
            Titles.JET_RESCUE,
            Titles.TEN_STAR_GENERALS,
            Titles.BLACK_FOREST_RESCUE_THE,
            Titles.DAY_THE_MOUNTAIN_SHOOK_THE,
        ),
    ),
    Playlist(
        playlist_id=DETECTIVE_PLAYLIST_ID,
        heading="The Detective Stories",
        intro=("[i]Stories where detecting is part of the plot.[/i]"),
        titles=(
            Titles.ICEBOX_ROBBER_THE,
            Titles.THUG_BUSTERS,
            Titles.GLADSTONES_TERRIBLE_SECRET,
            Titles.TRAVELLING_TRUANTS,
            Titles.SECRET_RESOLUTIONS,
            Titles.MR_PRIVATE_EYE,
            Titles.MISSILE_FIZZLE,
            Titles.OLD_CASTLES_SECRET_THE,
            Titles.NO_SUCH_VARMINT,
            Titles.STRANGE_SHIPWRECKS_THE,
            Titles.FOR_OLD_DIMES_SAKE,
            Titles.INVISIBLE_INTRUDER_THE,
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
