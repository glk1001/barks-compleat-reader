"""One-shot: reorder the ONE_PAGERS list literal into submitted-date order.

`ONE_PAGERS` is the "All One-Pagers" collection's page order: `get_located_one_pagers`
filters it and `get_one_pager_collection_pages` numbers the pre-baked pages
`ONE_PAGER_COLLECTION_PAGE_BASE + i` from those positions. It is hand-maintained and
separate from `BARKS_TITLE_INFO`, so `check_story_submitted_order` never validated it
and it drifted out of date order.

The reference order is the one-pager subsequence of `BARKS_TITLE_INFO`, which *is*
chronological and *is* gated. This rewrites ONLY the `ONE_PAGERS = [ ... ]` list body
in comic_book_info.py to that order, leaving every other line byte-for-byte identical.

AFTER RUNNING THIS the collection's page numbering changes, so the staged pages are
stale: re-run `barks-stage-one-pagers` (in ../barks-comic-building) and re-write the
overrides, or the collection will show the wrong scan on every moved page.

Run once with:  uv run python experiments/one_pagers/reorder_one_pagers.py
"""

from __future__ import annotations

import re
from pathlib import Path

from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, ONE_PAGERS

HERE = Path(__file__).resolve().parent
PKG_DIR = HERE.parents[1] / "src" / "barks-fantagraphics" / "src" / "barks_fantagraphics"
INFO_FILE = PKG_DIR / "comic_book_info.py"

HEAD_MARKER = "ONE_PAGERS = [\n"
LIST_CLOSE = "\n]\n"
ENTRY_RE = re.compile(r"^    Titles\.[A-Z0-9_]+,\n", re.MULTILINE)


def main() -> None:
    text = INFO_FILE.read_text(encoding="utf-8")

    start = text.index(HEAD_MARKER) + len(HEAD_MARKER)
    end = text.index(LIST_CLOSE, start) + 1  # keep the leading "\n"; end at the "]" line

    body = text[start:end]
    blocks = ENTRY_RE.findall(body)
    assert len(blocks) == len(ONE_PAGERS), f"{len(blocks)} entries != {len(ONE_PAGERS)}"
    assert "".join(blocks) == body, "entry split is lossy - body has content between entries"

    one_pagers = set(ONE_PAGERS)
    reference = [info.title for info in BARKS_TITLE_INFO if info.title in one_pagers]
    assert set(reference) == one_pagers, "reference order lost or gained a one-pager"

    # blocks[i] is the source line for ONE_PAGERS[i]; reindex into reference order.
    position = {title: i for i, title in enumerate(ONE_PAGERS)}
    sorted_blocks = [blocks[position[title]] for title in reference]
    assert sorted(sorted_blocks) == sorted(blocks), "sort changed the entry set"

    new_text = text[:start] + "".join(sorted_blocks) + text[end:]
    INFO_FILE.write_text(new_text, encoding="utf-8")
    moved = sum(1 for a, b in zip(ONE_PAGERS, reference, strict=True) if a != b)
    print(
        f"Reordered {len(sorted_blocks)} ONE_PAGERS entries into submitted-date order"
        f" ({moved} changed position). Re-run barks-stage-one-pagers."
    )


if __name__ == "__main__":
    main()
