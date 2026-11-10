"""Persist user settings and reading progress to a JSON store (Kivy-free).

The on-disk format is a plain JSON object keyed by section name, identical to
the kivy `JsonStore` format this module replaces, so existing user settings
files load unchanged.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

from .reader_tree_view_utils import BaseTreeViewNodeProtocol, get_tree_view_node_path
from .saved_page_info import SavedPageInfo

if TYPE_CHECKING:
    from pathlib import Path

_READER_SETTINGS = "AAA_Settings"
# The screen sizes warned as too small, kept apart: the reader settings are rewritten whole.
_SCREEN_SIZES_WARNED = "AAA_Screen_Sizes_Warned"
# How many more comics opened from the story picture it keeps its caption for
# (core.read_cue), kept apart for the same reason.
_READ_CUE = "AAA_Read_Cue"
_READ_CUE_OPENS_LEFT = "opens_left"
_READER_SETTING_LAST_SELECTED_NODE = "last_selected_node"
_READER_SETTING_LAST_SELECTED_NODE_STATE = "last_selected_node_state"
_TITLE_SETTING_LAST_READ_PAGE = "last_read_page"

# The 'Reading History' node became 'History' under a new 'Reading' parent.
# Saved node paths are leaf-first name lists, so migrate the old leaf path.
_LEGACY_HISTORY_NODE_PATH = ["Reading History", "root"]
_NEW_HISTORY_NODE_PATH = ["History", "Reading", "root"]


# A settings file that cannot be read is moved aside under this suffix, to be looked at.
CORRUPT_SUFFIX = ".corrupt"
_TEMP_SUFFIX = ".tmp"


def _load(store_path: Path) -> dict[str, dict[str, Any]]:
    """Return the settings stored at `store_path`: empty if it is missing, empty or corrupt.

    A file that is not a JSON object (cut short, or overwritten) once stopped the app
    booting. It is moved aside to `<name>.corrupt` instead, and the settings start
    empty: the next save writes a good file in its place. A file that cannot be read
    at all (its permissions, a folder in its place, a lock) is left where it is, as
    it may be whole, and the settings start empty too.
    """
    if not store_path.exists():
        return {}

    try:
        contents = store_path.read_text(encoding="utf-8").strip()
        data = json.loads(contents) if contents else {}
    except OSError as e:
        logger.error(
            f'Settings file "{store_path}" could not be read: {e}. Starting with empty settings.'
        )
        return {}
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        reason = f"not valid JSON ({e})"
    else:
        if isinstance(data, dict):
            return data
        reason = f"a JSON {type(data).__name__}, not an object"

    corrupt_path = store_path.with_name(store_path.name + CORRUPT_SUFFIX)
    try:
        store_path.replace(corrupt_path)
    except OSError as e:
        logger.error(
            f'Settings file "{store_path}" is {reason}, and could not be moved aside: {e}.'
            " Starting with empty settings."
        )
    else:
        logger.error(
            f'Settings file "{store_path}" is {reason}. Moved it to "{corrupt_path}";'
            " starting with empty settings."
        )
    return {}


class SavableTreeViewNode(BaseTreeViewNodeProtocol, Protocol):
    """A tree-view node whose expansion state can be persisted."""

    saved_state: dict[str, Any]


class SettingsManager:
    """Handles saving and loading of user settings and progress to a JSON store."""

    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._data: dict[str, dict[str, Any]] = _load(store_path)

    def _sync(self) -> None:
        # Written whole to a file beside it, then swapped in: a write cut short (a
        # crash, a kill, power lost mid page-turn) leaves the old file, not half of one.
        # A save comes with every page turn, so one that fails (a full disk, a file an
        # antivirus holds for a moment) is logged and the reading goes on: the settings
        # in memory are whole, and the next save writes them.
        temp_path = self._store_path.with_name(self._store_path.name + _TEMP_SUFFIX)
        try:
            temp_path.write_text(json.dumps(self._data, indent=4), encoding="utf-8")
            temp_path.replace(self._store_path)
        except OSError as e:
            logger.error(f'Could not save the settings to "{self._store_path}": {e}.')
            temp_path.unlink(missing_ok=True)

    def get_last_selected_node_path(self) -> tuple[list[str] | None, dict[str, Any]]:
        """Retrieve the path of the last selected node."""
        saved_node_settings = self._data.get(_READER_SETTINGS)
        # A hand-edited file may hold anything here: then nothing was selected.
        if not isinstance(saved_node_settings, dict):
            return None, {}

        raw_path = saved_node_settings.get(_READER_SETTING_LAST_SELECTED_NODE)
        saved_state = saved_node_settings.get(_READER_SETTING_LAST_SELECTED_NODE_STATE, {})

        if raw_path == _LEGACY_HISTORY_NODE_PATH:
            raw_path = _NEW_HISTORY_NODE_PATH

        return raw_path or None, saved_state

    def save_last_selected_node_path(self, last_selected_node: SavableTreeViewNode | None) -> None:
        """Save the path of the last selected node."""
        if not last_selected_node:
            path = []
            state = {}
        else:
            path = get_tree_view_node_path(last_selected_node)
            state = last_selected_node.saved_state

        self._data[_READER_SETTINGS] = {
            _READER_SETTING_LAST_SELECTED_NODE: path,
            _READER_SETTING_LAST_SELECTED_NODE_STATE: state,
        }
        self._sync()

        logger.debug(f'Settings: Saved last selected node path "{path}".')
        logger.debug(f'Settings: Saved last selected node state "{state}".')

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the last read page information for a specific title."""
        title_settings = self._data.get(title_str)
        # A hand-edited file may hold anything here: then the title has no saved page.
        if not isinstance(title_settings, dict):
            return None
        json_info = title_settings.get(_TITLE_SETTING_LAST_READ_PAGE)
        return SavedPageInfo.from_json(json_info) if json_info else None

    def save_last_read_page(self, title_str: str, page_info: SavedPageInfo) -> None:
        """Save the last read page information for a specific title."""
        self._data[title_str] = {_TITLE_SETTING_LAST_READ_PAGE: page_info.to_json()}
        self._sync()

    def get_read_cue_opens_left(self) -> int:
        """Return how many more comics the story picture keeps its caption for."""
        read_cue = self._data.get(_READ_CUE)
        # Never saved, or a hand-edited file holding anything: then none are left.
        left = read_cue.get(_READ_CUE_OPENS_LEFT) if isinstance(read_cue, dict) else None
        return left if type(left) is int and left > 0 else 0

    def save_read_cue_opens_left(self, opens_left: int) -> None:
        """Remember how many more comics the story picture keeps its caption for."""
        self._data[_READ_CUE] = {_READ_CUE_OPENS_LEFT: max(0, opens_left)}
        self._sync()

    def is_screen_size_warned(self, size_key: str) -> bool:
        """Return whether a too-small screen of this size has been warned about."""
        warned = self._data.get(_SCREEN_SIZES_WARNED)
        # A hand-edited file may hold anything here: then nothing has been warned about.
        return isinstance(warned, dict) and warned.get(size_key) is True

    def save_screen_size_warned(self, size_key: str) -> None:
        """Remember that a too-small screen of this size has been warned about."""
        warned = self._data.get(_SCREEN_SIZES_WARNED)
        if not isinstance(warned, dict):
            warned = self._data[_SCREEN_SIZES_WARNED] = {}
        warned[size_key] = True
        self._sync()
