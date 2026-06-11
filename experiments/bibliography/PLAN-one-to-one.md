# Plan: one-to-one match between `comic_book_info` and the Barrier bibliography

> **Status (2026-06-11): implemented.** All four phases are done; the report
> shows `UNDISPOSED: 0` and the invariant is enforced by tests in
> `src/barks-fantagraphics/tests/test_barks_bibliography.py`.
> Outstanding (user input needed):
> 1. the 27 DATE DISCREPANCIES (per-case review: fix `comic_book_info.py` or
>    `source.xhtml`);
> 2. real payment amounts for the 14 script-only additions (placeholder
>    `payment=-1.0` rows in `barks_payments.py`, marked `TODO(glk)`);
> 3. Friendly Enemy / Undercover Girl / The Inventive Gentleman are printed in
>    FANTA_27 pp. 118-120 but left `_TODO` in `ONE_PAGER_LOCATIONS` — locating
>    them requires re-baking the pre-baked All One-Pagers archive first (see the
>    comment in `comic_book_info.py`). The other 18 additions are in no
>    published Fantagraphics volume, so no `SERIES_INFO`/location rows exist yet.

## Goal

Every Barrier bibliography entry (outside explicitly excluded sections/categories)
corresponds to exactly one library record, and vice versa:

- **story/gag entry ↔ `Titles` member** (via `ComicBookInfo`) — 653 already done.
- **cover entry ↔ new `BARKS_COVERS` record** — registry to be created (~265).
- Everything else carries an **explicit disposition** (excluded section, reprint,
  uncertain attribution, post-1978, no-Barrier-counterpart). Nothing implicit.

The reconciliation report's end state: `UNDISPOSED: 0` in both directions.

## Current gap (346 unclaimed bibliography entries)

| Category | Count | Decision |
|---|---|---|
| Covers | 265 | **Full cover registry** (new data table, one-to-one) |
| Non-duck series stories | 35 | Excluded sections: Our Gang, New Funnies, Porky Pig, Tom & Jerry |
| Reprints | ~20 | **Excluded as a category** (no linkage) |
| Duck stories absent from `Titles` | ~21 | **Add to the library** (art + script-only) |
| "(Not listed)" gags, uncertain attribution | ~5 | Entry-level exclusions with reason |

Plus, from the cbi side, already documented: 7 absent-with-reason + 8 post-1978.

## Phase 1 — Disposition mechanism (parser only, no library changes)

Add to `parse_bibliography.py`:

- `Disposition` enum: `MATCHED_TITLE`, `COVER`, `REPRINT`, `EXCLUDED_SECTION`,
  `EXCLUDED_ENTRY` (with reason string).
- `EXCLUDED_SERIES` table: `OUR GANG COMICS`, `NEW FUNNIES`, `PORKY PIG`,
  `TOM AND JERRY SUMMER FUN`, `TOM AND JERRY WINTER CARNIVAL` — everything in
  these sections (stories *and* covers) is out of scope.
- Reprint classifier: entry text contains "A reprint of" / "Reprinted from"
  (verify the ~20 by eye in the report before trusting the regex).
- `ENTRY_EXCLUSIONS` in `overrides.py`: the "(Not listed)" gags —
  US 25 binoculars, US 32 Homey Touch + Turnabout, US 61 fur-coat,
  DD 71 Rainbow's End — each with a reason.
- Report section **UNDISPOSED** replaces the EXTRAS count: lists every entry with
  no disposition. This is the work queue; drives Phases 2–3.

Deliverable: report shows exactly the ~21 add-candidates and ~265 covers as the
remaining undisposed entries.

## Phase 2 — Library additions (~21 new titles)

The risky phase: `Titles` is `@verify(CONTINUOUS, UNIQUE)` and **chronologically
ordered** (`chronological_number = title + 1`), so additions insert mid-sequence
and renumber every later member.

**2a. Audit first** (before any edit):
- Confirm nothing persists `Titles` as ints (reader settings/DB, saved reading
  state). Initial grep: titles round-trip as strings via `STR_TITLE_TO_ENUM` — verify.
- Sibling repos `../barks-ocr` and `../barks-comic-building`: grep for hardcoded
  title values / counts.
- Enumerate the parallel Titles-keyed tables that may need a row per new title:
  `barks_titles.py` (enum + `_TITLE_OVERRIDES` + `NUM_TITLES`),
  `comic_book_info.py`, `fanta_comics_info.py`, `barks_tags_data.py` /
  `barks_tags.py`, `barks_payments.py`, `barks_extra_info.py`.
  Determine which are total (assert every title) vs. partial — mirror how the
  existing script-only HDL 6–13 titles are handled in each.

