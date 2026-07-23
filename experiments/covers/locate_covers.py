"""Bootstrap COVER_LOCATIONS: match BARKS_COVERS to their Fantagraphics CCBDL reprints.

Reads the barks-wiki INDUCKS-derived index ``../barks-wiki/okf/reference/data/
ccbdl-contents.md`` (READ-ONLY — never regenerate or edit it from this repo) and
matches each front cover in ``BARKS_COVERS`` to the CCBDL illustration row whose
INDUCKS code is ``W <pub> <issue>-00``. The printed book page is converted to the
zip body page using the per-volume delta segments from the index's "Page-offset
summary"; pages beyond a volume's cross-checked range are flagged
``# page offset extrapolated - verify`` (the cover galleries are back-matter, so
this is the common case).

Emits to stdout:
  1. the COVER_LOCATIONS dict literal to paste into barks_covers.py
  2. BARKS_COVERS with no CCBDL -00 row (review list)
  3. CCBDL -00 rows matching no BarksCover (review list)
  4. duplicate -00 codes and how they were resolved
  5. hand-assignment candidates for the INSIDE_FRONT/BACK covers (never auto-assigned)
  6. CCBDL matches skipped because their volume has no delta data (vol 30)

Run with:  uv run python experiments/covers/locate_covers.py
"""

from __future__ import annotations

import re
from pathlib import Path

from barks_fantagraphics.barks_covers import BARKS_COVERS, BarksCover, CoverKind
from barks_fantagraphics.comic_issues import Issues

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CCBDL_CONTENTS = REPO_ROOT.parent / "barks-wiki" / "okf" / "reference" / "data" / "ccbdl-contents.md"

# BarksCover.issue_name -> INDUCKS publication code (as used in ccbdl-contents.md).
# Covers whose issue_name is None or unmapped are structurally unmatched (Whitman/
# Gladstone-era series, HDL 9 redrawn by another artist, ...).
ISSUE_TO_INDUCKS_PUB: dict[Issues, str] = {
    Issues.FC: "OS",
    Issues.CS: "WDC",
    Issues.US: "US",
    Issues.DD: "DD",
}

# (pg_lo, pg_hi, delta)
DeltaSeg = tuple[int, int, int]

# Simple INDUCKS codes we can key on: "W <PUB> <issue>-<suffix>". Codes with extra
# tokens (e.g. "W CGW Y 1-00") never correspond to a BARKS_COVERS record.
SIMPLE_CODE_RE = re.compile(r"^W ([A-Z]+) (\d+)-(\d+)$")

ROW_RE = re.compile(
    r"^\| (\d+) \| (\d+)([a-z]?) \| (illustration|cover) \| (.*?) \| (.*?) \| (.*?) \|"
)

DELTA_VOL_RE = re.compile(r"^- \*\*Vol (\d+):\*\* (.*)$")
DELTA_SEG_RE = re.compile(r"Δ ([+-]\d+) \(Pg (\d+)[–-](\d+)\)")


class CcbdlRow:
    def __init__(self, vol: int, pg: int, pg_suffix: str, title: str, code: str) -> None:
        self.vol = vol
        self.pg = pg
        self.pg_suffix = pg_suffix
        self.title = title
        self.code = code

    def __repr__(self) -> str:
        return f"vol {self.vol} p{self.pg}{self.pg_suffix} '{self.title}' [{self.code}]"


def parse_delta_summary(text: str) -> dict[int, list[DeltaSeg]]:
    deltas: dict[int, list[DeltaSeg]] = {}
    for line in text.splitlines():
        m = DELTA_VOL_RE.match(line)
        if not m:
            continue
        vol = int(m.group(1))
        segs = [
            (int(lo), int(hi), int(delta)) for delta, lo, hi in DELTA_SEG_RE.findall(m.group(2))
        ]
        if segs:
            deltas[vol] = segs
    return deltas


def parse_rows(text: str) -> list[CcbdlRow]:
    """All illustration/cover rows of the contents table, with their INDUCKS code."""
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        vol, pg, pg_suffix, _type, title, _pp, code = m.groups()
        rows.append(CcbdlRow(int(vol), int(pg), pg_suffix, title.strip(), code.strip()))
    return rows


def apply_delta(
    vol: int, printed_pg: int, deltas: dict[int, list[DeltaSeg]]
) -> tuple[int, bool] | None:
    """Return (body_page, extrapolated), or None if the volume has no delta data."""
    segs = deltas.get(vol)
    if not segs:
        return None
    for lo, hi, delta in segs:
        if lo <= printed_pg <= hi:
            return printed_pg + delta, False
    # Beyond the cross-checked range (or in a gap): nearest preceding segment's delta.
    preceding = [s for s in segs if s[0] <= printed_pg]
    _, _, delta = preceding[-1] if preceding else segs[0]
    return printed_pg + delta, True


def expected_pub_issue(cover: BarksCover) -> tuple[str, int] | None:
    if cover.issue_name is None:
        return None
    pub = ISSUE_TO_INDUCKS_PUB.get(cover.issue_name)
    if pub is None:
        return None
    return pub, cover.issue_number


def cover_desc(cover: BarksCover) -> str:
    return (
        f"{cover.series_name} #{cover.issue_number} "
        f"{cover.issue_year}-{cover.issue_month:02d} {cover.kind.name}"
    )


