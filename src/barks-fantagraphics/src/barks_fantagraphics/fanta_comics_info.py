# ruff: noqa: ERA001

import collections
from collections import OrderedDict, defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from . import barks_titles as bt
from .barks_titles import BARKS_TITLE_INFO, BARKS_TITLES, ComicBookInfo, Titles
from .comic_issues import ISSUE_NAME, Issues


@dataclass(frozen=True, slots=True)
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


def get_fanta_volume_from_str(volume_str: str) -> int:
    assert volume_str.startswith("FANTA_")
    return int(volume_str[-2:])


@dataclass(frozen=True, slots=True)
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
FANTA_29 = "FANTA_29"

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
VOLUME_29 = f"{CB} Vol. 29 - {DD} - The Lonely Lighthouse on Cape Quack {SRC_SALEM}"

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
    f"{get_fanta_volume_str(29)}": FantaBook(VOLUME_29, FAN, 29, 2025, 218),
}

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
    29: "29 - Donald Duck - The Lonely Lighthouse on Cape.cbz",
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
EGMONT = "Egmont"


@dataclass(frozen=True, slots=True)
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

US_CENSORED_TITLE_ENUMS = [Titles.SILENT_NIGHT, Titles.MILKMAN_THE]
US_CENSORED_TITLES = [BARKS_TITLES[t] for t in US_CENSORED_TITLE_ENUMS]
CENSORED_TITLES = [bt.GOOD_DEEDS, bt.SILENT_NIGHT, bt.MILKMAN_THE]
HAND_RESTORED_TITLES = [bt.GOOD_DEEDS, bt.SILENT_NIGHT]
SILENT_NIGHT_PUBLICATION_ISSUE = "Gemstone's Christmas Parade, No.3, 2005"

# Late import: fanta_series_data imports FantaSeriesInfo and constants from this module.
# The circular import is safe because those symbols are fully defined above this line.
from .fanta_series_data import SERIES_INFO  # noqa: E402

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


def get_fanta_info(title: Titles) -> FantaComicBookInfo | None:
    """Look up the FantaComicBookInfo for a given title enum, or return None if not found."""
    title_str = BARKS_TITLES[title]
    return ALL_FANTA_COMIC_BOOK_INFO.get(title_str)


def get_num_comic_book_titles(year_range: tuple[int, int]) -> int:
    return len(
        [
            info.fanta_chronological_number
            for info in ALL_FANTA_COMIC_BOOK_INFO.values()
            if year_range[0] <= info.comic_book_info.submitted_year <= year_range[1]
        ]
    )


# def get_non_one_pager_titles(from_year: int, to_year: int) -> list[Titles]:
#     return sorted(
#             info.title
#             for info in BARKS_TITLE_INFO
#             if info.title not in ONE_PAGERS and from_year <= info.submitted_year <= to_year
#     )
