"""Newer data packs beside the executable: offered at boot, and looked for from the dots menu.

A development run looks nowhere unless BARKS_READER_DATA_PACK_DIR names a folder, so
the offer is exercised with two small packs written for the test and declined with
Escape; nothing is ever installed. The packs are version 999: above any pack a
machine could hold.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest
from barks_gui import nodes
from barks_reader.core import log_markers as markers
from barks_reader.core.data_pack import (
    DATA_PACK_DIR_ENV_VAR,
    DATA_PACK_FILE_NAMES,
    PACK_MEMBER,
    DataPackInfo,
)
from barks_reader.core.log_markers import pattern
from barks_reader.ui.main_screen import UPDATE_DATA_PACK_TITLE

if TYPE_CHECKING:
    from pathlib import Path

    from barks_gui.harness import AppBoot
    from gui_driver import Driver

ANY_NODE_SELECTED = pattern(markers.NEW_SELECTED_NODE)
OFFERED = pattern(markers.CONFIRM_POPUP_OPENED, title=UPDATE_DATA_PACK_TITLE)
DECLINED = pattern(markers.CONFIRM_POPUP_CANCELLED, title=UPDATE_DATA_PACK_TITLE)
NOTHING_TO_INSTALL = pattern(markers.MESSAGE_POPUP_OPENED, title=UPDATE_DATA_PACK_TITLE)
DISMISSED = pattern(markers.MESSAGE_POPUP_CANCELLED, title=UPDATE_DATA_PACK_TITLE)
# Settings, How To, Update Data, About: the dots menu opens on its first entry.
UPDATE_DATA_DOWNS = 2


@pytest.fixture
def fake_packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Two tiny versioned packs in a folder the app is told to look in."""
    pack_dir = tmp_path / "packs"
    pack_dir.mkdir()
    info = DataPackInfo(999, "data-v999", datetime(2026, 10, 29, tzinfo=UTC), "test", {})
    for name in DATA_PACK_FILE_NAMES:
        with ZipFile(pack_dir / name, "w") as pack:
            pack.writestr(PACK_MEMBER, info.to_json())
    monkeypatch.setenv(DATA_PACK_DIR_ENV_VAR, str(pack_dir))
    return pack_dir


def _open_dots_menu(d: Driver, downs: int) -> None:
    d.main_menu_button_then_wait("menu", d.FOCUS_MOVED)
    d.move_focus(*["Down"] * downs)


def test_newer_packs_are_offered_at_boot_and_escape_declines(
    boot: AppBoot, fake_packs: Path
) -> None:
    """The offer is up by the time the tree is; Escape keeps the reader running."""
    d = boot(nodes.THE_STORIES)
    d.wait_for(OFFERED)
    d.key_then_wait(DECLINED, "Escape")
    d.expect_no_new(pattern(markers.CLOSING_APP), 2.0)
    d.key_then_wait(ANY_NODE_SELECTED, "Down")  # still alive and answering
    assert fake_packs.is_dir()  # and nothing was installed from it


def test_the_dots_menu_looks_for_packs_and_says_when_there_are_none(boot: AppBoot) -> None:
    """With nowhere to look, Update Data says so, and its close returns to the Menu button."""
    d = boot(nodes.THE_STORIES)
    _open_dots_menu(d, downs=UPDATE_DATA_DOWNS)
    with d.expect(NOTHING_TO_INSTALL), d.expect(d.DROPDOWN_DISMISSED):
        d.key("Return")
    with d.expect(f'{d.FOCUS_MOVED} ChromeBarButton "Menu"'), d.expect(d.MENU_ENTERED):
        d.key_then_wait(DISMISSED, "Escape")
    d.key_then_wait(d.MENU_EXITED, "Escape")
    d.key_then_wait(ANY_NODE_SELECTED, "Down")
