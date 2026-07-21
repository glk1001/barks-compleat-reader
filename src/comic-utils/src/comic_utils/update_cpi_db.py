"""Update the bundled ``cpi.db`` 'All Items' CPI-U data from the U.S. BLS.

The inflation calculator (:func:`comic_utils.cpi_calculator.get_adjusted_usd`)
reads average annual CPI-U index values from the ``indexes`` table of
``cpi.db``, using the series ``CUUR0000SA0`` (All items in U.S. city average,
all urban consumers). The Bureau of Labor Statistics publishes fresh figures
monthly, so this module refreshes those "All Items" series in place from the
BLS bulk flat file.

Run it periodically to keep the calculator current::

    python -m comic_utils.update_cpi_db

or call it from code::

    result = update_cpi_db()
    print(result.latest_year)

Only the series contained in the BLS "All Items" file are rebuilt; every other
series already in ``cpi.db`` is left untouched (stale, but unused by the
calculator). The rebuild happens inside a temporary copy of the database and is
swapped into place atomically, so a failed or partial download can never
corrupt the working file.
"""

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CPI_DATABASE_PATH = Path(__file__).parent / "cpi.db"

# BLS bulk flat file holding every CPI-U "All Items" (item SA0) series, back to 1913.
BLS_ALL_ITEMS_URL = "https://download.bls.gov/pub/time.series/cu/cu.data.1.AllItems"

# BLS returns HTTP 403 to requests whose User-Agent is missing or looks like a
# library/bot default. A descriptive User-Agent with a contact email is required.
DEFAULT_USER_AGENT = "BarksReader-cpi-updater/1.0 (gregg.kay@gmail.com)"

# Series the calculator relies on; used as a post-update sanity check.
REFERENCE_SERIES = "CUUR0000SA0"

DOWNLOAD_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class UpdateResult:
    """Summary of a successful :func:`update_cpi_db` run.

    Attributes:
        db_path: The database file that was updated.
        series_updated: Number of distinct series rebuilt in ``indexes``.
        rows_written: Total observation rows inserted into ``indexes``.
        previous_latest_year: Latest year for ``REFERENCE_SERIES`` before the
            update, or ``None`` if the series was previously absent.
        latest_year: Latest year for ``REFERENCE_SERIES`` after the update.
        backup_path: Path to the backup of the pre-update database, or ``None``
            if no backup was kept.

    """

    db_path: Path
    series_updated: int
    rows_written: int
    previous_latest_year: int | None
    latest_year: int
    backup_path: Path | None


def download_all_items(
    url: str = BLS_ALL_ITEMS_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = DOWNLOAD_TIMEOUT_SECONDS,
) -> str:
    """Download the BLS 'All Items' flat file and return its text.

    Args:
        url: The BLS ``cu.data.*`` flat-file URL to fetch.
        user_agent: The ``User-Agent`` header to send. BLS rejects requests
            (HTTP 403) without a descriptive User-Agent containing a contact
            email.
        timeout: Socket timeout in seconds for the request.

    Returns:
        The decoded (UTF-8) contents of the file.

    Raises:
        urllib.error.HTTPError: If BLS rejects the request (e.g. 403).
        urllib.error.URLError: If the request otherwise fails (e.g. no network).

    """
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8")


def parse_index_rows(text: str) -> list[tuple[str, int, str, float]]:
    """Parse BLS flat-file text into ``indexes`` rows.

    The BLS format is tab-delimited with a header row; fields are padded with
    surrounding whitespace and lines use CRLF endings. Rows whose value is
    missing or non-numeric (e.g. suppressed observations) are skipped.

    Args:
        text: Raw contents of a BLS ``cu.data.*`` file.

    Returns:
        One ``(series_id, year, period, value)`` tuple per valid observation.

    """
    rows: list[tuple[str, int, str, float]] = []
    for line in text.splitlines()[1:]:  # skip the header row
        fields = line.split("\t")
        if len(fields) < 4:  # noqa: PLR2004 - series, year, period, value
            continue
        series_id = fields[0].strip()
        try:
            year = int(fields[1].strip())
            value = float(fields[3].strip())
        except ValueError:
            continue  # blank/suppressed value or malformed row
        rows.append((series_id, year, fields[2].strip(), value))
    return rows


def _latest_year(conn: sqlite3.Connection, series: str) -> int | None:
    """Return the most recent year present for ``series`` in ``indexes``."""
    cursor = conn.execute("SELECT MAX(year) FROM indexes WHERE series = ?", (series,))
    result = cursor.fetchone()
    return result[0] if result is not None else None


