#!/usr/bin/env python3
"""Check this machine's data pack against the one the main PC holds.

The overnight machines read copies of the main PC's data: the Reader Files folders,
the prebuilt comics and the PNG panels. Nothing re-syncs a copy when the data
changes there, and a stale copy passes the overnight run: the GUI tests derive what
they expect from the same data the app reads, and validate checks a prebuilt comic
only exists. In October 2026 three machines ran a month on a September search index
and on July's prebuilt comics, and no stage said so.

So the main PC records a fingerprint of each data folder - its file count, its total
size, and an md5 over every file's relative path and content - in a committed
manifest, ``scripts/data-manifest.json``, and each run recomputes them where it runs:

  uv run scripts/data_manifest.py --write   # on the main PC, after a data change;
                                            # then commit the manifest
  uv run scripts/data_manifest.py           # anywhere: compare with the manifest

The check names each folder that differs and exits 3 (the overnight run's WARNED);
0 when all match; 1 when the manifest or this machine's settings cannot be read. On
the main PC a difference means the data changed and ``--write`` was not run.

Each folder is found through this machine's own settings, so the layouts of Linux,
Windows and macOS all work: the Reader Files folders under BARKS_READER_DATA_DIR
(``.env.runtime``), the prebuilt comics and PNG panels where its barks-reader.ini
says (``prebuilt_dir``, ``png_barks_panels_dir``). The PNG panels are optional, as they
are to validate: a machine without them reads the panels zip, and only one that has
them is held to the manifest's. Backup folders beside them
(``Indexes-2026-03-25`` and the like) are not data and are not read. Neither are the
files a desktop leaves (``.DS_Store``, ``Thumbs.db``, ``desktop.ini``, ``._*``).

Hashing every file takes about a minute for the ~11 GB, so each file's md5 is kept
in ``build/data-manifest-cache.json`` (gitignored, this machine's own) under its
path, size and modified time, and hashed again only when one of those changes.

The same fingerprints version the data packs. ``scripts/build-data-zips.sh`` runs

  uv run scripts/data_manifest.py --write-pack-manifest OUT --version N --reader-files DIR

to write the ``Reader Files/data-pack.json`` it zips into both packs: data pack N
(the N of its data-vN release), built when and where, and the fingerprint of each
Reader Files folder under DIR (``core/data_pack.py`` reads the file; ``--list-entries``
prints the folders, so the build script packs the same list).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from configparser import ConfigParser
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from barks_reader.core.data_pack import pack_manifest_json
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = Path(__file__).with_name("data-manifest.json")
CACHE_PATH = REPO_ROOT / "build" / "data-manifest-cache.json"
DIFFER_EXIT = 3

# The folders the app reads under Reader Files (core/system_file_paths.py), and its panels zip.
READER_FILES_ENTRIES = (
    "Barks Panels.zip",
    "Carl Barks Wiki",
    "Fantagraphics Volumes Overrides",
    "Fantagraphics-panel-segments",
    "Indexes",
    "Reader Icons",
    "Statistics",
    "Various",
)
PREBUILT_ENTRY = "prebuilt comics"
PNG_PANELS_ENTRY = "PNG panels"
# Read where a machine has them (validate and the GUI tests then use them too), and not
# missed where it does not: the Windows and macOS machines read the panels zip only.
OPTIONAL_ENTRIES = frozenset({PNG_PANELS_ENTRY})
_DESKTOP_LITTER = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
_CHUNK = 1 << 20

Cache = dict[str, list]  # absolute path -> [size, mtime_ns, md5]


@dataclass(frozen=True)
class Fingerprint:
    """What a data folder (or a single data file) holds."""

    files: int
    bytes: int
    md5: str


def _is_litter(name: str) -> bool:
    return name in _DESKTOP_LITTER or name.startswith("._")


def _data_files(root: Path) -> list[tuple[str, Path]]:
    """Each data file under `root` (or `root` itself, a file), by relative posix path, sorted."""
    if root.is_file():
        return [(root.name, root)]
    found = [
        (path.relative_to(root).as_posix(), path)
        for path in root.rglob("*")
        if path.is_file() and not _is_litter(path.name)
    ]
    return sorted(found)


def _file_md5(path: Path, size: int, mtime_ns: int, cache: Cache) -> str:
    key = str(path)
    cached = cache.get(key)
    if cached is not None and cached[0] == size and cached[1] == mtime_ns:
        return cached[2]
    digest = hashlib.md5()  # noqa: S324 - a fingerprint, not security
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK):
            digest.update(chunk)
    cache[key] = [size, mtime_ns, digest.hexdigest()]
    return digest.hexdigest()


def fingerprint(root: Path, cache: Cache) -> Fingerprint | None:
    """Fingerprint a data folder or file; None when it is not there.

    Args:
        root: The folder (or single file) to fingerprint.
        cache: File md5s by path, reused while a file's size and modified time hold;
            updated in place.

    Returns:
        Its file count, total size, and an md5 over each file's relative path and
        md5, in path order - so a renamed, added, removed or edited file changes it,
        however the folder was copied.

    """
    if not root.exists():
        return None
    total = 0
    combined = hashlib.md5()  # noqa: S324 - a fingerprint, not security
    files = _data_files(root)
    for rel, path in files:
        stat = path.stat()
        total += stat.st_size
        md5 = _file_md5(path, stat.st_size, stat.st_mtime_ns, cache)
        combined.update(f"{rel}\0{md5}\n".encode())
    return Fingerprint(files=len(files), bytes=total, md5=combined.hexdigest())


def data_roots() -> dict[str, Path | None]:
    """Where this machine keeps each data entry, from its env and barks-reader.ini.

    Returns:
        Each entry's path, or None for a setting this machine does not have.

    """
    load_dotenv(REPO_ROOT / ".env.runtime")
    # After the env is loaded: config_info reads BARKS_READER_* when it is constructed.
    from barks_reader.core.config_info import ConfigInfo  # noqa: PLC0415
    from barks_reader.core.reader_file_paths import ReaderFilePaths  # noqa: PLC0415
    from barks_reader.core.reader_settings import (  # noqa: PLC0415
        PNG_BARKS_PANELS_DIR,
        PREBUILT_COMICS_DIR,
        READER_FILES_DIR,
        read_setting_from_config,
    )

    cfg_info = ConfigInfo()
    reader_files = cfg_info.app_data_dir / READER_FILES_DIR
    roots: dict[str, Path | None] = {name: reader_files / name for name in READER_FILES_ENTRIES}

    config = ConfigParser()
    config.read(cfg_info.app_config_path)
    try:
        roots[PREBUILT_ENTRY] = Path(read_setting_from_config(config, PREBUILT_COMICS_DIR))
    except Exception:  # noqa: BLE001 - an ini without it reads the app's default, as validate does
        roots[PREBUILT_ENTRY] = ReaderFilePaths.get_default_prebuilt_comic_zips_dir()
    try:
        roots[PNG_PANELS_ENTRY] = Path(read_setting_from_config(config, PNG_BARKS_PANELS_DIR))
    except Exception:  # noqa: BLE001 - no PNG panels setting: reported as missing
        roots[PNG_PANELS_ENTRY] = None
    return roots


def reader_files_fingerprints(reader_files: Path, cache: Cache) -> dict[str, Fingerprint | None]:
    """Fingerprint each Reader Files entry under `reader_files`; None for one not there."""
    return {name: fingerprint(reader_files / name, cache) for name in READER_FILES_ENTRIES}


def write_pack_manifest(out: Path, version: int, reader_files: Path, cache: Cache) -> list[str]:
    """Write the version file the data packs carry.

    Args:
        out: Where to write it (the build script zips it in as Reader Files/data-pack.json).
        version: The pack's number, the N of its data-vN release.
        reader_files: The Reader Files folder the packs are made from.
        cache: File md5s by path, as `fingerprint` takes.

    Returns:
        The entries missing under `reader_files`; nothing is written unless empty.

    """
    found = reader_files_fingerprints(reader_files, cache)
    missing = [name for name, fp in found.items() if fp is None]
    if missing:
        return missing
    entries = {name: asdict(fp) for name, fp in found.items() if fp is not None}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        pack_manifest_json(
            version, f"data-v{version}", datetime.now(UTC), platform.node(), entries
        ),
        encoding="utf-8",
    )
    return []


def fingerprints(roots: dict[str, Path | None], cache: Cache) -> dict[str, Fingerprint | None]:
    """Fingerprint every entry; None for one that is not on this machine."""
    return {
        name: None if root is None else fingerprint(root, cache)
        for name, root in sorted(roots.items())
    }


def manifest_json(found: dict[str, Fingerprint | None], host: str, when: datetime) -> str:
    """Return the manifest as written: who wrote it, when, and each entry's fingerprint."""
    entries = {name: None if fp is None else asdict(fp) for name, fp in found.items()}
    written_at = when.isoformat(timespec="seconds")
    body = {"written_on": host, "written_at": written_at, "entries": entries}
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def compare(manifest: dict, found: dict[str, Fingerprint | None]) -> list[str]:
    """Each difference between the manifest and this machine, as a line to print.

    Args:
        manifest: The parsed manifest.
        found: This machine's fingerprints.

    Returns:
        One line per entry that differs: missing here, not in the manifest, or
        holding other files. Empty when all match. An optional entry this machine
        does not have is no difference.

    """
    expected: dict[str, dict | None] = manifest["entries"]
    lines = []
    for name in sorted(set(expected) | set(found)):
        want = expected.get(name)
        have = found.get(name)
        if name not in expected:
            lines.append(f"{name}: here, but not in the manifest")
        elif have is None and want is not None and name not in OPTIONAL_ENTRIES:
            lines.append(f"{name}: MISSING here (expected {_describe(want)})")
        elif have is not None and want is None:
            source = manifest["written_on"]
            lines.append(f"{name}: here ({_describe(asdict(have))}), absent on {source}")
        elif have is not None and want is not None and asdict(have) != want:
            here = _describe(asdict(have))
            lines.append(f"{name}: DIFFERS - here {here}, expected {_describe(want)}")
    return lines


