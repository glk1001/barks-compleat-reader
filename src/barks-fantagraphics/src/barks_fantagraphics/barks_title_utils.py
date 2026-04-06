from pathlib import Path

from comic_utils.comic_consts import PanelPath

from .barks_titles import (
    BARKS_TITLES,
    US_1_FC_ISSUE_NUM,
    US_2_FC_ISSUE_NUM,
    US_3_FC_ISSUE_NUM,
    Titles,
)
from .comic_book_info import BARKS_TITLE_INFO
from .comic_issues import SHORT_ISSUE_NAME, Issues

ONE_PAGERS = [
    Titles.IF_THE_HAT_FITS,
    Titles.FASHION_IN_FLIGHT,
    Titles.TURN_FOR_THE_WORSE,
    Titles.MACHINE_MIX_UP,
    Titles.BIRD_WATCHING,
    Titles.HORSESHOE_LUCK,
    Titles.BEAN_TAKEN,
    Titles.SORRY_TO_BE_SAFE,
    Titles.BEST_LAID_PLANS,
    Titles.GENUINE_ARTICLE_THE,
    Titles.JUMPING_TO_CONCLUSIONS,
    Titles.TRUE_TEST_THE,
    Titles.ORNAMENTS_ON_THE_WAY,
    Titles.TOO_FIT_TO_FIT,
    Titles.TUNNEL_VISION,
    Titles.SLEEPY_SITTERS,
    Titles.SLIPPERY_SHINE,
    Titles.FRACTIOUS_FUN,
    Titles.KING_SIZE_CONE,
    Titles.NO_NOISE_IS_GOOD_NOISE,
    Titles.TOASTY_TOYS,
    Titles.NO_PLACE_TO_HIDE,
    Titles.TIED_DOWN_TOOLS,
    Titles.NOISE_NULLIFIER,
    Titles.MATINEE_MADNESS,
    Titles.FETCHING_PRICE_A,
    Titles.TALKING_PARROT,
    Titles.TREEING_OFF,
    Titles.CHRISTMAS_KISS,
    Titles.PROJECTING_DESIRES,
    Titles.OSOGOOD_SILVER_POLISH,
    Titles.COFFEE_FOR_TWO,
    Titles.SOUPLINE_EIGHT,
    Titles.FULL_SERVICE_WINDOWS,
    Titles.RIGGED_UP_ROLLER,
    Titles.AWASH_IN_SUCCESS,
    Titles.STABLE_PRICES,
    Titles.ARMORED_RESCUE,
    Titles.CRAFTY_CORNER,
    Titles.PRANK_ABOVE_A,
    Titles.FRIGHTFUL_FACE,
    Titles.FARE_DELAY,
    Titles.MONEY_LADDER_THE,
    Titles.CHECKER_GAME_THE,
    Titles.TEMPER_TAMPERING,
    Titles.DINER_DILEMMA,
    Titles.BARBER_COLLEGE,
    Titles.FOLLOW_THE_RAINBOW,
    Titles.ITCHING_TO_SHARE,
    Titles.BALLET_EVASIONS,
    Titles.CHEAPEST_WEIGH_THE,
    Titles.BUM_STEER,
    Titles.HOSPITALITY_WEEK,
    Titles.MCDUCK_TAKES_A_DIVE,
    Titles.SLIPPERY_SIPPER,
    Titles.OIL_THE_NEWS,
    Titles.DIG_IT,
    Titles.MENTAL_FEE,
    Titles.WRONG_NUMBER,
    Titles.CASH_ON_THE_BRAIN,
    Titles.CLASSY_TAXI,
    Titles.BLANKET_INVESTMENT,
    Titles.EASY_MOWING,
    Titles.SKI_LIFT_LETDOWN,
    Titles.CAST_OF_THOUSANDS,
    Titles.COURTSIDE_HEATING,
    Titles.POWER_PLOWING,
    Titles.REMEMBER_THIS,
    Titles.DEEP_DECISION,
    Titles.SMASH_SUCCESS,
    Titles.COME_AS_YOU_ARE,
    Titles.ROUNDABOUT_HANDOUT,
    Titles.WATT_AN_OCCASION,
    Titles.DOUGHNUT_DARE,
    Titles.SWEAT_DEAL_A,
    Titles.ART_OF_SECURITY_THE,
    Titles.FASHION_FORECAST,
    Titles.MUSH,
    Titles.LUNCHEON_LAMENT,
    Titles.GOLD_RUSH,
    Titles.FIREFLIES_ARE_FREE,
    Titles.EARLY_TO_BUILD,
    Titles.CHINA_SHOP_SHAKEUP,
    Titles.BUFFO_OR_BUST,
    Titles.POUND_FOR_SOUND,
    Titles.FERTILE_ASSETS,
    Titles.BACKYARD_BONANZA,
    Titles.ALL_SEASON_HAT,
    Titles.EYES_HAVE_IT_THE,
    Titles.RELATIVE_REACTION,
    Titles.SECRET_BOOK_THE,
    Titles.TREE_TRICK,
    Titles.NET_WORTH,
    Titles.HISTORY_TOSSED,
    Titles.DOGGED_DETERMINATION,
    Titles.FORGOTTEN_PRECAUTION,
    Titles.BIG_BOBBER_THE,
    Titles.WINDFALL_OF_THE_MIND,
    Titles.RESCUE_ENHANCEMENT,
    Titles.GOING_TO_PIECES,
    Titles.HIGH_RIDER,
    Titles.THAT_SINKING_FEELING,
    Titles.BALMY_SWAMI_THE,
    Titles.WINDY_STORY_THE,
    Titles.MOOLA_ON_THE_MOVE,
    Titles.THUMBS_UP,
    Titles.BILL_WIND,
    Titles.SLEEPIES_THE,
    Titles.LIGHTS_OUT,
    Titles.IMMOVABLE_MISER,
    Titles.KITTY_GO_ROUND,
    Titles.POOR_LOSER,
    Titles.CRAWLS_FOR_CASH,
    Titles.ALL_CHOKED_UP,
    Titles.BIRD_CAMERA_THE,
    Titles.ODD_ORDER_THE,
    Titles.MONEY_HAT_THE,
    Titles.CALL_OF_THE_WILD_THE,
    Titles.TALE_OF_THE_TAPE,
    Titles.HIS_SHINING_HOUR,
    Titles.THRIFT_GIFT_A,
    Titles.UNCLE_SCROOGE___MONKEY_BUSINESS,
    Titles.COLLECTION_DAY,
    Titles.SEEING_IS_BELIEVING,
    Titles.PLAYMATES,
    Titles.RAGS_TO_RICHES,
    Titles.ART_APPRECIATION,
    Titles.FLOWERS_ARE_FLOWERS,
    Titles.GETTING_THE_BIRD,
    Titles.NEST_EGG_COLLECTOR,
    Titles.MILLION_DOLLAR_SHOWER,
    Titles.DUELING_TYCOONS,
    Titles.WISHFUL_EXCESS,
    Titles.SIDEWALK_OF_THE_MIND,
    Titles.NO_BARGAIN,
    Titles.UP_AND_AT_IT,
    Titles.FIREMAN_SCROOGE,
    Titles.SAVED_BY_THE_BAG,
    Titles.TICKING_DETECTOR,
    Titles.IT_HAPPENED_ONE_WINTER,
    Titles.LOCK_OUT_THE,
    Titles.BIGGER_THE_BEGGAR_THE,
    Titles.PLUMMETING_WITH_PRECISION,
    Titles.SNAKE_TAKE,
    Titles.LAUNDRY_FOR_LESS,
    Titles.LONG_DISTANCE_COLLISION,
    Titles.TOP_WAGES,
    Titles.DOWN_FOR_THE_COUNT,
    Titles.WASTED_WORDS,
]


