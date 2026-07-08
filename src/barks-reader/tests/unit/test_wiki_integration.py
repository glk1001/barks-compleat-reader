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
    title_can_have_wiki_page,
    tree_navigable_title,
    wiki_page_for_title,
    wiki_session_path,
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


class TestStoryPageTitleExtras:
    def test_extras_title_is_still_a_story_page(self, tmp_path: Path) -> None:
        """An Extras title (in ALL_FANTA_COMIC_BOOK_INFO) still passes the plain gate."""
        page = tmp_path / "okf" / "concept" / "stories" / "one-pagers" / "x.md"
        assert story_page_title({"title": "All One-Pagers"}, page) == Titles.ALL_ONE_PAGERS


class TestTreeNavigableTitle:
    def test_non_extras_title_is_navigable(self, tmp_path: Path) -> None:
        """A regular story title keeps its tree position, so it passes."""
        page = tmp_path / "okf" / "concept" / "stories" / "comics-and-stories" / "x.md"
        assert (
            tree_navigable_title({"title": "Lost in the Andes!"}, page) == Titles.LOST_IN_THE_ANDES
        )

    def test_extras_title_is_excluded(self, tmp_path: Path) -> None:
        """An Extras title has no chronological tree position, so it is gated out."""
        page = tmp_path / "okf" / "concept" / "stories" / "one-pagers" / "x.md"
        # story_page_title accepts it, tree_navigable_title must not.
        assert story_page_title({"title": "All One-Pagers"}, page) == Titles.ALL_ONE_PAGERS
        assert tree_navigable_title({"title": "All One-Pagers"}, page) is None

    def test_non_story_page_is_none(self, tmp_path: Path) -> None:
        """A page outside concept/stories/ is never tree-navigable."""
        page = tmp_path / "okf" / "reference" / "x.md"
        assert tree_navigable_title({"title": "Lost in the Andes!"}, page) is None


class TestTitleCanHaveWikiPage:
    def test_true_for_series_with_story_dir(self) -> None:
        """A title whose series has a story directory can have a wiki page location."""
        assert title_can_have_wiki_page(Titles.LOST_IN_THE_ANDES) is True

    def test_false_for_extras_series(self) -> None:
        """An Extras title has no story directory, so no page location can exist."""
        assert title_can_have_wiki_page(Titles.ALL_ONE_PAGERS) is False


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

    def test_gyro_title_found_in_fallback_misc_dir(self, tmp_path: Path) -> None:
        """A Gyro title filed under the second candidate dir ("misc") is still found."""
        # Gyro Gearloose story dirs are ("gyro-gearloose-stories", "misc"); the
        # page lives only in the fallback dir, so the first candidate misses.
        slug = story_slug(ENUM_TO_STR_TITLE[Titles.TRAPPED_LIGHTNING])
        fallback_dir = tmp_path / "concept" / "stories" / "misc"
        fallback_dir.mkdir(parents=True)
        page = fallback_dir / f"{slug}.md"
        page.write_text("X", encoding="utf-8")
        assert wiki_page_for_title(tmp_path, Titles.TRAPPED_LIGHTNING) == page


class TestWikiSessionPath:
    def test_name_is_keyed_by_bundle_digest(self, tmp_path: Path) -> None:
        """The session filename embeds a stable digest of the resolved bundle path."""
        app_data = tmp_path / "app"
        bundle = tmp_path / "okf-bundle"
        session = wiki_session_path(app_data, bundle)
        assert session.parent == app_data
        assert session.name.startswith("okf-reader-session-")
        assert session.suffix == ".json"
        # Stable across calls for the same bundle.
        assert wiki_session_path(app_data, bundle) == session

    def test_different_bundles_get_different_session_files(self, tmp_path: Path) -> None:
        """Opening a different bundle can never clobber another bundle's resume point."""
        app_data = tmp_path / "app"
        one = wiki_session_path(app_data, tmp_path / "bundle-a")
        two = wiki_session_path(app_data, tmp_path / "bundle-b")
        assert one != two


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
