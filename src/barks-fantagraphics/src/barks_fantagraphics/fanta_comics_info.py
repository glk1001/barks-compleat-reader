# ruff: noqa: ERA001

import collections
from collections import OrderedDict, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import barks_titles as bt
from .barks_titles import BARKS_TITLE_INFO, ComicBookInfo, Titles
from .barks_titles import Titles as Bt
from .comic_issues import ISSUE_NAME, Issues


@dataclass
class FantaComicBookInfo:
    comic_book_info: ComicBookInfo
    colorist: str
    series_name: str = ""
    fantagraphics_volume: str = ""
    number_in_series: int = -1
    fanta_chronological_number: int = -1

    def get_short_issue_title(self) -> str:
        return self.comic_book_info.get_short_issue_title()


FantaComicBookInfoDict = OrderedDict[str, FantaComicBookInfo]


# TODO: Use a list here - not a dict
def _get_all_fanta_comic_book_info() -> FantaComicBookInfoDict:
    current_number_in_series = SERIES_INFO_START_NUMBERS.copy()

    all_fanta_info: FantaComicBookInfoDict = collections.OrderedDict()

    chrono_sorted_series_info = sorted(SERIES_INFO, key=lambda x: x.title)

    fanta_chronological_number = 1
    for title_info in chrono_sorted_series_info:
        # if title not in SERIES_INFO:
        #     logger.debug(f'Title "{title}" not in SERIES_INFO.')
        #     continue

        comic_book_info = BARKS_TITLE_INFO[title_info.title]

        fanta_info = FantaComicBookInfo(
            comic_book_info=comic_book_info,
            colorist=title_info.colorist,
            series_name=title_info.series_name,
            fantagraphics_volume=title_info.fanta_volume,
            number_in_series=current_number_in_series[title_info.series_name],
            fanta_chronological_number=fanta_chronological_number,
        )

        all_fanta_info[comic_book_info.get_title_str()] = fanta_info

        current_number_in_series[title_info.series_name] += 1
        fanta_chronological_number += 1

    return all_fanta_info


def get_fanta_volume_str(volume: int) -> str:
    return f"FANTA_{volume:02}"


@dataclass
class FantaBook:
    title: str
    pub: str
    volume: int
    year: int
    num_pages: int


FAN = "Fantagraphics"
CB = "Carl Barks"

SRC_SALEM = "(Salem-Empire)"
SRC_DIGI = "(Digital-Empire)"
SRC_BEAN = "(Bean-Empire)"

FANTAGRAPHICS = "Fantagraphics"
FANTAGRAPHICS_DIRNAME = FANTAGRAPHICS + "-original"
FANTAGRAPHICS_UPSCAYLED_DIRNAME = FANTAGRAPHICS + "-upscayled"
FANTAGRAPHICS_RESTORED_DIRNAME = FANTAGRAPHICS + "-restored"
FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME = FANTAGRAPHICS_RESTORED_DIRNAME + "-upscayled"
FANTAGRAPHICS_RESTORED_SVG_DIRNAME = FANTAGRAPHICS_RESTORED_DIRNAME + "-svg"
FANTAGRAPHICS_RESTORED_OCR_DIRNAME = FANTAGRAPHICS_RESTORED_DIRNAME + "-ocr"
FANTAGRAPHICS_FIXES_DIRNAME = FANTAGRAPHICS + "-fixes-and-additions"
FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME = FANTAGRAPHICS_FIXES_DIRNAME + "-scraps"
FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME = FANTAGRAPHICS_UPSCAYLED_DIRNAME + "-fixes-and-additions"
FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME = FANTAGRAPHICS_RESTORED_DIRNAME + "-panel-segments"

FANTA_01 = "FANTA_01"
FANTA_02 = "FANTA_02"
FANTA_03 = "FANTA_03"
FANTA_04 = "FANTA_04"
FANTA_05 = "FANTA_05"
FANTA_06 = "FANTA_06"
FANTA_07 = "FANTA_07"
FANTA_08 = "FANTA_08"
FANTA_09 = "FANTA_09"
FANTA_10 = "FANTA_10"
FANTA_11 = "FANTA_11"
FANTA_12 = "FANTA_12"
FANTA_13 = "FANTA_13"
FANTA_14 = "FANTA_14"
FANTA_15 = "FANTA_15"
FANTA_16 = "FANTA_16"
FANTA_17 = "FANTA_17"
FANTA_18 = "FANTA_18"
FANTA_19 = "FANTA_19"
FANTA_20 = "FANTA_20"
FANTA_21 = "FANTA_21"
FANTA_22 = "FANTA_22"
FANTA_23 = "FANTA_23"
FANTA_24 = "FANTA_24"
FANTA_25 = "FANTA_25"
FANTA_26 = "FANTA_26"
FANTA_27 = "FANTA_27"
FANTA_28 = "FANTA_28"

DD = "Donald Duck"
US = "Uncle Scrooge"

