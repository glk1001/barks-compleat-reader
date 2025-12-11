import json
from pathlib import Path

from barks_fantagraphics.whoosh_search_engine import SearchEngine, TitleDict


class WhooshIndexer:
    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        self.unstemmed_terms = self._get_unstemmed_terms()

        self._search_engine = SearchEngine(self._index_path)

    def _get_unstemmed_terms(self) -> list[str]:
        unstemmed_terms_path = self._index_path / "unstemmed-terms.json"

        return json.loads(unstemmed_terms_path.read_text())

    def find_unstemmed_words(self, search_words: str) -> TitleDict:
        return self._search_engine.find_words(search_words, use_unstemmed_terms=True)
