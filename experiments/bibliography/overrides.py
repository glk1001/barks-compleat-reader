"""Manual override tables for ambiguous / unresolvable bibliography matches.

Two kinds of overrides:

* ``Titles.X: (Issues.US, 25, 1959, 1)`` — pin a title to a specific bibliography
  entry: (issue_name, issue_number, issue_year, entry_index_within_issue). The
  ``entry_index`` is the 0-based position printed by the reconciliation report.

* ``Titles.X: None`` — the title has *no* counterpart in Barrier's 1978
  bibliography (a one-page gag Barrier left unplaced, an unpublished story, or a
  story comic_book_info assigns to an issue where Barrier does not list it). These
  are real validation findings, recorded here so the matcher stops flagging them.

Most of the pinned entries below are one-page "gag" titles whose punning name
never appears in the description (e.g. "Itching to Share" -> a trained-fleas gag,
"Power Plowing" -> a snowplow gag). Within each issue the assignment is a clean
bijection anchored by at least one unmistakable description match, so the rest
follow by elimination. The auto-matcher deliberately will not guess these (it
only pairs on an unambiguous same-date partner), so they live here.
"""

from __future__ import annotations

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import Issues

OVERRIDES: dict[Titles, tuple[Issues, int, int, int] | None] = {
    # --- title-less gag clusters, pinned by description --------------------- #
    # Four Color 178
    Titles.FASHION_IN_FLIGHT: (Issues.FC, 178, 1947, 0),     # Donald buys a huge visor for his tiny car
    Titles.TURN_FOR_THE_WORSE: (Issues.FC, 178, 1947, 2),    # Donald plays a joke by giving some misleading directions
    Titles.MACHINE_MIX_UP: (Issues.FC, 178, 1947, 3),        # "new modern kitchen, unhappy results"
    # Four Color 199
    Titles.SORRY_TO_BE_SAFE: (Issues.FC, 199, 1948, 1),      # "vacant lot where the nephews can play"
    Titles.BEST_LAID_PLANS: (Issues.FC, 199, 1948, 3),       # "pretends to be sick so the nephews cook"
    Titles.GENUINE_ARTICLE_THE: (Issues.FC, 199, 1948, 4),   # "tests the authenticity of worm holes"
    # Four Color 203
    Titles.JUMPING_TO_CONCLUSIONS: (Issues.FC, 203, 1948, 1),# "Donald returns the nephews’ presents"
    Titles.TRUE_TEST_THE: (Issues.FC, 203, 1948, 3),         # "Donald tests toys to see how sturdy"
    Titles.ORNAMENTS_ON_THE_WAY: (Issues.FC, 203, 1948, 4),  # "Donald acquires some unusual decorations"
    # Four Color 238
    Titles.SLIPPERY_SHINE: (Issues.FC, 238, 1949, 1),        # "freshly waxed floors"
    Titles.FRACTIOUS_FUN: (Issues.FC, 238, 1949, 3),         # "Daisy loses her temper at sports"
    # Four Color 367
    Titles.TREEING_OFF: (Issues.FC, 367, 1952, 1),           # "tree ornaments out of golf balls"
    Titles.CHRISTMAS_KISS: (Issues.FC, 367, 1952, 3),        # "mistletoe to win a kiss from Daisy"
    Titles.PROJECTING_DESIRES: (Issues.FC, 367, 1952, 4),    # "Christmas list the size of a postage stamp"
    # Four Color 456
    Titles.FARE_DELAY: (Issues.FC, 456, 1953, 1),            # "waits for the light before getting in a taxi"
    Titles.CHECKER_GAME_THE: (Issues.FC, 456, 1953, 5),      # "plays checkers ... with himself"
    # Four Color 495
    Titles.ITCHING_TO_SHARE: (Issues.FC, 495, 1953, 5),      # "trained fleas to a meal"
    Titles.FOLLOW_THE_RAINBOW: (Issues.FC, 495, 1953, 3),    # remaining slot
    # Uncle Scrooge 5
    Titles.MCDUCK_TAKES_A_DIVE: (Issues.US, 5, 1954, 3),     # "native boys risk their lives for pennies"
    Titles.SLIPPERY_SIPPER: (Issues.US, 5, 1954, 4),         # "one soda, and five straws"
    # Uncle Scrooge 9
    Titles.EASY_MOWING: (Issues.US, 9, 1955, 1),             # "'lawnmower' — a sheep"
    Titles.CAST_OF_THOUSANDS: (Issues.US, 9, 1955, 5),       # "'fishing' in his money bin"
    # Uncle Scrooge 10
    Titles.SMASH_SUCCESS: (Issues.US, 10, 1955, 4),          # "pottery shop on a bad curve in the road"
    Titles.DEEP_DECISION: (Issues.US, 10, 1955, 1),          # remaining slot ("folding cup to the diner")
    # Uncle Scrooge 13
    Titles.ART_OF_SECURITY_THE: (Issues.US, 13, 1956, 1),    # "paints a policeman ... to scare burglars"
    Titles.FASHION_FORECAST: (Issues.US, 13, 1956, 4),       # "spring has arrived before changing hats"
    # Uncle Scrooge 14
    Titles.LUNCHEON_LAMENT: (Issues.US, 14, 1956, 1),        # "Scrooge suffers stomach pains from Grandma Duck’s"
    Titles.FAULTY_FORTUNE: (Issues.US, 14, 1956, 4),         # "Scrooge gets a deed to an inch of Texas land in a"
    # Uncle Scrooge 17
    Titles.FISHING_MYSTERY: (Issues.US, 17, 1956, 3),        # "Gyro arouses the interest of fishermen"
    Titles.EYES_HAVE_IT_THE: (Issues.US, 17, 1956, 4),       # 'Scrooge sees a “quarter”'
    # Uncle Scrooge 21
    Titles.DOGGED_DETERMINATION: (Issues.US, 21, 1958, 4),   # "buys a dog to outmatch a watchdog"
    Titles.FORGOTTEN_PRECAUTION: (Issues.US, 21, 1958, 5),   # "forgets ... a self-locking door"
    Titles.GETTING_THOR: (Issues.US, 21, 1958, 1),           # remaining slot
    # Uncle Scrooge 22
    Titles.GOING_TO_PIECES: (Issues.US, 22, 1958, 1),        # "buy parts for his old car"
    Titles.HIGH_RIDER: (Issues.US, 22, 1958, 4),             # "bumpy ride on a horse"
    # Uncle Scrooge 42
    Titles.DUELING_TYCOONS: (Issues.US, 42, 1963, 0),        # "challenged to a duel by a rival millionaire"
    Titles.WISHFUL_EXCESS: (Issues.US, 42, 1963, 2),         # "genie ... Scrooge's demands are extravagant"
    # Uncle Scrooge 57
    Titles.BIGGER_THE_BEGGAR_THE: (Issues.US, 57, 1965, 1),  # "furious at a panhandling ... plea"
    Titles.SNAKE_TAKE: (Issues.US, 57, 1965, 4),             # remaining slot
    # Uncle Scrooge 25
    Titles.IMMOVABLE_MISER: (Issues.US, 25, 1959, 1),        # "won't budge from a park bench"
    Titles.KITTY_GO_ROUND: (Issues.US, 25, 1959, 7),         # "basket of kittens returns to Scrooge"
    # Uncle Scrooge 22 — keyword matcher had swapped these two
    Titles.THAT_SINKING_FEELING: (Issues.US, 22, 1958, 5),   # "going down with his ship"
    Titles.KNOW_IT_ALL_MACHINE_THE: (Issues.US, 22, 1958, 3),  # "machine that can read thoughts"
    # Donald Duck 45
    Titles.POWER_PLOWING: (Issues.DD, 45, 1956, 3),          # "aggressive snowplow driver"
    Titles.REMEMBER_THIS: (Issues.DD, 45, 1956, 2),          # remaining slot
    # WDCS 215
    Titles.MOCKING_BIRD_RIDGE: (Issues.CS, 215, 8, 58),

    # --- no counterpart in Barrier's 1978 bibliography (validation findings) - #
    Titles.SILENT_NIGHT: None,        # famous unpublished story; not listed in WDCS 64
    Titles.MILKMAN_THE: None,         # unpublished story; not listed in WDCS 215
    # (LIGHTS_OUT and ALL_CHOKED_UP were recorded here as absent until the US 23
    # entries were restored to source.xhtml from Appendix A's dates, 2026-06-12.)
    Titles.BIRD_CAMERA_THE: None,     # FC 1047 lists 5 Gyro stories; Bird Camera absent
    Titles.UP_AND_AT_IT: None,        # US 47 note: gag left unplaced by Barks
    Titles.IT_HAPPENED_ONE_WINTER: None,  # US 61 lists 4 Barks items; this is not among them
}

