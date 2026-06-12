"""One-off parser/matcher for the Michael Barrier Carl Barks bibliography.

Reads ``source.xhtml`` (a copy of the EPUB chapter), parses it into a
series/issue/entry tree, matches every ``ComicBookInfo`` record in
``barks_fantagraphics.comic_book_info`` to exactly one bibliography entry, prints
a reconciliation report (coverage, ambiguous matches, submission-date
discrepancies, extras), and emits the committed data module
``barks_fantagraphics.barks_bibliography``.

Run:  uv run python experiments/bibliography/parse_bibliography.py
Add:  uv run python experiments/bibliography/parse_bibliography.py --emit
"""

from __future__ import annotations

import html
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, ComicBookInfo
from barks_fantagraphics.comic_issues import Issues

from overrides import ENTRY_EXCLUSIONS, ILLUSTRATES_OVERRIDES, OVERRIDES

HERE = Path(__file__).parent
SOURCE = HERE / "source.xhtml"
_PKG_DIR = HERE.parent.parent / "src" / "barks-fantagraphics" / "src" / "barks_fantagraphics"
OUT_MODULE = _PKG_DIR / "barks_bibliography.py"
OUT_COVERS_MODULE = _PKG_DIR / "barks_covers.py"

# --------------------------------------------------------------------------- #
# H1 series name -> Issues enum (only series that overlap the curated data).
# "Four Color N" issue ids always resolve to Issues.FC regardless of series.
# --------------------------------------------------------------------------- #
SERIES_TO_ISSUE: dict[str, Issues] = {
    "BOYS’ AND GIRLS’ MARCH OF COMICS": Issues.MC,
    "MARCH OF COMICS": Issues.MC,
    "CHEERIOS PREMIUMS": Issues.CH,
    "CHRISTMAS IN DISNEYLAND": Issues.CID,
    "CHRISTMAS PARADE": Issues.CP,
    "DISNEYLAND BIRTHDAY PARTY": Issues.DIBP,
    "DONALD DUCK": Issues.DD,
    "FIRESTONE CHRISTMAS GIVEAWAYS": Issues.FG,
    "KITE GIVEAWAYS": Issues.KI,
    "MICKEY MOUSE ALMANAC": Issues.MMA,
    "SUMMER FUN": Issues.SF,
    "UNCLE SCROOGE": Issues.US,
    "UNCLE SCROOGE GOES TO DISNEYLAND": Issues.USGTD,
    "UNCLE SCROOGE AND DONALD DUCK": Issues.USA,
    "VACATION PARADE": Issues.VP,
    "HUEY, DEWEY AND LOUIE JUNIOR WOODCHUCKS": Issues.HDL,
    "WALT DISNEY’S COMICS AND STORIES": Issues.CS,
}

# H1 sections that are wholly out of scope for the one-to-one reconciliation:
# non-duck series whose stories *and* covers have no library counterpart.
EXCLUDED_SERIES: frozenset[str] = frozenset(
    {
        "OUR GANG COMICS",
        "NEW FUNNIES",
        "PORKY PIG",
        "TOM AND JERRY SUMMER FUN",
        "TOM AND JERRY WINTER CARNIVAL",
    }
)

# Entry text that marks a reprint of an earlier appearance: "A reprint of ...",
# "Reprinted from ...", and the USA 1 variant "Reprinted with changes by Barks
# from ...". Reprints are excluded as a category (the original carries the link).
REPRINT_RE = re.compile(
    r"\b(?:a reprint of|reprinted(?:\s+with\s+changes\s+by\s+barks)?\s+from)\b",
    re.IGNORECASE,
)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip

