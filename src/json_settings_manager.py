import json
from dataclasses import dataclass
from typing import Union, List, Dict, Any, Self

from kivy.storage.jsonstore import JsonStore

from barks_fantagraphics.comics_consts import PageType

_READER_SETTINGS = "AAA_Settings"
_READER_SETTING_LAST_SELECTED_NODE = "last_selected_node"
_TITLE_SETTING_LAST_READ_PAGE = "last_read_page"


JsonSavedPageInfo = Dict[str, Any]


@dataclass
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

    def __init__(self, store_path: str):
        self._store = JsonStore(store_path)

    def get_last_selected_node_path(self) -> Union[List[str], None]:
        """Retrieves the path of the last selected node."""
        if not self._store.exists(_READER_SETTINGS):
            return None
        raw_path = self._store.get(_READER_SETTINGS).get(_READER_SETTING_LAST_SELECTED_NODE)
        return json.loads(raw_path) if raw_path else None

    def save_last_selected_node_path(self, path: List[str]) -> None:
        """Saves the path of the last selected node."""
        self._store.put(_READER_SETTINGS, **{_READER_SETTING_LAST_SELECTED_NODE: json.dumps(path)})

    def get_last_read_page(self, title_str: str) -> Union[SavedPageInfo, None]:
        """Retrieves the last read page information for a specific title."""
        if not self._store.exists(title_str):
            return None
        json_info = self._store.get(title_str).get(_TITLE_SETTING_LAST_READ_PAGE)
        return SavedPageInfo.from_json(json_info) if json_info else None

    def save_last_read_page(self, title_str: str, page_info: SavedPageInfo) -> None:
        """Saves the last read page information for a specific title."""
        self._store.put(title_str, **{_TITLE_SETTING_LAST_READ_PAGE: page_info.to_json()})