VOLUME_01 = f"{CB} Vol. 1 - {DD} - Finds Pirate Gold {SRC_SALEM}"
VOLUME_02 = f"{CB} Vol. 2 - {DD} - Frozen Gold {SRC_SALEM}"
VOLUME_03 = f"{CB} Vol. 3 - {DD} - Mystery of the Swamp {SRC_SALEM}"
VOLUME_04 = f"{CB} Vol. 4 - {DD} - Maharajah Donald {SRC_SALEM}"
VOLUME_05 = f"{CB} Vol. 5 - {DD} - Christmas on Bear Mountain {SRC_DIGI}"
VOLUME_06 = f"{CB} Vol. 6 - {DD} - The Old Castle's Secret {SRC_DIGI}"
VOLUME_07 = f"{CB} Vol. 7 - {DD} - Lost in the Andes {SRC_DIGI}"
VOLUME_08 = f"{CB} Vol. 8 - {DD} - Trail of the Unicorn {SRC_DIGI}"
VOLUME_09 = f"{CB} Vol. 9 - {DD} - The Pixilated Parrot {SRC_DIGI}"
VOLUME_10 = f"{CB} Vol. 10 - {DD} - Terror of the Beagle Boys {SRC_DIGI}"
VOLUME_11 = f"{CB} Vol. 11 - {DD} - A Christmas for Shacktown {SRC_DIGI}"
VOLUME_12 = f"{CB} Vol. 12 - {US} - Only a Poor Old Man {SRC_DIGI}"
VOLUME_13 = f"{CB} Vol. 13 - {DD} - Trick or Treat {SRC_DIGI}"
VOLUME_14 = f"{CB} Vol. 14 - {US} - The Seven Cities of Gold {SRC_DIGI}"
VOLUME_15 = f"{CB} Vol. 15 - {DD} - The Ghost Sheriff of Last Gasp {SRC_DIGI}"
VOLUME_16 = f"{CB} Vol. 16 - {US} - The Lost Crown of Genghis Khan {SRC_DIGI}"
VOLUME_17 = f"{CB} Vol. 17 - {DD} - The Secret of Hondorica {SRC_DIGI}"
VOLUME_18 = f"{CB} Vol. 18 - {DD} - The Lost Peg Leg Mine {SRC_DIGI}"
VOLUME_19 = f"{CB} Vol. 19 - {DD} - The Black Pearls of Tabu Yama {SRC_BEAN}"
VOLUME_20 = f"{CB} Vol. 20 - {US} - The Mines of King Solomon {SRC_BEAN}"
VOLUME_21 = f"{CB} Vol. 21 - {DD} - Christmas in Duckburg {SRC_BEAN}"
VOLUME_22 = f"{CB} Vol. 22 - {US} - The Twenty-Four Carat Moon {SRC_BEAN}"
VOLUME_23 = f"{CB} Vol. 23 - {DD} - Under the Polar Ice {SRC_BEAN}"
VOLUME_24 = f"{CB} Vol. 24 - {US} - Island in the Sky"
VOLUME_25 = f"{CB} Vol. 25 - {DD} - Balloonatics {SRC_SALEM}"
VOLUME_26 = f"{CB} Vol. 26 - {US} - The Golden Nugget Boat {SRC_SALEM}"
VOLUME_27 = f"{CB} Vol. 27 - {DD} - Duck Luck {SRC_SALEM}"
VOLUME_28 = f"{CB} Vol. 28 - {US} - Cave of Ali Baba {SRC_SALEM}"

FANTA_SOURCE_COMICS = {
    f"{get_fanta_volume_str(1)}": FantaBook(VOLUME_01, FAN, 1, 2025, 250),
    f"{get_fanta_volume_str(2)}": FantaBook(VOLUME_02, FAN, 2, 2024, 245),
    f"{get_fanta_volume_str(3)}": FantaBook(VOLUME_03, FAN, 3, 2024, 248),
    f"{get_fanta_volume_str(4)}": FantaBook(VOLUME_04, FAN, 4, 2023, 225),
    f"{get_fanta_volume_str(5)}": FantaBook(VOLUME_05, FAN, 5, 2013, 216),
    f"{get_fanta_volume_str(6)}": FantaBook(VOLUME_06, FAN, 6, 2013, 232),
    f"{get_fanta_volume_str(7)}": FantaBook(VOLUME_07, FAN, 7, 2011, 239),
    f"{get_fanta_volume_str(8)}": FantaBook(VOLUME_08, FAN, 8, 2014, 223),
    f"{get_fanta_volume_str(9)}": FantaBook(VOLUME_09, FAN, 9, 2015, 215),
    f"{get_fanta_volume_str(10)}": FantaBook(VOLUME_10, FAN, 10, 2016, 231),
    f"{get_fanta_volume_str(11)}": FantaBook(VOLUME_11, FAN, 11, 2012, 240),
    f"{get_fanta_volume_str(12)}": FantaBook(VOLUME_12, FAN, 12, 2012, 248),
    f"{get_fanta_volume_str(13)}": FantaBook(VOLUME_13, FAN, 13, 2015, 227),
    f"{get_fanta_volume_str(14)}": FantaBook(VOLUME_14, FAN, 14, 2014, 240),
    f"{get_fanta_volume_str(15)}": FantaBook(VOLUME_15, FAN, 15, 2016, 248),
    f"{get_fanta_volume_str(16)}": FantaBook(VOLUME_16, FAN, 16, 2017, 234),
    f"{get_fanta_volume_str(17)}": FantaBook(VOLUME_17, FAN, 17, 2017, 201),
    f"{get_fanta_volume_str(18)}": FantaBook(VOLUME_18, FAN, 18, 2018, 202),
    f"{get_fanta_volume_str(19)}": FantaBook(VOLUME_19, FAN, 19, 2018, 201),
    f"{get_fanta_volume_str(20)}": FantaBook(VOLUME_20, FAN, 20, 2019, 209),
    f"{get_fanta_volume_str(21)}": FantaBook(VOLUME_21, FAN, 21, 2019, 201),
    f"{get_fanta_volume_str(22)}": FantaBook(VOLUME_22, FAN, 22, 2020, 210),
    f"{get_fanta_volume_str(23)}": FantaBook(VOLUME_23, FAN, 23, 2020, 201),
    f"{get_fanta_volume_str(24)}": FantaBook(VOLUME_24, FAN, 24, 2021, 216),
    f"{get_fanta_volume_str(25)}": FantaBook(VOLUME_25, FAN, 25, 2021, 216),
    f"{get_fanta_volume_str(26)}": FantaBook(VOLUME_26, FAN, 26, 2022, 217),
    f"{get_fanta_volume_str(27)}": FantaBook(VOLUME_27, FAN, 27, 2022, 209),
    f"{get_fanta_volume_str(28)}": FantaBook(VOLUME_28, FAN, 28, 2023, 206),
}

FANTA_VOLUME_OVERRIDES_ROOT = Path(
    "/mnt/2tb_drive/Books/Carl Barks/Fantagraphics Volumes Overrides"
)

