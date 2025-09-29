import csv
import functools
import os.path
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src import comics_info
from src.comics_info import (
    ComicBookInfo,
    CH,
    CP,
    CS,
    DD,
    FC,
    FG,
    KI,
    MC,
    US,
    VP,
)
from src.comics_info import MONTH_AS_LONG_STR, get_formatted_day
from src.consts import THIS_DIR, SUBMISSION_DATES_SUBDIR

from read_stories import get_all_stories, StoryInfo
from read_sub_dates import get_all_submitted_info, SubmittedInfo, SubmittedInfoDict

MONTH_AS_SHORT_STR: Dict[int, str] = {
    -1: "   ",
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

MONTH_AS_INT: Dict[str, int] = {
    "<none>": -1,
    "January": comics_info.JAN,
    "February": comics_info.FEB,
    "March": comics_info.MAR,
    "April": comics_info.APR,
    "May": comics_info.MAY,
    "June": comics_info.JUN,
    "July": comics_info.JUL,
    "August": comics_info.AUG,
    "September": comics_info.SEP,
    "October": comics_info.OCT,
    "November": comics_info.NOV,
    "December": comics_info.DEC,
}

SUBMISSION_DATES_DIR = str(os.path.join(THIS_DIR, SUBMISSION_DATES_SUBDIR))

COMICS_AND_STORIES_ISSUE_NAME = "W WDC"
COMICS_AND_STORIES_FILENAME = "sub-dates-cs-cleaned.txt"
FOUR_COLOR_ISSUE_NAME = "W OS"
FOUR_COLOR_FILENAME = "sub-dates-os-cleaned.txt"
DONALD_DUCK_ISSUE_NAME = "W DD"
DONALD_DUCK_FILENAME = "sub-dates-dd-cleaned.txt"
UNCLE_SCROOGE_ISSUE_NAME = "W US"
UNCLE_SCROOGE_FILENAME = "sub-dates-us-cleaned.txt"
CHRISTMAS_PARADE_ISSUE_NAME = "W CP"
CHRISTMAS_PARADE_FILENAME = "sub-dates-cp-cleaned.txt"
VACATION_PARADE_ISSUE_NAME = "W VP"
VACATION_PARADE_FILENAME = "sub-dates-vp-cleaned.txt"
FIRESTONE_GIVEAWAYS_FILENAME = "sub-dates-fg-cleaned.txt"
FIRESTONE_GIVEAWAYS_ISSUE_NAME = "W FGW"
KITES_GIVEAWAYS_FILENAME = "sub-dates-ki-cleaned.txt"
KITES_GIVEAWAYS_ISSUE_NAME = "W KGA"
MARCH_OF_COMICS_GIVEAWAYS_FILENAME = "sub-dates-moc-cleaned.txt"
MARCH_OF_COMICS_GIVEAWAYS_ISSUE_NAME = "W MOC"
CHEERIOS_GIVEAWAYS_FILENAME = "sub-dates-ch-cleaned.txt"
CHEERIOS_GIVEAWAYS_ISSUE_NAME = "W CGW"


@dataclass
class ComicBookInfo:
    issue_name: str
    issue_number: int
    issue_year: int
    issue_month: int
    submitted_year: int
    submitted_month: int
    submitted_day: int


all_stories: List[StoryInfo] = get_all_stories()

all_cs_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, COMICS_AND_STORIES_FILENAME),
    COMICS_AND_STORIES_ISSUE_NAME,
)
all_fc_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, FOUR_COLOR_FILENAME), FOUR_COLOR_ISSUE_NAME
)
all_dd_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, DONALD_DUCK_FILENAME), DONALD_DUCK_ISSUE_NAME
)
all_us_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, UNCLE_SCROOGE_FILENAME), UNCLE_SCROOGE_ISSUE_NAME
)
all_moc_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, MARCH_OF_COMICS_GIVEAWAYS_FILENAME),
    MARCH_OF_COMICS_GIVEAWAYS_ISSUE_NAME,
)
all_cp_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, CHRISTMAS_PARADE_FILENAME),
    CHRISTMAS_PARADE_ISSUE_NAME,
)
all_vp_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, VACATION_PARADE_FILENAME),
    VACATION_PARADE_ISSUE_NAME,
)
all_fg_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, FIRESTONE_GIVEAWAYS_FILENAME),
    FIRESTONE_GIVEAWAYS_ISSUE_NAME,
)
all_ch_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, CHEERIOS_GIVEAWAYS_FILENAME),
    CHEERIOS_GIVEAWAYS_ISSUE_NAME,
)
all_ki_sub_dates: SubmittedInfoDict = get_all_submitted_info(
    os.path.join(SUBMISSION_DATES_DIR, KITES_GIVEAWAYS_FILENAME),
    KITES_GIVEAWAYS_ISSUE_NAME,
)