def _get_shortest_issue_name(issue_name: Issues) -> str:
    return "CS" if issue_name == Issues.CS else SHORT_ISSUE_NAME[issue_name]


BARKS_ISSUE_DICT: dict[str, list[Titles]] = {
    f"{_get_shortest_issue_name(info.issue_name)} {info.issue_number}": sorted(
        inf.title
        for inf in BARKS_TITLE_INFO
        if (inf.issue_name == info.issue_name)
        and (inf.issue_number == info.issue_number)
        and (inf.title not in ONE_PAGERS)
    )
    for info in BARKS_TITLE_INFO
}
# Add Uncle Scrooge special cases:
BARKS_ISSUE_DICT[f"{SHORT_ISSUE_NAME[Issues.US]} 1"] = BARKS_ISSUE_DICT[
    f"{SHORT_ISSUE_NAME[Issues.FC]} {US_1_FC_ISSUE_NUM}"
]
BARKS_ISSUE_DICT[f"{SHORT_ISSUE_NAME[Issues.US]} 2"] = BARKS_ISSUE_DICT[
    f"{SHORT_ISSUE_NAME[Issues.FC]} {US_2_FC_ISSUE_NUM}"
]
BARKS_ISSUE_DICT[f"{SHORT_ISSUE_NAME[Issues.US]} 3"] = BARKS_ISSUE_DICT[
    f"{SHORT_ISSUE_NAME[Issues.FC]} {US_3_FC_ISSUE_NUM}"
]


def get_safe_title(title: str) -> str:
    """Return a filesystem-safe version of the title string."""
    safe_title = title.replace("\n", " ")
    safe_title = safe_title.replace("- ", "-")
    safe_title = safe_title.replace('"', "")
    return safe_title  # noqa: RET504


_FUN_WHATS_THAT = "Fun? What's That?"
_WANT_TO_BUY_AN_ISLAND = "Want to Buy an Island?"

TITLE_TO_FILENAME_SPECIAL_CASE_MAP: dict[str, str] = {
    _FUN_WHATS_THAT: "Fun What's That",
    _WANT_TO_BUY_AN_ISLAND: "Want to Buy an Island",
}
FILENAME_TO_TITLE_SPECIAL_CASE_MAP: dict[str, str] = {
    "Fun What's That": _FUN_WHATS_THAT,
    "Want to Buy an Island": _WANT_TO_BUY_AN_ISLAND,
}


def get_filename_from_title(title: Titles, ext: str) -> str:
    """Return the filename for a given title enum member."""
    return get_filename_from_title_str(BARKS_TITLES[title], ext)


def get_filename_from_title_str(title_str: str, ext: str) -> str:
    """Return the filename for a given title string."""
    return TITLE_TO_FILENAME_SPECIAL_CASE_MAP.get(title_str, title_str) + ext


def get_title_str_from_filename(filename: str | PanelPath) -> str:
    """Return the title string for a given filename."""
    path: PanelPath = Path(filename) if isinstance(filename, str) else filename

    # Can't use 'stem' on directories because a title may contain a '.'
    name = path.name if path.is_dir() else path.stem

    return FILENAME_TO_TITLE_SPECIAL_CASE_MAP.get(name, name)