FANTA_OVERRIDE_ZIPS = {
    1: "01 - Donald Duck - Pirate Gold.cbz",
    2: "02 - Donald Duck - Frozen Gold.cbz",
    3: "03 - Donald Duck - Mystery of the Swamp.cbz",
    4: "04 - Donald Duck - Maharajah Donald.cbz",
    5: "05 - Donald Duck - Christmas on Bear Mountain.cbz",
    6: "06 - Donald Duck - The Old Castle's Secret.cbz",
    7: "07 - Donald Duck - Lost in the Andes.cbz",
    8: "08 - Donald Duck - Trail of the Unicorn.cbz",
    9: "09 - Donald Duck - The Pixilated Parrot.cbz",
    10: "10 - Donald Duck - Terror of the Beagle Boys.cbz",
    11: "11 - Donald Duck - A Christmas for Shacktown.cbz",
    12: "12 - Uncle Scrooge - Only a Poor Old Man.cbz",
    13: "13 - Donald Duck - Trick or Treat.cbz",
    14: "14 - Uncle Scrooge - The Seven Cities of Gold.cbz",
    15: "15 - Donald Duck - The Ghost Sheriff of Last Gasp.cbz",
    16: "16 - Uncle Scrooge - The Lost Crown of Genghis Khan.cbz",
    17: "17 - Donald Duck - The Secret of Hondorica.cbz",
    18: "18 - Donald Duck - The Lost Peg Leg Mine",
    19: "19 - Donald Duck - The Black Pearls of Tabu Yama.cbz",
    20: "20 - Uncle Scrooge - The Mines of King Solomon.cbz",
    21: "21 - Donald Duck - Christmas in Duckburg.cbz",
    22: "22 - Uncle Scrooge - The Twenty-Four Carat Moon.cbz",
    23: "23 - Donald Duck - Under the Polar Ice.cbz",
    24: "24 - Uncle Scrooge - Island in the Sky.cbz",
    25: "25 - Donald Duck - Balloonatics.cbz",
    26: "26 - Uncle Scrooge - The Golden Nugget Boat.cbz",
    27: "27 - Donald Duck - 'Duck Luck'.cbz",
    28: "28 - Uncle Scrooge - 'Cave of Ali Baba'.cbz",
}

FIRST_VOLUME_NUMBER = 1
LAST_VOLUME_NUMBER = len(FANTA_SOURCE_COMICS)
NUM_VOLUMES = LAST_VOLUME_NUMBER - FIRST_VOLUME_NUMBER + 1

SERIES_DDA = ISSUE_NAME[Issues.DD] + " Adventures"
SERIES_USA = ISSUE_NAME[Issues.US] + " Adventures"
SERIES_DDS = ISSUE_NAME[Issues.DD] + " Short Stories"
SERIES_USS = ISSUE_NAME[Issues.US] + " Short Stories"
SERIES_CS = ISSUE_NAME[Issues.CS]
SERIES_GG = "Gyro Gearloose"
SERIES_MISC = "Misc"
SERIES_EXTRAS = "Extras"

RTOM = "Rich Tommaso"
GLEA = "Gary Leach"
SLEA = "Susan Daigle-Leach"
DIGI = "Digikore Studios"
BIGD = "Big Doors Studios"
JRC = "Joseph Robert Cowles"
TOZ = "Tom Ziuko"
EROS = "Erik Rosengarten"
DIT = "Disney Italia"
GER = "David Gerstein"
BAR = "Barry Englin Grossman"
COL = "Colleen Winkler"
NEA = "Nea Atkina A.E. and Kneon Transitt"


@dataclass
class FantaSeriesInfo:
    title: Titles
    colorist: str
    series_name: str
    fanta_volume: str
    number_in_series: int = -1


SERIES_INFO_START_NUMBERS: dict[str, int] = {
    SERIES_DDA: 1,
    SERIES_USA: 1,
    SERIES_DDS: 1,
    SERIES_USS: 1,
    SERIES_CS: 1,
    SERIES_GG: 1,
    SERIES_MISC: 1,
    SERIES_EXTRAS: 1,
}

US_CENSORED_TITLES = [bt.SILENT_NIGHT, bt.MILKMAN_THE]
CENSORED_TITLES = [bt.GOOD_DEEDS, bt.SILENT_NIGHT, bt.MILKMAN_THE]
HAND_RESTORED_TITLES = [bt.GOOD_DEEDS, bt.SILENT_NIGHT]
SILENT_NIGHT_PUBLICATION_ISSUE = "Gemstone's Christmas Parade, No.3, 2005"

