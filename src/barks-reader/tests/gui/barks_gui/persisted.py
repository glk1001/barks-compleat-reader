"""What the app persisted in the scratch profile, checked against what it logged.

Every read that saves progress leaves two things behind: a last-read cue for the
title in ``barks-reader.json`` and a reading-history event. The app logs both as
it writes them, so a teardown can hold the files to the log for every read a
test made, without the test saying a word about it.
"""

from __future__ import annotations

import configparser
import json
import re
from typing import TYPE_CHECKING, Any

from barks_gui.harness import FIXTURES_DIR, read_ini_value
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE, FIRST_BODY_PAGE

if TYPE_CHECKING:
    from pathlib import Path

SETTINGS_KEY = "AAA_Settings"
_QUOTED = re.compile(r'([^"]*)')
_SAVED_RE = re.compile(pattern(markers.LAST_READ_PAGE_SAVED, title=_QUOTED, page=_QUOTED))
_OPEN_RE = re.compile(pattern(markers.HISTORY_OPEN_RECORDED, title=_QUOTED))
_CLOSE_RE = re.compile(pattern(markers.HISTORY_CLOSE_RECORDED, title=_QUOTED))
_SHOWED_RE = re.compile(pattern(markers.SHOWED_PAGE, index=re.compile(r"(\d+)")))
_DOUBLE_PAGE_ON = pattern(markers.DOUBLE_PAGE_TOGGLED, mode=True)


def cues(scratch: Path) -> dict[str, dict[str, Any]]:
    """Return the last-read cue of every title in the profile's json, keyed by title."""
    settings = json.loads((scratch / "barks-reader.json").read_text())
    return {
        title: entry["last_read_page"]
        for title, entry in settings.items()
        if title != SETTINGS_KEY and isinstance(entry, dict) and "last_read_page" in entry
    }


def history_events(scratch: Path) -> list[dict[str, Any]]:
    """Return the profile's reading-history events, in file order."""
    return json.loads((scratch / "barks-reader-history.json").read_text())["events"]


def canned_history_ids() -> set[str]:
    """Return the ids of the events every test's history starts with."""
    canned = json.loads((FIXTURES_DIR / "barks-reader-history.json").read_text())
    return {e["id"] for e in canned["events"]}


def _saves_logged(app_log: str) -> list[tuple[str, str, int | None]]:
    """Return every save the app logged as (title, page, index of the page last shown)."""
    saves: list[tuple[str, str, int | None]] = []
    last_shown: int | None = None
    for line in app_log.splitlines():
        if found := _SHOWED_RE.search(line):
            last_shown = int(found[1])
        elif found := _SAVED_RE.search(line):
            saves.append((found[1], found[2], last_shown))
    return saves


def _cue_problems(
    scratch: Path, saves: list[tuple[str, str, int | None]], *, hold_index: bool
) -> list[str]:
    """Check each title's cue against the last save the app logged for it."""
    problems: list[str] = []
    saved_cues = cues(scratch)
    last_save_for = {title: (page, index) for title, page, index in saves}
    for title, (page, index) in last_save_for.items():
        cue = saved_cues.get(title)
        if cue is None:
            problems.append(f'no last-read cue for "{title}", which the app said it saved')
            continue
        cue_page, cue_index = cue.get("display_page_num"), cue.get("page_index")
        if cue_page != page:
            problems.append(f'"{title}": cue page {cue_page!r}, app saved {page!r}')
        if hold_index and index is not None and cue_index != index:
            problems.append(f'"{title}": cue page index {cue_index}, last shown {index}')
    return problems


def _page_history_records(scratch: Path, title: str, page: str) -> str:
    """Return the page the history records for a read that saved `page` of `title`.

    The cue keeps the page as saved; the history gets it normalised: a read that
    ended outside the body (front matter, the first or the last body page) is
    recorded at the beginning, so the next open starts the comic over
    (LastReadPageTracker.end).
    """
    cue = cues(scratch).get(title)
    if cue is None:
        return page  # no cue to judge by; its absence is reported on its own
    inside_body = cue.get("page_type") == "BODY" and page not in (
        FIRST_BODY_PAGE,
        cue.get("last_body_page"),
    )
    return page if inside_body else COMIC_BEGIN_PAGE


def _history_problems(
    scratch: Path, app_log: str, saves: list[tuple[str, str, int | None]]
) -> list[str]:
    """Check the new history events against the opens, closes and saves the app logged."""
    problems: list[str] = []
    opens = [found[1] for found in _OPEN_RE.finditer(app_log)]
    closes = [found[1] for found in _CLOSE_RE.finditer(app_log)]
    canned = canned_history_ids()
    new_events = [e for e in history_events(scratch) if e["id"] not in canned]
    titles = [e["title"] for e in new_events]
    if titles != opens:
        problems.append(f"history events {titles} do not match the opens the app recorded {opens}")
    for i, event in enumerate(new_events):
        if i < len(closes) and not event.get("closed_at"):
            problems.append(f'history event for "{event["title"]}" closed but has no close time')
    pages_saved = [_page_history_records(scratch, title, page) for title, page, _index in saves]
    pages_recorded = [e["last_display_page"] for e in new_events if e.get("last_display_page")]
    if pages_recorded != pages_saved[: len(pages_recorded)]:
        problems.append(f"history pages {pages_recorded} are not the pages saved {pages_saved}")
    return problems


def _double_page_booted(scratch: Path) -> bool:
    """Whether the profile booted in double-page mode (a matrix run flips it on)."""
    ini = scratch / "barks-reader.ini"
    if not ini.is_file():
        return False
    try:
        return read_ini_value(ini, "double_page_mode") == "1"
    except configparser.Error:
        return False


def reads_persisted_problems(scratch: Path, app_log: str) -> list[str]:
    """Return how the profile disagrees with the reads the app logged.

    For every read that saved progress: the title's cue holds the page the app
    said it saved, and (in single-page mode) the index of the page last shown.
    For the history: one event per open the app recorded, in order; each close
    the app recorded set its event's close time; each event with a page carries
    the page the read saved.

    Args:
        scratch: The test's config directory.
        app_log: The app log's text.

    Returns:
        One line per problem; empty when everything the app logged is on disk.

    """
    saves = _saves_logged(app_log)
    single_page_only = (
        not _double_page_booted(scratch) and re.search(_DOUBLE_PAGE_ON, app_log) is None
    )
    return [
        *_cue_problems(scratch, saves, hold_index=single_page_only),
        *_history_problems(scratch, app_log, saves),
    ]
