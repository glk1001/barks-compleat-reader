import json
from pathlib import Path


class WhooshIndexer:
    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        self._unstemmed_terms = self._get_unstemmed_terms()

    def _get_unstemmed_terms(self) -> list[str]:
        unstemmed_terms_path = self._index_path / "unstemmed-terms.json"

        return json.loads(unstemmed_terms_path.read_text())