SERIES_INFO: list[FantaSeriesInfo] = [
    # DDA
    FantaSeriesInfo(Bt.DONALD_DUCK_FINDS_PIRATE_GOLD, GLEA, SERIES_MISC, FANTA_01),
    FantaSeriesInfo(Bt.DONALD_DUCK_AND_THE_MUMMYS_RING, GLEA, SERIES_DDA, FANTA_01),
    FantaSeriesInfo(Bt.TOO_MANY_PETS, GLEA, SERIES_DDA, FANTA_02),
    FantaSeriesInfo(Bt.FROZEN_GOLD, GLEA, SERIES_DDA, FANTA_02),
    FantaSeriesInfo(Bt.MYSTERY_OF_THE_SWAMP, BIGD, SERIES_DDA, FANTA_03),
    FantaSeriesInfo(Bt.FIREBUG_THE, DIGI, SERIES_DDA, FANTA_03),
    FantaSeriesInfo(Bt.TERROR_OF_THE_RIVER_THE, SLEA, SERIES_DDA, FANTA_04),
    FantaSeriesInfo(Bt.MAHARAJAH_DONALD, GLEA, SERIES_DDA, FANTA_04),
    FantaSeriesInfo(Bt.VOLCANO_VALLEY, RTOM, SERIES_DDA, FANTA_05),
    FantaSeriesInfo(Bt.ADVENTURE_DOWN_UNDER, RTOM, SERIES_DDA, FANTA_05),
    FantaSeriesInfo(Bt.GHOST_OF_THE_GROTTO_THE, RTOM, SERIES_DDA, FANTA_05),
    FantaSeriesInfo(Bt.CHRISTMAS_ON_BEAR_MOUNTAIN, RTOM, SERIES_DDA, FANTA_05),
    FantaSeriesInfo(Bt.DARKEST_AFRICA, RTOM, SERIES_DDA, FANTA_06),
    FantaSeriesInfo(Bt.OLD_CASTLES_SECRET_THE, RTOM, SERIES_DDA, FANTA_06),
    FantaSeriesInfo(Bt.SHERIFF_OF_BULLET_VALLEY, RTOM, SERIES_DDA, FANTA_06),
    FantaSeriesInfo(Bt.GOLDEN_CHRISTMAS_TREE_THE, RTOM, SERIES_DDA, FANTA_07),
    FantaSeriesInfo(Bt.LOST_IN_THE_ANDES, RTOM, SERIES_DDA, FANTA_07),
    FantaSeriesInfo(Bt.RACE_TO_THE_SOUTH_SEAS, RTOM, SERIES_DDA, FANTA_07),
    FantaSeriesInfo(Bt.VOODOO_HOODOO, RTOM, SERIES_DDA, FANTA_07),
    FantaSeriesInfo(Bt.LETTER_TO_SANTA, RTOM, SERIES_DDA, FANTA_08),
    FantaSeriesInfo(Bt.LUCK_OF_THE_NORTH, RTOM, SERIES_DDA, FANTA_08),
    FantaSeriesInfo(Bt.TRAIL_OF_THE_UNICORN, RTOM, SERIES_DDA, FANTA_08),
    FantaSeriesInfo(Bt.LAND_OF_THE_TOTEM_POLES, RTOM, SERIES_DDA, FANTA_08),
    FantaSeriesInfo(Bt.IN_ANCIENT_PERSIA, RTOM, SERIES_DDA, FANTA_09),
    FantaSeriesInfo(Bt.VACATION_TIME, RTOM, SERIES_DDA, FANTA_09),
    FantaSeriesInfo(Bt.PIXILATED_PARROT_THE, RTOM, SERIES_DDA, FANTA_09),
    FantaSeriesInfo(Bt.MAGIC_HOURGLASS_THE, RTOM, SERIES_DDA, FANTA_09),
    FantaSeriesInfo(Bt.BIG_TOP_BEDLAM, RTOM, SERIES_DDA, FANTA_09),
    FantaSeriesInfo(Bt.YOU_CANT_GUESS, RTOM, SERIES_DDA, FANTA_09),
    FantaSeriesInfo(Bt.DANGEROUS_DISGUISE, RTOM, SERIES_DDA, FANTA_10),
    FantaSeriesInfo(Bt.NO_SUCH_VARMINT, RTOM, SERIES_DDA, FANTA_10),
    FantaSeriesInfo(Bt.IN_OLD_CALIFORNIA, JRC, SERIES_DDA, FANTA_10),
    FantaSeriesInfo(Bt.CHRISTMAS_FOR_SHACKTOWN_A, RTOM, SERIES_DDA, FANTA_11),
    FantaSeriesInfo(Bt.GOLDEN_HELMET_THE, RTOM, SERIES_DDA, FANTA_11),
    FantaSeriesInfo(Bt.GILDED_MAN_THE, RTOM, SERIES_DDA, FANTA_11),
    FantaSeriesInfo(Bt.TRICK_OR_TREAT, RTOM, SERIES_DDA, FANTA_13),
    FantaSeriesInfo(Bt.SECRET_OF_HONDORICA, RTOM, SERIES_DDA, FANTA_17),
    FantaSeriesInfo(Bt.FORBIDDEN_VALLEY, RTOM, SERIES_DDA, FANTA_19),
    FantaSeriesInfo(Bt.TITANIC_ANTS_THE, RTOM, SERIES_DDA, FANTA_19),
    # DD SHORTS
    FantaSeriesInfo(Bt.HARD_LOSER_THE, SLEA, SERIES_DDS, FANTA_02),
    FantaSeriesInfo(Bt.SEALS_ARE_SO_SMART, GLEA, SERIES_DDS, FANTA_04),
    FantaSeriesInfo(Bt.PEACEFUL_HILLS_THE, SLEA, SERIES_DDS, FANTA_04),
    FantaSeriesInfo(Bt.DONALD_DUCKS_BEST_CHRISTMAS, DIGI, SERIES_DDS, FANTA_03),
    FantaSeriesInfo(Bt.SANTAS_STORMY_VISIT, SLEA, SERIES_DDS, FANTA_04),
    FantaSeriesInfo(Bt.DONALD_DUCKS_ATOM_BOMB, SLEA, SERIES_DDS, FANTA_04),
    FantaSeriesInfo(Bt.THREE_GOOD_LITTLE_DUCKS, RTOM, SERIES_DDS, FANTA_05),
    FantaSeriesInfo(Bt.TOYLAND, RTOM, SERIES_DDS, FANTA_07),
    FantaSeriesInfo(Bt.NEW_TOYS, RTOM, SERIES_DDS, FANTA_08),
    FantaSeriesInfo(Bt.HOBBLIN_GOBLINS, RTOM, SERIES_DDS, FANTA_13),
    FantaSeriesInfo(Bt.DOGCATCHER_DUCK, RTOM, SERIES_DDS, FANTA_17),
    FantaSeriesInfo(Bt.LOST_PEG_LEG_MINE_THE, TOZ, SERIES_DDS, FANTA_18),
    FantaSeriesInfo(Bt.WATER_SKI_RACE, RTOM, SERIES_DDS, FANTA_19),
    # US
    FantaSeriesInfo(Bt.ONLY_A_POOR_OLD_MAN, RTOM, SERIES_USA, FANTA_12),
    FantaSeriesInfo(Bt.BACK_TO_THE_KLONDIKE, RTOM, SERIES_USA, FANTA_12),
    FantaSeriesInfo(Bt.HORSERADISH_STORY_THE, RTOM, SERIES_USA, FANTA_12),
    FantaSeriesInfo(Bt.MENEHUNE_MYSTERY_THE, RTOM, SERIES_USA, FANTA_12),
    FantaSeriesInfo(Bt.SECRET_OF_ATLANTIS_THE, RTOM, SERIES_USA, FANTA_12),
    FantaSeriesInfo(Bt.TRALLA_LA, RTOM, SERIES_USA, FANTA_12),
    FantaSeriesInfo(Bt.SEVEN_CITIES_OF_CIBOLA_THE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.MYSTERIOUS_STONE_RAY_THE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.LEMMING_WITH_THE_LOCKET_THE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.FABULOUS_PHILOSOPHERS_STONE_THE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.GREAT_STEAMBOAT_RACE_THE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.RICHES_RICHES_EVERYWHERE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.GOLDEN_FLEECING_THE, RTOM, SERIES_USA, FANTA_14),
    FantaSeriesInfo(Bt.LAND_BENEATH_THE_GROUND, RTOM, SERIES_USA, FANTA_16),
    FantaSeriesInfo(Bt.LOST_CROWN_OF_GENGHIS_KHAN_THE, RTOM, SERIES_USA, FANTA_16),
    FantaSeriesInfo(Bt.SECOND_RICHEST_DUCK_THE, RTOM, SERIES_USA, FANTA_16),
    FantaSeriesInfo(Bt.BACK_TO_LONG_AGO, RTOM, SERIES_USA, FANTA_16),
    FantaSeriesInfo(Bt.COLD_BARGAIN_A, RTOM, SERIES_USA, FANTA_16),
    FantaSeriesInfo(Bt.LAND_OF_THE_PYGMY_INDIANS, RTOM, SERIES_USA, FANTA_16),
    FantaSeriesInfo(Bt.BLACK_PEARLS_OF_TABU_YAMA_THE, RTOM, SERIES_DDA, FANTA_19),
    FantaSeriesInfo(Bt.MINES_OF_KING_SOLOMON_THE, RTOM, SERIES_USA, FANTA_20),
    FantaSeriesInfo(Bt.CITY_OF_GOLDEN_ROOFS, RTOM, SERIES_USA, FANTA_20),
    FantaSeriesInfo(Bt.MONEY_WELL_THE, RTOM, SERIES_USA, FANTA_20),
    FantaSeriesInfo(Bt.GOLDEN_RIVER_THE, RTOM, SERIES_USA, FANTA_20),
    FantaSeriesInfo(Bt.TWENTY_FOUR_CARAT_MOON_THE, DIGI, SERIES_USA, FANTA_22),
    FantaSeriesInfo(Bt.STRANGE_SHIPWRECKS_THE, DIGI, SERIES_USA, FANTA_22),
    FantaSeriesInfo(Bt.FLYING_DUTCHMAN_THE, GLEA, SERIES_USA, FANTA_22),
    FantaSeriesInfo(Bt.MONEY_CHAMP_THE, DIGI, SERIES_USA, FANTA_22),
    FantaSeriesInfo(Bt.PRIZE_OF_PIZARRO_THE, SLEA, SERIES_USA, FANTA_22),
    FantaSeriesInfo(Bt.PAUL_BUNYAN_MACHINE_THE, SLEA, SERIES_USA, FANTA_24),
    FantaSeriesInfo(Bt.ISLAND_IN_THE_SKY, GLEA, SERIES_USA, FANTA_24),
    FantaSeriesInfo(Bt.PIPELINE_TO_DANGER, GLEA, SERIES_USA, FANTA_24),
    FantaSeriesInfo(Bt.ALL_AT_SEA, SLEA, SERIES_USA, FANTA_24),
    # US SHORTS
    FantaSeriesInfo(Bt.SOMETHIN_FISHY_HERE, RTOM, SERIES_USS, FANTA_12),
    FantaSeriesInfo(Bt.ROUND_MONEY_BIN_THE, RTOM, SERIES_USS, FANTA_12),
    FantaSeriesInfo(Bt.MILLION_DOLLAR_PIGEON, RTOM, SERIES_USS, FANTA_14),
    FantaSeriesInfo(Bt.OUTFOXED_FOX, RTOM, SERIES_USS, FANTA_12),
    FantaSeriesInfo(Bt.CAMPAIGN_OF_NOTE_A, RTOM, SERIES_USS, FANTA_14),
    FantaSeriesInfo(Bt.TUCKERED_TIGER_THE, RTOM, SERIES_USS, FANTA_14),
    FantaSeriesInfo(Bt.HEIRLOOM_WATCH, RTOM, SERIES_USS, FANTA_14),
    FantaSeriesInfo(Bt.FAULTY_FORTUNE, RTOM, SERIES_USS, FANTA_16),
    FantaSeriesInfo(Bt.MIGRATING_MILLIONS, RTOM, SERIES_USS, FANTA_16),
    FantaSeriesInfo(Bt.COLOSSALEST_SURPRISE_QUIZ_SHOW_THE, RTOM, SERIES_USS, FANTA_16),
    FantaSeriesInfo(Bt.SEPTEMBER_SCRIMMAGE, GLEA, SERIES_USS, FANTA_20),
    FantaSeriesInfo(Bt.FABULOUS_TYCOON_THE, DIGI, SERIES_USS, FANTA_22),
    FantaSeriesInfo(Bt.MAGIC_INK_THE, EROS, SERIES_USS, FANTA_22),
    FantaSeriesInfo(Bt.PYRAMID_SCHEME, DIGI, SERIES_USS, FANTA_22),
    FantaSeriesInfo(Bt.RETURN_TO_PIZEN_BLUFF, DIGI, SERIES_USS, FANTA_22),
    FantaSeriesInfo(Bt.HIS_HANDY_ANDY, GLEA, SERIES_USS, FANTA_22),
    FantaSeriesInfo(Bt.WITCHING_STICK_THE, DIGI, SERIES_USS, FANTA_24),
    FantaSeriesInfo(Bt.HOUND_OF_THE_WHISKERVILLES, SLEA, SERIES_USS, FANTA_24),
    FantaSeriesInfo(Bt.YOICKS_THE_FOX, DIGI, SERIES_USS, FANTA_24),
    FantaSeriesInfo(Bt.TWO_WAY_LUCK, DIGI, SERIES_USS, FANTA_24),
    # GG
    FantaSeriesInfo(Bt.TRAPPED_LIGHTNING, TOZ, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.INVENTOR_OF_ANYTHING, RTOM, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.CAT_BOX_THE, RTOM, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.GRANDMAS_PRESENT, GLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.FORECASTING_FOLLIES, RTOM, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.FISHING_MYSTERY, RTOM, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.PICNIC, SLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.SURE_FIRE_GOLD_FINDER_THE, SLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.GYRO_BUILDS_A_BETTER_HOUSE, RTOM, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.AUGUST_ACCIDENT, GLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.ROSCOE_THE_ROBOT, GLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.GETTING_THOR, SLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.KNOW_IT_ALL_MACHINE_THE, SLEA, SERIES_GG, FANTA_20),
    FantaSeriesInfo(Bt.GYRO_GOES_FOR_A_DIP, EROS, SERIES_GG, FANTA_22),
    FantaSeriesInfo(Bt.HOUSE_ON_CYCLONE_HILL_THE, DIGI, SERIES_GG, FANTA_22),
    FantaSeriesInfo(Bt.WISHING_WELL_THE, DIGI, SERIES_GG, FANTA_22),
    FantaSeriesInfo(Bt.KRANKENSTEIN_GYRO, DIGI, SERIES_GG, FANTA_22),
    FantaSeriesInfo(Bt.FIREFLY_TRACKER_THE, DIGI, SERIES_GG, FANTA_22),
    FantaSeriesInfo(Bt.FUN_WHATS_THAT, GLEA, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.GAB_MUFFER_THE, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.STUBBORN_STORK_THE, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.LOST_RABBIT_FOOT_THE, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.MILKTIME_MELODIES, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.INVENTORS_CONTEST_THE, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.OODLES_OF_OOMPH, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.WAR_PAINT, DIGI, SERIES_GG, FANTA_24),
    FantaSeriesInfo(Bt.FISHY_WARDEN, DIGI, SERIES_GG, FANTA_24),
    # WDCS
    FantaSeriesInfo(Bt.VICTORY_GARDEN_THE, GLEA, SERIES_CS, FANTA_01),
    FantaSeriesInfo(Bt.RABBITS_FOOT_THE, SLEA, SERIES_CS, FANTA_01),
    FantaSeriesInfo(Bt.LIFEGUARD_DAZE, BIGD, SERIES_CS, FANTA_01),
    FantaSeriesInfo(Bt.GOOD_DEEDS, BIGD, SERIES_CS, FANTA_01),
    FantaSeriesInfo(Bt.LIMBER_W_GUEST_RANCH_THE, BIGD, SERIES_CS, FANTA_01),
    FantaSeriesInfo(Bt.MIGHTY_TRAPPER_THE, BIGD, SERIES_CS, FANTA_01),
    FantaSeriesInfo(Bt.GOOD_NEIGHBORS, BIGD, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.SALESMAN_DONALD, BIGD, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.SNOW_FUN, BIGD, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.DUCK_IN_THE_IRON_PANTS_THE, BIGD, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.KITE_WEATHER, GLEA, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.THREE_DIRTY_LITTLE_DUCKS, BIGD, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.MAD_CHEMIST_THE, SLEA, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.RIVAL_BOATMEN, DIGI, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.CAMERA_CRAZY, DIGI, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.FARRAGUT_THE_FALCON, DIGI, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.PURLOINED_PUTTY_THE, DIGI, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.HIGH_WIRE_DAREDEVILS, DIGI, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.TEN_CENTS_WORTH_OF_TROUBLE, GLEA, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.DONALDS_BAY_LOT, GLEA, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.THIEVERY_AFOOT, GLEA, SERIES_CS, FANTA_02),
    FantaSeriesInfo(Bt.TRAMP_STEAMER_THE, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.LONG_RACE_TO_PUMPKINBURG_THE, SLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.WEBFOOTED_WRANGLER, BIGD, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.ICEBOX_ROBBER_THE, BIGD, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.PECKING_ORDER, BIGD, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.TAMING_THE_RAPIDS, BIGD, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.EYES_IN_THE_DARK, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.DAYS_AT_THE_LAZY_K, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.THUG_BUSTERS, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.GREAT_SKI_RACE_THE, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.TEN_DOLLAR_DITHER, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.SILENT_NIGHT, SLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.DONALD_TAMES_HIS_TEMPER, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.SINGAPORE_JOE, GLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.MASTER_ICE_FISHER, DIGI, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.JET_RESCUE, DIGI, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.DONALDS_MONSTER_KITE, SLEA, SERIES_CS, FANTA_03),
    FantaSeriesInfo(Bt.BICEPS_BLUES, GLEA, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.SMUGSNORKLE_SQUATTIE_THE, SLEA, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.SWIMMING_SWINDLERS, GLEA, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.PLAYIN_HOOKEY, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.GOLD_FINDER_THE, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.TURKEY_RAFFLE, GLEA, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.BILL_COLLECTORS_THE, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.CANTANKEROUS_CAT_THE, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.GOING_BUGGY, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.JAM_ROBBERS, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.PICNIC_TRICKS, DIGI, SERIES_CS, FANTA_04),
    FantaSeriesInfo(Bt.DONALDS_POSY_PATCH, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.DONALD_MINES_HIS_OWN_BUSINESS, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.MAGICAL_MISERY, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.VACATION_MISERY, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.WALTZ_KING_THE, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.MASTERS_OF_MELODY_THE, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.FIREMAN_DONALD, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.TERRIBLE_TURKEY_THE, RTOM, SERIES_CS, FANTA_05),
    FantaSeriesInfo(Bt.WINTERTIME_WAGER, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.WATCHING_THE_WATCHMAN, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.WIRED, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.GOING_APE, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.SPOIL_THE_ROD, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.ROCKET_RACE_TO_THE_MOON, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.DONALD_OF_THE_COAST_GUARD, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.GLADSTONE_RETURNS, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.LINKS_HIJINKS, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.PEARLS_OF_WISDOM, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.FOXY_RELATIONS, RTOM, SERIES_CS, FANTA_06),
    FantaSeriesInfo(Bt.CRAZY_QUIZ_SHOW_THE, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.TRUANT_OFFICER_DONALD, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.DONALD_DUCKS_WORST_NIGHTMARE, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.PIZEN_SPRING_DUDE_RANCH, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.RIVAL_BEACHCOMBERS, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.SUNKEN_YACHT_THE, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.MANAGING_THE_ECHO_SYSTEM, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.PLENTY_OF_PETS, RTOM, SERIES_CS, FANTA_07),
    FantaSeriesInfo(Bt.SUPER_SNOOPER, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.GREAT_DUCKBURG_FROG_JUMPING_CONTEST_THE, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.DOWSING_DUCKS, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.GOLDILOCKS_GAMBIT_THE, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.DONALDS_LOVE_LETTERS, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.RIP_VAN_DONALD, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.SERUM_TO_CODFISH_COVE, RTOM, SERIES_CS, FANTA_08),
    FantaSeriesInfo(Bt.WILD_ABOUT_FLOWERS, RTOM, SERIES_CS, FANTA_09),
    FantaSeriesInfo(Bt.BILLIONS_TO_SNEEZE_AT, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.OPERATION_ST_BERNARD, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.FINANCIAL_FABLE_A, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.APRIL_FOOLERS_THE, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.KNIGHTLY_RIVALS, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.POOL_SHARKS, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.TROUBLE_WITH_DIMES_THE, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.GLADSTONES_LUCK, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.TEN_STAR_GENERALS, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.TRUANT_NEPHEWS_THE, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.TERROR_OF_THE_BEAGLE_BOYS, RTOM, SERIES_CS, FANTA_10),
    FantaSeriesInfo(Bt.BIG_BIN_ON_KILLMOTOR_HILL_THE, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.GLADSTONES_USUAL_VERY_GOOD_YEAR, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.SCREAMING_COWBOY_THE, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.STATUESQUE_SPENDTHRIFTS, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.ROCKET_WING_SAVES_THE_DAY, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.GLADSTONES_TERRIBLE_SECRET, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.THINK_BOX_BOLLIX_THE, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.HOUSEBOAT_HOLIDAY, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.GEMSTONE_HUNTERS, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.SPENDING_MONEY, RTOM, SERIES_CS, FANTA_11),
    FantaSeriesInfo(Bt.HYPNO_GUN_THE, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.OMELET, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.CHARITABLE_CHORE_A, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.TURKEY_WITH_ALL_THE_SCHEMINGS, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.FLIP_DECISION, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.MY_LUCKY_VALENTINE, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.EASTER_ELECTION_THE, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.TALKING_DOG_THE, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.MUCH_ADO_ABOUT_QUACKLY_HALL, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.WORM_WEARY, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.SOME_HEIR_OVER_THE_RAINBOW, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.MASTER_RAINMAKER_THE, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.MONEY_STAIRS_THE, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.BEE_BUMBLES, RTOM, SERIES_CS, FANTA_13),
    FantaSeriesInfo(Bt.WISPY_WILLIE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.HAMMY_CAMEL_THE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.TURKEY_TROT_AT_ONE_WHISTLE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.RAFFLE_REVERSAL, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.FIX_UP_MIX_UP, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.FLOUR_FOLLIES, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.PRICE_OF_FAME_THE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.MIDGETS_MADNESS, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.SALMON_DERBY, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.CHELTENHAMS_CHOICE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.RANTS_ABOUT_ANTS, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.TRAVELLING_TRUANTS, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.TOO_SAFE_SAFE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.SEARCH_FOR_THE_CUSPIDORIA, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.NEW_YEARS_REVOLUTIONS, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.ICEBOAT_TO_BEAVER_ISLAND, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.DAFFY_TAFFY_PULL_THE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.GHOST_SHERIFF_OF_LAST_GASP_THE, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.DESCENT_INTERVAL_A, RTOM, SERIES_CS, FANTA_15),
    FantaSeriesInfo(Bt.DONALDS_RAUCOUS_ROLE, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.GOOD_CANOES_AND_BAD_CANOES, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.CHICKADEE_CHALLENGE_THE, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.UNORTHODOX_OX_THE, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.TROUBLE_INDEMNITY, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.CUSTARD_GUN_THE, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.THREE_UN_DUCKS, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.SECRET_RESOLUTIONS, RTOM, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.ICE_TAXIS_THE, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.SEARCHING_FOR_A_SUCCESSOR, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.OLYMPIC_HOPEFUL_THE, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.GOPHER_GOOF_UPS, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.IN_THE_SWIM, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.CAMPING_CONFUSION, TOZ, SERIES_CS, FANTA_17),
    FantaSeriesInfo(Bt.MASTER_THE, TOZ, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.WHALE_OF_A_STORY_A, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.SMOKE_WRITER_IN_THE_SKY, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.RUNAWAY_TRAIN_THE, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.STATUES_OF_LIMITATIONS, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.BORDERLINE_HERO, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.FEARSOME_FLOWERS, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.KNIGHT_IN_SHINING_ARMOR, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.DONALDS_PET_SERVICE, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.IN_KAKIMAW_COUNTRY, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.LOSING_FACE, TOZ, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.DAY_DUCKBURG_GOT_DYED_THE, TOZ, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.GYROS_IMAGINATION_INVENTION, TOZ, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.RED_APPLE_SAP, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.SPECIAL_DELIVERY, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.CODE_OF_DUCKBURG_THE, RTOM, SERIES_CS, FANTA_18),
    FantaSeriesInfo(Bt.SAGMORE_SPRINGS_HOTEL, GLEA, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.TENDERFOOT_TRAP_THE, GLEA, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.ROCKET_RACE_AROUND_THE_WORLD, GLEA, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.WISHING_STONE_ISLAND, SLEA, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.HALF_BAKED_BAKER_THE, GLEA, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.DODGING_MISS_DAISY, RTOM, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.MILKMAN_THE, RTOM, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.PERSISTENT_POSTMAN_THE, RTOM, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.MOCKING_BIRD_RIDGE, RTOM, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.OLD_FROGGIE_CATAPULT, RTOM, SERIES_CS, FANTA_19),
    FantaSeriesInfo(Bt.DRAMATIC_DONALD, RTOM, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.NOBLE_PORPOISES, RTOM, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.TRACKING_SANDY, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.LITTLEST_CHICKEN_THIEF_THE, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.BEACHCOMBERS_PICNIC_THE, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.MASTER_MOVER_THE, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.ROCKET_ROASTED_CHRISTMAS_TURKEY, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.SPRING_FEVER, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.LOVELORN_FIREMAN_THE, RTOM, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.FLOATING_ISLAND_THE, DIGI, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.BLACK_FOREST_RESCUE_THE, EROS, SERIES_CS, FANTA_21),
    FantaSeriesInfo(Bt.UNDER_THE_POLAR_ICE, GLEA, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.WATCHFUL_PARENTS_THE, DIGI, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.GOOD_DEEDS_THE, DIGI, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.BLACK_WEDNESDAY, GLEA, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.WAX_MUSEUM_THE, GLEA, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.MASTER_GLASSER_THE, DIGI, SERIES_DDS, FANTA_23),
    FantaSeriesInfo(Bt.KNIGHTS_OF_THE_FLYING_SLEDS, DIGI, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.RIDING_THE_PONY_EXPRESS, DIGI, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.WANT_TO_BUY_AN_ISLAND, GLEA, SERIES_CS, FANTA_23),
    FantaSeriesInfo(Bt.BALLOONATICS, GLEA, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.FROGGY_FARMER, EROS, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.DOG_SITTER_THE, SLEA, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.MYSTERY_OF_THE_LOCH, EROS, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.VILLAGE_BLACKSMITH_THE, GLEA, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.FRAIDY_FALCON_THE, SLEA, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.ROCKS_TO_RICHES, EROS, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.TURKEY_TROUBLE, EROS, SERIES_CS, FANTA_25),
    FantaSeriesInfo(Bt.MISSILE_FIZZLE, EROS, SERIES_CS, FANTA_25),
    # MISC
    FantaSeriesInfo(Bt.RIDDLE_OF_THE_RED_HAT_THE, DIGI, SERIES_MISC, FANTA_03),
    FantaSeriesInfo(Bt.DONALD_DUCK_TELLS_ABOUT_KITES, RTOM, SERIES_MISC, FANTA_15),
    FantaSeriesInfo(Bt.FANTASTIC_RIVER_RACE_THE, RTOM, SERIES_MISC, FANTA_16),
    FantaSeriesInfo(Bt.CHRISTMAS_IN_DUCKBURG, RTOM, SERIES_MISC, FANTA_21),
    FantaSeriesInfo(Bt.FORBIDIUM_MONEY_BIN_THE, EROS, SERIES_MISC, FANTA_22),
    FantaSeriesInfo(Bt.JUNGLE_HI_JINKS, GLEA, SERIES_MISC, FANTA_21),
    FantaSeriesInfo(Bt.MASTERING_THE_MATTERHORN, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.ON_THE_DREAM_PLANET, DIGI, SERIES_MISC, FANTA_24),
    FantaSeriesInfo(Bt.TRAIL_TYCOON, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.FLYING_FARMHAND_THE, RTOM, SERIES_MISC, FANTA_21),
    FantaSeriesInfo(Bt.HONEY_OF_A_HEN_A, DIGI, SERIES_MISC, FANTA_21),
    FantaSeriesInfo(Bt.WEATHER_WATCHERS_THE, DIGI, SERIES_MISC, FANTA_21),
    FantaSeriesInfo(Bt.SHEEPISH_COWBOYS_THE, DIGI, SERIES_MISC, FANTA_21),
    # FantaSeriesInfo(Bt.DAISYS_DAZED_DAYS, GLEA, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.LIBRARIAN_THE, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.DOUBLE_DATE_THE, DIGI, SERIES_MISC, FANTA_23),
    # FantaSeriesInfo(Bt.FRAMED_MIRROR_THE, GLEA, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.TV_BABYSITTER_THE, DIGI, SERIES_MISC, FANTA_23),
    # FantaSeriesInfo(Bt.NEW_GIRL_THE, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.CHRISTMAS_CHA_CHA_THE, GLEA, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.BEAUTY_QUEEN_THE, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.DONALDS_PARTY, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.TOUCHE_TOUPEE, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.FREE_SKI_SPREE, DIGI, SERIES_MISC, FANTA_23),
    # FantaSeriesInfo(Bt.MOPPING_UP, GLEA, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.SNOW_CHASER_THE, DIGI, SERIES_MISC, FANTA_23),
    FantaSeriesInfo(Bt.PIED_PIPER_OF_DUCKBURG_THE, NEA, SERIES_MISC, FANTA_24),
    FantaSeriesInfo(Bt.WHOLE_HERD_OF_HELP_THE, EROS, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.DAY_THE_FARM_STOOD_STILL_THE, SLEA, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.TRAINING_FARM_FUSS_THE, EROS, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.REVERSED_RESCUE_THE, GLEA, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.PERIL_OF_THE_BLACK_FOREST, DIT, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.LIFE_SAVERS, DIT, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.WHALE_OF_A_GOOD_DEED, GER, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.BAD_DAY_FOR_TROOP_A, COL, SERIES_MISC, FANTA_25),
    FantaSeriesInfo(Bt.LET_SLEEPING_BONES_LIE, BAR, SERIES_MISC, FANTA_25),
    # Articles
    FantaSeriesInfo(Bt.RICH_TOMASSO___ON_COLORING_BARKS, "", SERIES_EXTRAS, FANTA_07),
    FantaSeriesInfo(Bt.DON_AULT___FANTAGRAPHICS_INTRODUCTION, "", SERIES_EXTRAS, FANTA_07),
    FantaSeriesInfo(Bt.DON_AULT___LIFE_AMONG_THE_DUCKS, "", SERIES_EXTRAS, FANTA_02),
    FantaSeriesInfo(
        Bt.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD, "", SERIES_EXTRAS, FANTA_01
    ),  # noqa: E501
    FantaSeriesInfo(Bt.CENSORSHIP_FIXES_AND_OTHER_CHANGES, "", SERIES_EXTRAS, FANTA_02),
]


