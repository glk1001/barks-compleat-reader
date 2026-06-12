"""Cross-check Appendix A (chronological listing) against the bibliography.

Barrier's *Carl Barks and the Art of the Comic Book* ends with Appendix A,
"A Chronological Listing of Barks's Comics Work" — the same data as the
bibliography, but organized by submission date. ``appendix-a.md`` is an
editable OCR copy of book pages 207-215 (fix OCR errors there, like
``source.xhtml``). This script parses it and verifies, in both directions,
that the appendix's (submission date, issue) pairs agree with the generated
``barks_bibliography`` module:

* forward: every dated appendix item points at a bibliography issue that has
  at least one entry submitted on that date;
* reverse: every dated bibliography entry is covered by an appendix item for
  its issue and date.

Run:  uv run python chrono_check.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from barks_fantagraphics.barks_bibliography import BIBLIOGRAPHY, BibEntry, BibIssue
from barks_fantagraphics.comic_issues import Issues

APPENDIX = Path(__file__).parent / "appendix-a.md"

# Everything after this marker is undated prose (late covers + the no-date list).
END_MARKER = "Barks's drawings on the covers"

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

YEAR_RE = re.compile(r"^#+\s*(19\d\d)\s*$")
DATE_LINE_RE = re.compile(
    r"^([A-Z][a-z]{2,8})\.?\s*(\?|\d{1,2})?\s*[-–]\s*(.+)$"
)
UNCERTAIN_RE = re.compile(r"^Date uncertain\s*[-–:]\s*(.+)$")

# An issue reference: optional series words, optional "4C", "No." and a number,
# optionally followed by more numbers ("US No. 38, 39, 54, and WDC No. 262").
SERIES_REF_RE = re.compile(
    r"([A-Z][A-Za-z.,'’&\s]*?)?\s*\b(4C\s+)?No\.?\s+(\d+)((?:\s*(?:,|and|;)\s*\d+)*)"
)
YEAR_SERIES_RE = re.compile(r"\b(Firestone giveaway|March of Comics),\s*(19\d\d)")
PAREN_RE = re.compile(r"\([^)]*\)")

# Items that date submitted *ideas* or unpublished work - the bibliography
# only dates the finished, published item, so these refs are not checkable.
UNCHECKABLE_RE = re.compile(r"(?i)\bideas?\b|\bunpublished\b|\bunknown\b")
# "FC?" = a cover whose location Barrier himself questions - drop just that
# reference, not the whole item ("FC?, WDC No. 165, FC, WDC No. 166").
UNCERTAIN_COVER_RE = re.compile(r"FC\?,?\s*[A-Z]*\s*No\.\s*\d+,?\s*")

# Appendix abbreviation -> bibliography series key (h1 name up to " (").
SERIES_ALIASES = {
    "WDC": "WALT DISNEY’S COMICS AND STORIES",
    "DD": "DONALD DUCK",
    "US": "UNCLE SCROOGE",
    "JW": "HUEY, DEWEY AND LOUIE JUNIOR WOODCHUCKS",
    "OG": "OUR GANG COMICS",
    "GG": "GYRO GEARLOOSE",
    "NEW FUNNIES": "NEW FUNNIES",
    "CHRISTMAS PARADE": "CHRISTMAS PARADE",
    "VACATION PARADE": "VACATION PARADE",
    # Dell's Picnic Party continued Vacation Parade; the bibliography lists
    # Picnic Party 8 under VACATION PARADE.
    "PICNIC PARTY": "VACATION PARADE",
    "DONALD DUCK ALBUM": "DONALD DUCK ALBUM",
    "MICKEY MOUSE ALMANAC": "MICKEY MOUSE ALMANAC",
    "SUMMER FUN": "SUMMER FUN",
    "TOM AND JERRY WINTER CARNIVAL": "TOM AND JERRY WINTER CARNIVAL",
    "TOM AND JERRY SUMMER FUN": "TOM AND JERRY SUMMER FUN",
    "UNCLE SCROOGE GOES TO DISNEYLAND": "UNCLE SCROOGE GOES TO DISNEYLAND",
    "CHRISTMAS IN DISNEYLAND": "CHRISTMAS IN DISNEYLAND",
    "DISNEYLAND BIRTHDAY PARTY": "DISNEYLAND BIRTHDAY PARTY",
    "MERRY CHRISTMAS": "MERRY CHRISTMAS",
    "UNCLE DONALD AND HIS NEPHEWS FAMILY FUN": "UNCLE DONALD AND HIS NEPHEWS FAMILY FUN",
    "FIRESTONE GIVEAWAY": "FIRESTONE CHRISTMAS GIVEAWAYS",
    "MARCH OF COMICS": "BOYS’ AND GIRLS’ MARCH OF COMICS",
}

# Items naming a giveaway/book with no "No. <n>" reference, and items whose
# reference needs a documented correction.
SPECIAL_ITEMS: list[tuple[re.Pattern[str], list[tuple[str, int]]]] = [
    (re.compile(r"Cheerios premium"), [("CHEERIOS PREMIUMS", 1)]),
    (re.compile(r"Kite giveaway"), [("KITE GIVEAWAYS", 1954)]),
    # "Oct. 8 - Drawings for five FC ideas listed under Sept. 17." - the
    # finished covers; the bibliography dates these four Oct. 8, 1953.
    (re.compile(r"Drawings for five FC ideas"),
     [("DONALD DUCK", 35), ("UNCLE SCROOGE", 7),
      ("UNCLE SCROOGE", 8), ("UNCLE SCROOGE", 9)]),
    # The 1965 partial redraw of Mummy's Ring = Uncle Scrooge and Donald Duck 1.
    (re.compile(r"Redrawing three pages"), [("UNCLE SCROOGE AND DONALD DUCK", 1)]),
]

# (series, appendix number) -> bibliography number. Barrier's appendix cites
# the Dell Giant number 38; his bibliography heads the issue "1".
SPECIAL_NUMBERS = {
    ("UNCLE DONALD AND HIS NEPHEWS FAMILY FUN", 38):
        ("UNCLE DONALD AND HIS NEPHEWS FAMILY FUN", 1),
}

# Leading qualifiers that precede a series ref within an item and are not part
# of the series name ("FC, WDC No. 150", "Covers, DD 4C ...").
QUALIFIER_WORDS = {
    "FC", "FC?", "IFC", "IBC", "BC", "COVERS", "ONE-PAGE GAG",
    "GRANDMA DUCK", "HAPPY HOUND", "BENNY BURRO", "BARNEY BEAR AND BENNY BURRO",
}


@dataclass
class ChronoItem:
    """One semicolon-separated item on a dated appendix line."""

    raw: str
    refs: list[tuple[str, int]] = field(default_factory=list)  # (series_key, number/year)


@dataclass
class ChronoRec:
    """One dated line of the appendix."""

    year: int
    month: int  # -1 = date uncertain
    day: int  # -1 = unknown day
    raw: str
    items: list[ChronoItem] = field(default_factory=list)


def parse_appendix() -> tuple[list[ChronoRec], list[str]]:
    text = APPENDIX.read_text(encoding="utf-8")
    text = text[: text.index(END_MARKER)]
    records: list[ChronoRec] = []
    unparsed: list[str] = []
    year = -1
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if m := YEAR_RE.match(line):
            year = int(m.group(1))
            continue
        if m := UNCERTAIN_RE.match(line):
            records.append(ChronoRec(year, -1, -1, line, parse_items(m.group(1))))
            continue
        m = DATE_LINE_RE.match(line)
        if m and m.group(1).lower()[:3] in MONTHS:
            day_tok = m.group(2)
            day = -1 if day_tok in (None, "?") else int(day_tok)
            month = MONTHS[m.group(1).lower()[:3]]
            records.append(ChronoRec(year, month, day, line, parse_items(m.group(3))))
        elif records:
            # Wrapped continuation of the previous line (column/page break).
            rec = records[-1]
            rec.raw += " " + line
            rec.items = parse_items(rec.raw.split(" - ", 1)[1])
        else:
            unparsed.append(line)
    return records, unparsed


def parse_items(text: str) -> list[ChronoItem]:
    items = []
    for part in text.replace("*", "").split(";"):
        part = part.strip().rstrip(".")
        if not part:
            continue
        item = ChronoItem(part)
        items.append(item)
        for pattern, refs in SPECIAL_ITEMS:
            if pattern.search(part):
                item.refs.extend(refs)
                break
        if item.refs or UNCHECKABLE_RE.search(part):
            continue
        clean = PAREN_RE.sub("", part)
        clean = UNCERTAIN_COVER_RE.sub("", clean)
        # Quoted story titles are identification only - drop them.
        clean = re.sub(r"[“\"][^”\"]*[”\"],?", "", clean)
        for m in YEAR_SERIES_RE.finditer(clean):
            key = SERIES_ALIASES[m.group(1).upper()].replace("’", "'")
            item.refs.append((key, int(m.group(2))))
        for m in SERIES_REF_RE.finditer(clean):
            series_key = normalize_series(m.group(1) or "", bool(m.group(2)))
            if series_key is None:
                continue
            numbers = [int(m.group(3))]
            numbers += [int(n) for n in re.findall(r"\d+", m.group(4) or "")]
            item.refs.extend(
                SPECIAL_NUMBERS.get((series_key, n), (series_key, n)) for n in numbers
            )
    return items


def normalize_series(words: str, is_four_color: bool) -> str | None:
    """Resolve the words before 'No. <n>' to a bibliography series key."""
    if is_four_color:
        return "FC"  # all Four Color one-shots share one number sequence
    tokens = [t.strip(",. ") for t in words.split(",") if t.strip(",. ")]
    candidate = tokens[-1].strip().upper().replace("’", "'") if tokens else ""
    candidate = re.sub(r"\s+", " ", candidate)
    if candidate in QUALIFIER_WORDS or not candidate:
        return None
    # Longest alias first, so e.g. TOM AND JERRY SUMMER FUN beats SUMMER FUN.
    for alias in sorted(SERIES_ALIASES, key=len, reverse=True):
        alias_n = alias.replace("’", "'")
        if candidate == alias_n or candidate.endswith(" " + alias_n):
            return SERIES_ALIASES[alias].replace("’", "'")
    return candidate  # unknown series - reported by the lookup


def biblio_index() -> dict[tuple[str, int], list[tuple[BibIssue, BibEntry]]]:
    index: dict[tuple[str, int], list[tuple[BibIssue, BibEntry]]] = {}
    for series in BIBLIOGRAPHY:
        series_key = series.h1_name.split(" (")[0].replace("’", "'")
        for issue in series.issues:
            if issue.issue_name is Issues.FC:
                key = ("FC", issue.issue_number)
            elif issue.issue_number == -1:
                key = (series_key, issue.issue_year)  # unnumbered giveaways
            else:
                key = (series_key, issue.issue_number)
            for entry in issue.entries:
                index.setdefault(key, []).append((issue, entry))
    return index


_RAW_DATE_RE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})\??,\s*(\d{4})")
_RAW_MONTHS = dict(MONTHS)


def dates_match(rec: ChronoRec, entry: BibEntry) -> bool:
    if rec.month == -1 or entry.date_unavailable:
        return True  # nothing to compare
    if entry.submitted_year == rec.year and entry.submitted_month == rec.month:
        if rec.day == -1 or entry.submitted_day == -1 or entry.submitted_day == rec.day:
            return True
    # Multi-date entries keep only the last date in submitted_*; accept any
    # date in the raw text ("June 17, 1954, and July 8, 1954" - the Kite book).
    for m in _RAW_DATE_RE.finditer(entry.raw_date):
        month = _RAW_MONTHS.get(m.group(1).lower()[:3], -2)
        if (int(m.group(3)) == rec.year and month == rec.month
                and (rec.day == -1 or int(m.group(2)) == rec.day)):
            return True
    return False


def main() -> None:
    records, unparsed = parse_appendix()
    index = biblio_index()
    n_refs = sum(len(i.refs) for r in records for i in r.items)
    n_no_ref = sum(1 for r in records for i in r.items if not i.refs)
    print(f"APPENDIX: {len(records)} dated lines, {n_refs} issue refs, "
          f"{n_no_ref} items without an issue ref (unpublished/unknown gags)")
    for line in unparsed:
        print(f"  UNPARSED LINE: {line}")

    print("\nFORWARD CHECK (appendix -> bibliography):")
    bad = 0
    for rec in records:
        for item in rec.items:
            for key in item.refs:
                pairs = index.get(key)
                if pairs is None:
                    bad += 1
                    print(f"  NO SUCH ISSUE {key}: "
                          f"{rec.day}/{rec.month}/{rec.year} | {item.raw}")
                elif not any(dates_match(rec, e) for _, e in pairs):
                    bad += 1
                    have = sorted({
                        f"{e.submitted_day}/{e.submitted_month}/{e.submitted_year}"
                        for _, e in pairs if e.submitted_year != -1
                    })
                    print(f"  DATE NOT IN ISSUE {key}: appendix "
                          f"{rec.day}/{rec.month}/{rec.year} | biblio has "
                          f"{', '.join(have) or 'no dated entries'} | {item.raw}")
    print(f"  forward mismatches: {bad}")

    print("\nREVERSE CHECK (bibliography -> appendix):")
    # Every dated bibliography entry must be covered by an appendix record
    # whose refs include its issue and whose date matches.
    covered: dict[tuple[str, int], list[ChronoRec]] = {}
    for rec in records:
        for item in rec.items:
            for key in item.refs:
                covered.setdefault(key, []).append(rec)
    bad = 0
    for key, pairs in sorted(index.items(), key=str):
        for issue, entry in pairs:
            if entry.submitted_year == -1:
                continue
            recs = covered.get(key, [])
            if not any(dates_match(rec, entry) for rec in recs):
                bad += 1
                print(f"  NOT IN APPENDIX {key}: biblio "
                      f"{entry.submitted_day}/{entry.submitted_month}/"
                      f"{entry.submitted_year} | {entry.raw_title[:60]}")
    print(f"  reverse mismatches: {bad}")


if __name__ == "__main__":
    main()
