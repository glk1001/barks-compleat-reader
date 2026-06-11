"""Manual override table for ambiguous / unresolvable bibliography matches.

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
    Titles.MACHINE_MIX_UP: (Issues.FC, 178, 1947, 3),        # "new modern kitchen, unhappy results"
    Titles.FASHION_IN_FLIGHT: (Issues.FC, 178, 1947, 2),     # remaining slot
    # Four Color 199
    Titles.GENUINE_ARTICLE_THE: (Issues.FC, 199, 1948, 4),   # "tests the authenticity of worm holes"
    Titles.BEST_LAID_PLANS: (Issues.FC, 199, 1948, 3),       # "pretends to be sick so the nephews cook"
    Titles.SORRY_TO_BE_SAFE: (Issues.FC, 199, 1948, 1),      # "vacant lot where the nephews can play"
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

    # --- no counterpart in Barrier's 1978 bibliography (validation findings) - #
    Titles.SILENT_NIGHT: None,        # famous unpublished story; not listed in WDCS 64
    Titles.MOCKING_BIRD_RIDGE: None,  # WDCS 215 lists only one Donald story (The Milkman)
    Titles.LIGHTS_OUT: None,          # US 23 lists 4 Barks items; this is not among them
    Titles.ALL_CHOKED_UP: None,       # US 23 — as above
    Titles.BIRD_CAMERA_THE: None,     # FC 1047 lists 5 Gyro stories; Bird Camera absent
    Titles.UP_AND_AT_IT: None,        # US 47 note: gag left unplaced by Barks
    Titles.IT_HAPPENED_ONE_WINTER: None,  # US 61 lists 4 Barks items; this is not among them
}
