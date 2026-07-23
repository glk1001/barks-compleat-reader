"""One-shot: reorder the BARKS_COVERS list literal into submitted-date order.

Rewrites ONLY the `BARKS_COVERS: list[BarksCover] = [ ... ]` list body in
barks_covers.py, leaving BARKS_COVER_BY_KEY, COVER_LOCATIONS, the accessors, and
every other line byte-for-byte identical. Entries are stable-sorted by
`cover_submitted_sort_key` (dated covers chronologically, the fully-undated ones
last), so the covers become the single canonical submitted-date order that the
Titles enum, BARKS_TITLE_INFO, BARKS_PAYMENTS, the reader tree, and the "All
Covers" collection all derive from.

After running this, run experiments/covers/emit_cover_titles.py to regenerate the
derived Titles/ComicBookInfo/PaymentInfo blocks in the same new order.

Run once with:  uv run python experiments/covers/reorder_barks_covers.py
"""

from __future__ import annotations

import re
from pathlib import Path

from barks_fantagraphics.barks_covers import BARKS_COVERS

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parents[1] / "src" / "barks-fantagraphics" / "src" / "barks_fantagraphics"
COVERS_FILE = PKG_DIR / "barks_covers.py"

HEAD_MARKER = "BARKS_COVERS: list[BarksCover] = [\n"
# The list body ends at the first column-0 "]" line (the entries are 4-indented).
LIST_CLOSE = "\n]\n"
ENTRY_RE = re.compile(r"    BarksCover\(.*?\n    \),\n", re.DOTALL)
DAY_RE = re.compile(r"submitted_day=(-?\d+)")
MONTH_RE = re.compile(r"submitted_month=(-?\d+)")
YEAR_RE = re.compile(r"submitted_year=(-?\d+)")


def _block_key(block: str) -> tuple[int, int, int]:
    year = int(YEAR_RE.search(block).group(1))  # ty: ignore[possibly-unbound-attribute]
    month = int(MONTH_RE.search(block).group(1))  # ty: ignore[possibly-unbound-attribute]
    day = int(DAY_RE.search(block).group(1))  # ty: ignore[possibly-unbound-attribute]
    return (
        year if year != -1 else 9999,
        month if month != -1 else 99,
        day if day != -1 else 99,
    )


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

    sorted_blocks = sorted(blocks, key=_block_key)
    assert set(sorted_blocks) == set(blocks), "sort changed the entry set"
    assert len(sorted_blocks) == len(blocks)

    new_text = text[:start] + "".join(sorted_blocks) + text[end:]
    COVERS_FILE.write_text(new_text, encoding="utf-8")
    print(f"Reordered {len(sorted_blocks)} BarksCover entries into submitted-date order.")


if __name__ == "__main__":
    main()