def get_formatted_submitted_date(info: ComicBookInfo) -> str:
    month = "<none>" if info.submitted_month == -1 else MONTH_AS_LONG_STR[info.submitted_month]
    return f"{month} {get_formatted_day(info.submitted_day)}, {info.submitted_year}"


TITLE_FIXUPS: dict[str, str] = {
    "If the Hat Fits": "hats and huge sombrero",
    "Adventure Down Under": 'in Adventure "Down Under"',
    "Fashion in Flight": "big visors add snap to a car",
    "Turn For the Worse": "two ways to find donald duck",
    "Machine Mix-up": "modern kitchen tryout",
    "Bird Watching": "two old crowes",
    "Horseshoe Luck": "horseshoes and bad luck",
    "Bean Taken": "beanz in jar",
    "Sorry to be Safe": "awful scared of broken windows",
    "Best Laid Plans": "pretending to be sick",
    "The Genuine Article": "worm holes test",
    "Jumping to Conclusions": "christmas shoveling",
    "The True Test": "unbreakable toys",
    "Ornaments on the Way": "swell christmas tree ornaments",
    "Too Fit to Fit": "awful tight tuxedo",
    "Tunnel Vision": "television fight",
    "Sleepy Sitters": "bowling babysitter",
    "Slippery Shine": "putting wax on too thick",
    "Fractious Fun": "playing games with daisy",
    "King-Size Cone": "one ice cream cone each",
    "Toasty Toys": "toys burning in fireplace",
    "No Place to Hide": "kids find christmas presents",
    "Tied-Down Tools": "box of tools for christmas",
    "Noise Nullifier": "quiet!",
    "Matinee Madness": "movie ticket office",
    "A Fetching Price": "bet dog won't bring back stick",
    "Donald's Grandma Duck": "bird's nest mailbox",
    "Ten-Star Generals": "merit badges try out",
    "Attic Antics": "attic fixed into guest room",
    "Treeing Off": "improvised christmas tree ornaments",
    "Christmas Kiss": "teenie weenie mistletoe kiss",
    "Projecting Desires": "microfilm christmas list",
    "Osogood Silver Polish": "osogood silver polish",
    "Coffee for Two": "second cup of coffee free",
    "Soupline Eight": "soupline eight raffle",
    "Full-Service Windows": "professional sparkle",
    "Rigged-Up Roller": "loaned roller",
    "Awash in Success": "park fountain towels",
    "Stable Prices": "riding stable robbery",
    "Armored Rescue": "going to rescue daisy's cat",
    "Crafty Corner": "painted into a corner",
    "A Prank Above": "buggy on roof",
    "Frightful Face": "awful masks",
    "Fare Delay": "waiting for traffic light to change",
    "The Money Ladder": "money bale ladder",
    "The Checker Game": "game for a billion dollars",
    "The Horseradish Story": "case of horse",
    "Barber College": "trimming sideburns",
    "The Round Money Bin": "water tank bin",
    "Follow the Rainbow": "money bin at end of rainbow",
    "Itching to Share": "trained fleas",
    "Ballet Evasions": "master of ballet dancing",
    "The Menehune Mystery": "menehunes island",
    "The Cheapest Weigh": "a penny to get weighed",
    "Bum Steer": "hold out your hands",
    "The Secret of Atlantis": "sunken city",
    "McDuck Takes a Dive": "native boys dive for pennies",
    "Slippery Sipper": "one soda and five straws",
    "The Price of Fame": "tv station audition ambition",
    "Oil the News": "big oil strike",
    "Tralla La": "valley of tralla la",
    "Outfoxed Fox": "old man fox's money",
    "Dig it!": "digging on beach",
    "Mental Fee": "penny for thoughts",
    "Cheltenham's Choice": "chipmunk mascot",
    "Temper Tampering": "wonderful day",
    "Billion Dollar Pigeon": "carrier pigeon",
    "Diner Dilemma": "half a cup of coffee",
    "Travelling Truants": "truant boat adventure",
    "Rants about Ants": "ant city aquarium",
    "Too Safe Safe": "impervi",
    "The Mysterious Stone Ray": "message from uncharted island",
    "Cash on the Brain": "not even money in pockets",
    "A Campaign of Note": "city treasurer candidate",
    "Classy Taxi!": "taxi on a rainy day",
    "Blanket Investment": "king size electric blanket",
    "Search for the Cuspidora": "submarine christmas eve",
    "Iceboat to Beaver Island": "iceboat mail carrier",
    "Easy Mowing": "fabulous lawn mower",
    "Ski Lift Letdown": "free skiing",
    "Cast of Thousands": "fishing and working at once",
    "The Daffy Taffy Pull": "taffy trouble",
    "Deep Decision": "folding cup",
    "Smash Success": "bad curve pottery",
    "Come as You are": "come",
    "Roundabout Handout": "squirrel and nuts",
    "Watt an Occasion": "seventy",
    "Doughnut Dare": "standard size cup",
    "A Sweat Deal": "joe's oasis",
    "Courtside Heating": "heating pads",
    "Dogcatcher Duck": "dogcather leaving duckburg",
    "Remember This": "first paper route",
    "Power Plowing": "snow cleared off of street",
    "The Art of Security": "dark night",
    "Trapped Lightning": "lightning bolt in lead box",
    "Fashion Forecast": "spring is here",
    "Faulty Fortune": "dinner at ritzmore cafe",
    "Inventor of Anything": "super",
    "Luncheon Lament": "canny brannies deeds",
    "Gold Rush": "gold pans on beach",
    "Fireflies are Free": "glow worms and electric light",
    "The Second-Richest Duck": 'in "the second"',
    "Buffo or Bust": "impression in the mud",
    "The Cat Box": "cat language",
    "Migrating Millions": "money bin progress",
    "Pound for Sound": "duckburg symphony orchestra",
    "Fertile Assets": "minerals into soil",
    "Forecasting Follies": "forecasting the future",
    "The Colossalest Surprise Quiz Show": "collossalest surprise quiz show",
    "Backyard Bonanza": "fuel oil price",
    "Knight in Shining Armor": "suppressed desire party",
    "Early to Build": "early american building",
    "Fishing Mystery": "a way to catch fish",
    "The Eyes Have It": "not so good eyesight",
    "China Shop Shakeup": "fine china!",
    "Gyro's Imagination Invention": "imagining machine",
    "Net Worth": "safety net",
    "The Sure-Fire Gold Finder": "device for finding gold",
    "Relative Reaction": "wait a minute!",
    "Losing Face": "great head park",
    "History Tossed": "dollar across river",
    "Gyro Builds a Better House": "soft pillowy house",
    "The Tenderfoot Trap": "wild burro contest",
    "Roscoe the Robot": "robot roscoe",
    "Rescue Enhancement": "desert island help",
    "The Code of Duckburg": "reindeer as christmas present",
    "The Persistent Postman": "helicopter mailman",
    "Getting Thor": "easy ways to get rich",
    "Windfall of the Mind": "scarecrow",
    "Dogged Determination": "loaned money to buy a dog",
    "Forgotten Precaution": "self",
    "Rocket Race Around the World": "rocket race around world",
    "Dodging Miss Daisy": "spring house cleaning",
    "Going to Pieces": "parts for old car",
    "The Know-It-All Machine": "glad! sad! mad!",
    "High Rider": "only one",
    "That Sinking Feeling": "captain goes down with ship",
    "Fearsome Flowers": "duckburg garden club",
    "Mocking Bird Ridge": "the right kind of echoes",
    "Old Froggie Catapult": "a big old bull",
    "Moola on the Move": "gravel truck and hay wagon",
    "Gyro Goes for a Dip": "disgraceful swimming pool",
    "All Choked Up": "roll that would choke a horse",
    "Lights Out": "electric light rates go up!",
    "Noble Porpoises": "catching porpoises",
    "The Twenty-four Carat Moon": "and the twenty",
    "The House on Cyclone Hill": "cyclone warning bell",
    "Rocket-Roasted Christmas Turkey": "stratosphere christmas turkey",
    "Pyramid Scheme": "park benches",
    "The Wishing Well": "wishing well order",
    "Immovable Miser": "king nutmost the rash",
    "Bill Wind": "butterfly and ten",
    "News from Afar": "newspaper and binoculars",
    "Kitty-Go-Round": "basket of kittens",
    "The Floating Island": "new",
    "The Watchful Parents": "watchful parents club",
    "The Paul Bunyan Machine": 'and the "paul bunyan" machine',
    "Thumbs Up": "thumps up",
    "Dueling Tycoons": "dueling field",
    "Wishful Excess": "genie of the lamp",
    "Sidewalk of the Mind": "coin glued to sidewalk",
    "Fireman Scrooge": "volunteer fire dept.",
    "Feud and Far Between": "fued and far between",
    "No Bargain": "light bulb testing",
    "Up and at It": "gadget that can find gold",
    "Saved by the Bag!": "stranded on raft",
    "Ticking Detector": "lost watch",
    "The Bigger the Beggar": "five dollars for cup of coffee",
    "The Lock Out": "click pat pat",
    "Plummeting with Precision": "parachute jumping school",
    "Snake Take": "hiss!",
    "Laundry for Less": "laundry soap",
    "Long Distance Collision": "front bumper accident",
    "Wasted Words": "fine fellow",
    "Down for the Count": "head money counter",
    "It Happened One Winter": "fur coat",
}
TITLE_FIXUPS = {key.lower(): TITLE_FIXUPS[key] for key in TITLE_FIXUPS}


