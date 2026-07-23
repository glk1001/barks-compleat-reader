"""Series names, colorist names, volume keys, and the FantaSeriesInfo record.

Leaf module shared by `fanta_comics_info` and `fanta_series_data`. It must not
import from either of them - `fanta_series_data` builds its SERIES_INFO table
from these definitions, and `fanta_comics_info` re-exports them for
backward compatibility.
"""

from dataclasses import dataclass

from .barks_titles import Titles
from .comic_issues import ISSUE_NAME, Issues


def get_fanta_volume_str(volume: int) -> str:
    return f"FANTA_{volume:02}"


def get_fanta_volume_from_str(volume_str: str) -> int:
    assert volume_str.startswith("FANTA_")
    return int(volume_str[-2:])


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

SERIES_DDA = ISSUE_NAME[Issues.DD] + " Adventures"
SERIES_USA = ISSUE_NAME[Issues.US] + " Adventures"
SERIES_DDS = ISSUE_NAME[Issues.DD] + " Short Stories"
SERIES_USS = ISSUE_NAME[Issues.US] + " Short Stories"
SERIES_CS = ISSUE_NAME[Issues.CS]
SERIES_GG = "Gyro Gearloose"
SERIES_MISC = "Misc"
SERIES_EXTRAS = "Extras"
SERIES_ONE_PAGERS = "One Pagers"
SERIES_COVERS = "Covers"

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
MARJ = "Marie Javins"
SUMH = "Summer Hinton"


@dataclass(frozen=True, slots=True)
class FantaSeriesInfo:
    title: Titles
    colorist: str
    series_name: str
    fanta_volume: str
    number_in_series: int = -1
