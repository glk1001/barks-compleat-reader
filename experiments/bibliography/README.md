# Barks bibliography → `barks_bibliography.py`

One-off tooling that converts Michael Barrier's *A Carl Barks Comic-Book
Bibliography* into the committed data module
`src/barks-fantagraphics/src/barks_fantagraphics/barks_bibliography.py`, and
reconciles it against `comic_book_info.BARKS_TITLE_INFO` (primarily to
**validate submission dates** and attach descriptions/notes to each title).

## Files

| File | Role |
|---|---|
| `source.xhtml` | The input — a copy of the EPUB bibliography chapter. **Edit this** to fix the source. |
| `parse_bibliography.py` | Parser + matcher + reconciliation report + module emitter. |
| `overrides.py` | Manual table for ambiguous / absent matches (see caveat below). |
| *(generated)* `…/barks_fantagraphics/barks_bibliography.py` | The committed output. **Never hand-edit.** |

`experiments/` is excluded from ruff/ty/cspell; the generated module is excluded
from cspell only (`ignorePaths` in `cspell.config.yaml`).

## Running

```bash
cd experiments/bibliography

# Report only (preview coverage + date discrepancies, no file changes):
uv run python parse_bibliography.py

# Report + regenerate the committed module (also runs `ruff format` on it):
uv run python parse_bibliography.py --emit
```

The report sections: **COVERAGE** (match counts), **ISSUE HEADERS NOT IN
&lt;h2&gt;** (headers the EPUB tagged `<strong>`/`<h3>`/`<p>` instead of `<h2>` —
worth fixing in source), **NOT IN BARRIER** / **NO BARRIER ENTRY** (titles with
no counterpart — expected), **UNMATCHED** (needs an override — should be 0),
**MATCHED BY KEYWORD / ORDER ALIGNMENT** (heuristic matches to spot-check), and
**DATE DISCREPANCIES** (`cbi=` is the reader's date, `bib=` is Barrier's).

Text fields (descriptions, notes, titles) preserve inline formatting tags
(`<em>`, `<i>`, `<strong>`, ...); structural tags are stripped. Dates are parsed
on a tag-stripped copy, so a wrapped date like `<em>(Mar. 14, 1957)</em>` still
works.

## Fixing an error in the source

1. Edit `source.xhtml` (this copy — not anything under `/tmp`).
2. Re-run without `--emit` and read the report to confirm the change took.
3. Re-run with `--emit` to rewrite the module.

What an edit does — and doesn't:

- It changes the **`bib=`** side of the report and the corresponding field in the
  generated module.
- It does **not** touch `comic_book_info.py` (the **`cbi=`** side). If Barrier is
  right and the reader's data is wrong, fix `comic_book_info.py` instead; if
  Barrier's book has the typo, fix `source.xhtml`.

Keep the formats the parser expects, or an entry can silently drop (the report's
COVERAGE / UNMATCHED sections are the safety net — a broken line shows up there):

- Submission date = a plain parenthetical at the end of the paragraph, e.g.
  `… <em>(Mar. 14, 1957)</em>`. Month abbreviated or full; `?` for an unknown day
  is fine; `(Date not available)` is recognised.
- Issue headers must end in `- <N> pages`.
- Story lines keep the `TITLE - <pages> - description` shape.

## Caveat: overrides use positional indices

`overrides.py` pins a few titles by their **position within an issue**, e.g.
`Titles.IMMOVABLE_MISER: (Issues.US, 25, 1959, 1)` — the `1` is the 0-based
entry index printed by the report. Pure text/date edits are safe. But if you
**add or remove an entry** inside an overridden issue, the indices shift and the
override points at the wrong entry — re-check it (the report flags a mismatch).
A `None` value means "this title has no Barrier counterpart" (a recorded
finding), not an error.

## How matching works (for reference)

Issue identity is keyed on `(issue_name, issue_number)` — Barrier's cover-date
*years* often differ from `comic_book_info` by a year, so the issue **number** is
the reliable join key, not the year. Within an issue, each `ComicBookInfo` record
is matched to one entry by, in order: full-title substring → description keyword →
sole-remaining-candidate → conservative exact-date alignment → manual override.
Front covers are never matched (they aren't reader titles).

The order pass is deliberately conservative: it pairs a record to an entry only
when they are each other's *unique same-date partner*. It never guesses across a
date tie or a date discrepancy — validating the dates means we can't lean on them
to break ambiguity. Same-issue gag clusters whose pun titles appear in neither the
text nor the date therefore land in `overrides.py`, pinned by reading the
description.
