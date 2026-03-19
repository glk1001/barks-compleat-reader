from __future__ import annotations

import string
from collections import defaultdict
from typing import TYPE_CHECKING, override

from barks_reader.ui.index_screen import IndexItem
from barks_reader.ui.speech_index_screen import SpeechIndexScreen, shorten_if_necessary

if TYPE_CHECKING:
    from barks_fantagraphics.entity_types import EntityType
    from barks_fantagraphics.whoosh_search_engine import TitleDict

    from barks_reader.core.reader_settings import ReaderSettings
    from barks_reader.ui.font_manager import FontManager
    from barks_reader.ui.user_error_handler import UserErrorHandler


class EntityIndexScreen(SpeechIndexScreen):
    """An index screen for entity types (persons, locations, etc.).

    Unlike the Words (SpeechIndexScreen) index, entity indexes skip the top
    prefix submenu and go straight from the side A-Z alphabet to the items grid
    (like MainIndexScreen).
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
        terms = self._whoosh_indexer.get_entity_terms(self._entity_type)
        for t in terms:
            if not t:
                continue
            ch = t[0].lower()
            if not "a" <= ch <= "z":
                msg = f'Entity term has non-alpha prefix: "{t}".'
                raise RuntimeError(msg)

            letter = ch.upper()
            self._item_index[letter].append(IndexItem(t, shorten_if_necessary(t)))

        # Hide the top prefix bar (widget defined in the .kv file).
        self.ids.alphabet_top_split_layout.height = 0
        self.ids.alphabet_top_split_layout.opacity = 0

    @override
    def _get_alphabet_letters(self) -> str:
        """Return only A-Z for entity indexes (no digits or apostrophes)."""
        return string.ascii_uppercase

    @override
    def _find_words(self, index_terms: str) -> TitleDict:
        return self._whoosh_indexer.find_entities(self._entity_type, index_terms)

    # --- Skip the prefix layer: go straight from alphabet to items grid ---

    @override
    def _populate_index_for_letter(self, first_letter: str) -> None:
        # Skip _populate_top_alphabet_split_menu; go directly to the grid.
        self._populate_index_grid(first_letter)

    # --- Keyboard nav: restore IndexScreen base behavior (skip PREFIX panel) ---

    @override
    def handle_key(self, key: int) -> bool:
        # Bypass SpeechIndexScreen's PREFIX interception; use IndexScreen logic.
        if self._popup_nav.is_open:
            return self._popup_nav.handle_key(key)
        return super(SpeechIndexScreen, self).handle_key(key)

    @override
    def _on_right_from_alphabet(self) -> None:
        self._enter_items_panel()

    @override
    def _on_back_from_items(self) -> None:
        self._enter_alphabet_panel()

    @override
    def _on_up_from_first_item(self) -> None:
        self._clear_all_item_focus()
        self._enter_alphabet_panel()

    @override
    def exit_nav_focus(self) -> None:
        # Skip SpeechIndexScreen's prefix cleanup.
        self._nav_on_speech_btn = False
        super(SpeechIndexScreen, self).exit_nav_focus()
