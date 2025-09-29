import sys
from pathlib import Path

ZIP_FILE_EXT = ".zip"
CBZ_FILE_EXT = ".cbz"
JPG_FILE_EXT = ".jpg"
PNG_FILE_EXT = ".png"
SVG_FILE_EXT = ".svg"
JSON_FILE_EXT = ".json"
TEXT_FILE_EXT = ".txt"

JAN = 1
FEB = 2
MAR = 3
APR = 4
MAY = 5
JUN = 6
JUL = 7
AUG = 8
SEP = 9
OCT = 10
NOV = 11
DEC = 12

MONTH_AS_SHORT_STR: dict[int, str] = {
    JAN: "Jan",
    FEB: "Feb",
    MAR: "Mar",
    APR: "Apr",
    MAY: "May",
    JUN: "Jun",
    JUL: "Jul",
    AUG: "Aug",
    SEP: "Sep",
    OCT: "Oct",
    NOV: "Nov",
    DEC: "Dec",
}

MONTH_AS_LONG_STR: dict[int, str] = {
    JAN: "January",
    FEB: "February",
    MAR: "March",
    APR: "April",
    MAY: "May",
    JUN: "June",
    JUL: "July",
    AUG: "August",
    SEP: "September",
    OCT: "October",
    NOV: "November",
    DEC: "December",
}

ROMAN_NUMERALS = {
    1: "i",
    2: "ii",
    3: "iii",
    4: "iv",
    5: "v",
    6: "vi",
    7: "vii",
    8: "viii",
    9: "ix",
    10: "x",
}


def _get_pyinstaller_bundled_main_dir() -> Path | None:
    try:
        # noinspection PyProtectedMember
        return Path(sys._MEIPASS)  # noqa: SLF001
    except AttributeError:
        return None


PYINSTALLER_BUNDLED_MAIN_DIR = _get_pyinstaller_bundled_main_dir()
IS_PYINSTALLER_BUNDLE = PYINSTALLER_BUNDLED_MAIN_DIR is not None
