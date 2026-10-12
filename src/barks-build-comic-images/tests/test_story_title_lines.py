# ruff: noqa: SLF001
"""Checks on how every story's title is broken into lines for its title page.

A title is lettered on the lines its ini file gives it (or, for a title made from an
issue name, the lines ``ISSUE_NAME_WRAPPED`` gives it). Nothing else checks those
breaks, so these tests hold them to the rules the lettering is designed around:

1. A full-size line never ends on a small word ("Hound of the / Moaning Hills"): the
   small words joining a title's halves go on a line of their own, lettered small
   ("Hound / of the / Moaning Hills").
2. So a later line never starts with a joining word followed by more ("The Prize / of
   Pizarro" is "The Prize / of / Pizarro").
3. A small line keeps the small words after it ("Mystery / of / the Swamp" is
   "Mystery / of the / Swamp").
4. Every line fits the page, with room to spare.

What no test can check is that a name stays on one line ("Cape / Quack"): telling a
name from two words needs a reader.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_build_comic_images.build_comic_images import (
    INTRO_TITLE_OUTLINE_WIDTH,
    INTRO_TITLE_SMALL_WORDS,
    ComicBookImageBuilder,
)
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.comic_book_info import NON_COMIC_TITLES, SYNTHETIC_TITLES
from barks_fantagraphics.comics_consts import DEST_TARGET_WIDTH
from barks_fantagraphics.comics_database import ComicsDatabase
from PIL import Image, ImageFont

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.comic_book import ComicBook

# The small words that join two parts of a title, as against an article like "the" that
# belongs to the noun after it ("The Day / the Mountain / Shook").
_JOINING_WORDS = INTRO_TITLE_SMALL_WORDS - {"a", "an", "the"}

# The least room a title line may leave at either side of the page, outline included.
_MIN_TITLE_MARGIN = 50


def _is_small_word_line(line: str) -> bool:
    return all(word.lower() in INTRO_TITLE_SMALL_WORDS for word in line.split())


def _get_line_break_problems(title: str) -> list[str]:
    """Return how a title's line breaks break the rules, or nothing if they don't.

    Args:
        title: The title, its lines separated by newlines.

    Returns:
        One description per broken rule, naming the line.

    """
    lines = title.split("\n")
    problems = []
    for line_num, (line, next_line) in enumerate(zip(lines, [*lines[1:], ""], strict=True)):
        words = line.split()
        if _is_small_word_line(line):
            if (
                next_line
                and next_line.split()[0].lower() in INTRO_TITLE_SMALL_WORDS
                and not _is_small_word_line(next_line)
            ):
                problems.append(f'small line "{line}" is split from "{next_line}"')
            continue
        if next_line and words[-1].lower() in INTRO_TITLE_SMALL_WORDS:
            problems.append(f'line "{line}" ends on "{words[-1]}"')
        if line_num > 0 and words[0].lower() in _JOINING_WORDS:
            problems.append(f'line "{line}" starts with "{words[0]}"')
    return problems


# The essays and the collections have no title page.
_NO_TITLE_PAGE = {ENUM_TO_STR_TITLE[title] for title in [*NON_COMIC_TITLES, *SYNTHETIC_TITLES]}


@pytest.fixture(scope="module")
def comics() -> list[ComicBook]:
    """Every story with a title page, read from its ini file."""
    db = ComicsDatabase(for_building_comics=False)
    return [
        db.get_comic_book(title)
        for title in db.get_all_story_titles()
        if title not in _NO_TITLE_PAGE
    ]


@pytest.fixture(scope="module")
def empty_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("title-lines") / "empty.png"
    Image.new("RGB", (8, 8), "white").save(path)
    return path


class TestTheLineBreakRules:
    @pytest.mark.parametrize(
        "title",
        [
            "Hound\nof the\nMoaning Hills",
            "The Prize\nof\nPizarro",
            "Mystery\nof the\nSwamp",
            "The Day\nthe Mountain\nShook",  # "the" belongs to "Mountain"
            "The\nBear Tamer",
            "Lost in the Andes!",  # small words inside a line are fine
        ],
    )
    def test_a_well_broken_title_passes(self, title: str) -> None:
        assert _get_line_break_problems(title) == []

    @pytest.mark.parametrize(
        ("title", "problem"),
        [
            ("Hound of the\nMoaning Hills", 'ends on "the"'),
            ("The Prize\nof Pizarro", 'starts with "of"'),
            ("Mystery\nof\nthe Swamp", 'small line "of" is split from "the Swamp"'),
        ],
    )
    def test_a_badly_broken_title_is_caught(self, title: str, problem: str) -> None:
        problems = _get_line_break_problems(title)

        assert len(problems) == 1
        assert problem in problems[0]


class TestEveryStoryTitle:
    def test_the_titles_are_found(self, comics: list[ComicBook]) -> None:
        # Guards the tests below: with no titles they would pass vacuously.
        assert len(comics) > 400  # noqa: PLR2004

    def test_every_title_breaks_between_phrases(self, comics: list[ComicBook]) -> None:
        problems = [
            f"{comic.ini_file.name}: {problem}"
            for comic in comics
            for problem in _get_line_break_problems(comic.get_comic_title())
        ]

        assert not problems, "Title lines break the rules:\n" + "\n".join(problems)

    def test_every_title_line_fits_the_page(
        self, comics: list[ComicBook], empty_page: Path
    ) -> None:
        max_width = DEST_TARGET_WIDTH - (2 * _MIN_TITLE_MARGIN)
        too_wide = []
        for comic in comics:
            builder = ComicBookImageBuilder(comic, empty_page)
            texts, _, _ = builder._get_title_and_fonts()
            if len(texts) > 1:
                continue  # a "Comics and Stories" title: fixed pieces, not ini lines

            title = comic.get_comic_title()
            font = ImageFont.truetype(comic.title_font_file, comic.title_font_size)
            outline = builder._get_title_scaled(INTRO_TITLE_OUTLINE_WIDTH, font)
            width = builder._get_title_text_width(title, font) + (2 * outline)
            if width > max_width:
                too_wide.append(f"{comic.ini_file.name}: {width:.0f}px wide")

        assert not too_wide, (
            f"Title lines wider than {max_width}px (less than {_MIN_TITLE_MARGIN}px from"
            " the page edge): re-break them, or set a smaller title_font_size:\n"
            + "\n".join(too_wide)
        )
