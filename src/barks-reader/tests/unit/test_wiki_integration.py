"""Unit tests for the kivy-free wiki integration providers (barks_reader.core.wiki_integration).

These pin the CLAUDE.md wiki title convention as code: slug derivation, the
display-title -> canonical-title join, the story-page gate, the reverse join to
a wiki page path, and the table decoration from our own is_barks_title.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_reader.core.wiki_integration import (
    BarksTableRewriter,
    canonical_title,
    story_page_title,
    story_slug,
    wiki_page_for_title,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestStorySlug:
    def test_apostrophes_dropped_not_hyphenated(self) -> None:
        """Map "You Can't Guess!" -> you-cant-guess (apostrophe removed, not a hyphen)."""
        assert story_slug("You Can't Guess!") == "you-cant-guess"

    def test_curly_apostrophe_dropped(self) -> None:
        """A typographic apostrophe (U+2019) behaves like a straight one."""
        title = f"Ten Cents{chr(0x2019)} Worth of Trouble"
        assert story_slug(title) == "ten-cents-worth-of-trouble"

    def test_non_alphanumerics_collapse_to_single_hyphen(self) -> None:
        """Quotes and spaces become one hyphen; leading/trailing hyphens stripped."""
        assert story_slug('Adventure "Down Under"') == "adventure-down-under"
        assert story_slug("Ten-Dollar Dither") == "ten-dollar-dither"


class TestCanonicalTitle:
    def test_exact_canonical_form(self) -> None:
        """A canonical title string maps straight to its enum."""
        assert canonical_title("Lost in the Andes!") == Titles.LOST_IN_THE_ANDES
        assert canonical_title("No Such Story Ever") is None

    def test_quoted_display_form_tolerated(self) -> None:
        """Straight or curly double quotes in a display form are stripped for the join."""
        canonical = ENUM_TO_STR_TITLE[Titles.ADVENTURE_DOWN_UNDER]
        quoted = canonical.replace("Down Under", '"Down Under"')
        assert canonical_title(quoted) == Titles.ADVENTURE_DOWN_UNDER
        curly = canonical.replace("Down Under", "“Down Under”")
        assert canonical_title(curly) == Titles.ADVENTURE_DOWN_UNDER


class TestStoryPageTitle:
    def test_story_page_maps_to_enum(self, tmp_path: Path) -> None:
        """A concept/stories page with a canonical frontmatter title is a story page."""
        page = tmp_path / "okf" / "concept" / "stories" / "comics-and-stories" / "x.md"
        fm = {"title": "Lost in the Andes!"}
        assert story_page_title(fm, page) == Titles.LOST_IN_THE_ANDES

    def test_non_story_location_is_none(self, tmp_path: Path) -> None:
        """The same frontmatter outside concept/stories/ is not a story page."""
        page = tmp_path / "okf" / "reference" / "x.md"
        assert story_page_title({"title": "Lost in the Andes!"}, page) is None

    def test_unknown_or_missing_title_is_none(self, tmp_path: Path) -> None:
        """A non-canonical or absent frontmatter title never matches."""
        page = tmp_path / "okf" / "concept" / "stories" / "misc" / "x.md"
        assert story_page_title({"title": "Not a Barks Story"}, page) is None
        assert story_page_title({}, page) is None


class TestWikiPageForTitle:
    def test_reverse_join_finds_written_page(self, tmp_path: Path) -> None:
        """A written story page is found via series dir + canonical slug."""
        slug_dir = tmp_path / "concept" / "stories" / "donald-duck-adventures"
        slug_dir.mkdir(parents=True)
        page = slug_dir / "lost-in-the-andes.md"
        page.write_text("---\ntype: story\n---\nX", encoding="utf-8")
        assert wiki_page_for_title(tmp_path, Titles.LOST_IN_THE_ANDES) == page

    def test_unwritten_page_is_none(self, tmp_path: Path) -> None:
        """A known title whose wiki page does not exist yet yields None."""
        assert wiki_page_for_title(tmp_path, Titles.LOST_IN_THE_ANDES) is None


class TestBarksTableRewriter:
    def test_non_barks_title_parenthesized(self) -> None:
        """A non-Barks title in a Title column gains parentheses; Barks titles don't."""
        rewriter = BarksTableRewriter()
        non_barks = next(iter(rewriter._non_barks_titles))  # noqa: SLF001
        header, body = rewriter.rewrite(
            ["Title", "Date"], [[non_barks, "1944-06"], ["Lost in the Andes!", "1948-12"]]
        )
        assert header == ["Title", "Date"]
        assert body[0][0] == f"({non_barks})"
        assert body[1][0] == "Lost in the Andes!"

    def test_barks_flag_column_dropped_and_header_renamed(self) -> None:
        """The redundant "Barks?" column is dropped; "Issue date" renames to "Date"."""
        rewriter = BarksTableRewriter()
        header, body = rewriter.rewrite(
            ["Title", "Barks?", "Issue date"], [["Story A", "yes", "1944-06"]]
        )
        assert header == ["Title", "Date"]
        assert body == [["Story A", "1944-06"]]

    def test_wrap_widths_align_with_header(self) -> None:
        """Per-column wrap overrides align positionally; unknown columns get None."""
        rewriter = BarksTableRewriter()
        assert rewriter.wrap_widths(["Tag", "Story", "Title"]) == [20, 24, None]
