"""The error popups, closed with the remote's keys.

Each test points the app at a Fantagraphics library of its own: symlinks to the
real volume archives with one left out or doubled, or a folder that is not there.
Until 2026-09-28 none of these popups took a key (auto_dismiss off, no keyboard
driver), and the main screen hands every key to an open popup, so a remote user
who met one could not get past it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from barks_gui import harness, nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

# Volume 5 holds The Ghost of the Grotto, one of the suite's story nodes.
MISSING_VOLUME_PREFIX = "05 "
VOLUME_MISSING = "Fantagraphics Volume Missing"


def _library(boot: AppBoot, tmp_path: Path, *, leave_out: str = "", double: str = "") -> Path:
    """Make a library of symlinks to the profile's real archives, one left out or doubled."""
    value = harness.read_ini_value(boot.scratch / "barks-reader.ini", "fanta_dir")
    real = Path(os.path.expandvars(value)).expanduser()
    if not real.is_dir():
        pytest.skip(f"no Fantagraphics library at {real}")
    library = tmp_path / "library"
    library.mkdir()
    for archive in sorted(real.iterdir()):
        if leave_out and archive.name.startswith(leave_out):
            continue
        (library / archive.name).symlink_to(archive)
        if double and archive.name.startswith(double) and archive.suffix == ".cbz":
            (library / f"{archive.stem} (copy){archive.suffix}").symlink_to(archive)
    return library


def _opened(title: str) -> str:
    return pattern(markers.MESSAGE_POPUP_OPENED, title=title)


def _closed(title: str) -> str:
    return pattern(markers.MESSAGE_POPUP_CLOSED, title=title)


def test_a_missing_volume_notice_closes_on_escape(boot: AppBoot, tmp_path: Path) -> None:
    library = _library(boot, tmp_path, leave_out=MISSING_VOLUME_PREFIX)
    d = boot(nodes.THE_STORIES, ini={"fanta_dir": str(library), "use_prebuilt_comics": "0"})
    d.wait_for(_opened(VOLUME_MISSING))
    d.key_then_wait(_closed(VOLUME_MISSING), "Escape")
    # Past the popup, the tree answers the remote again.
    d.key_then_wait(pattern(markers.NEW_SELECTED_NODE), "Down")


def test_reading_a_story_from_a_missing_volume_explains_and_returns(
    boot: AppBoot, tmp_path: Path
) -> None:
    library = _library(boot, tmp_path, leave_out=MISSING_VOLUME_PREFIX)
    d = boot(
        nodes.GHOST_OF_THE_GROTTO,
        cues={"The Ghost of the Grotto": None},
        ini={"fanta_dir": str(library), "use_prebuilt_comics": "0"},
    )
    boot.expect_error(r'Cannot show the title "The Ghost of the Grotto".*volume 5 is missing')
    d.wait_for(_opened(VOLUME_MISSING))
    d.key_then_wait(_closed(VOLUME_MISSING), "Escape")
    d.focus_portal()
    with d.expect(_opened(VOLUME_MISSING)):
        d.key("Return")
    d.key_then_wait(_closed(VOLUME_MISSING), "Return")


DIR_NOT_FOUND = "Fantagraphics Directory Not Found"
WRONG_ARCHIVE = "Wrong Fantagraphics Archive File"


def test_a_missing_library_offers_settings_and_enter_opens_them(
    boot: AppBoot, tmp_path: Path
) -> None:
    """Settings starts focused: Enter opens them, and Escape closes them again."""
    d = boot(
        nodes.THE_STORIES,
        ini={"fanta_dir": str(tmp_path / "no-such-library"), "use_prebuilt_comics": "0"},
    )
    boot.expect_error(r"Required directory not found: .*no-such-library")
    d.wait_for(_opened(DIR_NOT_FOUND))
    with d.expect(markers.DISPLAY_SETTINGS):
        d.key_then_wait(
            pattern(markers.MESSAGE_POPUP_OK, title=DIR_NOT_FOUND, button="Settings"), "Return"
        )
    d.key_then_wait(markers.SETTINGS_CLOSED, "Escape")


def test_a_doubled_volume_is_fatal_and_its_close_takes_enter(boot: AppBoot, tmp_path: Path) -> None:
    library = _library(boot, tmp_path, double=MISSING_VOLUME_PREFIX)
    d = boot(nodes.THE_STORIES, ini={"fanta_dir": str(library), "use_prebuilt_comics": "0"})
    d.wait_for(_opened(WRONG_ARCHIVE))
    d.key_then_wait(_closed(WRONG_ARCHIVE), "Return")