**2b. The additions** (submission dates come straight from Barrier):
- *Barks art:* Daisy's Diary FC 1150 — `SMALL_FRYERS`, `FALSE_FLATTERY`,
  `FRIENDLY_ENEMY`, `UNDERCOVER_GIRL`, `INVENTIVE_GENTLEMAN_THE`;
  Gyro FC 1184 — `OLD_TIMER_THE`, `MECHANIZED_MESS`.
- *Script-only:* DD 117 `PAWNS_OF_THE_LOUP_GAROU`, DD 126 `OFFICER_OF_THE_DAY`,
  DD 138 `DAY_IN_A_DUCKS_LIFE_A`; HDL 13–25 — `GOLD_OF_THE_49ERS`,
  `DUCKMADE_DISASTER`, `WAILING_WHALERS`, `WHERE_THERES_SMOKE`,
  `BE_LEERY_OF_LAKE_EERIE`, `TEAHOUSE_OF_THE_WAGGIN_DRAGON`, `NEW_ZOO_BREWS_ADO`,
  `MUSIC_HATH_CHARMS`, `PHANTOM_JOKER_THE`, `HARK_HARK_THE_ARK`,
  `CAPTAINS_OUTRAGEOUS`.
- Insert each at its chronological position in the enum and in
  `BARKS_TITLE_INFO` (ordered by submission date); update `NUM_TITLES`.
- New `Issues` members are NOT needed (DD/HDL/FC all exist), but
  `comic_book_info` HDL issue numbers must align with Barrier's
  (e.g. Barrier HDL 13 has both Mountain Shook *and* Gold of the '49ers).
- Re-run the matcher: each new record should match by title text automatically.
- Full gates + reader smoke test (`uv run main.py`) — new titles appear and
  don't break tree views, search, payments validation, or tags.

## Phase 3 — Cover registry

**3a. Schema** — new `barks_covers.py` in `barks_fantagraphics`:

```python
@dataclass(frozen=True)
class BarksCover:
    issue_name: Issues | None   # None for non-Issues duck series (Albums etc.)
    series_name: str            # bibliography series, for the None cases
    issue_number: int
    issue_month: int
    issue_year: int
    kind: CoverKind             # FRONT / INSIDE_FRONT / INSIDE_BACK / BACK / PART
    seq: int                    # disambiguator within (issue, kind)
    qualifier: str | None       # "art only", "pencil rough only", ...
    description: str
    submitted_day/month/year: int
    illustrates: Titles | None  # resolved from "(Illustrating "...")"
```

Key = `(series_name, issue_number, issue_year, kind, seq)` — stable, no enum, no
renumbering problem.

**3b. Bootstrap** — the registry is *generated from the bibliography* (Barrier is
the source of truth), emitted once into `barks_covers.py`, then hand-maintained
like `comic_book_info.py`. The matcher thereafter verifies the bijection instead
of generating (so later source edits get flagged, not silently absorbed).

**3c. `illustrates` resolution** — parse `(Illustrating "X.")` from cover
descriptions; resolve X against `STR_TITLE_TO_ENUM` (+ a small override table for
mismatched titles). Report unresolved ones.

Covers in duck cover-only sections (Donald Duck Album, Duck Album, Daisy and
Donald, Grandma Duck's Farm Friends, Merry Christmas, Uncle Donald...) are
**included** in the registry — only the non-duck sections are excluded.

## Phase 4 — Enforcement + tests

- `BibEntry` gains `disposition` (emitted into `barks_bibliography.py`).
- Bijection tests in `src/barks-fantagraphics/tests/`:
  1. every non-excluded story entry has a unique `title`;
  2. every `BARKS_TITLE_INFO` record matches or is in the documented-absent set;
  3. every non-excluded cover entry ↔ unique `BarksCover`;
  4. **zero undisposed entries** — the invariant that keeps future source edits honest.
- Resolve the open 27 date discrepancies (user review: fix `comic_book_info`
  or `source.xhtml` per case) — count should trend to 0.

## Order & checkpoints

1. Phase 1 (parser-only, low risk) → report shows the exact final work queue.
2. Phase 2a audit → go/no-go on the renumbering approach before touching the enum.
3. Phase 2b additions in 2–3 batches (Barks-art first — smallest, lowest risk).
4. Phase 3 cover registry.
5. Phase 4 tests; flip EXTRAS→UNDISPOSED=0 as the permanent invariant.

Each step ends with: ruff, ty, lint-imports, cspell, full pytest, and a
re-run of the reconciliation report.
