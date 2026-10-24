"""Story links beside a document page: read, labelled, and the bad ones skipped."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.document_links import StoryLink, load_story_links

if TYPE_CHECKING:
    from pathlib import Path


def _page(tmp_path: Path, figures: object) -> Path:
    page = tmp_path / "page-007.png"
    page.write_bytes(b"")
    page.with_suffix(".json").write_text(json.dumps({"figures": figures}), encoding="utf-8")
    return page


def test_a_page_with_no_links_file_has_no_links(tmp_path: Path) -> None:
    page = tmp_path / "page-001.png"
    page.write_bytes(b"")
    assert load_story_links(page) == []


def test_links_come_in_figure_order_labelled_from_our_own_titles(tmp_path: Path) -> None:
    page = _page(
        tmp_path,
        [
            {"figure": 5, "title": "LOST_IN_THE_ANDES", "page": "7", "display_title": "x"},
            # An assigned title shows in parentheses, whatever the file says.
            {"figure": 6, "title": "VICTORY_GARDEN_THE", "page": 2},
        ],
    )
    assert load_story_links(page) == [
        StoryLink(Titles.LOST_IN_THE_ANDES, "7", "Fig. 5: Lost in the Andes!, page 7"),
        StoryLink(Titles.VICTORY_GARDEN_THE, "2", "Fig. 6: (The Victory Garden), page 2"),
    ]


def test_an_unknown_title_is_skipped_with_a_warning(tmp_path: Path, loguru_sink: list[str]) -> None:
    page = _page(
        tmp_path,
        [
            {"figure": 1, "title": "NO_SUCH_TITLE", "page": "1"},
            {"figure": 2, "title": "LOST_IN_THE_ANDES", "page": "3"},
        ],
    )
    assert [link.page for link in load_story_links(page)] == ["3"]
    assert any("skipped" in line and "NO_SUCH_TITLE" in line for line in loguru_sink)


def test_an_unreadable_file_gives_no_links_and_a_warning(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    page = tmp_path / "page-001.png"
    page.write_bytes(b"")
    page.with_suffix(".json").write_text("{not json", encoding="utf-8")
    assert load_story_links(page) == []
    assert any("unreadable" in line for line in loguru_sink)
