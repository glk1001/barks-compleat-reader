"""One-shot bootstrap: make every cover in BARKS_COVERS a first-class title.

Inserts generated blocks (in BARKS_COVERS/bibliography order) into the
hand-maintained barks_fantagraphics modules:

* ``barks_titles.py``  - 264 ``Titles`` enum members, the ``_TITLE_OVERRIDES``
  entries carrying the non-derivable "#<issue>" part, and the ``NUM_TITLES`` bump
* ``comic_book_info.py`` - 264 ``ComicBookInfo`` rows (``is_barks_title=False``:
  cover titles are assigned, so they display parenthesised)
* ``barks_payments.py`` - 264 ``PaymentInfo`` placeholder rows (num_pages=1,
  accepted = submitted date, payment=-1.0: Barrier's bibliography has no cover
  payment amounts)

Titles are synthesized by ``barks_covers.get_cover_title_str`` (e.g.
"Uncle Scrooge #7 Cover"); enum names derive from them ("UNCLE_SCROOGE_7_COVER").

Run once with:  uv run python experiments/covers/emit_cover_titles.py
(then the blocks are hand-maintained like the rest of those modules).
"""

from __future__ import annotations

import re
from pathlib import Path

from barks_fantagraphics.barks_covers import BARKS_COVERS, BarksCover, get_cover_title_str

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parents[1] / "src" / "barks-fantagraphics" / "src" / "barks_fantagraphics"

TITLES_FILE = PKG_DIR / "barks_titles.py"
INFO_FILE = PKG_DIR / "comic_book_info.py"
PAYMENTS_FILE = PKG_DIR / "barks_payments.py"

ENUM_ANCHOR = "    # Synthetic collection (not a real Barks story) - bundles every one-pager.\n"
OVERRIDES_ANCHOR = "_TITLE_OVERRIDES: dict[str, str] = {\n"
NUM_TITLES_RE = re.compile(r"^NUM_TITLES = .*$", re.MULTILINE)
INFO_ANCHOR = (
    '    # Synthetic "All One-Pagers" collection - bundles every one-pager into one comic.\n'
)
PAYMENTS_ANCHOR = (
    "    Titles.CAPTAINS_OUTRAGEOUS: PaymentInfo(Titles.CAPTAINS_OUTRAGEOUS, 15, 30, 3, 1973, -1.0),\n"
)


def enum_name(title_str: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title_str).strip("_").upper()


def issues_member(cover: BarksCover) -> str:
    # Covers in series with no Issues member are filed under EXTRAS (they are all
    # unlocated Whitman/Gladstone-era covers; the synthesized title carries the
    # series name).
    return f"Issues.{cover.issue_name.name}" if cover.issue_name is not None else "Issues.EXTRAS"


def insert_before(text: str, anchor: str, block: str) -> str:
    assert text.count(anchor) == 1, f"Anchor not unique: {anchor!r}"
    return text.replace(anchor, block + anchor)


def insert_after(text: str, anchor: str, block: str) -> str:
    assert text.count(anchor) == 1, f"Anchor not unique: {anchor!r}"
    return text.replace(anchor, anchor + block)


def main() -> None:
    titles = [get_cover_title_str(c) for c in BARKS_COVERS]
    names = [enum_name(t) for t in titles]
    assert len(set(titles)) == len(titles), "Duplicate cover title strings."
    assert len(set(names)) == len(names), "Duplicate cover enum names."

    # --- barks_titles.py ---
    enum_block = "    # Covers (assigned titles; see barks_covers.py).\n" + "".join(
        f"    {name} = auto()\n" for name in names
    )
    overrides_block = (
        "    # Covers - the '#<issue>' part cannot be derived from the enum name.\n"
        + "".join(f'    "{name}": "{title}",\n' for name, title in zip(names, titles))
    )
    text = TITLES_FILE.read_text(encoding="utf-8")
    text = insert_before(text, ENUM_ANCHOR, enum_block)
    text = insert_after(text, OVERRIDES_ANCHOR, overrides_block)
    text = NUM_TITLES_RE.sub(
        f"NUM_TITLES = 684 + {len(BARKS_COVERS)} + 4 + 2"
        f"  # +{len(BARKS_COVERS)} covers, +4 articles, +2 synthetic collections",
        text,
        count=1,
    )
    TITLES_FILE.write_text(text, encoding="utf-8")

    # --- comic_book_info.py ---
    info_block = (
        "    # Covers (assigned titles, from Barrier's bibliography - see barks_covers.py).\n"
        "    # Not in submitted-date order - exempt from check_story_submitted_order via COVERS.\n"
        + "".join(
            f"    ComicBookInfo(Titles.{name}, False, {issues_member(c)}, {c.issue_number},"
            f" {c.issue_month}, {c.issue_year}, {c.submitted_day}, {c.submitted_month},"
            f" {c.submitted_year}),\n"
            for name, c in zip(names, BARKS_COVERS)
        )
    )
    text = INFO_FILE.read_text(encoding="utf-8")
    text = insert_before(text, INFO_ANCHOR, info_block)
    INFO_FILE.write_text(text, encoding="utf-8")

    # --- barks_payments.py ---
    payments_block = (
        "    # Covers: placeholder rows - Barrier's bibliography has no cover payment\n"
        "    # amounts. accepted = submitted date (-1s where unknown).\n"
        + "".join(
            f"    Titles.{name}: PaymentInfo(Titles.{name}, 1, {c.submitted_day},"
            f" {c.submitted_month}, {c.submitted_year}, -1.0),\n"
            for name, c in zip(names, BARKS_COVERS)
        )
    )
    text = PAYMENTS_FILE.read_text(encoding="utf-8")
    text = insert_after(text, PAYMENTS_ANCHOR, payments_block)
    PAYMENTS_FILE.write_text(text, encoding="utf-8")

    print(f"Inserted {len(BARKS_COVERS)} cover titles into:")
    for path in (TITLES_FILE, INFO_FILE, PAYMENTS_FILE):
        print(f"  {path}")


if __name__ == "__main__":
    main()
