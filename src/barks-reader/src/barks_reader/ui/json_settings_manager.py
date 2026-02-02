from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from barks_fantagraphics.comics_consts import PageType
from kivy.storage.jsonstore import JsonStore
from loguru import logger

from barks_reader.core.reader_tree_view_utils import get_tree_view_node_path

if TYPE_CHECKING:
    from pathlib import Path

    from barks_reader.ui.reader_ui_classes import BaseTreeViewNode

_READER_SETTINGS = "AAA_Settings"
_READER_SETTING_LAST_SELECTED_NODE = "last_selected_node"
_READER_SETTING_LAST_SELECTED_NODE_STATE = "last_selected_node_state"
_TITLE_SETTING_LAST_READ_PAGE = "last_read_page"


JsonSavedPageInfo = dict[str, Any]


@dataclass(slots=True)
class SavedPageInfo:
    page_index: int
    display_page_num: str
    page_type: PageType
    last_body_page: str

    def to_json(self) -> JsonSavedPageInfo:
        return {
            "page_index": self.page_index,
            "display_page_num": self.display_page_num,
            "page_type": self.page_type.name,
            "last_body_page": self.last_body_page,
        }

    @classmethod
    def from_json(cls, json_page_info: JsonSavedPageInfo) -> Self:
        return cls(
            json_page_info["page_index"],
            json_page_info["display_page_num"],
            PageType[json_page_info["page_type"]],
            json_page_info["last_body_page"],
        )


class SettingsManager:
    """Handles saving and loading of user settings and progress to a JSON store."""

    def __init__(self, store_path: Path) -> None:
        self._store = JsonStore(str(store_path), indent=4)

    def get_last_selected_node_path(self) -> tuple[list[str] | None, dict[str, Any]]:
        """Retrieve the path of the last selected node."""
        if not self._store.exists(_READER_SETTINGS):
            return None, {}

        saved_node_settings = self._store.get(_READER_SETTINGS)
        raw_path = saved_node_settings.get(_READER_SETTING_LAST_SELECTED_NODE)
        saved_state = (
            saved_node_settings.get(_READER_SETTING_LAST_SELECTED_NODE_STATE)
            if _READER_SETTING_LAST_SELECTED_NODE_STATE in saved_node_settings
            else {}
        )

        return raw_path if raw_path else None, saved_state

    def save_last_selected_node_path(self, last_selected_node: BaseTreeViewNode | None) -> None:
        """Save the path of the last selected node."""
        if not last_selected_node:
            path = []
            state = {}
        else:
            path = get_tree_view_node_path(last_selected_node)
            state = last_selected_node.saved_state

        self._store[_READER_SETTINGS] = {
            _READER_SETTING_LAST_SELECTED_NODE: path,
            _READER_SETTING_LAST_SELECTED_NODE_STATE: state,
        }

        logger.debug(f'Settings: Saved last selected node path "{path}".')
        logger.debug(f'Settings: Saved last selected node state "{state}".')

    def get_last_read_page(self, title_str: str) -> SavedPageInfo | None:
        """Retrieve the last read page information for a specific title."""
        if not self._store.exists(title_str):
            return None
        json_info = self._store.get(title_str).get(_TITLE_SETTING_LAST_READ_PAGE)
        return SavedPageInfo.from_json(json_info) if json_info else None

    def save_last_read_page(self, title_str: str, page_info: SavedPageInfo) -> None:
        """Save the last read page information for a specific title."""
        self._store.put(title_str, **{_TITLE_SETTING_LAST_READ_PAGE: page_info.to_json()})