def get_submitted_date(title: str, sub_info_list: List[SubmittedInfo]) -> Tuple[int, int, int]:
    def get_date(info: SubmittedInfo) -> Tuple[int, int, int]:
        year = -1 if info.submitted_year == "<none>" else int(info.submitted_year)
        month = MONTH_AS_INT[info.submitted_month]
        day = -1 if info.submitted_day in ["<none>", "?"] else int(info.submitted_day)
        return year, month, day

    if len(sub_info_list) == 1:
        return get_date(sub_info_list[0])

    orig_title = title
    for info in sub_info_list:
        title = title.lower()
        info_title = info.title.lower()
        if title in info_title or info_title in title:
            return get_date(info)
        if title in TITLE_FIXUPS:
            title = TITLE_FIXUPS[title]
            if title in info_title or info_title in title:
                return get_date(info)

    for info in sub_info_list:
        print(f'    "": "{info.title.lower()}",')

    raise Exception(f"Key Error: Could not find '{orig_title}' in {sub_info_list}.")


def get_comic_book_info(story: StoryInfo) -> ComicBookInfo:
    if story.issue_name == "Walt Disney's Comics and Stories":
        sub_info = all_cs_sub_dates[(COMICS_AND_STORIES_ISSUE_NAME, story.issue_num)]
        issue_name = CS
    elif story.issue_name == "Donald Duck Four Color":
        issue_name = FC
        sub_info = all_fc_sub_dates[(FOUR_COLOR_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Mickey Mouse Four Color":
        issue_name = FC
        sub_info = all_fc_sub_dates[(FOUR_COLOR_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Uncle Scrooge Four Color":
        issue_name = FC
        sub_info = all_fc_sub_dates[(FOUR_COLOR_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Donald Duck":
        issue_name = DD
        sub_info = all_dd_sub_dates[(DONALD_DUCK_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Uncle Scrooge":
        issue_name = US
        sub_info = all_us_sub_dates[(UNCLE_SCROOGE_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Walt Disney's Christmas Parade":
        issue_name = CP
        sub_info = all_cp_sub_dates[(CHRISTMAS_PARADE_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Walt Disney's Vacation Parade":
        issue_name = VP
        sub_info = all_vp_sub_dates[(VACATION_PARADE_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Boys' and Girls' March of Comics":
        issue_name = MC
        sub_info = all_moc_sub_dates[(MARCH_OF_COMICS_GIVEAWAYS_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Firestone Giveaway":
        issue_name = FG
        sub_info = all_fg_sub_dates[(FIRESTONE_GIVEAWAYS_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Cheerios Giveaway":
        issue_name = CH
        sub_info = all_ch_sub_dates[(CHEERIOS_GIVEAWAYS_ISSUE_NAME, story.issue_num)]
    elif story.issue_name == "Kites Giveaway":
        issue_name = KI
        sub_info = all_ki_sub_dates[(KITES_GIVEAWAYS_ISSUE_NAME, story.issue_num)]
    else:
        issue_name = ""
        sub_info = None
        print(f"Unknown story: {story.title}, {story.issue_name}")

    if not sub_info:
        return None

    sub_date = get_submitted_date(story.title, sub_info)

    return ComicBookInfo(
        issue_name,
        int(story.issue_num),
        int(story.issue_year),
        MONTH_AS_INT[story.issue_month],
        sub_date[0],
        sub_date[1],
        sub_date[2],
    )


all_comic_book_info: List[Tuple[str, ComicBookInfo]] = []
for story in all_stories:
    comic_book_info = get_comic_book_info(story)
    if comic_book_info:
        all_comic_book_info.append((story.title, comic_book_info))


def compare(info1: Tuple[str, ComicBookInfo], info2: Tuple[str, ComicBookInfo]) -> int:
    cb_info1 = info1[1]
    cb_info2 = info2[1]
    if cb_info1.submitted_year < cb_info2.submitted_year:
        return -1
    if cb_info1.submitted_year > cb_info2.submitted_year:
        return +1
    if cb_info1.submitted_month < cb_info2.submitted_month:
        return -1
    if cb_info1.submitted_month > cb_info2.submitted_month:
        return +1
    if cb_info1.submitted_day < cb_info2.submitted_day:
        return -1
    if cb_info1.submitted_day > cb_info2.submitted_day:
        return +1
    return 0


all_comic_book_info = sorted(all_comic_book_info, key=functools.cmp_to_key(compare))

# Now dump the sorted comic book info to a csv.
output_file = "/tmp/barks-stories.csv"
with open(output_file, "w") as f:
    for comic_info in all_comic_book_info:
        comic_title = comic_info[0]
        comic_book_info = comic_info[1]
        f.write(
            f'"{comic_title}","{comic_book_info.issue_name}",{comic_book_info.issue_number},'
            f"{comic_book_info.issue_year},{comic_book_info.issue_month},"
            f"{comic_book_info.submitted_year},"
            f"{comic_book_info.submitted_month},"
            f"{comic_book_info.submitted_day}\n"
        )

# Now retrieve and print the formatted csv as a check.
with open(output_file) as csv_file:
    all_comic_book_info: List[Tuple[str, ComicBookInfo]] = []
    reader = csv.reader(csv_file, delimiter=",", quotechar='"')

    max_title_len = 0
    max_issue_name = 0
    for row in reader:
        comic_title = row[0]
        issue_name = row[1]
        all_comic_book_info.append(
            (
                comic_title,
                ComicBookInfo(
                    issue_name,
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                    int(row[5]),
                    int(row[6]),
                    int(row[7]),
                ),
            )
        )

        if len(comic_title) > max_title_len:
            max_title_len = len(comic_title)
        if len(issue_name) > max_issue_name:
            max_issue_name = len(issue_name)

    for comic_info in all_comic_book_info:
        comic_title = comic_info[0]
        comic_book_info = comic_info[1]
        print(
            f'"{comic_title:<{max_title_len}}", "{comic_book_info.issue_name:<{max_issue_name}}",'
            f" {comic_book_info.issue_number:>4},"
            f" {MONTH_AS_SHORT_STR[comic_book_info.issue_month]:>3}"
            f" {comic_book_info.issue_year:>4},"
            f" {get_formatted_submitted_date(comic_book_info):<19}"
        )
