#!/usr/bin/env python3
# ruff: noqa: T201

"""Add new tags to barks_tags.py from an input file.

Usage:
    python scripts/add_tags.py <input_file> [--dry-run]

Input format — whitespace-separated, one entry per line:
    "tag term"  TITLES_ENUM_NAME  page_number  [extra fields ignored ...]

  - Lines starting with '#' and blank lines are ignored.
  - page_number: integer; use -1 to update only BARKS_TAGGED_TITLES (no page entry).
  - Extra fields after the third are silently ignored (useful for keeping notes).
  - If a Tags enum member already exists (matched by string value or derived name),
    the enum step is skipped with a warning; BARKS_TAGGED_TITLES and
    BARKS_TAGGED_PAGES are still updated using the existing enum name.
  - Duplicate titles or pages produce a warning and are skipped.
  - New Tags enum members are inserted in alphabetical order.
  - New BARKS_TAGGED_TITLES entries are inserted in alphabetical order by tag name.
  - New BARKS_TAGGED_PAGES entries are inserted in alphabetical order by (tag, title).

Example input file:
    # New chemistry tags
    "copper trail"  GOLD_FINDER_THE   1  nice opening panel
    "copper trail"  ONLY_A_POOR_OLD_MAN  8
    "new element"   SOME_STORY       -1  title-level tag only
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

import typer

_REPO_ROOT = Path(__file__).resolve().parent.parent

BARKS_TAGS_FILE = _REPO_ROOT / "src/barks-fantagraphics/src/barks_fantagraphics/barks_tags.py"
BARKS_TITLES_FILE = _REPO_ROOT / "src/barks-fantagraphics/src/barks_fantagraphics/barks_titles.py"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def tag_term_to_enum_name(tag_term: str) -> str:
    """Convert a human-readable tag term to a candidate Tags enum member name.

    Examples:
        "copper trail"  -> "COPPER_TRAIL"
        "Barks' Picks"  -> "BARKS_PICKS"
        "Indo-China"    -> "INDO_CHINA"
        "P.J.McBrine"   -> "PJMCBRINE"

    """
    name = tag_term.lower()
    name = re.sub(r"['\u2019\".]", "", name)  # remove apostrophes, quotes, dots
    name = re.sub(r"[^a-z0-9]+", "_", name)  # non-alnum runs -> underscore
    return name.strip("_").upper()


def parse_input_file(path: Path) -> list[tuple[str, str, int]]:
    """Return list of (tag_term, title_enum_name, page) tuples.

    page is -1 if BARKS_TAGGED_PAGES should not be updated.
    """
    entries: list[tuple[str, str, int]] = []
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^"([^"]+)"\s+([A-Z_][A-Z0-9_]*)\s+(-?\d+)', line)
        if not m:
            print(f"WARNING line {lineno}: cannot parse: {raw!r}", file=sys.stderr)
            continue
        entries.append((m.group(1), m.group(2), int(m.group(3))))
    return entries


def known_title_enums(titles_file: Path) -> set[str]:
    """Return the set of all Titles enum member names."""
    content = titles_file.read_text()
    # Titles enum members are indented with 4 spaces
    return set(re.findall(r"^    ([A-Z_][A-Z0-9_]*) = ", content, re.MULTILINE))


# ---------------------------------------------------------------------------
# File modifier
# ---------------------------------------------------------------------------


class BarkTagsModifier:
    """Reads barks_tags.py and applies targeted in-memory edits before writing."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._original = path.read_text()
        self.lines: list[str] = self._original.splitlines(keepends=True)

    # ------------------------------------------------------------------ #
    # Tags enum                                                            #
    # ------------------------------------------------------------------ #

    def resolve_enum_name(self, tag_term: str, derived_name: str) -> tuple[str, bool]:
        """Return (enum_name, already_exists) for the given tag_term.

        Searches within class Tags(Enum) for an existing member whose string
        value matches tag_term (preferred), or whose name matches derived_name.
        If neither is found, returns (derived_name, False).
        """
        in_enum = False
        for line in self.lines:
            s = line.rstrip()
            if s == "class Tags(Enum):":
                in_enum = True
                continue
            if in_enum:
                if s and not s.startswith(" "):
                    break  # left the class body
                m = re.match(r"    ([A-Z_][A-Z0-9_]*) = ", s)
                if m:
                    existing_name = m.group(1)
                    # Check by string value first
                    vm = re.match(r'    ([A-Z_][A-Z0-9_]*) = "(.+)"', s)
                    if vm and vm.group(2) == tag_term:
                        return existing_name, True
                    # Check by derived enum name
                    if existing_name == derived_name:
                        return derived_name, True
        return derived_name, False

    def add_enum_member(self, enum_name: str, tag_term: str) -> None:
        """Insert a new Tags enum member at the alphabetically correct position."""
        idx = self._alphabetical_insert_idx(enum_name)
        self.lines.insert(idx, f'    {enum_name} = "{tag_term}"\n')
        print(f'  + Tags.{enum_name} = "{tag_term}"')

    def _tags_enum_members(self) -> list[tuple[str, int]]:
        """Return (enum_name, line_idx) for each member in class Tags(Enum)."""
        members: list[tuple[str, int]] = []
        in_enum = False
        for i, line in enumerate(self.lines):
            s = line.rstrip()
            if s == "class Tags(Enum):":
                in_enum = True
                continue
            if in_enum:
                if s and not s.startswith(" "):
                    break
                m = re.match(r"    ([A-Z_][A-Z0-9_]*) = ", s)
                if m:
                    members.append((m.group(1), i))
        return members

    def _alphabetical_insert_idx(self, new_name: str) -> int:
        """Return the line index at which to insert new_name for alphabetical order."""
        members = self._tags_enum_members()
        for name, idx in members:
            if name > new_name:
                return idx  # insert before the first member that sorts after us
        if members:
            return members[-1][1] + 1  # append after the last member
        msg = "Tags enum has no members"
        raise RuntimeError(msg)

    # ------------------------------------------------------------------ #
    # BARKS_TAGGED_TITLES                                                  #
    # ------------------------------------------------------------------ #

    def add_title_to_tagged_titles(self, enum_name: str, title_enum: str) -> None:
        """Add title_enum to the BARKS_TAGGED_TITLES entry for enum_name."""
        ts, te = self._dict_bounds("BARKS_TAGGED_TITLES")
        es, ee = self._list_entry(f"Tags.{enum_name}", ts, te)
        title_ref = f"Titles.{title_enum}"
        tag_ref = f"Tags.{enum_name}"

        if es == -1:
            # Brand-new tag — insert alphabetically by enum name
            idx = self._tagged_titles_insert_idx(enum_name, ts, te)
            self.lines.insert(idx, f"    {tag_ref}: [{title_ref}],\n")
            print(f"  + BARKS_TAGGED_TITLES: {tag_ref}: [{title_ref}]")
            return

        block = "".join(self.lines[es : ee + 1])
        if title_ref in block:
            print(f"  WARNING: {title_ref} already listed under {tag_ref}, skipping")
            return

        if es == ee:
            # Single-line entry — convert to multi-line and append the new title
            m = re.match(r"(\s+\S+:\s*\[)(.*?)(\],\s*)$", self.lines[es])
            if not m:
                print(
                    f"  WARNING: cannot parse single-line entry for {tag_ref}",
                    file=sys.stderr,
                )
                return
            existing = [t.strip() for t in m.group(2).split(",") if t.strip()]
            existing.append(title_ref)
            new_lines = [f"    {tag_ref}: [\n"]
            new_lines += [f"        {t},\n" for t in existing]
            new_lines.append("    ],\n")
            self.lines[es : es + 1] = new_lines
        else:
            # Multi-line — insert just before the closing ],
            self.lines.insert(ee, f"        {title_ref},\n")
        print(f"  + BARKS_TAGGED_TITLES: {tag_ref} += {title_ref}")

    # ------------------------------------------------------------------ #
    # BARKS_TAGGED_PAGES                                                   #
    # ------------------------------------------------------------------ #

    def add_page_to_tagged_pages(self, enum_name: str, title_enum: str, page: int) -> None:
        """Add page to the BARKS_TAGGED_PAGES entry for (enum_name, title_enum)."""
        ps, pe = self._dict_bounds("BARKS_TAGGED_PAGES")
        key_ref = f"(Tags.{enum_name}, Titles.{title_enum})"
        key_prefix = f"    {key_ref}:"
        page_str = f'"{page}"'

        for i in range(ps, pe):
            if self.lines[i].startswith(key_prefix):
                line = self.lines[i].rstrip()
                if page_str in line:
                    print(f"  WARNING: page {page_str} already in {key_ref}, skipping")
                    return
                if line.endswith("],"):
                    # Single-line — append page inline
                    prefix = line[: -len("],")]
                    self.lines[i] = f"{prefix}, {page_str}],\n"
                else:
                    # Multi-line — find the ], and insert before it
                    for j in range(i + 1, pe + 1):
                        if self.lines[j].strip() == "],":
                            existing_block = "".join(self.lines[i:j])
                            if page_str in existing_block:
                                print(f"  WARNING: page {page_str} already in {key_ref}, skipping")
                                return
                            self.lines.insert(j, f"        {page_str},\n")
                            break
                print(f"  + BARKS_TAGGED_PAGES: {key_ref} += {page_str}")
                return

        # Key not found — insert alphabetically by (tag, title)
        idx = self._tagged_pages_insert_idx(enum_name, title_enum, ps, pe)
        self.lines.insert(idx, f"    {key_ref}: [{page_str}],\n")
        print(f"  + BARKS_TAGGED_PAGES: {key_ref}: [{page_str}]")

    # ------------------------------------------------------------------ #
    # Internals                                                            #
    # ------------------------------------------------------------------ #

    def _tagged_titles_insert_idx(self, enum_name: str, dict_start: int, dict_end: int) -> int:
        """Return the line index for alphabetical insertion in BARKS_TAGGED_TITLES.

        Scans for the first entry whose tag name sorts after enum_name and
        returns that line index.  Falls back to dict_end (before closing })
        if enum_name sorts last.
        """
        for i in range(dict_start, dict_end):
            m = re.match(r"    Tags\.([A-Z_][A-Z0-9_]*):", self.lines[i])
            if m and m.group(1) > enum_name:
                return i
        return dict_end

    def _tagged_pages_insert_idx(
        self, enum_name: str, title_enum: str, dict_start: int, dict_end: int
    ) -> int:
        """Return the line index for alphabetical insertion in BARKS_TAGGED_PAGES.

        Sorts by (tag_name, title_name) and returns the index of the first
        entry that sorts after the new key.  Falls back to dict_end if the
        new key sorts last.
        """
        for i in range(dict_start, dict_end):
            m = re.match(
                r"    \(Tags\.([A-Z_][A-Z0-9_]*), Titles\.([A-Z_][A-Z0-9_]*)\):",
                self.lines[i],
            )
            if m and (m.group(1), m.group(2)) > (enum_name, title_enum):
                return i
        return dict_end

    def _dict_bounds(self, dict_name: str) -> tuple[int, int]:
        """Return (start_idx, closing_brace_idx) for a named top-level dict."""
        start = next(
            (i for i, ln in enumerate(self.lines) if ln.startswith(f"{dict_name}:")),
            -1,
        )
        if start == -1:
            msg = f"Cannot find {dict_name}"
            raise RuntimeError(msg)
        depth = 0
        for i in range(start, len(self.lines)):
            depth += self.lines[i].count("{") - self.lines[i].count("}")
            if depth == 0 and i > start:
                return start, i
        msg = f"Cannot find closing brace of {dict_name}"
        raise RuntimeError(msg)

    def _list_entry(self, key_str: str, dict_start: int, dict_end: int) -> tuple[int, int]:
        """Find (start_line, end_line) for 'key_str: [...],' within a dict.

        Returns (-1, -1) if not found.
        For single-line entries start == end.
        For multi-line entries, end is the line containing the closing ],
        """
        prefix = f"    {key_str}:"
        for i in range(dict_start, dict_end):
            if self.lines[i].startswith(prefix):
                line = self.lines[i].rstrip()
                if line.endswith("],") or "[" not in line:
                    # Single-line list, or a non-list value (e.g. NON_COMIC_TITLES)
                    return i, i
                # Multi-line list — find the matching ],
                for j in range(i + 1, dict_end + 1):
                    if self.lines[j].strip() == "],":
                        return i, j
                msg = f"Cannot find closing ], for {key_str}"
                raise RuntimeError(msg)
        return -1, -1

    # ------------------------------------------------------------------ #
    # Output                                                               #
    # ------------------------------------------------------------------ #

    def unified_diff(self) -> list[str]:
        """Return a unified diff of original vs current in-memory state."""
        return list(
            difflib.unified_diff(
                self._original.splitlines(keepends=True),
                self.lines,
                fromfile=f"{self.path.name} (original)",
                tofile=f"{self.path.name} (modified)",
            )
        )

    def save(self) -> None:
        """Write the modified content back to disk."""
        self.path.write_text("".join(self.lines))
        print(f"\nSaved: {self.path}")


