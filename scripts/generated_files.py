#!/usr/bin/env python3
"""Say when a generated file in Reader Files is older than what it was made from.

Some of the Reader's files are made from sources that live elsewhere: the how-to
pages from ``docs/how-to-use.md``, the introduction page from its markdown and art,
the Statistics screen's word table and word clouds from the search index. Edit a
source and nothing redoes the file: the how-to's pages lacked a button for days
after its text gained one, and every check passed.

So each such set is recorded in ``scripts/generated-files.json``, committed: a hash
of every source it was made from and of every file made. The corpus validator
(``validate-barks-reader-files.py``) compares both with what is there now and
reports a set as stale when a source has changed since, or the files are not the
ones recorded.

  uv run scripts/generated_files.py                    # compare; exit 1 when stale
  uv run scripts/generated_files.py --record how-to    # after regenerating: record
  uv run scripts/generated_files.py --record all       # ... every set
  uv run scripts/generated_files.py --list

``--record`` says "these files were made from these sources": run it only after the
set's generator (and, for the how-to, the image editor's export), then commit the
record. It is taken on trust; nothing here can redo a page to prove it.

A document's sources are its markdown, its stylesheet, every image the markdown
shows and every file the stylesheet loads, found by reading them: a picture added
to the text is a source from then on. The search index is one source, hashed whole.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from barks_reader.core.statistics_series import MOST_FREQUENT_FILE, WORDCLOUD_GLOB
from dotenv import load_dotenv

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD_PATH = Path(__file__).with_name("generated-files.json")

HOW_TO_MD = REPO_ROOT / "docs" / "how-to-use.md"
HOW_TO_CSS = REPO_ROOT / "scripts" / "how-to-style.css"
INTRO_MD = REPO_ROOT / "docs" / "intro-to-barks-reader.md"
INTRO_CSS = REPO_ROOT / "scripts" / "intro-style.css"
INTRO_BACKGROUND = REPO_ROOT / "docs" / "intro-to-barks-reader-bgnd.png"

HOW_TO = "how-to"
INTRODUCTION = "introduction"
WORD_STATISTICS = "word-statistics"
INDEX_SOURCE = "the search index"
# Written beside each word cloud by scripts/generate_tfidf_wordcloud.py.
RANKED_WORDS_GLOB = "tfidf_ranked_words_*.txt"

_SHOWN = 5
_CHUNK = 1 << 20
_DESKTOP_LITTER = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
_MD_IMAGE = re.compile(r"""<img\b[^>]*?\bsrc=["']([^"']+)["']|!\[[^\]]*\]\(([^)\s]+)""")
_CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""")
_REMOTE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)

type Hashes = dict[str, str]


class _Paths(Protocol):
    """What is asked of the app's `SystemFilePaths`."""

    def get_how_to_doc_dir(self) -> Path: ...
    def get_intro_doc_dir(self) -> Path: ...
    def get_statistics_dir(self) -> Path: ...
    def get_barks_reader_indexes_dir(self) -> Path: ...


@dataclass(frozen=True, slots=True)
class ReaderDirs:
    """The Reader Files folders the generated sets are in or made from."""

    how_to: Path
    intro: Path
    statistics: Path
    indexes: Path


@dataclass(frozen=True, slots=True)
class GeneratedSet:
    """One set of generated files: what it is made from, where it is, how to redo it."""

    name: str
    sources: Callable[[ReaderDirs], Hashes]
    outputs: Callable[[ReaderDirs], list[Path]]
    remake: str


def file_hash(path: Path) -> str:
    """Return the sha256 of a file's content."""
    digest = hashlib.sha256()
    with path.open("rb") as opened:
        while chunk := opened.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def folder_hash(root: Path) -> str:
    """Return one sha256 over every file under `root`: its relative path and content.

    Desktop litter (``.DS_Store`` and the like) is not data and is left out.
    """
    digest = hashlib.sha256()
    files = sorted(
        (path.relative_to(root).as_posix(), path)
        for path in root.rglob("*")
        if path.is_file() and path.name not in _DESKTOP_LITTER and not path.name.startswith("._")
    )
    for relative, path in files:
        digest.update(f"{relative}\0{file_hash(path)}\n".encode())
    return digest.hexdigest()