def _replace_series(conn: sqlite3.Connection, rows: list[tuple[str, int, str, float]]) -> int:
    """Delete and re-insert every series present in ``rows`` within ``indexes``.

    Args:
        conn: Open connection to the (temporary) database being rebuilt.
        rows: Parsed observation rows to write.

    Returns:
        The number of distinct series that were replaced.

    """
    series_ids = {row[0] for row in rows}
    conn.executemany(
        "DELETE FROM indexes WHERE series = ?",
        [(series_id,) for series_id in series_ids],
    )
    conn.executemany(
        "INSERT INTO indexes (series, year, period, value) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(series_ids)


def _verify_latest_year(latest_year: int | None, previous_latest: int | None) -> int:
    """Validate the rebuilt reference series and return its latest year.

    Args:
        latest_year: Latest year for the reference series after the rebuild.
        previous_latest: Latest year before the rebuild, if known.

    Returns:
        The validated ``latest_year``.

    Raises:
        ValueError: If the reference series is missing, or the new data ends
            earlier than the data it would replace.

    """
    if latest_year is None:
        msg = f"Reference series {REFERENCE_SERIES} missing after update"
        raise ValueError(msg)
    if previous_latest is not None and latest_year < previous_latest:
        msg = f"Refusing update: new data ends {latest_year}, older than existing {previous_latest}"
        raise ValueError(msg)
    return latest_year


def update_cpi_db(
    db_path: Path = CPI_DATABASE_PATH,
    *,
    url: str = BLS_ALL_ITEMS_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = DOWNLOAD_TIMEOUT_SECONDS,
    keep_backup: bool = True,
) -> UpdateResult:
    """Refresh the 'All Items' CPI-U data in ``cpi.db`` from the BLS.

    Downloads the latest BLS bulk data, rebuilds the affected series inside a
    temporary copy of the database, sanity-checks the result, then atomically
    swaps it into place. A failed download or verification never touches the
    working database.

    Args:
        db_path: Path to the ``cpi.db`` SQLite database to update.
        url: The BLS ``cu.data.*`` flat-file URL to fetch.
        user_agent: The ``User-Agent`` header to send (see
            :data:`DEFAULT_USER_AGENT`).
        timeout: Socket timeout in seconds for the download.
        keep_backup: If ``True``, copy the pre-update database to
            ``<name>.bak`` before swapping in the new file.

    Returns:
        An :class:`UpdateResult` describing what changed.

    Raises:
        FileNotFoundError: If ``db_path`` does not exist.
        urllib.error.URLError: If the download fails.
        ValueError: If the download yields no rows, or the rebuilt database
            fails verification (missing reference series, or data older than
            what it replaces).

    """
    if not db_path.is_file():
        msg = f'Database not found at: "{db_path}"'
        raise FileNotFoundError(msg)

    with sqlite3.connect(db_path) as source_conn:
        previous_latest = _latest_year(source_conn, REFERENCE_SERIES)

    rows = parse_index_rows(download_all_items(url, user_agent, timeout))
    if not rows:
        msg = "BLS download contained no parseable CPI rows"
        raise ValueError(msg)

    # Build the new database in a sibling temp file so the swap-in is atomic.
    fd, temp_name = tempfile.mkstemp(dir=db_path.parent, suffix=".cpi.tmp")
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(db_path, temp_path)
        with sqlite3.connect(temp_path) as conn:
            series_updated = _replace_series(conn, rows)
            latest_year = _verify_latest_year(_latest_year(conn, REFERENCE_SERIES), previous_latest)

        backup_path: Path | None = None
        if keep_backup:
            backup_path = db_path.with_name(db_path.name + ".bak")
            shutil.copy2(db_path, backup_path)

        temp_path.replace(db_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return UpdateResult(
        db_path=db_path,
        series_updated=series_updated,
        rows_written=len(rows),
        previous_latest_year=previous_latest,
        latest_year=latest_year,
        backup_path=backup_path,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Update cpi.db 'All Items' data from the BLS.")
    parser.add_argument(
        "--db",
        type=Path,
        default=CPI_DATABASE_PATH,
        help="Path to cpi.db (default: the copy bundled with comic_utils).",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header sent to BLS (must contain a contact email).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not keep a .bak copy of the previous database.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the updater as a command-line tool.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code: ``0`` on success, ``1`` on failure.

    """
    args = _build_arg_parser().parse_args(argv)
    try:
        result = update_cpi_db(
            args.db,
            user_agent=args.user_agent,
            keep_backup=not args.no_backup,
        )
    except (OSError, urllib.error.URLError, ValueError) as error:
        print(f"CPI update failed: {error}", file=sys.stderr)  # noqa: T201
        return 1

    previous = result.previous_latest_year or "n/a"
    print(  # noqa: T201
        f"Updated {result.db_path.name}: {result.series_updated} series, "
        f"{result.rows_written} rows. "
        f"Latest {REFERENCE_SERIES} year: {previous} -> {result.latest_year}."
    )
    if result.backup_path is not None:
        print(f"Previous database backed up to {result.backup_path.name}.")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