# A bare H1 series title (without the trailing "(Dell)" etc.).
H1_RE = re.compile(r"<h1>(.*?)</h1>", re.DOTALL)
BLOCK_RE = re.compile(r"<(h1|h2|h3|p)\b[^>]*>(.*?)</\1>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
SPAN_RE = re.compile(r"<span\b[^>]*/>")

# Inline formatting tags preserved in stored text fields (descriptions, notes,
# titles); everything else is structural and stripped.
INLINE_KEEP = ("em", "i", "strong", "b", "sup", "sub", "u", "small")
_KEEP = "|".join(INLINE_KEEP)
NON_KEEP_TAG_RE = re.compile(rf"</?(?!(?:{_KEEP})\b)[a-zA-Z][^>]*>")
# A formatting tag wrapping a trailing submission date, e.g. "<em>(...)</em>".
WRAP_OPEN_RE = re.compile(rf"<(?:{_KEEP})\b[^>]*>\s*$", re.IGNORECASE)
WRAP_CLOSE_RE = re.compile(rf"\.?\s*</(?:{_KEEP})\s*>", re.IGNORECASE)

# Trailing parenthetical at the very end of a paragraph (the candidate date).
TAIL_PAREN_RE = re.compile(r"\(([^()]*)\)\.?\s*$")
# A strict Barks submission date: "Dec. 3, 1947" / "May 14?, 1959" / "April 18, 1957".
DATE_RE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(\?)?,\s*(\d{4})$")
# A submission date with no day: "(December 1942)".
DATE_NO_DAY_RE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$")
# A date anywhere (for date-list tails like "June 17, 1954, and July 8, 1954").
DATE_SUB_RE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(\??),\s*(\d{4})")
# Issue header: anything ending in "- <N> pages" (the blob before is id + date).
ISSUE_RE = re.compile(r"^(.+?)\s+-\s+(\d+)\s+[Pp]ages?\.?$")
# Split a dash-less issue blob like "43 (4/7) April 1944" into id + date.
ISSUE_BLOB_RE = re.compile(r"^(\d+\s*\(\d+/\d+\)|Four Color\s+\d+|\S+)\s+(.+)$")
# Cover paragraphs: "Front cover:", "Back cover:", "Inside front/back cover:".
COVER_RE = re.compile(r"^(?:Front|Back|Inside (?:front|back)) cover\b", re.IGNORECASE)
# Qualifier embedded in an entry body.
QUALIFIER_RE = re.compile(r"\b(art only|script only)\b", re.IGNORECASE)


class Disposition(Enum):
    """Why a bibliography entry does (or does not) link to a library record.

    Every entry must end up with exactly one disposition; ``None`` means
    undisposed — the work queue. ``COVER`` is assigned by the Phase 3 cover
    registry; until then covers stay undisposed.
    """

    MATCHED_TITLE = auto()  # linked to a Titles member via ComicBookInfo
    COVER = auto()  # linked to a BarksCover registry record (Phase 3)
    REPRINT = auto()  # reprint of an earlier appearance; the original has the link
    EXCLUDED_SECTION = auto()  # whole H1 section out of scope (non-duck series)
    EXCLUDED_ENTRY = auto()  # individually excluded, with a reason (overrides.py)


# --------------------------------------------------------------------------- #
# Builder dataclasses (mirrored by the emitted module).
# --------------------------------------------------------------------------- #
@dataclass
class BibEntry:
    raw_title: str
    page_count: str
    qualifier: str | None
    is_cover: bool
    description: str
    submitted_day: int
    submitted_month: int
    submitted_year: int
    raw_date: str
    date_unavailable: bool
    notes: list[str] = field(default_factory=list)
    title: Titles | None = None
    disposition: Disposition | None = None
    disposition_reason: str | None = None
    cover_key: tuple[str, int, int, str, int] | None = None  # BarksCover.key for COVER entries


@dataclass
class BibIssue:
    raw_issue_id: str
    issue_name: Issues | None
    issue_number: int
    issue_month: int
    issue_year: int
    page_count: int
    official_title: str | None
    raw_date: str
    header_tag: str = "h2"  # source tag the header came from: h2 / h3 / strong / p
    entries: list[BibEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class BibSeries:
    h1_name: str
    issue_name: Issues | None
    notes: list[str] = field(default_factory=list)
    issues: list[BibIssue] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #
def clean(raw_html: str) -> str:
    """Strip all tags/spans and unescape entities, collapsing whitespace."""
    text = SPAN_RE.sub("", raw_html)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def clean_rich(raw_html: str) -> str:
    """Like ``clean`` but keep inline formatting tags (``<em>``, ``<i>``, ...)."""
    text = SPAN_RE.sub("", raw_html)
    text = NON_KEEP_TAG_RE.sub("", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def strip_tags(text: str) -> str:
    """Remove any remaining tags from an already-cleaned (rich) string."""
    return re.sub(r"\s+", " ", TAG_RE.sub("", text)).strip()


def bare_series_name(h1: str) -> str:
    """'DONALD DUCK (Dell/Gold Key)' -> 'DONALD DUCK'."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", h1).strip()


def parse_month_token(token: str) -> int:
    return MONTHS.get(token.lower().rstrip(".")[:3], -1)


def parse_submission_date(paren_text: str) -> tuple[int, int, int, bool] | None:
    """Return (day, month, year, unavailable) for a strict submission date."""
    # Drop any inline tags and bracketed annotations, e.g.
    # "<em>Feb. 6, 1953 [idea] and May 21, 1953 [art]</em>", and repair a stray
    # period in a typo'd year, e.g. "195.1" -> "1951".
    t = re.sub(r"\[[^\]]*\]", "", strip_tags(paren_text)).strip()
    t = re.sub(r"(\d)\.(\d)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t)
    # A hedged date is still a date: "(Probably May 24, 1956)" - US 33 Tree
    # Trick and the DD FC at source line ~1565.
    t = re.sub(r"^Probably\s+", "", t, flags=re.IGNORECASE)
    if t.rstrip(".").lower() == "date not available":
        return (-1, -1, -1, True)
    m = DATE_RE.match(t)
    if m:
        month = parse_month_token(m.group(1))
        if month == -1:
            return None
        return (int(m.group(2)), month, int(m.group(4)), False)
    m = DATE_NO_DAY_RE.match(t)
    if m:
        month = parse_month_token(m.group(1))
        if month == -1:
            return None
        return (-1, month, int(m.group(2)), False)
    # Date-list tail, e.g. "June 17, 1954, and July 8, 1954": accept only if the
    # text is *nothing but* dates joined by "and"/punctuation, and use the last.
    matches = list(DATE_SUB_RE.finditer(t))
    if matches:
        residual = DATE_SUB_RE.sub("", t)
        # Also drop year-less "Month Day" fragments, e.g. the "Feb. 15" in
        # "Feb. 15 and Mar. 15, 1951" (both dates share the trailing year).
        residual = re.sub(r"[A-Za-z]{3,9}\.?\s+\d{1,2}\??", "", residual)
        residual = re.sub(r"\b(and|to)\b|[,.\s]", "", residual)
        if not residual:
            last = matches[-1]
            month = parse_month_token(last.group(1))
            if month != -1:
                return (int(last.group(2)), month, int(last.group(4)), False)
    return None


def parse_issue_date(date_str: str) -> tuple[int, int]:
    """Parse an issue header date -> (month, year); bracketed code date wins."""
    s = date_str.strip()
    bracket = re.search(r"\[(.*?)\]", s)
    if bracket:  # e.g. "Dec.-Feb. 1961 [(November) 1960]" -> code date in brackets
        inner = bracket.group(1)
        if not re.search(r"19\d{2}", inner):
            # Nested the other way: "Apr.-June 1960 ([March] 1960)" — only the
            # month is bracketed, so widen to the enclosing parenthetical to
            # keep the code date's year.
            paren = re.search(r"\(([^()]*\[[^\]]*\][^()]*)\)", s)
            if paren:
                inner = paren.group(1).replace("[", " ").replace("]", " ")
        s = inner
    year_m = re.search(r"(19\d{2})", s)
    year = int(year_m.group(1)) if year_m else -1
    mon_m = re.search(r"\(?([A-Za-z]{3,9})\.?\)?", s)
    month = parse_month_token(mon_m.group(1)) if mon_m else -1
    return (month, year)


def parse_issue_number(issue_id: str) -> int:
    """'Four Color 189' -> 189, 'Y1' -> 1, '209 (18/5)' -> 209, no digits -> -1."""
    m = re.search(r"(\d+)", issue_id)
    return int(m.group(1)) if m else -1


def issue_type_for(issue_id: str, series_default: Issues | None) -> Issues | None:
    if issue_id.lower().startswith("four color"):
        return Issues.FC
    return series_default


def split_issue_blob(blob: str) -> tuple[str, str]:
    """Split the text before '- N pages' into (issue_id, date_str)."""
    if " - " in blob:
        issue_id, _, date = blob.partition(" - ")
        return (issue_id.strip(), date.strip())
    m = ISSUE_BLOB_RE.match(blob)  # dash dropped, e.g. "43 (4/7) April 1944"
    if m:
        return (m.group(1).strip(), m.group(2).strip())
    return (blob.strip(), "")


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_tree() -> list[BibSeries]:
    text = SOURCE.read_text(encoding="utf-8")

    # Find the first real series H1 to skip the preamble + title-page H1.
    first_series_pos = None
    for m in H1_RE.finditer(text):
        if clean(m.group(1)) != "A Carl Barks Comic-Book Bibliography":
            first_series_pos = m.start()
            break
    body = text[first_series_pos:]

    series_list: list[BibSeries] = []
    cur_series: BibSeries | None = None
    cur_issue: BibIssue | None = None
    cur_entry: BibEntry | None = None
    pending_official_title: str | None = None

    for m in BLOCK_RE.finditer(body):
        tag = m.group(1)
        raw_inner = m.group(2)
        # A block may pack several logical lines, separated by <br/> or a raw
        # newline — e.g. an entry followed by its note, or an issue header
        # followed by its official title. Treat each as its own line. Inline
        # formatting tags (<em>, ...) are preserved; structural tags are dropped.
        segments = [s for s in (clean_rich(p) for p in re.split(r"<br\s*/?>|\n", raw_inner)) if s]
        if not segments:
            continue
        first = segments[0]
        first_plain = strip_tags(first)

        if tag == "h1":
            name = strip_tags(first)
            cur_series = BibSeries(h1_name=name, issue_name=SERIES_TO_ISSUE.get(bare_series_name(name)))
            series_list.append(cur_series)
            cur_issue = None
            cur_entry = None
            pending_official_title = None
            continue

        if cur_series is None:
            continue

        issue_m = ISSUE_RE.match(first_plain)
        if issue_m and not is_entry(first_plain):
            issue_id, date_str = split_issue_blob(issue_m.group(1).strip())
            month, year = parse_issue_date(date_str)
            official = segments[1] if len(segments) > 1 else pending_official_title
            # Record the source tag so the report can flag headers not in <h2>.
            if tag == "p":
                header_tag = "strong" if re.match(r"\s*<strong\b", raw_inner, re.IGNORECASE) else "p"
            else:
                header_tag = tag
            cur_issue = BibIssue(
                raw_issue_id=issue_id,
                issue_name=issue_type_for(issue_id, cur_series.issue_name),
                issue_number=parse_issue_number(issue_id),
                issue_month=month,
                issue_year=year,
                page_count=int(issue_m.group(2)),
                official_title=official,
                raw_date=date_str,
                header_tag=header_tag,
            )
            cur_series.issues.append(cur_issue)
            cur_entry = None
            pending_official_title = None
            continue

        if tag == "h3":  # non-issue H3 -> the issue's official story title
            pending_official_title = first
            if cur_issue is not None and cur_issue.official_title is None:
                cur_issue.official_title = first
            continue

        # A block may hold several entries (each its own newline-separated line) or
        # an entry split mid-sentence by a newline. Merge only continuation lines
        # (those that don't start with a capital) into the entry they belong to,
        # then treat each resulting unit independently.
        units: list[str] = []
        for seg in segments:
            seg_text = strip_tags(seg)
            # A line that is nothing but a parenthetical submission date belongs
            # to the entry above it (the EPUB wraps some dates onto their own
            # line, e.g. US 65 Micro-ducks' "(Dec. 7, 1965)").
            bare_date = re.match(r"^\([^()]*19\d\d[^()]*\)\.?$", seg_text)
            if units and (bare_date or not re.match(r'^["“(]?\s*[A-Z]', seg_text)):
                units[-1] = f"{units[-1]} {seg}"
            else:
                units.append(seg)

        def add_entry(entry: BibEntry) -> None:
            nonlocal cur_entry
            if cur_issue is not None:
                cur_issue.entries.append(entry)
            cur_entry = entry

        def add_note(text: str) -> None:
            if cur_entry is not None:
                cur_entry.notes.append(text)
            elif cur_issue is not None:
                cur_issue.notes.append(text)
            elif cur_series is not None:
                cur_series.notes.append(text)

        for unit in units:
            # An entry runs up to its submission date; text after the date is a
            # trailing note. Undated gags/covers are detected structurally.
            if looks_like_entry(strip_tags(unit)):
                date_hit = find_submission_date(unit)
                if date_hit is not None:
                    (day, month, year, unavail), raw_date, dstart, dend = date_hit
                    add_entry(build_entry(unit[:dstart].rstrip(" .,"), day, month, year, unavail, raw_date))
                    remainder = unit[dend:].strip(" .,")
                    if remainder:
                        cur_entry.notes.append(remainder)
                else:
                    add_entry(build_entry(unit, -1, -1, -1, False, ""))
            else:
                add_note(unit)

    return series_list


# A page-count signature near the start of an entry: a dash (hyphen/en/em) then a
# page number/fraction (but not a 4-digit year), OR "N (inside front cover)" /
# "N (pp. ...)" where the dash is sometimes dropped.
PAGECOUNT_SIG = re.compile(
    r"^.{0,90}?(?:[-–—]\s*(?:\d{1,3}|[¼½¾⅓⅔⅛⅜⅝⅞])(?!\d)"
    r"|\d{1,3}\s*\((?:inside|back|pp)\b)",
    re.IGNORECASE,
)
# A line that merely ends in "- N pages" is an issue/reprint note, not an entry.
ENDS_IN_PAGES_RE = re.compile(r"[-–—]\s*\d+\s+[Pp]ages?\.?$")


def find_submission_date(full: str) -> tuple[tuple[int, int, int, bool], str, int, int] | None:
    """Locate the first parenthesised Barks submission date in a paragraph.

    Returns the parsed date, the clean date text, and the [start, end) span to
    cut at — extended to swallow a wrapping formatting tag, e.g. the ``<em>`` and
    ``</em>`` around ``<em>(Mar. 14, 1957)</em>``, so neither dangles in a field.
    """
    for mm in re.finditer(r"\(([^()]*)\)", full):
        parsed = parse_submission_date(mm.group(1))
        if parsed is None:
            continue
        start, end = mm.start(), mm.end()
        pre = WRAP_OPEN_RE.search(full[:start])
        if pre:
            start = pre.start()
        post = WRAP_CLOSE_RE.match(full[end:])
        if post:
            end += post.end()
        return parsed, strip_tags(mm.group(1)).strip(), start, end
    return None


def looks_like_entry(txt: str) -> bool:
    """True for a story/cover paragraph, even when it carries no date."""
    if COVER_RE.match(txt):
        return True
    if ENDS_IN_PAGES_RE.search(txt):
        return False
    if not re.match(r'^["“(]?\s*[A-Z]', txt):
        return False
    return bool(PAGECOUNT_SIG.match(txt))


def is_entry(txt: str) -> bool:
    """Guard used to keep an issue-looking line that is really an entry out of
    issue parsing."""
    return bool(COVER_RE.match(txt)) or find_submission_date(txt) is not None


def build_entry(
    body: str, day: int, month: int, year: int, unavailable: bool, raw_date: str
) -> BibEntry:
    # ``body`` keeps inline tags; classify on a stripped copy but store the rich
    # title/description.
    stripped = strip_tags(body)
    is_cover = bool(COVER_RE.match(stripped))
    qmatch = QUALIFIER_RE.search(stripped)
    qualifier = qmatch.group(1).lower() if qmatch else None
    raw_title, page_count, description = split_entry_body(body, is_cover)
    return BibEntry(
        raw_title=raw_title,
        page_count=page_count,
        qualifier=qualifier,
        is_cover=is_cover,
        description=description,
        submitted_day=day,
        submitted_month=month,
        submitted_year=year,
        raw_date=raw_date,
        date_unavailable=unavailable,
    )


def split_entry_body(body: str, is_cover: bool) -> tuple[str, str, str]:
    """Best-effort split of an entry body into (title, page_count, description)."""
    if is_cover:
        # "Front cover: <desc>" or "Front cover (art only): <desc>"
        head, _, desc = body.partition(":")
        return (head.strip(), "", desc.strip())

    # Story: "<title> - <pages> <sep> <desc>".  The page count follows a dash; the
    # separator before the description is irregular (dash, period, or just space).
    page = r"(?:\d{1,3}|[¼½¾⅓⅔⅛⅜⅝⅞])[\d¼½¾⅓⅔⅛⅜⅝⅞/ ]*(?:\([^)]*\))?"
    m = re.search(rf"[-–—]\s*({page})", body)  # dash spacing is irregular
    if m is None:  # dash dropped: "<title> N (inside front cover) ..."
        m = re.search(r"\s(\d{1,3}\s*\([^)]*cover[^)]*\))", body)
    if m is None:
        return (body.strip(), "", "")
    title = body[: m.start()].strip()
    page_count = m.group(1).strip()
    desc = re.sub(r"^[-–—.]\s*", "", body[m.end() :].lstrip())
    # Drop a leading "art only"/"script only" qualifier from the description.
    desc = re.sub(r"^(art only|script only)\s*[-–—.]?\s*", "", desc, flags=re.IGNORECASE)
    return (title, page_count, desc.strip())


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def norm(s: str) -> str:
    s = TAG_RE.sub(" ", s).lower()  # drop inline tags so they don't pollute matching
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_nospace(s: str) -> str:
    return norm(s).replace(" ", "")


@dataclass
class MatchResult:
    cbi: ComicBookInfo
    entry: BibEntry | None
    method: str  # "title" | "keyword" | "override" | "unmatched"


class IssueIndex:
    """Bibliography issues indexed by (name, number) and by (name, year).

    Issue *number* is the reliable join key — Barrier's cover-date *years*
    routinely differ from comic_book_info by a year (e.g. US 4 is dated
    "Dec.-Feb. 1954" but listed as 1953). Year is only used for unnumbered
    issues (Firestone, March of Comics) and to break number collisions.
    """

    def __init__(self, series_list: list[BibSeries]) -> None:
        self.by_number: dict[tuple[Issues, int], list[BibIssue]] = {}
        self.by_year: dict[tuple[Issues, int], list[BibIssue]] = {}
        for series in series_list:
            for issue in series.issues:
                if issue.issue_name is None:
                    continue
                self.by_year.setdefault((issue.issue_name, issue.issue_year), []).append(issue)
                if issue.issue_number != -1:
                    self.by_number.setdefault(
                        (issue.issue_name, issue.issue_number), []
                    ).append(issue)


def issues_for(idx: IssueIndex, cbi: ComicBookInfo) -> list[BibIssue]:
    """Bibliography issues for a ComicBookInfo: by number, else by year."""
    if cbi.issue_number != -1:
        cands = idx.by_number.get((cbi.issue_name, cbi.issue_number), [])
        if len(cands) == 1:
            return cands
        if cands:  # number collision (e.g. Dell vs Gold Key) -> closest year
            return [min(cands, key=lambda i: abs(i.issue_year - cbi.issue_year))]
    group = idx.by_year.get((cbi.issue_name, cbi.issue_year), [])
    unnumbered = [i for i in group if i.issue_number == -1]
    if unnumbered:
        return unnumbered
    if len(group) == 1:
        return group
    return []


def issue_entries(idx: IssueIndex, cbi: ComicBookInfo) -> list[BibEntry]:
    """All entries (incl. covers) for a ComicBookInfo's issue, for display."""
    return [e for i in issues_for(idx, cbi) for e in i.entries]


def match_all(series_list: list[BibSeries]) -> list[MatchResult]:
    idx = IssueIndex(series_list)
    linked: set[int] = set()  # id() of already-claimed entries
    done: dict[Titles, tuple[BibEntry | None, str]] = {}
    cbis = list(BARKS_TITLE_INFO)

    def candidates(cbi: ComicBookInfo) -> list[BibEntry]:
        # Front covers are never ComicBookInfo records, so exclude them.
        return [
            e for e in issue_entries(idx, cbi) if not e.is_cover and id(e) not in linked
        ]

    def claim(title: Titles, entry: BibEntry, method: str) -> None:
        linked.add(id(entry))
        done[title] = (entry, method)

    # Pass 0: explicit overrides (Titles -> locator, or None = intentionally absent).
    for cbi in cbis:
        if cbi.title in OVERRIDES and cbi.title not in done:
            loc = OVERRIDES[cbi.title]
            if loc is None:
                done[cbi.title] = (None, "absent")
                continue
            entry = resolve_override(idx, loc)
            if entry is not None and id(entry) not in linked:
                claim(cbi.title, entry, "override")

    # Pass 1: full-title substring match.
    for cbi in cbis:
        if cbi.title in done:
            continue
        want = norm(ENUM_TO_STR_TITLE[cbi.title])
        want_ns = norm_nospace(ENUM_TO_STR_TITLE[cbi.title])
        for e in candidates(cbi):
            body = norm(e.raw_title + " " + e.description)
            body_ns = norm_nospace(e.raw_title + " " + e.description)
            if (want and want in body) or (want_ns and len(want_ns) >= 8 and want_ns in body_ns):
                claim(cbi.title, e, "title")
                break

    # Pass 2 + 3 to a fixpoint: keyword winner, then sole-remaining-candidate.
    changed = True
    while changed:
        changed = False
        for cbi in cbis:
            if cbi.title in done:
                continue
            cands = candidates(cbi)
            if not cands:
                continue
            tokens = [t for t in norm(ENUM_TO_STR_TITLE[cbi.title]).split() if len(t) > 2]
            scored = sorted(
                (
                    (sum(1 for t in tokens if t in body or t.rstrip("s") in body), e)
                    for e in cands
                    for body in [norm(e.raw_title + " " + e.description)]
                ),
                key=lambda x: -x[0],
            )
            if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                claim(cbi.title, scored[0][1], "keyword")
                changed = True
        # Sole-remaining-candidate pass (covers the title-less WDCS stories).
        for cbi in cbis:
            if cbi.title in done:
                continue
            cands = candidates(cbi)
            if len(cands) == 1:
                claim(cbi.title, cands[0], "single")
                changed = True

    # Pass 4: conservative exact-date alignment. Within a same-issue group of
    # still-unmatched cbis and unmatched (non-cover) entries, pair a cbi to an
    # entry ONLY when they are each other's UNIQUE same-date partner. This
    # resolves title-less gags whose dates agree, but never guesses across a date
    # tie or a date discrepancy (validating dates means we can't lean on them to
    # break ambiguity) — those are left unmatched for a manual override.
    groups: dict[tuple[int, ...], tuple[list[BibIssue], list[ComicBookInfo]]] = {}
    for cbi in cbis:
        if cbi.title in done:
            continue
        iss = issues_for(idx, cbi)
        if not iss:
            continue
        key = tuple(id(i) for i in iss)
        groups.setdefault(key, (iss, []))[1].append(cbi)

    def cbi_date(c: ComicBookInfo) -> tuple[int, int, int]:
        return (c.submitted_year, c.submitted_month, c.submitted_day)

    def ent_date(e: BibEntry) -> tuple[int, int, int]:
        return (e.submitted_year, e.submitted_month, e.submitted_day)

    for iss, group_cbis in groups.values():
        rem_cbis = list(group_cbis)
        rem_entries = [e for i in iss for e in i.entries if not e.is_cover and id(e) not in linked]
        changed = True
        while changed:
            changed = False
            for c in list(rem_cbis):
                if cbi_date(c) == (-1, -1, -1):
                    continue
                twins = [e for e in rem_entries if ent_date(e) == cbi_date(c)]
                if len(twins) != 1:
                    continue
                entry = twins[0]
                if sum(1 for cc in rem_cbis if cbi_date(cc) == ent_date(entry)) != 1:
                    continue  # the entry's date is shared by >1 cbi -> ambiguous
                claim(c.title, entry, "order")
                rem_cbis.remove(c)
                rem_entries.remove(entry)
                changed = True

    results = [
        MatchResult(cbi, done[cbi.title][0], done[cbi.title][1])
        if cbi.title in done
        else MatchResult(cbi, None, "unmatched")
        for cbi in cbis
    ]
    for r in results:  # write the resolved Titles back onto the entries
        if r.entry is not None:
            r.entry.title = r.cbi.title
    return results


def resolve_override(idx: IssueIndex, loc: tuple[Issues, int, int, int]) -> BibEntry | None:
    issue_name, number, year, entry_index = loc
    if number != -1:
        issues = idx.by_number.get((issue_name, number), [])
    else:
        issues = [i for i in idx.by_year.get((issue_name, year), []) if i.issue_number == -1]
    issues = [i for i in issues if i.issue_year == year] or issues
    entries = [e for i in issues for e in i.entries]
    if 0 <= entry_index < len(entries):
        return entries[entry_index]
    return None


# --------------------------------------------------------------------------- #
# Dispositions
# --------------------------------------------------------------------------- #
def assign_dispositions(series_list: list[BibSeries]) -> list[str]:
    """Stamp a ``Disposition`` on every entry; return human-readable warnings.

    Must run *after* ``match_all`` (matching writes ``entry.title``).
    Precedence: excluded section > matched title > manual entry exclusion >
    reprint. Anything left is undisposed — the work queue for Phases 2-3
    (story add-candidates and the cover registry).
    """
    warnings: list[str] = []
    idx = IssueIndex(series_list)

    # Resolve the manual exclusions up front, verifying each guard snippet so a
    # shifted positional index is reported instead of silently misfiring.
    excluded_entries: dict[int, str] = {}  # id(entry) -> reason
    for loc, (guard, reason) in ENTRY_EXCLUSIONS.items():
        entry = resolve_override(idx, loc)
        if entry is None:
            warnings.append(f"ENTRY_EXCLUSIONS {loc}: locator resolves to no entry")
            continue
        text = strip_tags(f"{entry.raw_title} {entry.description}")
        if guard.lower() not in text.lower():
            warnings.append(
                f"ENTRY_EXCLUSIONS {loc}: guard {guard!r} not found in "
                f"{text[:60]!r} — entry indices shifted?"
            )
            continue
        if entry.title is not None:
            warnings.append(
                f"ENTRY_EXCLUSIONS {loc}: entry is matched to {entry.title.name} — "
                "an exclusion must not shadow a real match"
            )
            continue
        excluded_entries[id(entry)] = reason

    for series in series_list:
        series_name = bare_series_name(series.h1_name)
        in_excluded_section = series_name in EXCLUDED_SERIES
        for issue in series.issues:
            for e in issue.entries:
                body = strip_tags(f"{e.raw_title} {e.description} {' '.join(e.notes)}")
                is_reprint = bool(REPRINT_RE.search(body))
                if in_excluded_section:
                    if e.title is not None:
                        warnings.append(
                            f"{series_name} {issue.raw_issue_id}: entry matched to "
                            f"{e.title.name} inside an excluded section"
                        )
                    e.disposition = Disposition.EXCLUDED_SECTION
                    e.disposition_reason = f"non-duck section: {series_name}"
                elif e.title is not None:
                    if is_reprint:
                        warnings.append(
                            f"{series_name} {issue.raw_issue_id}: matched entry "
                            f"{e.title.name} also looks like a reprint — check"
                        )
                    e.disposition = Disposition.MATCHED_TITLE
                elif id(e) in excluded_entries:
                    e.disposition = Disposition.EXCLUDED_ENTRY
                    e.disposition_reason = excluded_entries[id(e)]
                elif is_reprint:
                    e.disposition = Disposition.REPRINT
                else:
                    e.disposition = None  # undisposed: the Phase 2-3 work queue
    return warnings


# --------------------------------------------------------------------------- #
# Cover registry (barks_covers.py)
# --------------------------------------------------------------------------- #
COVER_KIND_RE = re.compile(r"^(Front|Inside front|Inside back|Back) cover", re.IGNORECASE)
COVER_QUALIFIER_RE = re.compile(r"^[^(]*\(([^)]*)\)")
ILLUSTRATING_RE = re.compile(r"\(\s*Illustrating\s+[“\"](.+?)[”\"]\s*\.?\s*\)")


@dataclass
class CoverRec:
    """A registry-shaped view of one bibliography cover entry."""

    entry: BibEntry
    series_name: str
    issue_name: Issues | None
    issue_number: int
    issue_month: int
    issue_year: int
    kind: str  # CoverKind member name: FRONT / INSIDE_FRONT / INSIDE_BACK / BACK
    seq: int
    qualifier: str | None
    description: str
    illustrates: Titles | None

    @property
    def key(self) -> tuple[str, int, int, str, int]:
        return (self.series_name, self.issue_number, self.issue_year, self.kind, self.seq)


def collect_covers(series_list: list[BibSeries], warnings: list[str]) -> list[CoverRec]:
    """Build registry records for every in-scope (non-excluded) cover entry.

    Must run after ``assign_dispositions``: covers already dispositioned as
    reprints or excluded-section members are out of scope. ``seq`` is the 0-based
    position within ``(series, issue_number, issue_year, kind)`` in bibliography
    order, mirroring how the emitted registry disambiguates same-kind covers.
    """
    norm_title_map = {norm(s): t for s, t in STR_TITLE_TO_ENUM.items()}
    seqs: dict[tuple[str, int, int, str], int] = {}
    recs: list[CoverRec] = []
    for series in series_list:
        series_name = bare_series_name(series.h1_name)
        for issue in series.issues:
            for e in issue.entries:
                if not e.is_cover or e.disposition not in (None, Disposition.COVER):
                    continue
                head = strip_tags(e.raw_title)
                kind_m = COVER_KIND_RE.match(head)
                if kind_m is None:
                    warnings.append(f"{series_name} {issue.raw_issue_id}: cover kind unparsable: {head!r}")
                    continue
                kind = kind_m.group(1).upper().replace(" ", "_")
                qual_m = COVER_QUALIFIER_RE.match(head)
                qualifier = qual_m.group(1).strip().lower() if qual_m else None

                illustrates: Titles | None = None
                ill_m = ILLUSTRATING_RE.search(strip_tags(e.description))
                if ill_m:
                    raw = ill_m.group(1).rstrip(".").strip()
                    if raw in STR_TITLE_TO_ENUM:
                        illustrates = STR_TITLE_TO_ENUM[raw]
                    elif norm(raw) in norm_title_map:
                        illustrates = norm_title_map[norm(raw)]
                    elif raw in ILLUSTRATES_OVERRIDES:
                        illustrates = ILLUSTRATES_OVERRIDES[raw]
                    else:
                        warnings.append(
                            f"{series_name} {issue.raw_issue_id}: unresolved "
                            f"(Illustrating {raw!r}) — add to ILLUSTRATES_OVERRIDES"
                        )

                seq_key = (series_name, issue.issue_number, issue.issue_year, kind)
                seq = seqs.get(seq_key, 0)
                seqs[seq_key] = seq + 1
                e.cover_key = (series_name, issue.issue_number, issue.issue_year, kind, seq)
                recs.append(
                    CoverRec(
                        entry=e,
                        series_name=series_name,
                        issue_name=issue.issue_name,
                        issue_number=issue.issue_number,
                        issue_month=issue.issue_month,
                        issue_year=issue.issue_year,
                        kind=kind,
                        seq=seq,
                        qualifier=qualifier,
                        description=e.description,
                        illustrates=illustrates,
                    )
                )
    return recs


def verify_covers(cover_recs: list[CoverRec], warnings: list[str]) -> None:
    """Verify the bibliography covers ↔ ``BARKS_COVERS`` bijection.

    Each verified entry gets ``Disposition.COVER``. Mismatched fields, missing
    registry records and orphaned registry records are reported as warnings, so
    later ``source.xhtml`` edits are flagged rather than silently absorbed.
    """
    try:
        from barks_fantagraphics.barks_covers import BARKS_COVERS
    except ImportError:
        warnings.append("barks_covers.py not generated yet — run with --emit-covers to bootstrap")
        return

    by_key = {(c.series_name, c.issue_number, c.issue_year, c.kind.name, c.seq): c for c in BARKS_COVERS}
    if len(by_key) != len(BARKS_COVERS):
        warnings.append("BARKS_COVERS contains duplicate keys")
    claimed: set[tuple] = set()
    for rec in cover_recs:
        cover = by_key.get(rec.key)
        if cover is None:
            warnings.append(f"cover registry: no BarksCover for bibliography entry {rec.key}")
            continue
        claimed.add(rec.key)
        mismatches = []
        if (cover.submitted_day, cover.submitted_month, cover.submitted_year) != (
            rec.entry.submitted_day, rec.entry.submitted_month, rec.entry.submitted_year
        ):
            mismatches.append("submitted date")
        if cover.qualifier != rec.qualifier:
            mismatches.append("qualifier")
        if strip_tags(cover.description) != strip_tags(rec.description):
            mismatches.append("description")
        if cover.illustrates != rec.illustrates:
            mismatches.append("illustrates")
        if mismatches:
            warnings.append(f"cover registry: {rec.key} differs from bibliography: {', '.join(mismatches)}")
            continue
        rec.entry.disposition = Disposition.COVER
    for key in by_key.keys() - claimed:
        warnings.append(f"cover registry: BarksCover {key} has no bibliography entry")


def emit_covers_module(cover_recs: list[CoverRec]) -> None:
    lines: list[str] = []
    w = lines.append
    w("# ruff: noqa: E501, RUF001")
    w("")
    w('"""Carl Barks comic-book covers, from Michael Barrier\'s bibliography.')
    w("")
    w("Bootstrap-generated by experiments/bibliography/parse_bibliography.py --emit-covers,")
    w("then hand-maintained (like comic_book_info.py). The reconciliation report verifies")
    w("the one-to-one match between these records and the bibliography's cover entries.")
    w('"""')
    w("")
    w("from dataclasses import dataclass")
    w("from enum import Enum, auto")
    w("")
    w("from .barks_titles import Titles")
    w("from .comic_issues import Issues")
    w("")
    w("")
    w("class CoverKind(Enum):")
    w("    FRONT = auto()")
    w("    INSIDE_FRONT = auto()")
    w("    INSIDE_BACK = auto()")
    w("    BACK = auto()")
    w("")
    w("")
    w("CoverKey = tuple[str, int, int, str, int]")
    w("")
    w("")
    w('''@dataclass(frozen=True)
class BarksCover:
    issue_name: Issues | None  # None for series with no Issues member (cover-only albums)
    series_name: str  # bibliography H1 series name
    issue_number: int  # -1 for unnumbered issues
    issue_month: int
    issue_year: int
    kind: CoverKind
    seq: int  # 0-based tie-breaker within (series, issue, year, kind)
    qualifier: str | None  # e.g. "art only", "part", "pencil rough only"
    description: str
    submitted_day: int
    submitted_month: int
    submitted_year: int
    illustrates: Titles | None  # the curated story this cover illustrates, if any

    @property
    def key(self) -> CoverKey:
        return (self.series_name, self.issue_number, self.issue_year, self.kind.name, self.seq)''')
    w("")
    w("")
    w("BARKS_COVERS: list[BarksCover] = [")
    for rec in cover_recs:
        e = rec.entry
        w("    BarksCover(")
        w(f"        issue_name={py_repr(rec.issue_name)},")
        w(f"        series_name={rec.series_name!r},")
        w(f"        issue_number={rec.issue_number!r},")
        w(f"        issue_month={rec.issue_month!r},")
        w(f"        issue_year={rec.issue_year!r},")
        w(f"        kind=CoverKind.{rec.kind},")
        w(f"        seq={rec.seq!r},")
        w(f"        qualifier={rec.qualifier!r},")
        w(f"        description={rec.description!r},")
        w(f"        submitted_day={e.submitted_day!r},")
        w(f"        submitted_month={e.submitted_month!r},")
        w(f"        submitted_year={e.submitted_year!r},")
        w(f"        illustrates={py_repr(rec.illustrates)},")
        w("    ),")
    w("]")
    w("")
    w("BARKS_COVER_BY_KEY: dict[CoverKey, BarksCover] = {cover.key: cover for cover in BARKS_COVERS}")
    w("assert len(BARKS_COVER_BY_KEY) == len(BARKS_COVERS), \"duplicate BarksCover keys\"")
    w("")

    OUT_COVERS_MODULE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["uv", "run", "ruff", "format", str(OUT_COVERS_MODULE)], check=False)
    print(f"\nWROTE {OUT_COVERS_MODULE} ({len(cover_recs)} covers)")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def date_tuple(cbi: ComicBookInfo) -> tuple[int, int, int]:
    return (cbi.submitted_day, cbi.submitted_month, cbi.submitted_year)


def report(
    series_list: list[BibSeries],
    results: list[MatchResult],
    disposition_warnings: list[str],
) -> None:
    n = len(results)
    by_method: dict[str, int] = {}
    for r in results:
        by_method[r.method] = by_method.get(r.method, 0) + 1

    print("=" * 78)
    print(f"COVERAGE: {n} ComicBookInfo records")
    for method in ("title", "keyword", "single", "order", "override", "absent", "unmatched"):
        print(f"  {method:10s}: {by_method.get(method, 0)}")
    print("=" * 78)

    # Source-quality flag: issue headers that were tagged <strong>/<h3>/<p>
    # instead of <h2> in the EPUB (worth correcting in source.xhtml).
    mis_tagged = [
        (s, i) for s in series_list for i in s.issues if i.header_tag != "h2"
    ]
    if mis_tagged:
        print(f"\nISSUE HEADERS NOT IN <h2> ({len(mis_tagged)}) — fix the tag in source.xhtml:")
        for s, i in mis_tagged:
            name = i.issue_name.name if i.issue_name else "—"
            print(
                f"  <{i.header_tag}>  {bare_series_name(s.h1_name)} :: "
                f"{i.raw_issue_id!r} ({i.raw_date}) [{name}]"
            )

    post1978 = [r for r in results if r.entry is None and r.method == "unmatched" and r.cbi.issue_year > 1978]
    overridden_absent = [r for r in results if r.method == "absent"]
    unmatched = [
        r for r in results if r.entry is None and r.method == "unmatched" and r.cbi.issue_year <= 1978
    ]
    if post1978:
        print(f"\nNOT IN BARRIER — expected, post-1978 / non-US ({len(post1978)}):")
        for r in post1978:
            cbi = r.cbi
            print(f"  {ENUM_TO_STR_TITLE[cbi.title]}  [{cbi.issue_name.name} {cbi.issue_number} {cbi.issue_year}]")
    if overridden_absent:
        print(f"\nNO BARRIER ENTRY — override-confirmed findings ({len(overridden_absent)}):")
        for r in overridden_absent:
            cbi = r.cbi
            print(f"  {ENUM_TO_STR_TITLE[cbi.title]}  [{cbi.issue_name.name} {cbi.issue_number} {cbi.issue_year}]")

    if unmatched:
        print(f"\nUNMATCHED ({len(unmatched)}) — need an override or a SERIES_TO_ISSUE fix:")
        for r in unmatched:
            cbi = r.cbi
            print(
                f"  {ENUM_TO_STR_TITLE[cbi.title]!r}  "
                f"[{cbi.issue_name.name} {cbi.issue_number} {cbi.issue_year}]  "
                f"date={cbi.submitted_day}/{cbi.submitted_month}/{cbi.submitted_year}"
            )
            dump_issue_entries(series_list, cbi)

    for method, label in (("keyword", "KEYWORD"), ("order", "ORDER ALIGNMENT")):
        rs = [r for r in results if r.method == method]
        if rs:
            print(f"\nMATCHED BY {label} ({len(rs)}) — spot-check these:")
            for r in rs:
                print(
                    f"  {ENUM_TO_STR_TITLE[r.cbi.title]!r}  ->  "
                    f"{r.entry.raw_title!r} | {r.entry.description[:60]!r}"
                )

    discreps = []
    for r in results:
        if r.entry is None or r.entry.date_unavailable or r.entry.submitted_year == -1:
            continue
        bib = (r.entry.submitted_day, r.entry.submitted_month, r.entry.submitted_year)
        if bib != date_tuple(r.cbi):
            discreps.append((r, bib))
    if discreps:
        print(f"\nDATE DISCREPANCIES ({len(discreps)}) — the point of the exercise:")
        for r, bib in discreps:
            cbi = r.cbi
            print(
                f"  {ENUM_TO_STR_TITLE[cbi.title]:45s}  "
                f"cbi={cbi.submitted_day:>2}/{cbi.submitted_month:>2}/{cbi.submitted_year}  "
                f"bib={bib[0]:>2}/{bib[1]:>2}/{bib[2]}  ({r.method})"
            )

    unavailable = [r for r in results if r.entry is not None and r.entry.date_unavailable]
    if unavailable:
        print(f"\nBIB DATE UNAVAILABLE ({len(unavailable)}):")
        for r in unavailable:
            print(f"  {ENUM_TO_STR_TITLE[r.cbi.title]}")

    # ----------------------------------------------------------------- #
    # Dispositions: every bibliography entry must end up explained.
    # ----------------------------------------------------------------- #
    disp_counts: dict[str, int] = {}
    undisposed_covers: list[tuple[BibSeries, BibIssue, BibEntry]] = []
    undisposed_stories: list[tuple[BibSeries, BibIssue, BibEntry]] = []
    for s in series_list:
        for i in s.issues:
            for e in i.entries:
                key = e.disposition.name if e.disposition is not None else "UNDISPOSED"
                disp_counts[key] = disp_counts.get(key, 0) + 1
                if e.disposition is None:
                    (undisposed_covers if e.is_cover else undisposed_stories).append((s, i, e))

    total_entries = sum(disp_counts.values())
    print(f"\nDISPOSITIONS ({total_entries} bibliography entries):")
    for name in (*(d.name for d in Disposition), "UNDISPOSED"):
        print(f"  {name:16s}: {disp_counts.get(name, 0)}")

    if disposition_warnings:
        print(f"\nDISPOSITION WARNINGS ({len(disposition_warnings)}) — fix before trusting the counts:")
        for warning in disposition_warnings:
            print(f"  {warning}")

    if undisposed_covers:
        by_series: dict[str, int] = {}
        for s, _i, _e in undisposed_covers:
            name = bare_series_name(s.h1_name)
            by_series[name] = by_series.get(name, 0) + 1
        print(
            f"\nUNDISPOSED COVERS ({len(undisposed_covers)}) — Phase 3 cover-registry work queue:"
        )
        for name, count in sorted(by_series.items()):
            print(f"  {count:4d}  {name}")

    if undisposed_stories:
        print(
            f"\nUNDISPOSED STORIES ({len(undisposed_stories)}) — Phase 2 add-candidates:"
        )
        for s, i, e in undisposed_stories:
            print(
                f"  {bare_series_name(s.h1_name)[:28]:28s} {i.raw_issue_id:15s} "
                f"{strip_tags(e.raw_title)[:42]:44s} {strip_tags(e.description)[:50]}"
            )

    if not undisposed_covers and not undisposed_stories:
        print("\nUNDISPOSED: 0 — one-to-one invariant holds.")


def dump_issue_entries(series_list: list[BibSeries], cbi: ComicBookInfo) -> None:
    idx = IssueIndex(series_list)
    entries = issue_entries(idx, cbi)
    if not entries:
        print(
            f"        (no bibliography issue for "
            f"{cbi.issue_name.name} {cbi.issue_number} {cbi.issue_year})"
        )
        return
    for i, e in enumerate(entries):
        tag = f"-> {e.title.name}" if e.title else ("[cover]" if e.is_cover else "")
        print(f"        [{i}] {e.raw_title!r} | {e.description[:50]!r} {tag}")


# --------------------------------------------------------------------------- #
# Emit module
# --------------------------------------------------------------------------- #
def py_repr(value: object) -> str:
    if isinstance(value, Titles):
        return f"Titles.{value.name}"
    if isinstance(value, Issues):
        return f"Issues.{value.name}"
    return repr(value)


def emit_module(series_list: list[BibSeries]) -> None:
    lines: list[str] = []
    w = lines.append
    w("# ruff: noqa: E501, RUF001")
    w("")
    w('"""Carl Barks comic-book bibliography (Michael Barrier), as structured data.')
    w("")
    w("Generated by experiments/bibliography/parse_bibliography.py — do not edit by hand.")
    w('"""')
    w("")
    w("from dataclasses import dataclass")
    w("from enum import Enum, auto")
    w("")
    w("from .barks_titles import Titles")
    w("from .comic_issues import Issues")
    w("")
    w("")
    for cls in (
        '''class Disposition(Enum):
    """Why this entry does (or does not) link to a library record.

    Every entry carries exactly one disposition - the one-to-one invariant
    between the bibliography and the curated library.
    """

    MATCHED_TITLE = auto()  # linked to a Titles member (see ``title``)
    COVER = auto()  # linked to a BarksCover registry record (see ``cover_key``)
    REPRINT = auto()  # reprint of an earlier appearance; the original carries the link
    EXCLUDED_SECTION = auto()  # whole section out of scope (non-duck series)
    EXCLUDED_ENTRY = auto()  # individually excluded, with a reason''',
        '''@dataclass(frozen=True)
class BibEntry:
    raw_title: str
    page_count: str
    qualifier: str | None
    is_cover: bool
    description: str
    submitted_day: int
    submitted_month: int
    submitted_year: int
    raw_date: str
    date_unavailable: bool
    notes: tuple[str, ...]
    title: Titles | None
    disposition: Disposition
    disposition_reason: str | None
    cover_key: tuple[str, int, int, str, int] | None''',
        '''@dataclass(frozen=True)
class BibIssue:
    raw_issue_id: str
    issue_name: Issues | None
    issue_number: int
    issue_month: int
    issue_year: int
    page_count: int
    official_title: str | None
    raw_date: str
    entries: tuple[BibEntry, ...]
    notes: tuple[str, ...]''',
        '''@dataclass(frozen=True)
class BibSeries:
    h1_name: str
    issue_name: Issues | None
    notes: tuple[str, ...]
    issues: tuple[BibIssue, ...]''',
    ):
        w(cls)
        w("")
        w("")

    w("BIBLIOGRAPHY: list[BibSeries] = [")
    for s in series_list:
        w("    BibSeries(")
        w(f"        h1_name={s.h1_name!r},")
        w(f"        issue_name={py_repr(s.issue_name)},")
        w(f"        notes={tuple(s.notes)!r},")
        w("        issues=(")
        for issue in s.issues:
            w("            BibIssue(")
            w(f"                raw_issue_id={issue.raw_issue_id!r},")
            w(f"                issue_name={py_repr(issue.issue_name)},")
            w(f"                issue_number={issue.issue_number!r},")
            w(f"                issue_month={issue.issue_month!r},")
            w(f"                issue_year={issue.issue_year!r},")
            w(f"                page_count={issue.page_count!r},")
            w(f"                official_title={issue.official_title!r},")
            w(f"                raw_date={issue.raw_date!r},")
            w("                entries=(")
            for e in issue.entries:
                w("                    BibEntry(")
                w(f"                        raw_title={e.raw_title!r},")
                w(f"                        page_count={e.page_count!r},")
                w(f"                        qualifier={e.qualifier!r},")
                w(f"                        is_cover={e.is_cover!r},")
                w(f"                        description={e.description!r},")
                w(f"                        submitted_day={e.submitted_day!r},")
                w(f"                        submitted_month={e.submitted_month!r},")
                w(f"                        submitted_year={e.submitted_year!r},")
                w(f"                        raw_date={e.raw_date!r},")
                w(f"                        date_unavailable={e.date_unavailable!r},")
                w(f"                        notes={tuple(e.notes)!r},")
                w(f"                        title={py_repr(e.title)},")
                if e.disposition is None:
                    msg = f"entry {e.raw_title!r} has no disposition - cannot emit"
                    raise ValueError(msg)
                w(f"                        disposition=Disposition.{e.disposition.name},")
                w(f"                        disposition_reason={e.disposition_reason!r},")
                w(f"                        cover_key={e.cover_key!r},")
                w("                    ),")
            w("                ),")
            w(f"                notes={tuple(issue.notes)!r},")
            w("            ),")
        w("        ),")
        w("    ),")
    w("]")
    w("")
    w("")
    w("TITLE_TO_BIB_ENTRY: dict[Titles, BibEntry] = {")
    w("    entry.title: entry")
    w("    for series in BIBLIOGRAPHY")
    w("    for issue in series.issues")
    w("    for entry in issue.entries")
    w("    if entry.title is not None")
    w("}")
    w("")

    OUT_MODULE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["uv", "run", "ruff", "format", str(OUT_MODULE)], check=False)
    print(f"\nWROTE {OUT_MODULE}")


# --------------------------------------------------------------------------- #
def main() -> None:
    series_list = parse_tree()
    results = match_all(series_list)
    disposition_warnings = assign_dispositions(series_list)
    cover_recs = collect_covers(series_list, disposition_warnings)
    if "--emit-covers" in sys.argv:
        emit_covers_module(cover_recs)
    verify_covers(cover_recs, disposition_warnings)
    report(series_list, results, disposition_warnings)
    if "--emit" in sys.argv:
        emit_module(series_list)


if __name__ == "__main__":
    main()
