"""Story links beside a document page: read, labelled, and the bad ones skipped."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import get_fanta_info
from barks_reader.core import log_markers
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


# A title with no Fantagraphics volume: listed, but there is no comic to open.
NO_VOLUME_TITLE = "ATTIC_ANTICS"


@pytest.mark.parametrize("title", ["NO_SUCH_TITLE", NO_VOLUME_TITLE])
def test_a_title_with_no_comic_is_skipped_with_a_warning_and_the_rest_kept(
    tmp_path: Path, loguru_sink: list[str], title: str
) -> None:
    skipped = {"figure": 1, "title": title, "page": "1"}
    page = _page(tmp_path, [skipped, {"figure": 2, "title": "LOST_IN_THE_ANDES", "page": "3"}])
    assert [link.page for link in load_story_links(page)] == ["3"]
    assert (
        log_markers.DOCUMENT_LINK_SKIPPED.format(path=page.with_suffix(".json"), entry=skipped)
        in loguru_sink
    )


def test_the_no_volume_title_is_a_title_with_no_volume() -> None:
    assert get_fanta_info(Titles[NO_VOLUME_TITLE]) is None


def test_an_unreadable_file_gives_no_links_and_a_warning(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    page = tmp_path / "page-001.png"
    page.write_bytes(b"")
    page.with_suffix(".json").write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as error:
        json.loads("{not json")
    assert load_story_links(page) == []
    assert (
        log_markers.DOCUMENT_LINKS_UNREADABLE.format(
            path=page.with_suffix(".json"), error=error.value
        )
        in loguru_sink
    )


@pytest.mark.parametrize(("figures", "kind"), [(None, "NoneType"), (5, "int"), ("abc", "str")])
def test_figures_that_are_not_a_list_give_no_links_and_one_warning(
    tmp_path: Path, loguru_sink: list[str], figures: object, kind: str
) -> None:
    page = _page(tmp_path, figures)
    assert load_story_links(page) == []
    assert (
        log_markers.DOCUMENT_LINKS_UNREADABLE.format(
            path=page.with_suffix(".json"), error=f"'figures' is {kind}, not a list"
        )
        in loguru_sink
    )
    # Not one skipped-entry warning per character of a string.
    assert not any("skipped" in line for line in loguru_sink)
