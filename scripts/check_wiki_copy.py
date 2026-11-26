#!/usr/bin/env python3
"""Check what Reader Files copies from barks-wiki: the wiki, and the illustrated history.

The reader shows the copy in ``<data dir>/Reader Files/Carl Barks Wiki`` unless
``use_live_wiki_bundle`` points it at the sibling ``barks-wiki`` repo, which is what
a developer machine does - so the validator, which checks the bundle the settings
select, never sees the copy users get. This checks that copy:

1. **Joins.** The validator's Phase 11 on the copy: a story page whose title does
   not match its story, or a story tied to two pages, is a broken join and fails.
2. **Staleness.** barks-wiki's own ``scripts/export_reader_wiki.py`` builds the copy
   (a copyright-free subset, its dead links rewritten), so the copy differs from
   the live bundle by design. The honest comparison is with what that export
   makes from the live bundle today: it is run into a temporary directory and the
   copy compared with it, file by file. A difference is only a note: the wiki is a
   work in progress, so its copy is expected to fall behind between data packs.
   barks-wiki is read-only from here: the export only reads it (``python -B``: not
   even bytecode is written), and writes to the temp dir.

3. **The illustrated history.** Its chapters are copied by hand from barks-wiki's
   ``illustrated-history/reader`` folder (all but the PDFs beside them), so the
   copy in ``Various/documents/illustrated-history`` is compared with that folder
   file by file. A difference fails: nothing else says a chapter was made again
   and not copied. The folder is not in barks-wiki's git, so a machine without it
   (every machine but the one the chapters are made on) skips this.

Exits 1 when a join is broken or the illustrated history differs, otherwise 0; a
missing barks-wiki skips steps 2 and 3.

With ``--strict``, which ``build-data-zips.sh`` uses so that each pack ships the wiki as
it stands, it also exits 3 when the copy is stale and 1 when it cannot tell.
"""

from __future__ import annotations

import argparse
import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

from barks_reader.core.reader_settings import READER_FILES_DIR, WIKI_BUNDLE_SUBDIR
from barks_reader.core.system_file_paths import SystemFilePaths
from validate_barks_reader_core import ErrorCollector, phase1_config, phase11_wiki

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_REPO = REPO_ROOT.parent / "barks-wiki"
EXPORT_SCRIPT = WIKI_REPO / "scripts" / "export_reader_wiki.py"
HISTORY_SOURCE = WIKI_REPO / "illustrated-history" / "reader"
# Made beside the chapters for reading elsewhere; the reader shows the page images.
HISTORY_NOT_COPIED = frozenset({".pdf"})
STALE_EXIT = 3
_SHOWN = 10


def _files(root: Path, skip_suffixes: frozenset[str]) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() not in skip_suffixes
    }


def differences(
    copy: Path, fresh: Path, skip_suffixes: frozenset[str] = frozenset()
) -> dict[str, list[str]]:
    """Compare the shipped copy with a fresh export, by relative path.

    Args:
        copy: The Reader Files copy.
        fresh: What the export makes today.
        skip_suffixes: File types on either side that are not part of the copy.

    Returns:
        ``missing`` (in the export, not the copy), ``extra`` (the reverse) and
        ``changed`` paths, each sorted.

    """
    copy_files = _files(copy, skip_suffixes)
    fresh_files = _files(fresh, skip_suffixes)
    changed = [
        rel
        for rel in sorted(copy_files & fresh_files)
        if not filecmp.cmp(copy / rel, fresh / rel, shallow=False)
    ]
    return {
        "missing": sorted(fresh_files - copy_files),
        "extra": sorted(copy_files - fresh_files),
        "changed": changed,
    }


