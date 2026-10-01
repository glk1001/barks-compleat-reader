"""A bundle file that cannot be read degrades, never crashes (tolerant consumption, SPEC §9).

The wiki can be regenerated under a running reader, and a file can lose its
permissions: each reader of the bundle falls back instead of raising. No run
meets an unreadable file, so these were never reached.
"""

# ruff: noqa: SLF001

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from okf_reader.core import render as okf
from okf_reader.core.search import build_search_index, search_index
from okf_reader.core.session import save_session_state

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def _unreadable(*names: str) -> Iterator[None]:
    """Make the files of these names refuse to be read, as a lost permission does."""
    real = Path.read_text

    def read_text(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self.name in names:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, encoding=encoding, errors=errors)

    with patch.object(Path, "read_text", read_text):
        yield


def _dir_with_index(tmp_path: Path) -> Path:
    directory = tmp_path / "comics-and-stories"
    directory.mkdir()
    (directory / "index.md").write_text(
        "# Curated Title\n\n- [B](b.md)\n- [A](a.md)\n", encoding="utf-8"
    )
    return directory


def test_an_unreadable_index_titles_its_dir_by_name(tmp_path: Path) -> None:
    directory = _dir_with_index(tmp_path)
    assert okf.dir_title(directory) == "Curated Title"
    with _unreadable("index.md"):
        assert okf.dir_title(directory) == "Comics And Stories"


def test_an_unreadable_index_gives_no_curated_order(tmp_path: Path) -> None:
    directory = _dir_with_index(tmp_path)
    assert okf._index_link_order(directory) == {"b.md": 0, "a.md": 1}
    with _unreadable("index.md"):
        assert okf._index_link_order(directory) == {}


def test_an_unreadable_page_is_indexed_without_its_headings(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "index.md").write_text("# Home\n", encoding="utf-8")
    (bundle / "dither.md").write_text("# Ten-Dollar Dither\n\n## Payment\n", encoding="utf-8")
    (bundle / "guess.md").write_text("# You Can't Guess!\n\n## The Bomb\n", encoding="utf-8")

    with _unreadable("dither.md"):
        index = build_search_index(bundle)

    assert {entry.path.name for entry in index.entries} == {"dither.md", "guess.md"}
    assert search_index(index, "payment") == []  # its heading was never read
    assert [hit.path.name for hit in search_index(index, "bomb")] == ["guess.md"]


def test_a_session_that_cannot_be_saved_is_dropped_quietly(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    page = bundle / "index.md"
    page.write_text("# Home\n", encoding="utf-8")
    blocker = tmp_path / "state"
    blocker.write_text("a file where the state dir goes", encoding="utf-8")

    save_session_state(blocker / "session.json", bundle, page, 0.5)

    assert blocker.is_file()
