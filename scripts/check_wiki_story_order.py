#!/usr/bin/env python3
"""Report story pages listed out of chronological order in the wiki bundle.

The reader's wiki sidebar is not sorted by the reader: `okf_reader.core.render`'s
``list_children`` lays each directory out in its ``index.md`` link order (what its
docstring calls "curated order") and falls back to filename order. So the sidebar
shows whatever the bundle says, and a story in the wrong place there is a fact
about the bundle, not about this app.

This script compares each story index's link order against Barks chronology and
prints the pairs that disagree. It is a diagnostic, not a gate: the bundle lives
in the sibling ``barks-wiki`` repo, which is read-only from here, so nothing is
rewritten - the output is meant to be handed over.

Chronology comes from the ``Titles`` enum, which is declared in chronological
order (``chronological_number`` is ``value + 1``, and monotonic across every title
carrying one). That covers the whole Barks corpus, where
``ALL_FANTA_COMIC_BOOK_INFO`` covers only the titles in the Fantagraphics volumes
- about a quarter of what the bundle links to.

Link targets are matched to titles by slug. Apostrophes are dropped rather than
turned into separators, because the bundle writes "That's No Fable!" as
``thats-no-fable``; treating them as separators silently loses those pages.

Usage:
    scripts/check_wiki_story_order.py                  # the sibling bundle
    scripts/check_wiki_story_order.py --bundle DIR
    scripts/check_wiki_story_order.py --show-order     # also print the fixed order
    scripts/check_wiki_story_order.py --quiet          # only the verdict, unless bad

Exits 1 when anything is out of order and 0 when every index is clean. A bundle
that is not there at all is also 0, said out loud rather than passed silently: the
sibling repo is not part of this checkout, so most machines and all of CI have
nothing to check.
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
from pathlib import Path
from typing import NamedTuple

from barks_fantagraphics import barks_titles as bt

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE = REPO_ROOT.parent / "barks-wiki" / "okf"
STORIES_GLOB = "concept/stories/*/index.md"
# Markdown links to a page in the same directory: "](some-slug.md)".
LINK_RE = re.compile(r"\]\(([a-z0-9-]+)\.md\)")
APOSTROPHES = re.compile(r"['\u2019]")
NON_SLUG = re.compile(r"[^a-z0-9]+")


def say(message: str = "") -> None:
    """Write one report line to stdout."""
    print(message)  # noqa: T201


class Entry(NamedTuple):
    """One story link, with the chronological rank it should sort by."""

    slug: str
    title: str
    rank: int


def slugify(title: str) -> str:
    """Return the bundle's filename form of `title`."""
    lowered = APOSTROPHES.sub("", title.lower().replace("&", "and"))
    return NON_SLUG.sub("-", lowered).strip("-")


def title_ranks() -> dict[str, Entry]:
    """Return every Barks title by slug, ranked chronologically."""
    ranks: dict[str, Entry] = {}
    for title in bt.Titles:
        name = bt.ENUM_TO_STR_TITLE[title.value]
        ranks[slugify(name)] = Entry(slugify(name), name, title.value)
    return ranks


def linked_entries(index: Path, ranks: dict[str, Entry]) -> tuple[list[Entry], list[str]]:
    """Return the index's story links in listed order, plus the slugs not recognised."""
    found: list[Entry] = []
    unknown: list[str] = []
    for slug in LINK_RE.findall(index.read_text(encoding="utf-8")):
        entry = ranks.get(slug)
        if entry is None:
            unknown.append(slug)
        else:
            found.append(entry)
    return found, unknown


def inversions(entries: list[Entry]) -> list[tuple[Entry, Entry]]:
    """Return adjacent pairs where the earlier-listed story is the later one."""
    return [(a, b) for a, b in itertools.pairwise(entries) if b.rank < a.rank]


def report(bundle: Path, *, show_order: bool = False, quiet: bool = False) -> int:
    """Print a report for every story index under `bundle`. Returns an exit code."""
    if not bundle.is_dir():
        say(f"no wiki bundle at {bundle} - nothing to check")
        return 0
    indexes = sorted(bundle.glob(STORIES_GLOB))
    if not indexes:
        say(f"no story indexes under {bundle}")
        return 2

    ranks = title_ranks()
    total_bad = 0
    for index in indexes:
        entries, unknown = linked_entries(index, ranks)
        bad = inversions(entries)
        total_bad += len(bad)
        if quiet and not bad:
            continue
        name = index.parent.name
        note = f", {len(unknown)} unrecognised" if unknown else ""
        say(f"\n{name}  ({len(entries)} story links{note})")
        if not bad:
            say("  in chronological order")
            continue
        for earlier, later in bad:
            say(f"  #{earlier.rank + 1:<4} {earlier.title}")
            say(f"  #{later.rank + 1:<4} {later.title}   <- listed after, belongs before")
        if show_order:
            say("  corrected order:")
            for entry in sorted(entries, key=lambda e: e.rank):
                say(f"    {entry.slug}.md")

    say(f"\n{total_bad} out-of-order pairs across {len(indexes)} story indexes")
    return 1 if total_bad else 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the report."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE, help="the okf bundle root")
    parser.add_argument(
        "--show-order", action="store_true", help="also print each index's corrected link order"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print only the verdict, unless something is wrong"
    )
    args = parser.parse_args(argv)
    return report(args.bundle, show_order=args.show_order, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