def _name(path: Path) -> str:
    """Name a source as the record does: from the repo's root, with forward slashes."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _referenced(text: str, pattern: re.Pattern[str], base: Path) -> list[Path]:
    found: list[Path] = []
    for match in pattern.finditer(text):
        target = next(group for group in match.groups() if group)
        if not _REMOTE.match(target):
            found.append(base / target.split("#")[0].split("?")[0])
    return found


def document_sources(md: Path, css: Path, *extras: Path) -> Hashes:
    """Hash everything a document's pages are drawn from.

    Args:
        md: The markdown. The images it shows are sources too, found beside it.
        css: The stylesheet. The files it loads (its fonts) are sources too.
        extras: Other files the generator reads (the introduction's background).

    Returns:
        Each source's name and hash. A source that is not there is named with the
        hash ``missing``, so losing one counts as a change.

    """
    files = [md, css, *extras]
    if md.is_file():
        files += _referenced(md.read_text(encoding="utf-8"), _MD_IMAGE, md.parent)
    if css.is_file():
        files += _referenced(css.read_text(encoding="utf-8"), _CSS_URL, css.parent)
    return {_name(path): file_hash(path) if path.is_file() else "missing" for path in files}


def _pages(folder: Path) -> list[Path]:
    return sorted(path for path in folder.glob("page-*") if path.is_file())


def _word_statistics_files(folder: Path) -> list[Path]:
    return sorted(
        [
            *folder.glob(MOST_FREQUENT_FILE),
            *folder.glob(WORDCLOUD_GLOB),
            *folder.glob(RANKED_WORDS_GLOB),
        ]
    )


def _index_source(dirs: ReaderDirs) -> Hashes:
    return {INDEX_SOURCE: folder_hash(dirs.indexes) if dirs.indexes.is_dir() else "missing"}


GENERATED_SETS: tuple[GeneratedSet, ...] = (
    GeneratedSet(
        HOW_TO,
        lambda _dirs: document_sources(HOW_TO_MD, HOW_TO_CSS),
        lambda dirs: _pages(dirs.how_to),
        "scripts/generate_how_to_pages.py, then the image editor's export",
    ),
    GeneratedSet(
        INTRODUCTION,
        lambda _dirs: document_sources(INTRO_MD, INTRO_CSS, INTRO_BACKGROUND),
        lambda dirs: _pages(dirs.intro),
        "scripts/generate_intro_page.py --output-dir <the introduction's folder>",
    ),
    GeneratedSet(
        WORD_STATISTICS,
        _index_source,
        lambda dirs: _word_statistics_files(dirs.statistics),
        "scripts/generate_stats_images.py --indexes-dir, and scripts/generate_tfidf_wordcloud.py",
    ),
)


def current(generated: GeneratedSet, dirs: ReaderDirs) -> dict[str, Hashes]:
    """Hash a set's sources and files as they are now, in the record's shape."""
    return {
        "sources": generated.sources(dirs),
        "outputs": {path.name: file_hash(path) for path in generated.outputs(dirs)},
    }


def _differing(recorded: Hashes, found: Hashes) -> str:
    """Name what differs between two sets of hashes, a few names at most."""
    names = sorted(
        name for name in recorded.keys() | found.keys() if recorded.get(name) != found.get(name)
    )
    shown = ", ".join(names[:_SHOWN])
    return shown if len(names) <= _SHOWN else f"{shown} and {len(names) - _SHOWN} more"


def stale_reasons(
    record: dict[str, dict[str, Hashes]],
    dirs: ReaderDirs,
    sets: tuple[GeneratedSet, ...] = GENERATED_SETS,
) -> list[str]:
    """Compare every set with the record; return a line for each thing that is stale.

    Args:
        record: The committed record (`load_record`).
        dirs: This machine's Reader Files folders.
        sets: The sets to check.

    Returns:
        One line per stale set and cause, naming what changed and how to redo it;
        empty when every set is as recorded.

    """
    reasons: list[str] = []
    for generated in sets:
        redo = (
            f"redo it ({generated.remake}), then"
            f" uv run scripts/generated_files.py --record {generated.name}"
        )
        recorded = record.get(generated.name)
        if recorded is None:
            reasons.append(f"{generated.name}: not in {RECORD_PATH.name}; {redo}")
            continue
        found = current(generated, dirs)
        if found["sources"] != recorded.get("sources"):
            changed = _differing(recorded.get("sources", {}), found["sources"])
            reasons.append(
                f"{generated.name} is stale: changed since it was made: {changed}; {redo}"
            )
        if found["outputs"] != recorded.get("outputs"):
            changed = _differing(recorded.get("outputs", {}), found["outputs"])
            reasons.append(
                f"{generated.name}: its files are not the ones recorded: {changed}; {redo}"
            )
    return reasons


def load_record(path: Path = RECORD_PATH) -> dict[str, dict[str, Hashes]]:
    """Read the committed record; an absent one records nothing."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def record_sets(
    names: list[str],
    dirs: ReaderDirs,
    path: Path = RECORD_PATH,
    sets: tuple[GeneratedSet, ...] = GENERATED_SETS,
) -> list[str]:
    """Record the named sets as they are now, leaving the others as they were.

    Args:
        names: The sets to record, or ``all``.
        dirs: This machine's Reader Files folders.
        path: The record to rewrite.
        sets: The sets there are.

    Returns:
        The names recorded.

    Raises:
        ValueError: A name is not a set's, or a set has no files to record.

    """
    by_name = {generated.name: generated for generated in sets}
    chosen = list(by_name) if "all" in names else names
    unknown = [name for name in chosen if name not in by_name]
    if unknown:
        msg = f"No such generated set: {', '.join(unknown)} (there are: {', '.join(by_name)})."
        raise ValueError(msg)

    record = load_record(path)
    for name in chosen:
        found = current(by_name[name], dirs)
        if not found["outputs"]:
            msg = f"{name}: no generated files found to record."
            raise ValueError(msg)
        record[name] = found
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return chosen