def main() -> None:
    text = CCBDL_CONTENTS.read_text(encoding="utf-8")
    deltas = parse_delta_summary(text)
    rows = parse_rows(text)

    # Front-cover rows keyed by (pub, issue); values sorted (vol, pg).
    front_rows: dict[tuple[str, int], list[CcbdlRow]] = {}
    all_cover_rows_by_issue: dict[tuple[str, int], list[CcbdlRow]] = {}
    unkeyed_00_rows: list[CcbdlRow] = []
    for row in rows:
        m = SIMPLE_CODE_RE.match(row.code)
        if not m:
            if row.code.endswith("-00"):
                unkeyed_00_rows.append(row)
            continue
        pub, issue, suffix = m.group(1), int(m.group(2)), m.group(3)
        all_cover_rows_by_issue.setdefault((pub, issue), []).append(row)
        if suffix == "00":
            front_rows.setdefault((pub, issue), []).append(row)
    for row_list in front_rows.values():
        row_list.sort(key=lambda r: (r.vol, r.pg, r.pg_suffix))

    matches: list[tuple[BarksCover, CcbdlRow, int, bool, list[CcbdlRow]]] = []
    unmatched_covers: list[tuple[BarksCover, str]] = []
    non_front_covers: list[BarksCover] = []
    no_delta_matches: list[tuple[BarksCover, CcbdlRow]] = []
    duplicates_resolved: list[tuple[str, CcbdlRow, list[CcbdlRow]]] = []
    used_keys: set[tuple[str, int]] = set()

    for cover in BARKS_COVERS:
        if cover.kind != CoverKind.FRONT:
            non_front_covers.append(cover)
            continue
        key = expected_pub_issue(cover)
        if key is None:
            unmatched_covers.append((cover, "no INDUCKS publication mapping"))
            continue
        candidates = front_rows.get(key)
        if not candidates:
            unmatched_covers.append((cover, f"no CCBDL row for W {key[0]} {key[1]}-00"))
            continue
        used_keys.add(key)
        # Duplicate -00 codes: prefer the first row (lowest vol/page) in a volume
        # that has delta data; report the losers.
        with_delta = [r for r in candidates if r.vol in deltas]
        chosen = with_delta[0] if with_delta else candidates[0]
        losers = [r for r in candidates if r is not chosen]
        if losers:
            duplicates_resolved.append((f"W {key[0]} {key[1]}-00", chosen, losers))
        loc = apply_delta(chosen.vol, chosen.pg, deltas)
        if loc is None:
            no_delta_matches.append((cover, chosen))
            continue
        body_page, extrapolated = loc
        matches.append((cover, chosen, body_page, extrapolated, losers))

    matches.sort(key=lambda m: (m[1].vol, m[2]))

    print("== COVER_LOCATIONS (paste into barks_covers.py) ==")
    print("COVER_LOCATIONS: dict[CoverKey, tuple[int, int]] = {")
    for cover, row, body_page, extrapolated, losers in matches:
        key_str = (
            f'("{cover.series_name}", {cover.issue_number}, {cover.issue_year},'
            f' "{cover.kind.name}", {cover.seq})'
        )
        comments = []
        if extrapolated:
            comments.append("page offset extrapolated - verify")
        comments.extend(f"also reprinted in vol {r.vol} p{r.pg}{r.pg_suffix}" for r in losers)
        comment = f"  # {'; '.join(comments)}" if comments else ""
        print(f"    {key_str}: ({row.vol}, {body_page}),{comment}")
    print("}")

    print(f"\n== BARKS_COVERS front covers with no CCBDL -00 row ({len(unmatched_covers)}) ==")
    for cover, reason in unmatched_covers:
        print(f"  {cover_desc(cover)}: {reason}")

    unused = sorted(
        (key for key in front_rows if key not in used_keys),
        key=lambda k: (front_rows[k][0].vol, front_rows[k][0].pg),
    )
    print(f"\n== CCBDL -00 rows matching no BarksCover ({len(unused) + len(unkeyed_00_rows)}) ==")
    for key in unused:
        for row in front_rows[key]:
            print(f"  {row}")
    for row in unkeyed_00_rows:
        print(f"  {row} (non-simple code)")

    print(f"\n== Duplicate -00 codes resolved ({len(duplicates_resolved)}) ==")
    for code, chosen, losers in duplicates_resolved:
        print(f"  {code}: chose vol {chosen.vol} p{chosen.pg}; also {losers}")

    print(f"\n== INSIDE_FRONT / BACK covers - hand-assignment candidates ({len(non_front_covers)}) ==")
    for cover in non_front_covers:
        print(f"  {cover_desc(cover)}:")
        key = expected_pub_issue(cover)
        candidates = all_cover_rows_by_issue.get(key, []) if key else []
        candidates = [r for r in candidates if not r.code.endswith("-00")]
        if candidates:
            for row in candidates:
                loc = apply_delta(row.vol, row.pg, deltas)
                body = f" -> body page {loc[0]}{' (extrapolated)' if loc[1] else ''}" if loc else ""
                print(f"    candidate: {row}{body}")
        else:
            print("    no non-front illustration rows for this issue")

    print(f"\n== CCBDL matches skipped: volume has no delta data ({len(no_delta_matches)}) ==")
    for cover, row in no_delta_matches:
        print(f"  {cover_desc(cover)} matched {row}")

    print(f"\nSummary: {len(matches)} located of {len(BARKS_COVERS)} covers")


if __name__ == "__main__":
    main()
