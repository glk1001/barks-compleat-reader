from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from barks_fantagraphics.comics_consts import PageType

from .reader_consts_and_types import FIRST_BODY_PAGE

JsonSavedPageInfo = dict[str, Any]


@dataclass(slots=True)
class SavedPageInfo:
    page_index: int
    display_page_num: str
    page_type: PageType
    last_body_page: str

    def is_inside_body(self) -> bool:
        return self.page_type == PageType.BODY and self.display_page_num not in (
            FIRST_BODY_PAGE,
            self.last_body_page,
        )

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
