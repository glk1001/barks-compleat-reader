# Handover: story indexes in the wiki bundle are not in chronological order

For the `barks-wiki` maintainers. Written from `barks-compleat-reader`, which only
reads the bundle — nothing here has been changed in `barks-wiki`.

## What was seen

In the reader's wiki screen, the left-hand list of story titles is out of order.
*The Golden Christmas Tree* is listed **after** *Lost in the Andes!*, though it was
submitted four months earlier.

## Where the order actually comes from

Not from the reader. `okf_reader.core.render.list_children` lays each directory out
in its `index.md` **link order** — what its own docstring calls "curated order" —
falling back to filename order for anything the index does not list. The sidebar is
therefore a faithful rendering of the bundle, and the reader needs no change.

The order lives in:

```
okf/concept/stories/*/index.md
```

`concept/stories/donald-duck-adventures/index.md` links, in this order:

```
the-old-castles-secret.md
lost-in-the-andes.md
race-to-the-south-seas.md
the-golden-christmas-tree.md
voodoo-hoodoo.md
```

Against Barks chronology (submission dates from `barks_fantagraphics`):

| listed | correct | submitted | title |
|-------:|--------:|-----------|-------|
| 1 | 1 | 1947-12-03 | The Old Castle's Secret (#87) |
| 2 | 3 | 1948-10-21 | Lost in the Andes! (#112) |
| 3 | 4 | 1948-12-15 | Race to the South Seas! (#117) |
| 4 | 2 | 1948-06-30 | The Golden Christmas Tree (#103) |
| 5 | 5 | 1949-03-03 | Voodoo Hoodoo (#120) |

## How widespread

Counting adjacent pairs where the earlier-listed story is chronologically the later
one:

| index | story links | out-of-order pairs |
|-------|------------:|-------------------:|
| comics-and-stories | 235 | 106 |
| one-pagers | 140 | 72 |
| gyro-gearloose-stories | 48 | 25 |
| uncle-scrooge-adventures | 60 | 24 |
| misc | 46 | 20 |
| donald-duck-adventures | 39 | 12 |
| uncle-scrooge-short-stories | 30 | 8 |
| donald-duck-short-stories | 14 | 2 |
| covers, non-disney | 0 | 0 |
| **total** | **612** | **269** |

Eleven link targets are not recognised as Barks titles and are skipped: four in
`misc`, four in `covers`, three in `non-disney`. They may be legitimately
non-story pages — worth a glance, but they are not what this report is about.

## It is not some other sort order

Checked on `donald-duck-adventures`, over the 38 of its 39 links that carry
Fantagraphics metadata (the only subset with dates to compare): 12 inversions by
submission date, 12 by issue date, 12 by chronological number. The lists are not
sorted by any of them — the likeliest explanation is that they have been appended
to over time.

## Suggested place to fix

`barks-wiki/scripts/regenerate_indexes.py` looks like the generator for these files,
so the ordering probably wants fixing there rather than in 8 hand-edited indexes.
That has not been examined in any detail — it was found by name, not read.

## Who checks what

`barks-wiki` gates its own ordering — that is where the data and the generator
live, and where a failure is actionable.

This repo keeps the same check in `scripts/full-lint.sh` as a **non-gating**
warning, for the same reason `uv audit` is non-gating there: its subject sits
outside this checkout, so a commit in another repo could otherwise redden a tree
that has not changed. It names itself in the summary and the lint still passes.
It also passes, saying so, when the bundle is not present at all — which is most
checkouts and all of CI, since no workflow here checks out `barks-wiki`.

## Re-running the check

Committed here as a diagnostic (it never writes to the bundle):

```
scripts/check_wiki_story_order.py                 # the sibling bundle
scripts/check_wiki_story_order.py --bundle DIR
scripts/check_wiki_story_order.py --show-order    # print each index's corrected link order
```

`--show-order` prints the full corrected list of `*.md` links per index, which is the
form the fix needs. Exit status is 1 while anything is out of order, so it can verify
the fix afterwards.

## Two notes on method

Chronological rank comes from the `Titles` enum, which is declared in chronological
order (`chronological_number` is `value + 1`, monotonic wherever both exist). That
matters because it spans the whole Barks corpus — `ALL_FANTA_COMIC_BOOK_INFO` covers
only the titles in the Fantagraphics volumes, about a quarter of what the bundle
links to, and an earlier pass using it found only 98 of these 269 pairs.

Slugs drop apostrophes rather than turning them into separators, because the bundle
writes *That's No Fable!* as `thats-no-fable`. Treating them as separators silently
skips those pages.
