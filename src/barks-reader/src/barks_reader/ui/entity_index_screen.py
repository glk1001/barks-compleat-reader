from __future__ import annotations

import string
from collections import defaultdict
from typing import TYPE_CHECKING, override

from .index_screen import IndexItem
from .speech_index_screen import SpeechSubItemsIndexScreen, shorten_if_necessary

if TYPE_CHECKING:
    from barks_fantagraphics.entity_types import EntityType
    from barks_fantagraphics.whoosh_search_engine import TitleDict

    from barks_reader.core.reader_settings import ReaderSettings

    from .font_manager import FontManager
    from .user_error_handler import UserErrorHandler


class EntityIndexScreen(SpeechSubItemsIndexScreen):
    """An index screen for entity types (persons, locations, etc.).

    There are few enough names or places per letter to list them directly, so this
    has no prefix bar and goes straight from the side A-Z alphabet to the items grid.
    """

    def __init__(
        self,
        entity_type: EntityType,
        reader_settings: ReaderSettings,
        font_manager: FontManager,
        user_error_handler: UserErrorHandler,
        **kwargs,  # noqa: ANN003
    ) -> None:
        self._entity_type = entity_type
        super().__init__(reader_settings, font_manager, user_error_handler, **kwargs)

        # Build a flat {letter: [IndexItem, ...]} from entity terms, bypassing
        # the nested alpha-split structure that SpeechIndexScreen uses.
        self._item_index = defaultdict(list)
        terms = self._search.get_entity_terms(self._entity_type)
        for t in terms:
            if not t:
                continue
            ch = t[0].lower()
            if not "a" <= ch <= "z":
                msg = f'Entity term has non-alpha prefix: "{t}".'
                raise RuntimeError(msg)

            letter = ch.upper()
            self._item_index[letter].append(IndexItem(t, shorten_if_necessary(t)))

    @override
    def _get_alphabet_letters(self) -> str:
        """Return only A-Z for entity indexes (no digits or apostrophes)."""
        return string.ascii_uppercase

    @override
    def _find_words(self, index_terms: str) -> TitleDict:
        return self._search.find_entities(self._entity_type, index_terms)

    @override
    def _on_up_from_first_item(self) -> None:
        # Unlike the main index, which stays put, Up from the top row goes back to
        # the A-Z menu -- there is no prefix bar in between to land on.
        self._clear_all_item_focus()
        self._enter_alphabet_panel()
