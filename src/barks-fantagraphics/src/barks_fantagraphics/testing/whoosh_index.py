"""A small Whoosh index in the production schema, for tests.

Every field the schema names gets an empty default, so a test spells out only the
fields it is about, and a field added to ``build_index_schema`` is one edit here
rather than one per hand-written document. Keys the schema does not name pass
through to the writer, so Whoosh's ``_stored_<field>`` convention still works.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from whoosh.index import create_in

from barks_fantagraphics.whoosh_search_engine import build_index_schema

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path


def build_test_index(index_dir: Path, docs: Iterable[Mapping[str, str]] = ()) -> Path:
    """Create an index in ``index_dir`` holding ``docs``, each filled out to the schema.

    Args:
        index_dir: An existing, empty directory (a ``tmp_path``).
        docs: The documents, each a mapping of field name to value; unnamed schema
            fields are stored empty.

    Returns:
        ``index_dir``, for a fixture to hand on.

    """
    schema = build_index_schema()
    defaults = dict.fromkeys(schema.names(), "")
    writer = create_in(str(index_dir), schema).writer()
    for doc in docs:
        writer.add_document(**{**defaults, **doc})
    writer.commit()
    return index_dir


def schema_tokens(text: str) -> list[str]:
    """Tokenize ``text`` the way the index's ``unstemmed`` field does.

    The chain is read from the schema, so a test using it follows a change to the
    tokenizer, the case folding or the stop words instead of passing against a stale
    hand-assembled copy.
    """
    analyzer = build_index_schema()["unstemmed"].analyzer
    return [token.text for token in analyzer(text)]