def reader_dirs() -> ReaderDirs:
    """Find this machine's Reader Files folders through its own settings."""
    load_dotenv(REPO_ROOT / ".env.runtime")
    # After the env is loaded: config_info reads BARKS_READER_* when it is constructed.
    from barks_reader.core.config_info import ConfigInfo  # noqa: PLC0415
    from barks_reader.core.reader_settings import READER_FILES_DIR  # noqa: PLC0415
    from barks_reader.core.system_file_paths import SystemFilePaths  # noqa: PLC0415

    sys_paths = SystemFilePaths()
    sys_paths.set_barks_reader_files_dir(
        ConfigInfo().app_data_dir / READER_FILES_DIR, check_files=False
    )
    return dirs_from(sys_paths)


def dirs_from(sys_paths: _Paths) -> ReaderDirs:
    """Take the folders from the app's own paths (a `SystemFilePaths`)."""
    return ReaderDirs(
        how_to=sys_paths.get_how_to_doc_dir(),
        intro=sys_paths.get_intro_doc_dir(),
        statistics=sys_paths.get_statistics_dir(),
        indexes=sys_paths.get_barks_reader_indexes_dir(),
    )


def main(argv: list[str] | None = None) -> int:
    """Compare the generated sets with the record, or record them; return the exit status."""
    parser = argparse.ArgumentParser(description="Check the Reader's generated files are current.")
    parser.add_argument("--record", nargs="+", metavar="SET", help="record these sets, or 'all'")
    parser.add_argument("--list", action="store_true", help="name the sets and stop")
    args = parser.parse_args(argv)

    if args.list:
        for generated in GENERATED_SETS:
            print(f"{generated.name}: {generated.remake}")  # noqa: T201
        return 0

    dirs = reader_dirs()
    if args.record:
        try:
            recorded = record_sets(args.record, dirs)
        except ValueError as error:
            print(error, file=sys.stderr)  # noqa: T201
            return 1
        print(f"Recorded {', '.join(recorded)} in {RECORD_PATH.name}: commit it.")  # noqa: T201
        return 0

    reasons = stale_reasons(load_record(), dirs)
    for reason in reasons:
        print(reason)  # noqa: T201
    if not reasons:
        print(f"All {len(GENERATED_SETS)} generated sets are as recorded.")  # noqa: T201
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