ALL_LISTS = "All"


def get_filtered_title_lists(
    filters: dict[str, Callable[[FantaComicBookInfo], bool]],
) -> dict[str, list[FantaComicBookInfo]]:
    titles = ALL_FANTA_COMIC_BOOK_INFO

    filtered_dict = defaultdict(list)
    for title in titles:
        fanta_info = titles[title]

        for filt, filter_func in filters.items():
            if filter_func(fanta_info):
                filtered_dict[filt].append(fanta_info)

        filtered_dict[ALL_LISTS].append(fanta_info)

    return filtered_dict


ALL_FANTA_COMIC_BOOK_INFO: FantaComicBookInfoDict = _get_all_fanta_comic_book_info()


def get_num_comic_book_titles(year_range: tuple[int, int]) -> int:
    return len(
        [
            info.fanta_chronological_number
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
            if year_range[0] <= info.comic_book_info.submitted_year <= year_range[1]
        ]
    )


def get_volume_page_resolution(volume: int) -> tuple[int, int]:
    if 5 <= volume <= 17:  # noqa: PLR2004
        return 2216, 3056
    return 2175, 3000


# def get_non_one_pager_titles(from_year: int, to_year: int) -> list[Titles]:
#     return sorted(
#             info.title
#             for info in BARKS_TITLE_INFO
#             if info.title not in ONE_PAGERS and from_year <= info.submitted_year <= to_year
#     )
