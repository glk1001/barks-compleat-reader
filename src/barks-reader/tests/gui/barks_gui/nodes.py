"""Tree nodes and stories the GUI tests boot onto, in the app's own terms.

A node is leaf-to-root, as ``AAA_Settings.last_selected_node`` stores it; titles
go in by enum name. A cue map is keyed by DISPLAY title, which is what
``barks-reader.json`` keys on. To find a new chain, navigate there by hand once
and read back what the app saved in a test's scratch ``barks-reader.json``.
"""

from __future__ import annotations

Cue = dict[str, int | str] | None

# --- group nodes ---------------------------------------------------------------
THE_STORIES = ["The Stories", "root"]
SERIES = ["Series", "The Stories", "root"]
CHRONO_RANGE = ["1947-1950", "Chronological", "The Stories", "root"]
SPEECH_INDEX = ["Speech Bubble Index", "Indexes", "root"]
MAIN_INDEX = ["Main Index", "Indexes", "root"]
NAMES_INDEX = ["Names", "Speech Bubble Index", "Indexes", "root"]
LOCATIONS_INDEX = ["Locations", "Speech Bubble Index", "Indexes", "root"]
STATISTICS = ["Statistics", "Appendix", "root"]
READING = ["Reading", "root"]
HISTORY = ["History", "Reading", "root"]
TITLE_SEARCH = ["Titles", "Search", "root"]
TAG_SEARCH = ["Tags", "Search", "root"]
WORD_SEARCH = ["Words", "Search", "root"]
INTRODUCTION = ["Introduction", "root"]
ONE_PAGERS = ["One Pagers", "Series", "The Stories", "root"]
APPENDIX = ["Appendix", "root"]
# Full-screen leaves (documents, By the Numbers, the wiki) are not boot nodes: a
# restore opens them straight away, so a test selects them from their parent.
INTRO_DOCUMENT = "The Compleat Barks Disney Reader"
CENSORSHIP_DOCUMENT = "Censorship Fixes and Other Changes"
BY_THE_NUMBERS = "By the Numbers"
WIKI_NODE = "Carl Barks Wiki"
INDEXES = ["Indexes", "root"]
# An article under Introduction. Not a boot node: restoring a saved article node
# opens its reader straight away, so a test reaches it from INTRODUCTION instead.
FANTA_INTRO_ARTICLE = "Don Ault: Fantagraphics Introduction"

# --- stories -------------------------------------------------------------------
# A plain story with a wiki page and no overrides: the seventh title in the
# 1947-1950 chronological range, which is where the browse beat lands.
GHOST_OF_THE_GROTTO = ["GHOST_OF_THE_GROTTO_THE", *CHRONO_RANGE]
GHOST_OF_THE_GROTTO_TITLE = "The Ghost of the Grotto"

# Reached through the series tree; has an overrides row ("dere"/"theah").
LOST_IN_THE_ANDES = ["LOST_IN_THE_ANDES", "Donald Duck Adventures", *SERIES]
LOST_IN_THE_ANDES_TITLE = "Lost in the Andes!"
# A body-page cue for it, so the title view shows a ticked goto-page row and the
# reader opens there. page_index is what the reader logs as "Showed page N".
LOST_IN_THE_ANDES_PAGE = 34
LOST_IN_THE_ANDES_CUE: Cue = {
    "page_index": LOST_IN_THE_ANDES_PAGE,
    "display_page_num": "29",
    "page_type": "BODY",
    "last_body_page": "32",
}

# A censored-but-fixed story with an overrides row (the GLK alternate ending).
THE_FIREBUG = [
    "FIREBUG_THE",
    "censored but fixed stories",
    "Themes",
    "Categories",
    "The Stories",
    "root",
]
THE_FIREBUG_TITLE = "The Firebug"

# Pin every story above to "no cue": opens at the front page, no goto-page row.
NO_CUES: dict[str, Cue] = {
    GHOST_OF_THE_GROTTO_TITLE: None,
    LOST_IN_THE_ANDES_TITLE: None,
    THE_FIREBUG_TITLE: None,
}