# ---------------------------------------------------------------------------
# Per-entry processing
# ---------------------------------------------------------------------------


def process_entry(
    modifier: BarkTagsModifier,
    seen_enums: set[str],
    tag_term: str,
    title_enum: str,
    page: int,
) -> None:
    """Apply one input-file entry to the in-memory modifier."""
    derived = tag_term_to_enum_name(tag_term)
    enum_name, already_exists = modifier.resolve_enum_name(tag_term, derived)

    desc = f'"{tag_term}" -> Tags.{enum_name}, Titles.{title_enum}'
    if page >= 0:
        desc += f", p.{page}"
    print(f"\n{desc}")

    if enum_name not in seen_enums:
        seen_enums.add(enum_name)
        if already_exists:
            print(f"  WARNING: Tags.{enum_name} already exists, skipping enum step")
        else:
            modifier.add_enum_member(enum_name, tag_term)

    modifier.add_title_to_tagged_titles(enum_name, title_enum)

    if page >= 0:
        modifier.add_page_to_tagged_pages(enum_name, title_enum, page)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(
    input_file: Path = typer.Argument(..., help="Input file with tag entries"),  # noqa: B008
    dry_run: bool = typer.Option(
        default=False,
        help="Print a unified diff of changes without writing the file",
    ),
) -> None:
    """Add new tags to barks_tags.py from an input file."""
    if not input_file.exists():
        typer.echo(f"ERROR: input file not found: {input_file}", err=True)
        raise typer.Exit(1)

    entries = parse_input_file(input_file)
    if not entries:
        typer.echo("No valid entries found in input file.", err=True)
        raise typer.Exit(1)

    # Validate all title enum names up front before touching any file
    known = known_title_enums(BARKS_TITLES_FILE)
    unknown = sorted({t for _, t, _ in entries if t not in known})
    if unknown:
        for t in unknown:
            print(f"ERROR: Unknown Titles enum member: {t}", file=sys.stderr)
        raise typer.Exit(1)

    modifier = BarkTagsModifier(BARKS_TAGS_FILE)
    seen_enums: set[str] = set()

    for tag_term, title_enum, page in entries:
        process_entry(modifier, seen_enums, tag_term, title_enum, page)

    if dry_run:
        diff = modifier.unified_diff()
        if diff:
            sys.stdout.writelines(diff)
        else:
            print("\n(no changes)")
        print("\nDry-run: nothing written.")
    else:
        modifier.save()


if __name__ == "__main__":
    typer.run(main)