# Bibliography entries with *no* library counterpart, excluded by hand with a
# reason (the EXCLUDED_ENTRY disposition). Keyed by the same positional locator
# as OVERRIDES: (issue_name, issue_number, issue_year, entry_index). Because the
# index is positional, each exclusion carries a guard snippet that must appear in
# the entry's text — if a source edit shifts the indices, the disposition pass
# reports the mismatch instead of silently excluding the wrong entry.
ENTRY_EXCLUSIONS: dict[tuple[Issues, int, int, int], tuple[str, str]] = {
    (Issues.US, 25, 1959, 6): (
        "binoculars to read a newspaper",
        "One-page gag marked '(Not listed.)' — absent from Barks's own records; "
        "uncertain attribution, not in the curated library.",
    ),
    (Issues.US, 32, 1961, 4): (
        "beautifies",  # "Scrooge 'beautifies' his money bags with bows"
        "'The Homey Touch' gag marked '(Not listed.)' — absent from Barks's own "
        "records; uncertain attribution, not in the curated library.",
    ),
    (Issues.US, 32, 1961, 6): (
        "pursued by a hoodlum",
        "'Turnabout' gag marked '(Not listed.)' — absent from Barks's own "
        "records; uncertain attribution, not in the curated library.",
    ),
    (Issues.US, 61, 1966, 5): (
        "fur coat to a ragged man",
        "Inside-back-cover gag with uncertain attribution: Barks's list shows the "
        "Aug. 19, 1963 art submission as intended for US 47; Barrier only "
        "tentatively places it here.",
    ),
    (Issues.DD, 71, 1960, 1): (
        "first to the end of the rainbow",
        "'Rainbow's End' gag marked '(Not listed.)' — absent from Barks's own "
        "records; uncertain attribution, not in the curated library.",
    ),
}

# Cover descriptions say '(Illustrating "X.")'; X is resolved against the curated
# title strings. The titles below have no Titles member — Barks drew the cover for
# another artist's interior story — so they intentionally resolve to None.
ILLUSTRATES_OVERRIDES: dict[str, Titles | None] = {
    "The Crocodile Collector": None,        # FC 348 interior story not by Barks
    "From Rags to Riches": None,            # FC 356 interior story not by Barks
    "Malayalaya": None,                     # FC 394 interior story not by Barks
    "The Flying Horse": None,               # DD 27 interior story not by Barks
    "Robert the Robot": None,               # DD 28 interior story not by Barks
    "The Incredible Golden Iceberg": None,  # DD 101 interior story not by Barks
    "Treasure of Aztec-Land,": None,        # DD 103 interior story not by Barks
    "The Great Rainbow Race": None,         # DD 105 interior story not by Barks
    "Ambush at Thunder Mountain": None,     # DD 106 interior story not by Barks
    "The Giant of Duckburg": None,          # DD 111 interior story not by Barks
    "Timber Tycoon": None,                  # CS 295 interior story not by Barks
}
