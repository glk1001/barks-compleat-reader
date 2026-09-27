#!/usr/bin/env python3
"""Check the wiki copy shipped in Reader Files: its joins, and whether it is stale.

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
   copy compared with it, file by file. A difference means the copy needs
   refreshing (re-run the export into Reader Files), a warning rather than a
   failure. barks-wiki is read-only from here: the export only reads it
   (``python -B``: not even bytecode is written), and writes to the temp dir.

Exits 1 when a join is broken, 3 when the copy is stale but its joins hold (the
overnight run's WARNED), 0 when it is current; a missing barks-wiki skips step 2.
"""

from __future__ import annotations

import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

from barks_reader.core.reader_settings import READER_FILES_DIR, WIKI_BUNDLE_SUBDIR
from validate_barks_reader_core import ErrorCollector, phase1_config, phase11_wiki

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_REPO = REPO_ROOT.parent / "barks-wiki"
EXPORT_SCRIPT = WIKI_REPO / "scripts" / "export_reader_wiki.py"
STALE_EXIT = 3
_SHOWN = 10


def differences(copy: Path, fresh: Path) -> dict[str, list[str]]:
    """Compare the shipped copy with a fresh export, by relative path.

    Args:
        copy: The Reader Files copy.
        fresh: What the export makes today.

    Returns:
        ``missing`` (in the export, not the copy), ``extra`` (the reverse) and
        ``changed`` paths, each sorted.

    """
    copy_files = {p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file()}
    fresh_files = {p.relative_to(fresh).as_posix() for p in fresh.rglob("*") if p.is_file()}
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


def main() -> int:
    """Check the copy's joins, then its staleness; return the exit status."""
    collector = ErrorCollector()
    cfg_info = phase1_config(collector, None, None)
    if cfg_info is None:
        return 1
    copy = cfg_info.app_data_dir / READER_FILES_DIR / WIKI_BUNDLE_SUBDIR
    phase11_wiki(collector, copy if (copy / "index.md").is_file() else None)
    joins_broken = collector.any_failed

    with tempfile.TemporaryDirectory(prefix="wiki-export-") as tmp:
        fresh = Path(tmp) / "okf"
        stale = fresh_export(fresh) and report_staleness(differences(copy, fresh))

    if joins_broken:
        print(f"wiki copy: joins broken in {copy}")  # noqa: T201
        return 1
    return STALE_EXIT if stale else 0


if __name__ == "__main__":
    sys.exit(main())
