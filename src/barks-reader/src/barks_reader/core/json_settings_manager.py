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
_READER_SETTING_LAST_SELECTED_NODE = "last_selected_node"
_READER_SETTING_LAST_SELECTED_NODE_STATE = "last_selected_node_state"
_TITLE_SETTING_LAST_READ_PAGE = "last_read_page"

# The 'Reading History' node became 'History' under a new 'Reading' parent.
# Saved node paths are leaf-first name lists, so migrate the old leaf path.
_LEGACY_HISTORY_NODE_PATH = ["Reading History", "root"]
_NEW_HISTORY_NODE_PATH = ["History", "Reading", "root"]


class SavableTreeViewNode(BaseTreeViewNodeProtocol, Protocol):
    """A tree-view node whose expansion state can be persisted."""

    saved_state: dict[str, Any]


class SettingsManager:
    """Handles saving and loading of user settings and progress to a JSON store."""

    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._data: dict[str, dict[str, Any]] = {}
        if store_path.exists() and (contents := store_path.read_text(encoding="utf-8").strip()):
            self._data = json.loads(contents)

    def _sync(self) -> None:
        self._store_path.write_text(json.dumps(self._data, indent=4), encoding="utf-8")

    def get_last_selected_node_path(self) -> tuple[list[str] | None, dict[str, Any]]:
        """Retrieve the path of the last selected node."""
        if _READER_SETTINGS not in self._data:
            return None, {}

        saved_node_settings = self._data[_READER_SETTINGS]
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
        if title_str not in self._data:
            return None
        json_info = self._data[title_str].get(_TITLE_SETTING_LAST_READ_PAGE)
        return SavedPageInfo.from_json(json_info) if json_info else None

    def save_last_read_page(self, title_str: str, page_info: SavedPageInfo) -> None:
        """Save the last read page information for a specific title."""
        self._data[title_str] = {_TITLE_SETTING_LAST_READ_PAGE: page_info.to_json()}
        self._sync()
