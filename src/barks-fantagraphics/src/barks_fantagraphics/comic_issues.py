from enum import IntEnum, auto


class Issues(IntEnum):
    """The comic series Barks's work came out in; the value indexes the name lists below."""

    ANDERS = 0
    CH = auto()
    CID = auto()
    CP = auto()
    CS = auto()
    DD = auto()
    DIBP = auto()
    FC = auto()
    FG = auto()
    HDL = auto()
    KI = auto()
    MC = auto()
    MMA = auto()
    SF = auto()
    US = auto()
    USA = auto()
    USGTD = auto()
    VP = auto()
    EXTRAS = auto()


# Keyed by issue, so that a new `Issues` member with no name here fails at import (the
# lists below are built in `Issues` order) rather than shifting every later name by one.
_SHORT_ISSUE_NAMES: dict[Issues, str] = {
    Issues.ANDERS: "ANDERS",
    Issues.CH: "CG",
    Issues.CID: "CID",
    Issues.CP: "CP",
    Issues.CS: "WDCS",
    Issues.DD: "DD",
    Issues.DIBP: "DIBP",
    Issues.FC: "FC",
    Issues.FG: "FG",
    Issues.HDL: "HDL",
    Issues.KI: "KG",
    Issues.MC: "MOC",
    Issues.MMA: "MMA",
    Issues.SF: "SF",
    Issues.US: "US",
    Issues.USA: "USA",
    Issues.USGTD: "USGTD",
    Issues.VP: "VP",
    Issues.EXTRAS: "EX",
}

_ISSUE_NAMES: dict[Issues, str] = {
    Issues.ANDERS: "Anders And & Co",
    Issues.CH: "Cheerios Giveaway",
    Issues.CID: "Christmas in Disneyland",
    Issues.CP: "Christmas Parade",
    Issues.CS: "Comics and Stories",
    Issues.DD: "Donald Duck",
    Issues.DIBP: "Disneyland Birthday Party",
    Issues.FC: "Four Color",
    Issues.FG: "Firestone Giveaway",
    Issues.HDL: "Huey, Dewey and Louie Junior Woodchucks",
    Issues.KI: "Kites Giveaway",
    Issues.MC: "Boys' and Girls' March of Comics",
    Issues.MMA: "Mickey Mouse Almanac",
    Issues.SF: "Summer Fun",
    Issues.US: "Uncle Scrooge",
    Issues.USA: "Uncle Scrooge Adventures",
    Issues.USGTD: "Uncle Scrooge Goes to Disneyland",
    Issues.VP: "Vacation Parade",
    Issues.EXTRAS: "Extras (Non-Barks)",
}

# Indexed by `Issues`: SHORT_ISSUE_NAME[Issues.CS] is "WDCS".
SHORT_ISSUE_NAME = [_SHORT_ISSUE_NAMES[issue] for issue in Issues]
ISSUE_NAME = [_ISSUE_NAMES[issue] for issue in Issues]

ISSUE_NAME_WRAPPED = {
    Issues.US: "Uncle\nScrooge",
    Issues.FG: "Firestone\nGiveaway",
    Issues.HDL: "Huey, Dewey\nand Louie\nJunior Woodchucks",
    Issues.USGTD: "Uncle Scrooge\nGoes\nto\nDisneyland",
    Issues.CID: "Christmas\nin\nDisneyland",
}


def get_shortest_issue_name(issue_name: Issues) -> str:
    """Return an issue's code as its titles' rows show it: its short name, but CS for WDCS.

    Args:
        issue_name: The issue.

    Returns:
        The code, such as "CS", "FC" or "MOC".

    """
    return "CS" if issue_name == Issues.CS else SHORT_ISSUE_NAME[issue_name]
