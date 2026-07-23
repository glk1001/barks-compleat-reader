"""One-shot: (re)generate the cover Titles/ComicBookInfo/PaymentInfo blocks.

Every cover in BARKS_COVERS is a first-class title. This regenerates, in the
current BARKS_COVERS order (now submitted-date order), the four hand-maintained
blocks derived from it:

* ``barks_titles.py``  - 264 ``Titles`` enum members + the ``_TITLE_OVERRIDES``
  entries carrying the non-derivable "#<issue>" part, and the ``NUM_TITLES`` value
* ``comic_book_info.py`` - 264 ``ComicBookInfo`` rows (``is_barks_title=False``:
  cover titles are assigned, so they display parenthesised)
* ``barks_payments.py`` - 264 ``PaymentInfo`` placeholder rows (num_pages=1,
  accepted = submitted date, payment=-1.0: Barrier's bibliography has no cover
  payment amounts)

It is idempotent: each block is REPLACED in place (matched between its start
comment and the following anchor), so re-running after reordering BARKS_COVERS
just rewrites the blocks in the new order. The four blocks are emitted from one
`for c in BARKS_COVERS` pass, so enum members, overrides, ComicBookInfo rows and
PaymentInfo rows stay in exact lockstep (required by test_sorted_by_chronological_number).

Run with:  uv run python experiments/covers/emit_cover_titles.py
(then `uv run ruff format` the three files; the blocks are hand-maintained after).
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

ENUM_START = "    # Covers (assigned titles; see barks_covers.py).\n"
ENUM_ANCHOR = "    # Synthetic collection (not a real Barks story) - bundles every one-pager.\n"
NUM_TITLES_RE = re.compile(r"^NUM_TITLES = .*$", re.MULTILINE)
INFO_START = "    # Covers (assigned titles, from Barrier's bibliography - see barks_covers.py).\n"
INFO_ANCHOR = (
    '    # Synthetic "All One-Pagers" collection - bundles every one-pager into one comic.\n'
)
PAYMENTS_START = "    # Covers: placeholder rows - Barrier's bibliography has no cover payment\n"
PAYMENTS_END = "}\n# fmt: on"
# The _TITLE_OVERRIDES cover block has no trailing anchor (non-cover overrides
# follow immediately); delimit it by the contiguous run of `_COVER` keys. The
# value part is `.*` so an optional trailing `# noqa: E501` on long lines matches.
OVERRIDES_RE = re.compile(
    r"    # Covers - the '#<issue>' part cannot be derived from the enum name\.\n"
    r'(?:    "[A-Za-z0-9_]+_COVER":.*\n)+'
)
MAX_LINE_LEN = 100


def enum_name(title_str: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title_str).strip("_").upper()


def issues_member(cover: BarksCover) -> str:
    # Covers in series with no Issues member are filed under EXTRAS.
    return f"Issues.{cover.issue_name.name}" if cover.issue_name is not None else "Issues.EXTRAS"


def replace_between(text: str, start_marker: str, end_marker: str, new_block: str) -> str:
    """Replace ``text[start_of(start_marker):start_of(end_marker)]`` with new_block.

    new_block must itself begin with start_marker and end just before end_marker.
    """
    assert text.count(start_marker) == 1, f"start not unique: {start_marker!r}"
    s = text.index(start_marker)
    e = text.index(end_marker, s)
    assert new_block.startswith(start_marker), "new_block must start with the start marker"
    return text[:s] + new_block + text[e:]


def main() -> None:
    titles = [get_cover_title_str(c) for c in BARKS_COVERS]
    names = [enum_name(t) for t in titles]
    n = len(BARKS_COVERS)
    assert len(set(titles)) == n, "Duplicate cover title strings."
    assert len(set(names)) == n, "Duplicate cover enum names."

    # --- barks_titles.py: enum members + _TITLE_OVERRIDES + NUM_TITLES ---
    enum_block = ENUM_START + "".join(f"    {name} = auto()\n" for name in names)
    override_lines = []
    for name, title in zip(names, titles):
        line = f'    "{name}": "{title}",'
        # barks_titles.py has no file-level E501 noqa, so tag over-long lines.
        if len(line) > MAX_LINE_LEN:
            line += "  # noqa: E501"
        override_lines.append(line + "\n")
    overrides_block = (
        "    # Covers - the '#<issue>' part cannot be derived from the enum name.\n"
        + "".join(override_lines)
    )
    text = TITLES_FILE.read_text(encoding="utf-8")
    text = replace_between(text, ENUM_START, ENUM_ANCHOR, enum_block)
    assert len(OVERRIDES_RE.findall(text)) == 1, "_TITLE_OVERRIDES cover block not unique"
    assert OVERRIDES_RE.search(text).group(0).count('_COVER": ') == n  # ty: ignore[possibly-unbound-attribute]
    text = OVERRIDES_RE.sub(lambda _m: overrides_block, text, count=1)
    text = NUM_TITLES_RE.sub(
        f"NUM_TITLES = 684 + {n} + 4 + 2  # +{n} covers, +4 articles, +2 synthetic collections",
        text,
        count=1,
    )
    TITLES_FILE.write_text(text, encoding="utf-8")

    # --- comic_book_info.py: ComicBookInfo rows ---
    info_block = (
        INFO_START
        + "    # In submitted-date order; exempt from the main story check (COVERS_SET),\n"
        "    # validated by check_cover_submitted_order.\n"
        + "".join(
            f"    ComicBookInfo(Titles.{name}, False, {issues_member(c)}, {c.issue_number},"
            f" {c.issue_month}, {c.issue_year}, {c.submitted_day}, {c.submitted_month},"
            f" {c.submitted_year}),\n"
            for name, c in zip(names, BARKS_COVERS)
        )
    )
    text = INFO_FILE.read_text(encoding="utf-8")
    text = replace_between(text, INFO_START, INFO_ANCHOR, info_block)
    INFO_FILE.write_text(text, encoding="utf-8")

    # --- barks_payments.py: PaymentInfo rows ---
    payments_block = (
        PAYMENTS_START
        + "    # amounts. accepted = submitted date (-1s where unknown).\n"
        + "".join(
            f"    Titles.{name}: PaymentInfo(Titles.{name}, 1, {c.submitted_day},"
            f" {c.submitted_month}, {c.submitted_year}, -1.0),\n"
            for name, c in zip(names, BARKS_COVERS)
        )
    )
    text = PAYMENTS_FILE.read_text(encoding="utf-8")
    text = replace_between(text, PAYMENTS_START, PAYMENTS_END, payments_block)
    PAYMENTS_FILE.write_text(text, encoding="utf-8")

    print(f"Regenerated {n} cover titles (submitted-date order) into:")
    for path in (TITLES_FILE, INFO_FILE, PAYMENTS_FILE):
        print(f"  {path}")


if __name__ == "__main__":
    main()
