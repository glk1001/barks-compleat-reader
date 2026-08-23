"""One-shot: reorder the BARKS_COVERS list literal into submitted-date order.

Rewrites ONLY the `BARKS_COVERS: list[BarksCover] = [ ... ]` list body in
barks_covers.py, leaving BARKS_COVER_BY_KEY, COVER_LOCATIONS, the accessors, and
every other line byte-for-byte identical. Entries are sorted by
`cover_submitted_sort_key` (dated covers chronologically, the fully-undated ones
last), so the covers become the single canonical submitted-date order that the
Titles enum, BARKS_TITLE_INFO, BARKS_PAYMENTS, the reader tree, and the "All
Covers" collection all derive from.

Covers sharing a submitted date are broken by their current `Titles` position, so
re-running this reproduces the existing hand-authored order within a date rather
than reshuffling it. Without that tie-break the sort is merely *stable*, which
means a cover whose date was just edited keeps its stale list position relative to
its new date-mates - the exact drift this script exists to repair. A cover with no
`Titles` member yet (added to BARKS_COVERS but not yet emitted) sorts last within
its date.

After running this, run experiments/covers/emit_cover_titles.py to regenerate the
derived Titles/ComicBookInfo/PaymentInfo blocks in the same new order.

Run once with:  uv run python experiments/covers/reorder_barks_covers.py
"""

from __future__ import annotations

import re
from pathlib import Path

from barks_fantagraphics.barks_covers import (
    BARKS_COVERS,
    BarksCover,
    cover_submitted_sort_key,
    get_cover_title_str,
)
from barks_fantagraphics.barks_titles import Titles

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parents[1] / "src" / "barks-fantagraphics" / "src" / "barks_fantagraphics"
COVERS_FILE = PKG_DIR / "barks_covers.py"

HEAD_MARKER = "BARKS_COVERS: list[BarksCover] = [\n"
# The list body ends at the first column-0 "]" line (the entries are 4-indented).
LIST_CLOSE = "\n]\n"
ENTRY_RE = re.compile(r"    BarksCover\(.*?\n    \),\n", re.DOTALL)
# Sorts a not-yet-emitted cover last within its date (any value above len(Titles)).
NOT_IN_ENUM = 1 << 30


def _enum_name(title_str: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title_str).strip("_").upper()


def _cover_key(cover: BarksCover) -> tuple[int, int, int, int]:
    member = getattr(Titles, _enum_name(get_cover_title_str(cover)), None)
    position = NOT_IN_ENUM if member is None else int(member)
    return (*cover_submitted_sort_key(cover), position)


def main() -> None:
    text = COVERS_FILE.read_text(encoding="utf-8")

    start = text.index(HEAD_MARKER) + len(HEAD_MARKER)
    end = text.index(LIST_CLOSE, start) + 1  # keep the leading "\n"; end at the "]" line
    # The list literal must close before BARKS_COVER_BY_KEY (never inside COVER_LOCATIONS).
    assert end < text.index("BARKS_COVER_BY_KEY"), "list-close detection overran the literal"

    body = text[start:end]
    blocks = ENTRY_RE.findall(body)
    assert len(blocks) == len(BARKS_COVERS), f"{len(blocks)} entries != {len(BARKS_COVERS)}"
    assert "".join(blocks) == body, "entry split is lossy - body has content between entries"

    # blocks[i] is the source text of BARKS_COVERS[i], so sort the indices and
    # reindex - that keys off the parsed cover records rather than re-parsing.
    order = sorted(range(len(blocks)), key=lambda i: _cover_key(BARKS_COVERS[i]))
    sorted_blocks = [blocks[i] for i in order]
    assert sorted(sorted_blocks) == sorted(blocks), "sort changed the entry set"

    new_text = text[:start] + "".join(sorted_blocks) + text[end:]
    COVERS_FILE.write_text(new_text, encoding="utf-8")
    moved = sum(1 for position, i in enumerate(order) if position != i)
    print(
        f"Reordered {len(sorted_blocks)} BarksCover entries into submitted-date order"
        f" ({moved} changed position)."
    )


if __name__ == "__main__":
    main()