def report_staleness(found: dict[str, list[str]]) -> bool:
    """Print what differs, a few names per kind; return whether anything does."""
    total = sum(len(paths) for paths in found.values())
    if total == 0:
        print("wiki copy: current - it matches a fresh export of the live bundle")  # noqa: T201
        return False
    print(  # noqa: T201
        f"wiki copy: STALE - {len(found['changed'])} pages changed, {len(found['missing'])}"
        f" missing, {len(found['extra'])} no longer exported, against a fresh export;"
        f" refresh it with barks-wiki's scripts/export_reader_wiki.py"
    )
    for kind, paths in found.items():
        for path in paths[:_SHOWN]:
            print(f"  {kind:8s} {path}")  # noqa: T201
        if len(paths) > _SHOWN:
            print(f"  {kind:8s} ... and {len(paths) - _SHOWN} more")  # noqa: T201
    return True


def history_is_stale(copy: Path, source: Path = HISTORY_SOURCE) -> bool:
    """Compare the illustrated history's copy with barks-wiki's folder; print what differs.

    Args:
        copy: The Reader Files copy of the chapters.
        source: The folder the chapters are made in.

    Returns:
        Whether the copy differs. False, with a line saying so, where there is no
        source folder to compare with.

    """
    if not source.is_dir():
        print(f"illustrated history: no {source} - not checked")  # noqa: T201
        return False
    found = differences(copy, source, HISTORY_NOT_COPIED)
    total = sum(len(paths) for paths in found.values())
    if total == 0:
        print(f"illustrated history: current - it matches {source}")  # noqa: T201
        return False
    print(  # noqa: T201
        f"illustrated history: STALE - {len(found['changed'])} files changed,"
        f" {len(found['missing'])} missing, {len(found['extra'])} no longer there, against"
        f" {source}; copy its chapter folders (not the PDFs) to {copy}"
    )
    for kind, paths in found.items():
        for path in paths[:_SHOWN]:
            print(f"  {kind:8s} {path}")  # noqa: T201
        if len(paths) > _SHOWN:
            print(f"  {kind:8s} ... and {len(paths) - _SHOWN} more")  # noqa: T201
    return True


def _history_copy(reader_files: Path) -> Path:
    sys_paths = SystemFilePaths()
    sys_paths.set_barks_reader_files_dir(reader_files, check_files=False)
    return sys_paths.get_illustrated_history_doc_dir()


def fresh_export(dest: Path) -> bool:
    """Export the live bundle into `dest` with barks-wiki's own script; False if it cannot."""
    if not EXPORT_SCRIPT.is_file():
        print(f"wiki copy: no {EXPORT_SCRIPT} - staleness not checked")  # noqa: T201
        return False
    result = subprocess.run(  # noqa: S603 - our own interpreter on a known script
        [sys.executable, "-B", str(EXPORT_SCRIPT), str(dest), "--apply"],
        cwd=WIKI_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"wiki copy: the export failed - staleness not checked:\n{result.stderr}")  # noqa: T201
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Check the wiki copy's joins and staleness, then the history; return the exit status."""
    parser = argparse.ArgumentParser(description="Check what Reader Files copies from barks-wiki.")
    parser.add_argument(
        "--strict", action="store_true", help="fail unless the copy is known to be current"
    )
    strict = parser.parse_args(argv).strict

    collector = ErrorCollector()
    cfg_info = phase1_config(collector, None, None)
    if cfg_info is None:
        return 1
    reader_files = cfg_info.app_data_dir / READER_FILES_DIR
    copy = reader_files / WIKI_BUNDLE_SUBDIR
    phase11_wiki(collector, copy if (copy / "index.md").is_file() else None)
    joins_broken = collector.any_failed

    with tempfile.TemporaryDirectory(prefix="wiki-export-") as tmp:
        fresh = Path(tmp) / "okf"
        exported = fresh_export(fresh)
        stale = exported and report_staleness(differences(copy, fresh))

    history_stale = history_is_stale(_history_copy(reader_files))

    if joins_broken:
        print(f"wiki copy: joins broken in {copy}")  # noqa: T201
        return 1
    if history_stale:
        return 1
    if not strict:
        if stale:
            print("wiki copy: a note only; it is refreshed when a data pack is built")  # noqa: T201
        return 0
    if not exported:
        print("wiki copy: cannot tell whether it is current")  # noqa: T201
        return 1
    return STALE_EXIT if stale else 0


if __name__ == "__main__":
    sys.exit(main())
