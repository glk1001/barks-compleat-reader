"""Manual override table for ambiguous / unresolvable bibliography matches.

Two kinds of overrides:

* ``Titles.X: (Issues.US, 25, 1959, 1)`` — pin a title to a specific bibliography
  entry: (issue_name, issue_number, issue_year, entry_index_within_issue). The
  ``entry_index`` is the 0-based position printed by the reconciliation report.

* ``Titles.X: None`` — the title has *no* counterpart in Barrier's 1978
  bibliography (a one-page gag Barrier left unplaced, an unpublished story, or a
  story comic_book_info assigns to an issue where Barrier does not list it). These
  are real validation findings, recorded here so the matcher stops flagging them.

Everything else matches automatically; add entries here only for cases the
auto-matcher cannot resolve confidently.
"""

from __future__ import annotations

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_issues import Issues

OVERRIDES: dict[Titles, tuple[Issues, int, int, int] | None] = {
    # Ambiguous title-less gags pinned by description.
    Titles.IMMOVABLE_MISER: (Issues.US, 25, 1959, 1),   # "won't budge from a park bench"
    Titles.KITTY_GO_ROUND: (Issues.US, 25, 1959, 7),    # "basket of kittens returns to Scrooge"
    # Keyword matcher swapped these two US 22 gags; pin by description + date.
    Titles.THAT_SINKING_FEELING: (Issues.US, 22, 1958, 5),       # "going down with his ship"
    Titles.KNOW_IT_ALL_MACHINE_THE: (Issues.US, 22, 1958, 3),    # "machine that can read thoughts"
    # No counterpart in Barrier's 1978 bibliography (validation findings):
    Titles.SILENT_NIGHT: None,        # famous unpublished story; not listed in WDCS 64
    Titles.MOCKING_BIRD_RIDGE: None,  # WDCS 215 lists only one Donald story (The Milkman)
    Titles.LIGHTS_OUT: None,          # US 23 lists 4 Barks items; this is not among them
    Titles.ALL_CHOKED_UP: None,       # US 23 — as above
    Titles.BIRD_CAMERA_THE: None,     # FC 1047 lists 5 Gyro stories; Bird Camera absent
    Titles.UP_AND_AT_IT: None,        # US 47 note: gag left unplaced by Barks ("no bargain"/"up and at it")
}