def _describe(fields: dict) -> str:
    return f"{fields['files']:,} files, {fields['bytes'] / 1e6:,.1f} MB"


def _load_cache() -> Cache:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: Cache) -> None:
    CACHE_PATH.parent.mkdir(exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def main(argv: list[str] | None = None) -> int:
    """Write the manifest, or compare this machine with it; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write", action="store_true", help="record this machine's data as the manifest"
    )
    parser.add_argument(
        "--list-entries", action="store_true", help="print the Reader Files entries, one a line"
    )
    parser.add_argument(
        "--write-pack-manifest",
        metavar="OUT",
        type=Path,
        help="write the data packs' version file (with --version and --reader-files)",
    )
    parser.add_argument("--version", type=int, help="the pack's number, the N of data-vN")
    parser.add_argument(
        "--reader-files", type=Path, help="the Reader Files folder the packs are made from"
    )
    args = parser.parse_args(argv)

    if args.list_entries:
        print("\n".join(READER_FILES_ENTRIES))  # noqa: T201
        return 0
    if args.write_pack_manifest is not None:
        if args.version is None or args.reader_files is None:
            parser.error("--write-pack-manifest needs --version and --reader-files")
        return _write_pack_manifest(args.write_pack_manifest, args.version, args.reader_files)
    return _write_or_compare(write=args.write)


def _write_or_compare(*, write: bool) -> int:
    try:
        roots = data_roots()
    except Exception as exc:  # noqa: BLE001 - say why, rather than a traceback, in the run's log
        print(f"data: cannot read this machine's settings: {exc}")  # noqa: T201
        return 1
    cache = _load_cache()
    found = fingerprints(roots, cache)
    _save_cache(cache)

    if write:
        host = platform.node()
        MANIFEST_PATH.write_text(manifest_json(found, host, datetime.now(UTC)), encoding="utf-8")
        print(f"data: wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} from {host}; commit it")  # noqa: T201
        return 0

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"data: cannot read {MANIFEST_PATH.name}: {exc}")  # noqa: T201
        return 1
    differences = compare(manifest, found)
    source = f"{manifest['written_on']} on {manifest['written_at']}"
    if not differences:
        print(f"data: every folder matches the manifest written by {source}")  # noqa: T201
        return 0
    print(f"data: differs from the manifest written by {source}:")  # noqa: T201
    for line in differences:
        print(f"  {line}")  # noqa: T201
    print("  copy those folders from the main PC; there, a difference means: run --write")  # noqa: T201
    return DIFFER_EXIT


def _write_pack_manifest(out: Path, version: int, reader_files: Path) -> int:
    cache = _load_cache()
    missing = write_pack_manifest(out, version, reader_files, cache)
    _save_cache(cache)
    if missing:
        print(f"data: not under {reader_files}: {', '.join(missing)}")  # noqa: T201
        return 1
    print(f"data: wrote {out} for data pack {version}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
